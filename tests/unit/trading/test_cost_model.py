"""Tests: cost model + broker bid/ask correctness."""

from __future__ import annotations

import pytest

from trading.account.account_state import AccountState
from trading.execution.broker import Broker
from trading.execution.costs import CostModel


def test_broker_constructs_default_cost_model() -> None:
    broker = Broker()

    assert isinstance(broker.cost_model, CostModel)


@pytest.mark.parametrize("point_value", [True, 0.0, -1.0, float("inf"), float("nan")])
def test_cost_model_rejects_invalid_point_value(point_value: float) -> None:
    with pytest.raises(ValueError, match="point_value must be finite and positive"):
        CostModel(point_value=point_value)


@pytest.mark.parametrize("contract_size", [True, 0.0, -1.0, float("inf"), float("nan")])
def test_broker_rejects_invalid_contract_size(contract_size: float) -> None:
    with pytest.raises(ValueError, match="contract_size must be finite and positive"):
        Broker(contract_size=contract_size)


def test_fill_price_buy_is_ask():
    c = CostModel(spread_points=1.0, slippage_points=0.0)
    fill = c.fill_price(bid=99.5, ask=100.5, direction=1)
    assert fill == pytest.approx(100.5)


def test_fill_price_sell_is_bid():
    c = CostModel(spread_points=1.0, slippage_points=0.0)
    fill = c.fill_price(bid=99.5, ask=100.5, direction=-1)
    assert fill == pytest.approx(99.5)


def test_total_cost_is_commission_only():
    c = CostModel(spread_points=0.6, commission_per_lot=3.0)
    assert c.total_cost(lots=2.0) == pytest.approx(6.0)


def test_bar_quote_derives_ask_from_close():
    c = CostModel(spread_points=0.6, point_size=0.01)
    bid, ask = c.bar_quote(close=20000.0)
    assert bid == pytest.approx(20000.0)
    assert ask == pytest.approx(20000.6)


def test_long_opens_at_ask_closes_at_bid():
    cm = CostModel(spread_points=1.0, slippage_points=0.0, commission_per_lot=0.0)
    broker = Broker(cost_model=cm, margin_pct=0.02)
    acc = AccountState(initial_balance=100_000.0)

    pos = broker.open_position(acc, quote=(99.5, 100.5), lots=1.0, direction=1)
    assert pos is not None
    assert pos.entry_price == pytest.approx(100.5)

    pnl, fill_price = broker.close_position(acc, pos, quote=(99.5, 100.5))
    assert pnl == pytest.approx(-1.0)
    assert fill_price == pytest.approx(99.5)


def test_round_trip_spread_charged_once():
    cm = CostModel(spread_points=1.0, slippage_points=0.0, commission_per_lot=0.0)
    broker = Broker(cost_model=cm, margin_pct=0.02)
    acc = AccountState(initial_balance=100_000.0)

    quote = (100.0, 101.0)
    pos = broker.open_position(acc, quote=quote, lots=1.0, direction=1)
    assert pos is not None
    pnl, fill_price = broker.close_position(acc, pos, quote=quote)
    assert pnl == pytest.approx(-1.0)
    assert fill_price == pytest.approx(100.0)


def test_round_trip_commission_deducted():
    cm = CostModel(spread_points=0.0, slippage_points=0.0, commission_per_lot=2.5)
    broker = Broker(cost_model=cm, margin_pct=0.02)
    acc = AccountState(initial_balance=100_000.0)

    quote = (100.0, 100.0)
    pos = broker.open_position(acc, quote=quote, lots=2.0, direction=1)
    assert pos is not None

    pnl, fill_price = broker.close_position(acc, pos, quote=quote)

    total_cost = 100_000.0 - acc.balance
    assert total_cost == pytest.approx(10.0)
    assert fill_price == pytest.approx(100.0)


@pytest.mark.parametrize(
    ("direction", "entry_quote", "exit_quote", "expected_pnl"),
    [
        (1, (100.0, 100.0), (104.0, 104.0), 12.0),
        (-1, (104.0, 104.0), (100.0, 100.0), 12.0),
    ],
)
def test_realized_pnl_uses_account_currency_point_value(
    direction: int,
    entry_quote: tuple[float, float],
    exit_quote: tuple[float, float],
    expected_pnl: float,
) -> None:
    broker = Broker(
        cost_model=CostModel(point_value=2.0, commission_per_lot=0.0),
        contract_size=3.0,
    )
    account = AccountState(initial_balance=1000.0)
    position = broker.open_position(account, entry_quote, lots=0.5, direction=direction)
    assert position is not None

    pnl, _ = broker.close_position(account, position, exit_quote)

    assert pnl == pytest.approx(expected_pnl)
    assert account.balance == pytest.approx(1000.0 + expected_pnl)


@pytest.mark.parametrize(
    ("direction", "entry", "quote", "expected"),
    [
        (1, 100.0, (103.0, 103.0), 9.0),
        (-1, 103.0, (100.0, 100.0), 9.0),
    ],
)
def test_mark_to_market_uses_account_currency_point_value(
    direction: int,
    entry: float,
    quote: tuple[float, float],
    expected: float,
) -> None:
    broker = Broker(cost_model=CostModel(point_value=2.0), contract_size=3.0)
    account = AccountState(initial_balance=1000.0)
    position = broker.open_position(account, (entry, entry), lots=0.5, direction=direction)
    assert position is not None

    unrealized = broker.mark_to_market(account, position, quote)

    assert unrealized == pytest.approx(expected)
    assert account.equity == pytest.approx(1000.0 + expected)
