"""Smoke tests for PO3/IFVG signal charts.

Uses the matplotlib Agg backend so tests run headless in CI.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import numpy as np
import pandas as pd
import pytest

from evaluation.plotting.plots_interactive import plot_fvg_signals_interactive
from evaluation.plotting.po3_plots import plot_fvg_signals
from features.po3.fvg_detection import detect_fvg
from features.po3.trigger_rules import detect_po3_entries


@pytest.fixture()
def signal_bars() -> pd.DataFrame:
    """Synthetic M1 bars with forced imbalances so zones are non-empty."""
    idx = pd.date_range("2025-01-01", periods=200, freq="1min")
    close = 20000.0 + np.cumsum(np.random.default_rng(7).normal(0, 1.5, 200))
    close[20] = close[19] + 12  # create FVG
    close[25] = close[24] - 14  # create bearish move
    return pd.DataFrame(
        {
            "open": close - 1.0,
            "high": close + 2.0,
            "low": close - 2.0,
            "close": close,
        },
        index=idx,
    )


@pytest.fixture()
def po3_signals(signal_bars: pd.DataFrame) -> pd.DataFrame:
    return detect_po3_entries(signal_bars, htf="M15", primary_tf="M5")


def test_static_plot_writes_png(
    signal_bars: pd.DataFrame, po3_signals: pd.DataFrame, tmp_path
) -> None:
    out = tmp_path / "po3.png"
    fig = plot_fvg_signals(signal_bars, po3_signals, candle_tf="1min", out_path=out, dpi=80)
    assert out.exists()
    assert out.stat().st_size > 0
    assert len(fig.axes) == 1


def test_static_plot_with_window(
    signal_bars: pd.DataFrame, po3_signals: pd.DataFrame, tmp_path
) -> None:
    start = signal_bars.index[10]
    end = signal_bars.index[40]
    fig = plot_fvg_signals(
        signal_bars, po3_signals, window=(start, end), candle_tf="1min", out_path=tmp_path / "w.png"
    )
    # Window plotted: 31 bars -> candlestick patches fit within that range.
    assert len(fig.axes) == 1


def test_static_plot_no_entries(signal_bars: pd.DataFrame, po3_signals: pd.DataFrame) -> None:
    fig = plot_fvg_signals(signal_bars, po3_signals, candle_tf="5min", show_entries=False)
    assert len(fig.axes) == 1


def test_static_plot_empty_data_raises() -> None:
    bars = pd.DataFrame(columns=["open", "high", "low", "close"])
    with pytest.raises(ValueError):
        plot_fvg_signals(bars, pd.DataFrame(), candle_tf="1min")


def test_interactive_plot_writes_html(
    signal_bars: pd.DataFrame, po3_signals: pd.DataFrame, tmp_path
) -> None:
    out = tmp_path / "po3.html"
    fig = plot_fvg_signals_interactive(signal_bars, po3_signals, candle_tf="1min", out_path=out)
    assert out.exists()
    assert out.stat().st_size > 0
    assert len(fig.data) >= 1


def test_interactive_plot_has_zone_shapes(
    signal_bars: pd.DataFrame, po3_signals: pd.DataFrame
) -> None:
    fig = plot_fvg_signals_interactive(signal_bars, po3_signals, candle_tf="1min")
    assert len(fig.layout.shapes) > 0


def test_interactive_plot_window(signal_bars: pd.DataFrame, po3_signals: pd.DataFrame) -> None:
    start = signal_bars.index[0]
    end = signal_bars.index[50]
    fig = plot_fvg_signals_interactive(
        signal_bars, po3_signals, window=(start, end), candle_tf="1min"
    )
    assert len(fig.data) >= 1


def test_static_plot_with_plain_fvg(signal_bars: pd.DataFrame, tmp_path) -> None:
    """Works with just FVG signal columns (no HTF/IFVG columns)."""
    fvg = detect_fvg(signal_bars)
    fig = plot_fvg_signals(signal_bars, fvg, candle_tf="5min", out_path=tmp_path / "fvg.png")
    assert len(fig.axes) == 1


def test_candle_body_width_matches_bar_spacing(signal_bars: pd.DataFrame) -> None:
    """Candle bodies must be on the order of bar spacing, not ~0.7 date-days."""
    from matplotlib.patches import Rectangle

    from evaluation.plotting.po3_plots import _draw_candles, _resample_ohlc

    ohlcv = _resample_ohlc(signal_bars, "1min")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots()
    _draw_candles(ax, ohlcv)
    widths = [p.get_width() for p in ax.patches if isinstance(p, Rectangle)]
    plt.close(fig)
    assert widths, "expected at least one candle body patch"
    # 1-minute bars are ~1/1440 days; body width should be ≪ 0.1 days.
    assert max(widths) < 0.1
    assert max(widths) < 0.01  # ~0.0004 for 1-min spacing * 0.6


def test_entry_markers_at_candle_close(signal_bars: pd.DataFrame) -> None:
    """Long/short markers sit on the candle close, not wick ± pad or price×1.004."""
    import matplotlib.pyplot as plt

    from evaluation.plotting.po3_plots import _draw_entries, _resample_ohlc

    ohlcv = _resample_ohlc(signal_bars, "1min")
    signals = pd.DataFrame(0, index=signal_bars.index, columns=["entry_long", "entry_short"])
    hit_ts = signal_bars.index[50]
    signals.loc[hit_ts, "entry_long"] = 1
    fig, ax = plt.subplots()
    _draw_entries(ax, signals, ohlcv)
    collections = ax.collections
    plt.close(fig)
    assert collections, "expected entry scatter"
    offsets = np.asarray(collections[0].get_offsets(), dtype=float)
    ys = offsets[:, 1]
    loc = int(ohlcv.index.searchsorted(hit_ts, side="left"))
    assert float(ys[0]) == pytest.approx(float(ohlcv["close"].iloc[loc]))
    # Old bug: high * 1.004 is far from close at ~20k.
    assert abs(float(ys[0]) - float(ohlcv["high"].iloc[loc]) * 1.004) > 1.0


def test_plot_window_keeps_lookback_for_zones(signal_bars: pd.DataFrame, tmp_path) -> None:
    """Display window may be short; zone builder still sees full ``bars`` spine."""
    start = signal_bars.index[100]
    end = signal_bars.index[150]
    signals = detect_po3_entries(signal_bars, htf="M15", primary_tf="M5")
    fig = plot_fvg_signals(
        signal_bars,
        signals,
        window=(start, end),
        candle_tf="1min",
        out_path=tmp_path / "win.png",
        dpi=80,
    )
    assert len(fig.axes) == 1


def test_interactive_plot_rejects_empty_bars_and_empty_selected_window() -> None:
    pytest.importorskip("plotly")
    empty_bars = pd.DataFrame(
        columns=["open", "high", "low", "close"],
        index=pd.DatetimeIndex([], name="time"),
    )
    with pytest.raises(ValueError, match="No bars to plot after applying window"):
        plot_fvg_signals_interactive(empty_bars, pd.DataFrame(index=empty_bars.index))

    bars = pd.DataFrame(
        {"open": [10.0, 11.0], "high": [11.0, 12.0], "low": [9.0, 10.0], "close": [10.5, 11.5]},
        index=pd.date_range("2025-01-01", periods=2, freq="min"),
    )
    with pytest.raises(ValueError, match="No bars to plot after applying window"):
        plot_fvg_signals_interactive(
            bars,
            pd.DataFrame(index=bars.index),
            window=(
                bars.index[-1] + pd.Timedelta(minutes=1),
                bars.index[-1] + pd.Timedelta(minutes=2),
            ),
        )


def test_interactive_plot_caps_candles_to_the_most_recent_points(
    signal_bars: pd.DataFrame,
) -> None:
    pytest.importorskip("plotly")
    signals = pd.DataFrame(index=signal_bars.index)

    figure = plot_fvg_signals_interactive(signal_bars, signals, candle_tf="1min", max_points=7)

    candles = figure.data[0]
    assert candles.name == "Price"
    assert list(candles.x) == list(signal_bars.index[-7:])
    assert list(candles.close) == signal_bars["close"].iloc[-7:].tolist()


def test_interactive_entry_markers_follow_visible_signal_rows_and_option(
    signal_bars: pd.DataFrame,
) -> None:
    pytest.importorskip("plotly")
    signals = pd.DataFrame(0, index=signal_bars.index, columns=["entry_long", "entry_short"])
    signals.loc[signal_bars.index[0], "entry_long"] = 1
    signals.loc[signal_bars.index[40], "entry_long"] = 1
    signals.loc[signal_bars.index[70], "entry_short"] = 1
    visible_window = (signal_bars.index[30], signal_bars.index[50])

    visible = plot_fvg_signals_interactive(
        signal_bars, signals, window=visible_window, candle_tf="1min"
    )
    without_entries = plot_fvg_signals_interactive(
        signal_bars, signals, window=visible_window, candle_tf="1min", show_entries=False
    )

    assert [trace.name for trace in visible.data] == ["Price", "entry_long"]
    assert list(visible.data[1].x) == [signal_bars.index[40]]
    assert list(visible.data[1].y) == [signal_bars.loc[signal_bars.index[40], "close"]]
    assert [trace.name for trace in without_entries.data] == ["Price"]


def test_interactive_plot_rejects_bars_that_resample_to_no_candles() -> None:
    pytest.importorskip("plotly")
    index = pd.date_range("2025-01-01", periods=2, freq="min")
    bars = pd.DataFrame(
        {
            "open": [np.nan, np.nan],
            "high": [np.nan, np.nan],
            "low": [np.nan, np.nan],
            "close": [np.nan, np.nan],
        },
        index=index,
    )

    with pytest.raises(ValueError, match="No candles to plot after resampling"):
        plot_fvg_signals_interactive(bars, pd.DataFrame(index=index), candle_tf="1min")
