"""Hypothesis properties for the semantic oracle (SEMANTIC-ORACLE).

Each property is an invariant from the domain contract, not a re-run of the production
formula: cash and equity conservation, partition invariance of closes and of reward
telescoping, risk parity of sized lots, stop-fill direction, session and FTMO clock
invariance, and the strict-below breach rule. The expected side of each identity is
written out in the test. Tolerances match the ``tolerances`` table in the fixture file.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from market_data.loading.ticks import event_keyed_execution_rng
from market_data.transforms.sessions import ny_session_mask
from simulation.environment.rewards import EquityDeltaReward, EquityLogGrowthReward
from trading.account import AccountState
from trading.execution.broker import Broker
from trading.execution.costs import CostModel
from trading.execution.quotes import (
    adverse_tick_fill_quote,
    bar_stop_fill_quote,
    undo_adverse_tick_slippage_quote,
)
from trading.risk.ftmo_clock import ftmo_trading_day
from trading.risk.guardrails import FTMOGuardrails
from trading.risk.sizing import compute_lots, compute_lots_with_execution_reserve

PROPERTY_SETTINGS = settings(max_examples=200, deadline=None, database=None, derandomize=True)

price = st.floats(min_value=1.0, max_value=50_000.0, allow_nan=False, allow_infinity=False)
spread_price = st.floats(min_value=0.0, max_value=5.0, allow_nan=False, allow_infinity=False)
slip = st.floats(min_value=0.0, max_value=5.0, allow_nan=False, allow_infinity=False)


@st.composite
def bid_ask(draw: st.DrawFn) -> tuple[float, float]:
    bid = draw(price)
    ask = bid + draw(spread_price)
    return bid, ask


# --- quotes, fills and slippage --------------------------------------------------------


@PROPERTY_SETTINGS
@given(quote=bid_ask(), direction=st.sampled_from([1, -1]), slippage=slip, opening=st.booleans())
def test_adverse_slippage_never_improves_the_transacted_side(
    quote: tuple[float, float], direction: int, slippage: float, opening: bool
) -> None:
    bid, ask = quote
    worse_bid, worse_ask = adverse_tick_fill_quote(quote, direction, slippage, opening=opening)
    transacted_long_buy = (direction == 1) == opening
    if transacted_long_buy:
        assert worse_ask >= ask - 1e-12
        assert worse_bid == bid
    else:
        assert worse_bid <= bid + 1e-12
        assert worse_ask == ask


@PROPERTY_SETTINGS
@given(quote=bid_ask(), direction=st.sampled_from([1, -1]), slippage=slip, opening=st.booleans())
def test_undo_recovers_the_quote_before_adverse_slippage(
    quote: tuple[float, float], direction: int, slippage: float, opening: bool
) -> None:
    applied = adverse_tick_fill_quote(quote, direction, slippage, opening=opening)
    restored = undo_adverse_tick_slippage_quote(applied, direction, slippage, opening=opening)
    assert restored[0] == pytest.approx(quote[0], abs=1e-9)
    assert restored[1] == pytest.approx(quote[1], abs=1e-9)


@PROPERTY_SETTINGS
@given(bid_ask_pair=bid_ask(), direction=st.sampled_from([1, -1]), spread=spread_price)
def test_market_fill_lies_between_bid_and_ask(
    bid_ask_pair: tuple[float, float], direction: int, spread: float
) -> None:
    bid, ask = bid_ask_pair
    cost = CostModel(spread_points=spread, slippage_points=0.0)
    fill = cost.fill_price(bid, ask, direction)
    assert bid - 1e-12 <= fill <= ask + 1e-12
    assert fill == (ask if direction == 1 else bid)


@PROPERTY_SETTINGS
@given(
    stop=price,
    bar_open=price,
    direction=st.sampled_from([1, -1]),
    raw_spread=st.integers(min_value=0, max_value=500),
    slippage=slip,
)
def test_protective_stop_never_fills_better_than_its_level(
    stop: float, bar_open: float, direction: int, raw_spread: int, slippage: float
) -> None:
    """A stop fill is at the level or at a worse opening quote, never better."""
    cost = CostModel(spread_points=0.6, slippage_points=slippage, point_size=0.01)
    bid, ask = bar_stop_fill_quote(direction, stop, bar_open, float(raw_spread), cost)
    fill = bid if direction == 1 else ask
    if direction == 1:
        assert fill <= stop + 1e-9
    else:
        assert fill >= stop - 1e-9


# --- lot rounding and risk parity -------------------------------------------------------


@PROPERTY_SETTINGS
@given(
    budget=st.floats(min_value=1.0, max_value=5_000.0, allow_nan=False),
    stop_distance=st.floats(min_value=0.01, max_value=50.0, allow_nan=False),
    reserve=st.floats(min_value=0.0, max_value=20.0, allow_nan=False),
    lot_step=st.sampled_from([0.01, 0.1, 1.0]),
)
def test_sized_lots_fit_the_all_in_budget_and_sit_on_the_lot_grid(
    budget: float, stop_distance: float, reserve: float, lot_step: float
) -> None:
    """Risk parity: stop risk plus execution reserve on the returned lots never exceeds the budget."""
    entry = 100.0
    lots = compute_lots_with_execution_reserve(
        total_risk_budget_usd=budget,
        equity=1_000_000.0,
        risk_frac=0.5,
        entry_price=entry,
        sl_price=entry - stop_distance,
        contract_size=1.0,
        execution_reserve_per_lot=reserve,
        lot_step=lot_step,
    )
    if lots == 0.0:
        return
    all_in_per_lot = stop_distance + reserve
    assert lots * all_in_per_lot <= budget * (1.0 + 1e-12)
    steps = lots / lot_step
    assert abs(steps - round(steps)) <= 1e-6
    assert lots >= 0.01 - 1e-12


@PROPERTY_SETTINGS
@given(
    equity=st.floats(min_value=100.0, max_value=1e7, allow_nan=False),
    risk_frac=st.floats(min_value=0.0001, max_value=0.2, allow_nan=False),
    stop_distance=st.floats(min_value=0.0005, max_value=10.0, allow_nan=False),
)
def test_compute_lots_is_clipped_to_the_broker_range(
    equity: float, risk_frac: float, stop_distance: float
) -> None:
    lots = compute_lots(
        equity=equity,
        risk_frac=risk_frac,
        entry_price=100.0,
        sl_price=100.0 - stop_distance,
        contract_size=100.0,
        point_value=1.0,
    )
    assert 0.01 - 1e-12 <= lots <= 100.0 + 1e-12


# --- cash and equity conservation, partition invariance ----------------------------------


@st.composite
def partition_of(draw: st.DrawFn, total: float) -> list[float]:
    """Split ``total`` lots into pieces on a 0.01 grid, summing exactly to ``total``."""
    cents = round(total * 100)
    pieces = draw(st.integers(min_value=1, max_value=5))
    cuts = sorted(
        draw(
            st.lists(
                st.integers(min_value=0, max_value=cents), min_size=pieces - 1, max_size=pieces - 1
            )
        )
    )
    bounds = [0, *cuts, cents]
    return [(bounds[i + 1] - bounds[i]) / 100.0 for i in range(pieces) if bounds[i + 1] > bounds[i]]


@PROPERTY_SETTINGS
@given(
    commission=st.floats(min_value=0.0, max_value=5.0, allow_nan=False),
    lots=st.integers(min_value=1, max_value=200).map(lambda n: n / 100.0),
    entry_quote=bid_ask(),
    close_quote=bid_ask(),
    direction=st.sampled_from([1, -1]),
    data=st.data(),
)
def test_closing_in_any_partition_conserves_cash_and_equity(
    commission: float,
    lots: float,
    entry_quote: tuple[float, float],
    close_quote: tuple[float, float],
    direction: int,
    data: st.DataObject,
) -> None:
    """Balance and equity follow the explicit ledger identity for any partition of exits."""
    initial = 1_000_000.0
    acc = AccountState(initial_balance=initial)
    broker = Broker(
        contract_size=100.0, margin_pct=0.02, cost_model=CostModel(commission_per_lot=commission)
    )
    position = broker.open_position(acc, entry_quote, lots, direction)
    assert position is not None
    fill_entry = position.entry_price
    pieces = data.draw(partition_of(lots))
    closed = 0.0
    realised = 0.0
    for size in pieces:
        pnl, fill = broker.close_position(acc, position, close_quote, size=size)
        closed += size
        gross = (fill - fill_entry) * direction * size * 100.0
        assert pnl == pytest.approx(gross - commission * size, abs=1e-6)
        realised += pnl
        assert acc.balance == pytest.approx(initial - commission * lots + realised, abs=1e-6)
        if position.size > 0.0:
            unrealised = (
                ((close_quote[0] if direction == 1 else close_quote[1]) - fill_entry)
                * direction
                * position.size
                * 100.0
            )
            assert acc.open_pnl == pytest.approx(unrealised, abs=1e-6)
            assert acc.equity == pytest.approx(acc.balance + unrealised, abs=1e-6)
    assert closed == pytest.approx(lots, abs=1e-9)
    assert position.size == 0.0
    assert acc.equity == pytest.approx(acc.balance, abs=1e-6)


@PROPERTY_SETTINGS
@given(
    commission=st.floats(min_value=0.0, max_value=5.0, allow_nan=False),
    lots=st.integers(min_value=1, max_value=200).map(lambda n: n / 100.0),
    entry_quote=bid_ask(),
    close_quote=bid_ask(),
    direction=st.sampled_from([1, -1]),
    data=st.data(),
)
def test_partitioned_close_equals_single_close_for_the_same_quote(
    commission: float,
    lots: float,
    entry_quote: tuple[float, float],
    close_quote: tuple[float, float],
    direction: int,
    data: st.DataObject,
) -> None:
    """Partition invariance: pieces closed at one quote total the same as one close."""
    pieces = data.draw(partition_of(lots))

    def final_balance(sizes: list[float]) -> float:
        acc = AccountState(initial_balance=1_000_000.0)
        broker = Broker(
            contract_size=100.0,
            margin_pct=0.02,
            cost_model=CostModel(commission_per_lot=commission),
        )
        position = broker.open_position(acc, entry_quote, lots, direction)
        assert position is not None
        for size in sizes:
            broker.close_position(acc, position, close_quote, size=size)
        return acc.balance

    assert final_balance(pieces) == pytest.approx(final_balance([lots]), abs=1e-6)


@PROPERTY_SETTINGS
@given(
    equity=st.integers(min_value=0, max_value=20_000).map(float),
    balance_delta=st.integers(min_value=-3000, max_value=3000).map(float),
    anchor=st.integers(min_value=5_000, max_value=15_000).map(float),
)
def test_mark_to_market_changes_equity_and_never_balance(
    equity: float, balance_delta: float, anchor: float
) -> None:
    acc = AccountState(initial_balance=10_000.0)
    acc.balance = 10_000.0 + balance_delta
    before = acc.balance
    acc.update_equity(equity - acc.balance)
    assert acc.balance == before
    assert acc.equity == pytest.approx(equity, abs=1e-9)


# --- daily floor and breach rule -------------------------------------------------------


@PROPERTY_SETTINGS
@given(
    equity=st.integers(min_value=3_000, max_value=17_000).map(float),
    anchor=st.integers(min_value=5_000, max_value=15_000).map(float),
)
def test_daily_breach_is_exactly_equity_strictly_below_the_session_floor(
    equity: float, anchor: float
) -> None:
    """With integer USD values the strict-below rule is exact: breach iff equity < anchor - 500."""
    acc = AccountState(initial_balance=10_000.0)
    acc.equity = equity
    acc.session_start_equity = anchor
    guard = FTMOGuardrails(daily_loss_limit_pct=0.05, max_loss_limit_initial_pct=1.0)
    expected_breach = equity < anchor - 500.0
    assert guard.check_daily(acc) is expected_breach
    remaining = acc.remaining_daily_capacity(500.0)
    assert remaining >= 0.0
    assert remaining == max(0.0, equity - (anchor - 500.0))


# --- reward components -----------------------------------------------------------------


@PROPERTY_SETTINGS
@given(
    steps=st.lists(st.integers(min_value=1, max_value=1000).map(float), min_size=1, max_size=20),
    start=st.integers(min_value=1000, max_value=100_000).map(float),
)
def test_log_growth_rewards_telescope_to_the_single_transition(
    steps: list[float], start: float
) -> None:
    """Batch-vs-single: summed per-step log rewards equal one transition over the whole path."""
    reward = EquityLogGrowthReward(scale=100.0)
    path = [start]
    for delta in steps:
        path.append(path[-1] + delta)
    per_step = sum(
        reward(0.0, previous_equity=before, equity=after)
        for before, after in zip(path, path[1:], strict=False)
    )
    single = EquityLogGrowthReward(scale=100.0)(0.0, previous_equity=path[0], equity=path[-1])
    assert per_step == pytest.approx(single, abs=1e-9 * len(steps))
    assert per_step == pytest.approx(100.0 * math.log(path[-1] / path[0]), abs=1e-9 * len(steps))


@PROPERTY_SETTINGS
@given(
    pnls=st.lists(st.integers(min_value=-2000, max_value=2000).map(float), min_size=1, max_size=20),
    risk=st.integers(min_value=1, max_value=500).map(float),
)
def test_equity_delta_rewards_are_additive_over_partitions(pnls: list[float], risk: float) -> None:
    reward = EquityDeltaReward(fixed_risk_usd=risk)
    summed = sum(reward(p) for p in pnls)
    assert summed == pytest.approx(sum(pnls) / risk, abs=1e-12 * len(pnls))


# --- clocks and sessions ----------------------------------------------------------------


@PROPERTY_SETTINGS
@given(offset_minutes=st.integers(min_value=-(10**6), max_value=10**6))
def test_ftmo_day_depends_only_on_the_instant_not_the_source_zone(offset_minutes: int) -> None:
    instant = datetime(2026, 3, 28, 22, 0, tzinfo=UTC) + timedelta(minutes=offset_minutes)
    other_zones = [
        instant.astimezone(ZoneInfo("America/New_York")),
        instant.astimezone(ZoneInfo("Asia/Tokyo")),
        instant.astimezone(ZoneInfo("Etc/GMT-3")),
    ]
    expected = ftmo_trading_day(instant)
    assert all(ftmo_trading_day(value) == expected for value in other_zones)


@PROPERTY_SETTINGS
@given(
    minutes=st.lists(
        st.integers(min_value=0, max_value=60 * 24 * 3 - 1), min_size=2, max_size=60, unique=True
    ),
    split=st.integers(min_value=1, max_value=59),
    days=st.integers(min_value=-300, max_value=300),
)
def test_session_mask_is_per_bar_partition_invariant_and_date_shift_invariant(
    minutes: list[int], split: int, days: int
) -> None:
    base = pd.Timestamp("2025-01-06 00:00") + pd.to_timedelta(sorted(minutes), unit="min")
    index = pd.DatetimeIndex(base)
    whole = ny_session_mask(index).to_numpy()
    cut = min(split, len(index) - 1)
    left = ny_session_mask(index[:cut]).to_numpy()
    right = ny_session_mask(index[cut:]).to_numpy()
    assert np.array_equal(whole, np.concatenate([left, right]))
    shifted = ny_session_mask(index + pd.Timedelta(days=days)).to_numpy()
    assert np.array_equal(whole, shifted)


@PROPERTY_SETTINGS
@given(
    seed=st.integers(min_value=0, max_value=2**31),
    first=st.text(min_size=1, max_size=8),
    second=st.text(min_size=1, max_size=8),
)
def test_event_keyed_stream_is_independent_of_other_keys_drawn_first(
    seed: int, first: str, second: str
) -> None:
    assume(first != second)
    alone = event_keyed_execution_rng(seed, second).random(4)
    _ = event_keyed_execution_rng(seed, first).random(10)
    after_other = event_keyed_execution_rng(seed, second).random(4)
    assert np.array_equal(alone, after_other)
