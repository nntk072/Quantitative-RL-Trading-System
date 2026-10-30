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
        [{"ticket": 17, "symbol": "US100.cash", "volume": 0.2, "type": position_type}]
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

    trader.close_positions("test", symbol="US100.cash", position_type=position_type)

    assert len(submitted) == 1
    assert submitted[0]["type"] == expected_order_type
    assert submitted[0]["price"] == expected_price
