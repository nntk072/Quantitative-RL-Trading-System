"""Order-chart levels, swing pivots, and the ATR reward-ratio cap."""

from __future__ import annotations

import inspect
from typing import Any, cast

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest
from matplotlib.figure import Figure

import evaluation.plotting.order_chart as legacy_order_chart
from evaluation.metrics.trades import TradeChartMetrics, compute_trade_metrics
from evaluation.plotting.chart_levels import (
    at_sample_extreme,
    deviation_levels,
    isolated_spike_mask,
    ohlc_ok_mask,
)
from evaluation.plotting.chart_overlays import (
    OverlayEvents,
    SmtSegment,
    SweepLine,
    SwingRay,
    build_overlay_events,
    draw_overlays_mpl,
)
from evaluation.plotting.order_chart_data import (
    _feature_zones,
    _retracement_segments,
    order_levels,
)
from evaluation.plotting.order_chart_renderers import draw_order_levels_mpl
from evaluation.plotting.orders import _position_events
from evaluation.plotting.overlay_events import _rays_from_origins, _swing_origins
from evaluation.plotting.plots import plot_per_trade_orders
from evaluation.plotting.plots_interactive import (
    plot_per_trade_orders as plot_per_trade_orders_html,
)
from features.context.reachability import max_tp_distance, rr_reaches
from features.technical.structure import structure_levels
from simulation.environment.env import TradingEnv
from trading.strategies.po3_ifvg import PO3IFVGStrategy


def test_clip_cuts_smt_that_runs_months_past_the_trade() -> None:
    start = pd.Timestamp("2024-12-31 16:00")
    end = pd.Timestamp("2024-12-31 17:00")
    seg = SmtSegment(
        t0=pd.Timestamp("2024-12-31 16:20"),
        p0=21200.0,
        t1=pd.Timestamp("2025-03-08 16:00"),
        p1=22000.0,
        side="high",
        label="SMT",
    )
    clipped = OverlayEvents(smt=[seg]).clip(start, end)
    assert clipped.smt == []
    inside = SmtSegment(
        t0=pd.Timestamp("2024-12-31 16:20"),
        p0=21200.0,
        t1=pd.Timestamp("2024-12-31 16:40"),
        p1=21240.0,
        side="high",
        label="SMT",
    )
    kept = OverlayEvents(smt=[inside]).clip(start, end)
    assert len(kept.smt) == 1
    assert kept.smt[0].t0 == inside.t0
    assert kept.smt[0].t1 == inside.t1


def test_clip_drops_a_swing_whose_pivot_is_outside_the_window() -> None:
    idx = pd.date_range("2026-03-02 16:30", periods=10, freq="1min")
    ray = SwingRay(t0=idx[0], t1=idx[8], price=10.0, side="high", origin=idx[0])
    clipped = OverlayEvents(swings=[ray]).clip(pd.Timestamp(idx[4]), pd.Timestamp(idx[8]))
    assert clipped.swings == []

    inside = SwingRay(t0=idx[5], t1=idx[9], price=10.0, side="high", origin=idx[5])
    kept = OverlayEvents(swings=[inside]).clip(pd.Timestamp(idx[4]), pd.Timestamp(idx[8]))
    assert len(kept.swings) == 1
    assert kept.swings[0].origin == idx[5]
    assert kept.swings[0].t0 == idx[5]
    assert kept.swings[0].t1 == idx[8]
    fig, ax = plt.subplots()
    draw_overlays_mpl(ax, kept)
    assert len(ax.collections) == 1
    plt.close(fig)


def test_swing_origin_is_the_pivot_candle() -> None:
    n = 40
    idx = pd.date_range("2026-03-02 16:30", periods=n, freq="1min")
    close = np.full(n, 100.0)
    close[20] = 110.0
    high = close + 0.2
    high[20] = 112.0
    low = close - 0.2
    bars = pd.DataFrame(
        {"open": close, "high": high, "low": low, "close": close},
        index=idx,
    )
    levels = structure_levels(bars, swing_period=3)
    events = build_overlay_events(bars, swing_period=3)
    highs = [r for r in events.swings if r.side == "high"]
    assert highs
    ray = highs[0]
    assert ray.origin is not None
    assert pd.Timestamp(ray.origin) == pd.Timestamp(levels["last_swing_high_time"].dropna().iloc[0])
    loc = int(bars.index.get_indexer(pd.Index([ray.origin]))[0])
    assert float(bars["high"].iloc[loc]) == float(ray.price)


def test_swing_off_the_wick_still_draws_on_that_candle() -> None:
    idx = pd.date_range("2026-03-02 16:30", periods=10, freq="1min")
    high = np.full(10, 100.0)
    high[4] = 112.0
    levels = pd.DataFrame(
        {
            "last_swing_high": np.nan,
            "last_swing_high_time": pd.Series(pd.NaT, index=idx),
        },
        index=idx,
    )
    levels.loc[idx[4], "last_swing_high"] = 999.0
    levels.loc[idx[4], "last_swing_high_time"] = idx[4]
    origins = _swing_origins(levels, pd.Series(high, index=idx), idx, 3, "high")
    assert origins
    origin_i, price = origins[0]
    assert origin_i == 4
    assert price == 112.0


def test_swing_ray_ends_at_first_later_candle_that_sweeps_it() -> None:
    idx = pd.date_range("2026-03-02 16:30", periods=6, freq="1min")
    high = np.array([10.0, 9.0, 9.5, 10.1, 11.0, 12.0])
    bars = pd.DataFrame({"open": high, "high": high, "low": high - 1.0, "close": high}, index=idx)

    ray = _rays_from_origins(idx, [(0, 10.0)], "high", bars)[0]

    assert ray.t0 == idx[0]
    assert ray.t1 == idx[3]


def test_sweep_label_uses_legend_instead_of_overlapping_the_line() -> None:
    idx = pd.date_range("2026-03-02 16:30", periods=8, freq="1min")
    line = SweepLine(t0=idx[1], t1=idx[5], price=101.5, side="high", label="X")
    fig, ax = plt.subplots()
    draw_overlays_mpl(ax, OverlayEvents(sweeps=[line]))
    assert not ax.texts
    sweep_line = next(line for line in ax.lines if line.get_label() == "X")
    assert list(cast(Any, sweep_line.get_xdata())) == [idx[1], idx[5]]
    assert list(cast(Any, sweep_line.get_ydata())) == [101.5, 101.5]
    plt.close(fig)


def test_order_png_legend_omits_vwap(tmp_path, monkeypatch) -> None:
    idx = pd.date_range("2026-03-02 16:30", periods=80, freq="1min")
    close = 20000.0 + np.linspace(0, 5, 80)
    bars = pd.DataFrame(
        {
            "open": close,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "tickvol": np.full(80, 10),
        },
        index=idx,
    )
    trades = pd.DataFrame(
        [
            {
                "type": "open",
                "direction": 1,
                "price": float(close[20]),
                "time": idx[20],
                "bar": 20,
                "lots": 1.0,
            },
            {
                "type": "close",
                "direction": 1,
                "price": float(close[40]),
                "time": idx[40],
                "bar": 40,
                "pnl": 1.0,
                "reason": "close",
            },
        ]
    )
    labels: list[str] = []
    orig = Figure.savefig

    def _save(self, *args, **kwargs):
        for legend in self.legends:
            labels.extend(t.get_text() for t in legend.get_texts())
        return orig(self, *args, **kwargs)

    monkeypatch.setattr(Figure, "savefig", _save)
    plot_per_trade_orders(bars, trades, orders_dir=tmp_path, max_charts=1, dpi=72, show_sl_tp=False)
    assert labels
    assert "VWAP" not in labels
    assert "M1 EMA 50" in labels


def test_both_plotters_call_prepare_order_chart() -> None:
    assert "prepare_order_chart" in inspect.getsource(plot_per_trade_orders)
    assert "prepare_order_chart" in inspect.getsource(plot_per_trade_orders_html)


def test_legacy_partial_trade_reconstructs_post_partial_breakeven_stop() -> None:
    trades = pd.DataFrame(
        [
            {
                "type": "open",
                "position_id": "p1",
                "direction": -1,
                "time": "2025-01-01 10:00:00+00:00",
                "price": 100.0,
                "sl_price": 110.0,
            },
            {
                "type": "tp_partial_close",
                "position_id": "p1",
                "time": "2025-01-01 10:01:00+00:00",
                "actual_tick_time": "2025-01-01 10:01:00.1+00:00",
                "price": 95.0,
                "pnl": 1.0,
            },
            {
                "type": "stop_close",
                "position_id": "p1",
                "time": "2025-01-01 10:02:00+00:00",
                "price": 98.0,
                "pnl": 1.0,
            },
        ]
    )
    events = _position_events(
        trades,
        trades.iloc[0],
        trades.iloc[-1],
        breakeven_buffer_pts=2.0,
    )

    update = events.loc[events["type"].eq("sl_update")].iloc[0]
    assert update["price"] == 98.0
    assert update["reason"] == "post_partial_breakeven_reconstructed_from_config"


def test_trade_like_13_keeps_mfe_on_the_wick_and_off_the_rr_target() -> None:
    idx = pd.date_range("2025-01-06 18:21", periods=42, freq="1min")
    high = np.full(42, 21690.0)
    high[8] = 21699.45
    low = np.full(42, 21650.0)
    low[30] = 21641.55
    close = np.full(42, 21670.0)
    bars = pd.DataFrame(
        {"open": close, "high": high, "low": low, "close": close},
        index=idx,
    )
    open_row = pd.Series(
        {
            "time": idx[0],
            "direction": 1,
            "price": 21679.55,
            "sl_price": 21451.35,
            "tp_price": 22421.44,
            "rr_ratio": 3.25,
        }
    )
    close_row = pd.Series({"time": idx[-1], "price": 21658.75, "pnl": -55.68})
    metrics = compute_trade_metrics(bars, open_row, close_row)
    assert metrics.mfe_price == 21699.45
    assert metrics.tp_time is None
    levels = order_levels(
        bars,
        metrics,
        OverlayEvents(),
        bars,
        idx[0],
        idx[-1],
        open_row,
    )
    assert levels.ylim[1] < 21800
    assert any(note.startswith("TP 22421.44") for note in levels.notes)
    assert all(seg.label != "TP" for seg in levels.segs)
    assert levels.green is not None
    assert levels.green[1] <= levels.ylim[1]
    assert levels.green[1] < 21800


def test_only_selected_deviation_is_plotted() -> None:
    idx = pd.date_range("2025-01-06 18:21", periods=8, freq="1min")
    close = np.full(8, 105.0)
    bars = pd.DataFrame(
        {"open": close, "high": close + 1.0, "low": close - 1.0, "close": close},
        index=idx,
    )
    metrics = TradeChartMetrics(
        entry_price=105.0,
        exit_price=105.0,
        direction=1,
        mae_price=104.0,
        mfe_price=106.0,
        mae_time=idx[2],
        mfe_time=idx[3],
        sl_price=100.0,
        tp_price=110.0,
        mae_drawn=False,
        mfe_drawn=False,
    )
    events = OverlayEvents(
        swings=[
            SwingRay(idx[0], idx[-1], 100.0, "low", origin=idx[0]),
            SwingRay(idx[0], idx[-1], 110.0, "high", origin=idx[0]),
        ]
    )

    levels = order_levels(
        bars,
        metrics,
        events,
        bars,
        idx[2],
        idx[5],
        pd.Series({"direction": 1, "sl_ref": "dev_0", "tp_ref": "target"}),
        show_mae_mfe=False,
    )

    assert levels.deviations == [(0.0, 100.0)]
    assert any(
        name == "Selected range projection 0x" for name, _price, _color in levels.off_chart_levels
    )


def test_unselected_deviation_is_not_plotted() -> None:
    idx = pd.date_range("2025-01-06 18:21", periods=8, freq="1min")
    close = np.full(8, 105.0)
    bars = pd.DataFrame(
        {"open": close, "high": close + 1.0, "low": close - 1.0, "close": close},
        index=idx,
    )
    metrics = TradeChartMetrics(
        entry_price=105.0,
        exit_price=105.0,
        direction=1,
        mae_price=105.0,
        mfe_price=105.0,
        mae_time=idx[2],
        mfe_time=idx[2],
        sl_price=100.0,
        tp_price=110.0,
    )
    events = OverlayEvents(
        swings=[
            SwingRay(idx[0], idx[-1], 100.0, "low", origin=idx[0]),
            SwingRay(idx[0], idx[-1], 110.0, "high", origin=idx[0]),
        ]
    )

    levels = order_levels(
        bars,
        metrics,
        events,
        bars,
        idx[2],
        idx[5],
        pd.Series({"direction": 1, "sl_ref": "last_swing_low", "tp_ref": "target"}),
        show_mae_mfe=False,
    )

    assert levels.deviations == []
    assert not any(
        name.startswith("Selected range projection") for name, *_ in levels.off_chart_levels
    )


def test_fib_like_plot_shows_nearby_requested_level_values_for_its_timeframe() -> None:
    idx = pd.date_range("2025-01-06 18:21", periods=4, freq="1min")
    window = pd.DataFrame({"low": [98.0] * 4, "high": [102.0] * 4}, index=idx)
    features = pd.DataFrame(
        {
            "M5_standard_deviation_leg_start_time_ns": idx[0].value,
            "M5_standard_deviation_leg_end_time_ns": idx[1].value,
            "M5_standard_deviation_level_1_price": [97.0] * 4,
            "M5_standard_deviation_level_0_786_price": [98.5] * 4,
            "M5_standard_deviation_level_0_707_price": [99.0] * 4,
            "M5_standard_deviation_level_0_5_price": [100.0] * 4,
            "M5_standard_deviation_level_0_price": [101.0] * 4,
            "M5_standard_deviation_level_neg_0_5_price": [103.0] * 4,
            "M5_standard_deviation_level_neg_8_price": [150.0] * 4,
        },
        index=idx,
    )
    open_row = pd.Series(
        {
            "entry_ideas": ["standard_deviation"],
            "entry_idea_timeframes": {"standard_deviation": ["M5"]},
        }
    )

    segments = _retracement_segments(
        features,
        window,
        open_row,
        idx[2],
        idx[3],
        98.0,
        102.0,
        entry_idea_plot_config={
            "standard_deviation": {
                "timeframes": "M5",
                "levels": [0.786, 0.5],
                "max_chart_range_fraction": 0.15,
            }
        },
    )

    labels = {segment.label for segment in segments}
    assert "Fib/SD: 0.786 (M5)" in labels
    assert "Fib/SD: 0.5 (M5)" in labels
    assert len(segments) == 2
    assert not any("-8" in label for label in labels)
    assert all(segment.t0 == idx[0] and segment.t1 == idx[3] for segment in segments)


def test_linked_zone_plot_shows_only_saved_zone_and_timeframe() -> None:
    idx = pd.date_range("2025-01-06 18:21", periods=4, freq="1min")
    window = pd.DataFrame(index=idx)
    features = pd.DataFrame(
        {
            "M5_ifvg_bull_active": [1.0] * 4,
            "M5_ifvg_bull_low": [100.0] * 4,
            "M5_ifvg_bull_high": [101.5] * 4,
            "M5_ifvg_bear_active": [1.0] * 4,
            "M5_ifvg_bear_low": [102.0] * 4,
            "M5_ifvg_bear_high": [103.0] * 4,
        },
        index=idx,
    )
    open_row = pd.Series(
        {
            "time": idx[2],
            "direction": 1,
            "entry_ideas": ["po3"],
            "entry_idea_timeframes": {"po3": ["M5"]},
            "entry_idea_zones": [
                {
                    "idea": "po3",
                    "family": "ifvg",
                    "timeframe": "M5",
                    "side": "bull",
                    "low": 100.0,
                    "high": 101.5,
                }
            ],
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
    assert zones[0].label == "PO3 · M5 Bull IFVG"
    assert (zones[0].low, zones[0].high) == (100.0, 101.5)


def test_plot_config_selects_zone_family_per_entry_idea() -> None:
    idx = pd.date_range("2025-01-06 18:21", periods=4, freq="1min")
    window = pd.DataFrame(index=idx)
    features = pd.DataFrame(
        {
            "M5_fvg_bull_active": 1.0,
            "M5_fvg_bull_low": 100.0,
            "M5_fvg_bull_high": 101.5,
            "M5_ifvg_bull_active": 1.0,
            "M5_ifvg_bull_low": 100.0,
            "M5_ifvg_bull_high": 101.5,
        },
        index=idx,
    )
    open_row = pd.Series(
        {
            "time": idx[2],
            "direction": 1,
            "entry_ideas": ["po3"],
            "entry_idea_timeframes": {"po3": ["M5"]},
            "entry_idea_zones": [
                {
                    "idea": "po3",
                    "family": family,
                    "timeframe": "M5",
                    "side": "bull",
                    "low": 100.0,
                    "high": 101.5,
                }
                for family in ("fvg", "ifvg")
            ],
        }
    )

    zones = _feature_zones(
        features,
        window,
        open_row,
        order_block_timeframes=(),
        fvg_timeframes=(),
        ifvg_timeframes=(),
        entry_idea_plot_config={"po3": {"show_fvg": False, "show_ifvg": True}},
    )

    assert len(zones) == 1
    assert "IFVG" in zones[0].label


def test_plot_config_selects_timeframe_per_entry_idea() -> None:
    idx = pd.date_range("2025-01-06 18:21", periods=4, freq="1min")
    window = pd.DataFrame(index=idx)
    features = pd.DataFrame(
        {
            "M5_ob_bull_active": 1.0,
            "M5_ob_bull_low": 100.0,
            "M5_ob_bull_high": 101.0,
            "H1_ob_bull_active": 1.0,
            "H1_ob_bull_low": 102.0,
            "H1_ob_bull_high": 103.0,
        },
        index=idx,
    )
    open_row = pd.Series(
        {
            "time": idx[2],
            "direction": 1,
            "entry_ideas": ["order_block"],
            "entry_idea_timeframes": {"order_block": ["M5", "H1"]},
            "entry_idea_zones": [
                {
                    "idea": "order_block",
                    "family": "ob",
                    "timeframe": timeframe,
                    "side": "bull",
                    "low": low,
                    "high": high,
                }
                for timeframe, low, high in (("M5", 100.0, 101.0), ("H1", 102.0, 103.0))
            ],
        }
    )

    zones = _feature_zones(
        features,
        window,
        open_row,
        order_block_timeframes=(),
        fvg_timeframes=(),
        ifvg_timeframes=(),
        entry_idea_plot_config={"order_block": {"timeframes": "H1", "show_zone": True}},
    )

    assert len(zones) == 1
    assert "H1" in zones[0].label
    assert (zones[0].low, zones[0].high) == (102.0, 103.0)


def test_isolated_spike_is_ignored_and_news_is_kept() -> None:
    idx = pd.date_range("2026-01-02 16:30", periods=12, freq="1min")
    high = np.full(12, 100.0)
    low = np.full(12, 99.0)
    high[6] = 500.0
    bars = pd.DataFrame(
        {"open": np.full(12, 99.5), "high": high, "low": low, "close": np.full(12, 99.5)},
        index=idx,
    )
    assert isolated_spike_mask(bars)[6]
    news = bars.copy()
    news.loc[news.index[6] :, "high"] = 500.0
    news.loc[news.index[6] :, "close"] = 499.0
    news.loc[news.index[6] :, "open"] = 100.0
    assert not isolated_spike_mask(news)[6]
    broken = bars.copy()
    broken.loc[broken.index[3], "low"] = 200.0
    assert not ohlc_ok_mask(broken)[3]


def test_deviation_levels_skip_far_multiples_and_need_an_extreme() -> None:
    levels = deviation_levels(100.0, 110.0, 98.0, 112.0)
    ks = [k for k, _ in levels]
    assert 0.0 in ks and 1.0 in ks
    assert 8.0 not in ks
    idx = pd.date_range("2026-01-02 16:30", periods=30, freq="1min")
    high = np.linspace(100, 110, 30)
    bars = pd.DataFrame(
        {"open": high, "high": high + 0.2, "low": high - 0.2, "close": high},
        index=idx,
    )
    # Last bar is the sample high.
    assert at_sample_extreme(bars, idx[-1], 1)
    fallen = bars.copy()
    fallen.loc[fallen.index[-1], ["open", "high", "low", "close"]] = [90, 91, 89, 90]
    assert not at_sample_extreme(fallen, idx[-1], 1)


def test_ny_trade_window_ignores_earlier_pivots() -> None:
    idx = pd.date_range("2024-12-30 07:00", "2024-12-31 23:00", freq="1min")
    close = np.linspace(21000.0, 21200.0, len(idx))
    bars = pd.DataFrame(
        {"open": close, "high": close + 1.0, "low": close - 1.0, "close": close},
        index=idx,
    )
    t_open = pd.Timestamp("2024-12-31 16:32")
    t_close = pd.Timestamp("2024-12-31 16:33")
    open_payload: dict[str, Any] = {
        "time": t_open,
        "direction": 1,
        "price": float(cast(Any, bars.loc[t_open, "close"])),
        "type": "open",
        "lots": 1.0,
    }
    close_payload: dict[str, Any] = {
        "time": t_close,
        "price": float(cast(Any, bars.loc[t_close, "close"])),
        "pnl": -100.0,
        "type": "stop_close",
    }
    open_row = pd.Series(open_payload)
    close_row = pd.Series(close_payload)
    events = OverlayEvents(
        swings=[
            SwingRay(
                t0=pd.Timestamp("2024-12-30 07:15"),
                t1=pd.Timestamp("2024-12-31 18:00"),
                price=21100.0,
                side="high",
                origin=pd.Timestamp("2024-12-30 07:15"),
            ),
            SwingRay(
                t0=pd.Timestamp("2024-12-31 10:00"),
                t1=pd.Timestamp("2024-12-31 18:00"),
                price=21150.0,
                side="low",
                origin=pd.Timestamp("2024-12-31 10:00"),
            ),
        ],
        sweeps=[
            SweepLine(
                t0=pd.Timestamp("2024-12-31 10:00"),
                t1=pd.Timestamp("2024-12-31 16:40"),
                price=21150.0,
                side="low",
                label="SSL",
            )
        ],
        smt=[
            SmtSegment(
                t0=pd.Timestamp("2024-12-30 08:00"),
                p0=21100.0,
                t1=pd.Timestamp("2024-12-31 12:00"),
                p1=21140.0,
                side="high",
                label="SMT",
            )
        ],
    )
    flat = pd.Series(close, index=idx)
    overlays = {key: flat.copy() for key in ("ema50", "macd", "signal", "histogram", "rsi", "vwap")}
    from evaluation.plotting.chart_indicators import break_overlay_gaps
    from evaluation.plotting.order_window import prepare_order_chart

    prepared = prepare_order_chart(
        bars,
        open_row,
        close_row,
        overlay_events=events,
        full_overlays=overlays,
        context_bars=60,
    )
    assert prepared is not None
    assert prepared.window.index[0] == pd.Timestamp("2024-12-31 15:32")
    assert prepared.window.index[-1] <= pd.Timestamp("2024-12-31 17:33")
    assert all(ts.normalize() == pd.Timestamp("2024-12-31") for ts in prepared.window.index)
    assert t_open in prepared.window.index
    assert t_close in prepared.window.index
    assert prepared.events.smt == []
    assert prepared.events.swings == []
    assert prepared.events.sweeps == []

    gapped = pd.Series(
        [1.0, 2.0, 3.0, 4.0],
        index=pd.to_datetime(
            [
                "2024-12-30 22:59",
                "2024-12-30 23:00",
                "2024-12-31 16:30",
                "2024-12-31 16:31",
            ]
        ),
    )
    broken = break_overlay_gaps({"ema50": gapped})["ema50"]
    assert broken.isna().any()
    assert list(broken.dropna()) == [1.0, 2.0, 3.0, 4.0]


def _session(
    start: str, n: int, price: float, span: float, atr: float
) -> tuple[pd.DataFrame, pd.Series]:
    idx = pd.date_range(start, periods=n, freq="1min")
    high = np.full(n, price + span / 2)
    low = np.full(n, price - span / 2)
    bars = pd.DataFrame(
        {"open": np.full(n, price), "high": high, "low": low, "close": np.full(n, price)},
        index=idx,
    )
    return bars, pd.Series(np.full(n, atr), index=idx)


def test_rr_cap_scales_with_atr_not_a_fixed_point_distance() -> None:
    quiet_bars, quiet_atr = _session("2026-01-02 16:30", 30, 100.0, span=20.0, atr=2.0)
    quiet_bars2, quiet_atr2 = _session("2026-01-05 16:30", 30, 100.0, span=20.0, atr=2.0)
    quiet = pd.concat([quiet_bars, quiet_bars2])
    qatr = pd.concat([quiet_atr, quiet_atr2])
    qdist = max_tp_distance(quiet, qatr)
    # Prior session range 20 / atr 2 = 10 ATR, times current atr 2 → 20 points.
    assert qdist.iloc[-1] == 20.0
    assert not rr_reaches(100.0, 50.0, 4.0, float(qdist.iloc[-1]))

    big_bars, big_atr = _session("2200-01-02 16:30", 30, 1_000_000.0, span=2000.0, atr=200.0)
    big_bars2, big_atr2 = _session("2200-01-05 16:30", 30, 1_000_000.0, span=2000.0, atr=200.0)
    big = pd.concat([big_bars, big_bars2])
    batr = pd.concat([big_atr, big_atr2])
    bdist = max_tp_distance(big, batr)
    # Same 10 ATR ratio, but the point cap is 2000. A 50-point stop at 4R now fits.
    assert bdist.iloc[-1] == 2000.0
    assert rr_reaches(100.0, 50.0, 4.0, float(bdist.iloc[-1]))


def test_dynamic_rr_scales_with_reachable_reward() -> None:
    idx = pd.date_range("2026-01-02 16:30", periods=40, freq="1min")
    close = np.full(40, 100.0)
    bars = pd.DataFrame(
        {"open": close, "high": close + 1, "low": close - 1, "close": close, "session": "ny"},
        index=idx,
    )
    n = 40
    feats = pd.DataFrame(
        {
            "atr_5": np.ones(n),
            "asian_high": np.full(n, 102.0),
            "asian_low": np.full(n, 98.0),
            "sweep_high": np.zeros(n),
            "sweep_low": np.ones(n),
            "po3_manipulation_low": np.full(n, 95.0),
            "po3_manipulation_high": np.full(n, 105.0),
            "po3_manipulation_end": np.zeros(n),
            "po3_distribution": np.zeros(n),
            "ifvg_bull_low": np.full(n, 98.0),
            "ifvg_bull_high": np.full(n, 99.0),
            "ifvg_bear_low": np.full(n, 99.0),
            "ifvg_bear_high": np.full(n, 100.0),
        },
        index=idx,
    )
    env = TradingEnv(
        bars,
        feats,
        strategy_actions=True,
        strategy=PO3IFVGStrategy(enforce_gate=False),
        obs_window=5,
        rr_ratio_range=(1.5, 5.0),
    )
    # Stop distance is 10. A tight bar (12 points of room) stays near 1R.
    tight = env._resolve_trader_tp(
        direction=1,
        entry_price=100.0,
        sl_price=90.0,
        reward_fraction=1.0,
        max_tp_distance=12.0,
    )
    assert tight == pytest.approx(112.0)
    # A wide bar can pay past 5R. Full fraction uses the whole reachable distance.
    wide = env._resolve_trader_tp(
        direction=1,
        entry_price=100.0,
        sl_price=90.0,
        reward_fraction=1.0,
        max_tp_distance=70.0,
    )
    assert wide == pytest.approx(170.0)
    # Half of a wide bar is 4R (40 points), not a preset 5R print.
    mid = env._resolve_trader_tp(
        direction=1,
        entry_price=100.0,
        sl_price=90.0,
        reward_fraction=0.5,
        max_tp_distance=70.0,
    )
    assert mid == pytest.approx(140.0)
    # Reachable reward shorter than the stop cannot pay 1R.
    skipped = env._resolve_trader_tp(
        direction=1,
        entry_price=100.0,
        sl_price=90.0,
        reward_fraction=1.0,
        max_tp_distance=8.0,
    )
    assert skipped is None


def test_order_chart_shades_active_manipulation_and_marks_the_end() -> None:
    idx = pd.date_range("2020-01-02 16:30", periods=6, freq="1min")
    window = pd.DataFrame(
        {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 1},
        index=idx,
    )
    features = pd.DataFrame(
        {
            "po3_manipulation_active": [1.0, 1.0, 1.0, 0.0, 0.0, 0.0],
            "po3_manipulation_end": [0.0, 0.0, 0.0, 1.0, 0.0, 0.0],
            "po3_distribution": [0.0, 0.0, 0.0, 1.0, 1.0, 1.0],
            "asian_high": 110.0,
            "asian_low": 90.0,
            "london_high": 112.0,
            "london_low": 88.0,
            "po3_manipulation_high": 104.0,
            "po3_manipulation_low": 96.0,
            "sweep_low_level": 97.0,
        },
        index=idx,
    )
    metrics = TradeChartMetrics(
        entry_price=100.0,
        exit_price=101.0,
        direction=1,
        mae_price=99.0,
        mfe_price=101.0,
        mae_time=idx[2],
        mfe_time=idx[4],
        sl_price=96.0,
        tp_price=110.0,
        mae_drawn=False,
        mfe_drawn=False,
    )
    levels = order_levels(
        window,
        metrics,
        OverlayEvents(),
        window,
        idx[4],
        idx[5],
        pd.Series({"direction": 1}),
        show_mae_mfe=False,
        features=features,
    )
    assert levels.manip_spans == [(idx[0], idx[2])]
    assert levels.manip_ends == [idx[3]]
    assert levels.distribution_spans == [(idx[3], idx[4])]
    labels = {seg.label for seg in levels.segs}
    assert {
        "Asian high",
        "Asian low",
        "London high",
        "London low",
        "manip high",
        "manip low",
        "sweep",
    } <= labels
    fig, ax = plt.subplots()
    draw_order_levels_mpl(ax, levels)
    plt.close(fig)

    po3_levels = order_levels(
        window,
        metrics,
        OverlayEvents(),
        window,
        idx[4],
        idx[5],
        pd.Series(
            {
                "direction": 1,
                "entry_ideas": ["po3"],
                "entry_idea_timeframes": {"po3": ["M1"]},
            }
        ),
        show_mae_mfe=False,
        features=features,
        entry_idea_plot_config={
            "po3": {
                "timeframes": ["M1"],
                "show_manipulation": True,
                "show_distribution": False,
                "show_fvg": False,
                "show_ifvg": False,
            }
        },
    )
    assert po3_levels.manip_spans == [(idx[0], idx[2])]
    assert po3_levels.distribution_spans == []
    assert "PO3 M1 manipulation high" in {segment.label for segment in po3_levels.segs}


def test_selected_mtf_zone_families_create_timeframe_labeled_bands() -> None:
    idx = pd.date_range("2025-01-06 16:00", periods=5, freq="1min")
    window = pd.DataFrame({"open": 100.0, "high": 102.0, "low": 98.0, "close": 100.0}, index=idx)
    features = pd.DataFrame(
        {
            "ob_bull_active": 1.0,
            "ob_bull_low": 98.5,
            "ob_bull_high": 99.0,
            "M5_ob_bull_active": 1.0,
            "M5_ob_bull_low": 98.0,
            "M5_ob_bull_high": 98.5,
            "M1_fvg_bear_active": 1.0,
            "M1_fvg_bear_low": 101.0,
            "M1_fvg_bear_high": 101.5,
            "ifvg_bear_active": 1.0,
            "ifvg_bear_low": 101.5,
            "ifvg_bear_high": 102.0,
            "M5_last_swing_high": 110.0,
            "H1_last_swing_high": 110.0,
        },
        index=idx,
    )
    metrics = TradeChartMetrics(
        entry_price=100.0,
        exit_price=101.0,
        direction=1,
        mae_price=99.0,
        mfe_price=101.0,
        mae_time=idx[1],
        mfe_time=idx[3],
        sl_price=None,
        tp_price=None,
        mae_drawn=False,
        mfe_drawn=False,
    )

    levels = order_levels(
        window,
        metrics,
        OverlayEvents(),
        window,
        idx[0],
        idx[-1],
        pd.Series({"direction": 1}),
        features=features,
        order_block_timeframes=("M1", "M5"),
        fvg_timeframes=("M1",),
        ifvg_timeframes=("M1",),
        swing_timeframes=("M1", "M5", "H1"),
    )

    assert {zone.label for zone in levels.zones} == {
        "M1 Bull Order Block",
        "M5 Bull Order Block",
        "M1 Bear FVG",
        "M1 Bear IFVG",
    }
    # Synthetic aligned feature values have no matching source wick at 110;
    # omit them instead of drawing a level that appears to float in space.
    assert [seg.label for seg in levels.segs if "Swing" in seg.label] == []


def test_ema_exit_without_target_does_not_fabricate_a_tp_band() -> None:
    """A realized EMA exit is not a planned TP level."""
    idx = pd.date_range("2025-10-27 17:44", periods=40, freq="1min")
    close = np.linspace(25744.0, 25730.0, 40)
    bars = pd.DataFrame(
        {
            "open": close,
            "high": close + 6.0,
            "low": close - 6.0,
            "close": close,
        },
        index=idx,
    )
    open_row = pd.Series(
        {
            "time": idx[0],
            "direction": 1,
            "price": 25744.25,
            "sl_price": 25683.385,
            "tp_price": float("nan"),
            "tp_ref": "ema_21",
            "exit_mode": "ema_21",
        }
    )
    close_row = pd.Series({"time": idx[6], "price": 25729.85, "pnl": -21.53})
    metrics = compute_trade_metrics(bars, open_row, close_row)
    assert metrics.tp_price is None

    levels = order_levels(
        bars,
        metrics,
        OverlayEvents(),
        bars,
        idx[0],
        idx[6],
        open_row,
    )
    assert levels.green is None
    assert any("no fixed TP level" in note for note in levels.notes)
    assert levels.red is not None


def test_structural_target_keeps_the_entry_to_tp_band() -> None:
    idx = pd.date_range("2025-10-28 19:02", periods=40, freq="1min")
    close = np.linspace(25930.0, 25950.0, 40)
    bars = pd.DataFrame(
        {"open": close, "high": close + 5.0, "low": close - 5.0, "close": close},
        index=idx,
    )
    open_row = pd.Series(
        {
            "time": idx[0],
            "direction": -1,
            "price": 25929.75,
            "sl_price": 25951.66,
            "tp_price": 25870.0,
            "tp_ref": "H1_last_swing_low",
            "exit_mode": "structural",
        }
    )
    close_row = pd.Series({"time": idx[10], "price": 25945.0, "pnl": -200.0})
    metrics = compute_trade_metrics(bars, open_row, close_row)
    levels = order_levels(bars, metrics, OverlayEvents(), bars, idx[0], idx[10], open_row)
    assert levels.green is not None
    lo, hi = levels.green
    # A short's TP sits below the candles, so the entry is the top edge and the
    # TP edge is clipped up to the axis. This is the pre-existing target path.
    assert hi == pytest.approx(metrics.entry_price)
    assert lo >= levels.ylim[0] - 1e-6
    assert lo < hi


def test_legacy_order_chart_exports_forward_to_canonical_modules() -> None:
    assert legacy_order_chart.draw_order_levels_mpl is draw_order_levels_mpl
    assert legacy_order_chart.order_levels is order_levels
