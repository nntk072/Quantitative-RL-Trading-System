"""Trade markers stay aligned with visible candles in static and interactive charts."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest
from matplotlib.figure import Figure

from evaluation.metrics.trades import TradeChartMetrics
from evaluation.plotting import orders
from evaluation.plotting.chart_overlays import OverlayEvents
from evaluation.plotting.interactive import orders as interactive_orders
from evaluation.plotting.order_chart_data import order_levels


def _bars() -> pd.DataFrame:
    index = pd.date_range("2025-02-03 15:00", periods=6, freq="5min", tz="UTC")
    close = [100.0, 100.5, 101.0, 100.75, 101.25, 101.5]
    return pd.DataFrame(
        {
            "open": close,
            "high": [value + 0.25 for value in close],
            "low": [value - 0.25 for value in close],
            "close": close,
        },
        index=index,
    )


def _trades(index: pd.DatetimeIndex) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"type": "open", "direction": 1, "time": index[2], "price": 101.125},
            {"type": "open", "direction": -1, "time": index[3], "price": 100.875},
            {"type": "close", "direction": 1, "time": index[4], "price": 101.25},
            {"type": "stop_close", "direction": -1, "time": index[5], "price": 101.5},
            {
                "type": "open",
                "direction": 1,
                "time": index[-1] + pd.Timedelta(minutes=5),
                "price": 102.0,
            },
        ]
    )


def test_interactive_order_chart_labels_fill_types_and_omits_out_of_window_rows() -> None:
    pytest.importorskip("plotly")
    bars = _bars()
    trades: pd.DataFrame = pd.concat(
        [
            pd.DataFrame(
                [
                    {
                        "type": "open",
                        "direction": 1,
                        "time": bars.index[0],
                        "price": 99.0,
                    }
                ]
            ),
            _trades(pd.DatetimeIndex(bars.index)),
        ],
        ignore_index=True,
    )
    figure = interactive_orders.plot_price_with_orders(bars, trades, candle_tf="5min", max_points=4)

    traces = {trace.name: trace for trace in figure.data}
    assert set(traces) == {
        "Price",
        "Long open",
        "Short open",
        "Close",
        "Forced/Stop close",
    }
    assert list(traces["Long open"].x) == [bars.index[2]]
    assert list(traces["Long open"].y) == [101.125]
    assert list(traces["Short open"].x) == [bars.index[3]]
    assert list(traces["Short open"].y) == [100.875]
    assert list(traces["Close"].x) == [bars.index[4]]
    assert list(traces["Close"].y) == [bars.loc[bars.index[4], "close"]]
    assert list(traces["Forced/Stop close"].x) == [bars.index[5]]


def test_interactive_trade_in_empty_resample_bin_snaps_to_next_visible_candle() -> None:
    pytest.importorskip("plotly")
    bars = _bars().iloc[[0, 2, 4]]
    trades = pd.DataFrame(
        [
            {
                "type": "open",
                "direction": 1,
                "time": bars.index[0] + pd.Timedelta(minutes=7),
                "price": 100.75,
            }
        ]
    )

    figure = interactive_orders.plot_price_with_orders(bars, trades, candle_tf="5min")

    traces = {trace.name: trace for trace in figure.data}
    assert list(traces["Long open"].x) == [bars.index[1]]
    assert list(traces["Long open"].y) == [100.75]


def test_interactive_chart_omits_directionless_open_and_uses_candle_close(
    tmp_path: Path,
) -> None:
    pytest.importorskip("plotly")
    bars = _bars()
    trades = pd.DataFrame(
        [
            {"type": "open", "time": bars.index[2], "price": 101.1},
            {"type": "close", "time": bars.index[4]},
        ]
    )
    out_path = tmp_path / "orders.html"

    figure = interactive_orders.plot_price_with_orders(
        bars, trades, candle_tf="5min", out_path=out_path
    )

    traces = {trace.name: trace for trace in figure.data}
    assert set(traces) == {"Price", "Close"}
    assert list(traces["Close"].x) == [bars.index[4]]
    assert list(traces["Close"].y) == [bars.loc[bars.index[4], "close"]]
    assert out_path.is_file()


def test_interactive_chart_without_trade_time_still_saves_price_candles(
    tmp_path: Path,
) -> None:
    pytest.importorskip("plotly")
    bars = _bars()
    out_path = tmp_path / "price-only.html"

    figure = interactive_orders.plot_price_with_orders(
        bars,
        pd.DataFrame([{"type": "open", "direction": 1}]),
        candle_tf="5min",
        out_path=out_path,
    )

    assert [trace.name for trace in figure.data] == ["Price"]
    assert out_path.is_file()


def test_interactive_chart_omits_each_marker_category_outside_visible_window() -> None:
    pytest.importorskip("plotly")
    bars = _bars()
    trades = pd.DataFrame(
        [
            {"type": "open", "direction": 1, "time": bars.index[0], "price": 99.0},
            {"type": "open", "direction": -1, "time": bars.index[0], "price": 99.0},
            {"type": "close", "time": bars.index[-1] + pd.Timedelta(minutes=5)},
            {"type": "stop_close", "time": bars.index[-1] + pd.Timedelta(minutes=5)},
        ]
    )

    figure = interactive_orders.plot_price_with_orders(bars, trades, candle_tf="5min", max_points=4)

    assert [trace.name for trace in figure.data] == ["Price"]


def test_interactive_per_trade_plot_skips_a_chart_when_html_save_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("plotly")
    bars = _bars()
    trades = pd.DataFrame(
        [
            {"type": "open", "direction": 1, "time": bars.index[1], "price": 100.5},
            {"type": "close", "direction": 1, "time": bars.index[4], "price": 101.25, "pnl": 0.75},
        ]
    )
    orders_dir = tmp_path / "orders"

    def fail_save(_figure: object, _path: Path | str) -> None:
        raise OSError("destination is unavailable")

    monkeypatch.setattr(interactive_orders, "_save", fail_save)
    interactive_orders.plot_per_trade_orders(bars, trades, orders_dir, context_bars=2)

    assert orders_dir.is_dir()
    assert list(orders_dir.iterdir()) == []


def test_interactive_per_trade_plot_creates_empty_output_for_unclosed_trade(
    tmp_path: Path,
) -> None:
    pytest.importorskip("plotly")
    bars = _bars()
    trades = pd.DataFrame([{"type": "open", "direction": 1, "time": bars.index[2], "price": 101.0}])
    orders_dir = tmp_path / "orders"

    interactive_orders.plot_per_trade_orders(bars, trades, orders_dir)

    assert orders_dir.is_dir()
    assert list(orders_dir.iterdir()) == []


def test_static_per_trade_plot_skips_failed_save_and_continues_to_next_trade(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bars = _bars()
    trades = pd.DataFrame(
        [
            {"type": "open", "direction": 1, "time": bars.index[1], "price": 100.5},
            {"type": "close", "direction": 1, "time": bars.index[2], "price": 101.0, "pnl": 1.0},
            {"type": "open", "direction": -1, "time": bars.index[3], "price": 100.75},
            {
                "type": "close",
                "direction": -1,
                "time": bars.index[4],
                "price": 101.25,
                "pnl": -0.5,
            },
        ]
    )
    orders_dir = tmp_path / "orders"
    attempts: list[str] = []

    def save_trade(figure: Figure, path: str, **_kwargs: object) -> None:
        del figure
        target = Path(path)
        attempts.append(target.name)
        if len(attempts) == 1:
            raise OSError("first destination is unavailable")
        target.write_bytes(b"rendered trade")

    monkeypatch.setattr(Figure, "savefig", save_trade)

    orders.plot_per_trade_orders(
        bars, trades, orders_dir, context_bars=1, max_charts=2, swing_timeframes=()
    )

    assert len(attempts) == 2
    assert attempts[0].startswith("trade_0001_")
    assert attempts[1].startswith("trade_0002_")
    assert sorted(path.name for path in orders_dir.iterdir()) == [attempts[1]]


def test_interactive_per_trade_plot_samples_completed_trades_and_writes_html(
    tmp_path: Path,
) -> None:
    pytest.importorskip("plotly")
    index = pd.date_range("2025-02-03 14:30", periods=90, freq="min", tz="UTC")
    close = [100.0 + position * 0.02 for position in range(len(index))]
    low = [value - 0.1 for value in close]
    low[4] = 100.0
    low[5] = 99.0
    bars = pd.DataFrame(
        {
            "open": close,
            "high": [value + 0.1 for value in close],
            "low": low,
            "close": close,
        },
        index=index,
    )
    trades = pd.DataFrame(
        [
            {
                "type": "open",
                "direction": 1,
                "time": index[5],
                "price": close[5],
                "entry_setup_types": ["sweep"],
                "entry_origin_bar": 5,
                "entry_setup_levels": {
                    "sweep_low_level": 100.0,
                    "sweep_low_pivot_bar": 4,
                },
            },
            {"type": "close", "direction": 1, "time": index[10], "price": close[10], "pnl": 1.0},
            {
                "type": "open",
                "direction": -1,
                "time": index[20],
                "price": close[20],
            },
            {
                "type": "close",
                "direction": -1,
                "time": index[25],
                "price": close[25],
                "pnl": 2.0,
            },
            {
                "type": "open",
                "direction": 1,
                "time": index[35],
                "price": close[35],
            },
            {"type": "close", "direction": 1, "time": index[40], "price": close[40], "pnl": 3.0},
        ]
    )
    orders_dir = tmp_path / "orders"

    interactive_orders.plot_per_trade_orders(
        bars, trades, orders_dir, max_charts=2, show_vwap=True, swing_timeframes=()
    )

    charts = sorted(orders_dir.glob("*.html"))
    assert [path.name for path in charts] == [
        "trade_0001_20250203_1435_1440_L_p1.0.html",
        "trade_0002_20250203_1505_1510_L_p3.0.html",
    ]
    assert "PnL: +1.00" in charts[0].read_text(encoding="utf-8")
    assert "PnL: +3.00" in charts[1].read_text(encoding="utf-8")
    assert "VWAP" in charts[0].read_text(encoding="utf-8")


def test_static_order_chart_fallback_keeps_open_fill_prices_and_exit_markers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bars = _bars()
    trades = _trades(pd.DatetimeIndex(bars.index)).iloc[:4].copy()
    trades.loc[trades["type"].eq("close") | trades["type"].eq("stop_close"), "equity"] = 100_001.0
    monkeypatch.setitem(sys.modules, "mplfinance", None)

    figure = orders.plot_price_with_orders(
        bars,
        trades,
        candle_tf="5min",
        out_path=tmp_path / "price.png",
    )
    try:
        labels = [collection.get_label() for collection in figure.axes[0].collections]
        assert labels == ["Long", "Short", "Close"]
        assert (tmp_path / "price.png").is_file()
        assert np.asarray(figure.axes[0].collections[0].get_offsets())[0, 1] == pytest.approx(
            101.125
        )
        assert np.asarray(figure.axes[0].collections[1].get_offsets())[0, 1] == pytest.approx(
            100.875
        )
    finally:
        plt.close(figure)


def test_order_levels_hide_risk_bands_when_chart_risk_overlay_is_disabled() -> None:
    bars = _bars()
    opened = bars.index[1]
    closed = bars.index[4]
    metrics = TradeChartMetrics(
        entry_price=100.5,
        exit_price=101.25,
        direction=1,
        mae_price=100.25,
        mfe_price=101.5,
        mae_time=bars.index[2],
        mfe_time=bars.index[5],
        sl_price=98.0,
        tp_price=120.0,
    )

    levels = order_levels(
        bars,
        metrics,
        OverlayEvents(),
        bars,
        opened,
        closed,
        pd.Series({"time": opened, "direction": 1}),
        show_mae_mfe=False,
        show_sl_tp=False,
    )

    assert levels.red is None
    assert levels.green is None
    assert levels.off_chart_levels == []
    assert not any(
        "Stop loss" in segment.label or "Take profit" in segment.label for segment in levels.segs
    )
    assert not any(note.startswith(("SL ", "TP ")) for note in levels.notes)
