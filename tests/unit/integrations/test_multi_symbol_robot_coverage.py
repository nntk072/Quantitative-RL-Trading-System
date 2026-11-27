"""Exercise multi-symbol robot decisions with broker calls replaced by fakes."""

from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from typing import Any, cast

import pytest

if "MetaTrader5" not in sys.modules:
    try:  # pragma: no cover - depends on platform
        import MetaTrader5  # noqa: F401
    except ImportError:
        sys.modules["MetaTrader5"] = ModuleType("MetaTrader5")

mt5 = cast(Any, sys.modules["MetaTrader5"])
for _name, _value in {
    "ORDER_TYPE_BUY": 0,
    "ORDER_TYPE_SELL": 1,
    "TRADE_RETCODE_DONE": 10009,
    "TRADE_RETCODE_DONE_PARTIAL": 10010,
}.items():
    if not hasattr(mt5, _name):
        setattr(mt5, _name, _value)

from integrations.mt5.domain.signal import Signal  # noqa: E402
from integrations.mt5.robot.multi_symbol_robot import MultiSymbolRobot  # noqa: E402


class _Strategy:
    def __init__(self, signal: Signal, symbol: str = "US100") -> None:
        self.value = signal
        self.symbol = symbol

    def signal(self) -> tuple[str, Signal]:
        return self.symbol, self.value


class _Manager:
    def __init__(self, metrics: dict[str, Any] | None = None) -> None:
        self.metrics = metrics

    def get_volatility_metrics(self, _symbol: str) -> dict[str, Any] | None:
        return self.metrics


class _Risk:
    supports_training_account_loss_guardrails = False

    def __init__(self, *, size: float = 0.25, allowed: bool = True) -> None:
        self.size = size
        self.allowed = allowed
        self.calls: list[tuple[Any, ...]] = []

    def get_volatility_multiplier(self, atr_percentage: float) -> float:
        self.calls.append(("volatility", atr_percentage))
        return 0.5

    def calculate_position_size(self, **kwargs: Any) -> float:
        self.calls.append(("size", kwargs))
        return self.size

    def calculate_stop_loss_price(self, symbol: str, side: int, pips: float) -> float:
        self.calls.append(("stop", symbol, side, pips))
        return 19000.0

    def check_risk_limits(self, symbol: str, size: float, pips: float) -> tuple[bool, str]:
        self.calls.append(("check", symbol, size, pips))
        return self.allowed, "risk limit"

    def get_total_exposure(self) -> dict[str, Any]:
        return {"total_positions": 0, "total_volume": 0.0, "total_profit": 0.0, "symbols": {}}


class _Trader:
    def __init__(self, positions: dict[int, int] | None = None, result: Any = None) -> None:
        self.positions = positions or {}
        self.result = result
        self.calls: list[tuple[Any, ...]] = []

    def get_opened_positions(
        self, _symbol: str, side: int, *, magic_number: int
    ) -> tuple[int, list[Any]]:
        self.calls.append(("positions", side, magic_number))
        return self.positions.get(side, 0), []

    def close_positions(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("close", *args, kwargs))

    def open_position(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append(("open", *args, kwargs))
        return self.result


def _robot(
    signal: Signal = Signal.BUY,
    *,
    risk: _Risk | None = None,
    trader: _Trader | None = None,
    manager: _Manager | None = None,
    strategies: dict[str, _Strategy] | None = None,
    paper: bool = True,
) -> tuple[MultiSymbolRobot, _Risk, _Trader]:
    selected_risk = risk or _Risk()
    selected_trader = trader or _Trader()
    robot = MultiSymbolRobot(
        symbol_manager=cast(Any, manager or _Manager()),
        trader=cast(Any, selected_trader),
        strategies=cast(
            Any,
            strategies if strategies is not None else {"US100": _Strategy(signal)},
        ),
        risk_manager=cast(Any, selected_risk),
        stop_loss_pips=12.0,
        paper_trading=paper,
    )
    return robot, selected_risk, selected_trader


def test_paper_buy_uses_volatility_risk_and_never_sends_an_order() -> None:
    robot, risk, trader = _robot(manager=_Manager({"atr_percentage": 1.7}))

    robot.trade_symbol("US100")

    assert risk.calls == [
        ("volatility", 1.7),
        (
            "size",
            {"symbol": "US100", "stop_loss_pips": 12.0, "volatility_multiplier": 0.5},
        ),
        ("stop", "US100", mt5.ORDER_TYPE_BUY, 12.0),
        ("check", "US100", 0.25, 12.0),
    ]
    assert all(call[0] != "open" for call in trader.calls)


def test_robot_refuses_bad_size_or_risk_before_paper_order() -> None:
    for risk in (_Risk(size=0.0), _Risk(allowed=False)):
        robot, _, trader = _robot(risk=risk)
        robot.trade_symbol("US100")
        assert all(call[0] != "open" for call in trader.calls)


def test_robot_handles_missing_strategy_existing_position_and_no_signal() -> None:
    robot, risk, trader = _robot(strategies={})
    robot.trade_symbol("US100")
    assert not risk.calls
    assert not trader.calls

    robot, risk, trader = _robot(
        trader=_Trader({mt5.ORDER_TYPE_BUY: 1}),
        strategies={"US100": _Strategy(Signal.BUY, "OTHER")},
    )
    robot.trade_symbol("US100")
    assert not risk.calls
    assert sum(call[0] == "positions" for call in trader.calls) == 2

    robot, risk, trader = _robot(Signal.NONE)
    robot.trade_symbol("US100")
    assert not risk.calls
    assert not trader.calls


def test_paper_sell_does_not_close_opposite_broker_position() -> None:
    robot, risk, trader = _robot(
        Signal.SELL,
        trader=_Trader({mt5.ORDER_TYPE_BUY: 1}),
    )

    robot.trade_symbol("US100")

    assert ("check", "US100", 0.25, 12.0) in risk.calls
    assert all(call[0] != "close" for call in trader.calls)
    assert all(call[0] != "open" for call in trader.calls)


@pytest.mark.parametrize(
    ("retcode", "expected_message"),
    [
        (10009, "Buy position opened"),
        (10010, "partially filled"),
        (999, "Failed to open"),
    ],
)
def test_guarded_live_buy_reports_order_outcome_without_real_broker(
    retcode: int, expected_message: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    class GuardedRisk(_Risk):
        supports_training_account_loss_guardrails = True

    trader = _Trader(result=SimpleNamespace(retcode=retcode, order=42, volume=0.25, price=20000.0))
    monkeypatch.setattr(mt5, "ORDER_TYPE_BUY", 0, raising=False)
    robot, _, _ = _robot(risk=GuardedRisk(), trader=trader, paper=False)
    messages: list[str] = []
    monkeypatch.setattr(
        "integrations.mt5.robot.multi_symbol_robot.logger.info",
        lambda message, *_args: messages.append(str(message)),
    )
    monkeypatch.setattr(
        "integrations.mt5.robot.multi_symbol_robot.logger.warning",
        lambda message, *_args: messages.append(str(message)),
    )
    monkeypatch.setattr(
        "integrations.mt5.robot.multi_symbol_robot.logger.error",
        lambda message, *_args: messages.append(str(message)),
    )

    robot.trade_symbol("US100")

    assert any(expected_message in message for message in messages)
    order_calls = [call for call in trader.calls if call[0] == "open"]
    assert len(order_calls) == 1
    assert order_calls[0][1:4] == ("US100", 0.25, mt5.ORDER_TYPE_BUY)


def test_live_robot_requires_explicit_training_account_guardrails() -> None:
    with pytest.raises(ValueError, match="training-equivalent daily and maximum"):
        _robot(paper=False, risk=_Risk())


@pytest.mark.parametrize(
    ("signal", "opposite_side"),
    [
        (Signal.BUY, mt5.ORDER_TYPE_SELL),
        (Signal.SELL, mt5.ORDER_TYPE_BUY),
    ],
)
def test_live_entry_rechecks_guardrails_after_risk_reducing_close(
    signal: Signal, opposite_side: int
) -> None:
    class GuardedRisk(_Risk):
        supports_training_account_loss_guardrails = True

    class ClosingTrader(_Trader):
        def close_positions(self, *args: Any, **kwargs: Any) -> None:
            super().close_positions(*args, **kwargs)
            self.positions[opposite_side] = 0

    risk = GuardedRisk()
    trader = ClosingTrader({opposite_side: 1})
    robot, _, _ = _robot(signal, risk=risk, trader=trader, paper=False)
    risk.supports_training_account_loss_guardrails = False

    robot.trade_symbol("US100")

    assert not risk.calls
    assert sum(call[0] == "close" for call in trader.calls) == 1
    assert sum(call[0] == "open" for call in trader.calls) == 0


def test_robot_cycle_and_status_include_available_account_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BrokenStrategy:
        def signal(self) -> tuple[str, Signal]:
            raise RuntimeError("feed unavailable")

    robot, _, _ = _robot(
        strategies={
            "BROKEN": cast(Any, BrokenStrategy()),
            "US100": _Strategy(Signal.NONE),
        }
    )
    monkeypatch.setattr(
        mt5,
        "account_info",
        lambda: SimpleNamespace(balance=25000.0, equity=24750.0, margin=125.0),
        raising=False,
    )
    errors: list[str] = []
    monkeypatch.setattr(
        "integrations.mt5.robot.multi_symbol_robot.logger.exception",
        lambda message, *_args: errors.append(str(message)),
    )

    robot.trade()
    status = robot.get_status()

    assert any("BROKEN" in error for error in errors)
    assert status["symbols"] == ["BROKEN", "US100"]
    assert status["account_balance"] == 25000.0
    assert status["account_equity"] == 24750.0


@pytest.mark.parametrize(
    ("retcode", "expected_message"),
    [
        (10009, "Sell position opened"),
        (10010, "partially filled"),
        (999, "Failed to open"),
    ],
)
def test_guarded_live_sell_reports_order_outcome_without_real_broker(
    retcode: int, expected_message: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    class GuardedRisk(_Risk):
        supports_training_account_loss_guardrails = True

    trader = _Trader(result=SimpleNamespace(retcode=retcode, order=43, volume=0.25, price=19900.0))
    monkeypatch.setattr(mt5, "ORDER_TYPE_SELL", 1, raising=False)
    robot, _, _ = _robot(Signal.SELL, risk=GuardedRisk(), trader=trader, paper=False)
    messages: list[str] = []
    for method_name in ("info", "warning", "error"):
        monkeypatch.setattr(
            f"integrations.mt5.robot.multi_symbol_robot.logger.{method_name}",
            lambda message, *_args: messages.append(str(message)),
        )

    robot.trade_symbol("US100")

    assert any(expected_message in message for message in messages)
    order_calls = [call for call in trader.calls if call[0] == "open"]
    assert len(order_calls) == 1
    assert order_calls[0][1:4] == ("US100", 0.25, mt5.ORDER_TYPE_SELL)


@pytest.mark.parametrize("flattens", [True, False])
def test_live_entry_waits_for_opposite_positions_to_flatten(
    flattens: bool,
) -> None:
    class GuardedRisk(_Risk):
        supports_training_account_loss_guardrails = True

    class ClosingTrader(_Trader):
        def close_positions(self, *args: Any, **kwargs: Any) -> None:
            super().close_positions(*args, **kwargs)
            if flattens:
                self.positions[mt5.ORDER_TYPE_SELL] = 0

    trader = ClosingTrader(
        positions={mt5.ORDER_TYPE_SELL: 1},
        result=SimpleNamespace(
            retcode=mt5.TRADE_RETCODE_DONE, order=44, volume=0.25, price=20000.0
        ),
    )
    robot, risk, _ = _robot(risk=GuardedRisk(), trader=trader, paper=False)

    robot.trade_symbol("US100")

    assert sum(call[0] == "close" for call in trader.calls) == 1
    assert sum(call[0] == "open" for call in trader.calls) == int(flattens)
    assert sum(call[0] == "check" for call in risk.calls) == int(flattens)


def test_live_entry_returns_when_broker_provides_no_order_result() -> None:
    class GuardedRisk(_Risk):
        supports_training_account_loss_guardrails = True

    trader = _Trader(result=None)
    robot, _, _ = _robot(risk=GuardedRisk(), trader=trader, paper=False)

    robot.trade_symbol("US100")

    assert sum(call[0] == "open" for call in trader.calls) == 1


def test_position_sizing_uses_default_atr_and_fails_closed_on_metrics_error() -> None:
    robot, risk, _ = _robot(manager=_Manager({"source": "fixture"}))

    assert robot.calculate_position_size("US100", volatility_multiplier=0.75) == pytest.approx(0.25)
    assert risk.calls == [
        (
            "size",
            {"symbol": "US100", "stop_loss_pips": 12.0, "volatility_multiplier": 0.75},
        )
    ]
    risk.calls.clear()
    assert robot.calculate_position_size("US100") == pytest.approx(0.25)
    assert risk.calls == [
        ("volatility", 1.0),
        (
            "size",
            {"symbol": "US100", "stop_loss_pips": 12.0, "volatility_multiplier": 0.5},
        ),
    ]

    class BrokenManager:
        def get_volatility_metrics(self, _symbol: str) -> dict[str, Any]:
            raise RuntimeError("metrics unavailable")

    robot, _, _ = _robot(manager=cast(Any, BrokenManager()))
    assert robot.calculate_position_size("US100") == 0.0
