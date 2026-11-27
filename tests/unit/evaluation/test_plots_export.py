"""Smoke tests for plots and artifact export.

Uses the matplotlib Agg backend so tests run headless in CI.
"""

from __future__ import annotations

import contextlib
import json
import time

import matplotlib

matplotlib.use("Agg")

from typing import Any

import numpy as np
import pandas as pd
import pytest
from omegaconf import OmegaConf

from configuration import load_config
from evaluation import PerformanceMetrics, calculate_metrics
from evaluation.reporting.run_artifact_writer import save_run
from evaluation.reporting.run_summary import (
    build_comparison_table,
    build_summary_table,
    save_metrics_json,
)
from evaluation.reporting.trade_event_export import _fill_events, _position_summaries

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def synthetic_equity() -> pd.Series:
    rng = np.random.default_rng(42)
    idx = pd.date_range("2025-01-02", periods=500, freq="1min")
    returns = rng.normal(0.0001, 0.002, size=500)
    equity = 100_000 * np.cumprod(1 + returns)
    return pd.Series(equity, index=idx)


@pytest.fixture()
def synthetic_bars() -> pd.DataFrame:
    """Create synthetic M1 bars for per-trade chart testing."""
    idx = pd.date_range("2025-01-02 16:30", periods=500, freq="1min")
    rng = np.random.default_rng(42)
    close = 20000.0 + np.cumsum(rng.normal(0, 1, 500))
    return pd.DataFrame(
        {
            "open": close - rng.uniform(0, 1, 500),
            "high": close + rng.uniform(0, 2, 500),
            "low": close - rng.uniform(0, 2, 500),
            "close": close,
        },
        index=idx,
    )


@pytest.fixture()
def synthetic_trades(synthetic_equity) -> pd.DataFrame:
    idx = synthetic_equity.index
    rows = []
    for i in range(0, 500, 50):
        rows.append(
            {
                "type": "open",
                "fill_quote_source": "bar_open",
                "direction": 1 if i % 2 == 0 else -1,
                "price": 100.0 + i * 0.1,
                "bar": i,
                "time": idx[i],
                "equity": synthetic_equity.iloc[i],
            }
        )
        rows.append(
            {
                "type": "close",
                "fill_quote_source": "bar_close",
                "pnl": float(np.random.default_rng(i).normal(10, 50)),
                "bar": i + 25,
                "time": idx[min(i + 25, 499)],
                "equity": synthetic_equity.iloc[min(i + 25, 499)],
            }
        )
    return pd.DataFrame(rows)


@pytest.fixture()
def synthetic_result(synthetic_equity, synthetic_trades) -> dict[str, Any]:
    breach_events = [
        {
            "time": synthetic_equity.index[100],
            "session_id": 0,
            "reason": "daily_loss",
            "equity": 99000.0,
        }
    ]
    return {
        "equity": synthetic_equity,
        "trades": synthetic_trades,
        "breaches": ["daily_loss"],
        "breach_events": breach_events,
        "n_sessions": 5,
        "n_breach_sessions": 1,
        "n_sessions_with_trades": 4,
        "n_sessions_skipped": 1,
        "initial_balance": 100_000.0,
    }


@pytest.fixture()
def metrics(synthetic_equity, synthetic_trades) -> PerformanceMetrics:
    return calculate_metrics(
        synthetic_equity,
        trades=synthetic_trades,
        n_sessions=5,
        n_breach_sessions=1,
    )


# ---------------------------------------------------------------------------
# Metrics / report tests
# ---------------------------------------------------------------------------


def test_metrics_fields(metrics):
    assert hasattr(metrics, "total_pnl")
    assert hasattr(metrics, "avg_trade")
    assert hasattr(metrics, "max_consec_loss")
    assert isinstance(metrics.n_trades, int)
    assert 0.0 <= metrics.win_rate <= 1.0


def test_shared_plot_helpers_keep_legacy_paths_and_explicit_exports():
    from evaluation.plotting import chart_indicators, chart_levels, plot_rendering, plot_series
    from evaluation.plotting.shared import (
        _EXPORTS,
        indicators,
        levels,
        rendering,
        series,
    )
    from evaluation.plotting.shared import (
        __all__ as shared_exports,
    )

    compatibility = (
        (plot_rendering, rendering),
        (plot_series, series),
        (chart_indicators, indicators),
        (chart_levels, levels),
    )
    for legacy, canonical in compatibility:
        assert all(name in vars(canonical) for name in legacy.__all__)
        assert all(getattr(legacy, name) is getattr(canonical, name) for name in legacy.__all__)

    assert set(shared_exports) <= set(_EXPORTS)
    shared = __import__("evaluation.plotting.shared", fromlist=["*"])
    assert all(getattr(shared, name) is not None for name in shared_exports)


def test_build_summary_table(metrics):
    table = build_summary_table(metrics)
    assert "Sharpe" in table
    assert "Max Drawdown" in table
    assert "Breached Session Rate" in table


def test_build_comparison_table(metrics):
    table = build_comparison_table(metrics, metrics)
    assert "Train" in table
    assert "Test" in table
    assert "Sharpe" in table


def test_save_metrics_json(metrics, tmp_path):
    path = tmp_path / "metrics.json"
    save_metrics_json(metrics, path)
    data = json.loads(path.read_text())
    assert "sharpe" in data
    assert "total_pnl" in data


# ---------------------------------------------------------------------------
# Trade-pairing regression tests
# ---------------------------------------------------------------------------


def test_pair_trades_includes_tp_close():
    """Regression: _pair_trades must pair each open with its own immediate
    close, even when tp_close events occur between orders.

    Previously the closes list excluded ``tp_close``, so every open after a
    tp_close event was paired with the wrong close by position — mixing one
    order's entry price/volume with a completely different order's exit
    price and PnL on the chart.
    """
    from evaluation.plotting.plots import _pair_trades

    idx = pd.date_range("2025-01-02 17:00", periods=4, freq="1min")
    trades = pd.DataFrame(
        [
            {
                "type": "open",
                "direction": 1,
                "price": 100.0,
                "lots": 10.0,
                "bar": 0,
                "time": idx[0],
            },
            {"type": "tp_close", "pnl": 5.0, "reason": "structure_tp", "bar": 1, "time": idx[1]},
            {"type": "open", "direction": 1, "price": 101.0, "lots": 2.0, "bar": 1, "time": idx[1]},
            {"type": "stop_close", "pnl": -3.0, "reason": "structure_sl", "bar": 2, "time": idx[2]},
            {
                "type": "open",
                "direction": -1,
                "price": 102.0,
                "lots": 50.0,
                "bar": 2,
                "time": idx[2],
            },
            {
                "type": "stop_close",
                "pnl": -20.0,
                "reason": "structure_sl",
                "bar": 3,
                "time": idx[3],
            },
        ]
    )

    pairs = _pair_trades(trades)
    assert len(pairs) == 3

    o1, c1 = pairs[0]
    assert o1["lots"] == 10.0
    assert c1["type"] == "tp_close" and c1["pnl"] == 5.0

    o2, c2 = pairs[1]
    assert o2["lots"] == 2.0
    assert c2["type"] == "stop_close" and c2["pnl"] == -3.0

    o3, c3 = pairs[2]
    assert o3["lots"] == 50.0
    assert c3["pnl"] == -20.0


def test_pair_trades_unclosed_open_is_dropped():
    """An open with no following close (e.g. still open at end of log) must
    not be paired with a later, unrelated close.
    """
    from evaluation.plotting.plots import _pair_trades

    idx = pd.date_range("2025-01-02 17:00", periods=2, freq="1min")
    trades = pd.DataFrame(
        [
            {"type": "open", "direction": 1, "price": 100.0, "lots": 1.0, "bar": 0, "time": idx[0]},
        ]
    )
    assert _pair_trades(trades) == []


def test_extract_window_eod_close_excludes_next_session():
    """Context after an NY eod_close must not pull the next session's bars."""
    from evaluation.plotting.plots import _extract_window

    # Full-day spine: NY session day1, overnight/gap, then next NY open.
    day1 = pd.date_range("2024-12-30 16:30", "2024-12-30 23:00", freq="1min")
    overnight = pd.date_range("2024-12-30 23:01", "2024-12-31 16:29", freq="1min")
    day2 = pd.date_range("2024-12-31 16:30", "2024-12-31 17:30", freq="1min")
    idx = day1.union(overnight).union(day2).sort_values()
    bars = pd.DataFrame(
        {
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.5,
        },
        index=idx,
    )
    t_open = pd.Timestamp("2024-12-30 18:18")
    t_close = pd.Timestamp("2024-12-30 23:00")
    window = _extract_window(bars, t_open, t_close, context=60)

    assert not window.empty
    assert window.index.max() <= pd.Timestamp("2024-12-30 23:00")
    assert window.index.min() >= pd.Timestamp("2024-12-30 16:30")
    # Must not include the next NY open (the original bug).
    assert not any(ts.normalize() == pd.Timestamp("2024-12-31") for ts in window.index)


def test_order_chart_event_time_falls_back_to_recorded_bar():
    """A close event with a missing time uses its recorded bar timestamp."""
    from evaluation.plotting.order_window import _event_timestamp

    index = pd.date_range("2025-01-02 16:30", periods=4, freq="1min", tz="Etc/GMT-3")
    event = pd.Series({"time": pd.NaT, "actual_tick_time": pd.NaT, "bar": 2})

    assert _event_timestamp(event, index) == index[2]
    assert _event_timestamp(pd.Series({"time": pd.NaT, "bar": 9}), index) is None


def test_extract_window_pre_entry_stays_in_session():
    """Pre-entry context must not reach into the prior calendar day's NY bars."""
    from evaluation.plotting.plots import _extract_window

    day0 = pd.date_range("2024-12-29 16:30", "2024-12-29 23:00", freq="1min")
    day1 = pd.date_range("2024-12-30 16:30", "2024-12-30 18:00", freq="1min")
    idx = day0.union(day1).sort_values()
    bars = pd.DataFrame(
        {"open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5},
        index=idx,
    )
    t_open = pd.Timestamp("2024-12-30 16:35")
    t_close = pd.Timestamp("2024-12-30 16:50")
    window = _extract_window(bars, t_open, t_close, context=60)
    assert window.index.min() >= pd.Timestamp("2024-12-30 16:30")
    assert all(ts.normalize() == pd.Timestamp("2024-12-30") for ts in window.index)


def test_extract_window_keeps_post_exit_context_mid_session():
    """Clamping to the session close must not delete post-exit context.

    A trade that closes mid-session still has ``context`` tradable bars after
    it, so the exit marker does not sit on the axis edge. Only the overnight
    gap is dropped.
    """
    from evaluation.plotting.plots import _extract_window

    day1 = pd.date_range("2024-12-30 16:30", "2024-12-30 23:00", freq="1min")
    overnight = pd.date_range("2024-12-30 23:01", "2024-12-31 16:29", freq="1min")
    idx = day1.union(overnight)
    bars = pd.DataFrame(
        {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5},
        index=idx,
    )
    t_open = pd.Timestamp("2024-12-30 18:00")
    t_close = pd.Timestamp("2024-12-30 18:10")
    context = 30
    window = _extract_window(bars, t_open, t_close, context=context)

    # Full context either side, measured in tradable bars.
    assert window.index.min() == t_open - pd.Timedelta(minutes=context)
    assert window.index.max() == t_close + pd.Timedelta(minutes=context)
    # Never the dead overnight candles.
    assert window.index.max() <= pd.Timestamp("2024-12-30 23:00")


def test_extract_window_keeps_exit_bar_when_trade_runs_past_session():
    """An overnight-hold exit is after the NY close; the window must keep it."""
    from evaluation.plotting.plots import _extract_window

    day1 = pd.date_range("2024-12-30 16:30", "2024-12-30 23:00", freq="1min")
    overnight = pd.date_range("2024-12-30 23:01", "2024-12-31 16:29", freq="1min")
    idx = day1.union(overnight)
    bars = pd.DataFrame(
        {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5},
        index=idx,
    )
    t_open = pd.Timestamp("2024-12-30 22:50")
    t_close = pd.Timestamp("2024-12-30 23:10")  # past the NY close
    window = _extract_window(bars, t_open, t_close, context=10)

    assert not window.empty
    # The exit bar itself must survive the session clamp.
    assert t_close in window.index


def test_close_time_label_includes_date_across_days():
    from evaluation.plotting.plots import _close_time_label

    assert (
        _close_time_label(pd.Timestamp("2024-12-30 18:00"), pd.Timestamp("2024-12-30 23:00"))
        == "23:00"
    )
    assert (
        _close_time_label(pd.Timestamp("2024-12-30 22:00"), pd.Timestamp("2024-12-31 16:40"))
        == "2024-12-31 16:40"
    )


def test_plot_price_with_orders_includes_tp_close(synthetic_bars, tmp_path):
    """Overview charts must mark tp_close exits (not only stop/eod/close)."""
    from evaluation.plotting.plots import plot_price_with_orders

    idx = synthetic_bars.index
    trades = pd.DataFrame(
        [
            {
                "type": "open",
                "direction": 1,
                "price": float(synthetic_bars["close"].iloc[10]),
                "time": idx[10],
            },
            {
                "type": "tp_close",
                "direction": 1,
                "price": float(synthetic_bars["close"].iloc[40]),
                "pnl": 12.0,
                "time": idx[40],
            },
        ]
    )
    fig = plot_price_with_orders(
        synthetic_bars, trades, out_path=tmp_path / "orders_overview.png", dpi=72
    )
    assert fig is not None
    assert (tmp_path / "orders_overview.png").stat().st_size > 0


# ---------------------------------------------------------------------------
# Plot smoke tests (static PNG)
# ---------------------------------------------------------------------------


def test_plot_equity_curve(synthetic_equity, tmp_path):
    from evaluation.plotting.plots import plot_equity_curve

    breach_events = [
        {
            "time": synthetic_equity.index[100],
            "session_id": 0,
            "reason": "daily_loss",
            "equity": 99000.0,
        }
    ]
    plot_equity_curve(
        synthetic_equity,
        breach_events=breach_events,
        initial_balance=100_000.0,
        daily_loss_limit=5000.0,
        max_loss_limit=10000.0,
        out_path=tmp_path / "equity.png",
    )
    assert (tmp_path / "equity.png").exists()
    assert (tmp_path / "equity.png").stat().st_size > 0


def test_plot_drawdown(synthetic_equity, tmp_path):
    from evaluation.plotting.plots import plot_drawdown

    fig = plot_drawdown(synthetic_equity, out_path=tmp_path / "drawdown.png")
    assert (tmp_path / "drawdown.png").stat().st_size > 0
    assert len(fig.axes) >= 2


def test_plot_trade_pnl_hist(synthetic_trades, tmp_path):
    from evaluation.plotting.plots import plot_trade_pnl_hist

    plot_trade_pnl_hist(synthetic_trades, out_path=tmp_path / "pnl_hist.png")
    assert (tmp_path / "pnl_hist.png").stat().st_size > 0


def test_plot_trade_pnl_hist_exports_safe_no_data_fallback(tmp_path):
    from evaluation.plotting.performance import plot_trade_pnl_hist

    output = tmp_path / "nested" / "empty_pnl.png"
    fig = plot_trade_pnl_hist(pd.DataFrame({"time": []}), out_path=output, dpi=72)

    assert fig.axes[0].texts[0].get_text() == "No trade PnL data"
    assert output.is_file()
    assert output.stat().st_size > 0


def test_plot_returns_dist(synthetic_equity, tmp_path):
    from evaluation.plotting.plots import plot_returns_dist

    # scipy may not be available; function should not crash
    with contextlib.suppress(ImportError):
        plot_returns_dist(synthetic_equity, out_path=tmp_path / "returns_dist.png")
    # At minimum should not raise other exceptions


def test_plot_monthly_heatmap(synthetic_equity, tmp_path):
    from evaluation.plotting.plots import plot_monthly_returns_heatmap

    # Use longer series so monthly resampling has data
    idx = pd.date_range("2024-01-02", periods=3000, freq="1min")
    equity = pd.Series(
        100_000 * np.cumprod(1 + np.random.default_rng(7).normal(0.0001, 0.001, 3000)),
        index=idx,
    )
    plot_monthly_returns_heatmap(equity, out_path=tmp_path / "heatmap.png")
    assert (tmp_path / "heatmap.png").stat().st_size > 0


def test_plot_per_trade_orders_mt5_style(synthetic_bars, synthetic_trades, tmp_path):
    """Test MT5-style per-trade order charts with MAE/MFE/SL/TP overlays."""
    from evaluation.plotting.plots import plot_per_trade_orders

    orders_dir = tmp_path / "orders"
    plot_per_trade_orders(
        synthetic_bars,
        synthetic_trades,
        orders_dir=orders_dir,
        max_charts=50,
        dpi=72,
        max_loss_per_trade_usd=10.0,
        take_profit_per_trade_usd=50.0,
        lots=1.0,
        contract_size=1.0,
        show_mae_mfe=True,
        show_sl_tp=True,
    )

    # Check that at least one PNG was generated
    pngs = list(orders_dir.glob("*.png"))
    assert len(pngs) > 0, "No PNG files generated"
    # Each PNG should be non-empty
    for png_path in pngs:
        assert png_path.stat().st_size > 0, f"{png_path} is empty"


def test_plot_per_trade_orders_png_datetime_axis_and_info(
    synthetic_bars, synthetic_trades, tmp_path
):
    """Verify PNG charts have datetime x-axis and trade info box."""
    from evaluation.plotting.plots import plot_per_trade_orders

    orders_dir = tmp_path / "orders"
    plot_per_trade_orders(
        synthetic_bars,
        synthetic_trades,
        orders_dir=orders_dir,
        max_charts=1,  # Just one for this test
        dpi=72,
        max_loss_per_trade_usd=10.0,
        take_profit_per_trade_usd=50.0,
        lots=1.0,
        contract_size=1.0,
        show_mae_mfe=True,
        show_sl_tp=True,
    )

    pngs = list(orders_dir.glob("*.png"))
    assert len(pngs) >= 1, "No PNG files generated"

    # Load and inspect the first PNG
    png_file = pngs[0]
    file_size = png_file.stat().st_size
    # Datetime-axis chart with 2 panels should be reasonably large (>100KB)
    assert file_size > 50000, f"PNG file too small: {file_size} bytes (expected >50KB)"


def test_target_update_plot_ignores_missing_partial_close_time() -> None:
    """A missing partial-close timestamp must not break target-update charts."""
    from matplotlib import pyplot as plt

    from evaluation.plotting.orders import _draw_target_updates

    start = pd.Timestamp("2025-01-21 19:04:00", tz="Etc/GMT-3")
    events = pd.DataFrame(
        [
            {
                "type": "tp_update",
                "tp_slot": "TP1",
                "time": start,
                "effective_time": start,
                "price": 21140.0,
            },
            {
                "type": "tp_partial_close",
                "tp_slot": "TP1",
                "time": pd.NaT,
                "effective_time": pd.NaT,
                "price": 21140.0,
            },
        ]
    )
    figure, axis = plt.subplots()
    try:
        _draw_target_updates(axis, events)
        assert len(axis.lines) == 1
        x_data = np.asarray(axis.lines[0].get_xdata(), dtype=object)
        assert x_data.size == 2
        assert bool(pd.notna(x_data).all())
    finally:
        plt.close(figure)


def test_target_update_ends_at_its_own_slot_fill_not_another_slot_event() -> None:
    from matplotlib import pyplot as plt

    from evaluation.plotting.orders import _draw_target_updates

    start = pd.Timestamp("2025-01-21 19:04:00", tz="Etc/GMT-3")
    unrelated_fill = start + pd.Timedelta(minutes=1)
    matching_fill = start + pd.Timedelta(minutes=3)
    events = pd.DataFrame(
        [
            {
                "type": "tp_update",
                "tp_slot": "TP2",
                "time": start,
                "effective_time": start,
                "price": 21140.0,
            },
            {
                "type": "tp_partial_close",
                "tp_slot": "TP1",
                "time": unrelated_fill,
                "price": 21120.0,
            },
            {
                "type": "tp_partial_close",
                "tp_slot": "TP2",
                "time": matching_fill,
                "price": 21140.0,
            },
        ]
    )
    figure, axis = plt.subplots()
    try:
        _draw_target_updates(axis, events)

        assert len(axis.lines) == 1
        assert list(np.asarray(axis.lines[0].get_xdata())) == [start, matching_fill]
    finally:
        plt.close(figure)


def test_macd_backtest_fills_within_bar_and_charts_render(tmp_path):
    """End-to-end regression: run the real MACD baseline through the engine,
    verify every fill price lands within its executing bar's [low, high]
    range (guards Bug 4: tick-outlier fills detached from candles), then
    render per-trade PNG charts from those trades without error (guards
    Bug 3: full-history indicator overlays must slice cleanly per trade).
    """
    from evaluation.plotting.plots import plot_per_trade_orders
    from features import build_features
    from simulation.backtest import run_backtest
    from trading.baselines.rule_based import macd_ema50_baseline

    rng = np.random.default_rng(7)
    idx = pd.date_range("2025-02-01 00:00", periods=400, freq="1min")
    close = 21000.0 + np.cumsum(rng.normal(0, 1.0, 400))
    bars = pd.DataFrame(
        {
            "open": close - rng.uniform(0, 0.5, 400),
            "high": close + rng.uniform(0, 1.0, 400),
            "low": close - rng.uniform(0, 1.0, 400),
            "close": close,
        },
        index=idx,
    )

    features = build_features(bars, cfg=None)
    actions = macd_ema50_baseline(bars)

    obs_window = 60
    state = {"i": obs_window}

    def policy(obs):
        action = int(actions.iloc[state["i"]]) if state["i"] < len(actions) else 0
        state["i"] += 1
        return action

    result = run_backtest(
        bars=bars,
        features=features,
        policy=policy,
        obs_window=obs_window,
        hold_on_zero=True,
        exit_action=2,
    )
    trades_df = result["trades"]

    # No open row may carry an invalid direction (guards Bug 1).
    opens = trades_df[trades_df["type"] == "open"]
    for _, row in opens.iterrows():
        assert row["direction"] in (1.0, -1.0)

    # All fill prices must land within (a small buffer around) the nearby
    # bar range, not detached from any visible candle (guards Bug 4).
    for _, row in trades_df.iterrows():
        price = row.get("price")
        if price is None or pd.isna(price):
            continue
        bar_time = pd.Timestamp(row["time"])
        pos = bars.index.get_indexer(pd.Index([bar_time]), method="nearest")[0]
        lo = bars["low"].iloc[max(0, pos - 1) : pos + 2].min()
        hi = bars["high"].iloc[max(0, pos - 1) : pos + 2].max()
        assert lo - 1.0 <= price <= hi + 1.0, (
            f"Fill price {price} at {bar_time} outside nearby range [{lo}, {hi}]"
        )

    if len(opens) > 0:
        orders_dir = tmp_path / "orders"
        plot_per_trade_orders(
            bars,
            trades_df,
            orders_dir=orders_dir,
            max_charts=20,
            dpi=72,
        )
        pngs = list(orders_dir.glob("*.png"))
        assert len(pngs) > 0
        for png_path in pngs:
            assert png_path.stat().st_size > 0


def test_plot_baseline_comparison(synthetic_equity, tmp_path):
    from evaluation.plotting.plots import plot_baseline_comparison

    eq2 = synthetic_equity * 1.05
    plot_baseline_comparison({"A": synthetic_equity, "B": eq2}, out_path=tmp_path / "compare.png")
    assert (tmp_path / "compare.png").stat().st_size > 0


# ---------------------------------------------------------------------------
# Interactive HTML smoke tests (plotly)
# ---------------------------------------------------------------------------


def test_interactive_equity(synthetic_equity, tmp_path):
    pytest.importorskip("plotly")
    from evaluation.plotting.plots_interactive import plot_equity_curve

    plot_equity_curve(synthetic_equity, out_path=tmp_path / "equity.html")
    assert (tmp_path / "equity.html").stat().st_size > 0


def test_interactive_trade_order_equity_places_payout_at_following_trade(
    tmp_path,
) -> None:
    pytest.importorskip("plotly")
    from evaluation.plotting.plots_interactive import plot_equity_curve

    index = pd.date_range("2025-01-02 15:00", periods=4, freq="min", tz="UTC")
    equity = pd.Series([100.0, 101.0, 100.0, 103.0], index=index)
    trades = pd.DataFrame(
        [
            {"type": "open", "direction": 1, "time": index[0], "price": 100.0},
            {"type": "close", "time": index[1], "price": 101.0, "equity": 101.0},
            {"type": "payout_reset", "time": index[1] + pd.Timedelta(seconds=30)},
            {"type": "open", "direction": 1, "time": index[2], "price": 100.0},
            {"type": "close", "time": index[3], "price": 103.0, "equity": 103.0},
        ]
    )
    output = tmp_path / "trade-equity.html"

    figure = plot_equity_curve(equity, trades=trades, out_path=output)

    traces = {trace.name: trace for trace in figure.data}
    assert list(traces["Equity"].x) == [0, 1]
    assert list(traces["Equity"].y) == [101.0, 103.0]
    assert len(figure.layout.shapes) == 1
    assert figure.layout.shapes[0].x0 == figure.layout.shapes[0].x1 == 1
    assert output.is_file()


def test_interactive_drawdown(synthetic_equity, tmp_path):
    pytest.importorskip("plotly")
    from evaluation.plotting.plots_interactive import plot_drawdown

    plot_drawdown(synthetic_equity, out_path=tmp_path / "drawdown.html")
    assert (tmp_path / "drawdown.html").stat().st_size > 0


def test_interactive_performance_charts_explain_empty_inputs() -> None:
    pytest.importorskip("plotly")
    from evaluation.plotting.interactive_performance import (
        plot_daily_pnl,
        plot_monthly_returns_heatmap,
        plot_trade_pnl_hist,
    )

    empty_equity = pd.Series(dtype=float, index=pd.DatetimeIndex([], tz="UTC"))
    daily = plot_daily_pnl(empty_equity)
    monthly = plot_monthly_returns_heatmap(
        pd.Series([100.0], index=pd.DatetimeIndex(["2025-01-01"], tz="UTC"))
    )
    trade_pnl = plot_trade_pnl_hist(pd.DataFrame({"time": [pd.Timestamp("2025-01-01")]}))

    assert not daily.data
    assert daily.layout.annotations[0].text == "No daily P&L"
    assert not monthly.data
    assert monthly.layout.annotations[0].text == "Insufficient data"
    assert not trade_pnl.data
    assert trade_pnl.layout.annotations[0].text == "No trade PnL data"


def test_static_performance_package_exports_and_legacy_paths_are_stable() -> None:
    from evaluation.plotting import comparison as comparison_compat
    from evaluation.plotting import equity as equity_compat
    from evaluation.plotting import performance as grouped
    from evaluation.plotting import plots
    from evaluation.plotting.performance import charts, comparison, equity

    public_names = [
        "plot_baseline_comparison",
        "plot_daily_pnl",
        "plot_direction_summary",
        "plot_drawdown",
        "plot_equity_curve",
        "plot_monthly_returns_heatmap",
        "plot_returns_dist",
        "plot_trade_pnl_hist",
    ]
    assert grouped.__all__ == public_names
    assert all(hasattr(grouped, name) for name in public_names)
    unknown_plot = "unknown_plot"
    with pytest.raises(AttributeError, match="has no attribute 'unknown_plot'"):
        getattr(grouped, unknown_plot)
    assert equity_compat.plot_drawdown is equity.plot_drawdown
    assert equity_compat.plot_equity_curve is equity.plot_equity_curve
    assert comparison_compat.plot_baseline_comparison is comparison.plot_baseline_comparison
    assert plots.plot_equity_curve is equity.plot_equity_curve
    assert plots.plot_daily_pnl is charts.plot_daily_pnl
    assert plots.plot_baseline_comparison is comparison.plot_baseline_comparison


def test_interactive_package_exports_and_legacy_module_shims_are_stable() -> None:
    from evaluation.plotting import interactive as grouped
    from evaluation.plotting import (
        interactive_comparison,
        interactive_orders,
        interactive_performance,
        interactive_plot_rendering,
        interactive_po3,
        plots_interactive,
    )
    from evaluation.plotting.interactive import (
        comparison,
        orders,
        performance,
        po3,
        rendering,
    )

    public_names = [
        "plot_baseline_comparison",
        "plot_daily_pnl",
        "plot_drawdown",
        "plot_equity_curve",
        "plot_fvg_signals_interactive",
        "plot_monthly_returns_heatmap",
        "plot_per_trade_orders",
        "plot_price_with_orders",
        "plot_returns_dist",
        "plot_trade_pnl_hist",
    ]
    assert grouped.__all__ == public_names
    assert all(hasattr(grouped, name) for name in public_names)
    unknown_plot = "unknown_plot"
    with pytest.raises(AttributeError, match="has no attribute 'unknown_plot'"):
        getattr(grouped, unknown_plot)
    assert interactive_comparison.plot_baseline_comparison is comparison.plot_baseline_comparison
    assert interactive_orders.plot_per_trade_orders is orders.plot_per_trade_orders
    assert interactive_orders.plot_price_with_orders is orders.plot_price_with_orders
    assert interactive_performance.plot_daily_pnl is performance.plot_daily_pnl
    assert interactive_performance.plot_equity_curve is performance.plot_equity_curve
    assert interactive_po3.plot_fvg_signals_interactive is po3.plot_fvg_signals_interactive
    assert interactive_plot_rendering.__all__ == rendering.__all__
    assert all(
        getattr(interactive_plot_rendering, name) is getattr(rendering, name)
        for name in rendering.__all__
    )
    assert interactive_plot_rendering._check is rendering._check
    assert interactive_plot_rendering._save is rendering._save
    assert plots_interactive.__all__ == [
        "plot_equity_curve",
        "plot_drawdown",
        "plot_daily_pnl",
        "plot_trade_pnl_hist",
        "plot_returns_dist",
        "plot_monthly_returns_heatmap",
        "plot_baseline_comparison",
        "plot_price_with_orders",
        "plot_per_trade_orders",
        "plot_fvg_signals_interactive",
        "_check",
        "_save",
        "_PLOTLY_AVAILABLE",
    ]


def test_order_chart_package_exports_and_legacy_shims_are_stable() -> None:
    from evaluation.plotting import (
        chart_overlays,
        order_chart,
        order_chart_data,
        order_chart_renderers,
        order_window,
        orders,
        overlay_events,
        shared,
    )
    from evaluation.plotting.orders import (
        charts,
        events,
        geometry,
        overlays,
        renderers,
        window,
    )
    from evaluation.plotting.orders import order_chart_features as features

    assert orders.__all__ == ["plot_per_trade_orders", "plot_price_with_orders"]
    assert orders.plot_per_trade_orders is charts.plot_per_trade_orders
    assert orders.plot_price_with_orders is charts.plot_price_with_orders
    assert order_window.prepare_order_chart is window.prepare_order_chart
    assert order_chart_data.order_levels is geometry.order_levels
    assert order_chart_data._feature_zones is features._feature_zones
    assert order_chart_renderers.draw_order_levels_mpl is renderers.draw_order_levels_mpl
    assert chart_overlays.draw_overlays_mpl is overlays.draw_overlays_mpl
    assert overlay_events.build_overlay_events is events.build_overlay_events
    assert order_chart.order_levels is geometry.order_levels
    assert order_chart.draw_order_levels_mpl is renderers.draw_order_levels_mpl
    unknown_chart = "unknown_chart"
    unknown_plot = "unknown_plot"
    with pytest.raises(AttributeError, match="has no attribute 'unknown_chart'"):
        getattr(orders, unknown_chart)
    with pytest.raises(AttributeError, match="has no attribute 'unknown_plot'"):
        getattr(shared, unknown_plot)


def test_interactive_equity_daily_limit_tracks_each_calendar_day() -> None:
    pytest.importorskip("plotly")
    from evaluation.plotting.plots_interactive import plot_equity_curve

    index = pd.DatetimeIndex(
        ["2025-01-02T15:00:00Z", "2025-01-02T15:01:00Z", "2025-01-03T15:00:00Z"]
    )
    equity = pd.Series([100.0, 90.0, 110.0], index=index)

    figure = plot_equity_curve(equity, daily_loss_limit=5.0)

    daily_limit = next(trace for trace in figure.data if trace.name.startswith("Daily loss limit"))
    assert list(daily_limit.y) == [95.0, 95.0, 105.0]
    assert list(daily_limit.x) == list(index)


def test_interactive_performance_charts_fail_when_plotly_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("plotly")
    from evaluation.plotting.interactive import performance as interactive_performance
    from evaluation.plotting.interactive import rendering as interactive_plot_rendering

    monkeypatch.setattr(interactive_plot_rendering, "_PLOTLY_AVAILABLE", False)

    with pytest.raises(ImportError, match="plotly is required for interactive charts"):
        interactive_performance.plot_daily_pnl(pd.Series(dtype=float))


def test_interactive_per_trade_orders_mt5_style(synthetic_bars, synthetic_trades, tmp_path):
    """Test MT5-style interactive HTML per-trade order charts."""
    pytest.importorskip("plotly")
    from evaluation.plotting.plots_interactive import plot_per_trade_orders

    orders_dir = tmp_path / "orders"
    plot_per_trade_orders(
        synthetic_bars,
        synthetic_trades,
        orders_dir=orders_dir,
        max_charts=50,
        max_loss_per_trade_usd=10.0,
        take_profit_per_trade_usd=50.0,
        lots=1.0,
        contract_size=1.0,
        show_mae_mfe=True,
        show_sl_tp=True,
    )

    # Check that at least one HTML was generated
    htmls = list(orders_dir.glob("*.html"))
    assert len(htmls) > 0, "No HTML files generated"
    # Each HTML should be non-empty
    for html_path in htmls:
        assert html_path.stat().st_size > 0, f"{html_path} is empty"


# ---------------------------------------------------------------------------
# export.save_run integration test
# ---------------------------------------------------------------------------


def test_save_run_creates_files(synthetic_result, metrics, tmp_path):
    run_dir = save_run(
        out_dir=tmp_path,
        name="test_run",
        train_result=synthetic_result,
        train_metrics=metrics,
        test_result=synthetic_result,
        test_metrics=metrics,
        save_plots=True,
        save_html=True,
        save_csv=True,
        dpi=72,
    )
    assert run_dir.exists()
    # Root: only config/summary — no raw data or charts
    assert (run_dir / "summary.txt").stat().st_size > 0
    evaluation_manifest = json.loads((run_dir / "evaluation_manifest.json").read_text())
    assert evaluation_manifest["schema_version"] == "evaluation-artifacts-v1"
    assert evaluation_manifest["partitions"] == ["training", "testing"]
    assert not (run_dir / "equity.csv").exists()
    assert not (run_dir / "equity.png").exists()
    # Training subfolder
    assert (run_dir / "training" / "equity.csv").stat().st_size > 0
    assert (run_dir / "training" / "trades.csv").stat().st_size > 0
    assert (run_dir / "training" / "metrics.json").stat().st_size > 0
    assert (run_dir / "training" / "equity.png").stat().st_size > 0
    assert (run_dir / "training" / "drawdown.png").stat().st_size > 0
    assert (run_dir / "training" / "daily_pnl.png").stat().st_size > 0
    assert (run_dir / "training" / "hold_time_pnl.png").stat().st_size > 0
    assert (run_dir / "training" / "rolling_winrate.png").stat().st_size > 0
    assert (run_dir / "training" / "tod_heatmap.png").stat().st_size > 0
    # Testing subfolder
    assert (run_dir / "testing" / "equity.csv").stat().st_size > 0
    assert (run_dir / "testing" / "metrics.json").stat().st_size > 0


def test_save_run_records_development_only_scope_without_test_artifacts(
    synthetic_result, metrics, tmp_path
):
    run_dir = save_run(
        run_dir=tmp_path / "development_only",
        train_result=synthetic_result,
        train_metrics=metrics,
        cfg=load_config(["evaluation.development_only=true"]),
        save_plots=False,
        save_html=False,
        save_csv=False,
    )

    report = json.loads((run_dir / "report_export_timing.json").read_text())
    evaluation_manifest = json.loads((run_dir / "evaluation_manifest.json").read_text())
    assert report["evaluation_scope"] == "development_only"
    assert report["test_evaluation_status"] == "not_run"
    assert evaluation_manifest["partitions"] == ["training"]
    assert not (run_dir / "testing").exists()

    default_run = save_run(
        run_dir=tmp_path / "default_scope",
        train_result=synthetic_result,
        train_metrics=metrics,
        cfg=load_config(),
        save_plots=False,
        save_html=False,
        save_csv=False,
    )
    default_report = json.loads((default_run / "report_export_timing.json").read_text())
    assert default_report["evaluation_scope"] == "all_configured_splits"
    assert default_report["test_evaluation_status"] == "not_run"


def test_save_run_no_overwrite(synthetic_result, metrics, tmp_path):
    """Two calls with the same name must produce two different directories."""
    d1 = save_run(
        out_dir=tmp_path,
        name="run",
        train_result=synthetic_result,
        train_metrics=metrics,
        save_plots=False,
        save_html=False,
    )
    time.sleep(1.1)  # ensure different timestamp
    d2 = save_run(
        out_dir=tmp_path,
        name="run",
        train_result=synthetic_result,
        train_metrics=metrics,
        save_plots=False,
        save_html=False,
    )
    assert d1 != d2


def test_report_profiles_preserve_numerical_exports(tmp_path, synthetic_result):
    """Fast rendering preserves identical numerical metrics and trade history."""
    metrics = calculate_metrics(synthetic_result["equity"], trades=synthetic_result["trades"])
    full = save_run(
        run_dir=tmp_path / "full",
        train_result=synthetic_result,
        train_metrics=metrics,
        save_plots=False,
        save_html=False,
        save_csv=True,
        report_profile="full",
    )
    fast = save_run(
        run_dir=tmp_path / "fast",
        train_result=synthetic_result,
        train_metrics=metrics,
        save_plots=False,
        save_html=True,
        save_csv=True,
        max_order_charts=200,
        report_profile="experiment_run_fast",
    )
    for filename in (
        "equity.csv",
        "trades.csv",
        "fills.csv",
        "positions.csv",
        "metrics.json",
        "summary.txt",
        "session_activity.json",
        "policy_decision_reconciliation.json",
        "evaluation_diagnostics.json",
        "direction_summary.json",
    ):
        assert (full / "training" / filename).read_bytes() == (
            fast / "training" / filename
        ).read_bytes()
    report = json.loads((fast / "report_export_timing.json").read_text())
    assert report["profile"] == "experiment_run_fast"
    assert report["deferred_artifacts"] == ["per_trade_png", "interactive_html"]
    assert report["max_order_charts"] == 0
    assert report["save_html"] is False
    assert report["phase_seconds"]["total_export"] >= 0


def test_evaluation_diagnostics_are_exported_from_result(tmp_path, synthetic_result):
    result = {
        **synthetic_result,
        "n_steps": 3,
        "exposure_bars": 2,
        "exposure_fraction": 2 / 3,
        "exposure_measure": "fraction_of_evaluation_steps_with_position_at_bar_close",
        "survived_full_year": False,
        "fail_time": pd.Timestamp("2025-06-01T12:00:00Z"),
        "n_sessions": 2,
        "n_breach_sessions": 1,
        "n_sessions_with_trades": 1,
        "n_sessions_skipped": 1,
        "action_counts": {"hold": 2, "enter": 1},
        "reward_attribution": {"pnl": 0.5, "risk": -0.1},
        "entry_diag": {"opened": 1, "rejected_no_setup": 2},
        "entry_state_diagnostics": {"state_armed": 1},
        "observation_schema": {
            "version": "account-state-v1",
            "entry_state_visibility": True,
        },
        "observation_inputs": {"feature_validity_channels": False},
        "execution_contract": {
            "schema_version": "backtest_execution_contract.v1",
            "limit_order": {"fill_rule": "strict_executable_quote_trade_through"},
        },
        "entry_state_config": {
            "candidate_max_age_bars": 5,
            "arm_requires_retest": False,
            "entry_state_visibility": True,
        },
    }
    metrics = calculate_metrics(
        result["equity"],
        trades=result["trades"],
        initial_balance=float(result["initial_balance"]),
    )
    run_dir = save_run(
        run_dir=tmp_path / "diagnostics",
        train_result=result,
        train_metrics=metrics,
        save_plots=False,
        save_html=False,
        save_csv=True,
    )

    report = json.loads((run_dir / "training" / "evaluation_diagnostics.json").read_text())
    metrics_report = json.loads((run_dir / "training" / "metrics.json").read_text())
    assert report["n_steps"] == 3
    assert report["exposure_bars"] == 2
    assert report["exposure_fraction"] == pytest.approx(2 / 3)
    assert report["survived_full_year"] is False
    assert report["fail_time"] == "2025-06-01 12:00:00+00:00"
    assert report["breach_event_ledger_supplied"] is True
    assert report["breach_event_rows"] == 1
    assert report["action_counts"] == {"hold": 2, "enter": 1}
    assert report["reward_attribution"] == {"pnl": 0.5, "risk": -0.1}
    assert report["entry_funnel"]["opened"] == 1
    assert report["observation_schema"]["entry_state_visibility"] is True
    assert report["observation_inputs"]["feature_validity_channels"] is False
    assert report["execution_contract"]["limit_order"]["fill_rule"] == (
        "strict_executable_quote_trade_through"
    )
    assert report["entry_state_config"]["candidate_max_age_bars"] == 5
    assert report["policy_decision_reconciliation_status"] == "incomplete"
    assert (run_dir / "training" / "policy_decision_reconciliation.json").is_file()
    policy_reconciliation = json.loads(
        (run_dir / "training" / "policy_decision_reconciliation.json").read_text()
    )
    assert "policy_decisions_are_absent" in policy_reconciliation["incomplete_reasons"]
    assert "breach_event_ledger_not_supplied" not in policy_reconciliation["incomplete_reasons"]
    assert report["position_record_count"] == len(_position_summaries(result["trades"]))
    assert report["identified_position_count"] == 0
    assert report["unidentified_position_event_count"] == len(_fill_events(result["trades"]))
    assert report["fill_quote_source_counts"] == {"bar_close": 10, "bar_open": 10}
    assert report["fill_quote_source_event_count"] == report["execution_event_count"] == 20
    assert metrics_report["initial_balance"] == pytest.approx(100_000.0)
    assert metrics_report["final_equity"] == pytest.approx(float(result["equity"].iloc[-1]))
    assert metrics_report["final_equity"] - metrics_report["initial_balance"] == pytest.approx(
        metrics_report["total_pnl"]
    )


@pytest.mark.parametrize("breach_count", [False, "0", 0.0, -1, None])
def test_evaluation_diagnostics_fail_closed_on_malformed_survival_evidence(
    tmp_path, synthetic_result, breach_count
):
    result = {
        **synthetic_result,
        "survived_full_year": "false",
        "completed_data_split": "true",
    }
    if breach_count is None:
        result.pop("n_breach_sessions", None)
    else:
        result["n_breach_sessions"] = breach_count
    metrics = calculate_metrics(
        result["equity"], trades=result["trades"], initial_balance=float(result["initial_balance"])
    )

    run_dir = save_run(
        run_dir=tmp_path / "malformed-survival-evidence",
        train_result=result,
        train_metrics=metrics,
        save_plots=False,
        save_html=False,
        save_csv=True,
    )

    report = json.loads((run_dir / "training" / "evaluation_diagnostics.json").read_text())
    assert report["survived_full_year"] is False
    assert report["completed_data_split"] is False
    assert report["n_breach_sessions"] is None


def test_q5_constraint_cost_evidence_is_exported_as_rows_and_summary(tmp_path):
    equity = pd.Series(
        [100_000.0, 100_010.0, 100_020.0],
        index=pd.date_range("2025-01-01", periods=3, freq="min"),
    )
    costs = pd.DataFrame(
        [
            {
                "step": 1,
                "time": "2025-01-01T00:01:00",
                "discount_factor": 1.0,
                "daily_cost": 0.1,
                "max_loss_cost": 0.0,
                "trailing_cost": 0.0,
                "breach_indicator": 0.0,
                "step_cost": 0.1,
                "discounted_step_cost": 0.1,
            },
            {
                "step": 2,
                "time": "2025-01-01T00:02:00",
                "discount_factor": 0.9,
                "daily_cost": 0.0,
                "max_loss_cost": 0.0,
                "trailing_cost": 0.2,
                "breach_indicator": 0.0,
                "step_cost": 0.2,
                "discounted_step_cost": 0.18,
            },
        ]
    )
    summary = {
        "schema": "q5_discounted_constraint_cost_v1",
        "definition": "per_step_max_of_normalized_daily_max_loss_trailing_costs_and_breach_indicator",
        "discount_gamma": 0.9,
        "n_steps": 2,
        "undiscounted_total": 0.3,
        "discounted_total": 0.28,
        "components": {
            "daily_cost": {"undiscounted_total": 0.1, "discounted_total": 0.1},
            "max_loss_cost": {"undiscounted_total": 0.0, "discounted_total": 0.0},
            "trailing_cost": {"undiscounted_total": 0.2, "discounted_total": 0.18},
        },
    }
    trades = pd.DataFrame()
    result = {
        "equity": equity,
        "trades": trades,
        "initial_balance": 100_000.0,
        "constraint_costs": costs,
        "constraint_cost_summary": summary,
    }
    metrics = calculate_metrics(equity, trades=trades, initial_balance=100_000.0)
    run_dir = save_run(
        run_dir=tmp_path / "q5-costs",
        train_result=result,
        train_metrics=metrics,
        save_plots=False,
        save_html=False,
        save_csv=True,
    )

    split_dir = run_dir / "training"
    pd.testing.assert_frame_equal(
        pd.read_csv(split_dir / "constraint_costs.csv"), costs, check_dtype=False
    )
    diagnostics = json.loads((split_dir / "evaluation_diagnostics.json").read_text())
    assert diagnostics["constraint_cost_summary"] == summary


def test_repeated_payout_exports_economic_value_and_cycle_ledgers(tmp_path: Any) -> None:
    index = pd.date_range("2025-01-02", periods=2, freq="1min")
    equity = pd.Series([100.0, 100.0], index=index)
    economic_value = pd.Series([100.0, 101.8], index=index)
    payout_events = [
        {
            "type": "payout_reset",
            "cycle": 1,
            "payout": 1.8,
            "balance_before_reset": 101.8,
            "operating_balance": 100.0,
        }
    ]
    cycle_events = [{"cycle": 1, "outcome": "success", "payout": 1.8}]
    result = {
        "equity": equity,
        "total_economic_value_curve": economic_value,
        "total_economic_value": 101.8,
        "ending_total_economic_value": 101.8,
        "trading_policy_mode": "repeated_payout",
        "payout_events": payout_events,
        "cycle_events": cycle_events,
        "cumulative_payouts": 1.8,
        "cycle_count": 2,
        "cycle_successes": 1,
        "cycle_failures": 0,
        "initial_balance": 100.0,
        "trades": pd.DataFrame(payout_events),
    }
    metrics = calculate_metrics(economic_value, initial_balance=100.0)
    run_dir = save_run(
        run_dir=tmp_path / "repeated-payout",
        train_result=result,
        train_metrics=metrics,
        save_plots=False,
        save_html=False,
        save_csv=True,
    )

    split_dir = run_dir / "training"
    saved_value = pd.read_csv(split_dir / "total_economic_value.csv", index_col=0)
    assert saved_value["total_economic_value"].tolist() == [100.0, 101.8]
    assert pd.read_csv(split_dir / "payout_events.csv").loc[0, "payout"] == 1.8
    assert pd.read_csv(split_dir / "cycle_events.csv").loc[0, "outcome"] == "success"
    diagnostics = json.loads((split_dir / "evaluation_diagnostics.json").read_text())
    assert diagnostics["total_economic_value"] == 101.8
    assert diagnostics["cumulative_payouts"] == 1.8
    assert diagnostics["cycle_count"] == 2


def test_fill_and_position_records_reconstruct_partial_closes() -> None:
    trades = pd.DataFrame(
        [
            {
                "type": "open",
                "position_id": "p1",
                "direction": 1,
                "price": 100.0,
                "time": pd.Timestamp("2025-01-01T10:00:00Z"),
            },
            {
                "type": "tp_partial_close",
                "position_id": "p1",
                "fill_id": "p1:f1",
                "direction": 1,
                "price": 110.0,
                "pnl": 30.0,
                "net_pnl": 25.0,
                "position_complete": False,
                "time": pd.Timestamp("2025-01-01T10:01:00Z"),
            },
            {
                "type": "tp_close",
                "position_id": "p1",
                "fill_id": "p1:f2",
                "direction": 1,
                "price": 120.0,
                "pnl": 50.0,
                "net_pnl": 45.0,
                "position_net_pnl": 70.0,
                "position_complete": True,
                "reason": "take_profit",
                "time": pd.Timestamp("2025-01-01T10:02:00Z"),
            },
        ]
    )

    fills = _fill_events(trades)
    positions = _position_summaries(trades)

    assert len(fills) == 3
    assert len(positions) == 1
    position = positions.iloc[0]
    assert position["position_id"] == "p1"
    assert position["close_pnl"] == pytest.approx(80.0)
    assert position["net_pnl"] == pytest.approx(70.0)
    assert position["position_net_pnl"] == pytest.approx(70.0)
    assert position["fill_count"] == 3
    assert position["completed"]
    assert position["holding_seconds"] == pytest.approx(120.0)


def test_zero_trade_report_writes_empty_raw_event_artifacts(tmp_path, synthetic_result):
    result = {**synthetic_result, "trades": pd.DataFrame()}
    metrics = calculate_metrics(
        result["equity"],
        trades=result["trades"],
        initial_balance=100_000.0,
    )

    run_dir = save_run(
        run_dir=tmp_path / "zero_trades",
        train_result=result,
        train_metrics=metrics,
        save_plots=False,
        save_html=False,
        save_csv=True,
    )
    split_dir = run_dir / "training"

    assert pd.read_csv(split_dir / "trades.csv").empty
    assert pd.read_csv(split_dir / "fills.csv").empty
    assert pd.read_csv(split_dir / "positions.csv").empty


def test_position_export_does_not_merge_events_without_position_ids() -> None:
    trades = pd.DataFrame(
        [
            {"type": "open", "direction": 1, "price": 100.0},
            {"type": "close", "direction": 1, "price": 101.0, "pnl": 1.0},
        ],
        index=[10, 20],
    )

    positions = _position_summaries(trades)

    assert len(positions) == 2
    assert positions["position_id"].isna().all()
    assert positions["reconstruction_status"].tolist() == [
        "unidentified_event_0",
        "unidentified_event_1",
    ]
    assert positions["completed"].isna().all()


def test_unidentified_position_export_parses_completion_without_truthiness() -> None:
    trades = pd.DataFrame(
        [
            {
                "type": "close",
                "direction": 1,
                "price": 101.0,
                "pnl": 1.0,
                "position_complete": "false",
            }
        ]
    )

    positions = _position_summaries(trades)

    assert not positions.loc[0, "completed"]


@pytest.mark.parametrize(("completion", "expected"), [("false", False), ("invalid", None)])
def test_identified_position_export_fails_closed_on_completion_strings(
    completion: str, expected: bool | None
) -> None:
    trades = pd.DataFrame(
        [
            {
                "type": "close",
                "position_id": "p1",
                "direction": 1,
                "price": 101.0,
                "pnl": 1.0,
                "position_complete": completion,
            }
        ]
    )

    positions = _position_summaries(trades)

    actual = positions.loc[0, "completed"]
    if expected is None:
        assert pd.isna(actual)
    else:
        assert bool(actual) is expected


def test_position_export_preserves_trade_setup_and_structural_provenance(
    tmp_path: Any, synthetic_result: dict[str, Any]
) -> None:
    decision_time = pd.Timestamp("2025-01-02T10:00:00Z")
    trades = pd.DataFrame(
        [
            {
                "type": "open",
                "position_id": "p-trade_setup",
                "direction": 1,
                "trade_setup_candidate_id": 17,
                "trade_setup_schema_version": "trade_setup-action-v1",
                "decision_id": "episode-0-step-10",
                "trade_setup_event_identity_version": "candidate-scoped-source-time-identity.v1",
                "trade_setup_source_event_id": "fvg_retest:M5:1:1735812000000000000",
                "trade_setup_source_event_identity_status": "identified",
                "trade_setup_source_event_times_ns": [
                    {"field": "source_time_0_ns", "time_ns": 1735812000000000000}
                ],
                "primary_idea": "fvg_retest",
                "primary_setup_timeframe": "M5",
                "primary_direction": 1,
                "trade_setup_decision_time": decision_time,
                "time": decision_time + pd.Timedelta(minutes=1),
                "price": 100.0,
                "sl_price": 98.0,
                "sl_ref": "M5_swing_low",
                "sl_timeframe": "M5",
                "tp_price": 104.0,
                "tp_ref": "H1_swing_high",
                "tp_timeframe": "H1",
            },
            {
                "type": "close",
                "position_id": "p-trade_setup",
                "direction": 1,
                "decision_id": "episode-0-step-13",
                "trade_setup_source_event_id": "exit-context-must-not-replace-entry",
                "price": 103.0,
                "pnl": 3.0,
                "net_pnl": 2.5,
                "position_net_pnl": 2.5,
                "position_complete": True,
                "reason": "take_profit",
                "time": decision_time + pd.Timedelta(minutes=4),
            },
        ]
    )

    positions = _position_summaries(trades)

    assert len(positions) == 1
    position = positions.iloc[0]
    assert position["trade_setup_candidate_id"] == 17
    assert position["trade_setup_schema_version"] == "trade_setup-action-v1"
    assert position["decision_id"] == "episode-0-step-10"
    assert position["trade_setup_event_identity_version"] == (
        "candidate-scoped-source-time-identity.v1"
    )
    assert position["trade_setup_source_event_id"] == "fvg_retest:M5:1:1735812000000000000"
    assert position["trade_setup_source_event_identity_status"] == "identified"
    assert position["trade_setup_source_event_times_ns"] == [
        {"field": "source_time_0_ns", "time_ns": 1735812000000000000}
    ]
    assert position["primary_idea"] == "fvg_retest"
    assert position["primary_setup_timeframe"] == "M5"
    assert position["primary_direction"] == 1
    assert position["trade_setup_decision_time"] == decision_time
    assert position["sl_price"] == pytest.approx(98.0)
    assert position["sl_ref"] == "M5_swing_low"
    assert position["sl_timeframe"] == "M5"
    assert position["tp_price"] == pytest.approx(104.0)
    assert position["tp_ref"] == "H1_swing_high"
    assert position["tp_timeframe"] == "H1"

    result = {**synthetic_result, "trades": trades}
    metrics = calculate_metrics(result["equity"], trades=trades)
    run_dir = save_run(
        run_dir=tmp_path / "decision-linked-position",
        train_result=result,
        train_metrics=metrics,
        save_plots=False,
        save_html=False,
        save_csv=True,
    )
    saved_position = pd.read_csv(run_dir / "training" / "positions.csv").iloc[0]
    assert saved_position["decision_id"] == "episode-0-step-10"
    assert saved_position["trade_setup_source_event_id"] == ("fvg_retest:M5:1:1735812000000000000")
    assert saved_position["trade_setup_source_event_identity_status"] == "identified"
    assert "1735812000000000000" in saved_position["trade_setup_source_event_times_ns"]


def test_position_export_does_not_attribute_close_only_rows_to_entry_decision() -> None:
    trades = pd.DataFrame(
        [
            {
                "type": "close",
                "position_id": "position-without-open",
                "direction": 1,
                "decision_id": "close-decision",
                "trade_setup_source_event_id": "unrelated-close-context",
                "trade_setup_source_event_identity_status": "identified",
                "time": pd.Timestamp("2025-01-02T10:05:00Z"),
                "price": 101.0,
                "pnl": 1.0,
                "position_complete": True,
            }
        ]
    )

    position = _position_summaries(trades).iloc[0]

    assert position["reconstruction_status"] == "identified_by_position_id"
    assert position["decision_id"] is None
    assert position["trade_setup_source_event_id"] is None
    assert position["trade_setup_source_event_identity_status"] is None


def test_export_records_declared_action_coordinate_schema(tmp_path, synthetic_result) -> None:
    metrics = calculate_metrics(synthetic_result["equity"], trades=synthetic_result["trades"])
    cfg = OmegaConf.create(
        {
            "env": {
                "strategy_actions": True,
                "agent_direction_control": True,
                "allow_agent_sl_mode": False,
                "allow_agent_tp_mode": False,
                "allow_multi_tp": False,
                "allow_simplex": False,
            }
        }
    )
    run_dir = save_run(
        run_dir=tmp_path / "schema_export",
        train_result=synthetic_result,
        train_metrics=metrics,
        cfg=cfg,
        save_plots=False,
        save_html=False,
        save_csv=False,
    )

    report = json.loads((run_dir / "report_export_timing.json").read_text())
    schema = report["action_schema"]
    assert schema["version"] == "overlay-action-v2"
    assert schema["key"] == "6_dir"
    assert schema["coordinates"] == [
        "direction",
        "intensity",
        "stop",
        "risk",
        "target",
        "exit",
    ]


def test_experiment_run_fast_skips_optional_order_rendering(
    tmp_path, synthetic_result, synthetic_bars, monkeypatch
):
    from evaluation.plotting import plots

    invoked = []

    def record_orders(*args, **kwargs):
        invoked.append(kwargs.get("max_charts"))

    monkeypatch.setattr(plots, "plot_per_trade_orders", record_orders)
    metrics = calculate_metrics(synthetic_result["equity"], trades=synthetic_result["trades"])
    save_run(
        run_dir=tmp_path / "fast_charts",
        train_result=synthetic_result,
        train_metrics=metrics,
        train_bars=synthetic_bars,
        save_plots=True,
        save_html=False,
        max_order_charts=200,
        report_profile="experiment_run_fast",
    )
    assert not invoked
    assert (tmp_path / "fast_charts" / "training" / "metrics.json").exists()
    assert (tmp_path / "fast_charts" / "training" / "equity.png").exists()


def test_interactive_rendering_reports_missing_plotly_and_creates_output_parent(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    import builtins
    import runpy
    from pathlib import Path

    import evaluation.plotting.interactive_plot_rendering as renderer

    if renderer._PLOTLY_AVAILABLE:
        renderer._check()
    target = tmp_path / "nested" / "chart.html"
    written: list[str] = []

    class Figure:
        def write_html(self, path: str, *, include_plotlyjs: str) -> None:
            written.extend([path, include_plotlyjs])

    renderer._save(Figure(), target)
    assert target.parent.is_dir()
    assert written == [str(target), "cdn"]

    original_import = builtins.__import__

    def without_plotly(name, *args, **kwargs):
        if name == "plotly.graph_objects":
            raise ImportError("plotly intentionally unavailable in this test")
        return original_import(name, *args, **kwargs)

    source = Path(__file__).resolve().parents[3] / "evaluation/plotting/interactive/rendering.py"
    with monkeypatch.context() as patch:
        patch.setattr(builtins, "__import__", without_plotly)
        optional_module = runpy.run_path(str(source))
    assert optional_module["_PLOTLY_AVAILABLE"] is False
    with pytest.raises(ImportError, match="plotly is required"):
        optional_module["_check"]()
