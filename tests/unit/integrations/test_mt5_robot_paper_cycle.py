"""The crossover robot's paper cycle reads positions without submitting orders."""

from __future__ import annotations

import sys
from types import ModuleType
from typing import Any, cast

import pandas as pd

if "MetaTrader5" not in sys.modules:
    try:  # pragma: no cover - depends on platform
        import MetaTrader5  # noqa: F401
    except ImportError:
        sys.modules["MetaTrader5"] = ModuleType("MetaTrader5")

mt5 = cast(Any, sys.modules["MetaTrader5"])
for _name, _value in {
    "TIMEFRAME_H1": 16385,
    "ORDER_TYPE_BUY": 0,
    "ORDER_TYPE_SELL": 1,
}.items():
    if not hasattr(mt5, _name):
        setattr(mt5, _name, _value)

from integrations.mt5.domain.signal import Signal  # noqa: E402
from integrations.mt5.robot.cross_over_robot import CrossOverRobot  # noqa: E402


def test_paper_buy_cycle_checks_both_sides_without_submitting_orders() -> None:
    position_queries: list[tuple[str, int]] = []
    writes: list[str] = []

    class Trader:
        def get_opened_positions(self, symbol: str, position_type: int) -> tuple[int, pd.DataFrame]:
            position_queries.append((symbol, position_type))
            count = int(position_type == mt5.ORDER_TYPE_SELL)
            return count, pd.DataFrame()

        def open_position(self, *_args: object, **_kwargs: object) -> None:
            writes.append("open")

        def close_positions(self, *_args: object, **_kwargs: object) -> None:
            writes.append("close")

    class Strategy:
        def signal(self) -> tuple[str, Signal]:
            return "US100", Signal.BUY

    CrossOverRobot(volume=0.1, trader=cast(Any, Trader()), strategy=cast(Any, Strategy())).trade()

    assert position_queries == [
        ("US100", mt5.ORDER_TYPE_BUY),
        ("US100", mt5.ORDER_TYPE_SELL),
    ]
    assert writes == []
