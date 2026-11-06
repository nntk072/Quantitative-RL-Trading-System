from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd
import pytest

from decisioning.trade_setup import (
    NO_TRADE_ID,
    TradeSetupActionSchema,
    build_trade_setup_action_schema,
    trade_setup_candidate_id,
    trade_setup_center,
)
from evaluation.metrics.limit_execution_sensitivity import compare_limit_execution_sensitivity
from evaluation.reporting.policy_decision_reconciliation import reconcile_policy_decisions
from features.context.trade_setup_candidates import (
    trade_setup_candidate_event_time_fields,
    trade_setup_candidate_feature_columns,
)
from market_data.loading.ticks import TickBook, TickExecutionUnavailable
from simulation.backtest import run_backtest
from simulation.environment.env import TradingEnv
from tests.unit.simulation.test_environment._account_fixtures import _make_bars, _make_features
from trading.execution import FILL_COST_PROVENANCE_SCHEMA_VERSION, CostModel
from trading.strategies.baseline import BaselineStrategy

Array = np.ndarray[Any, Any]


def _trade_setup_schema(env: TradingEnv) -> TradeSetupActionSchema:
    schema = env.action_schema
    assert isinstance(schema, TradeSetupActionSchema)
    return schema


def _event_number(event: Mapping[Any, Any], key: str) -> float:
    value = event[key]
    assert isinstance(value, (int, float))
    return float(value)


class _SwingGeometryStrategy(BaselineStrategy):
    name = "swing_geometry_test"

    def sl_candidates(self, *, direction: int, row: pd.Series) -> list[tuple[str, float]]:
        column = "last_swing_low" if direction == 1 else "last_swing_high"
        return [(column, float(row[column]))]


def _action(
    schema: TradeSetupActionSchema,
    *,
    candidate_id: int,
    limit: bool,
) -> Array:
    values = np.zeros(schema.width, dtype=np.float32)
    indices = schema.indices
    values[indices["trade_setup"]] = trade_setup_center(candidate_id)
    values[indices["entry_execution"]] = 1.0 if limit else -1.0
    values[indices["limit_offset_atr"]] = -1.0  # at the causal decision close
    values[indices["limit_ttl_bars"]] = -1.0  # one bar
    values[indices["stop"]] = -0.4
    values[indices["target"]] = 0.8
    values[indices["exit"]] = -1.0
    return values


def _backtest_inputs() -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    TickBook,
    TradeSetupActionSchema,
    int,
    Array,
]:
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
    candidate_id = trade_setup_candidate_id("fvg_retest", "M1", 1)
    features.loc[index[1:], "entry_idea_fvg_retest_M1_long"] = 1.0
    features.loc[index[1:], "fvg_bull_active"] = 1.0
    features.loc[index[1:], "fvg_bull_retest_confirmed_at_time_ns"] = index[1].value
    features.loc[index[1:], "fvg_bull_retest_origin_time_ns"] = index[0].value
    schema = build_trade_setup_action_schema(has_sl_mode=True, has_entry_execution=True)
    choice = _action(schema, candidate_id=candidate_id, limit=True)
    return (
        bars,
        features,
        TickBook(np.array([], dtype=np.int64), np.array([]), np.array([])),
        schema,
        candidate_id,
        choice,
    )


def _add_m5_fvg_state(features: pd.DataFrame, bars: pd.DataFrame, start: int = 65) -> None:
    active_column = "M5_fvg_bull_active"
    confirmed_column = "M5_fvg_bull_retest_confirmed_at_time_ns"
    origin_column = "M5_fvg_bull_retest_origin_time_ns"
    features[active_column] = 0.0
    features[confirmed_column] = np.nan
    features[origin_column] = np.nan
    features.loc[bars.index[start:], active_column] = 1.0
    features.loc[bars.index[start:], confirmed_column] = bars.index[start].value
    features.loc[bars.index[start:], origin_column] = bars.index[start - 1].value


def test_event_backtest_limit_order_fills_only_from_executable_tick_quote() -> None:
    bars, features, _, schema, candidate_id, limit_action = _backtest_inputs()
    tick_time = bars.index[2] + pd.Timedelta(seconds=30)
    tickbook = TickBook(
        np.asarray([tick_time.value], dtype=np.int64),
        np.asarray([19_999.5]),
        np.asarray([19_999.75]),
    )

    result = run_backtest(
        bars,
        features,
        lambda _observation: limit_action,
        obs_window=1,
        cost_model=CostModel(spread_points=0.0, point_size=0.25, commission_per_lot=0.0),
        hold_on_zero=True,
        block_overnight=False,
        trade_setup_actions=True,
        trade_setup_action_schema=schema,
        tickbook=tickbook,
        trade_setup_geometry=False,
        tick_fill_slippage_points=1.0,
    )

    records = result["trades"].to_dict("records")
    submitted = next(event for event in records if event.get("type") == "order_submit")
    filled = next(event for event in records if event.get("type") == "order_fill")
    opened = next(event for event in records if event.get("type") == "open")
    decision = result["policy_decisions"].set_index("decision_id").loc[submitted["decision_id"]]
    assert submitted["order_type"] == "limit"
    assert submitted["trade_setup_candidate_id"] == candidate_id
    assert submitted["decision_id"] == filled["decision_id"] == opened["decision_id"]
    assert decision["trade_setup_candidate_id"] == candidate_id
    assert bool(decision["trade_setup_eligible"])
    assert decision["execution_type"] == "limit"
    assert filled["time"] == tick_time
    assert filled["ask"] <= filled["limit_price"]
    assert filled["price"] == filled["ask"]
    assert opened["fill_quote_source"] == "tick"
    assert opened["fill_time"] == tick_time
    assert opened["order_submission_time"] == submitted["order_submission_time"]
    assert opened["order_id"] == submitted["order_id"]
    assert opened["price"] == filled["price"]
    assert opened["price"] <= filled["limit_price"]


def test_limit_quote_is_not_recorded_as_fill_when_margin_rejects_the_entry() -> None:
    bars, features, _, schema, _, limit_action = _backtest_inputs()
    features["last_swing_low"] = bars["close"] - 20.0
    features["last_swing_high"] = bars["close"] + 40.0
    tick_time = bars.index[2] + pd.Timedelta(seconds=30)
    tickbook = TickBook(
        np.asarray([tick_time.value], dtype=np.int64),
        np.asarray([19_999.5]),
        np.asarray([19_999.75]),
    )
    no_trade = _action(schema, candidate_id=NO_TRADE_ID, limit=False)
    env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=1,
        strategy_actions=True,
        trade_setup_actions=True,
        agent_entry_execution=True,
        tickbook=tickbook,
        strategy=_SwingGeometryStrategy(),
        broker_kwargs={"margin_pct": 100_000.0},
        cost_model=CostModel(spread_points=0.0, point_size=0.25, commission_per_lot=0.0),
        tick_execution_required=True,
        open_manipulation_bars=0,
        block_overnight=False,
        max_episode_steps=3,
    )
    env.reset(seed=13)
    env.step_idx = 1
    env._ny_pos = int(np.searchsorted(env._ny_indices, env.step_idx))
    env.step(limit_action)
    env.step(no_trade)

    backtest = run_backtest(
        bars,
        features,
        lambda _observation: limit_action,
        obs_window=1,
        cost_model=CostModel(spread_points=0.0, point_size=0.25, commission_per_lot=0.0),
        hold_on_zero=True,
        block_overnight=False,
        trade_setup_actions=True,
        trade_setup_action_schema=schema,
        tickbook=tickbook,
        strategy=_SwingGeometryStrategy(),
        trade_setup_geometry=False,
        broker_kwargs={"margin_pct": 100_000.0},
    )

    for events in (env.trade_log, backtest["trades"].to_dict("records")):
        submission = next(event for event in events if event.get("type") == "order_submit")
        rejected_cancel = next(
            event
            for event in events
            if event.get("type") == "order_cancel"
            and event.get("reason") == "entry_rejected_at_limit_fill"
        )
        assert any(
            event.get("type") == "reject"
            and (
                event.get("reason") == "insufficient_margin"
                or event.get("entry_rejection_reason") == "insufficient_margin"
            )
            for event in events
        ), events
        assert rejected_cancel["decision_id"] == submission["decision_id"]
        assert rejected_cancel["trade_setup_candidate_id"] == submission["trade_setup_candidate_id"]
        assert (
            rejected_cancel["trade_setup_source_event_id"]
            == submission["trade_setup_source_event_id"]
        )
        assert rejected_cancel["trigger_quote_time"] == tick_time
        assert rejected_cancel["trigger_quote_price"] == rejected_cancel["trigger_quote_ask"]
        assert rejected_cancel["trigger_quote_price"] <= rejected_cancel["limit_price"]
        assert not any(event.get("type") in {"order_fill", "open"} for event in events)
    reconciliation = reconcile_policy_decisions(
        backtest["policy_decisions"], backtest["trades"], []
    )
    assert reconciliation["status"] == "matched", reconciliation
    assert reconciliation["checks"]["rejected_limit_trigger_price_matches_quote_side"] == 1
    assert reconciliation["checks"]["rejected_limit_trigger_respects_price_and_lifetime"] == 1


@pytest.mark.parametrize(
    ("source_defect", "expected_reason"),
    (
        ("identity", "limit_entry_source_identity_unavailable"),
        ("state", "limit_entry_source_setup_unavailable"),
    ),
)
def test_event_backtest_rejects_limit_without_current_setup_source(
    source_defect: str, expected_reason: str
) -> None:
    bars, features, _, schema, candidate_id, limit_action = _backtest_inputs()
    if source_defect == "identity":
        features.loc[bars.index[1] :, "fvg_bull_retest_origin_time_ns"] = np.nan
    else:
        features.loc[bars.index[1] :, "fvg_bull_active"] = 0.0
    tick_time = bars.index[2] + pd.Timedelta(seconds=30)
    tickbook = TickBook(
        np.asarray([tick_time.value], dtype=np.int64),
        np.asarray([19_999.5]),
        np.asarray([19_999.75]),
    )

    result = run_backtest(
        bars,
        features,
        lambda _observation: limit_action,
        obs_window=1,
        cost_model=CostModel(spread_points=0.0, point_size=0.25, commission_per_lot=0.0),
        hold_on_zero=True,
        block_overnight=False,
        trade_setup_actions=True,
        trade_setup_action_schema=schema,
        tickbook=tickbook,
        trade_setup_geometry=False,
    )

    events = result["trades"].to_dict("records")
    assert any(
        event.get("type") == "reject"
        and event.get("reason") == expected_reason
        and event.get("trade_setup_candidate_id") == candidate_id
        for event in events
    )
    assert not any(event.get("type") in {"order_submit", "order_fill", "open"} for event in events)


@pytest.mark.parametrize(
    ("source_defect", "expected_reason"),
    (
        ("identity", "limit_entry_source_identity_unavailable"),
        ("state", "limit_entry_source_setup_unavailable"),
    ),
)
def test_trading_env_rejects_limit_without_current_setup_source(
    source_defect: str, expected_reason: str
) -> None:
    bars, features, _, _, candidate_id, _ = _backtest_inputs()
    if source_defect == "identity":
        features.loc[bars.index[1] :, "fvg_bull_retest_origin_time_ns"] = np.nan
    else:
        features.loc[bars.index[1] :, "fvg_bull_active"] = 0.0
    tick_time = bars.index[2] + pd.Timedelta(seconds=30)
    tickbook = TickBook(
        np.asarray([tick_time.value], dtype=np.int64),
        np.asarray([19_999.5]),
        np.asarray([19_999.75]),
    )
    env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=1,
        strategy_actions=True,
        trade_setup_actions=True,
        agent_entry_execution=True,
        tickbook=tickbook,
        cost_model=CostModel(spread_points=0.0, point_size=0.25, commission_per_lot=0.0),
        tick_execution_required=True,
        open_manipulation_bars=0,
        block_overnight=False,
        max_episode_steps=4,
    )
    env.reset(seed=5)
    env.step_idx = 1
    env._ny_pos = int(np.searchsorted(env._ny_indices, env.step_idx))
    _, _, _, _, info = env.step(
        _action(_trade_setup_schema(env), candidate_id=candidate_id, limit=True)
    )

    assert env._pending_entry_order is None
    assert info["entry_rejected_entry_execution"] == 1
    assert info["entry_rejection_reason"] == expected_reason
    assert any(event.get("entry_rejection_reason") == expected_reason for event in env.trade_log)
    assert not any(
        event.get("type") in {"order_submit", "order_fill", "open"} for event in env.trade_log
    )


def test_trading_env_episode_end_cancellation_preserves_limit_setup_identity() -> None:
    bars, features, tickbook, _, candidate_id, _ = _backtest_inputs()
    schema = build_trade_setup_action_schema(has_sl_mode=True, has_entry_execution=True)
    action = _action(schema, candidate_id=candidate_id, limit=True)
    env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=1,
        strategy_actions=True,
        trade_setup_actions=True,
        agent_entry_execution=True,
        tickbook=tickbook,
        cost_model=CostModel(spread_points=0.0, point_size=0.25, commission_per_lot=0.0),
        tick_execution_required=True,
        open_manipulation_bars=0,
        block_overnight=False,
        max_episode_steps=1,
    )
    env.reset(seed=17)
    env.step_idx = 1
    env._ny_pos = int(np.searchsorted(env._ny_indices, env.step_idx))
    env.step(action)

    submit = next(event for event in env.trade_log if event.get("type") == "order_submit")
    cancel = next(event for event in env.trade_log if event.get("type") == "order_cancel")
    assert cancel["reason"] == "episode_ended_before_limit_expiry"
    assert cancel["decision_id"] == submit["decision_id"]
    assert cancel["order_id"] == submit["order_id"]
    assert cancel["trade_setup_candidate_id"] == candidate_id
    assert cancel["trade_setup_source_event_id"] == submit["trade_setup_source_event_id"]
    assert not any(event.get("type") in {"order_fill", "open"} for event in env.trade_log)


@pytest.mark.parametrize(
    ("zone_change", "expected_cancel_reason"),
    (
        ("remains_active", None),
        ("expires", "source_setup_invalidated"),
        ("replaced", "source_setup_replaced"),
    ),
)
def test_event_backtest_ifvg_limit_follows_zone_lifetime_after_retest_pulse(
    zone_change: str,
    expected_cancel_reason: str | None,
) -> None:
    bars, features, _, schema, _, _ = _backtest_inputs()
    index = bars.index
    candidate_id = trade_setup_candidate_id("ifvg_retest", "M1", 1)
    features["entry_idea_fvg_retest_M1_long"] = 0.0
    features["entry_idea_ifvg_retest_M1_long"] = 0.0
    features.loc[index[1], "entry_idea_ifvg_retest_M1_long"] = 1.0
    features["ifvg_bull_active"] = 1.0
    features["ifvg_bull_confirmed_at_time_ns"] = index[0].value
    features["ifvg_bull_fvg_origin_time_ns"] = index[0].value
    features["ifvg_bull_retest_confirmed_at_time_ns"] = np.nan
    features.loc[index[1], "ifvg_bull_retest_confirmed_at_time_ns"] = index[1].value
    if zone_change == "expires":
        features.loc[index[2], "ifvg_bull_active"] = 0.0
    elif zone_change == "replaced":
        features.loc[index[2], "ifvg_bull_confirmed_at_time_ns"] = index[2].value
        features.loc[index[2], "ifvg_bull_fvg_origin_time_ns"] = index[1].value
    limit_action = _action(schema, candidate_id=candidate_id, limit=True)
    tick_time = index[2] + pd.Timedelta(seconds=30)
    tickbook = TickBook(
        np.asarray([tick_time.value], dtype=np.int64),
        np.asarray([19_999.5]),
        np.asarray([19_999.75]),
    )

    result = run_backtest(
        bars,
        features,
        lambda _observation: limit_action,
        obs_window=1,
        cost_model=CostModel(spread_points=0.0, point_size=0.25, commission_per_lot=0.0),
        hold_on_zero=True,
        block_overnight=False,
        trade_setup_actions=True,
        trade_setup_action_schema=schema,
        tickbook=tickbook,
        trade_setup_geometry=False,
    )

    records = result["trades"].to_dict("records")
    submitted = next(event for event in records if event.get("type") == "order_submit")
    assert submitted["trade_setup_candidate_id"] == candidate_id
    if expected_cancel_reason is None:
        filled = next(event for event in records if event.get("type") == "order_fill")
        assert filled["trade_setup_source_event_id"] == submitted["trade_setup_source_event_id"]
        assert filled["time"] == tick_time
        assert not any(event.get("type") == "order_cancel" for event in records)
    else:
        cancelled = next(event for event in records if event.get("type") == "order_cancel")
        assert cancelled["reason"] == expected_cancel_reason
        assert cancelled["trade_setup_source_event_id"] == submitted["trade_setup_source_event_id"]
        assert not any(event.get("type") in {"order_fill", "open"} for event in records)


@pytest.mark.parametrize(
    ("idea", "source_change", "expected_reason"),
    (
        ("po3", "new_sweep", "source_setup_replaced"),
        ("po3", "zone_expires", "source_setup_invalidated"),
        ("standard_deviation", "envelope_expires", "source_setup_invalidated"),
    ),
)
def test_event_backtest_cancels_limit_when_po3_or_deviation_source_ends(
    idea: str, source_change: str, expected_reason: str
) -> None:
    bars, features, _, schema, _, _ = _backtest_inputs()
    index = bars.index
    candidate_id = trade_setup_candidate_id(idea, "M1", 1)
    features["entry_idea_fvg_retest_M1_long"] = 0.0
    features.loc[index[1] :, f"entry_idea_{idea}_M1_long"] = 1.0
    source_fields = trade_setup_candidate_event_time_fields(candidate_id)
    for field, scale in source_fields:
        features.loc[index[1] :, field] = index[0].value / scale

    if idea == "po3":
        features.loc[index[1] :, "po3_distribution_after_ifvg"] = 1.0
        features.loc[index[1] :, "po3_distribution_direction"] = 1.0
        features.loc[index[1] :, "ifvg_bull_active"] = 1.0
        if source_change == "new_sweep":
            features.loc[index[2], "po3_sweep_time_ns"] = index[2].value
        else:
            features.loc[index[2], "ifvg_bull_active"] = 0.0
    else:
        features.loc[index[1] :, "standard_deviation_leg_valid"] = 1.0
        features.loc[index[1] :, "standard_deviation_leg_direction"] = 1.0
        # The producer drops source timestamps when price closes outside its
        # 0–0.786 envelope, while this row is eligible for a fresh decision.
        features.loc[index[2], "standard_deviation_leg_valid"] = 0.0
        for field, _ in source_fields:
            features.loc[index[2], field] = np.nan

    tick_time = index[2] + pd.Timedelta(seconds=30)
    tickbook = TickBook(
        np.asarray([tick_time.value], dtype=np.int64),
        np.asarray([19_999.5]),
        np.asarray([19_999.75]),
    )
    limit_action = _action(schema, candidate_id=candidate_id, limit=True)
    no_trade = _action(schema, candidate_id=NO_TRADE_ID, limit=False)
    submitted_once = False

    def submit_once(observation: object) -> Array:
        nonlocal submitted_once
        if isinstance(observation, dict):
            mask = np.asarray(observation.get("trade_setup_mask", []), dtype=np.float32).reshape(-1)
            if not submitted_once and candidate_id < len(mask) and mask[candidate_id] > 0.0:
                submitted_once = True
                return limit_action
        return no_trade

    result = run_backtest(
        bars,
        features,
        submit_once,
        obs_window=1,
        cost_model=CostModel(spread_points=0.0, point_size=0.25, commission_per_lot=0.0),
        hold_on_zero=True,
        block_overnight=False,
        trade_setup_actions=True,
        trade_setup_action_schema=schema,
        tickbook=tickbook,
        trade_setup_geometry=False,
    )

    records = result["trades"].to_dict("records")
    submitted = next(event for event in records if event.get("type") == "order_submit")
    cancelled = next(event for event in records if event.get("type") == "order_cancel")
    assert cancelled["reason"] == expected_reason
    assert cancelled["trade_setup_candidate_id"] == candidate_id
    assert cancelled["trade_setup_source_event_id"] == submitted["trade_setup_source_event_id"]
    assert not any(event.get("type") in {"order_fill", "open"} for event in records)


def test_reversal_close_keeps_the_policy_decision_that_triggered_it() -> None:
    bars, features, _, schema, long_candidate_id, _ = _backtest_inputs()
    short_candidate_id = trade_setup_candidate_id("fvg_retest", "M1", -1)
    features["entry_idea_fvg_retest_M1_short"] = 1.0
    actions = [
        _action(schema, candidate_id=long_candidate_id, limit=False),
        _action(schema, candidate_id=short_candidate_id, limit=False),
    ]
    calls = 0

    def reverse_once(_observation: Any) -> Array:
        nonlocal calls
        action = actions[min(calls, len(actions) - 1)]
        calls += 1
        return action

    result = run_backtest(
        bars,
        features,
        reverse_once,
        obs_window=1,
        cost_model=CostModel(spread_points=0.0, point_size=0.25, commission_per_lot=0.0),
        hold_on_zero=True,
        block_overnight=False,
        trade_setup_actions=True,
        trade_setup_action_schema=schema,
        trade_setup_geometry=False,
    )
    events = result["trades"].to_dict("records")
    opens = [event for event in events if event.get("type") == "open"]
    reversal_close = next(
        event
        for event in events
        if event.get("type") == "close" and event.get("position_id") == opens[0]["position_id"]
    )
    decisions = result["policy_decisions"].set_index("decision_id")
    first_open_submit = next(
        event
        for event in events
        if event.get("type") == "order_submit" and event.get("order_id") == opens[0].get("order_id")
    )

    assert opens[0]["direction"] == 1
    assert (
        opens[0]["trade_setup_source_event_id"] == first_open_submit["trade_setup_source_event_id"]
    )
    assert (
        opens[0]["trade_setup_source_event_id"]
        == decisions.loc[opens[0]["decision_id"], "trade_setup_source_event_id"]
    )
    assert reversal_close["position_id"] == opens[0]["position_id"]
    assert reversal_close["decision_id"] in decisions.index
    assert decisions.loc[reversal_close["decision_id"], "action"] == -1


def test_limit_touch_and_trade_through_assumptions_are_explicit_sensitivities() -> None:
    bars, features, _, schema, candidate_id, limit_action = _backtest_inputs()
    tick_time = bars.index[2] + pd.Timedelta(seconds=30)
    exact_touch = TickBook(
        np.asarray([tick_time.value], dtype=np.int64),
        np.asarray([19_999.75]),
        np.asarray([20_000.0]),
    )

    def execute(require_trade_through: bool):
        selected = False
        no_trade_action = np.zeros(schema.width, dtype=np.float32)
        no_trade_action[schema.indices["trade_setup"]] = trade_setup_center(NO_TRADE_ID)
        no_trade_action[schema.indices["entry_execution"]] = -1.0

        def policy(observation: Any) -> Array:
            nonlocal selected
            mask = np.asarray(observation["trade_setup_mask"])
            if not selected and mask[candidate_id] > 0.0:
                selected = True
                return limit_action
            return no_trade_action

        return run_backtest(
            bars,
            features,
            policy,
            obs_window=1,
            cost_model=CostModel(spread_points=0.0, point_size=0.25, commission_per_lot=0.0),
            hold_on_zero=True,
            block_overnight=False,
            trade_setup_actions=True,
            trade_setup_action_schema=schema,
            trade_setup_geometry=False,
            tickbook=exact_touch,
            limit_order_require_trade_through=require_trade_through,
        )

    exact_result = execute(require_trade_through=False)
    conservative_result = execute(require_trade_through=True)
    assert exact_result["execution_contract"]["schema_version"] == (
        "backtest_execution_contract.v1"
    )
    assert exact_result["execution_contract"]["limit_order"]["require_trade_through"] is False
    assert exact_result["execution_contract"]["limit_order"]["fill_rule"] == (
        "executable_quote_exact_touch_or_better"
    )
    assert conservative_result["execution_contract"]["limit_order"]["require_trade_through"] is True
    assert conservative_result["execution_contract"]["limit_order"]["fill_rule"] == (
        "strict_executable_quote_trade_through"
    )
    sensitivity = compare_limit_execution_sensitivity(exact_result, conservative_result)
    assert sensitivity["status"] == "execution_contracts_match"
    assert sensitivity["limit_order_counts"]["paired"] == 1
    assert sensitivity["paired_limit_outcomes"][0]["exact_touch"]["status"] == "filled"
    assert sensitivity["paired_limit_outcomes"][0]["trade_through"]["status"] == "cancelled"
    exact_events = exact_result["trades"].to_dict("records")
    conservative_events = conservative_result["trades"].to_dict("records")

    exact_open = next(event for event in exact_events if event.get("type") == "open")
    assert exact_open["trade_setup_candidate_id"] == candidate_id
    assert exact_open["fill_time"] == tick_time
    assert not any(event.get("type") == "open" for event in conservative_events)
    assert any(
        event.get("type") == "order_cancel" and event.get("reason") == "limit_ttl_expired"
        for event in conservative_events
    )
    exact_reconciliation = reconcile_policy_decisions(
        exact_result["policy_decisions"], exact_result["trades"], exact_result["breach_events"]
    )
    assert exact_reconciliation["status"] == "matched", {
        "failures": exact_reconciliation["failures"],
        "incomplete_reasons": exact_reconciliation["incomplete_reasons"],
    }
    assert (
        reconcile_policy_decisions(
            conservative_result["policy_decisions"],
            conservative_result["trades"],
            conservative_result["breach_events"],
        )["status"]
        == "matched"
    )


def test_versioned_action_can_still_select_market_entry() -> None:
    bars, features, tickbook, schema, candidate_id, _ = _backtest_inputs()
    market_action = _action(schema, candidate_id=candidate_id, limit=False)

    result = run_backtest(
        bars,
        features,
        lambda _observation: market_action,
        obs_window=1,
        cost_model=CostModel(spread_points=0.0, point_size=0.25, commission_per_lot=0.0),
        hold_on_zero=True,
        block_overnight=False,
        trade_setup_actions=True,
        trade_setup_action_schema=schema,
        tickbook=None,
        trade_setup_geometry=False,
    )

    records = result["trades"].to_dict("records")
    opened = next(event for event in records if event.get("type") == "open")
    assert opened["fill_quote_source"] == "bar_open"
    assert opened["decision_bar_time"] == bars.index[1]
    assert opened["decision_time"] == bars.index[2]
    assert opened["order_submission_time"] == bars.index[2]
    assert not any(event.get("order_type") == "limit" for event in records)


def test_configured_cost_slippage_applies_to_bar_open_market_entry_by_default() -> None:
    bars, features, _, schema, candidate_id, _ = _backtest_inputs()
    result = run_backtest(
        bars,
        features,
        lambda _observation: _action(schema, candidate_id=candidate_id, limit=False),
        obs_window=1,
        cost_model=CostModel(
            spread_points=0.0,
            point_size=0.25,
            commission_per_lot=0.0,
            slippage_points=1.0,
        ),
        hold_on_zero=True,
        block_overnight=False,
        trade_setup_actions=True,
        trade_setup_action_schema=schema,
        trade_setup_geometry=False,
    )

    opened = next(
        event for event in result["trades"].to_dict("records") if event.get("type") == "open"
    )
    assert opened["fill_quote_source"] == "bar_open"
    assert opened["price"] == pytest.approx(20_001.0)
    assert opened["entry_slippage_applied"] is True
    assert opened["entry_slippage_points"] == pytest.approx(1.0)
    assert opened["fill_cost_provenance_schema_version"] == FILL_COST_PROVENANCE_SCHEMA_VERSION
    assert opened["pre_execution_quote_ask"] == pytest.approx(20_000.0)
    assert opened["broker_execution_quote_ask"] == pytest.approx(opened["price"])
    assert opened["slippage_points_applied_here"] == pytest.approx(1.0)
    assert result["market_fill_slippage_points"] == pytest.approx(1.0)


def test_limit_fill_stays_inside_bound_when_configured_slippage_is_nonzero() -> None:
    bars, features, tickbook, schema, candidate_id, limit_action = _backtest_inputs()
    tick_time = bars.index[2] + pd.Timedelta(seconds=1)
    tickbook = TickBook(
        np.asarray([tick_time.value], dtype=np.int64),
        np.asarray([19_999.0]),
        np.asarray([20_000.0]),
    )
    result = run_backtest(
        bars,
        features,
        lambda _observation: limit_action,
        obs_window=1,
        cost_model=CostModel(
            spread_points=0.0,
            point_size=0.25,
            commission_per_lot=0.0,
            slippage_points=5.0,
        ),
        hold_on_zero=True,
        block_overnight=False,
        trade_setup_actions=True,
        trade_setup_action_schema=schema,
        trade_setup_geometry=False,
        tickbook=tickbook,
    )

    records = result["trades"].to_dict("records")
    submitted = next(event for event in records if event.get("type") == "order_submit")
    opened = next(event for event in records if event.get("type") == "open")
    assert opened["price"] <= submitted["limit_price"]
    assert opened["entry_slippage_applied"] is False
    assert opened["fill_cost_provenance_schema_version"] == FILL_COST_PROVENANCE_SCHEMA_VERSION
    assert opened["slippage_applied_here"] is False
    assert opened["slippage_points_applied_here"] == pytest.approx(0.0)


def test_market_tick_slippage_is_included_before_risk_sizing() -> None:
    bars, features, _, schema, candidate_id, _ = _backtest_inputs()
    features["last_swing_low"] = 19_990.0
    features["last_swing_high"] = 20_030.0
    market_action = _action(schema, candidate_id=candidate_id, limit=False)
    market_action[schema.indices["exit"]] = -1.0
    fill_time = bars.index[2] + pd.Timedelta(seconds=30)
    quote_times = [
        fill_time,
        *(stamp + pd.Timedelta(seconds=1) for stamp in bars.index[3:]),
        bars.index[-1] + pd.Timedelta(minutes=1, seconds=1),
    ]
    tickbook = TickBook(
        np.asarray([stamp.value for stamp in quote_times], dtype=np.int64),
        np.full(len(quote_times), 20_000.0),
        np.full(len(quote_times), 20_000.25),
    )

    class GeometryStrategy:
        def sl_candidates(self, *, direction: int, row: pd.Series) -> list[tuple[str, float]]:
            column = "last_swing_low" if direction == 1 else "last_swing_high"
            return [(column, float(row[column]))]

        def sl_reference(self, *, direction: int, row: pd.Series) -> None:  # noqa: ARG002
            return None

    result = run_backtest(
        bars,
        features,
        lambda _observation: market_action,
        obs_window=1,
        cost_model=CostModel(spread_points=0.0, point_size=0.25, commission_per_lot=0.0),
        initial_balance=100_000.0,
        hold_on_zero=True,
        block_overnight=False,
        trade_setup_actions=True,
        trade_setup_action_schema=schema,
        tickbook=tickbook,
        tick_execution_required=True,
        tick_fill_slippage_points=0.5,
        strategy=GeometryStrategy(),
    )
    opened = next(
        event for event in result["trades"].to_dict("records") if event.get("type") == "open"
    )
    actual_stop_risk = (float(opened["price"]) - float(opened["sl_price"])) * float(opened["lots"])
    assert opened["price"] == pytest.approx(20_000.75)
    assert opened["fill_time"] == fill_time
    assert actual_stop_risk <= float(opened["risk_budget_usd"])


def test_limit_entry_sizes_from_intended_price_when_fill_improves() -> None:
    bars, features, _, schema, candidate_id, limit_action = _backtest_inputs()
    features["last_swing_low"] = 19_990.0
    features["last_swing_high"] = 20_030.0
    limit_action[schema.indices["risk"]] = 1.0
    limit_action[schema.indices["exit"]] = -1.0
    tick_time = bars.index[2] + pd.Timedelta(seconds=30)
    tickbook = TickBook(
        np.asarray([tick_time.value], dtype=np.int64),
        np.asarray([19_999.5]),
        np.asarray([19_999.75]),
    )

    class GeometryStrategy:
        def sl_candidates(self, *, direction: int, row: pd.Series) -> list[tuple[str, float]]:
            column = "last_swing_low" if direction == 1 else "last_swing_high"
            return [(column, float(row[column]))]

        def sl_reference(self, *, direction: int, row: pd.Series) -> None:  # noqa: ARG002
            return None

    result = run_backtest(
        bars,
        features,
        lambda _observation: limit_action,
        obs_window=1,
        cost_model=CostModel(spread_points=0.0, point_size=0.25, commission_per_lot=0.0),
        initial_balance=100_000.0,
        hold_on_zero=True,
        block_overnight=False,
        trade_setup_actions=True,
        trade_setup_action_schema=schema,
        tickbook=tickbook,
        strategy=GeometryStrategy(),
    )
    records = result["trades"].to_dict("records")
    submitted = next(event for event in records if event.get("type") == "order_submit")
    opened = next(event for event in records if event.get("type") == "open")
    assert opened["price"] < submitted["limit_price"]
    assert opened["risk_reference_price"] == pytest.approx(submitted["limit_price"])
    assert opened["sl_price"] == pytest.approx(19_990.0)
    assert opened["lots"] <= (opened["risk_budget_usd"] / 10.0) + 1e-9


def test_limit_choice_fails_closed_without_tickbook_but_market_choice_does_not() -> None:
    bars, features, _, schema, _, limit_action = _backtest_inputs()
    candidate_id = trade_setup_candidate_id("fvg_retest", "M1", 1)
    market_action = _action(schema, candidate_id=candidate_id, limit=False)

    with pytest.raises(TickExecutionUnavailable, match="require TickBook"):
        run_backtest(
            bars,
            features,
            lambda _observation: limit_action,
            obs_window=1,
            trade_setup_actions=True,
            trade_setup_action_schema=schema,
            block_overnight=False,
        )

    market_result = run_backtest(
        bars,
        features,
        lambda _observation: market_action,
        obs_window=1,
        hold_on_zero=True,
        block_overnight=False,
        trade_setup_actions=True,
        trade_setup_action_schema=schema,
        tickbook=None,
        trade_setup_geometry=False,
    )
    assert not market_result["trades"].empty


def test_event_backtest_limit_order_expires_without_ohlc_only_fill() -> None:
    bars, features, _, schema, candidate_id, limit_action = _backtest_inputs()
    # The bars cross the limit, but every executable ask stays above it.
    bars.loc[bars.index[2:4], ["low", "close", "high"]] = [19_998.0, 19_999.0, 20_001.0]
    tick_times = [bars.index[2] + pd.Timedelta(seconds=30)]
    tickbook = TickBook(
        np.asarray([timestamp.value for timestamp in tick_times], dtype=np.int64),
        np.asarray([20_000.25]),
        np.asarray([20_000.5]),
    )
    calls = 0
    no_trade = _action(schema, candidate_id=NO_TRADE_ID, limit=False)

    def enter_then_wait(_observation: object) -> Array:
        nonlocal calls
        calls += 1
        return limit_action if calls == 1 else no_trade

    result = run_backtest(
        bars,
        features,
        enter_then_wait,
        obs_window=1,
        cost_model=CostModel(spread_points=0.0, point_size=0.25, commission_per_lot=0.0),
        hold_on_zero=True,
        block_overnight=False,
        trade_setup_actions=True,
        trade_setup_action_schema=schema,
        tickbook=tickbook,
    )

    records = result["trades"].to_dict("records")
    assert any(event.get("reason") == "limit_ttl_expired" for event in records)
    assert not any(event.get("type") in {"order_fill", "open"} for event in records)
    pending_trace = result["account_state_trace"].loc[
        result["account_state_trace"]["pending_order_type"].eq("limit")
    ]
    assert not pending_trace.empty
    assert pending_trace["pending_order_direction"].eq(1).all()
    assert pending_trace["pending_order_limit_price"].notna().all()
    assert pending_trace["pending_order_expiry_time"].notna().all()


@pytest.mark.parametrize(
    ("source_change", "expected_reason"),
    (
        ("invalidates", "source_setup_invalidated"),
        ("replaces", "source_setup_replaced"),
        ("new_retest", "source_setup_replaced"),
        ("session_end", "session_end_before_limit_fill"),
        ("session_change", "session_changed_before_limit_fill"),
    ),
)
def test_event_backtest_cancels_limit_when_source_setup_or_session_ends(
    source_change: str, expected_reason: str
) -> None:
    bars, features, _, schema, _, limit_action = _backtest_inputs()
    limit_action[schema.indices["limit_ttl_bars"]] = 1.0
    if source_change == "invalidates":
        features.loc[bars.index[3], "fvg_bull_active"] = 0.0
    elif source_change == "replaces":
        features.loc[bars.index[3], "fvg_bull_retest_origin_time_ns"] = bars.index[2].value
    elif source_change == "new_retest":
        features.loc[bars.index[3], "fvg_bull_retest_confirmed_at_time_ns"] = bars.index[3].value
    elif source_change == "session_change":
        bars.loc[bars.index[2], "session_id"] = 1
    else:
        bars.loc[bars.index[4], "session"] = "asia"
    tick_time = bars.index[3] + pd.Timedelta(seconds=30)
    tickbook = TickBook(
        np.asarray([tick_time.value], dtype=np.int64),
        np.asarray([19_999.5]),
        np.asarray([19_999.75]),
    )
    calls = 0
    no_trade = _action(schema, candidate_id=NO_TRADE_ID, limit=False)

    def enter_once(_observation: object) -> Array:
        nonlocal calls
        calls += 1
        return limit_action if calls == 1 else no_trade

    result = run_backtest(
        bars,
        features,
        enter_once,
        obs_window=1,
        cost_model=CostModel(spread_points=0.0, point_size=0.25, commission_per_lot=0.0),
        hold_on_zero=True,
        block_overnight=source_change in {"session_end", "session_change"},
        trade_setup_actions=True,
        trade_setup_action_schema=schema,
        tickbook=tickbook,
        trade_setup_geometry=False,
    )

    records = result["trades"].to_dict("records")
    cancellation = next(event for event in records if event.get("type") == "order_cancel")
    assert cancellation["reason"] == expected_reason
    submit = next(event for event in records if event.get("type") == "order_submit")
    assert cancellation["trade_setup_candidate_id"] == submit["trade_setup_candidate_id"]
    assert cancellation["trade_setup_source_event_id"] == submit["trade_setup_source_event_id"]
    assert not any(event.get("type") in {"order_fill", "open"} for event in records)


def test_event_backtest_can_submit_new_setup_after_old_limit_source_expires() -> None:
    bars, features, _, schema, old_candidate_id, old_limit_action = _backtest_inputs()
    old_limit_action[schema.indices["limit_ttl_bars"]] = 1.0
    features.loc[bars.index[3], "fvg_bull_active"] = 0.0

    new_candidate_id = trade_setup_candidate_id("order_block", "M1", 1)
    features.loc[bars.index[3] :, "entry_idea_order_block_M1_long"] = 1.0
    features.loc[bars.index[3] :, "ob_bull_active"] = 1.0
    for field, scale in trade_setup_candidate_event_time_fields(new_candidate_id):
        features.loc[bars.index[3] :, field] = (
            bars.index[2].value / scale if field.endswith("origin_time_ms") else bars.index[3].value
        )

    old_order_fill_time = bars.index[3] + pd.Timedelta(seconds=30)
    tickbook = TickBook(
        np.asarray([old_order_fill_time.value], dtype=np.int64),
        np.asarray([19_999.5]),
        np.asarray([19_999.75]),
    )
    no_trade = _action(schema, candidate_id=NO_TRADE_ID, limit=False)
    new_limit_action = _action(schema, candidate_id=new_candidate_id, limit=True)
    decisions = 0

    def switch_to_new_setup(_observation: object) -> Array:
        nonlocal decisions
        decisions += 1
        if decisions == 1:
            return old_limit_action
        if decisions == 3:
            return new_limit_action
        return no_trade

    result = run_backtest(
        bars,
        features,
        switch_to_new_setup,
        obs_window=1,
        cost_model=CostModel(spread_points=0.0, point_size=0.25, commission_per_lot=0.0),
        hold_on_zero=True,
        block_overnight=False,
        trade_setup_actions=True,
        trade_setup_action_schema=schema,
        tickbook=tickbook,
        trade_setup_geometry=False,
    )

    records = result["trades"].to_dict("records")
    cancellations = [event for event in records if event.get("type") == "order_cancel"]
    submissions = [event for event in records if event.get("type") == "order_submit"]
    assert any(
        event.get("reason") == "source_setup_invalidated"
        and event.get("trade_setup_candidate_id") == old_candidate_id
        for event in cancellations
    )
    assert [event["trade_setup_candidate_id"] for event in submissions] == [
        old_candidate_id,
        new_candidate_id,
    ]
    assert not any(event.get("type") in {"order_fill", "open"} for event in records)


@pytest.mark.parametrize("idea", ("fvg_retest", "ifvg_retest"))
@pytest.mark.parametrize(
    ("zone_change", "expected_cancel_reason"),
    (
        ("remains_active", None),
        ("expires", "source_setup_invalidated"),
        ("replaced", "source_setup_replaced"),
    ),
)
def test_trading_env_limit_lifecycle_follows_retest_zone(
    idea: str,
    zone_change: str,
    expected_cancel_reason: str | None,
) -> None:
    bars = _make_bars(120)
    setup_features = pd.DataFrame(
        0.0,
        index=bars.index,
        columns=[name for _, name in trade_setup_candidate_feature_columns()],
    )
    features = pd.concat([_make_features(bars), setup_features], axis=1)
    features["atr_5"] = 1.0
    features["ema_21"] = bars["close"]
    candidate_id = trade_setup_candidate_id(idea, "M5", 1)
    if idea == "fvg_retest":
        features.loc[bars.index[65], "entry_idea_fvg_retest_M5_long"] = 1.0
        _add_m5_fvg_state(features, bars)
        if zone_change == "expires":
            features.loc[bars.index[66], "M5_fvg_bull_active"] = 0.0
        elif zone_change == "replaced":
            features.loc[bars.index[66], "M5_fvg_bull_retest_confirmed_at_time_ns"] = bars.index[
                66
            ].value
    else:
        features.loc[bars.index[65], "entry_idea_ifvg_retest_M5_long"] = 1.0
        features["M5_ifvg_bull_active"] = 0.0
        features.loc[bars.index[65] :, "M5_ifvg_bull_active"] = 1.0
        features["M5_ifvg_bull_confirmed_at_time_ns"] = np.nan
        features.loc[bars.index[65] :, "M5_ifvg_bull_confirmed_at_time_ns"] = bars.index[64].value
        features["M5_ifvg_bull_retest_confirmed_at_time_ns"] = np.nan
        features.loc[bars.index[65], "M5_ifvg_bull_retest_confirmed_at_time_ns"] = bars.index[
            65
        ].value
        features["M5_ifvg_bull_fvg_origin_time_ns"] = np.nan
        features.loc[bars.index[65] :, "M5_ifvg_bull_fvg_origin_time_ns"] = bars.index[63].value
        if zone_change == "expires":
            features.loc[bars.index[66], "M5_ifvg_bull_active"] = 0.0
        elif zone_change == "replaced":
            features.loc[bars.index[66], "M5_ifvg_bull_confirmed_at_time_ns"] = bars.index[66].value
    tick_time = bars.index[66].tz_convert("UTC") + pd.Timedelta(seconds=30)
    tickbook = TickBook(
        np.asarray([tick_time.value], dtype=np.int64),
        np.asarray([float(bars.iloc[65]["close"]) - 0.5]),
        np.asarray([float(bars.iloc[65]["close"]) - 0.25]),
    )
    env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=10,
        strategy_actions=True,
        trade_setup_actions=True,
        agent_entry_execution=True,
        tickbook=tickbook,
        strategy=_SwingGeometryStrategy(),
        cost_model=CostModel(spread_points=0.0, point_size=0.25, commission_per_lot=0.0),
        tick_fill_slippage_points=1.0,
        tick_execution_required=True,
        open_manipulation_bars=0,
        block_overnight=False,
        max_episode_steps=10,
    )
    env.reset(seed=5)
    env.step_idx = 65
    env._ny_pos = int(np.searchsorted(env._ny_indices, env.step_idx))
    schema = _trade_setup_schema(env)
    action = _action(schema, candidate_id=candidate_id, limit=True)

    _, _, _, _, info = env.step(action)
    assert env.position is None
    assert env._pending_entry_order is not None, (info, env.trade_log)
    pending_trace = info["account_state_snapshot"]
    assert pending_trace["pending_order_type"] == "limit"
    assert pending_trace["pending_order_limit_price"] == pytest.approx(
        env._pending_entry_order["limit_price"]
    )
    assert pending_trace["pending_order_expiry_time"] == str(
        env._pending_entry_order["expiry_time"]
    )
    _, _, _, _, fill_info = env.step(_action(schema, candidate_id=NO_TRADE_ID, limit=False))
    assert fill_info["account_state_snapshot"]["pending_order_type"] is None

    submit = next(event for event in env.trade_log if event.get("type") == "order_submit")
    fill = next(
        (event for event in env.trade_log if event.get("type") == "order_fill"),
        None,
    )
    opened = next((event for event in env.trade_log if event.get("type") == "open"), None)
    assert submit["order_type"] == "limit"
    if expected_cancel_reason is None:
        assert fill is not None and opened is not None, (fill_info, env.trade_log)
        assert fill["decision_id"] == submit["decision_id"]
        assert fill["trade_setup_candidate_id"] == submit["trade_setup_candidate_id"]
        assert fill["trade_setup_source_event_id"] == submit["trade_setup_source_event_id"]
        assert fill["time"] == tick_time
        assert fill["ask"] <= fill["limit_price"]
        assert opened["fill_time"] == tick_time
        assert opened["fill_quote_source"] == "tick"
        assert opened.get("order_id") == submit["order_id"], (opened, submit)
        assert opened["price"] == fill["price"]
        assert opened["price"] <= fill["limit_price"]
    else:
        assert fill is None and opened is None
        cancellation = next(event for event in env.trade_log if event.get("type") == "order_cancel")
        assert cancellation["reason"] == expected_cancel_reason
        assert cancellation["decision_id"] == submit["decision_id"]
        assert cancellation["trade_setup_candidate_id"] == submit["trade_setup_candidate_id"]
        assert cancellation["trade_setup_source_event_id"] == submit["trade_setup_source_event_id"]


def test_limit_latency_is_paired_across_environment_and_event_backtest() -> None:
    bars, features, _, schema, candidate_id, limit_action = _backtest_inputs()
    features["last_swing_low"] = bars["close"] - 20.0
    features["last_swing_high"] = bars["close"] + 40.0
    limit_action[schema.indices["limit_ttl_bars"]] = 1.0
    no_trade = _action(schema, candidate_id=NO_TRADE_ID, limit=False)
    submission_time = bars.index[3]
    limit_price = float(bars.iloc[1]["close"])
    tick_times = np.asarray(
        [
            *(
                (submission_time + pd.Timedelta(milliseconds=offset)).value
                for offset in range(1, 11)
            ),
            *((stamp + pd.Timedelta(seconds=1)).value for stamp in bars.index[4:]),
            (bars.index[-1] + pd.Timedelta(minutes=1, seconds=1)).value,
        ],
        dtype=np.int64,
    )
    tickbook = TickBook(
        tick_times,
        np.full(len(tick_times), limit_price - 0.25),
        np.full(len(tick_times), limit_price),
    )

    env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=1,
        strategy_actions=True,
        trade_setup_actions=True,
        agent_entry_execution=True,
        tickbook=tickbook,
        strategy=_SwingGeometryStrategy(),
        cost_model=CostModel(spread_points=0.0, point_size=0.25, commission_per_lot=0.0),
        randomized_fill_latency_ms=10.0,
        tick_execution_required=True,
        open_manipulation_bars=0,
        block_overnight=False,
        max_episode_steps=10,
    )
    env.reset(seed=42)
    env.step_idx = 1
    env._ny_pos = int(np.searchsorted(env._ny_indices, env.step_idx))
    env.step(limit_action)
    env.step(no_trade)
    env.step(no_trade)

    decisions = 0

    def enter_on_second_decision(_observation: object) -> Array:
        nonlocal decisions
        decisions += 1
        return limit_action if decisions == 2 else no_trade

    result = run_backtest(
        bars,
        features,
        enter_on_second_decision,
        obs_window=1,
        cost_model=CostModel(spread_points=0.0, point_size=0.25, commission_per_lot=0.0),
        hold_on_zero=True,
        block_overnight=False,
        trade_setup_actions=True,
        trade_setup_action_schema=schema,
        tickbook=tickbook,
        strategy=_SwingGeometryStrategy(),
        tick_execution_required=True,
        randomized_fill_latency_ms=10.0,
        execution_seed=42,
    )

    environment_fill = next(
        (event for event in env.trade_log if event.get("type") == "order_fill"), None
    )
    assert environment_fill is not None, env.trade_log
    backtest_fill = next(
        event for event in result["trades"].to_dict("records") if event.get("type") == "order_fill"
    )
    assert environment_fill["time"] == backtest_fill["time"]
    assert environment_fill["time"] in pd.to_datetime(tick_times, unit="ns", utc=True)
    assert environment_fill["ask"] == backtest_fill["ask"] == limit_price
    assert environment_fill["limit_price"] == backtest_fill["limit_price"]
    for ledger in (
        env.trade_log,
        result["trades"].to_dict("records"),
    ):
        submit = next(event for event in ledger if event.get("type") == "order_submit")
        fill = next(event for event in ledger if event.get("type") == "order_fill")
        opened = next(event for event in ledger if event.get("type") == "open")
        source_event_id = submit["trade_setup_source_event_id"]
        assert source_event_id
        assert fill["trade_setup_source_event_id"] == source_event_id
        assert opened["trade_setup_source_event_id"] == source_event_id


@pytest.mark.parametrize(
    ("cancel_cause", "expected_reason"),
    (
        ("source_setup_invalidates", "source_setup_invalidated"),
        ("source_setup_replaced", "source_setup_replaced"),
        ("new_retest_confirmation", "source_setup_replaced"),
        ("session_changes", "session_changed_before_limit_fill"),
        ("session_ends", "session_end_before_limit_fill"),
    ),
)
def test_trading_env_cancels_limit_before_fill_for_setup_or_session_change(
    cancel_cause: str, expected_reason: str
) -> None:
    bars = _make_bars(120)
    setup_features = pd.DataFrame(
        0.0,
        index=bars.index,
        columns=[name for _, name in trade_setup_candidate_feature_columns()],
    )
    features = pd.concat([_make_features(bars), setup_features], axis=1)
    features["atr_5"] = 1.0
    features["ema_21"] = bars["close"]
    candidate_id = trade_setup_candidate_id("fvg_retest", "M5", 1)
    features.loc[bars.index[65], "entry_idea_fvg_retest_M5_long"] = 1.0
    _add_m5_fvg_state(features, bars)
    if cancel_cause == "source_setup_invalidates":
        features.loc[bars.index[66], "M5_fvg_bull_active"] = 0.0
    elif cancel_cause == "source_setup_replaced":
        features.loc[bars.index[66], "M5_fvg_bull_retest_origin_time_ns"] = bars.index[63].value
    elif cancel_cause == "new_retest_confirmation":
        features.loc[bars.index[66], "M5_fvg_bull_retest_confirmed_at_time_ns"] = bars.index[
            66
        ].value
    elif cancel_cause == "session_changes":
        bars.loc[bars.index[68], "session_id"] = 1
    else:
        bars["session"] = "ny"
        bars.loc[bars.index[68] :, "session"] = "asia"
    tick_index = 68 if cancel_cause in {"session_changes", "session_ends"} else 67
    tick_time = bars.index[tick_index].tz_convert("UTC") + pd.Timedelta(seconds=30)
    limit_price = float(bars.iloc[65]["close"])
    tickbook = TickBook(
        np.asarray([tick_time.value], dtype=np.int64),
        np.asarray([limit_price - 0.5]),
        np.asarray([limit_price - 0.25]),
    )
    env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=10,
        strategy_actions=True,
        trade_setup_actions=True,
        agent_entry_execution=True,
        tickbook=tickbook,
        cost_model=CostModel(spread_points=0.0, point_size=0.25, commission_per_lot=0.0),
        tick_execution_required=True,
        open_manipulation_bars=0,
        block_overnight=cancel_cause in {"session_changes", "session_ends"},
        max_episode_steps=10,
    )
    env.reset(seed=5)
    env.step_idx = 65
    env._ny_pos = int(np.searchsorted(env._ny_indices, env.step_idx))
    schema = _trade_setup_schema(env)
    action = _action(schema, candidate_id=candidate_id, limit=True)
    action[schema.indices["limit_ttl_bars"]] = 1.0

    env.step(action)
    assert env._pending_entry_order is not None
    no_trade = _action(schema, candidate_id=NO_TRADE_ID, limit=False)
    env.step(no_trade)
    if cancel_cause in {"session_changes", "session_ends"}:
        env.step(no_trade)
    if cancel_cause == "session_changes":
        env.step(no_trade)

    assert env.position is None
    assert env._pending_entry_order is None
    assert any(
        event.get("type") == "order_cancel" and event.get("reason") == expected_reason
        for event in env.trade_log
    )
    submit = next(event for event in env.trade_log if event.get("type") == "order_submit")
    cancel = next(
        event
        for event in env.trade_log
        if event.get("type") == "order_cancel" and event.get("reason") == expected_reason
    )
    assert cancel["trade_setup_candidate_id"] == submit["trade_setup_candidate_id"]
    assert cancel["trade_setup_source_event_id"] == submit["trade_setup_source_event_id"]
    assert not any(event.get("type") in {"order_fill", "open"} for event in env.trade_log)


def test_trading_env_can_submit_new_setup_after_old_limit_source_expires() -> None:
    bars = _make_bars(120)
    setup_features = pd.DataFrame(
        0.0,
        index=bars.index,
        columns=[name for _, name in trade_setup_candidate_feature_columns()],
    )
    features = pd.concat([_make_features(bars), setup_features], axis=1)
    features["atr_5"] = 1.0
    features["ema_21"] = bars["close"]

    old_candidate_id = trade_setup_candidate_id("fvg_retest", "M5", 1)
    features.loc[bars.index[65], "entry_idea_fvg_retest_M5_long"] = 1.0
    _add_m5_fvg_state(features, bars)
    features.loc[bars.index[66], "M5_fvg_bull_active"] = 0.0

    new_candidate_id = trade_setup_candidate_id("order_block", "M5", 1)
    features.loc[bars.index[66] :, "entry_idea_order_block_M5_long"] = 1.0
    features.loc[bars.index[66] :, "M5_ob_bull_active"] = 1.0
    for field, scale in trade_setup_candidate_event_time_fields(new_candidate_id):
        features.loc[bars.index[66] :, field] = (
            bars.index[64].value / scale
            if field.endswith("origin_time_ms")
            else bars.index[66].value
        )

    tick_time = bars.index[67].tz_convert("UTC") + pd.Timedelta(seconds=30)
    old_limit_price = float(bars.iloc[65]["close"])
    tickbook = TickBook(
        np.asarray([tick_time.value], dtype=np.int64),
        np.asarray([old_limit_price - 0.5]),
        np.asarray([old_limit_price - 0.25]),
    )
    env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=10,
        strategy_actions=True,
        trade_setup_actions=True,
        agent_entry_execution=True,
        tickbook=tickbook,
        cost_model=CostModel(spread_points=0.0, point_size=0.25, commission_per_lot=0.0),
        tick_execution_required=True,
        open_manipulation_bars=0,
        block_overnight=False,
        max_episode_steps=10,
    )
    env.reset(seed=5)
    env.step_idx = 65
    env._ny_pos = int(np.searchsorted(env._ny_indices, env.step_idx))
    schema = _trade_setup_schema(env)
    old_limit_action = _action(schema, candidate_id=old_candidate_id, limit=True)
    old_limit_action[schema.indices["limit_ttl_bars"]] = 1.0
    new_limit_action = _action(schema, candidate_id=new_candidate_id, limit=True)

    env.step(old_limit_action)
    env.step(new_limit_action)

    submissions = [event for event in env.trade_log if event.get("type") == "order_submit"]
    cancellations = [event for event in env.trade_log if event.get("type") == "order_cancel"]
    assert [event["trade_setup_candidate_id"] for event in submissions] == [
        old_candidate_id,
        new_candidate_id,
    ]
    assert any(
        event.get("reason") == "source_setup_invalidated"
        and event.get("trade_setup_candidate_id") == old_candidate_id
        for event in cancellations
    )
    assert env.position is None
    assert env._pending_entry_order is not None
    assert env._pending_entry_order["selected"]["_selected_trade_setup"].candidate_id == (
        new_candidate_id
    )


def test_trading_env_exact_touch_and_trade_through_are_explicit_sensitivities() -> None:
    bars = _make_bars(120)
    setup_features = pd.DataFrame(
        0.0,
        index=bars.index,
        columns=[name for _, name in trade_setup_candidate_feature_columns()],
    )
    features = pd.concat([_make_features(bars), setup_features], axis=1)
    features["atr_5"] = 1.0
    features["ema_21"] = bars["close"]
    candidate_id = trade_setup_candidate_id("fvg_retest", "M5", 1)
    features.loc[bars.index[65], "entry_idea_fvg_retest_M5_long"] = 1.0
    _add_m5_fvg_state(features, bars)
    exact_fill_time = bars.index[66].tz_convert("UTC") + pd.Timedelta(seconds=30)
    point_size = 0.25
    raw_limit = float(bars.iloc[65]["close"])
    exact_limit = np.floor(raw_limit / point_size) * point_size
    tickbook = TickBook(
        np.asarray([exact_fill_time.value], dtype=np.int64),
        np.asarray([exact_limit - 0.25]),
        np.asarray([exact_limit]),
    )

    def execute(require_trade_through: bool) -> TradingEnv:
        env = TradingEnv(
            bars=bars,
            features=features,
            obs_window=10,
            strategy_actions=True,
            trade_setup_actions=True,
            agent_entry_execution=True,
            entry_state_machine=True,
            tickbook=tickbook,
            cost_model=CostModel(spread_points=0.0, point_size=0.25, commission_per_lot=0.0),
            tick_execution_required=True,
            limit_order_require_trade_through=require_trade_through,
            open_manipulation_bars=0,
            block_overnight=False,
            max_episode_steps=10,
        )
        env.reset(seed=5)
        env.step_idx = 65
        env._ny_pos = int(np.searchsorted(env._ny_indices, env.step_idx))
        action_schema = _trade_setup_schema(env)
        action = _action(action_schema, candidate_id=candidate_id, limit=True)
        env.step(action)
        env.step(_action(action_schema, candidate_id=NO_TRADE_ID, limit=False))
        return env

    exact_env = execute(require_trade_through=False)
    conservative_env = execute(require_trade_through=True)

    assert exact_env.position is not None
    assert exact_env.position.entry_timestamp == exact_fill_time
    assert exact_env.entry_state_machine is not None
    assert exact_env.entry_state_machine.state == "IN_POSITION"
    assert exact_env.entry_state_machine.entered == 1
    assert conservative_env.position is None
    assert conservative_env._pending_entry_order is None
    assert any(
        event.get("type") == "order_cancel" and event.get("reason") == "limit_ttl_expired"
        for event in conservative_env.trade_log
    )


def test_trading_env_applies_market_slippage_to_bar_open_quotes() -> None:
    bars = _make_bars(120)
    setup_features = pd.DataFrame(
        0.0,
        index=bars.index,
        columns=[name for _, name in trade_setup_candidate_feature_columns()],
    )
    features = pd.concat([_make_features(bars), setup_features], axis=1)
    features["atr_5"] = 1.0
    features["ema_21"] = bars["close"]
    candidate_id = trade_setup_candidate_id("fvg_retest", "M5", 1)
    features.loc[bars.index[65], "entry_idea_fvg_retest_M5_long"] = 1.0
    _add_m5_fvg_state(features, bars)

    def market_open(slippage: float) -> dict[str, object]:
        env = TradingEnv(
            bars=bars,
            features=features,
            obs_window=10,
            strategy_actions=True,
            trade_setup_actions=True,
            agent_entry_execution=True,
            cost_model=CostModel(
                spread_points=0.0,
                point_size=0.25,
                slippage_points=slippage,
            ),
            tick_fill_slippage_points=slippage,
            tick_execution_required=False,
            open_manipulation_bars=0,
            block_overnight=False,
            max_episode_steps=10,
        )
        env.reset(seed=5)
        env.step_idx = 65
        env._ny_pos = int(np.searchsorted(env._ny_indices, env.step_idx))
        env.step(_action(_trade_setup_schema(env), candidate_id=candidate_id, limit=False))
        return next(event for event in env.trade_log if event.get("type") == "open")

    no_slippage = market_open(0.0)
    configured_slippage = market_open(1.0)
    assert no_slippage["fill_quote_source"] in {"bar_open", "tick"}
    assert configured_slippage["fill_quote_source"] in {"bar_open", "tick"}
    assert configured_slippage["price"] == pytest.approx(_event_number(no_slippage, "price") + 1.0)
    assert configured_slippage["entry_slippage_applied"] is True


def test_trading_env_does_not_replace_a_resting_limit_order() -> None:
    bars = _make_bars(120)
    setup_features = pd.DataFrame(
        0.0,
        index=bars.index,
        columns=[name for _, name in trade_setup_candidate_feature_columns()],
    )
    features = pd.concat([_make_features(bars), setup_features], axis=1)
    features["atr_5"] = 1.0
    features["ema_21"] = bars["close"]
    candidate_id = trade_setup_candidate_id("fvg_retest", "M5", 1)
    features.loc[bars.index[65:], "entry_idea_fvg_retest_M5_long"] = 1.0
    _add_m5_fvg_state(features, bars)
    start = bars.index[66].tz_convert("UTC")
    tickbook = TickBook(
        np.asarray([(start + pd.Timedelta(seconds=30)).value], dtype=np.int64),
        np.asarray([float(bars.iloc[65]["close"]) + 1.0]),
        np.asarray([float(bars.iloc[65]["close"]) + 1.25]),
    )
    env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=10,
        strategy_actions=True,
        trade_setup_actions=True,
        agent_entry_execution=True,
        tickbook=tickbook,
        open_manipulation_bars=0,
        block_overnight=False,
        max_episode_steps=10,
    )
    env.reset(seed=5)
    env.step_idx = 65
    env._ny_pos = int(np.searchsorted(env._ny_indices, env.step_idx))
    schema = _trade_setup_schema(env)
    limit_action = _action(schema, candidate_id=candidate_id, limit=True)
    limit_action[schema.indices["limit_ttl_bars"]] = -0.85
    env.step(limit_action)
    original = env._pending_entry_order
    assert original is not None

    _, _, _, _, info = env.step(limit_action)

    assert env._pending_entry_order is original, (info, env.trade_log)
    assert sum(event.get("type") == "order_submit" for event in env.trade_log) == 1
    assert info["entry_rejection_reason"] == "entry_pending"


def test_trading_env_requires_tickbook_only_when_limit_choice_is_selected() -> None:
    bars = _make_bars(120)
    setup_features = pd.DataFrame(
        0.0,
        index=bars.index,
        columns=[name for _, name in trade_setup_candidate_feature_columns()],
    )
    features = pd.concat([_make_features(bars), setup_features], axis=1)
    features["atr_5"] = 1.0
    candidate_id = trade_setup_candidate_id("fvg_retest", "M5", 1)
    features.loc[bars.index[65], "entry_idea_fvg_retest_M5_long"] = 1.0
    _add_m5_fvg_state(features, bars)

    def make_env() -> TradingEnv:
        env = TradingEnv(
            bars=bars,
            features=features,
            obs_window=10,
            strategy_actions=True,
            trade_setup_actions=True,
            agent_entry_execution=True,
            open_manipulation_bars=0,
            block_overnight=False,
            max_episode_steps=10,
        )
        env.reset(seed=5)
        env.step_idx = 65
        env._ny_pos = int(np.searchsorted(env._ny_indices, env.step_idx))
        return env

    market_env = make_env()
    market_action = _action(_trade_setup_schema(market_env), candidate_id=candidate_id, limit=False)
    market_env.step(market_action)
    assert not any(event.get("order_type") == "limit" for event in market_env.trade_log)

    limit_env = make_env()
    limit_action = _action(_trade_setup_schema(limit_env), candidate_id=candidate_id, limit=True)
    with pytest.raises(TickExecutionUnavailable, match="require TickBook"):
        limit_env.step(limit_action)
