"""Chain A tests: per-timeframe technical features are causally aligned.

M1 bar t sees only completed HTF candles (one-period shift before ffill).
"""

from __future__ import annotations

from typing import Any, cast

import numpy as np
import pandas as pd
import pytest
from omegaconf import OmegaConf

from features import build_features
from features.technical.indicators import build_indicators
from market_data.transforms.resample import resample

HTF_TFS = ["M3", "M5", "M10", "M15", "M30", "H1", "H4", "D1"]


@pytest.fixture
def feat_cfg():
    """Minimal features config matching config/default.yaml keys."""
    return OmegaConf.create(
        {
            "ema_periods": [9, 21, 50, 200],
            "macd_fast": 12,
            "macd_slow": 26,
            "macd_signal": 9,
            "rsi_period": 14,
            "atr_period": 14,
            "adx_period": 14,
            "bb_period": 20,
            "bb_std": 2.0,
            "stoch_k": 14,
            "stoch_d": 3,
            "return_horizons": [1, 5],
            "realized_vol_period": 20,
            "smt_swing_period": 5,
            "smt_corr_window": 20,
            "zscore_window": 100,
            "htf_timeframes": HTF_TFS,
        }
    )


def _expected_htf_value(
    tf: str, col: str, t: pd.Timestamp, m1_bars: pd.DataFrame, feat_cfg
) -> float:
    """Value M1 t should see: last HTF bar that has already completed by t."""
    htf = build_indicators(resample(m1_bars, tf), feat_cfg)  # type: ignore[arg-type]
    completed = htf.shift(1)
    eligible = completed.loc[completed.index <= t]
    assert not eligible.empty, f"no completed {tf} bar at or before {t}"
    return float(eligible[col].iloc[-1])


def test_htf_columns_present(m1_bars, feat_cfg):
    feat = build_features(m1_bars, cfg=OmegaConf.create({"features": feat_cfg}))
    for tf in HTF_TFS:
        htf_cols = [c for c in feat.columns if str(c).startswith(f"{tf}_")]
        assert htf_cols, f"no {tf}_* columns in feature matrix"
        for native in [
            "ema_9",
            "ema_21",
            "ema_50",
            "ema_200",
            "rsi",
            "macd",
            "macd_signal",
            "macd_hist",
        ]:
            assert f"{tf}_{native}" in [str(c) for c in feat.columns]


def test_order_blocks_are_built_for_primary_and_configured_timeframes(m1_bars, feat_cfg):
    all_timeframes = ["M1", *HTF_TFS]
    config = OmegaConf.create(
        {
            "features": {
                **cast(dict[str, Any], OmegaConf.to_container(feat_cfg, resolve=True)),
                "order_blocks": {
                    "enabled": True,
                    "timeframes": all_timeframes,
                    "swing_period": 3,
                    "impulse_atr": 0.0,
                },
            }
        }
    )

    features = build_features(m1_bars, cfg=config)

    for timeframe in all_timeframes:
        prefix = "" if timeframe == "M1" else f"{timeframe}_"
        assert f"{prefix}ob_bull_active" in features.columns
        assert f"{prefix}ob_bear_retest" in features.columns
        assert f"{prefix}ob_bull_low" in features.columns
    assert "po3_distribution" not in features.columns


def test_order_block_mtf_signal_is_visible_at_source_close(feat_cfg) -> None:
    """An M5 order-block event reaches M1 only at the source bar close."""
    start = pd.Timestamp("2025-01-06 16:30", tz="Etc/GMT-3")
    source_index = pd.date_range(start, periods=50, freq="5min")
    close = np.full(len(source_index), 100.0)
    open_price = close.copy()
    high = close + 0.5
    low = close - 0.5

    # The confirmed high at 12 is broken at 20; bar 19 is the opposing
    # candle selected as the bullish block's origin.
    high[12], low[12] = 105.0, 99.0
    open_price[19], close[19], high[19], low[19] = 104.5, 104.0, 105.0, 103.5
    open_price[20], close[20], high[20], low[20] = 104.0, 108.0, 109.0, 103.8
    source_bars = pd.DataFrame(
        {"open": open_price, "high": high, "low": low, "close": close},
        index=source_index,
    )

    m1_index = pd.date_range(start, periods=250, freq="1min")
    m1_bars = pd.DataFrame(
        {
            "open": np.full(len(m1_index), 100.0),
            "high": np.full(len(m1_index), 100.5),
            "low": np.full(len(m1_index), 99.5),
            "close": np.full(len(m1_index), 100.0),
            "tickvol": np.ones(len(m1_index)),
            "volume": np.ones(len(m1_index)),
        },
        index=m1_index,
    )
    feature_values = cast(dict[str, Any], OmegaConf.to_container(feat_cfg, resolve=True))
    config = OmegaConf.create(
        {
            "features": {
                **feature_values,
                "htf_timeframes": ["M5"],
                "order_blocks": {
                    "enabled": True,
                    "timeframes": ["M5"],
                    "swing_period": 3,
                    "impulse_atr": 0.0,
                },
            }
        }
    )

    full = build_features(m1_bars, cfg=config, timeframe_bars={"M5": source_bars})
    source_close = source_index[20] + pd.Timedelta(minutes=5)
    before_close = source_close - pd.Timedelta(minutes=1)

    assert full.loc[before_close, "M5_ob_bull_new"] == 0.0
    assert full.loc[before_close, "M5_ob_bull_active"] == 0.0
    assert full.loc[source_close, "M5_ob_bull_new"] == 1.0
    assert full.loc[source_close, "M5_ob_bull_active"] == 1.0
    assert full.loc[source_close + pd.Timedelta(minutes=5), "M5_ob_bull_new"] == 0.0

    prefix_end = source_close + pd.Timedelta(minutes=2)
    prefix = build_features(
        m1_bars.loc[:prefix_end],
        cfg=config,
        timeframe_bars={"M5": source_bars.loc[: source_index[20]]},
    )
    pd.testing.assert_series_equal(
        full.loc[:prefix_end, "M5_ob_bull_new"],
        prefix["M5_ob_bull_new"],
        check_names=True,
    )


def test_build_features_uses_supplied_native_timeframe_bars(m1_bars, feat_cfg) -> None:
    feature_config = cast(dict[str, Any], OmegaConf.to_container(feat_cfg, resolve=True))
    cfg = OmegaConf.create({"features": {**feature_config, "htf_timeframes": ["M3"]}})
    native_m3 = resample(m1_bars, "M3")
    native_close = np.where(np.arange(len(native_m3)) % 2, 250.0, 150.0)
    native_m3 = native_m3.copy()
    native_m3["open"] = native_close
    native_m3["high"] = native_close + 1.0
    native_m3["low"] = native_close - 1.0
    native_m3["close"] = native_close

    resampled_features = build_features(m1_bars, cfg=cfg)
    native_features = build_features(m1_bars, cfg=cfg, timeframe_bars={"M3": native_m3})

    valid = resampled_features["M3_ema_9"].notna() & native_features["M3_ema_9"].notna()
    assert valid.any()
    assert not np.allclose(
        resampled_features.loc[valid, "M3_ema_9"].to_numpy(),
        native_features.loc[valid, "M3_ema_9"].to_numpy(),
    )


def test_align_timeframes_completed_bar():
    """M1 during a forming H1 bar must not see that H1's final OHLC."""
    from market_data.transforms.align import align_timeframes

    idx = pd.date_range("2025-01-06 16:00", periods=120, freq="1min", tz="Etc/GMT-3")
    close = np.arange(120, dtype=float)
    m1 = pd.DataFrame(
        {"open": close, "high": close + 1, "low": close - 1, "close": close, "v": close},
        index=idx,
    )
    h1 = m1.resample("1h", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "v": "last"}
    )
    aligned = align_timeframes(m1[["v"]], {"H1": h1[["close"]]})
    t1630 = pd.Timestamp("2025-01-06 16:30", tz="Etc/GMT-3")
    t17 = pd.Timestamp("2025-01-06 17:00", tz="Etc/GMT-3")
    hour_16 = pd.Timestamp("2025-01-06 16:00", tz="Etc/GMT-3")
    hour_16_close = float(h1["close"].loc[hour_16])
    assert (
        pd.isna(aligned.loc[t1630, "H1_close"]) or aligned.loc[t1630, "H1_close"] != hour_16_close
    )
    assert aligned.loc[t17, "H1_close"] == pytest.approx(hour_16_close)


def test_align_timeframes_uses_explicit_close_times_for_short_final_bar() -> None:
    from market_data.transforms.align import align_timeframes

    tz = "Etc/GMT-3"
    m1_idx = pd.date_range("2025-01-06 16:32", periods=4, freq="1min", tz=tz)
    htf_idx = pd.DatetimeIndex(
        [pd.Timestamp("2025-01-06 16:30", tz=tz), pd.Timestamp("2025-01-06 16:33", tz=tz)]
    )
    m1 = pd.DataFrame({"close": [1.0, 2.0, 3.0, 4.0]}, index=m1_idx)
    htf_features = pd.DataFrame({"signal": [10.0, 20.0]}, index=htf_idx)
    close_times = pd.Series(
        [pd.Timestamp("2025-01-06 16:33", tz=tz), pd.Timestamp("2025-01-06 16:35", tz=tz)],
        index=htf_idx,
    )

    aligned = align_timeframes(
        m1,
        {"M3": htf_features},
        availability_times={"M3": close_times},
    )

    assert pd.isna(aligned.loc[pd.Timestamp("2025-01-06 16:32", tz=tz), "M3_signal"])
    assert aligned.loc[pd.Timestamp("2025-01-06 16:33", tz=tz), "M3_signal"] == 10.0
    assert aligned.loc[pd.Timestamp("2025-01-06 16:34", tz=tz), "M3_signal"] == 10.0
    assert aligned.loc[pd.Timestamp("2025-01-06 16:35", tz=tz), "M3_signal"] == 20.0


def test_htf_alignment_causal_open_time(m1_bars, feat_cfg):
    """Feature at bar t equals the HTF value from the last completed HTF bar."""
    from market_data.transforms.align import align_timeframes

    for tf in HTF_TFS:
        htf = build_indicators(resample(m1_bars, tf), feat_cfg)  # type: ignore[arg-type]
        aligned = align_timeframes(m1_bars[["close"]], {tf: htf[["ema_9"]]})[f"{tf}_ema_9"]
        for t in m1_bars.index[300::100]:
            expected = _expected_htf_value(tf, "ema_9", t, m1_bars, feat_cfg)
            if np.isnan(expected):
                continue
            assert abs(aligned.loc[t] - expected) < 1e-9, (
                f"{tf} value at {t} not from last completed bar"
            )


def test_htf_future_invariance(m1_bars, feat_cfg):
    """Truncating future M1 bars must not change past HTF feature values."""
    cfg_full = OmegaConf.create({"features": feat_cfg})
    feat_full = build_features(m1_bars, cfg=cfg_full)
    feat_trunc = build_features(m1_bars.iloc[:400], cfg=cfg_full)

    overlap = feat_trunc.index[:250]
    htf_cols = [c for c in feat_full.columns if any(str(c).startswith(f"{tf}_") for tf in HTF_TFS)]
    pd.testing.assert_frame_equal(
        feat_full.loc[overlap, htf_cols],
        feat_trunc.loc[overlap, htf_cols],
        rtol=1e-9,
    )


def test_htf_disabled_when_empty(m1_bars, feat_cfg):
    """Empty htf_timeframes must reproduce the M1-only feature matrix."""
    cfg = feat_cfg.copy()
    OmegaConf.set_struct(cfg, False)
    cfg.htf_timeframes = []
    feat = build_features(m1_bars, cfg=OmegaConf.create({"features": cfg}))
    assert not any(str(c).startswith(tuple(HTF_TFS)) for c in feat.columns)


def test_mtf_features_use_only_completed_htf_bars(m1_bars, feat_cfg):
    test_htf_alignment_causal_open_time(m1_bars, feat_cfg)  # type: ignore[no-untyped-call]
