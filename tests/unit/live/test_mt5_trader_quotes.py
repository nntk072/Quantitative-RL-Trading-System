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
    "TIMEFRAME_H1": 16385,
}.items():
    if not hasattr(mt5, _name):
        setattr(mt5, _name, _value)

from integrations.mt5.domain.trader import MT5Trader  # noqa: E402


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
