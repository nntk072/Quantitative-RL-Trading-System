"""Content-hash feature cache and fit-scoped z-score tests (T-02.1 / T-02.4)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
from omegaconf import OmegaConf

import features.pipeline.feature_cache_identity as cache_identity
import features.pipeline.feature_matrix_builder as feature_matrix_builder
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


def test_swing_semantic_change_invalidates_v44_cache_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bars = _bars()
    cfg = _cfg()
    new_hash = feature_cache_content_hash(cfg, bars)

    monkeypatch.setattr(cache_identity, "FEATURE_CACHE_VERSION", "v44-wilder-adx")
    previous_hash = feature_cache_content_hash(cfg, bars)

    assert new_hash != previous_hash


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


def test_session_schedule_content_invalidates_feature_cache_identity(tmp_path: Path) -> None:
    bars = _bars(8)
    schedule_path = tmp_path / "sessions.csv"
    cfg = _cfg()
    OmegaConf.update(
        cfg,
        "data.session_schedule_file",
        str(schedule_path),
        force_add=True,
    )

    missing_hash = feature_cache_content_hash(cfg, bars)
    schedule_path.write_text("date,start,end\n2025-01-06,08:30,15:00\n", encoding="utf-8")
    first_content_hash = feature_cache_content_hash(cfg, bars)
    schedule_path.write_text("date,start,end\n2025-01-06,09:00,15:30\n", encoding="utf-8")
    changed_content_hash = feature_cache_content_hash(cfg, bars)

    assert first_content_hash != missing_hash
    assert changed_content_hash != first_content_hash


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
    cache_path = tmp_path / "features.parquet"
    training_features = build_features(
        primary,
        cfg=cfg,
        train_mask=train_mask,
        timeframe_bars={"D1": daily},
        cache_path=cache_path,
        fit_state_path=state_path,
        force=True,
    )
    cached_features = build_features(
        primary,
        cfg=cfg,
        train_mask=train_mask,
        timeframe_bars={"D1": daily},
        cache_path=cache_path,
        fit_state_path=state_path,
    )
    pd.testing.assert_frame_equal(training_features, cached_features, check_freq=False)
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
    missing_source_state = json.loads(json.dumps(state))
    del missing_source_state["stages"]["source:D1"]
    with pytest.raises(ValueError, match="missing source:D1 fit"):
        build_features(
            primary,
            cfg=cfg,
            timeframe_bars={"D1": daily},
            fitted_normalization_state=missing_source_state,
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
    missing_matrix_state = json.loads(json.dumps(state))
    del missing_matrix_state["stages"]["matrix"]
    with pytest.raises(ValueError, match="missing matrix fit"):
        build_features(
            primary,
            cfg=cfg,
            timeframe_bars={"D1": daily},
            fitted_normalization_state=missing_matrix_state,
            force=True,
        )
    validation_index = training_features.index[
        training_features.index.isin(primary.index[~train_mask])
    ]
    pd.testing.assert_frame_equal(
        live_features.loc[validation_index, training_features.columns],
        training_features.loc[validation_index],
        check_freq=False,
    )


def test_fitted_matrix_state_reuses_train_only_statistics_without_d1_source_fit(
    tmp_path: Path,
) -> None:
    bars = _bars(180)
    train_mask = pd.Series(np.arange(len(bars)) < 120, index=bars.index)
    cfg = _cfg()
    state_path = tmp_path / "fit-state.json"
    training_features = build_features(
        bars,
        cfg=cfg,
        train_mask=train_mask,
        fit_state_path=state_path,
        force=True,
    )
    state = json.loads(state_path.read_text(encoding="utf-8"))
    live_features = build_features(
        bars,
        cfg=cfg,
        fitted_normalization_state=state,
        force=True,
    )
    validation_index = training_features.index[
        train_mask.reindex(training_features.index).eq(False)
    ]

    pd.testing.assert_frame_equal(
        live_features.loc[validation_index],
        training_features.loc[validation_index],
        check_freq=False,
    )


def test_mtf_builder_skips_empty_optional_timeframe_blocks() -> None:
    primary = _bars(80)
    empty_m5 = pd.DataFrame(
        columns=["open", "high", "low", "close"],
        index=pd.DatetimeIndex([], tz="Etc/GMT-3"),
        dtype=float,
    )
    cfg = _cfg(
        htf_timeframes=["M5"],
        include_pd_context=True,
        order_blocks={"enabled": True, "timeframes": ["M5"]},
        liquidity={"enabled": True, "timeframes": ["M5"]},
        entry_ideas={"enabled": True, "timeframes": ["M5"]},
    )

    features = build_features(
        primary,
        cfg=cfg,
        timeframe_bars={"M5": empty_m5},
        force=True,
    )

    assert len(features) == len(primary)
    assert "atr_5" in features
    assert "M5_ob_bull_active" not in features
    assert "M5_sweep_high" not in features
    assert "M5_pd_swing_high_dist_atr" not in features
    assert "M5_swing_retracement_valid" not in features
    assert features.columns.is_unique


def test_mtf_builder_keeps_native_m1_blocks_and_aligns_configured_higher_timeframes() -> None:
    primary = _bars(240)
    secondary = _bars(240)
    cfg = _cfg(
        smt={"enabled": True, "timeframes": ["M1", "M5"]},
        liquidity={"enabled": True, "timeframes": ["M1", "M5"]},
    )

    features = build_features(primary, secondary=secondary, cfg=cfg, force=True)

    assert {"smt_corr", "M5_smt_corr", "M5_sweep_high", "M5_sweep_low"} <= set(
        map(str, features.columns)
    )
    assert not any(str(column).startswith("M1_") for column in features.columns)
    assert features.columns.is_unique


def test_feature_builder_requires_train_mask_when_persisting_fit_state(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="requires a training mask"):
        build_features(
            _bars(40),
            cfg=_cfg(),
            fit_state_path=tmp_path / "fit-state.json",
            force=True,
        )


def test_feature_builder_rejects_simultaneous_fit_state_input_and_output(tmp_path: Path) -> None:
    bars = _bars(40)
    with pytest.raises(ValueError, match="mutually exclusive"):
        build_features(
            bars,
            cfg=_cfg(),
            train_mask=pd.Series([True] * len(bars), index=bars.index),
            fit_state_path=tmp_path / "fit-state.json",
            fitted_normalization_state={},
            force=True,
        )


def test_feature_builder_rejects_duplicate_produced_column_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bars = _bars(40)
    cfg = _cfg(entry_ideas={"enabled": True, "timeframes": ["M1"]})

    def duplicate_idea_columns(features: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame(
            np.zeros((len(features), 2)), index=features.index, columns=["duplicate", "duplicate"]
        )

    monkeypatch.setattr(feature_matrix_builder, "build_entry_idea_features", duplicate_idea_columns)

    with pytest.raises(ValueError, match="feature builder produced duplicate column names"):
        build_features(bars, cfg=cfg, force=True)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("schema", "unsupported feature normalization state"),
        ("configuration", "does not match the effective configuration"),
        ("mode", "mode differs from the requested mode"),
        ("window", "window differs from the effective config"),
        ("stages", "must contain stage fits"),
        ("stage_shape", "stage 'matrix' is malformed"),
        ("stage_contract", "stage 'matrix' differs from the run fit contract"),
    ],
)
def test_feature_builder_rejects_incompatible_fitted_state_contracts(
    mutation: str, message: str
) -> None:
    cfg = _cfg()
    window = int(cfg.features.zscore_window)
    state: dict[str, Any] = {
        "schema": "feature-normalization-v1",
        "configuration_sha256": feature_matrix_builder._normalization_configuration_sha256(
            cfg, mode="legacy_masked_window", window=window
        ),
        "mode": "legacy_masked_window",
        "window": window,
        "stages": {"matrix": {"mode": "legacy_masked_window", "window": window}},
    }
    if mutation == "schema":
        state["schema"] = "unsupported"
    elif mutation == "configuration":
        state["configuration_sha256"] = "different"
    elif mutation == "mode":
        state["mode"] = "frozen_fold"
    elif mutation == "window":
        state["window"] = window + 1
    elif mutation == "stages":
        state["stages"] = []
    elif mutation == "stage_shape":
        state["stages"]["matrix"] = None
    else:
        state["stages"]["matrix"]["mode"] = "frozen_fold"

    with pytest.raises(ValueError, match=message):
        build_features(
            _bars(40),
            cfg=cfg,
            fitted_normalization_state=state,
            force=True,
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


def test_failed_feature_cache_rebuild_preserves_published_parquet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bars = _bars()
    cfg = _cfg()
    path = feature_cache_path(tmp_path, "US100", cfg, bars)
    build_features(bars, cfg=cfg, cache_path=path)
    original_parquet = path.read_bytes()
    original_hash = Path(str(path) + ".hash").read_bytes()

    def fail_after_partial_write(
        _frame: pd.DataFrame, destination: str | Path, **_kwargs: Any
    ) -> None:
        Path(destination).write_bytes(b"partial parquet")
        raise OSError("simulated interrupted cache write")

    monkeypatch.setattr(pd.DataFrame, "to_parquet", fail_after_partial_write)
    with pytest.raises(OSError, match="simulated interrupted cache write"):
        build_features(bars, cfg=cfg, cache_path=path, force=True)

    assert path.read_bytes() == original_parquet
    assert Path(str(path) + ".hash").read_bytes() == original_hash
    assert list(tmp_path.glob(f".{path.stem}.*{path.suffix}")) == []


def test_failed_feature_cache_marker_write_cannot_reuse_replaced_parquet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bars = _bars()
    changed_bars = bars.copy()
    changed_bars["close"] += 250.0
    cfg = _cfg()
    path = feature_cache_path(tmp_path, "US100", cfg, bars)
    original_features = build_features(bars, cfg=cfg, cache_path=path)
    original_parquet = path.read_bytes()

    def fail_marker_write(*_args: Any, **_kwargs: Any) -> None:
        raise OSError("simulated marker write failure")

    with monkeypatch.context() as patcher:
        patcher.setattr(feature_matrix_builder, "write_text_atomic", fail_marker_write)
        with pytest.raises(OSError, match="simulated marker write failure"):
            build_features(changed_bars, cfg=cfg, cache_path=path, force=True)

    assert path.read_bytes() != original_parquet
    assert not Path(str(path) + ".hash").exists()

    read_count = 0
    read_parquet = pd.read_parquet

    def track_cache_read(*args: Any, **kwargs: Any) -> pd.DataFrame:
        nonlocal read_count
        read_count += 1
        return read_parquet(*args, **kwargs)

    monkeypatch.setattr(pd, "read_parquet", track_cache_read)
    recovered = build_features(bars, cfg=cfg, cache_path=path)

    assert read_count == 0
    pd.testing.assert_frame_equal(recovered, original_features, check_freq=False)


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


def test_walkforward_feature_builder_rejects_empty_or_overlapping_fold_inputs(
    tmp_path: Path,
) -> None:
    primary = _bars(40)
    with pytest.raises(ValueError, match="nonempty, unique, ordered bars"):
        build_walkforward_fold_features(
            primary.iloc[:0],
            None,
            _cfg(),
            primary.iloc[:20],
            primary.iloc[20:30],
            tmp_path,
            "US100.cash",
        )

    with pytest.raises(ValueError, match="ordered and disjoint"):
        build_walkforward_fold_features(
            primary,
            None,
            _cfg(),
            primary.iloc[:20],
            primary.iloc[19:30],
            tmp_path,
            "US100.cash",
        )


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
