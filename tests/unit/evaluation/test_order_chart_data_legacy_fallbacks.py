"""Legacy chart attribution falls back to safe side and timeframe defaults."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

import evaluation.plotting.orders.geometry as order_chart_geometry
from evaluation.metrics.trades import TradeChartMetrics
from evaluation.plotting.chart_overlays import OverlayEvents
from evaluation.plotting.order_chart_data import (
    _feature_swing_segments,
    _feature_zones,
    order_levels,
)


@pytest.mark.parametrize(
    ("direction", "side", "low", "high"),
    [("buy", "Bull", 100.0, 101.0), ("sell", "Bear", 90.0, 91.0)],
)
def test_non_mapping_timeframe_attribution_uses_m1_and_textual_trade_side(
    direction: str, side: str, low: float, high: float
) -> None:
    index = pd.date_range("2025-04-01 15:00", periods=3, freq="min", tz="UTC")
    window = pd.DataFrame(index=index)
    features = pd.DataFrame(
        {
            "ifvg_bull_active": [1.0, 1.0, 0.0],
            "ifvg_bull_low": [100.0, 100.0, 100.0],
            "ifvg_bull_high": [101.0, 101.0, 101.0],
            "ifvg_bear_active": [1.0, 0.0, 1.0],
            "ifvg_bear_low": [90.0, 90.0, 90.0],
            "ifvg_bear_high": [91.0, 91.0, 91.0],
        },
        index=index,
    )
    open_row = pd.Series(
        {
            "time": index[1],
            "direction": direction,
            "entry_ideas": ["ifvg_retest"],
            "entry_idea_timeframes": ["H1"],
        }
    )

    zones = _feature_zones(
        features,
        window,
        open_row,
        order_block_timeframes=(),
        fvg_timeframes=(),
        ifvg_timeframes=(),
    )

    assert len(zones) == 1
    assert zones[0].label == f"IFVG retest · M1 {side} IFVG"
    assert (zones[0].low, zones[0].high) == (low, high)
    assert (zones[0].t0, zones[0].t1) == (index[0], index[1] if side == "Bull" else index[2])


@pytest.mark.parametrize(
    ("origin_bar", "origin_time"),
    [("not-a-bar", None), (1, "not-a-timestamp")],
)
def test_malformed_legacy_origin_metadata_keeps_saved_ifvg_zone(
    origin_bar: object, origin_time: object
) -> None:
    index = pd.date_range("2025-04-01 15:00", periods=4, freq="min", tz="UTC")
    window = pd.DataFrame(index=index)
    features = pd.DataFrame(
        {
            "ifvg_bull_active": [0.0] * len(index),
            "ifvg_bull_low": [100.0] * len(index),
            "ifvg_bull_high": [101.0] * len(index),
        },
        index=index,
    )
    open_row = pd.Series(
        {
            "time": index[2],
            "direction": "buy",
            "entry_setup_types": "['fvg_retest']",
            "entry_setup_levels": "{malformed snapshot",
            "entry_origin_bar": origin_bar,
            "entry_origin_time": origin_time,
            "ifvg_zone_low": 100.0,
            "ifvg_zone_high": 101.0,
        }
    )

    zones = _feature_zones(
        features,
        window,
        open_row,
        order_block_timeframes=(),
        fvg_timeframes=(),
        ifvg_timeframes=(),
    )

    assert len(zones) == 1
    assert zones[0].label == "FVG/IFVG · M1 Bull IFVG"
    assert (zones[0].low, zones[0].high) == (100.0, 101.0)
    assert (zones[0].t0, zones[0].t1) == (index[2], index[-1])


@pytest.mark.parametrize(
    ("include_aligned_swing", "source_wick"),
    [(True, 9.0), (False, 10.0)],
)
def test_mtf_swing_is_omitted_without_aligned_value_or_exact_source_wick(
    monkeypatch: pytest.MonkeyPatch,
    include_aligned_swing: bool,
    source_wick: float,
) -> None:
    index = pd.date_range("2025-04-01 15:00", periods=3, freq="min", tz="UTC")
    bars = pd.DataFrame({"high": [source_wick, 9.0, 9.0], "low": [8.0, 8.0, 8.0]}, index=index)
    source_levels = pd.DataFrame(
        {
            "last_swing_high": [10.0, 10.0],
            "last_swing_high_time": [index[0], index[0]],
            "last_swing_low": [np.nan, np.nan],
            "last_swing_low_time": [pd.NaT, pd.NaT],
        },
        index=pd.DatetimeIndex([index[0], index[1]]),
    )
    monkeypatch.setattr(order_chart_geometry, "resample", lambda _bars, _tf: source_levels)
    monkeypatch.setattr(
        order_chart_geometry, "structure_levels", lambda *_args, **_kwargs: source_levels
    )
    aligned = {"H1_last_swing_high": [10.0, 10.0, np.nan]} if include_aligned_swing else {}
    features = pd.DataFrame(aligned, index=index)
    window = bars.copy()

    segments = _feature_swing_segments(features, window, ("H1",), bars=bars)

    assert segments == []


def test_mtf_swing_uses_exact_source_wick_and_suppresses_overlapping_lower_swing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index = pd.date_range("2025-04-01 15:00", periods=4, freq="min", tz="UTC")
    bars = pd.DataFrame({"high": [10.0, 9.0, 9.0, 9.0], "low": [8.0, 8.0, 8.0, 8.0]}, index=index)
    source_levels = pd.DataFrame(
        {
            "last_swing_high": [10.0, 10.0],
            "last_swing_high_time": [index[0], index[0]],
            "last_swing_low": [np.nan, np.nan],
            "last_swing_low_time": [pd.NaT, pd.NaT],
        },
        index=pd.DatetimeIndex([index[0], index[1]]),
    )
    monkeypatch.setattr(order_chart_geometry, "resample", lambda _bars, _tf: source_levels)
    monkeypatch.setattr(
        order_chart_geometry, "structure_levels", lambda *_args, **_kwargs: source_levels
    )
    features = pd.DataFrame({"H1_last_swing_high": [10.0] * len(index)}, index=index)

    without_lower_swing = _feature_swing_segments(features, bars, ("H1",), bars=bars)
    with_lower_swing = _feature_swing_segments(
        features,
        bars,
        ("H1",),
        lower_timeframe_swings=(
            SimpleNamespace(side="high", t0=index[0], t1=index[3], price=10.0),
        ),
        bars=bars,
    )

    assert [
        (segment.label, segment.price, segment.t0, segment.t1) for segment in without_lower_swing
    ] == [("H1 Swing High", 10.0, index[0], index[3])]
    assert with_lower_swing == []


def test_order_levels_keeps_basic_stop_and_target_with_absent_features_and_null_notes() -> None:
    index = pd.date_range("2025-04-01 15:00", periods=3, freq="min", tz="UTC")
    candles = pd.DataFrame(
        {
            "open": [100.0, 100.25, 100.5],
            "high": [100.5, 100.75, 101.0],
            "low": [99.5, 99.75, 100.0],
            "close": [100.0, 100.5, 100.75],
        },
        index=index,
    )
    metrics = TradeChartMetrics(
        entry_price=100.0,
        exit_price=100.75,
        direction=1,
        mae_price=99.75,
        mfe_price=101.0,
        mae_time=index[0],
        mfe_time=index[1],
        sl_price=98.0,
        tp_price=103.0,
        mae_drawn=False,
        mfe_drawn=False,
    )
    open_row = pd.Series(
        {
            "time": index[1],
            "sl_ref": pd.NA,
            "tp_ref": None,
            "exit_mode": pd.NA,
            "planned_rr": pd.NA,
            "rr_ratio": None,
        }
    )

    levels = order_levels(
        candles,
        metrics,
        OverlayEvents(),
        candles,
        index[1],
        index[2],
        open_row,
        features=None,
    )

    assert levels.zones == []
    assert [segment.label for segment in levels.segs] == []
    assert {label for label, _price, _color in levels.off_chart_levels} == {
        "Stop loss (SL)",
        "Take profit (TP)",
    }
    assert levels.red is not None and levels.green is not None
    assert metrics.sl_price is not None and levels.ylim[0] > metrics.sl_price
    assert metrics.tp_price is not None and levels.ylim[1] < metrics.tp_price


def test_order_levels_draws_in_window_excursions_and_protective_levels() -> None:
    index = pd.date_range("2025-04-01 15:00", periods=3, freq="min", tz="UTC")
    candles = pd.DataFrame(
        {
            "open": [100.0, 100.25, 100.5],
            "high": [100.5, 101.0, 101.5],
            "low": [99.5, 99.75, 100.0],
            "close": [100.0, 100.5, 101.0],
        },
        index=index,
    )
    metrics = TradeChartMetrics(
        entry_price=100.0,
        exit_price=101.0,
        direction=1,
        mae_price=99.5,
        mfe_price=101.5,
        mae_time=index[1],
        mfe_time=index[2],
        sl_price=99.5,
        tp_price=101.5,
        sl_time=index[1],
        tp_time=index[2],
    )

    levels = order_levels(
        candles,
        metrics,
        OverlayEvents(),
        candles,
        index[0],
        index[2],
        pd.Series({"sl_ref": "swing_low", "tp_ref": "swing_high", "planned_rr": 2.0}),
    )

    labels = [segment.label for segment in levels.segs]
    assert labels[:2] == ["MAE", "MFE"]
    assert labels[2].startswith("Stop loss (SL) - ")
    assert labels[3].startswith("Take profit (TP) - ")
    assert levels.off_chart_levels == []
    assert levels.red == (99.5, 100.0)
    assert levels.green == (100.0, 101.5)


def test_selected_saved_swing_levels_keep_known_levels_off_chart_without_expanding_axis() -> None:
    index = pd.date_range("2025-04-01 15:00", periods=3, freq="min", tz="UTC")
    bars = pd.DataFrame(
        {
            "open": [100.0, 100.05, 100.1],
            "high": [100.1, 100.2, 100.15],
            "low": [99.9, 99.95, 100.0],
            "close": [100.05, 100.1, 100.15],
        },
        index=index,
    )
    features = pd.DataFrame(
        {
            "M5_standard_deviation_level_0_5_price": [110.0] * len(index),
            "M5_standard_deviation_level_0_707_price": [101.0] * len(index),
            "M5_standard_deviation_level_custom_price": [100.5] * len(index),
        },
        index=index,
    )
    metrics = TradeChartMetrics(
        entry_price=100.0,
        exit_price=100.15,
        direction=1,
        mae_price=99.0,
        mfe_price=102.0,
        mae_time=index[0],
        mfe_time=index[1],
        sl_price=None,
        tp_price=None,
        mae_drawn=False,
        mfe_drawn=False,
    )
    open_row = pd.Series(
        {
            "time": index[1],
            "direction": 1,
            "sl_ref": (
                "M5_standard_deviation_level_0_5_price|"
                "M5_standard_deviation_level_0_707_price|"
                "M5_standard_deviation_level_custom_price"
            ),
        }
    )

    levels = order_levels(
        bars,
        metrics,
        OverlayEvents(),
        bars,
        index[1],
        index[2],
        open_row,
        show_mae_mfe=False,
        show_sl_tp=False,
        features=features,
        swing_timeframes=(),
    )

    assert set(levels.deviations) == {(0.5, 110.0), (0.707, 101.0)}
    assert any(
        label == "Swing level 0.5" and price == 110.0
        for label, price, _color in levels.off_chart_levels
    )
    assert levels.ylim[1] < 110.0


def test_selected_range_deviations_use_feature_swings_and_ignore_unknown_tokens() -> None:
    index = pd.date_range("2025-04-01 15:00", periods=3, freq="min", tz="UTC")
    bars = pd.DataFrame(
        {
            "open": [100.0, 100.25, 100.5],
            "high": [101.0, 102.0, 101.5],
            "low": [99.0, 99.5, 99.75],
            "close": [100.5, 101.0, 101.25],
        },
        index=index,
    )
    features = pd.DataFrame(
        {"last_swing_low": [99.0] * 3, "last_swing_high": [101.0] * 3}, index=index
    )
    metrics = TradeChartMetrics(
        entry_price=100.0,
        exit_price=101.25,
        direction=1,
        mae_price=99.0,
        mfe_price=102.0,
        mae_time=index[0],
        mfe_time=index[1],
        sl_price=None,
        tp_price=None,
        mae_drawn=False,
        mfe_drawn=False,
    )

    levels = order_levels(
        bars,
        metrics,
        OverlayEvents(),
        bars,
        index[1],
        index[2],
        pd.Series({"sl_ref": "dev_1.0|dev_9.0|dev_invalid"}),
        show_mae_mfe=False,
        show_sl_tp=False,
        features=features,
    )

    assert levels.deviations == [(1.0, 101.0)]
    assert levels.ylim[0] <= 101.0 <= levels.ylim[1]
    assert not any(
        label == "Selected range projection 1x" for label, _, _ in levels.off_chart_levels
    )
    assert any("not statistical standard deviation" in note for note in levels.notes)
