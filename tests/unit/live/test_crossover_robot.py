"""Live crossover robot guardrail boundary tests."""

from __future__ import annotations

import sys
from types import ModuleType
from typing import Any, cast

import pytest

if "MetaTrader5" not in sys.modules:
    try:  # pragma: no cover - depends on platform
        import MetaTrader5  # noqa: F401
    except ImportError:
        mt5_stub = ModuleType("MetaTrader5")
        setattr(mt5_stub, "TIMEFRAME_H1", 16385)
        sys.modules["MetaTrader5"] = mt5_stub
if not hasattr(sys.modules["MetaTrader5"], "TIMEFRAME_H1"):
    setattr(sys.modules["MetaTrader5"], "TIMEFRAME_H1", 16385)
from integrations.mt5.robot.cross_over_robot import CrossOverRobot


def test_crossover_robot_rejects_nonpaper_mode_without_account_guardrails() -> None:
    with pytest.raises(ValueError, match="training-equivalent account-loss guardrails"):
        CrossOverRobot(
            volume=0.1,
            trader=cast(Any, object()),
            strategy=cast(Any, object()),
            paper_trading=False,
        )


def test_headless_mt5_stub_remains_a_module() -> None:
    assert isinstance(sys.modules["MetaTrader5"], ModuleType)
    assert getattr(sys.modules["MetaTrader5"], "TIMEFRAME_H1") == 16385


def test_crossover_robot_keeps_paper_mode_available() -> None:
    robot = CrossOverRobot(
        volume=0.1,
        trader=cast(Any, object()),
        strategy=cast(Any, object()),
    )

    assert robot.paper_trading is True
