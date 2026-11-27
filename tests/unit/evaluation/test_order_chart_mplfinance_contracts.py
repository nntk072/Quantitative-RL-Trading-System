"""Mplfinance rendering contracts for candlestick aggregation and markers."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

from evaluation.plotting import orders


def test_candlestick_renderer_aggregates_bars_and_buckets_visible_order_events(
    tmp_path: Path, monkeypatch: Any
) -> None:
    index = pd.DatetimeIndex(
        ["2025-02-03T15:00:00Z", "2025-02-03T15:10:00Z", "2025-02-03T15:11:00Z"]
    )
    bars = pd.DataFrame(
        {
            "open": [100.0, 102.0, 102.5],
            "high": [101.0, 103.0, 104.0],
            "low": [99.0, 101.0, 102.0],
            "close": [100.5, 102.5, 103.5],
            "volume": [2.0, 3.0, 5.0],
        },
        index=index,
    )
    trades = pd.DataFrame(
        [
            {"type": "open", "direction": 1, "time": index[0]},
            # 15:05 has no candle after dropna; its marker should snap right.
            {
                "type": "open",
                "direction": -1,
                "time": index[0] + pd.Timedelta(minutes=7),
            },
            {"type": "eod_close", "time": index[0]},
            {"type": "stop_close", "time": index[1]},
            {"type": "open", "direction": 1, "time": index[0] - pd.Timedelta(minutes=1)},
            {"type": "close", "time": index[1] + pd.Timedelta(minutes=2)},
        ]
    )
    calls: dict[str, Any] = {"addplots": []}
    fake = ModuleType("mplfinance")

    def make_addplot(series: pd.Series, **kwargs: Any) -> dict[str, Any]:
        result = {"series": series.copy(), **kwargs}
        calls["addplots"].append(result)
        return result

    def capture_plot(frame: pd.DataFrame, **kwargs: Any) -> tuple[Any, list[Any]]:
        calls["frame"] = frame.copy()
        calls["plot_kwargs"] = kwargs
        figure, axis = plt.subplots()
        return figure, [axis]

    fake.make_addplot = make_addplot  # type: ignore[attr-defined]
    fake.make_marketcolors = lambda **kwargs: kwargs  # type: ignore[attr-defined]
    fake.make_mpf_style = lambda **kwargs: kwargs  # type: ignore[attr-defined]
    fake.plot = capture_plot  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "mplfinance", fake)
    output = tmp_path / "nested" / "candles.png"

    figure = orders.plot_price_with_orders(
        bars, trades, candle_tf="5min", max_points=2, out_path=output
    )

    try:
        candles = calls["frame"]
        assert candles.index.tolist() == [index[0], index[1]]
        assert candles.loc[index[0], ["open", "high", "low", "close", "volume"]].tolist() == [
            100.0,
            101.0,
            99.0,
            100.5,
            2.0,
        ]
        assert candles.loc[index[1], "volume"] == 8.0
        markers = {plot["marker"]: plot["series"] for plot in calls["addplots"]}
        assert set(markers) == {"^", "v", "x", "X"}
        assert markers["^"].dropna().index.tolist() == [index[0]]
        assert markers["v"].dropna().index.tolist() == [index[1]]
        assert markers["x"].dropna().index.tolist() == [index[0]]
        assert markers["X"].dropna().index.tolist() == [index[1]]
        assert calls["plot_kwargs"]["type"] == "candle"
        assert calls["plot_kwargs"]["savefig"]["fname"] == str(output)
        assert output.parent.is_dir()
    finally:
        plt.close(figure)
