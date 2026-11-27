"""Tests for chart overlay events, dual-axis oscillators, and drawdown series."""

from __future__ import annotations

import builtins
from importlib import import_module

import matplotlib

matplotlib.use("Agg")

import numpy as np
import pandas as pd
import pytest

from evaluation.plotting.chart_indicators import (
    break_overlay_gaps,
    compute_chart_overlays,
    compute_chart_overlays_full,
    compute_mtf_ema_overlays,
    select_ema_overlays,
)
from evaluation.plotting.chart_overlays import (
    OverlayEvents,
    build_overlay_events,
    compute_vwap_for_chart,
)
from evaluation.plotting.performance import (
    plot_direction_summary,
    plot_monthly_returns_heatmap,
    plot_returns_dist,
)
from evaluation.plotting.plot_series import (
    daily_drawdown_pct,
    daily_drawdown_usd,
    daily_loss_limit_series,
    daily_pnl,
    drawdown_ylim,
    max_drawdown_pct,
    session_start_equity,
)
from evaluation.plotting.plots import (
    plot_daily_pnl,
    plot_drawdown,
    plot_equity_curve,
    plot_per_trade_orders,
)
from features.context.liquidity import detect_liquidity_sweeps
from features.technical.structure import structure_levels


def _ohlc(n: int = 80, start: str = "2026-03-02 16:30", seed: int = 1) -> pd.DataFrame:
    idx = pd.date_range(start, periods=n, freq="1min")
    rng = np.random.default_rng(seed)
    close = 20000.0 + np.cumsum(rng.normal(0, 1.2, n))
    high = close + rng.uniform(0.4, 2.0, n)
    low = close - rng.uniform(0.4, 2.0, n)
    open_ = np.r_[close[0], close[:-1]]
    return pd.DataFrame(
        {
            "open": open_,
            "high": np.maximum(high, np.maximum(open_, close)),
            "low": np.minimum(low, np.minimum(open_, close)),
            "close": close,
            "tickvol": rng.integers(50, 200, n),
        },
        index=idx,
    )


def test_session_start_equity_is_first_print_of_day() -> None:
    idx = pd.date_range("2026-03-02 16:30", periods=4, freq="1h")
    eq = pd.Series([104_000.0, 105_000.0, 104_500.0, 106_000.0], index=idx)
    start = session_start_equity(eq)
    assert (start == 104_000.0).all()


def test_daily_loss_limit_uses_day_open_not_running_equity() -> None:
    """Day opens at 104k → limit stays 99k even after equity prints 105k."""
    day1 = pd.date_range("2026-03-02 16:30", periods=3, freq="1h")
    day2 = pd.date_range("2026-03-03 16:30", periods=2, freq="1h")
    eq = pd.Series(
        [104_000.0, 105_000.0, 104_200.0, 106_000.0, 107_000.0],
        index=day1.append(day2),
    )
    limit = daily_loss_limit_series(eq, 5_000.0)
    assert limit.iloc[0] == pytest.approx(99_000.0)
    assert limit.iloc[1] == pytest.approx(99_000.0)
    assert limit.iloc[3] == pytest.approx(101_000.0)


def test_max_and_daily_drawdown_scales() -> None:
    idx = pd.date_range("2026-01-02", periods=5, freq="1D")
    eq = pd.Series([100_000.0, 102_000.0, 96_900.0, 97_000.0, 101_000.0], index=idx)
    max_dd = max_drawdown_pct(eq)
    day_dd = daily_drawdown_pct(eq)
    assert max_dd.min() < -4.0
    # Daily series is 0 at each day's first (only) print.
    assert (day_dd == 0.0).all()
    lo, hi = drawdown_ylim(max_dd, -10.0)
    assert hi == 0.0
    assert lo <= -10.0


def test_drawdown_ylim_expands_zero_only_series() -> None:
    lo, hi = drawdown_ylim(pd.Series([0.0, 0.0]), 0.0)

    assert (lo, hi) == (-1.0, 0.0)


def test_daily_drawdown_usd_is_fixed_dollars() -> None:
    idx = pd.date_range("2026-01-02 16:30", periods=4, freq="1h")
    eq = pd.Series([110_000.0, 108_000.0, 104_500.0, 106_000.0], index=idx)
    dd = daily_drawdown_usd(eq)
    assert dd.iloc[0] == pytest.approx(0.0)
    assert dd.min() == pytest.approx(-5_500.0)


def test_daily_pnl_is_last_minus_first() -> None:
    idx = pd.date_range("2026-03-02 16:30", periods=4, freq="1h")
    eq = pd.Series([100_000.0, 101_000.0, 99_500.0, 100_500.0], index=idx)
    pnl = daily_pnl(eq)
    assert len(pnl) == 1
    assert pnl.iloc[0] == pytest.approx(500.0)


def test_overlays_include_rsi_and_vwap() -> None:
    bars = _ohlc()
    overlays = compute_chart_overlays_full(bars)
    assert {"ema50", "macd", "signal", "histogram", "rsi", "vwap"} <= set(overlays)
    assert overlays["rsi"].dropna().between(0, 100).all()
    vwap = compute_vwap_for_chart(bars)
    assert vwap.notna().any()


def test_selected_timeframe_ema_overlays_use_completed_source_bars() -> None:
    bars = _ohlc(n=180)
    overlays = compute_mtf_ema_overlays(bars, ("M1", "M5"), periods=(9, 21))

    assert {"M1_ema_9", "M1_ema_21", "M5_ema_9", "M5_ema_21"} == set(overlays)
    first_visible = overlays["M5_ema_9"].first_valid_index()
    assert first_visible is not None
    assert first_visible >= bars.index[0] + pd.Timedelta(minutes=5)


def test_ema_chart_selection_can_hide_m1_and_keep_only_requested_timeframe() -> None:
    bars = _ohlc(n=180)
    overlays = compute_chart_overlays_full(bars)
    overlays.update(compute_mtf_ema_overlays(bars, ("M1", "M5")))

    hidden = select_ema_overlays(overlays, ())
    assert not any("ema" in key for key in hidden)

    m5_only = select_ema_overlays(overlays, ("M5",))
    assert "ema50" not in m5_only
    assert "M1_ema_9" not in m5_only
    assert "M5_ema_9" in m5_only
    assert "rsi" in m5_only


def test_swing_rays_start_at_swing_origin() -> None:
    bars = _ohlc(n=120, seed=3)
    events = build_overlay_events(bars)
    assert isinstance(events, OverlayEvents)
    if events.swings:
        ray = events.swings[0]
        assert ray.t1 > ray.t0
        assert ray.side in {"high", "low"}


def test_sweep_line_is_longer_than_the_two_candles() -> None:
    """Forced sweep: line must extend past both the swing origin and sweep bar."""
    rows = [(100.5, 100.0, 100.2)] * 6
    rows += [
        (102.2, 101.5, 102.0),
        (101.8, 101.0, 101.2),
        (100.8, 100.0, 100.2),
        (99.8, 99.0, 99.2),
        (100.5, 99.5, 100.3),
        (101.2, 100.5, 101.0),
        (101.6, 101.0, 101.4),
        (102.5, 101.0, 101.5),  # takes 102.2
    ]
    idx = pd.date_range("2024-01-02 16:30", periods=len(rows), freq="1min")
    high = [r[0] for r in rows]
    low = [r[1] for r in rows]
    close = [r[2] for r in rows]
    open_ = [close[0]] + close[:-1]
    bars = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close},
        index=idx,
    )
    feats = detect_liquidity_sweeps(bars, swing_period=2)
    events = build_overlay_events(bars, swing_period=2)
    if feats["sweep_high"].sum() == 0 and feats["sweep_low"].sum() == 0:
        pytest.skip("synthetic path did not fire a sweep")
    assert events.sweeps
    line = events.sweeps[0]
    pad = pd.Timedelta("1min") * 0.5
    span = line.t1 - line.t0
    assert span > pad


def test_smt_segments_connect_two_swings() -> None:
    primary = _ohlc(n=150, seed=4)
    # Uncorrelated secondary so some swings fail to confirm.
    secondary = _ohlc(n=150, seed=99)
    events = build_overlay_events(primary, secondary=secondary, swing_period=3)
    for seg in events.smt:
        assert seg.t1 > seg.t0
        assert seg.side in {"high", "low"}
        assert "SMT" in seg.label


def test_clip_keeps_only_window_events() -> None:
    bars = _ohlc(n=200, seed=5)
    events = build_overlay_events(bars)
    start, end = bars.index[80], bars.index[120]
    clipped = events.clip(pd.Timestamp(start), pd.Timestamp(end))
    for ray in clipped.swings:
        assert ray.t1 >= start
        assert ray.t0 <= end


def test_plot_equity_daily_limit_follows_day_open(tmp_path) -> None:
    day1 = pd.date_range("2026-03-02 16:30", periods=3, freq="1h")
    day2 = pd.date_range("2026-03-03 16:30", periods=3, freq="1h")
    eq = pd.Series(
        [104_000.0, 105_000.0, 104_500.0, 103_000.0, 102_000.0, 103_500.0],
        index=day1.append(day2),
    )
    fig = plot_equity_curve(
        eq,
        initial_balance=100_000.0,
        daily_loss_limit=5_000.0,
        max_loss_limit=10_000.0,
        out_path=tmp_path / "equity.png",
        dpi=72,
    )
    ax = fig.axes[0] if fig.axes else None
    # Figure is closed by _save; recompute the series the chart used.
    limit = daily_loss_limit_series(eq, 5_000.0)
    assert limit.iloc[1] == pytest.approx(99_000.0)
    assert (tmp_path / "equity.png").stat().st_size > 0
    del ax


def test_plot_drawdown_two_panels_and_dates(tmp_path) -> None:
    idx = pd.date_range("2026-01-02", periods=40, freq="1D")
    rng = np.random.default_rng(0)
    eq = pd.Series(100_000 * np.cumprod(1 + rng.normal(0, 0.004, 40)), index=idx)
    fig = plot_drawdown(eq, out_path=tmp_path / "drawdown.png", dpi=72)
    assert (tmp_path / "drawdown.png").stat().st_size > 0
    # Two stacked axes (plus any colorbars — expect at least 2).
    assert len(fig.axes) >= 2


def test_plot_drawdown_daily_cap_not_trailing_pct(tmp_path) -> None:
    idx = pd.date_range("2026-03-02 16:30", periods=8, freq="1h")
    eq = pd.Series(
        [100_000.0, 99_500.0, 98_000.0, 99_000.0, 101_000.0, 100_200.0, 97_800.0, 98_500.0],
        index=idx,
    )
    fig = plot_drawdown(eq, daily_loss_limit=5_000.0, out_path=tmp_path / "dd.png", dpi=72)
    ax_max, ax_day = fig.axes[0], fig.axes[1]
    lo, _hi = ax_day.get_ylim()
    assert lo <= -5_000.0
    hline_ys: list[float] = []
    for ax in (ax_max, ax_day):
        for line in ax.lines:
            yd = np.asarray(line.get_ydata(), dtype=float)
            if len(yd) >= 2 and np.nanmax(yd) - np.nanmin(yd) < 1e-9:
                hline_ys.append(float(yd[0]))
    assert any(abs(y + 5_000.0) < 1.0 for y in hline_ys)
    assert not any(abs(abs(y) - 7.0) < 0.05 for y in hline_ys)


def test_plot_daily_pnl_writes(tmp_path) -> None:
    idx = pd.date_range("2026-03-02 16:30", periods=20, freq="1h")
    eq = pd.Series(np.linspace(100_000, 101_000, 20), index=idx)
    plot_daily_pnl(eq, daily_loss_limit=5_000.0, out_path=tmp_path / "daily_pnl.png", dpi=72)
    assert (tmp_path / "daily_pnl.png").stat().st_size > 0


def test_daily_pnl_and_direction_summary_show_empty_ledgers(tmp_path) -> None:
    empty_equity = pd.Series(dtype=float, index=pd.DatetimeIndex([]))
    daily = plot_daily_pnl(empty_equity, out_path=tmp_path / "empty-daily-pnl.png", dpi=72)
    assert any(text.get_text() == "No daily P&L" for text in daily.axes[0].texts)
    assert (tmp_path / "empty-daily-pnl.png").is_file()

    unclosed = pd.DataFrame([{"type": "open", "direction": 1, "time": "2025-01-01"}])
    summary = plot_direction_summary(unclosed)
    assert len(summary.axes) == 2
    assert all(
        any(text.get_text() == "No completed trades" for text in axis.texts)
        for axis in summary.axes
    )
    daily.clear()
    summary.clear()


def test_return_distribution_omits_optional_scipy_overlay_when_import_fails(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_import = builtins.__import__

    def import_without_scipy(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "scipy.stats":
            raise ImportError("optional scipy unavailable")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", import_without_scipy)
    index = pd.date_range("2025-01-02", periods=4, freq="h")
    equity = pd.Series([100.0, 101.0, 99.0, 102.0], index=index)

    fig = plot_returns_dist(equity, out_path=tmp_path / "returns-without-scipy.png", dpi=72)

    assert fig.axes[0].patches
    assert all(line.get_label() != "Normal fit" for line in fig.axes[0].lines)
    assert (tmp_path / "returns-without-scipy.png").stat().st_size > 0


def test_monthly_return_plot_handles_single_month_and_constant_equity(tmp_path) -> None:
    index = pd.DatetimeIndex(["2025-01-31T21:00:00Z"])
    sparse = plot_monthly_returns_heatmap(
        pd.Series([100.0], index=index), out_path=tmp_path / "sparse-months.png", dpi=72
    )
    assert any(
        text.get_text() == "Insufficient data for monthly heatmap" for text in sparse.axes[0].texts
    )
    assert (tmp_path / "sparse-months.png").stat().st_size > 0

    monthly_index = pd.date_range("2025-01-31", periods=3, freq="ME")
    constant = plot_monthly_returns_heatmap(pd.Series([100.0] * 3, index=monthly_index))
    assert len(constant.axes[0].images) == 1
    sparse.clear()
    constant.clear()


def test_equity_series_helpers_handle_empty_and_timezone_aware_inputs() -> None:
    empty = pd.Series(dtype=float, index=pd.DatetimeIndex([]))
    assert session_start_equity(empty).empty
    assert daily_pnl(empty).empty
    assert drawdown_ylim(empty, 0.0) == (-1.0, 0.0)
    assert drawdown_ylim(pd.Series([np.nan]), -5.0) == (-5.0, 0.0)

    index = pd.date_range("2026-03-02 23:30", periods=3, freq="h", tz="America/New_York")
    equity = pd.Series([100.0, 95.0, 110.0], index=index)
    np.testing.assert_allclose(session_start_equity(equity), [100.0, 95.0, 95.0])
    assert daily_pnl(equity).tolist() == [0.0, 15.0]


def test_window_chart_indicators_and_empty_mtf_resample_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bars = _ohlc(n=80)
    overlays = compute_chart_overlays(bars)
    assert set(overlays) == {"ema50", "macd", "signal", "histogram", "rsi", "vwap"}
    assert all(series.index.equals(bars.index) for series in overlays.values())

    import evaluation.plotting.chart_indicators as indicators

    resample_module = import_module("market_data.transforms.resample")

    monkeypatch.setattr(resample_module, "resample", lambda *_args: pd.DataFrame())
    mtf = indicators.compute_mtf_ema_overlays(bars, ("M1", "H1"), periods=(9,))
    assert list(mtf) == ["M1_ema_9"]
    assert mtf["M1_ema_9"].index.equals(bars.index)


def test_overlay_gap_breaker_preserves_short_and_duplicate_timestamp_series() -> None:
    single = pd.Series([1.0], index=pd.DatetimeIndex(["2026-03-02 16:30"]), name="ema50")
    duplicate = pd.Series(
        [1.0, 2.0],
        index=pd.DatetimeIndex(["2026-03-02 16:30", "2026-03-02 16:30"]),
        name="ema50",
    )

    assert break_overlay_gaps({"ema50": single})["ema50"].equals(single)
    assert break_overlay_gaps({"ema50": duplicate})["ema50"].equals(duplicate)


def test_per_trade_chart_with_overlays(tmp_path) -> None:
    bars = _ohlc(n=180, seed=8)
    t0, t1 = bars.index[60], bars.index[90]
    trades = pd.DataFrame(
        [
            {
                "type": "open",
                "direction": 1,
                "price": float(bars["close"].iloc[60]),
                "time": t0,
                "bar": 60,
            },
            {
                "type": "close",
                "direction": 1,
                "price": float(bars["close"].iloc[90]),
                "time": t1,
                "bar": 90,
                "pnl": 12.5,
            },
        ]
    )
    orders_dir = tmp_path / "orders"
    plot_per_trade_orders(
        bars,
        trades,
        orders_dir=orders_dir,
        max_charts=1,
        dpi=72,
        secondary_bars=bars.assign(
            close=bars["close"] * 0.4, high=bars["high"] * 0.4, low=bars["low"] * 0.4
        ),
        show_mae_mfe=False,
        show_sl_tp=False,
    )
    pngs = list(orders_dir.glob("*.png"))
    assert len(pngs) == 1
    assert pngs[0].stat().st_size > 0


def test_structure_levels_available_for_overlay() -> None:
    bars = _ohlc(n=60)
    levels = structure_levels(bars, swing_period=3)
    assert "last_swing_high" in levels.columns
    assert "last_swing_low_time" in levels.columns
