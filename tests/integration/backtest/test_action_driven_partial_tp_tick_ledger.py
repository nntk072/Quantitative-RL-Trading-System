from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import pytest

from decisioning.trade_setup import (
    NO_TRADE_ID,
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


class _StructuralEntryStrategy(BaselineStrategy):
    name = "action_driven_partial_tp_test"

    def sl_candidates(self, *, direction: int, row: pd.Series) -> list[tuple[str, float]]:
        column = "last_swing_low" if direction == 1 else "last_swing_high"
        return [(column, float(row[column]))]


def _actions(schema: Any, candidate_id: int) -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any]]:
    action = np.zeros(schema.width, dtype=np.float32)
    action[schema.indices["trade_setup"]] = trade_setup_center(candidate_id)
    action[schema.indices["stop"]] = -0.4
    action[schema.indices["risk"]] = -1.0
    action[schema.indices["tp1_sel"]] = -1.0
    action[schema.indices["tp2_sel"]] = -0.3
    action[schema.indices["tp3_sel"]] = 1.0
    if "sl_mode" in schema.indices:
        action[schema.indices["sl_mode"]] = -1.0
    action[schema.indices["exit"]] = -1.0
    no_trade = np.zeros(schema.width, dtype=np.float32)
    no_trade[schema.indices["trade_setup"]] = trade_setup_center(NO_TRADE_ID)
    return action, no_trade


def test_action_selected_partial_tp_uses_first_source_tick_and_reconciles_ledger() -> None:
    index = pd.date_range("2025-01-06 14:30", periods=7, freq="1min", tz="UTC")
    close = np.full(len(index), 20_000.0)
    high = close + 1.0
    high[2] = 20_012.0
    bars = pd.DataFrame(
        {
            "open": close,
            "high": high,
            "low": close - 1.0,
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
    features["last_swing_high"] = 20_012.0
    features["asian_high"] = 20_014.0
    features["london_high"] = 20_016.0
    candidate_id = trade_setup_candidate_id("fvg_retest", "M1", 1)
    features.loc[index[1:], "entry_idea_fvg_retest_M1_long"] = 1.0
    features.loc[index[1:], "fvg_bull_active"] = 1.0
    features.loc[index[1:], "fvg_bull_retest_confirmed_at_time_ns"] = index[1].value
    features.loc[index[1:], "fvg_bull_retest_origin_time_ns"] = index[0].value
    schema = build_trade_setup_action_schema(has_sl_mode=True, has_multi_tp=True)
    market_action, no_trade_action = _actions(schema, candidate_id)

    entry_tick = index[2] + pd.Timedelta(milliseconds=1)
    first_tp_crossing = index[2] + pd.Timedelta(seconds=20)
    terminal_tick = index[-1] + pd.Timedelta(minutes=1, milliseconds=2)
    quiet_ticks = [index[i] + pd.Timedelta(milliseconds=1) for i in range(3, len(index))]
    tick_times = [entry_tick, first_tp_crossing, *quiet_ticks, terminal_tick]
    bids = [20_000.0, 20_012.0, *([20_000.0] * len(quiet_ticks)), 20_000.0]
    asks = [20_000.25, 20_012.25, *([20_000.25] * len(quiet_ticks)), 20_000.25]
    tickbook = TickBook(
        np.asarray([timestamp.value for timestamp in tick_times], dtype=np.int64),
        np.asarray(bids),
        np.asarray(asks),
    )
    costs = CostModel(spread_points=0.0, point_size=0.25, commission_per_lot=1.0)
    initial_balance = 100_000.0
    environment_kwargs: dict[str, Any] = {
        "obs_window": 1,
        "initial_balance": initial_balance,
        "cost_model": costs,
        "risk_frac_range": (0.001, 0.001),
        "min_lot": 0.01,
        "max_lot": 1.0,
        "contract_size": 1.0,
        "strategy_actions": True,
        "trade_setup_actions": True,
        "allow_multi_tp": True,
        "allow_simplex": False,
        "tickbook": tickbook,
        "tick_execution_required": True,
        "randomized_fill_latency_ms": 1.0,
        "server_side_protective_orders": True,
        "block_overnight": False,
        "open_manipulation_bars": 0,
        "max_episode_steps": 5,
        "strategy": _StructuralEntryStrategy(),
    }
    env = TradingEnv(bars=bars, features=features, **environment_kwargs)
    env.reset(seed=7)
    env.step_idx = 1
    env._ny_pos = int(np.searchsorted(env._ny_indices, env.step_idx))
    env.step(market_action)
    for _ in range(4):
        if env.position is None:
            break
        env.step(no_trade_action)

    calls = 0

    def policy(_observation: Any) -> np.ndarray[Any, Any]:
        nonlocal calls
        calls += 1
        return market_action if calls == 1 else no_trade_action

    backtest = run_backtest(
        bars,
        features,
        policy,
        obs_window=1,
        initial_balance=initial_balance,
        cost_model=costs,
        risk_frac=0.001,
        policy_risk_frac_range=(0.001, 0.001),
        min_lot=0.01,
        max_lot=1.0,
        contract_size=1.0,
        hold_on_zero=True,
        block_overnight=False,
        open_manipulation_bars=0,
        trade_setup_actions=True,
        trade_setup_action_schema=schema,
        trade_setup_geometry=True,
        tickbook=tickbook,
        tick_execution_required=True,
        randomized_fill_latency_ms=1.0,
        server_side_protective_orders=True,
        strategy=_StructuralEntryStrategy(),
        execution_seed=7,
    )

    environment_events = env.trade_log
    backtest_events = backtest["trades"].to_dict("records")
    assert any(event.get("type") == "open" for event in environment_events), environment_events
    env_open = next(event for event in environment_events if event.get("type") == "open")
    bt_open = next(event for event in backtest_events if event.get("type") == "open")
    env_partial = next(
        event for event in environment_events if event.get("type") == "tp_partial_close"
    )
    bt_partial = next(event for event in backtest_events if event.get("type") == "tp_partial_close")
    assert (
        env_open["trade_setup_candidate_id"] == bt_open["trade_setup_candidate_id"] == candidate_id
    )
    assert env_open["tp_legs"][0]["executed_price"] == bt_open["tp1_price"] == 20_012.0
    assert env_open["tp_legs"][0]["lot_fraction"] == pytest.approx(1.0 / 3.0)
    assert env_open["lots"] == bt_open["lots"] == 1.0
    assert env_partial["reason"] == bt_partial["reason"] == "structure_tp1"
    assert env_partial["fill_quote_source"] == bt_partial["fill_quote_source"] == "tick"
    assert env_partial["actual_tick_time"] == bt_partial["actual_tick_time"] == first_tp_crossing
    assert env_partial["price"] == bt_partial["price"] == bids[1]
    assert env_partial["size"] == pytest.approx(0.33)
    assert bt_partial["size"] == pytest.approx(0.33)
    remaining_after_first_target = env_open["lots"] - env_partial["size"]
    assert remaining_after_first_target == pytest.approx(0.67)
    assert bt_open["lots"] - bt_partial["size"] == pytest.approx(remaining_after_first_target)
    source_tick = tickbook.quote_event_at(first_tp_crossing)
    assert source_tick is not None
    assert source_tick[1] == env_partial["price"] == bt_partial["price"]

    for engine_name, events, final_balance, open_event in (
        ("environment", environment_events, env.account.balance, env_open),
        ("backtest", backtest_events, float(backtest["account"].balance), bt_open),
    ):
        close_events = [
            event
            for event in events
            if event.get("type")
            in {"tp_partial_close", "tp_close", "stop_close", "close", "forced_close", "eod_close"}
        ]
        net_cashflows = [float(event["net_pnl"]) for event in close_events]
        for event in close_events:
            assert float(event["gross_price_pnl"]) - float(event["exit_commission"]) - float(
                event["entry_commission_allocated"]
            ) == pytest.approx(float(event["net_pnl"]))
        assert initial_balance + sum(net_cashflows) == pytest.approx(final_balance), (
            engine_name,
            close_events,
        )
        assert sum(float(event["size"]) for event in close_events) == pytest.approx(1.0)
