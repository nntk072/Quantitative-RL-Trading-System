from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from market_data.loading.ticks import TickBook
from simulation.environment.env import TradingEnv
from simulation.environment.market_view import BarView
from tests.unit.simulation.test_environment._account_fixtures import (
    _make_bars,
    _make_features,
)
from trading.execution import Position


def _empty_tickbook() -> TickBook:
    return TickBook(np.asarray([], dtype=np.int64), np.asarray([]), np.asarray([]))


def test_tick_only_protection_keeps_position_open_for_pre_entry_excursion() -> None:
    bars = _make_bars(120)
    env = TradingEnv(bars=bars, features=_make_features(bars), obs_window=10)
    env.reset(seed=3)
    env.step_idx = 50
    env.tick_execution_required = True
    bar_time = env._bar_time(env.step_idx)
    bar = env._bar_at(env.step_idx)
    env.position = Position(
        direction=-1,
        size=0.1,
        entry_price=bar.close,
        margin_used=1.0,
        sl_price=bar.high + env.cost_model.spread_points / 2.0,
        entry_timestamp=bar_time + pd.Timedelta(seconds=10),
    )

    env._check_sl_tp(bar, bar.close, bar.close, env.step_idx)
    assert env.position is not None
    assert not any(row.get("type") == "stop_close" for row in env.trade_log)


def test_untriggered_stop_uses_level_when_nearest_tick_would_make_exit_better() -> None:
    bars = _make_bars(120)
    env = TradingEnv(
        bars=bars,
        features=_make_features(bars),
        obs_window=10,
        tickbook=_empty_tickbook(),
        tick_execution_required=True,
        max_tick_quote_wait_ms=1_000,
    )
    env.reset(seed=5)
    bar_time = env._bar_time(env.step_idx)
    env._tickbook = TickBook(
        np.asarray([(bar_time + pd.Timedelta(milliseconds=100)).value], dtype=np.int64),
        np.asarray([99.5]),
        np.asarray([99.6]),
    )
    position = env.broker.open_position(env.account, (100.0, 100.0), 1.0, 1)
    assert position is not None
    position.entry_price = 100.0
    position.sl_price = 99.0
    position.tp_price = 101.0
    env.position = position

    # Both levels are inside the OHLC range, but the nearby tick has not crossed
    # the long stop. Using it as a stop fill would improve the exit above the
    # protective level, so the level price must remain authoritative.
    env._check_sl_tp(
        BarView(open=100.0, high=102.0, low=98.0, close=101.0, spread=0.0),
        fill_bid=102.0,
        fill_ask=102.0,
        bar_idx=env.step_idx,
    )

    closes = [event for event in env.trade_log if event.get("type") == "stop_close"]
    assert env.position is None
    assert len(closes) == 1
    assert closes[0]["price"] <= 99.0
    assert closes[0]["pnl"] < 0.0


def test_untriggered_level_uses_a_valid_adverse_tick_quote() -> None:
    bars = _make_bars(120)
    env = TradingEnv(
        bars=bars,
        features=_make_features(bars),
        obs_window=10,
        tickbook=_empty_tickbook(),
        tick_execution_required=True,
    )
    env.reset(seed=7)
    bar_time = env._bar_time(env.step_idx)
    env._tickbook = TickBook(
        np.asarray([(bar_time + pd.Timedelta(milliseconds=100)).value], dtype=np.int64),
        np.asarray([98.5]),
        np.asarray([98.6]),
    )

    quote = env._untriggered_level_quote(bar_time, direction=1, level=99.0)

    assert quote == (98.5, 98.6)


def test_untriggered_level_falls_back_when_tick_quote_is_malformed() -> None:
    bars = _make_bars(120)
    env = TradingEnv(
        bars=bars,
        features=_make_features(bars),
        obs_window=10,
        tickbook=_empty_tickbook(),
        tick_execution_required=True,
    )
    env.reset(seed=8)
    bar_time = env._bar_time(env.step_idx)
    env._tickbook = TickBook(
        np.asarray([(bar_time + pd.Timedelta(milliseconds=100)).value], dtype=np.int64),
        np.asarray([np.nan]),
        np.asarray([np.nan]),
    )

    quote = env._untriggered_level_quote(bar_time, direction=1, level=99.0)

    assert quote == env._sl_tp_fill_quote(direction=1, hit_price=99.0)


def test_one_ulp_adverse_tick_remains_a_valid_stop_quote() -> None:
    bars = _make_bars(120)
    env = TradingEnv(
        bars=bars,
        features=_make_features(bars),
        obs_window=10,
        tickbook=_empty_tickbook(),
        tick_execution_required=True,
    )
    env.reset(seed=9)
    bar_time = env._bar_time(env.step_idx)
    bid = np.nextafter(99.0, -np.inf)
    ask = float(np.nextafter(bid, np.inf))
    env._tickbook = TickBook(
        np.asarray([(bar_time + pd.Timedelta(milliseconds=100)).value], dtype=np.int64),
        np.asarray([bid]),
        np.asarray([ask]),
    )

    quote = env._untriggered_level_quote(bar_time, direction=1, level=99.0)

    assert quote == (bid, ask)


def test_stop_falls_back_to_gap_open_when_tick_quote_is_too_far_away() -> None:
    bars = _make_bars(120)
    env = TradingEnv(
        bars=bars,
        features=_make_features(bars),
        obs_window=10,
        tickbook=_empty_tickbook(),
        tick_execution_required=True,
        max_tick_quote_wait_ms=1,
    )
    env.reset(seed=10)
    bar_time = env._bar_time(env.step_idx)
    env._tickbook = TickBook(
        np.asarray([(bar_time + pd.Timedelta(minutes=2)).value], dtype=np.int64),
        np.asarray([98.0]),
        np.asarray([98.1]),
    )
    position = env.broker.open_position(env.account, (100.0, 100.0), 1.0, 1)
    assert position is not None
    position.entry_price = 100.0
    position.sl_price = 99.0
    position.tp_price = 110.0
    env.position = position

    env._check_sl_tp(
        BarView(open=98.0, high=100.0, low=97.0, close=98.0, spread=0.0),
        fill_bid=98.0,
        fill_ask=98.0,
        bar_idx=env.step_idx,
    )

    closes = [event for event in env.trade_log if event.get("type") == "stop_close"]
    assert env.position is None
    assert len(closes) == 1
    assert closes[0]["price"] <= 98.0


def test_tick_replay_closes_partial_target_then_stop_without_bar_reprocessing() -> None:
    bars = _make_bars(120)
    env = TradingEnv(
        bars=bars,
        features=_make_features(bars),
        obs_window=10,
        tickbook=_empty_tickbook(),
        tick_execution_required=True,
    )
    env.reset(seed=11)
    bar_time = env._bar_time(env.step_idx)
    tick_times = [bar_time + pd.Timedelta(seconds=offset) for offset in (5, 20)]
    env._tickbook = TickBook(
        np.asarray([tick.value for tick in tick_times], dtype=np.int64),
        np.asarray([106.0, 94.0]),
        np.asarray([106.5, 94.5]),
    )
    position = env.broker.open_position(env.account, (100.0, 100.0), 1.0, 1)
    assert position is not None
    position.position_id = "runtime-replay-partial-stop"
    position.entry_price = 100.0
    position.entry_timestamp = bar_time
    position.sl_price = 95.0
    position.tp1_price = 105.0
    position.tp2_price = 110.0
    position.tp_initial_size = 1.0
    position.tp_lot_fractions = (0.3, 0.7)
    env.position = position

    env._check_sl_tp(
        BarView(open=100.0, high=111.0, low=90.0, close=100.0, spread=0.0),
        fill_bid=100.0,
        fill_ask=100.0,
        bar_idx=env.step_idx,
    )

    exits = [event for event in env.trade_log if event.get("type") != "open"]
    assert env.position is None
    assert [event["type"] for event in exits] == ["tp_partial_close", "stop_close"]
    assert [event["size"] for event in exits] == pytest.approx([0.3, 0.7])
    assert [event["time"] for event in exits] == tick_times
    assert all(event["fill_quote_source"] == "tick" for event in exits)
    assert env._last_multi_target_replay["after"] is None


def test_bar_touch_closes_multiple_target_slots_in_order() -> None:
    bars = _make_bars(120)
    env = TradingEnv(bars=bars, features=_make_features(bars), obs_window=10)
    env.reset(seed=12)
    position = env.broker.open_position(env.account, (100.0, 100.0), 1.0, 1)
    assert position is not None
    position.position_id = "runtime-bar-multiple-targets"
    position.entry_price = 100.0
    position.sl_price = 95.0
    position.tp1_price = 101.0
    position.tp2_price = 102.0
    position.tp_initial_size = 1.0
    position.tp_lot_fractions = (0.4, 0.6)
    env.position = position

    env._check_sl_tp(
        BarView(open=100.0, high=103.0, low=99.0, close=102.0, spread=0.0),
        fill_bid=102.0,
        fill_ask=102.0,
        bar_idx=env.step_idx,
    )

    exits = [event for event in env.trade_log if event.get("type", "").startswith("tp_")]
    assert env.position is None
    assert [event["type"] for event in exits] == ["tp_partial_close", "tp_close"]
    assert [event["tp_slot"] for event in exits] == [1, 2]
    assert [event["size"] for event in exits] == pytest.approx([0.4, 0.6])
