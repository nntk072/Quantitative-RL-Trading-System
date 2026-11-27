"""Pure broker metadata checks do not require a connected MT5 terminal."""

from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from typing import Any, cast

import pytest

if "MetaTrader5" not in sys.modules:
    try:
        import MetaTrader5  # noqa: F401
    except ImportError:
        sys.modules["MetaTrader5"] = ModuleType("MetaTrader5")

mt5 = cast(Any, sys.modules["MetaTrader5"])
for name, value in {
    "SYMBOL_TRADE_EXECUTION_REQUEST": 0,
    "SYMBOL_TRADE_EXECUTION_INSTANT": 1,
    "SYMBOL_TRADE_EXECUTION_MARKET": 2,
    "SYMBOL_TRADE_EXECUTION_EXCHANGE": 3,
    "ORDER_FILLING_FOK": 0,
    "ORDER_FILLING_IOC": 1,
    "ORDER_FILLING_RETURN": 2,
    "SYMBOL_FILLING_FOK": 1,
    "SYMBOL_FILLING_IOC": 2,
    "SYMBOL_ORDER_MARKET": 1,
    "SYMBOL_ORDER_SL": 2,
    "SYMBOL_ORDER_TP": 4,
    "SYMBOL_TRADE_MODE_DISABLED": 0,
    "SYMBOL_TRADE_MODE_CLOSEONLY": 1,
    "SYMBOL_TRADE_MODE_LONGONLY": 2,
    "SYMBOL_TRADE_MODE_SHORTONLY": 3,
    "SYMBOL_TRADE_MODE_FULL": 4,
    "ORDER_TYPE_BUY": 0,
    "ORDER_TYPE_SELL": 1,
}.items():
    if not hasattr(mt5, name):
        setattr(mt5, name, value)

from integrations.mt5.domain.symbol_rules import (  # noqa: E402
    filling_type,
    symbol_allows_open,
    volume_matches_symbol,
)


@pytest.mark.parametrize("volume", [0.1, 0.2, 0.3, 1.0])
def test_volume_matches_min_max_and_decimal_step(volume: float) -> None:
    info = SimpleNamespace(volume_min=0.1, volume_max=1.0, volume_step=0.1)
    assert volume_matches_symbol(info, volume)


@pytest.mark.parametrize(
    ("info", "volume"),
    [
        (SimpleNamespace(volume_min=True, volume_max=1.0, volume_step=0.1), 0.2),
        (SimpleNamespace(volume_min=0.1, volume_max=1.0, volume_step=0.0), 0.2),
        (SimpleNamespace(volume_min=0.1, volume_max=1.0, volume_step=0.1), 0.25),
        (SimpleNamespace(volume_min=0.1, volume_max=1.0, volume_step=0.1), float("inf")),
    ],
)
def test_volume_rejects_invalid_constraints_and_off_step_values(
    info: SimpleNamespace, volume: float
) -> None:
    assert not volume_matches_symbol(info, volume)


@pytest.mark.parametrize("value", ["not-a-number", object()])
def test_volume_and_filling_rules_reject_non_numeric_broker_values(value: object) -> None:
    info = SimpleNamespace(volume_min=value, volume_max=1.0, volume_step=0.1)
    assert not volume_matches_symbol(info, 0.2)
    assert filling_type(SimpleNamespace(filling_mode=value, trade_exemode=2)) is None
    assert not symbol_allows_open(
        SimpleNamespace(trade_mode=value, order_mode=7), mt5.ORDER_TYPE_BUY, sl=None, tp=None
    )


@pytest.mark.parametrize(
    ("mode", "flags", "expected"),
    [
        (mt5.SYMBOL_TRADE_EXECUTION_REQUEST, 0, mt5.ORDER_FILLING_FOK),
        (mt5.SYMBOL_TRADE_EXECUTION_INSTANT, 0, mt5.ORDER_FILLING_FOK),
        (mt5.SYMBOL_TRADE_EXECUTION_MARKET, mt5.SYMBOL_FILLING_FOK, mt5.ORDER_FILLING_FOK),
        (mt5.SYMBOL_TRADE_EXECUTION_MARKET, mt5.SYMBOL_FILLING_IOC, mt5.ORDER_FILLING_IOC),
        (mt5.SYMBOL_TRADE_EXECUTION_MARKET, 0, None),
        (mt5.SYMBOL_TRADE_EXECUTION_EXCHANGE, 0, mt5.ORDER_FILLING_RETURN),
    ],
)
def test_filling_policy_respects_execution_mode_and_supported_flags(
    mode: int, flags: int, expected: int | None
) -> None:
    assert filling_type(SimpleNamespace(filling_mode=flags, trade_exemode=mode)) == expected


@pytest.mark.parametrize(
    ("flags", "mode"),
    [(True, mt5.SYMBOL_TRADE_EXECUTION_MARKET), (float("nan"), 2), (-1, 2), (0, 99)],
)
def test_filling_policy_fails_closed_on_invalid_or_unsupported_metadata(
    flags: float | bool, mode: int
) -> None:
    assert filling_type(SimpleNamespace(filling_mode=flags, trade_exemode=mode)) is None


@pytest.mark.parametrize(
    ("trade_mode", "order_mode", "order_type", "sl", "tp", "expected"),
    [
        (
            mt5.SYMBOL_TRADE_MODE_FULL,
            mt5.SYMBOL_ORDER_MARKET | mt5.SYMBOL_ORDER_SL | mt5.SYMBOL_ORDER_TP,
            mt5.ORDER_TYPE_BUY,
            95.0,
            110.0,
            True,
        ),
        (
            mt5.SYMBOL_TRADE_MODE_LONGONLY,
            mt5.SYMBOL_ORDER_MARKET | mt5.SYMBOL_ORDER_SL,
            mt5.ORDER_TYPE_BUY,
            95.0,
            None,
            True,
        ),
        (
            mt5.SYMBOL_TRADE_MODE_SHORTONLY,
            mt5.SYMBOL_ORDER_MARKET | mt5.SYMBOL_ORDER_TP,
            mt5.ORDER_TYPE_SELL,
            None,
            110.0,
            True,
        ),
        (mt5.SYMBOL_TRADE_MODE_DISABLED, 7, mt5.ORDER_TYPE_BUY, None, None, False),
        (mt5.SYMBOL_TRADE_MODE_FULL, 1, mt5.ORDER_TYPE_BUY, 95.0, None, False),
        (mt5.SYMBOL_TRADE_MODE_FULL, 7, 8, None, None, False),
        (True, 7, mt5.ORDER_TYPE_BUY, None, None, False),
    ],
)
def test_symbol_entry_checks_market_stop_target_and_direction_permissions(
    trade_mode: int,
    order_mode: int,
    order_type: int,
    sl: float | None,
    tp: float | None,
    expected: bool,
) -> None:
    info = SimpleNamespace(trade_mode=trade_mode, order_mode=order_mode)
    assert symbol_allows_open(info, order_type, sl=sl, tp=tp) is expected
