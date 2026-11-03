"""Live crossover robot guardrail boundary tests."""

from __future__ import annotations

import sys
from types import ModuleType
from typing import Any, cast
from unittest.mock import MagicMock

import pytest

if "MetaTrader5" not in sys.modules:
    try:  # pragma: no cover - depends on platform
        import MetaTrader5  # noqa: F401
    except ImportError:
        sys.modules["MetaTrader5"] = ModuleType("MetaTrader5")
if not hasattr(sys.modules["MetaTrader5"], "ORDER_TYPE_BUY"):
    sys.modules["MetaTrader5"] = MagicMock()

from integrations.mt5.robot.cross_over_robot import CrossOverRobot


def test_crossover_robot_rejects_nonpaper_mode_without_account_guardrails() -> None:
    with pytest.raises(ValueError, match="training-equivalent account-loss guardrails"):
        CrossOverRobot(
            volume=0.1,
            trader=cast(Any, object()),
            strategy=cast(Any, object()),
            paper_trading=False,
        )


def test_crossover_robot_keeps_paper_mode_available() -> None:
    robot = CrossOverRobot(
        volume=0.1,
        trader=cast(Any, object()),
        strategy=cast(Any, object()),
    )

    assert robot.paper_trading is True
