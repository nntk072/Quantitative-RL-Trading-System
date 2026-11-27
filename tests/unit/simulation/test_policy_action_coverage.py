"""Structured setup actions must create or refuse orders from their geometry."""

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
from trading.execution import CostModel
from trading.strategies import BaselineStrategy


class _StructuralEntryStrategy(BaselineStrategy):
    name = "policy_action_coverage"

    def sl_candidates(self, *, direction: int, row: pd.Series) -> list[tuple[str, float]]:
        del row
        if direction == 1:
            return [("last_swing_low", 19_990.0)]
        return [("last_swing_high", 20_010.0)]


def _flat_market_frame(n: int = 4) -> tuple[pd.DataFrame, pd.DataFrame]:
    index = pd.date_range("2026-02-02 14:30", periods=n, freq="min", tz="UTC")
    close = np.full(n, 100.0)
    bars = pd.DataFrame(
        {
            "open": close,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "spread": 0.0,
            "session_id": 1,
            "session": "ny",
        },
        index=index,
    )
    return bars, pd.DataFrame(index=index)


def _run_structured_entry(*, has_target: bool) -> dict[str, Any]:
    index = pd.date_range("2026-02-02 14:30", periods=6, freq="min", tz="UTC")
    close = np.full(len(index), 20_000.0)
    bars = pd.DataFrame(
        {
            "open": close,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "spread": 0.0,
            "session_id": 1,
            "session": "ny",
        },
        index=index,
    )
    feature_names = [name for _, name in trade_setup_candidate_feature_columns()]
    features = pd.DataFrame(0.0, index=index, columns=feature_names)
    features["atr_5"] = 1.0
    features["last_swing_low"] = 19_990.0
    features["last_swing_high"] = 20_020.0 if has_target else np.nan
    features["entry_idea_fvg_retest_M1_long"] = 1.0

    schema = build_trade_setup_action_schema()
    candidate_id = trade_setup_candidate_id("fvg_retest", "M1", 1)
    entry_action = np.zeros(schema.width, dtype=np.float32)
    entry_action[schema.indices["trade_setup"]] = trade_setup_center(candidate_id)
    entry_action[schema.indices["risk"]] = 1.0
    entry_action[schema.indices["exit"]] = -1.0
    no_trade_action = np.zeros(schema.width, dtype=np.float32)
    no_trade_action[schema.indices["trade_setup"]] = trade_setup_center(0)
    calls = 0

    def policy(_observation: Any) -> np.ndarray[Any, Any]:
        nonlocal calls
        calls += 1
        return entry_action if calls == 1 else no_trade_action

    return run_backtest(
        bars,
        features,
        policy,
        obs_window=1,
        cost_model=CostModel(spread_points=0.0, point_size=0.25),
        initial_balance=100_000.0,
        risk_frac=0.01,
        policy_risk_frac_range=(0.005, 0.02),
        min_lot=0.01,
        max_lot=1.0,
        contract_size=1.0,
        hold_on_zero=True,
        block_overnight=False,
        trade_setup_actions=True,
        trade_setup_action_schema=schema,
        trade_setup_geometry=True,
        strategy=_StructuralEntryStrategy(),
    )


def test_structured_entry_records_selected_geometry_and_sized_risk() -> None:
    result = _run_structured_entry(has_target=True)

    opened = result["trades"].loc[result["trades"]["type"].eq("open")]
    assert len(opened) == 1
    event = opened.iloc[0]
    assert event["trade_setup_candidate_id"] == trade_setup_candidate_id("fvg_retest", "M1", 1)
    assert event["sl_price"] == 19_990.0
    assert event["tp_price"] == 20_020.0
    assert event["risk_frac"] == 0.02
    assert event["risk_budget_usd"] > 0.0
    assert event["selected_geometry_action"]["exit_mode"] == "structural"
    assert not result["trades"]["type"].eq("reject").any()


def test_structured_entry_without_a_target_is_refused_without_opening() -> None:
    result = _run_structured_entry(has_target=False)

    rejects = result["trades"].loc[result["trades"]["type"].eq("reject")]
    assert len(rejects) == 1
    assert rejects.iloc[0]["reason"] == "no_valid_tp"
    assert not result["trades"]["type"].eq("open").any()
    assert not result["trades"]["type"].eq("order_fill").any()


def test_reversing_direction_closes_the_old_position_before_opening_the_new_one() -> None:
    index = pd.date_range("2026-02-02 14:30", periods=6, freq="min", tz="UTC")
    close = np.full(len(index), 100.0)
    bars = pd.DataFrame(
        {
            "open": close,
            "high": close + 0.2,
            "low": close - 0.2,
            "close": close,
            "session_id": 1,
            "session": "ny",
        },
        index=index,
    )
    actions = iter((1, -1, 0, 0, 0))

    result = run_backtest(
        bars,
        pd.DataFrame(index=index),
        lambda _observation: next(actions, 0),
        obs_window=1,
        cost_model=CostModel(spread_points=0.0, point_size=0.01),
        initial_balance=10_000.0,
        hold_on_zero=True,
        block_overnight=False,
    )

    events = result["trades"].to_dict("records")
    opens = [event for event in events if event["type"] == "open"]
    closes = [event for event in events if event["type"] == "close"]
    assert len(opens) == 2
    assert len(closes) == 1
    assert opens[0]["direction"] == 1
    assert closes[0]["position_id"] == opens[0]["position_id"]
    assert opens[1]["direction"] == -1
    assert opens[1]["position_id"] != opens[0]["position_id"]
    transition_events = [event["type"] for event in events if event["type"] in {"open", "close"}]
    assert transition_events == ["open", "close", "open"]


def test_market_tick_slippage_changes_only_the_transacted_entry_side() -> None:
    index = pd.date_range("2026-02-02 14:30", periods=5, freq="min", tz="UTC")
    close = np.full(len(index), 100.0)
    bars = pd.DataFrame(
        {
            "open": close,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "session_id": 1,
            "session": "ny",
        },
        index=index,
    )
    tick_times = [*index[1:], index[-1] + pd.Timedelta(minutes=1)]
    tickbook = TickBook(
        np.asarray([time.value for time in tick_times], dtype=np.int64),
        np.full(len(tick_times), 100.0),
        np.full(len(tick_times), 100.25),
    )
    actions = iter((1, 0, 0, 0))

    result = run_backtest(
        bars,
        pd.DataFrame(index=index),
        lambda _observation: next(actions, 0),
        obs_window=1,
        cost_model=CostModel(spread_points=0.0, point_size=0.25),
        tickbook=tickbook,
        tick_execution_required=True,
        tick_fill_slippage_points=0.5,
        initial_balance=10_000.0,
        hold_on_zero=True,
        block_overnight=False,
    )

    opened = result["trades"].loc[result["trades"]["type"].eq("open")].iloc[0]
    assert opened["pre_execution_quote_bid"] == 100.0
    assert opened["pre_execution_quote_ask"] == 100.25
    assert opened["broker_execution_quote_bid"] == 100.0
    assert opened["broker_execution_quote_ask"] == 100.75
    assert opened["price"] == 100.75
    assert opened["slippage_points_applied_here"] == 0.5
    assert bool(opened["slippage_applied_here"])


def test_entry_is_refused_when_tickbook_has_no_executable_quote_within_wait() -> None:
    bars, features = _flat_market_frame()
    tickbook = TickBook(np.asarray([], dtype=np.int64), np.asarray([]), np.asarray([]))

    result = run_backtest(
        bars,
        features,
        lambda _observation: 1,
        obs_window=1,
        cost_model=CostModel(spread_points=0.0, point_size=0.01),
        tickbook=tickbook,
        tick_execution_required=True,
        initial_balance=10_000.0,
        hold_on_zero=True,
        block_overnight=False,
    )

    rejects = result["trades"].loc[result["trades"]["type"].eq("reject")]
    assert not result["trades"]["type"].eq("open").any()
    assert len(rejects) == result["policy_decisions"]["action"].eq(1).sum()
    assert rejects["reason"].eq("no_executable_tick_within_wait").all()


def test_fixed_risk_cap_refuses_entry_before_opening_a_position() -> None:
    bars, features = _flat_market_frame()
    result = run_backtest(
        bars,
        features,
        lambda _observation: 1,
        obs_window=1,
        cost_model=CostModel(spread_points=0.0, point_size=0.01),
        initial_balance=10_000.0,
        lots=1.0,
        max_loss_per_trade_usd=100.0,
        guardrail_kwargs={"risk_per_trade_limit": 10.0, "limit_value_mode": "fixed_usd"},
        hold_on_zero=True,
        block_overnight=False,
    )

    rejects = result["trades"].loc[result["trades"]["type"].eq("reject")]
    assert not result["trades"]["type"].eq("open").any()
    assert len(rejects) == result["policy_decisions"]["action"].eq(1).sum()
    assert rejects["reason"].eq("trade_risk_limit").all()
