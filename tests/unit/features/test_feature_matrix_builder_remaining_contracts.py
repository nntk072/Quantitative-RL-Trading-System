"""Behavior contracts for assembled feature-matrix cache state."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from configuration import load_config
from features.pipeline.feature_matrix_builder import build_features


def _primary_with_daily_sessions() -> pd.DataFrame:
    starts = [
        pd.Timestamp("2025-01-06", tz="Etc/GMT-3") + pd.Timedelta(days=day, hours=16, minutes=30)
        for day in range(6)
    ]
    index = pd.DatetimeIndex(
        [
            timestamp
            for start in starts
            for timestamp in pd.date_range(start, periods=40, freq="min")
        ]
    )
    close = 20_000.0 + np.arange(len(index), dtype=float) * 0.25
    return pd.DataFrame(
        {
            "open": close - 0.2,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "tickvol": 100,
            "volume": 1000,
            "vol": 0,
            "spread": 0.6,
        },
        index=index,
    )


def _daily_bars(primary: pd.DataFrame) -> pd.DataFrame:
    return (
        primary.resample("1D")
        .agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "tickvol": "sum",
                "volume": "sum",
                "vol": "sum",
                "spread": "last",
            }
        )
        .dropna()
    )


def test_missing_cached_d1_fit_rebuilds_source_normalization_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    primary = _primary_with_daily_sessions()
    daily = _daily_bars(primary)
    cfg = load_config(config_path="config/base/default.yaml")
    cfg.features.htf_timeframes = ["D1"]
    cfg.features.normalize_d1_technical_on_source = True
    cfg.features.zscore_window = 3
    train_mask = pd.Series(np.arange(len(primary)) < 160, index=primary.index)
    cache_path = tmp_path / "features.parquet"
    fit_state_path = tmp_path / "normalization.json"

    original = build_features(
        primary,
        cfg=cfg,
        train_mask=train_mask,
        timeframe_bars={"D1": daily},
        cache_path=cache_path,
        fit_state_path=fit_state_path,
        force=True,
    )
    damaged_state: dict[str, Any] = json.loads(fit_state_path.read_text(encoding="utf-8"))
    assert "source:D1" in damaged_state["stages"]
    del damaged_state["stages"]["source:D1"]
    fit_state_path.write_text(json.dumps(damaged_state), encoding="utf-8")

    read_parquet = pd.read_parquet
    cache_reads = 0

    def count_cache_reads(*args: Any, **kwargs: Any) -> pd.DataFrame:
        nonlocal cache_reads
        cache_reads += 1
        return read_parquet(*args, **kwargs)

    monkeypatch.setattr(pd, "read_parquet", count_cache_reads)
    rebuilt = build_features(
        primary,
        cfg=cfg,
        train_mask=train_mask,
        timeframe_bars={"D1": daily},
        cache_path=cache_path,
        fit_state_path=fit_state_path,
    )

    repaired_state = json.loads(fit_state_path.read_text(encoding="utf-8"))
    assert cache_reads == 0
    assert "source:D1" in repaired_state["stages"]
    pd.testing.assert_frame_equal(rebuilt, original, check_freq=False)


def test_empty_secondary_timeframe_keeps_m1_smt_and_skips_only_that_htf_block() -> None:
    primary = _primary_with_daily_sessions()
    assert isinstance(primary.index, pd.DatetimeIndex)
    secondary = primary.copy()
    secondary["close"] = secondary["close"] + np.sin(np.arange(len(secondary)))
    empty_m5 = pd.DataFrame(
        columns=["open", "high", "low", "close"],
        index=pd.DatetimeIndex([], tz=primary.index.tz),
        dtype=float,
    )
    cfg = load_config(config_path="config/base/default.yaml")
    cfg.features.htf_timeframes = []
    cfg.features.structure.enabled = False
    cfg.features.smt.enabled = True
    cfg.features.smt.timeframes = ["M1", "M5"]
    cfg.features.zscore_window = 10

    features = build_features(
        primary,
        secondary=secondary,
        cfg=cfg,
        secondary_timeframe_bars={"M5": empty_m5},
        force=True,
    )

    assert "smt_corr" in features
    assert "M5_smt_corr" not in features
    assert not any(str(column).startswith("M1_") for column in features.columns)
