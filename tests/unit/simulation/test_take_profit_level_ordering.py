from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from market_data.loading.ticks import TickBook
from simulation.environment.market_view import BarView
from tests.unit.simulation.test_environment._tp_mode_fixtures import _make_tp_env


def test_tick_at_first_target_equality_fills_only_first_ordered_slot() -> None:
    empty_book = TickBook(np.asarray([], dtype=np.int64), np.asarray([]), np.asarray([]))
    env = _make_tp_env(tickbook=empty_book)
    env.reset(seed=42)
    pos = env.broker.open_position(env.account, (100.0, 100.0), 1.0, 1)
    assert pos is not None
    pos.position_id = "tp-equality"
    pos.entry_timestamp = env._bar_time(env.step_idx) - pd.Timedelta(minutes=1)
    pos.sl_price = 99.0
    pos.tp_initial_size = 1.0
    pos.tp_lot_fractions = (0.3, 0.3, 0.4)
    pos.tp1_price = 101.0
    pos.tp2_price = 102.0
    pos.tp3_price = 103.0
    pos.tp_price = pos.tp1_price
    env.position = pos

    bar_time = pd.Timestamp(env._bar_time(env.step_idx))
    env._tickbook = TickBook(
        np.asarray([bar_time.value], dtype=np.int64),
        np.asarray([101.0]),
        np.asarray([101.6]),
    )
    balance_before = env.account.balance

    env._check_sl_tp(
        BarView(open=100.0, high=101.0, low=99.5, close=100.5, spread=0.0),
        fill_bid=100.5,
        fill_ask=100.5,
    )

    fills = [row for row in env.trade_log if row.get("tp_slot") is not None]
    assert len(fills) == 1
    assert fills[0]["type"] == "tp_partial_close"
    assert fills[0]["tp_slot"] == 1
    assert fills[0]["price"] == 101.0
    assert fills[0]["size"] == pytest.approx(0.3)
    assert fills[0]["pnl"] > 0.0
    assert pos.tp_hit_mask == 1
    assert pos.tp1_price is None
    assert (pos.tp2_price, pos.tp3_price) == (102.0, 103.0)
    assert pos.size == 0.7
    assert env.account.balance == balance_before + fills[0]["pnl"]
