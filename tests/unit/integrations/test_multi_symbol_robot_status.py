"""Multi-symbol status reports exposure and handles unavailable account data."""

from __future__ import annotations

import sys
from types import ModuleType
from typing import Any, cast

import pytest

if "MetaTrader5" not in sys.modules:
    try:  # pragma: no cover - depends on platform
        import MetaTrader5  # noqa: F401
    except ImportError:
        sys.modules["MetaTrader5"] = ModuleType("MetaTrader5")

mt5 = cast(Any, sys.modules["MetaTrader5"])
if not hasattr(mt5, "TIMEFRAME_H1"):
    mt5.TIMEFRAME_H1 = 16385

from integrations.mt5.robot.multi_symbol_robot import MultiSymbolRobot  # noqa: E402


def test_status_preserves_exposure_and_defaults_missing_account_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exposure = {
        "total_positions": 2,
        "total_volume": 0.3,
        "total_profit": 12.5,
        "symbols": {"US100": {"positions": 2, "volume": 0.3}},
    }

    class RiskManager:
        def get_total_exposure(self) -> dict[str, object]:
            return exposure

    monkeypatch.setattr(mt5, "account_info", lambda: None, raising=False)
    robot = MultiSymbolRobot(
        symbol_manager=cast(Any, object()),
        trader=cast(Any, object()),
        strategies={"US100": cast(Any, object())},
        risk_manager=cast(Any, RiskManager()),
    )

    status = robot.get_status()

    assert status == {
        "symbols": ["US100"],
        "total_positions": 2,
        "total_volume": 0.3,
        "total_profit": 12.5,
        "symbol_exposure": exposure["symbols"],
        "account_balance": 0.0,
        "account_equity": 0.0,
    }
