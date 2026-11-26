"""Flagged shared-data-ABI check of a bundle's feature matrix (SHARED-DATA-ABI).

The check runs only when ``env.native_data_abi.enabled`` is true. It must read back exactly what
the bundle holds and must refuse anything the ABI refuses, with no fill or repair.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from types import MappingProxyType
from typing import Any

import numpy as np
import pytest

from simulation.environment.env import TradingEnv
from simulation.environment.native_feature_block import (
    build_native_feature_block,
    native_data_abi_enabled,
)
from simulation.environment.shared_bundle import BundleArrays

T0 = 1_700_000_000_000_000_000
MINUTE = 60_000_000_000


def _bundle(
    features: np.ndarray[Any, Any] | None = None,
    *,
    primary: str | None = "US100.cash",
    dtype: Any = np.float64,
) -> BundleArrays:
    rows = 5
    values = np.full((rows, 2), 0.5) if features is None else features
    values = values.astype(dtype, copy=True)
    values[0] = np.nan  # warm-up row: missing, stored as NaN
    config: dict[str, Any] = {"data": {"primary": primary}} if primary is not None else {"data": {}}
    manifest = {"bundle_version": 7, "key": "bundle-key-1", "config": config}
    arrays = {
        "bar_time_ns": T0 + np.arange(rows, dtype=np.int64) * MINUTE,
        "features_num": values,
    }
    return BundleArrays(
        path=Path("unused-bundle"),
        arrays=MappingProxyType(arrays),
        manifest=MappingProxyType(manifest),
    )


def _native() -> Any:
    return pytest.importorskip("qrl_native")


def test_flag_is_off_unless_explicitly_enabled() -> None:
    assert native_data_abi_enabled({}) is False
    assert native_data_abi_enabled({"env": {}}) is False
    assert native_data_abi_enabled({"env": {"native_data_abi": {"enabled": False}}}) is False
    assert native_data_abi_enabled({"env": {"native_data_abi": {"enabled": True}}}) is True


def test_environment_exposes_the_flag_with_default_off() -> None:
    parameter = inspect.signature(TradingEnv.__init__).parameters["native_data_abi"]
    assert parameter.default is False


def test_block_reads_back_the_bundle_matrix_with_its_identities() -> None:
    _native()
    bundle = _bundle()
    block = build_native_feature_block(bundle, np.array([1, 2, 3]))
    assert block.rows == 5
    assert block.width == 2
    assert block.feature_set_id == "features_num"
    values = np.frombuffer(block.column("values"), dtype="<f8").reshape(5, 2)
    assert np.isnan(values[0]).all()
    assert np.array_equal(values[1:], bundle.arrays["features_num"][1:])
    session = np.frombuffer(block.column("session_eligible"), dtype="u1")
    assert session.tolist() == [0, 1, 1, 1, 0]


def test_non_finite_present_feature_is_refused_not_treated_as_missing() -> None:
    _native()
    features = np.full((5, 2), 0.5)
    features[2, 1] = np.inf
    with pytest.raises(ValueError, match=r"values\[2\]: present values must be finite"):
        build_native_feature_block(_bundle(features), np.array([1, 2]))


def test_float32_feature_matrix_is_refused_rather_than_converted() -> None:
    _native()
    with pytest.raises(ValueError, match="must be a float64 matrix"):
        build_native_feature_block(_bundle(dtype=np.float32), np.array([1]))


def test_missing_instrument_identity_is_refused() -> None:
    _native()
    with pytest.raises(ValueError, match="data.primary"):
        build_native_feature_block(_bundle(primary=None), np.array([1]))


def test_missing_extension_is_a_clear_runtime_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib

    real_import_module = importlib.import_module

    def blocked(name: str, package: str | None = None) -> Any:
        if name == "qrl_native":
            raise ImportError("blocked for the test")
        return real_import_module(name, package)

    monkeypatch.setattr(importlib, "import_module", blocked)
    with pytest.raises(RuntimeError, match="requires the qrl_native extension"):
        build_native_feature_block(_bundle(), np.array([1]))
