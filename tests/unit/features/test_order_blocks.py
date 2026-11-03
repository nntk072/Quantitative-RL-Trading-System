"""Causality and context requirements for the order-block feature."""

from __future__ import annotations

import numpy as np
import pandas as pd

from features.context.order_blocks import (
    build_order_block_features,
    build_order_block_features_with_event_ledger,
)


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
    retests = full["ob_bull_retest"] > 0.0
    if retests.any():
        assert full.loc[retests, "ob_bull_retest_confirmed_at_time_ns"].notna().all()
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


def test_order_block_retest_requires_overlap_then_later_close_confirmation() -> None:
    bars = _bars(35)
    bars.loc[bars.index[21], :] = [104.3, 104.5, 103.8, 104.2]
    bars.loc[bars.index[22], :] = [104.2, 104.8, 104.0, 104.6]

    result = build_order_block_features(bars, swing_period=3, impulse_atr=0.0)

    assert result.iloc[20]["ob_bull_new"] == 1.0
    assert result.iloc[20]["ob_bull_active"] == 1.0
    assert result.iloc[21]["ob_bull_retest"] == 0.0
    assert result.iloc[22]["ob_bull_retest"] == 1.0
    assert result.iloc[22]["ob_bull_retest_confirmed_at_time_ns"] == bars.index[22].value
    pd.testing.assert_frame_equal(
        result.iloc[:23],
        build_order_block_features(bars.iloc[:23], swing_period=3, impulse_atr=0.0),
    )


def test_new_same_side_order_block_replaces_previous_zone() -> None:
    bars = _bars(40)
    bars.loc[bars.index[27], :] = [108.8, 109.0, 108.0, 108.5]
    bars.loc[bars.index[28], :] = [108.5, 113.0, 108.2, 112.0]

    result = build_order_block_features(bars, swing_period=3, impulse_atr=0.0)

    assert result.iloc[20]["ob_bull_new"] == 1.0
    assert result.iloc[28]["ob_bull_new"] == 1.0
    assert result.iloc[28]["ob_bull_active"] == 1.0
    assert result.iloc[28]["ob_bull_origin_time_ms"] == bars.index[27].value // 1_000_000


def test_order_block_event_ledger_preserves_overlapping_zone_retests() -> None:
    bars = _bars(40)
    for i in range(21, 28):
        bars.iloc[i] = [104.0, 104.5, 103.8, 104.1]
    bars.iloc[22] = [104.0, 104.8, 103.9, 104.6]
    bars.iloc[27] = [104.5, 105.0, 103.5, 104.0]
    bars.iloc[28] = [104.0, 113.0, 103.5, 112.0]
    bars.iloc[29] = [111.0, 112.0, 103.8, 111.0]
    bars.iloc[30] = [112.0, 113.0, 103.8, 112.5]

    scalar, ledger = build_order_block_features_with_event_ledger(
        bars, swing_period=3, impulse_atr=0.5
    )

    same_bar = ledger.loc[ledger["confirmation_bar"].eq(30) & ledger["side"].eq("bull")]
    assert len(same_bar) == 2
    assert same_bar["zone_id"].nunique() == 2
    assert int(same_bar["selected_by_scalar"].sum()) == 1
    assert scalar.iloc[30]["ob_bull_retest"] == 1.0
    pd.testing.assert_frame_equal(
        scalar,
        build_order_block_features(bars, swing_period=3, impulse_atr=0.5),
    )


def test_order_block_event_ledger_is_prefix_causal() -> None:
    bars = _bars(180)
    full_features, full_ledger = build_order_block_features_with_event_ledger(
        bars, swing_period=3, impulse_atr=0.0
    )
    prefix_features, prefix_ledger = build_order_block_features_with_event_ledger(
        bars.iloc[:120], swing_period=3, impulse_atr=0.0
    )

    pd.testing.assert_frame_equal(full_features.iloc[:120], prefix_features)
    pd.testing.assert_frame_equal(
        full_ledger.loc[full_ledger["confirmation_bar"] < 120].reset_index(drop=True),
        prefix_ledger,
    )
