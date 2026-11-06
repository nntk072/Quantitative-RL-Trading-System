from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from omegaconf import OmegaConf

from training.runner import feature_preparation
from training.runner.feature_csv_validation import validate_feature_csv_against_canonical


def test_split_feature_builder_passes_date_mask_to_builder_and_cache(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    index = pd.date_range("2025-12-30", periods=4, freq="D", tz="UTC")
    primary = pd.DataFrame({"close": [1.0, 2.0, 3.0, 4.0]}, index=index)
    secondary = primary.copy()
    cfg = OmegaConf.create({"features": {}})
    expected_mask = pd.Series([False, True, True, False], index=index)
    cache_path = tmp_path / "features.parquet"
    seen: dict[str, Any] = {}

    def fake_cache_path(*args: Any, **kwargs: Any) -> Path:
        seen["cache_mask"] = kwargs["train_mask"]
        seen["cache_secondary"] = kwargs["secondary"]
        return cache_path

    def fake_build_features(*args: Any, **kwargs: Any) -> pd.DataFrame:
        seen["build_mask"] = kwargs["train_mask"]
        seen["build_cache_path"] = kwargs["cache_path"]
        seen["force"] = kwargs["force"]
        return primary.assign(feature=0.0)

    monkeypatch.setattr(feature_preparation, "feature_cache_path", fake_cache_path)
    monkeypatch.setattr(feature_preparation, "build_features", fake_build_features)

    result = feature_preparation.build_split_scoped_features(
        primary,
        secondary=secondary,
        cfg=cfg,
        train_start="2025-12-31",
        train_end="2026-01-01",
        cache_dir=tmp_path,
        symbol="US100",
        force=True,
    )

    pd.testing.assert_series_equal(seen["cache_mask"], expected_mask)
    pd.testing.assert_series_equal(seen["build_mask"], expected_mask)
    assert seen["cache_secondary"] is secondary
    assert seen["build_cache_path"] == cache_path
    assert seen["force"] is True
    assert result.index.equals(index)


def test_split_feature_builder_requires_datetime_index() -> None:
    primary = pd.DataFrame({"close": [1.0]}, index=[0])

    with pytest.raises(TypeError, match="DatetimeIndex"):
        feature_preparation.build_split_scoped_features(
            primary,
            cfg=None,
            train_end="2025-12-31",
        )


def test_split_feature_builder_requires_symbol_when_caching(tmp_path: Path) -> None:
    index = pd.date_range("2025-12-31", periods=1, freq="D", tz="UTC")
    primary = pd.DataFrame({"close": [1.0]}, index=index)

    with pytest.raises(ValueError, match="symbol is required"):
        feature_preparation.build_split_scoped_features(
            primary,
            cfg=None,
            train_end="2025-12-31",
            cache_dir=tmp_path,
        )


def test_feature_csv_validator_accepts_csv_round_trip_values() -> None:
    index = pd.date_range("2025-12-31", periods=2, freq="min", tz="UTC")
    canonical = pd.DataFrame({"feature": [0.1234567890123, float("nan")]}, index=index)
    supplied = pd.DataFrame({"feature": [0.12345678901231, float("nan")]}, index=index)

    validate_feature_csv_against_canonical(supplied, canonical)


def test_feature_csv_validator_rejects_different_post_split_normalization() -> None:
    index = pd.DatetimeIndex(
        [
            "2025-12-31 23:59:00+00:00",
            "2026-01-01 00:00:00+00:00",
            "2026-01-01 00:01:00+00:00",
        ]
    )
    canonical = pd.DataFrame({"feature": [0.1, 0.2, 0.3]}, index=index)
    supplied = canonical.copy()
    supplied.iloc[-1, 0] = 0.7

    with pytest.raises(ValueError, match="train-scoped canonical build"):
        validate_feature_csv_against_canonical(supplied, canonical)
