"""Shared-data-ABI validation of a bundle's feature matrix, behind ``env.native_data_abi.enabled``.

When the flag is on, the environment builds a ``qrl_native.FeatureRowBlock`` from the shared
bundle arrays and checks that its values read back exactly as the bundle holds them. The block is
an ABI check at construction time. The step path still reads the NumPy arrays, so enabling the
flag does not change any result. Any refusal raises: nothing is filled, repaired, or silently
skipped. Feature values that are missing are NaN in the bundle and are carried as masked slots.

The flag defaults to off, so default behaviour and evidence are unchanged.
"""

from __future__ import annotations

import importlib
from typing import Any

import numpy as np

from .shared_bundle import BundleArrays

FEATURE_SET_ID = "features_num"
"""Feature-set identity of the bundle's numeric feature matrix (``features_num``)."""


def native_data_abi_enabled(cfg: Any) -> bool:
    """Return whether the flagged ABI check is enabled in a resolved configuration.

    Args:
        cfg: Resolved configuration mapping with an ``env`` section.

    Returns:
        ``True`` only when ``env.native_data_abi.enabled`` is set to true.
    """
    env = cfg.get("env", {}) if hasattr(cfg, "get") else {}
    section = env.get("native_data_abi", {}) if hasattr(env, "get") else {}
    return bool(section.get("enabled", False)) if hasattr(section, "get") else False


def build_native_feature_block(bundle: BundleArrays, session_indices: np.ndarray[Any, Any]) -> Any:
    """Validate a bundle's feature matrix through the shared data ABI.

    Args:
        bundle: Loaded shared bundle with ``bar_time_ns`` and ``features_num`` arrays and a manifest.
        session_indices: Row indices that are session-eligible (the NY eligibility mask).

    Returns:
        The validated ``qrl_native.FeatureRowBlock``.

    Raises:
        RuntimeError: If the native extension cannot be imported.
        ValueError: If identities, dtypes or shapes are not as the ABI requires, or if the native
            layer refuses the arrays (for example a non-finite present value).
    """
    try:
        qrl_native = importlib.import_module("qrl_native")
    except ImportError as error:
        raise RuntimeError(
            "env.native_data_abi.enabled requires the qrl_native extension on PYTHONPATH"
        ) from error

    manifest = bundle.manifest
    config = manifest.get("config", {})
    try:
        instrument_id = str(config["data"]["primary"])
    except (KeyError, TypeError) as error:
        raise ValueError("bundle manifest has no data.primary instrument identity") from error
    if not instrument_id.strip():
        raise ValueError("bundle manifest data.primary is empty")

    values = np.asarray(bundle.arrays[FEATURE_SET_ID])
    if values.ndim != 2 or values.dtype != np.float64:
        raise ValueError(
            f"{FEATURE_SET_ID} must be a float64 matrix, found dtype {values.dtype} shape {values.shape}"
        )
    event = np.ascontiguousarray(bundle.arrays["bar_time_ns"], dtype=np.int64)
    session = np.zeros(event.shape[0], dtype=np.uint8)
    session[np.asarray(session_indices, dtype=np.int64)] = 1
    values = np.ascontiguousarray(values)
    valid = np.ascontiguousarray(~np.isnan(values), dtype=np.uint8)

    block = qrl_native.FeatureRowBlock.from_columns(
        schema_id="feature-row.v1",
        instrument_id=instrument_id,
        feature_set_id=FEATURE_SET_ID,
        feature_version=str(manifest.get("bundle_version")),
        content_hash=str(manifest.get("key")),
        width=int(values.shape[1]),
        columns={
            "event_time_ns": event,
            "available_at_ns": event,
            "session_eligible": session,
            "values": values,
            "values_valid": valid,
        },
    )
    read_back = np.frombuffer(block.column("values"), dtype="<f8").reshape(values.shape)
    if not np.array_equal(read_back, values, equal_nan=True):
        raise ValueError("shared data ABI read-back differs from the bundle feature matrix")
    return block


__all__ = ["FEATURE_SET_ID", "build_native_feature_block", "native_data_abi_enabled"]
