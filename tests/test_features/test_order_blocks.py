"""Causality and context requirements for the order-block feature."""

from __future__ import annotations

import numpy as np
import pandas as pd

from features.context.order_blocks import build_order_block_features


def _bars(n: int) -> pd.DataFrame:
    index = pd.date_range("2025-01-06 09:00", periods=n, freq="1min", tz="UTC")
    close = np.full(n, 100.0)
    open_price = close.copy()
    high = close + 0.5
    low = close - 0.5
    if n > 25:
        # A confirmed wick high at bar 12 is broken by bullish displacement at
        # bar 20. Bar 19 is the last opposing candle and becomes the OB source.
        high[12] = 105.0
        low[12] = 99.0
        open_price[19], close[19], high[19], low[19] = 104.5, 104.0, 105.0, 103.5
        open_price[20], close[20], high[20], low[20] = 104.0, 108.0, 109.0, 103.8
    frame = pd.DataFrame(
        {
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
        },
        index=index,
    )
    return frame


def test_order_block_features_are_causal_and_keep_raw_zone_prices() -> None:
    bars = _bars(180)
    full = build_order_block_features(bars, swing_period=3, impulse_atr=0.0)
    prefix = build_order_block_features(bars.iloc[:120], swing_period=3, impulse_atr=0.0)

    assert "ob_bull_active" in full
    assert "ob_bear_retest" in full
    assert "ob_bull_low" in full
    active = full["ob_bull_active"] > 0.0
    assert active.any()
    assert np.allclose(
        full.loc[active, "ob_bull_mid"],
        (full.loc[active, "ob_bull_low"] + full.loc[active, "ob_bull_high"]) / 2.0,
    )
    assert full.loc[active, "ob_bull_origin_time_ms"].notna().all()
    pd.testing.assert_frame_equal(full.iloc[:120], prefix)
    assert bool((full[["ob_bull_new", "ob_bear_new"]].to_numpy() > 0).any())


def test_order_block_parameters_reject_invalid_values() -> None:
    bars = _bars(20)
    try:
        build_order_block_features(bars, search_bars=0)
    except ValueError as exc:
        assert "positive" in str(exc)
    else:
        raise AssertionError("expected invalid search window to fail")
