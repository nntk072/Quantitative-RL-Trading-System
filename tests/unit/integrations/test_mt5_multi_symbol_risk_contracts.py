"""Behavior contracts for multi-symbol sizing and aggregate-risk inputs."""

from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from typing import Any, cast

import pandas as pd
import pytest

if "MetaTrader5" not in sys.modules:
    try:  # pragma: no cover - depends on platform
        import MetaTrader5  # noqa: F401
    except ImportError:
        sys.modules["MetaTrader5"] = ModuleType("MetaTrader5")

mt5 = cast(Any, sys.modules["MetaTrader5"])
for _name, _value in {"ORDER_TYPE_BUY": 0, "ORDER_TYPE_SELL": 1}.items():
    if not hasattr(mt5, _name):
        setattr(mt5, _name, _value)

from integrations.mt5 import risk_configuration  # noqa: E402
from integrations.mt5.domain.risk_manager import RiskManager  # noqa: E402
from integrations.mt5.domain.signal import Signal  # noqa: E402
from integrations.mt5.robot.multi_symbol_robot import MultiSymbolRobot  # noqa: E402


class _Trader:
    def __init__(self, counts: dict[int, int] | None = None) -> None:
        self.counts = counts or {}
        self.queries: list[int] = []
        self.writes: list[str] = []

    def get_opened_positions(
        self, _symbol: str, position_type: int, **_kwargs: Any
    ) -> tuple[int, pd.DataFrame]:
        self.queries.append(position_type)
        return self.counts.get(position_type, 0), pd.DataFrame()

    def close_positions(self, *_args: Any, **_kwargs: Any) -> None:
        self.writes.append("close")

    def open_position(self, *_args: Any, **_kwargs: Any) -> None:
        self.writes.append("open")


class _Risk:
    def __init__(self, *, multiplier: float = 1.0, size: float = 0.2) -> None:
        self.multiplier = multiplier
        self.size = size
        self.sizing: list[dict[str, Any]] = []
        self.supports_training_account_loss_guardrails = False

    def get_volatility_multiplier(self, atr_percentage: float) -> float:
        return self.multiplier

    def calculate_position_size(self, **kwargs: Any) -> float:
        self.sizing.append(kwargs)
        return self.size

    def calculate_stop_loss_price(self, *_args: Any) -> float:
        return 101.0

    def check_risk_limits(self, *_args: Any) -> tuple[bool, str]:
        return True, "allowed"


def _robot(
    *,
    signal: Signal,
    trader: _Trader | None = None,
    risk: _Risk | None = None,
    metrics: dict[str, Any] | None = None,
    strategies: dict[str, Any] | None = None,
) -> tuple[MultiSymbolRobot, _Trader, _Risk]:
    symbol = "US100"

    class Strategy:
        def signal(self) -> tuple[str, Signal]:
            return symbol, signal

    class SymbolManager:
        def get_volatility_metrics(self, _symbol: str) -> dict[str, Any] | None:
            return metrics

    selected_trader = trader or _Trader()
    selected_risk = risk or _Risk()
    robot = MultiSymbolRobot(
        symbol_manager=cast(Any, SymbolManager()),
        trader=cast(Any, selected_trader),
        strategies=strategies or {symbol: Strategy()},
        risk_manager=cast(Any, selected_risk),
    )
    return robot, selected_trader, selected_risk


def test_robot_applies_volatility_multiplier_to_sizing_and_keeps_paper_mode_read_only() -> None:
    robot, trader, risk = _robot(
        signal=Signal.BUY,
        risk=_Risk(multiplier=0.6),
        metrics={"atr_percentage": 2.5},
    )

    robot.trade_symbol("US100")

    assert risk.sizing == [
        {"symbol": "US100", "stop_loss_pips": 50.0, "volatility_multiplier": 0.6}
    ]
    assert trader.queries == [mt5.ORDER_TYPE_SELL, mt5.ORDER_TYPE_BUY]
    assert trader.writes == []


def test_robot_uses_explicit_multiplier_and_handles_neutral_or_missing_strategy() -> None:
    robot, trader, risk = _robot(signal=Signal.NONE, metrics={"atr_percentage": 2.0})

    assert robot.calculate_position_size("US100", volatility_multiplier=1.5) == 0.2
    assert risk.sizing[-1]["volatility_multiplier"] == 1.5
    robot.trade_symbol("US100")
    robot.trade_symbol("US500")

    assert trader.queries == []
    assert trader.writes == []


def test_paper_robot_does_not_close_or_submit_when_opposite_position_exists() -> None:
    trader = _Trader({mt5.ORDER_TYPE_SELL: 1})
    robot, _, _ = _robot(signal=Signal.BUY, trader=trader)

    robot.trade_symbol("US100")

    assert trader.queries == [mt5.ORDER_TYPE_SELL, mt5.ORDER_TYPE_BUY]
    assert trader.writes == []


def test_missing_current_quote_blocks_sizing_without_mutating_orders_or_account(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, Any]] = []
    info = SimpleNamespace(
        trade_tick_size=0.01,
        trade_tick_value=1.0,
        digits=2,
        volume_min=0.01,
        volume_max=10.0,
        volume_step=0.01,
    )

    def select_symbol(symbol: str, selected: bool) -> bool:
        calls.append(("select", (symbol, selected)))
        return True

    def symbol_info(symbol: str) -> Any:
        calls.append(("info", symbol))
        return info

    def stale_tick(symbol: str) -> None:
        calls.append(("tick", symbol))
        return None

    monkeypatch.setattr(mt5, "symbol_select", select_symbol, raising=False)
    monkeypatch.setattr(mt5, "symbol_info", symbol_info, raising=False)
    monkeypatch.setattr(mt5, "symbol_info_tick", stale_tick, raising=False)
    monkeypatch.setattr(
        mt5, "account_info", lambda: pytest.fail("quote check precedes sizing"), raising=False
    )

    robot, trader, _ = _robot(signal=Signal.BUY, risk=cast(Any, RiskManager()))
    robot.trade_symbol("US100")

    assert calls == [("select", ("US100", True)), ("info", "US100"), ("tick", "US100")]
    assert trader.queries == [mt5.ORDER_TYPE_SELL, mt5.ORDER_TYPE_BUY]
    assert trader.writes == []
    assert trader.counts == {}


@pytest.mark.parametrize(
    ("positions", "expected_risk", "expected_reserve"),
    [
        (
            [
                {
                    "symbol": "US100",
                    "volume": 2.0,
                    "price_open": 100.0,
                    "sl": 99.0,
                    "profit": 12.0,
                }
            ],
            200.0,
            0.0,
        ),
        ([], 0.0, 0.0),
    ],
)
def test_exposure_accepts_mapping_records_and_reports_empty_account(
    monkeypatch: pytest.MonkeyPatch,
    positions: list[dict[str, Any]],
    expected_risk: float,
    expected_reserve: float,
) -> None:
    info = SimpleNamespace(trade_tick_size=0.01, trade_tick_value=1.0)
    monkeypatch.setattr(mt5, "positions_get", lambda: positions, raising=False)
    monkeypatch.setattr(mt5, "symbol_info", lambda _symbol: info, raising=False)

    exposure = RiskManager().get_total_exposure()

    assert exposure["total_positions"] == len(positions)
    assert exposure["total_open_risk"] == pytest.approx(expected_risk)
    assert exposure["total_open_execution_reserve"] == pytest.approx(expected_reserve)
    assert exposure["risk_unknown_positions"] == 0
    assert exposure["query_failed"] is False


def test_risk_configuration_reads_config_objects_through_their_getter() -> None:
    value = {"risk_per_symbol": 0.01}
    block = SimpleNamespace(get=lambda key, default=None: value.get(key, default))

    assert risk_configuration._read_value(block, "risk_per_symbol") == 0.01
    assert risk_configuration._read_value(block, "missing") is None
