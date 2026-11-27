"""Fail-closed execution and live signal branches for the RL robot."""

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

from integrations.mt5.robot import rl_robot as rl_robot_module  # noqa: E402
from live.runtime.contracts import LiveSignal  # noqa: E402

_MT5 = SimpleNamespace(
    ORDER_TYPE_BUY=0,
    ORDER_TYPE_SELL=1,
    TRADE_RETCODE_DONE=10009,
    TRADE_RETCODE_DONE_PARTIAL=10010,
)


class _Data:
    def get_symbol(self) -> str:
        return "US100.cash"


class _Strategy:
    def __init__(self, signal: LiveSignal | Exception = LiveSignal.NONE) -> None:
        self.selected_signal = signal

    def signal(self) -> tuple[str, LiveSignal]:
        if isinstance(self.selected_signal, Exception):
            raise self.selected_signal
        return "US100.cash", self.selected_signal


class _Adapter:
    def __init__(self, strategy: _Strategy) -> None:
        self.strategy = strategy

    def as_strategy(self, _data: object, _secondary: object | None) -> _Strategy:
        return self.strategy


class _Risk:
    def __init__(
        self,
        *,
        size: float = 0.2,
        allowed: bool = True,
        supports_guardrails: bool = True,
        stop_error: Exception | None = None,
        size_error: Exception | None = None,
    ) -> None:
        self.size = size
        self.allowed = allowed
        self.supports_training_account_loss_guardrails = supports_guardrails
        self.stop_error = stop_error
        self.size_error = size_error
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def calculate_position_size(self, *args: Any) -> float:
        self.calls.append(("size", args))
        if self.size_error is not None:
            raise self.size_error
        return self.size

    def calculate_stop_loss_price(self, *args: Any) -> float:
        self.calls.append(("stop", args))
        if self.stop_error is not None:
            raise self.stop_error
        return 98.5

    def check_risk_limits(self, *args: Any) -> tuple[bool, str]:
        self.calls.append(("limits", args))
        return self.allowed, "risk limit rejected" if not self.allowed else "risk accepted"


class _Trader:
    def __init__(
        self,
        *,
        buys: int = 0,
        sells: int = 0,
        open_result: object | None = None,
        close_completes: bool = True,
    ) -> None:
        self.counts = {_MT5.ORDER_TYPE_BUY: buys, _MT5.ORDER_TYPE_SELL: sells}
        self.open_result = open_result
        self.close_completes = close_completes
        self.opens: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
        self.closes: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
        self.queries: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def get_opened_positions(self, *args: Any, **kwargs: Any) -> tuple[int, object]:
        self.queries.append((args, kwargs))
        return self.counts[args[1]], object()

    def close_positions(self, *args: Any, **kwargs: Any) -> None:
        self.closes.append((args, kwargs))
        if self.close_completes:
            self.counts[args[2]] = 0

    def open_position(self, *args: Any, **kwargs: Any) -> object | None:
        self.opens.append((args, kwargs))
        return self.open_result


def _make_robot(
    *,
    signal: LiveSignal | Exception = LiveSignal.NONE,
    risk: _Risk | None = None,
    trader: _Trader | None = None,
    paper: bool = False,
) -> tuple[Any, _Risk, _Trader]:
    selected_risk = risk or _Risk(supports_guardrails=not paper)
    selected_trader = trader or _Trader()
    robot = rl_robot_module.RLRobot(
        adapter=cast(Any, _Adapter(_Strategy(signal))),
        data_source=cast(Any, _Data()),
        trader=cast(Any, selected_trader),
        risk_manager=cast(Any, selected_risk),
        paper_trading=paper,
    )
    return robot, selected_risk, selected_trader


@pytest.fixture(autouse=True)
def _install_mt5_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rl_robot_module, "mt5", _MT5)


def test_live_mode_requires_training_equivalent_risk_guardrails() -> None:
    with pytest.raises(ValueError, match="training-equivalent"):
        _make_robot(risk=_Risk(supports_guardrails=False), paper=False)


@pytest.mark.parametrize("size", [0.0, -0.1])
def test_open_refuses_nonpositive_position_size(size: float) -> None:
    robot, risk, trader = _make_robot(risk=_Risk(size=size))

    robot._open("US100.cash", _MT5.ORDER_TYPE_BUY)

    assert [name for name, _ in risk.calls] == ["size"]
    assert trader.opens == []


def test_position_sizing_failure_fails_closed() -> None:
    robot, risk, trader = _make_robot(risk=_Risk(size_error=RuntimeError("invalid quote")))

    assert robot.calculate_position_size("US100.cash") == 0.0
    robot._open("US100.cash", _MT5.ORDER_TYPE_BUY)

    assert [name for name, _ in risk.calls] == ["size", "size"]
    assert trader.opens == []


def test_stop_price_failure_and_risk_limit_rejection_do_not_submit_orders() -> None:
    stop_robot, stop_risk, stop_trader = _make_robot(
        risk=_Risk(stop_error=RuntimeError("no quote"))
    )
    stop_robot._open("US100.cash", _MT5.ORDER_TYPE_BUY)

    denied_robot, denied_risk, denied_trader = _make_robot(risk=_Risk(allowed=False))
    denied_robot._open("US100.cash", _MT5.ORDER_TYPE_SELL)

    assert [name for name, _ in stop_risk.calls] == ["size", "stop"]
    assert [name for name, _ in denied_risk.calls] == ["size", "stop", "limits"]
    assert stop_trader.opens == denied_trader.opens == []


@pytest.mark.parametrize(
    ("result", "expected_method", "expected_message"),
    [
        (None, None, None),
        (
            SimpleNamespace(retcode=10009, order=7, volume=0.2, price=101.0),
            "info",
            "position opened",
        ),
        (
            SimpleNamespace(retcode=10010, order=8, volume=0.1, price=100.5),
            "warning",
            "partially filled",
        ),
        (SimpleNamespace(retcode=10030), "error", "Failed to open SELL position"),
    ],
)
def test_live_open_records_order_and_handles_broker_result(
    result: object | None,
    expected_method: str | None,
    expected_message: str | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages: list[tuple[str, str]] = []

    def record(method: str) -> Any:
        def log(message: str, *_args: Any, **_kwargs: Any) -> None:
            messages.append((method, message))

        return log

    for method in ("info", "warning", "error"):
        monkeypatch.setattr(cast(Any, rl_robot_module).logger, method, record(method))
    robot, _risk, trader = _make_robot(trader=_Trader(open_result=result))

    robot._open("US100.cash", _MT5.ORDER_TYPE_SELL)

    assert len(trader.opens) == 1
    args, kwargs = trader.opens[0]
    assert args[:5] == (
        "US100.cash",
        0.2,
        _MT5.ORDER_TYPE_SELL,
        "RL Robot sell position",
        robot.magic_number,
    )
    assert kwargs == {"sl": 98.5, "tp": None}
    if expected_method is None:
        assert not any("position opened" in message for _method, message in messages)
    else:
        assert expected_message is not None
        assert any(
            method == expected_method and expected_message in message
            for method, message in messages
        )


def test_live_open_guard_refuses_if_guardrail_capability_is_lost() -> None:
    robot, risk, trader = _make_robot()
    risk.supports_training_account_loss_guardrails = False

    robot._open("US100.cash", _MT5.ORDER_TYPE_BUY)

    assert risk.calls == []
    assert trader.opens == []


def test_close_routes_live_requests_and_paper_mode_stays_read_only() -> None:
    live_robot, _risk, live_trader = _make_robot()
    live_robot._close("US100.cash", _MT5.ORDER_TYPE_SELL)
    paper_robot, _paper_risk, paper_trader = _make_robot(paper=True)
    paper_robot._close("US100.cash", _MT5.ORDER_TYPE_BUY)

    assert live_trader.closes == [
        (
            ("RL Robot", "US100.cash", _MT5.ORDER_TYPE_SELL),
            {"magic_number": live_robot.magic_number},
        )
    ]
    assert paper_trader.closes == []


def test_paper_buy_logs_close_and_open_intents_without_broker_writes() -> None:
    trader = _Trader(sells=1)
    robot, _risk, _trader = _make_robot(
        signal=LiveSignal.BUY,
        risk=_Risk(),
        trader=trader,
        paper=True,
    )

    robot.trade()

    assert len(trader.queries) == 2
    assert trader.opens == trader.closes == []


def test_trade_handles_signal_error_none_and_hold_without_broker_writes() -> None:
    failed_robot, _risk, failed_trader = _make_robot(signal=RuntimeError("policy unavailable"))
    failed_robot.trade()
    none_robot, _none_risk, none_trader = _make_robot(signal=LiveSignal.NONE)
    none_robot.trade()
    hold_robot, _hold_risk, hold_trader = _make_robot(signal=LiveSignal.HOLD)
    hold_robot.trade()

    assert failed_trader.queries == failed_trader.opens == failed_trader.closes == []
    assert none_trader.queries == none_trader.opens == none_trader.closes == []
    assert hold_trader.queries == hold_trader.opens == hold_trader.closes == []


@pytest.mark.parametrize(
    ("signal", "own_side", "opposite_side", "expected_close"),
    [
        (LiveSignal.BUY, 0, 1, _MT5.ORDER_TYPE_SELL),
        (LiveSignal.SELL, 1, 0, _MT5.ORDER_TYPE_BUY),
    ],
)
def test_trade_closes_opposite_position_but_keeps_existing_own_position(
    signal: LiveSignal, own_side: int, opposite_side: int, expected_close: int
) -> None:
    trader = _Trader(buys=own_side, sells=own_side, close_completes=True)
    trader.counts[own_side] = 1
    trader.counts[opposite_side] = 1
    robot, _risk, _trader = _make_robot(signal=signal, trader=trader)

    robot.trade()

    assert len(trader.closes) == 1
    assert trader.closes[0][0][2] == expected_close
    assert trader.opens == []
