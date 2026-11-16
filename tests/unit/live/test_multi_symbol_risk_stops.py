"""The multi-symbol risk robot must submit the stop it sized against."""

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

_mt5 = sys.modules["MetaTrader5"]
for _name, _value in {
    "TIMEFRAME_H1": 60,
    "ORDER_TYPE_BUY": 0,
    "ORDER_TYPE_SELL": 1,
    "TRADE_RETCODE_DONE": 10009,
    "TRADE_RETCODE_DONE_PARTIAL": 10010,
}.items():
    if not hasattr(_mt5, _name):
        setattr(_mt5, _name, _value)

import MetaTrader5 as mt5  # noqa: E402

from integrations.mt5.domain.risk_manager import RiskManager  # noqa: E402
from integrations.mt5.domain.signal import Signal  # noqa: E402
from integrations.mt5.robot.multi_symbol_robot import MultiSymbolRobot  # noqa: E402


class _Trader:
    def __init__(self) -> None:
        self.open_calls: list[dict[str, Any]] = []

    def open_position(
        self, symbol: str, volume: float, position_type: int, *args: Any, **kwargs: Any
    ):
        self.open_calls.append({"symbol": symbol, "type": position_type, "sl": kwargs.get("sl")})
        return SimpleNamespace(retcode=mt5.TRADE_RETCODE_DONE, order=1, volume=volume, price=100.0)

    def get_opened_positions(self, *_args: Any, **_kwargs: Any) -> tuple[int, pd.DataFrame]:
        return 0, pd.DataFrame()

    def close_positions(self, *_args: Any, **_kwargs: Any) -> None:
        return None


class _Strategy:
    def __init__(self, symbol: str, signal: Signal) -> None:
        self.symbol = symbol
        self._signal = signal

    def signal(self) -> tuple[str, Signal]:
        return self.symbol, self._signal


class _Risk:
    supports_training_account_loss_guardrails = True

    def calculate_position_size(self, *_args: Any, **_kwargs: Any) -> float:
        return 0.1

    def check_risk_limits(self, *_args: Any, **_kwargs: Any) -> tuple[bool, str]:
        return True, "risk ok"

    def calculate_stop_loss_price(self, _symbol: str, order_type: int, _pips: float) -> float:
        return 99.0 if order_type == mt5.ORDER_TYPE_BUY else 101.0


class _Symbols:
    def get_volatility_metrics(self, _symbol: str) -> None:
        return None


@pytest.mark.parametrize(
    ("signal", "order_type", "expected_stop"),
    [(Signal.BUY, mt5.ORDER_TYPE_BUY, 99.0), (Signal.SELL, mt5.ORDER_TYPE_SELL, 101.0)],
)
def test_multi_symbol_robot_submits_broker_stop(
    signal: Signal, order_type: int, expected_stop: float
) -> None:
    trader = _Trader()
    symbol = "US100.cash"
    robot = MultiSymbolRobot(
        symbol_manager=cast(Any, _Symbols()),
        trader=trader,  # type: ignore[arg-type]
        strategies=cast(Any, {symbol: _Strategy(symbol, signal)}),
        risk_manager=_Risk(),  # type: ignore[arg-type]
        paper_trading=False,
    )

    robot.trade_symbol(symbol)

    assert trader.open_calls == [{"symbol": symbol, "type": order_type, "sl": expected_stop}]


def test_multi_symbol_robot_refuses_entry_when_risk_sizing_returns_zero() -> None:
    class UnsizeableRisk(_Risk):
        def calculate_position_size(self, *_args: Any, **_kwargs: Any) -> float:
            return 0.0

    trader = _Trader()
    symbol = "US100.cash"
    robot = MultiSymbolRobot(
        symbol_manager=cast(Any, _Symbols()),
        trader=trader,  # type: ignore[arg-type]
        strategies=cast(Any, {symbol: _Strategy(symbol, Signal.BUY)}),
        risk_manager=UnsizeableRisk(),  # type: ignore[arg-type]
        paper_trading=False,
    )

    robot.trade_symbol(symbol)

    assert trader.open_calls == []


def test_multi_symbol_robot_refuses_entry_when_risk_sizing_raises() -> None:
    class UnavailableRisk(_Risk):
        def calculate_position_size(self, *_args: Any, **_kwargs: Any) -> float:
            raise RuntimeError("symbol tick value unavailable")

    trader = _Trader()
    symbol = "US100.cash"
    robot = MultiSymbolRobot(
        symbol_manager=cast(Any, _Symbols()),
        trader=trader,  # type: ignore[arg-type]
        strategies=cast(Any, {symbol: _Strategy(symbol, Signal.BUY)}),
        risk_manager=UnavailableRisk(),  # type: ignore[arg-type]
        paper_trading=False,
    )

    robot.trade_symbol(symbol)

    assert trader.open_calls == []


def test_multi_symbol_robot_rejects_real_order_mode_without_account_loss_guardrails() -> None:
    trader = _Trader()
    symbol = "US100.cash"
    with pytest.raises(ValueError, match="training-equivalent daily and maximum account-loss"):
        MultiSymbolRobot(
            symbol_manager=cast(Any, _Symbols()),
            trader=trader,  # type: ignore[arg-type]
            strategies=cast(Any, {symbol: _Strategy(symbol, Signal.BUY)}),
            risk_manager=RiskManager(),
            paper_trading=False,
        )


@pytest.mark.parametrize("signal", [Signal.BUY, Signal.SELL])
def test_multi_symbol_robot_closes_opposite_position_before_opening(
    signal: Signal,
) -> None:
    opening_type = mt5.ORDER_TYPE_BUY if signal is Signal.BUY else mt5.ORDER_TYPE_SELL
    closing_type = mt5.ORDER_TYPE_SELL if signal is Signal.BUY else mt5.ORDER_TYPE_BUY

    class ReversingTrader(_Trader):
        def __init__(self, *, close_completes: bool) -> None:
            super().__init__()
            self.open_position_type: int | None = closing_type
            self.close_completes = close_completes
            self.events: list[tuple[str, int]] = []

        def open_position(
            self, symbol: str, volume: float, position_type: int, *args: Any, **kwargs: Any
        ):
            self.events.append(("open", position_type))
            return super().open_position(symbol, volume, position_type, *args, **kwargs)

        def get_opened_positions(
            self, _symbol: str | None = None, position_type: int | None = None, **_kwargs: Any
        ) -> tuple[int, pd.DataFrame]:
            return int(position_type == self.open_position_type), pd.DataFrame()

        def close_positions(
            self,
            _robot_name: str,
            _symbol: str | None = None,
            position_type: int | None = None,
            **_kwargs: Any,
        ):
            assert position_type is not None
            self.events.append(("close", int(position_type)))
            if self.close_completes:
                self.open_position_type = None

    trader = ReversingTrader(close_completes=True)
    symbol = "US100.cash"
    robot = MultiSymbolRobot(
        symbol_manager=cast(Any, _Symbols()),
        trader=trader,  # type: ignore[arg-type]
        strategies=cast(Any, {symbol: _Strategy(symbol, signal)}),
        risk_manager=_Risk(),  # type: ignore[arg-type]
        paper_trading=False,
    )

    robot.trade_symbol(symbol)

    assert trader.events == [("close", closing_type), ("open", opening_type)]


@pytest.mark.parametrize("signal", [Signal.BUY, Signal.SELL])
def test_multi_symbol_robot_does_not_reverse_while_close_is_incomplete(
    signal: Signal,
) -> None:
    closing_type = mt5.ORDER_TYPE_SELL if signal is Signal.BUY else mt5.ORDER_TYPE_BUY

    class ReversingTrader(_Trader):
        def __init__(self) -> None:
            super().__init__()
            self.open_position_type: int | None = closing_type
            self.closed = False

        def get_opened_positions(
            self, _symbol: str | None = None, position_type: int | None = None, **_kwargs: Any
        ) -> tuple[int, pd.DataFrame]:
            return int(position_type == self.open_position_type), pd.DataFrame()

        def close_positions(
            self,
            _robot_name: str,
            _symbol: str | None = None,
            _position_type: int | None = None,
            **_kwargs: Any,
        ) -> None:
            self.closed = True

    trader = ReversingTrader()
    symbol = "US100.cash"
    robot = MultiSymbolRobot(
        symbol_manager=cast(Any, _Symbols()),
        trader=trader,  # type: ignore[arg-type]
        strategies=cast(Any, {symbol: _Strategy(symbol, signal)}),
        risk_manager=_Risk(),  # type: ignore[arg-type]
        paper_trading=False,
    )

    robot.trade_symbol(symbol)

    assert trader.closed
    assert trader.open_calls == []
