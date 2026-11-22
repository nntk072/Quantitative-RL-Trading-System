from __future__ import annotations

import pandas as pd

from simulation.backtest.event_driven_backtest import _decision_valuation_time


def test_close_valuation_uses_close_tick_not_position_entry_fill_time() -> None:
    entry_fill = pd.Timestamp("2025-11-28T15:22:00.024Z")
    close_fill = pd.Timestamp("2025-11-28T15:49:07.585Z")
    boundary = pd.Timestamp("2025-11-28T15:50:00Z")
    events = [
        {
            "type": "stop_close",
            "bar": 89,
            "fill_time": entry_fill,
            "actual_tick_time": close_fill,
            "time": close_fill,
        }
    ]

    valuation_time = _decision_valuation_time(boundary, events, 89)

    assert pd.Timestamp(valuation_time) == close_fill
