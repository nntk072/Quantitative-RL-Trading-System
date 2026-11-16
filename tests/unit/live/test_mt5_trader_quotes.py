"""MT5 close orders use the executable side of the current quote."""

from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace

import pandas as pd
import pytest

if "MetaTrader5" not in sys.modules:
    try:  # pragma: no cover - depends on platform
        import MetaTrader5  # noqa: F401
    except ImportError:
        sys.modules["MetaTrader5"] = ModuleType("MetaTrader5")

import MetaTrader5 as mt5  # noqa: E402

for _name, _value in {
    "TRADE_ACTION_DEAL": 1,
    "ORDER_TYPE_BUY": 0,
    "ORDER_TYPE_SELL": 1,
    "ORDER_TIME_GTC": 0,
    "ORDER_FILLING_FOK": 0,
    "ORDER_FILLING_IOC": 1,
    "ORDER_FILLING_RETURN": 2,
    "SYMBOL_FILLING_FOK": 1,
    "SYMBOL_FILLING_IOC": 2,
    "SYMBOL_TRADE_EXECUTION_REQUEST": 0,
    "SYMBOL_TRADE_EXECUTION_INSTANT": 1,
    "SYMBOL_TRADE_EXECUTION_MARKET": 2,
    "SYMBOL_TRADE_EXECUTION_EXCHANGE": 3,
    "SYMBOL_TRADE_MODE_DISABLED": 0,
    "SYMBOL_TRADE_MODE_LONGONLY": 1,
    "SYMBOL_TRADE_MODE_SHORTONLY": 2,
    "SYMBOL_TRADE_MODE_CLOSEONLY": 3,
    "SYMBOL_TRADE_MODE_FULL": 4,
    "SYMBOL_ORDER_MARKET": 1,
    "SYMBOL_ORDER_SL": 16,
    "SYMBOL_ORDER_TP": 32,
    "TRADE_RETCODE_DONE": 10009,
    "TRADE_RETCODE_DONE_PARTIAL": 10010,
    "TIMEFRAME_H1": 16385,
}.items():
    if not hasattr(mt5, _name):
        setattr(mt5, _name, _value)

from integrations.mt5.domain.trader import MT5Trader  # noqa: E402


def _symbol_info(
    filling_mode: int,
    execution_mode: int,
    *,
    volume_min: float = 0.01,
    volume_max: float = 100.0,
    volume_step: float = 0.01,
    trade_mode: int = 4,
    order_mode: int = 49,
) -> SimpleNamespace:
    return SimpleNamespace(
        filling_mode=filling_mode,
        trade_exemode=execution_mode,
        volume_min=volume_min,
        volume_max=volume_max,
        volume_step=volume_step,
        trade_mode=trade_mode,
        order_mode=order_mode,
    )


@pytest.mark.parametrize(
    ("position_type", "expected_order_type", "expected_price"),
    [
        (mt5.ORDER_TYPE_BUY, mt5.ORDER_TYPE_SELL, 100.1),
        (mt5.ORDER_TYPE_SELL, mt5.ORDER_TYPE_BUY, 100.2),
    ],
)
def test_close_position_uses_executable_quote_side(
    monkeypatch: pytest.MonkeyPatch,
    position_type: int,
    expected_order_type: int,
    expected_price: float,
) -> None:
    trader = MT5Trader()
    positions = pd.DataFrame(
        [
            {
                "ticket": 17,
                "symbol": "US100.cash",
                "volume": 0.2,
                "type": position_type,
                "magic": 42,
            }
        ]
    )
    submitted: list[dict[str, object]] = []
    monkeypatch.setattr(trader, "get_all_positions", lambda: positions)
    monkeypatch.setattr(
        mt5,
        "symbol_info",
        lambda _symbol: _symbol_info(mt5.SYMBOL_FILLING_FOK, mt5.SYMBOL_TRADE_EXECUTION_MARKET),
        raising=False,
    )
    monkeypatch.setattr(
        mt5,
        "symbol_info_tick",
        lambda _symbol: SimpleNamespace(bid=100.1, ask=100.2),
        raising=False,
    )
    monkeypatch.setattr(mt5, "order_send", lambda order: submitted.append(order), raising=False)

    trader.close_positions(
        "test", symbol="US100.cash", position_type=position_type, magic_number=42
    )

    assert len(submitted) == 1
    assert submitted[0]["type"] == expected_order_type
    assert submitted[0]["price"] == expected_price


@pytest.mark.parametrize(
    ("filling_mode", "execution_mode", "expected"),
    [
        (
            mt5.SYMBOL_FILLING_FOK | mt5.SYMBOL_FILLING_IOC,
            mt5.SYMBOL_TRADE_EXECUTION_MARKET,
            mt5.ORDER_FILLING_FOK,
        ),
        (
            mt5.SYMBOL_FILLING_IOC,
            mt5.SYMBOL_TRADE_EXECUTION_MARKET,
            mt5.ORDER_FILLING_IOC,
        ),
        (0, mt5.SYMBOL_TRADE_EXECUTION_REQUEST, mt5.ORDER_FILLING_FOK),
        (0, mt5.SYMBOL_TRADE_EXECUTION_EXCHANGE, mt5.ORDER_FILLING_RETURN),
    ],
)
def test_open_position_uses_a_fill_mode_supported_by_symbol(
    monkeypatch: pytest.MonkeyPatch,
    filling_mode: int,
    execution_mode: int,
    expected: int,
) -> None:
    submitted: list[dict[str, object]] = []

    def send_order(order: dict[str, object]) -> SimpleNamespace:
        submitted.append(order)
        return SimpleNamespace(retcode=mt5.TRADE_RETCODE_DONE)

    monkeypatch.setattr(
        mt5,
        "symbol_info",
        lambda _symbol: _symbol_info(filling_mode, execution_mode),
        raising=False,
    )
    monkeypatch.setattr(
        mt5,
        "order_send",
        send_order,
        raising=False,
    )

    result = MT5Trader().open_position("US100.cash", 0.1, 0, "test", 42)

    assert result is not None
    assert submitted[0]["type_filling"] == expected


def test_open_position_rejects_volume_off_symbol_step(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    submitted: list[dict[str, object]] = []
    monkeypatch.setattr(
        mt5,
        "symbol_info",
        lambda _symbol: _symbol_info(mt5.SYMBOL_FILLING_FOK, mt5.SYMBOL_TRADE_EXECUTION_MARKET),
        raising=False,
    )
    monkeypatch.setattr(mt5, "order_send", lambda order: submitted.append(order), raising=False)

    result = MT5Trader().open_position("US100.cash", 0.015, 0, "test", 42)

    assert result is None
    assert submitted == []


def test_open_position_accepts_volume_steps_from_minimum_volume(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    submitted: list[dict[str, object]] = []

    def send_order(order: dict[str, object]) -> SimpleNamespace:
        submitted.append(order)
        return SimpleNamespace(retcode=mt5.TRADE_RETCODE_DONE)

    monkeypatch.setattr(
        mt5,
        "symbol_info",
        lambda _symbol: _symbol_info(
            mt5.SYMBOL_FILLING_FOK,
            mt5.SYMBOL_TRADE_EXECUTION_MARKET,
            volume_min=0.1,
            volume_step=0.2,
        ),
        raising=False,
    )
    monkeypatch.setattr(
        mt5,
        "order_send",
        send_order,
        raising=False,
    )

    result = MT5Trader().open_position("US100.cash", 0.3, 0, "test", 42)

    assert result is not None
    assert submitted[0]["volume"] == 0.3


def test_close_position_uses_ioc_when_symbol_disallows_fok(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trader = MT5Trader()
    positions = pd.DataFrame(
        [
            {
                "ticket": 17,
                "symbol": "US100.cash",
                "volume": 0.2,
                "type": mt5.ORDER_TYPE_BUY,
                "magic": 42,
            }
        ]
    )
    submitted: list[dict[str, object]] = []

    def send_partial_close(order: dict[str, object]) -> SimpleNamespace:
        submitted.append(order)
        return SimpleNamespace(retcode=mt5.TRADE_RETCODE_DONE_PARTIAL)

    monkeypatch.setattr(trader, "get_all_positions", lambda: positions)
    monkeypatch.setattr(
        mt5,
        "symbol_info",
        lambda _symbol: _symbol_info(mt5.SYMBOL_FILLING_IOC, mt5.SYMBOL_TRADE_EXECUTION_MARKET),
        raising=False,
    )
    monkeypatch.setattr(
        mt5,
        "symbol_info_tick",
        lambda _symbol: SimpleNamespace(bid=100.1, ask=100.2),
        raising=False,
    )
    monkeypatch.setattr(
        mt5,
        "order_send",
        send_partial_close,
        raising=False,
    )

    trader.close_positions(
        "test", symbol="US100.cash", position_type=mt5.ORDER_TYPE_BUY, magic_number=42
    )

    assert submitted[0]["type_filling"] == mt5.ORDER_FILLING_IOC


def test_open_position_rejects_filling_mode_not_allowed_by_market_symbol(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    submitted: list[dict[str, object]] = []
    monkeypatch.setattr(
        mt5,
        "symbol_info",
        lambda _symbol: _symbol_info(0, mt5.SYMBOL_TRADE_EXECUTION_MARKET),
        raising=False,
    )
    monkeypatch.setattr(mt5, "order_send", lambda order: submitted.append(order), raising=False)

    result = MT5Trader().open_position("US100.cash", 0.1, 0, "test", 42)

    assert result is None
    assert submitted == []


@pytest.mark.parametrize(
    ("trade_mode", "order_mode", "position_type"),
    [
        (mt5.SYMBOL_TRADE_MODE_DISABLED, mt5.SYMBOL_ORDER_MARKET, mt5.ORDER_TYPE_BUY),
        (mt5.SYMBOL_TRADE_MODE_CLOSEONLY, mt5.SYMBOL_ORDER_MARKET, mt5.ORDER_TYPE_SELL),
        (mt5.SYMBOL_TRADE_MODE_LONGONLY, mt5.SYMBOL_ORDER_MARKET, mt5.ORDER_TYPE_SELL),
        (mt5.SYMBOL_TRADE_MODE_SHORTONLY, mt5.SYMBOL_ORDER_MARKET, mt5.ORDER_TYPE_BUY),
        (mt5.SYMBOL_TRADE_MODE_FULL, 0, mt5.ORDER_TYPE_BUY),
    ],
)
def test_open_position_rejects_symbol_trade_restrictions(
    monkeypatch: pytest.MonkeyPatch,
    trade_mode: int,
    order_mode: int,
    position_type: int,
) -> None:
    submitted: list[dict[str, object]] = []
    monkeypatch.setattr(
        mt5,
        "symbol_info",
        lambda _symbol: _symbol_info(
            mt5.SYMBOL_FILLING_FOK,
            mt5.SYMBOL_TRADE_EXECUTION_MARKET,
            trade_mode=trade_mode,
            order_mode=order_mode,
        ),
        raising=False,
    )
    monkeypatch.setattr(mt5, "order_send", lambda order: submitted.append(order), raising=False)

    result = MT5Trader().open_position("US100.cash", 0.1, position_type, "test", 42)

    assert result is None
    assert submitted == []


def test_close_positions_only_closes_owned_magic_number(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trader = MT5Trader()
    positions = pd.DataFrame(
        [
            {
                "ticket": 17,
                "symbol": "US100.cash",
                "volume": 0.2,
                "type": mt5.ORDER_TYPE_BUY,
                "magic": 42,
            },
            {
                "ticket": 18,
                "symbol": "US100.cash",
                "volume": 0.3,
                "type": mt5.ORDER_TYPE_BUY,
                "magic": 99,
            },
        ]
    )
    submitted: list[dict[str, object]] = []
    monkeypatch.setattr(trader, "get_all_positions", lambda: positions)
    monkeypatch.setattr(
        mt5,
        "symbol_info",
        lambda _symbol: _symbol_info(mt5.SYMBOL_FILLING_FOK, mt5.SYMBOL_TRADE_EXECUTION_MARKET),
        raising=False,
    )
    monkeypatch.setattr(
        mt5,
        "symbol_info_tick",
        lambda _symbol: SimpleNamespace(bid=100.1, ask=100.2),
        raising=False,
    )
    monkeypatch.setattr(mt5, "order_send", lambda order: submitted.append(order), raising=False)

    trader.close_positions(
        "test", symbol="US100.cash", position_type=mt5.ORDER_TYPE_BUY, magic_number=42
    )

    assert len(submitted) == 1
    assert submitted[0]["position"] == 17
    assert submitted[0]["magic"] == 42


def test_close_positions_fails_closed_without_magic_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trader = MT5Trader()
    positions = pd.DataFrame(
        [{"ticket": 17, "symbol": "US100.cash", "volume": 0.2, "type": mt5.ORDER_TYPE_BUY}]
    )
    submitted: list[dict[str, object]] = []
    monkeypatch.setattr(trader, "get_all_positions", lambda: positions)
    monkeypatch.setattr(mt5, "order_send", lambda order: submitted.append(order), raising=False)

    with pytest.raises(ValueError, match="magic"):
        trader.close_positions(
            "test", symbol="US100.cash", position_type=mt5.ORDER_TYPE_BUY, magic_number=42
        )
    assert submitted == []


def test_get_opened_positions_filters_by_strategy_magic_number(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trader = MT5Trader()

    class Position(SimpleNamespace):
        def _asdict(self) -> dict[str, object]:
            return vars(self)

    monkeypatch.setattr(
        mt5,
        "positions_get",
        lambda: (
            Position(ticket=17, symbol="US100.cash", type=mt5.ORDER_TYPE_BUY, magic=42),
            Position(ticket=18, symbol="US100.cash", type=mt5.ORDER_TYPE_BUY, magic=99),
        ),
        raising=False,
    )

    count, positions = trader.get_opened_positions(
        "US100.cash", mt5.ORDER_TYPE_BUY, magic_number=42
    )

    assert count == 1
    assert positions["ticket"].tolist() == [17]


def test_get_opened_positions_does_not_turn_broker_failure_into_no_positions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trader = MT5Trader()
    monkeypatch.setattr(mt5, "positions_get", lambda: None, raising=False)
    monkeypatch.setattr(mt5, "last_error", lambda: (1, "terminal unavailable"), raising=False)

    with pytest.raises(RuntimeError, match="terminal unavailable"):
        trader.get_opened_positions("US100.cash", mt5.ORDER_TYPE_BUY, magic_number=42)
