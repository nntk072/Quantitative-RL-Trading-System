"""Per-trade plotting contracts for normalized events and incomplete overlays."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from evaluation.plotting.orders import (
    _position_events,
    _position_pnl_from_fills,
    plot_per_trade_orders,
)
from evaluation.plotting.orders import window as order_window
from evaluation.plotting.shared import indicators as chart_indicators


@pytest.mark.parametrize(
    ("overlay_keys", "show_vwap"),
    [((), False), (("macd", "signal", "histogram"), True)],
    ids=["empty", "partial"],
)
def test_trade_chart_recovers_origin_and_normalizes_fill_times_before_preparing_the_window(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    overlay_keys: tuple[str, ...],
    show_vwap: bool,
) -> None:
    bars_index = pd.date_range("2025-02-03 17:00", periods=4, freq="min", tz="Europe/Helsinki")
    bars = pd.DataFrame(
        {
            "open": [100.0, 100.1, 100.2, 100.3],
            "high": [100.2, 100.3, 100.4, 100.5],
            "low": [99.8, 99.9, 100.0, 100.1],
            "close": [100.1, 100.2, 100.3, 100.4],
        },
        index=bars_index,
    )
    open_utc = bars_index[2].tz_convert("UTC")
    close_utc = bars_index[3].tz_convert("UTC")
    trades = pd.DataFrame(
        [
            {
                "type": "open",
                "position_id": "position-1",
                "direction": 1,
                "time": open_utc.isoformat(),
                "actual_tick_time": (open_utc + pd.Timedelta(milliseconds=250)).isoformat(),
                "fill_time": (open_utc + pd.Timedelta(milliseconds=250)).isoformat(),
                "price": 100.2,
                "entry_origin_bar": 1,
            },
            {
                "type": "close",
                "position_id": "position-1",
                "direction": 1,
                "time": close_utc.isoformat(),
                "price": 100.4,
                "pnl": 0.2,
            },
        ]
    )
    observed: list[tuple[pd.Series, pd.Series]] = []

    monkeypatch.setattr(
        chart_indicators,
        "compute_chart_overlays_full",
        lambda *_args: {key: pd.Series(0.0, index=bars_index) for key in overlay_keys},
    )
    prepare_order_chart = order_window.prepare_order_chart

    def capture_open_row(
        bars: pd.DataFrame, open_row: pd.Series, close_row: pd.Series, **kwargs: Any
    ) -> order_window.PreparedOrderChart | None:
        observed.append((open_row.copy(), close_row.copy()))
        return prepare_order_chart(bars, open_row, close_row, **kwargs)

    monkeypatch.setattr(order_window, "prepare_order_chart", capture_open_row)

    plot_per_trade_orders(
        bars, trades, orders_dir=tmp_path, max_charts=1, show_vwap=show_vwap, ema_timeframes=()
    )

    assert len(list(tmp_path.glob("*.png"))) == 1
    assert len(observed) == 1
    open_row, close_row = observed[0]
    assert open_row["entry_origin_time"] == bars_index[1]
    assert open_row["time"] == bars_index[2]
    assert open_row["actual_tick_time"] == bars_index[2] + pd.Timedelta(milliseconds=250)
    assert open_row["fill_time"] == bars_index[2] + pd.Timedelta(milliseconds=250)
    assert close_row["time"] == bars_index[3]


def test_chart_pnl_fallback_uses_each_logged_partial_and_final_fill_size() -> None:
    trades = pd.DataFrame(
        [
            {
                "type": "open",
                "position_id": "position-1",
                "time": "2025-02-03T15:00:00Z",
                "price": 100.0,
            },
            {
                "type": "tp_partial_close",
                "position_id": "position-1",
                "time": "2025-02-03T15:01:00Z",
                "price": 101.0,
                "size": 0.25,
                "pnl": None,
            },
            {
                "type": "close",
                "position_id": "position-1",
                "time": "2025-02-03T15:02:00Z",
                "price": 99.5,
                "size": 0.75,
                "pnl": None,
            },
        ]
    )
    open_row = trades.iloc[0]
    close_row = trades.iloc[-1]
    events = _position_events(trades, open_row, close_row)

    pnl = _position_pnl_from_fills(events, direction=1, entry=100.0, initial_lots=1.0, contract=2.0)

    assert len(events.loc[events["type"].eq("tp_partial_close")]) == 1
    assert pnl == -0.25
