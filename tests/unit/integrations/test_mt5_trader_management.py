"""MT5 position management maps broker state into safe order requests."""

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
for _name, _value in {
    "TIMEFRAME_H1": 16385,
    "TRADE_ACTION_DEAL": 1,
    "TRADE_ACTION_SLTP": 6,
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
    "SYMBOL_ORDER_SL": 2,
    "SYMBOL_ORDER_TP": 4,
    "TRADE_RETCODE_DONE": 10009,
}.items():
    if not hasattr(mt5, _name):
        setattr(mt5, _name, _value)

from integrations.mt5.domain.trader import MT5Trader  # noqa: E402


@pytest.mark.parametrize(
    ("position_type", "current_price", "expected_close_type"),
    [
        (mt5.ORDER_TYPE_BUY, 108.0, mt5.ORDER_TYPE_SELL),
        (mt5.ORDER_TYPE_SELL, 94.0, mt5.ORDER_TYPE_BUY),
    ],
)
def test_send_to_break_even_modifies_stop_only_after_profit_threshold(
    monkeypatch: pytest.MonkeyPatch,
    position_type: int,
    current_price: float,
    expected_close_type: int,
) -> None:
    submitted: list[dict[str, object]] = []
    positions = pd.DataFrame(
        [
            {
                "ticket": 17,
                "symbol": "US100",
                "price_open": 100.0,
                "tp": 110.0 if position_type == mt5.ORDER_TYPE_BUY else 90.0,
                "type": position_type,
                "price_current": current_price,
            }
        ]
    )
    monkeypatch.setattr(mt5, "order_send", lambda order: submitted.append(order), raising=False)

    MT5Trader().send_to_break_even(positions, percentage=0.5)

    assert len(submitted) == 1
    assert submitted[0] == {
        "action": mt5.TRADE_ACTION_SLTP,
        "symbol": "US100",
        "position": 17,
        "type": expected_close_type,
        "sl": 100.0,
        "tp": positions["tp"].iloc[0],
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }


def test_calculate_position_size_converts_stop_distance_to_lots(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, object]] = []

    def select_symbol(symbol: str, enabled: bool) -> bool:
        calls.append(("select", (symbol, enabled)))
        return True

    def symbol_tick(symbol: str) -> SimpleNamespace:
        calls.append(("tick", symbol))
        return SimpleNamespace(bid=99.9, ask=100.1)

    def symbol_info(symbol: str) -> SimpleNamespace:
        calls.append(("info", symbol))
        return SimpleNamespace(trade_tick_size=0.1, trade_tick_value=2.0)

    monkeypatch.setattr(
        mt5,
        "symbol_select",
        select_symbol,
        raising=False,
    )
    monkeypatch.setattr(mt5, "symbol_info_tick", symbol_tick, raising=False)
    monkeypatch.setattr(mt5, "symbol_info", symbol_info, raising=False)
    monkeypatch.setattr(
        mt5,
        "account_info",
        lambda: SimpleNamespace(balance=10_000.0),
        raising=False,
    )

    lots = MT5Trader().calculate_position_size("US100", stop_loss=98.0, per_to_risk=0.01)

    assert lots == pytest.approx(2.5)
    assert calls == [
        ("select", ("US100", True)),
        ("tick", "US100"),
        ("info", "US100"),
    ]


def _symbol_info() -> SimpleNamespace:
    return SimpleNamespace(
        filling_mode=mt5.SYMBOL_FILLING_FOK,
        trade_exemode=mt5.SYMBOL_TRADE_EXECUTION_MARKET,
        trade_mode=mt5.SYMBOL_TRADE_MODE_FULL,
        order_mode=mt5.SYMBOL_ORDER_MARKET | mt5.SYMBOL_ORDER_SL | mt5.SYMBOL_ORDER_TP,
        volume_min=0.01,
        volume_max=10.0,
        volume_step=0.01,
    )


def test_open_position_returns_none_when_terminal_disables_autotrading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[dict[str, object]] = []
    monkeypatch.setattr(mt5, "symbol_info", lambda _symbol: _symbol_info(), raising=False)

    def send_order(request: dict[str, object]) -> SimpleNamespace:
        requests.append(request)
        return SimpleNamespace(retcode=10027)

    monkeypatch.setattr(
        mt5,
        "order_send",
        send_order,
        raising=False,
    )

    result = MT5Trader().open_position("US100", 0.1, mt5.ORDER_TYPE_BUY, "test", 42, 99.0, 102.0)

    assert result is None
    assert len(requests) == 1
    assert requests[0]["sl"] == 99.0
    assert requests[0]["tp"] == 102.0


def test_close_position_skips_request_when_quote_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trader = MT5Trader()
    positions = pd.DataFrame(
        [{"ticket": 17, "symbol": "US100", "volume": 0.1, "type": mt5.ORDER_TYPE_BUY, "magic": 42}]
    )
    requests: list[dict[str, object]] = []
    monkeypatch.setattr(trader, "get_all_positions", lambda: positions)
    monkeypatch.setattr(mt5, "symbol_info", lambda _symbol: _symbol_info(), raising=False)
    monkeypatch.setattr(mt5, "symbol_info_tick", lambda _symbol: None, raising=False)
    monkeypatch.setattr(mt5, "order_send", lambda request: requests.append(request), raising=False)

    trader.close_positions("test", symbol="US100", magic_number=42)

    assert requests == []


@pytest.mark.parametrize("metadata", [None, "unsupported_fill"])
def test_close_position_skips_request_when_symbol_metadata_is_unusable(
    monkeypatch: pytest.MonkeyPatch, metadata: object | None
) -> None:
    trader = MT5Trader()
    positions = pd.DataFrame(
        [{"ticket": 17, "symbol": "US100", "volume": 0.1, "type": mt5.ORDER_TYPE_BUY, "magic": 42}]
    )
    requests: list[dict[str, object]] = []
    info = _symbol_info()
    if metadata == "unsupported_fill":
        info.filling_mode = 0
    monkeypatch.setattr(trader, "get_all_positions", lambda: positions)
    monkeypatch.setattr(
        mt5,
        "symbol_info",
        lambda _symbol: None if metadata is None else info,
        raising=False,
    )
    monkeypatch.setattr(
        mt5,
        "symbol_info_tick",
        lambda _symbol: SimpleNamespace(bid=99.9, ask=100.1),
        raising=False,
    )
    monkeypatch.setattr(mt5, "order_send", lambda request: requests.append(request), raising=False)

    trader.close_positions("test", symbol="US100", magic_number=42)

    assert requests == []


def test_close_position_handles_missing_broker_result_after_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trader = MT5Trader()
    positions = pd.DataFrame(
        [{"ticket": 17, "symbol": "US100", "volume": 0.1, "type": mt5.ORDER_TYPE_BUY, "magic": 42}]
    )
    requests: list[dict[str, object]] = []
    monkeypatch.setattr(trader, "get_all_positions", lambda: positions)
    monkeypatch.setattr(mt5, "symbol_info", lambda _symbol: _symbol_info(), raising=False)
    monkeypatch.setattr(
        mt5,
        "symbol_info_tick",
        lambda _symbol: SimpleNamespace(bid=99.9, ask=100.1),
        raising=False,
    )

    def send_order(request: dict[str, object]) -> None:
        requests.append(request)

    monkeypatch.setattr(mt5, "order_send", send_order, raising=False)

    trader.close_positions("test", symbol="US100", magic_number=42)

    assert len(requests) == 1
    assert requests[0]["position"] == 17


@pytest.mark.parametrize("broker_positions", [None, []])
def test_get_all_positions_returns_empty_frame_for_missing_or_empty_snapshot(
    monkeypatch: pytest.MonkeyPatch, broker_positions: object
) -> None:
    monkeypatch.setattr(mt5, "positions_get", lambda: broker_positions, raising=False)

    positions = MT5Trader().get_all_positions()

    assert positions.empty
    assert list(positions.columns) == []


def test_get_all_positions_returns_empty_frame_when_snapshot_query_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_query_error() -> None:
        raise RuntimeError("terminal disconnected")

    monkeypatch.setattr(mt5, "positions_get", raise_query_error, raising=False)

    positions = MT5Trader().get_all_positions()

    assert positions.empty
    assert list(positions.columns) == []
