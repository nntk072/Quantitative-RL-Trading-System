from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from decisioning.trade_setup import (
    build_trade_setup_action_schema,
    trade_setup_candidate_id,
    trade_setup_center,
)
from features.context.trade_setup_candidates import trade_setup_candidate_feature_columns
from market_data.loading.ticks import TickBook
from simulation.backtest import run_backtest
from simulation.environment.env import TradingEnv
from trading.execution import CostModel
from trading.strategies.baseline import BaselineStrategy


class _SwingGeometryStrategy(BaselineStrategy):
    name = "market_fill_event_test"

    def sl_candidates(self, *, direction: int, row: pd.Series) -> list[tuple[str, float]]:
        column = "last_swing_low" if direction == 1 else "last_swing_high"
        return [(column, float(row[column]))]


def _market_action(schema: Any, candidate_id: int) -> np.ndarray[Any, Any]:
    action = np.zeros(schema.width, dtype=np.float32)
    action[schema.indices["trade_setup"]] = trade_setup_center(candidate_id)
    action[schema.indices["entry_execution"]] = -1.0
    action[schema.indices["stop"]] = -0.4
    action[schema.indices["target"]] = 0.8
    action[schema.indices["exit"]] = -1.0
    return action


def test_accepted_market_entry_emits_equivalent_fill_event_in_both_engines() -> None:
    index = pd.date_range("2025-01-06 14:30", periods=7, freq="1min", tz="UTC")
    close = np.full(len(index), 20_000.0)
    bars = pd.DataFrame(
        {
            "open": close,
            "high": close + 2.0,
            "low": close - 2.0,
            "close": close,
            "spread": 0.0,
            "session_id": 0,
            "session": "ny",
        },
        index=index,
    )
    features = pd.DataFrame(
        0.0,
        index=index,
        columns=[name for _, name in trade_setup_candidate_feature_columns()],
    )
    features["atr_5"] = 1.0
    features["last_swing_low"] = 19_990.0
    features["last_swing_high"] = 20_010.0
    candidate_id = trade_setup_candidate_id("fvg_retest", "M1", 1)
    features.loc[index[1:], "entry_idea_fvg_retest_M1_long"] = 1.0
    features.loc[index[1:], "fvg_bull_active"] = 1.0
    features.loc[index[1:], "fvg_bull_retest_confirmed_at_time_ns"] = index[1].value
    features.loc[index[1:], "fvg_bull_retest_origin_time_ns"] = index[0].value
    schema = build_trade_setup_action_schema(has_sl_mode=True, has_entry_execution=True)
    market_action = _market_action(schema, candidate_id)
    tick_time = index[2] + pd.Timedelta(seconds=30)
    tick_times = [tick_time, index[-1] + pd.Timedelta(minutes=1, seconds=1)]
    tickbook = TickBook(
        np.asarray([timestamp.value for timestamp in tick_times], dtype=np.int64),
        np.asarray([19_999.5, 19_999.5]),
        np.asarray([19_999.75, 19_999.75]),
    )
    costs = CostModel(spread_points=0.0, point_size=0.25, commission_per_lot=0.0)

    env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=1,
        strategy_actions=True,
        trade_setup_actions=True,
        agent_entry_execution=True,
        tickbook=tickbook,
        cost_model=costs,
        tick_execution_required=True,
        randomized_fill_latency_ms=1.0,
        open_manipulation_bars=0,
        block_overnight=False,
        max_episode_steps=4,
        strategy=_SwingGeometryStrategy(),
    )
    env.reset(seed=7)
    env.step_idx = 1
    env._ny_pos = int(np.searchsorted(env._ny_indices, env.step_idx))
    env.step(market_action)

    result = run_backtest(
        bars,
        features,
        lambda _observation: market_action,
        obs_window=1,
        cost_model=costs,
        hold_on_zero=True,
        block_overnight=False,
        trade_setup_actions=True,
        trade_setup_action_schema=schema,
        tickbook=tickbook,
        tick_execution_required=True,
        randomized_fill_latency_ms=1.0,
        execution_seed=7,
        trade_setup_geometry=False,
        strategy=_SwingGeometryStrategy(),
    )
    backtest_events = result["trades"].to_dict("records")
    env_fill = next(event for event in env.trade_log if event.get("type") == "order_fill")
    backtest_fill = next(event for event in backtest_events if event.get("type") == "order_fill")
    env_submit = next(event for event in env.trade_log if event.get("type") == "order_submit")
    backtest_submit = next(
        event for event in backtest_events if event.get("type") == "order_submit"
    )
    env_open = next(event for event in env.trade_log if event.get("type") == "open")
    backtest_open = next(event for event in backtest_events if event.get("type") == "open")

    assert env_fill["order_type"] == backtest_fill["order_type"] == "market"
    assert env_fill["order_id"] == env_submit["order_id"]
    assert backtest_fill["order_id"] == backtest_submit["order_id"]
    assert env_fill["decision_id"] == env_submit["decision_id"]
    assert backtest_fill["decision_id"] == backtest_submit["decision_id"]
    assert env_fill["direction"] == backtest_fill["direction"] == 1
    assert env_fill["time"] == backtest_fill["time"] == tick_time
    assert env_fill["bid"] == backtest_fill["bid"] == 19_999.5
    assert env_fill["ask"] == backtest_fill["ask"] == 19_999.75
    assert (
        env_fill["price"] == backtest_fill["price"] == env_open["price"] == backtest_open["price"]
    )
    assert [
        event["type"] for event in env.trade_log if event.get("type") in {"order_fill", "open"}
    ] == ["order_fill", "open"]
    assert [
        event["type"] for event in backtest_events if event.get("type") in {"order_fill", "open"}
    ] == ["order_fill", "open"]
