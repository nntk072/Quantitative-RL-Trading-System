"""Content-hash feature cache and fit-scoped z-score tests (T-02.1 / T-02.4)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
from omegaconf import OmegaConf

from features import (
    build_features,
    build_walkforward_fold_features,
    feature_cache_content_hash,
    feature_cache_path,
)
from features.pipeline.normalization import rolling_zscore


def _bars(n: int = 400) -> pd.DataFrame:
    idx = pd.date_range("2025-01-06 01:05", periods=n, freq="1min", tz="Etc/GMT-3")
    rng = np.random.default_rng(0)
    close = 20000.0 + np.cumsum(rng.normal(0, 2, n))
    return pd.DataFrame(
        {
            "open": close - 0.5,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "tickvol": rng.integers(10, 200, n),
            "volume": rng.integers(1000, 5000, n),
            "vol": np.zeros(n, dtype=int),
            "spread": np.full(n, 0.6),
            "gap_flag": False,
            "session_id": 0,
        },
        index=idx,
    )


def _cfg(**feature_overrides: Any) -> Any:
    base: dict[str, Any] = {
        "data": {"tz": "Etc/GMT-3"},
        "session": {"tz": "Etc/GMT-3"},
        "features": {
            "ema_periods": [9, 13],
            "rsi_period": 14,
            "macd_fast": 12,
            "macd_slow": 26,
            "macd_signal": 9,
            "atr_period": 14,
            "adx_period": 14,
            "bb_period": 20,
            "bb_std": 2.0,
            "stoch_k": 14,
            "stoch_d": 3,
            "vwap_session": False,
            "return_horizons": [1, 5],
            "realized_vol_period": 20,
            "smt_swing_period": 5,
            "smt_corr_window": 20,
            "zscore_window": 50,
            "htf_timeframes": [],
            "include_po3": False,
            "include_fvg_ifvg": False,
            "include_po3_full": False,
            "include_strategy_state": False,
            "include_session_ohlc": False,
            "include_pd_context": False,
        },
    }
    base["features"].update(feature_overrides)
    return OmegaConf.create(base)


def test_cache_hash_changes_when_feature_flag_flips() -> None:
    bars = _bars()
    cfg_a = _cfg(include_po3=False)
    cfg_b = _cfg(include_po3=True)
    assert feature_cache_content_hash(cfg_a, bars) != feature_cache_content_hash(cfg_b, bars)


def test_d1_source_normalization_flag_has_distinct_cache_identity() -> None:
    bars = _bars()
    historical = _cfg()
    explicit_default = _cfg(normalize_d1_technical_on_source=False)
    treatment = _cfg(normalize_d1_technical_on_source=True)

    assert feature_cache_content_hash(historical, bars) == feature_cache_content_hash(
        explicit_default, bars
    )
    assert feature_cache_content_hash(historical, bars) != feature_cache_content_hash(
        treatment, bars
    )


def test_d1_technical_features_are_normalized_before_m1_alignment() -> None:
    day_starts = pd.date_range("2025-01-06 16:30", periods=12, freq="D", tz="Etc/GMT-3")
    m1_index = pd.DatetimeIndex(
        [day + pd.Timedelta(minutes=minute) for day in day_starts for minute in range(10)]
    )
    m1_close = 20_000.0 + np.cumsum(np.random.default_rng(13).normal(0.0, 2.0, len(m1_index)))
    primary = pd.DataFrame(
        {
            "open": m1_close - 0.5,
            "high": m1_close + 1.0,
            "low": m1_close - 1.0,
            "close": m1_close,
            "tickvol": 100,
            "volume": 1000,
            "vol": 0,
            "spread": 0.6,
        },
        index=m1_index,
    )
    daily_index = pd.date_range("2025-01-06", periods=16, freq="D", tz="Etc/GMT-3")
    daily_close = 20_000.0 + np.cumsum(
        np.random.default_rng(21).normal(0.0, 35.0, len(daily_index))
    )
    daily = pd.DataFrame(
        {
            "open": daily_close - 3.0,
            "high": daily_close + 8.0,
            "low": daily_close - 8.0,
            "close": daily_close,
            "tickvol": 1000,
            "volume": 10000,
            "vol": 0,
            "spread": 0.6,
        },
        index=daily_index,
    )
    cfg = _cfg(
        htf_timeframes=["D1"],
        zscore_window=3,
        normalize_d1_technical_on_source=True,
    )
    train_mask = pd.Series(np.arange(len(primary)) < 90, index=primary.index)

    features = build_features(
        primary,
        cfg=cfg,
        train_mask=train_mask,
        timeframe_bars={"D1": daily},
        force=True,
    )

    same_session = features.loc["2025-01-15 16:35":"2025-01-15 16:39", "D1_ret_5"]
    assert same_session.notna().all()
    assert same_session.nunique() == 1

    future_changed = daily.copy()
    future_changed.loc["2025-01-15":, ["open", "high", "low", "close"]] *= 10.0
    poisoned = build_features(
        primary,
        cfg=cfg,
        train_mask=train_mask,
        timeframe_bars={"D1": future_changed},
        force=True,
    )
    pd.testing.assert_series_equal(
        same_session,
        poisoned.loc["2025-01-15 16:35":"2025-01-15 16:39", "D1_ret_5"],
    )


def test_live_feature_rebuild_reuses_both_training_normalization_stages(
    tmp_path: Path,
) -> None:
    primary = _bars(240)
    daily_sessions = [
        pd.date_range(
            pd.Timestamp("2025-01-06", tz="Etc/GMT-3")
            + pd.Timedelta(days=day)
            + pd.Timedelta(hours=16, minutes=30),
            periods=40,
            freq="1min",
        )
        for day in range(6)
    ]
    primary.index = pd.DatetimeIndex([timestamp for index in daily_sessions for timestamp in index])
    daily = (
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
    cfg = _cfg(
        htf_timeframes=["D1"],
        zscore_window=3,
        normalize_d1_technical_on_source=True,
    )
    train_mask = pd.Series(np.arange(len(primary)) < 160, index=primary.index)
    state_path = tmp_path / "feature_normalization_state.json"
    training_features = build_features(
        primary,
        cfg=cfg,
        train_mask=train_mask,
        timeframe_bars={"D1": daily},
        fit_state_path=state_path,
        force=True,
    )
    state = json.loads(state_path.read_text(encoding="utf-8"))
    mismatched_stage_state = json.loads(json.dumps(state))
    mismatched_stage_state["stages"]["matrix"]["window"] += 1
    with pytest.raises(ValueError, match="differs from the run fit contract"):
        build_features(
            primary,
            cfg=cfg,
            timeframe_bars={"D1": daily},
            fitted_normalization_state=mismatched_stage_state,
            force=True,
        )
    live_features = build_features(
        primary,
        cfg=cfg,
        timeframe_bars={"D1": daily},
        fitted_normalization_state=state,
        force=True,
    )

    assert "source:D1" in state["stages"]
    validation_index = training_features.index[
        training_features.index.isin(primary.index[~train_mask])
    ]
    pd.testing.assert_frame_equal(
        live_features.loc[validation_index, training_features.columns],
        training_features.loc[validation_index],
        check_freq=False,
    )


def test_feature_cache_hit_and_miss(tmp_path: Path) -> None:
    bars = _bars()
    cfg = _cfg()
    path = feature_cache_path(tmp_path, "US100", cfg, bars)
    feat1 = build_features(bars, cfg=cfg, cache_path=path)
    mtime1 = path.stat().st_mtime_ns
    feat2 = build_features(bars, cfg=cfg, cache_path=path)
    assert path.stat().st_mtime_ns == mtime1
    pd.testing.assert_frame_equal(feat1, feat2, check_freq=False)

    cfg2 = _cfg(rsi_period=21)
    path2 = feature_cache_path(tmp_path, "US100", cfg2, bars)
    assert path2 != path
    build_features(bars, cfg=cfg2, cache_path=path2)
    assert path2.exists()


def test_cache_rebuilds_missing_fit_state_and_reuses_matching_state(tmp_path: Path) -> None:
    bars = _bars(180)
    train_mask = pd.Series(np.arange(len(bars)) < 120, index=bars.index)
    cfg = _cfg()
    cache_path = feature_cache_path(tmp_path, "US100", cfg, bars, train_mask=train_mask)
    state_path = Path(str(cache_path) + ".normalization.json")

    first = build_features(
        bars,
        cfg=cfg,
        train_mask=train_mask,
        cache_path=cache_path,
        fit_state_path=state_path,
    )
    state_bytes = state_path.read_bytes()
    cache_mtime = cache_path.stat().st_mtime_ns
    cached = build_features(
        bars,
        cfg=cfg,
        train_mask=train_mask,
        cache_path=cache_path,
        fit_state_path=state_path,
    )
    assert state_path.read_bytes() == state_bytes
    assert cache_path.stat().st_mtime_ns == cache_mtime
    pd.testing.assert_frame_equal(first, cached, check_freq=False)

    state_path.unlink()
    rebuilt = build_features(
        bars,
        cfg=cfg,
        train_mask=train_mask,
        cache_path=cache_path,
        fit_state_path=state_path,
    )
    assert state_path.is_file()
    pd.testing.assert_frame_equal(first, rebuilt, check_freq=False)

    corrupted_state = json.loads(state_path.read_text(encoding="utf-8"))
    corrupted_state["stages"]["matrix"]["mean"].pop(
        corrupted_state["stages"]["matrix"]["columns"][0]
    )
    state_path.write_text(json.dumps(corrupted_state), encoding="utf-8")
    repaired = build_features(
        bars,
        cfg=cfg,
        train_mask=train_mask,
        cache_path=cache_path,
        fit_state_path=state_path,
    )
    repaired_state = json.loads(state_path.read_text(encoding="utf-8"))
    assert len(repaired_state["stages"]["matrix"]["mean"]) == len(
        repaired_state["stages"]["matrix"]["columns"]
    )
    pd.testing.assert_frame_equal(first, repaired, check_freq=False)


def test_fit_scoped_zscore_ignores_future_poison() -> None:
    """With train_mask, future spikes must not change train-window z-scores."""
    n = 200
    idx = pd.date_range("2025-01-01", periods=n, freq="1min", tz="UTC")
    values = np.linspace(0.0, 1.0, n)
    df = pd.DataFrame({"x": values}, index=idx)
    train_mask = pd.Series(np.arange(n) < 100, index=idx)

    clean = rolling_zscore(df, window=20, train_mask=train_mask)
    poisoned = df.copy()
    poisoned.iloc[150:, 0] = 1e6
    scoped = rolling_zscore(poisoned, window=20, train_mask=train_mask)
    pd.testing.assert_series_equal(
        clean.loc[train_mask, "x"],
        scoped.loc[train_mask, "x"],
        check_names=False,
    )
    # Test-side values under train_mask are frozen via ffill of train stats:
    # a late spike must not move the first post-train z-score.
    first_test = ~train_mask
    assert np.isfinite(scoped.loc[first_test, "x"].iloc[0])
    assert scoped.loc[first_test, "x"].iloc[0] == clean.loc[first_test, "x"].iloc[0]


def test_fold_cache_separates_normalization_conventions() -> None:
    bars = _bars(180)
    mask = pd.Series(np.arange(len(bars)) < 100, index=bars.index)
    legacy = feature_cache_content_hash(_cfg(), bars, train_mask=mask)
    frozen = feature_cache_content_hash(
        _cfg(), bars, train_mask=mask, normalization_mode="frozen_fold"
    )
    assert frozen != legacy


def test_walkforward_fold_rebuilds_using_only_fold_train_fit(tmp_path: Path) -> None:
    bars = _bars(400)
    secondary = _bars(400)
    secondary.loc[:, ["open", "high", "low", "close"]] += 3_000.0
    train = bars.iloc[:220]
    validation = bars.iloc[245:310]
    cfg = _cfg()
    fitted_train, fitted_val, cache_path = build_walkforward_fold_features(
        bars, secondary, cfg, train, validation, tmp_path, "US100"
    )
    assert cache_path.exists()
    assert fitted_train.index.equals(train.index)
    assert fitted_val.index.equals(validation.index)

    # The later-fold training period is extreme; it must not influence the
    # fit of an earlier fold, even when supplied in the primary data frame.
    altered = bars.copy()
    altered.loc[altered.index[310:], "close"] *= 50
    altered.loc[altered.index[310:], "open"] *= 50
    altered.loc[altered.index[310:], "high"] *= 50
    altered.loc[altered.index[310:], "low"] *= 50
    altered_secondary = secondary.copy()
    altered_secondary.loc[altered_secondary.index[310:], "close"] *= 50
    altered_secondary.loc[altered_secondary.index[310:], "open"] *= 50
    altered_secondary.loc[altered_secondary.index[310:], "high"] *= 50
    altered_secondary.loc[altered_secondary.index[310:], "low"] *= 50
    other_train, other_val, other_cache = build_walkforward_fold_features(
        altered, altered_secondary, cfg, train, validation, tmp_path, "US100"
    )
    pd.testing.assert_frame_equal(fitted_train, other_train, check_freq=False)
    pd.testing.assert_frame_equal(fitted_val, other_val, check_freq=False)
    assert other_cache == cache_path

    # A secondary-symbol validation shock is allowed to affect validation
    # features, but it must not alter the earlier fold's fitted/training view.
    validation_poisoned_secondary = secondary.copy()
    validation_poisoned_secondary.loc[validation.index[0] :, ["open", "high", "low", "close"]] *= (
        1.5
    )
    validation_poison_train, _, validation_poison_cache = build_walkforward_fold_features(
        bars,
        validation_poisoned_secondary,
        cfg,
        train,
        validation,
        tmp_path,
        "US100",
    )
    pd.testing.assert_frame_equal(fitted_train, validation_poison_train, check_freq=False)
    assert validation_poison_cache != cache_path

    # Changing which observations belong to the fold changes fitted state
    # and the cache identity even though the bars are identical.
    wider_train = bars.iloc[:235]
    _, _, wider_cache = build_walkforward_fold_features(
        bars, None, cfg, wider_train, validation, tmp_path, "US100"
    )
    assert wider_cache != cache_path
