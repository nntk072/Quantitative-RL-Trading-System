from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd
import pytest

from decisioning.observation_state import entry_state_one_hot
from decisioning.observations import (
    OBSERVATION_SCHEMA_V1,
    OBSERVATION_SCHEMA_V2,
    OBSERVATION_SCHEMA_V3,
    account_state_v2,
    build_observation_schema,
)
from decisioning.trade_setup import (
    TRADE_SETUP_CATEGORY_COUNT,
    TradeSetupActionSchema,
    build_trade_setup_action_schema,
    trade_setup_candidate_id,
    trade_setup_center,
)
from evaluation.reporting.policy_decision_reconciliation import reconcile_policy_decisions
from features.context.trade_setup_candidates import trade_setup_candidate_feature_columns
from simulation.backtest import run_backtest
from simulation.environment.env import TradingEnv
from trading.execution import CostModel
from trading.strategies import BaselineStrategy

Array = np.ndarray[Any, Any]


def _event_number(event: Mapping[Any, Any], key: str) -> float:
    value = event[key]
    assert isinstance(value, (int, float))
    return float(value)


class _GeometryStrategy:
    def sl_candidates(self, *, direction: int, row: pd.Series) -> list[tuple[str, float]]:
        column = "last_swing_low" if direction == 1 else "last_swing_high"
        value = float(row[column]) if column in row.index else float("nan")
        return [(column, value)] if np.isfinite(value) else []

    def sl_reference(self, *, direction: int, row: pd.Series) -> None:  # noqa: ARG002
        return None


def test_opt_in_setup_mask_rejects_inactive_candidate_and_keeps_scalar_default() -> None:
    index = pd.date_range("2025-01-06 14:30", periods=5, freq="1min", tz="UTC")
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
    costs = CostModel(spread_points=0.0, point_size=0.01, commission_per_lot=0.0)

    env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=1,
        strategy_actions=True,
        trade_setup_actions=True,
        cost_model=costs,
        block_overnight=False,
        max_episode_steps=len(bars),
        episodic=False,
    )
    assert isinstance(env.action_schema, TradeSetupActionSchema)
    observation, _ = env.reset(seed=7)
    candidate_id = trade_setup_candidate_id("fvg_retest", "M1", 1)
    assert observation["trade_setup_mask"].sum() == 1.0

    action = np.zeros(env.action_schema.width, dtype=np.float32)
    action[env.action_schema.indices["trade_setup"]] = trade_setup_center(candidate_id)
    _, _, _, _, info = env.step(action)
    assert info["trade_setup_eligible"] is False
    assert any(
        event.get("entry_rejection_reason") == "trade_setup_inactive" for event in env.trade_log
    )
    assert not any(event.get("type") in {"order_submit", "open"} for event in env.trade_log)

    backtest = run_backtest(
        bars,
        features,
        lambda _observation: 1,
        obs_window=1,
        cost_model=costs,
        hold_on_zero=True,
        block_overnight=False,
    )
    assert "open" in backtest["trades"]["type"].tolist()

    schema = env.action_schema
    assert isinstance(schema, TradeSetupActionSchema)
    setup_action = np.zeros(schema.width, dtype=np.float32)
    setup_action[schema.indices["trade_setup"]] = trade_setup_center(candidate_id)
    setup_action[schema.indices["stop"]] = -0.4
    setup_action[schema.indices["target"]] = 0.8
    setup_action[schema.indices["exit"]] = -1.0

    policy_observations: list[dict[str, Array]] = []

    def choose_setup(observation: Any) -> Array:
        policy_observations.append(
            {name: np.asarray(value).copy() for name, value in observation.items()}
        )
        assert observation["seq"].shape[0] == 1
        np.testing.assert_array_equal(observation["seq_mask"], np.ones(1, dtype=np.float32))
        assert observation["account"].shape == (6,)
        assert observation["trade_setup_mask"].shape == (TRADE_SETUP_CATEGORY_COUNT,)
        return setup_action

    masked_backtest = run_backtest(
        bars,
        features,
        choose_setup,
        obs_window=1,
        cost_model=costs,
        hold_on_zero=True,
        block_overnight=False,
        trade_setup_actions=True,
        trade_setup_action_schema=schema,
        strategy=_GeometryStrategy(),
    )
    assert policy_observations
    expected_observations: list[dict[str, Array]] = []
    env_observation, _ = env.reset(seed=7)
    for _ in policy_observations:
        expected_observations.append(
            {name: np.asarray(value).copy() for name, value in env_observation.items()}
        )
        env_observation, _, terminated, truncated, _ = env.step(setup_action)
        assert not terminated
        assert not truncated
    assert len(expected_observations) == len(policy_observations)
    for decision_idx, (actual, expected) in enumerate(
        zip(policy_observations, expected_observations, strict=True)
    ):
        assert set(actual) == set(expected), f"observation keys at decision {decision_idx}"
        for name, expected_value in expected.items():
            np.testing.assert_array_equal(
                actual[name], expected_value, err_msg=f"decision {decision_idx}: {name}"
            )
    assert not (masked_backtest["trades"]["type"] == "open").any()
    rejection = next(
        event
        for event in masked_backtest["trades"].to_dict("records")
        if event.get("reason") == "trade_setup_inactive"
    )
    assert rejection["trade_setup_candidate_id"] == candidate_id
    rejection_decision = (
        masked_backtest["policy_decisions"].set_index("decision_id").loc[rejection["decision_id"]]
    )
    assert rejection_decision["trade_setup_candidate_id"] == candidate_id
    assert not bool(rejection_decision["trade_setup_eligible"])
    rejection_reconciliation = reconcile_policy_decisions(
        masked_backtest["policy_decisions"], masked_backtest["trades"], []
    )
    assert rejection_reconciliation["status"] == "matched", {
        "failures": rejection_reconciliation["failures"],
        "incomplete_reasons": rejection_reconciliation["incomplete_reasons"],
    }

    active_features = features.copy()
    active_features["entry_idea_fvg_retest_M1_long"] = 1.0
    active_features["atr_5"] = 10.0
    active_features["last_swing_low"] = 19_990.0
    active_features["last_swing_high"] = 20_010.0
    active_features["fvg_bull_active"] = 1.0
    index_ns = np.asarray(index, dtype="datetime64[ns]").view("i8")
    active_features["fvg_bull_retest_confirmed_at_time_ns"] = index_ns
    active_features["fvg_bull_retest_origin_time_ns"] = index_ns - 60_000_000_000
    active_env = TradingEnv(
        bars=bars,
        features=active_features,
        obs_window=1,
        strategy_actions=True,
        trade_setup_actions=True,
        cost_model=costs,
        block_overnight=False,
        max_episode_steps=len(bars),
        episodic=False,
    )
    expected_active_observation, _ = active_env.reset(seed=7)
    assert expected_active_observation["trade_setup_mask"][candidate_id] == 1.0
    active_observation_start = len(policy_observations)
    active_backtest = run_backtest(
        bars,
        active_features,
        choose_setup,
        obs_window=1,
        cost_model=costs,
        hold_on_zero=True,
        block_overnight=False,
        trade_setup_actions=True,
        trade_setup_action_schema=schema,
        strategy=_GeometryStrategy(),
    )
    actual_active_observation = policy_observations[active_observation_start]
    assert set(actual_active_observation) == set(expected_active_observation)
    for name, expected_value in expected_active_observation.items():
        np.testing.assert_array_equal(
            actual_active_observation[name], expected_value, err_msg=f"active setup: {name}"
        )
    setup_open = next(
        event
        for event in active_backtest["trades"].to_dict("records")
        if event.get("type") == "open"
    )
    assert setup_open["trade_setup_candidate_id"] == candidate_id
    market_submit = next(
        event
        for event in active_backtest["trades"].to_dict("records")
        if event.get("type") == "order_submit" and event.get("order_type") == "market"
    )
    assert market_submit["decision_id"] == setup_open["decision_id"]
    assert market_submit["order_id"] == setup_open["order_id"]
    assert any(
        event.get("position_id") == setup_open["position_id"]
        and event.get("type") in {"close", "stop_close", "tp_close", "forced_close", "eod_close"}
        for event in active_backtest["trades"].to_dict("records")
    )
    setup_decision = (
        active_backtest["policy_decisions"].set_index("decision_id").loc[setup_open["decision_id"]]
    )
    assert setup_decision["trade_setup_candidate_id"] == candidate_id
    assert bool(setup_decision["trade_setup_eligible"])
    assert setup_decision["eligibility_status"] == "eligible"

    assert setup_open["trade_setup_idea"] == "fvg_retest"
    assert setup_open["trade_setup_timeframe"] == "M1"
    assert setup_open["sl_price"] is not None
    assert setup_open["tp_price"] is not None
    assert setup_open["exit_mode"] == "structural"
    selected_geometry = setup_open["selected_geometry_action"]
    assert selected_geometry["stop_anchor_fraction"] == pytest.approx(0.6)
    assert selected_geometry["target_fraction"] == pytest.approx(0.9)
    assert selected_geometry["target_selections"] is None
    assert selected_geometry["simplex_logits"] is None
    assert selected_geometry["exit_mode"] == "structural"

    rejecting_backtest = run_backtest(
        bars,
        active_features,
        choose_setup,
        obs_window=1,
        cost_model=costs,
        hold_on_zero=True,
        block_overnight=False,
        trade_setup_actions=True,
        trade_setup_action_schema=schema,
        strategy=_GeometryStrategy(),
        broker_kwargs={"margin_pct": 100_000.0},
    )
    rejection = next(
        event
        for event in rejecting_backtest["trades"].to_dict("records")
        if event.get("type") == "reject" and event.get("reason") == "insufficient_margin"
    )
    rejected_decision = (
        rejecting_backtest["policy_decisions"]
        .set_index("decision_id")
        .loc[rejection["decision_id"]]
    )
    assert rejection["trade_setup_candidate_id"] == candidate_id
    assert (
        rejection["trade_setup_source_event_id"] == rejected_decision["trade_setup_source_event_id"]
    )
    assert rejection["trade_setup_source_event_identity_status"] == "identified"
    rejection_reconciliation = reconcile_policy_decisions(
        rejecting_backtest["policy_decisions"], rejecting_backtest["trades"], []
    )
    assert rejection_reconciliation["status"] == "matched", rejection_reconciliation

    short_candidate_id = trade_setup_candidate_id("fvg_retest", "M1", -1)
    short_features = features.copy()
    short_features["entry_idea_fvg_retest_M1_short"] = 1.0
    short_features["atr_5"] = 10.0
    short_features["last_swing_low"] = 19_990.0
    short_features["last_swing_high"] = 20_010.0
    short_action = np.zeros(schema.width, dtype=np.float32)
    short_action[schema.indices["trade_setup"]] = trade_setup_center(short_candidate_id)
    short_action[schema.indices["exit"]] = -1.0

    def choose_short_setup(observation: Any) -> Array:
        assert observation["trade_setup_mask"][short_candidate_id] == 1.0
        return short_action

    short_backtest = run_backtest(
        bars,
        short_features,
        choose_short_setup,
        obs_window=1,
        cost_model=costs,
        hold_on_zero=True,
        block_overnight=False,
        trade_setup_actions=True,
        trade_setup_action_schema=schema,
        strategy=_GeometryStrategy(),
    )
    short_open = next(
        event
        for event in short_backtest["trades"].to_dict("records")
        if event.get("type") == "open"
    )
    assert short_open["direction"] == -1
    assert short_open["trade_setup_candidate_id"] == short_candidate_id

    delayed_backtest = run_backtest(
        bars,
        active_features,
        choose_setup,
        obs_window=1,
        cost_model=costs,
        hold_on_zero=True,
        block_overnight=False,
        fill_latency_bars=1,
        trade_setup_actions=True,
        trade_setup_action_schema=schema,
        strategy=_GeometryStrategy(),
    )
    submitted_setup = next(
        event
        for event in delayed_backtest["trades"].to_dict("records")
        if event.get("type") == "order_submit"
    )
    delayed_open = next(
        event
        for event in delayed_backtest["trades"].to_dict("records")
        if event.get("type") == "open"
    )
    assert submitted_setup["trade_setup_candidate_id"] == candidate_id
    assert submitted_setup["decision_id"] == delayed_open["decision_id"]
    delayed_decision = (
        delayed_backtest["policy_decisions"]
        .set_index("decision_id")
        .loc[submitted_setup["decision_id"]]
    )
    assert delayed_decision["decision_index"] == submitted_setup["decision_bar"]
    assert delayed_decision["trade_setup_candidate_id"] == candidate_id
    assert submitted_setup["selected_geometry_action"]["stop_anchor_fraction"] == pytest.approx(
        selected_geometry["stop_anchor_fraction"]
    )
    assert submitted_setup["selected_geometry_action"]["target_fraction"] == pytest.approx(
        selected_geometry["target_fraction"]
    )
    assert delayed_open["trade_setup_candidate_id"] == candidate_id
    assert delayed_open["order_id"] == submitted_setup["order_id"]
    assert delayed_open["order_submission_time"] == submitted_setup["order_submission_time"]
    delayed_geometry = delayed_open["selected_geometry_action"]
    assert delayed_geometry["stop_anchor_fraction"] == pytest.approx(
        selected_geometry["stop_anchor_fraction"]
    )
    assert delayed_geometry["target_fraction"] == pytest.approx(
        selected_geometry["target_fraction"]
    )

    no_trade_action = np.zeros(schema.width, dtype=np.float32)
    no_trade_action[schema.indices["trade_setup"]] = trade_setup_center(0)
    policy_calls = 0

    def enter_then_abstain(observation: Any) -> Array:
        nonlocal policy_calls
        assert observation["trade_setup_mask"].shape == (TRADE_SETUP_CATEGORY_COUNT,)
        policy_calls += 1
        return setup_action if policy_calls == 1 else no_trade_action

    abstention_backtest = run_backtest(
        bars,
        active_features,
        enter_then_abstain,
        obs_window=1,
        cost_model=costs,
        hold_on_zero=False,
        block_overnight=False,
        trade_setup_actions=True,
        trade_setup_action_schema=schema,
        strategy=_GeometryStrategy(),
    )
    abstention_close = next(
        event
        for event in abstention_backtest["trades"].to_dict("records")
        if event.get("type") == "eod_close"
    )
    assert pd.Timestamp(abstention_close["time"]) > bars.index[-1]


def test_setup_policy_observation_resets_sequence_at_session_boundary() -> None:
    index = pd.date_range("2025-01-06 14:30", periods=4, freq="1min", tz="UTC")
    close = np.full(len(index), 20_000.0)
    bars = pd.DataFrame(
        {
            "open": close,
            "high": close + 2.0,
            "low": close - 2.0,
            "close": close,
            "spread": 0.0,
            "session_id": [0, 1, 1, 1],
            "session": "ny",
        },
        index=index,
    )
    features = pd.DataFrame({"feature": np.arange(len(index), dtype=np.float32)}, index=index)
    schema = build_trade_setup_action_schema()
    observed: list[dict[str, Array]] = []

    def hold(observation: Any) -> Array:
        observed.append(observation)
        return np.zeros(schema.width, dtype=np.float32)

    run_backtest(
        bars,
        features,
        hold,
        obs_window=2,
        hold_on_zero=True,
        block_overnight=False,
        trade_setup_actions=True,
        trade_setup_action_schema=schema,
    )

    assert observed
    np.testing.assert_array_equal(observed[0]["seq_mask"], np.asarray([0.0, 1.0], dtype=np.float32))
    np.testing.assert_array_equal(
        observed[0]["seq"], np.asarray([[0.0, 0.0], [1.0, 0.0]], dtype=np.float32)
    )


def test_setup_policy_risk_coordinate_sizes_from_fill_and_respects_cost_reserve() -> None:
    index = pd.date_range("2025-01-06 14:30", periods=5, freq="1min", tz="UTC")
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
    candidate_id = trade_setup_candidate_id("fvg_retest", "M1", 1)
    features = pd.DataFrame(
        {
            "entry_idea_fvg_retest_M1_long": 1.0,
            "atr_5": 10.0,
            "last_swing_low": 19_990.0,
            "last_swing_high": 20_040.0,
        },
        index=index,
    )
    schema = build_trade_setup_action_schema()
    costs = CostModel(
        spread_points=0.0,
        point_size=0.01,
        commission_per_lot=2.0,
        slippage_points=0.25,
    )

    def open_at_risk(raw_risk: float) -> dict[str, object]:
        action = np.zeros(schema.width, dtype=np.float32)
        action[schema.indices["trade_setup"]] = trade_setup_center(candidate_id)
        action[schema.indices["risk"]] = raw_risk
        action[schema.indices["exit"]] = -1.0
        result = run_backtest(
            bars,
            features,
            lambda _observation: action,
            obs_window=1,
            cost_model=costs,
            initial_balance=100_000.0,
            guardrail_kwargs={
                "limit_value_mode": "fixed_usd",
                "risk_per_trade_limit": 3_000.0,
            },
            use_structure_sl_tp=True,
            policy_risk_frac_range=(0.005, 0.02),
            hold_on_zero=True,
            block_overnight=False,
            trade_setup_actions=True,
            trade_setup_action_schema=schema,
            strategy=_GeometryStrategy(),
        )
        return next(
            event for event in result["trades"].to_dict("records") if event.get("type") == "open"
        )

    low_risk_open = open_at_risk(-1.0)
    high_risk_open = open_at_risk(1.0)
    assert low_risk_open["risk_frac"] == 0.005
    assert high_risk_open["risk_frac"] == 0.02
    assert _event_number(high_risk_open, "lots") > _event_number(low_risk_open, "lots")
    assert low_risk_open["risk_budget_usd"] == 500.0
    assert high_risk_open["risk_budget_usd"] == 2_000.0
    for open_event in (low_risk_open, high_risk_open):
        lots = _event_number(open_event, "lots")
        modeled_risk = (
            _event_number(open_event, "price") - _event_number(open_event, "sl_price")
        ) * lots + lots * (0.25 + 4.0)
        assert modeled_risk <= _event_number(open_event, "risk_budget_usd")

    policy_calls = 0

    def change_risk_after_submit(_observation: Any) -> Array:
        nonlocal policy_calls
        action = np.zeros(schema.width, dtype=np.float32)
        action[schema.indices["trade_setup"]] = trade_setup_center(candidate_id)
        action[schema.indices["risk"]] = -1.0 if policy_calls == 0 else 1.0
        action[schema.indices["exit"]] = -1.0
        policy_calls += 1
        return action

    delayed = run_backtest(
        bars,
        features,
        change_risk_after_submit,
        obs_window=1,
        cost_model=costs,
        initial_balance=100_000.0,
        guardrail_kwargs={"risk_per_trade_limit": 3_000.0},
        use_structure_sl_tp=True,
        policy_risk_frac_range=(0.005, 0.02),
        fill_latency_bars=1,
        hold_on_zero=True,
        block_overnight=False,
        trade_setup_actions=True,
        trade_setup_action_schema=schema,
        strategy=_GeometryStrategy(),
    )
    delayed_open = next(
        event for event in delayed["trades"].to_dict("records") if event.get("type") == "open"
    )
    assert delayed_open["risk_frac"] == 0.005


def test_setup_geometry_installs_ema_exit_and_closes_after_one_risk_of_travel() -> None:
    index = pd.date_range("2025-01-06 14:30", periods=6, freq="1min", tz="UTC")
    close = np.full(len(index), 20_000.0)
    high = close + 2.0
    high[3] = 20_012.0
    bars = pd.DataFrame(
        {
            "open": close,
            "high": high,
            "low": close - 2.0,
            "close": close,
            "spread": 0.0,
            "session_id": 0,
            "session": "ny",
        },
        index=index,
    )
    features = pd.DataFrame(
        {
            "entry_idea_fvg_retest_M1_long": 1.0,
            "atr_5": 10.0,
            "last_swing_low": 19_990.0,
            "ema_21": 20_005.0,
        },
        index=index,
    )
    schema = build_trade_setup_action_schema()
    candidate_id = trade_setup_candidate_id("fvg_retest", "M1", 1)
    action = np.zeros(schema.width, dtype=np.float32)
    action[schema.indices["trade_setup"]] = trade_setup_center(candidate_id)
    action[schema.indices["exit"]] = 1.0
    calls = 0

    def enter_once(_observation: Any) -> Array:
        nonlocal calls
        calls += 1
        return action if calls == 1 else np.zeros(schema.width, dtype=np.float32)

    result = run_backtest(
        bars,
        features,
        enter_once,
        obs_window=1,
        cost_model=CostModel(spread_points=0.0, point_size=0.01),
        hold_on_zero=True,
        block_overnight=False,
        trade_setup_actions=True,
        trade_setup_action_schema=schema,
        strategy=_GeometryStrategy(),
    )
    events = result["trades"].to_dict("records")
    opened = next(event for event in events if event.get("type") == "open")
    ema_close = next(event for event in events if event.get("reason") == "ema_21_exit")
    assert opened["exit_mode"] == "ema_21"
    assert pd.isna(opened["tp_price"])
    assert ema_close["type"] == "close"


def test_setup_geometry_installs_selected_multi_target_ladder_and_fractions() -> None:
    index = pd.date_range("2025-01-06 14:30", periods=5, freq="1min", tz="UTC")
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
    candidate_id = trade_setup_candidate_id("fvg_retest", "M1", 1)
    features = pd.DataFrame(
        {
            "entry_idea_fvg_retest_M1_long": 1.0,
            "atr_5": 10.0,
            "last_swing_low": 19_990.0,
            "last_swing_high": 20_010.0,
            "asian_high": 20_020.0,
            "london_high": 20_030.0,
        },
        index=index,
    )
    schema = build_trade_setup_action_schema(has_multi_tp=True, has_simplex=True)
    action = np.zeros(schema.width, dtype=np.float32)
    action[schema.indices["trade_setup"]] = trade_setup_center(candidate_id)
    action[schema.indices["exit"]] = -1.0
    action[schema.indices["tp1_sel"]] = -1.0
    action[schema.indices["tp2_sel"]] = -0.3
    action[schema.indices["tp3_sel"]] = 1.0
    action[schema.indices["z1"]] = -0.2
    action[schema.indices["z2"]] = 0.3

    result = run_backtest(
        bars,
        features,
        lambda _observation: action,
        obs_window=1,
        cost_model=CostModel(spread_points=0.0, point_size=0.01),
        hold_on_zero=True,
        block_overnight=False,
        trade_setup_actions=True,
        trade_setup_action_schema=schema,
        strategy=_GeometryStrategy(),
    )
    opened = next(
        event for event in result["trades"].to_dict("records") if event.get("type") == "open"
    )
    assert pd.notna(opened["tp1_price"])
    assert pd.notna(opened["tp2_price"])
    assert pd.notna(opened["tp3_price"])
    assert opened["tp1_price"] < opened["tp2_price"] < opened["tp3_price"]
    fractions = tuple(opened["tp_lot_fractions"])
    assert len(fractions) == 3
    assert sum(fractions) == pytest.approx(1.0)


def test_management_mode_choices_survive_delayed_market_submission_and_fill() -> None:
    index = pd.date_range("2025-01-06 14:30", periods=6, freq="1min", tz="UTC")
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
    candidate_id = trade_setup_candidate_id("fvg_retest", "M1", 1)
    features["entry_idea_fvg_retest_M1_long"] = 1.0
    features["atr_5"] = 10.0
    features["last_swing_low"] = 19_990.0
    features["last_swing_high"] = 20_010.0
    schema = build_trade_setup_action_schema(has_sl_mode=True, has_tp_mode=True)
    action = np.zeros(schema.width, dtype=np.float32)
    action[schema.indices["trade_setup"]] = trade_setup_center(candidate_id)
    action[schema.indices["stop"]] = -0.4
    action[schema.indices["target"]] = 0.8
    action[schema.indices["exit"]] = -1.0
    action[schema.indices["sl_mode"]] = 1.0
    action[schema.indices["tp_mode"]] = -1.0
    costs = CostModel(spread_points=0.0, point_size=0.01, commission_per_lot=0.0)

    result = run_backtest(
        bars,
        features,
        lambda _observation: action,
        obs_window=1,
        cost_model=costs,
        hold_on_zero=True,
        block_overnight=False,
        fill_latency_bars=1,
        trade_setup_actions=True,
        trade_setup_action_schema=schema,
        strategy=_GeometryStrategy(),
    )
    events = result["trades"].to_dict("records")
    submitted = next(event for event in events if event["type"] == "order_submit")
    opened = next(event for event in events if event["type"] == "open")

    assert submitted["selected_geometry_action"]["sl_mode"] == "trailing"
    assert submitted["selected_geometry_action"]["tp_mode"] == "fixed"
    assert opened["selected_geometry_action"]["sl_mode"] == "trailing"
    assert opened["selected_geometry_action"]["tp_mode"] == "fixed"
    assert opened["sl_mode"] == "trailing"
    assert opened["sl_mode_overridden"] is True
    assert opened["tp_mode"] == "fixed"
    assert opened["tp_mode_overridden"] is True


@pytest.mark.parametrize("schema_version", [OBSERVATION_SCHEMA_V2, OBSERVATION_SCHEMA_V3])
def test_setup_backtest_emits_versioned_account_state(schema_version: str) -> None:
    index = pd.date_range("2025-01-06 14:30", periods=3, freq="1min", tz="UTC")
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
    action_schema = build_trade_setup_action_schema()
    action = np.zeros(action_schema.width, dtype=np.float32)
    action[action_schema.indices["trade_setup"]] = trade_setup_center(0)
    observation_schema = build_observation_schema(schema_version)
    captured: dict[str, Array] = {}

    def no_trade(observation: Any) -> Array:
        if not captured:
            captured.update(observation)
        return action

    result = run_backtest(
        bars,
        features,
        no_trade,
        obs_window=1,
        cost_model=CostModel(spread_points=0.0, point_size=0.01),
        hold_on_zero=True,
        block_overnight=False,
        trade_setup_actions=True,
        trade_setup_action_schema=action_schema,
        observation_schema=observation_schema,
    )

    expected = account_state_v2(
        equity=100_000.0,
        initial_balance=100_000.0,
        position_direction=0.0,
        open_pnl=0.0,
        planned_risk_usd=0.0,
        trailing_drawdown_pct=0.0,
        trailing_drawdown_limit=0.0,
        daily_loss=0.0,
        daily_loss_limit=5_000.0,
        loss_from_initial=0.0,
        max_loss_limit=10_000.0,
        risk_per_trade_limit=1_000.0,
        current_price=20_000.0,
        entry_price=0.0,
    )
    np.testing.assert_allclose(captured["account"], expected)
    assert captured["account"].shape == (28,)
    assert result["observation_schema"] == observation_schema.to_dict()
    assert result["daily_pnl_basis"] == "session_net_equity"
    assert result["daily_loss_limit_pct"] == 0.05
    assert result["daily_loss_limit_usd"] == 5_000.0

    visible_entry_state = build_observation_schema(schema_version, entry_state_visibility=True)
    captured.clear()
    visible_result = run_backtest(
        bars,
        features,
        no_trade,
        obs_window=1,
        trade_setup_actions=True,
        trade_setup_action_schema=action_schema,
        observation_schema=visible_entry_state,
        entry_state_machine=True,
    )
    visible_expected = account_state_v2(
        equity=100_000.0,
        initial_balance=100_000.0,
        position_direction=0.0,
        open_pnl=0.0,
        planned_risk_usd=0.0,
        trailing_drawdown_pct=0.0,
        trailing_drawdown_limit=0.0,
        daily_loss=0.0,
        daily_loss_limit=5_000.0,
        loss_from_initial=0.0,
        max_loss_limit=10_000.0,
        risk_per_trade_limit=1_000.0,
        current_price=20_000.0,
        entry_price=0.0,
        entry_state="FLAT",
    )
    np.testing.assert_allclose(captured["account"], visible_expected)
    assert captured["account"].shape == (32,)
    assert visible_result["observation_schema"] == visible_entry_state.to_dict()
    assert visible_result["entry_state_diagnostics"]["entry_state_machine"] is True
    assert visible_result["entry_state_diagnostics"]["entered"] == 0
    assert visible_result["entry_state_config"] == {
        "candidate_max_age_bars": 5,
        "arm_requires_retest": False,
        "entry_state_visibility": True,
    }

    scalar_observations: list[dict[str, Array]] = []

    def scalar_long(observation: Any) -> int:
        scalar_observations.append(observation)
        return 1

    scalar_fsm_schema = build_observation_schema(OBSERVATION_SCHEMA_V1, entry_state_visibility=True)
    scalar_fsm_result = run_backtest(
        bars,
        features,
        scalar_long,
        obs_window=1,
        observation_schema=scalar_fsm_schema,
        entry_state_machine=True,
        hold_on_zero=True,
    )
    assert scalar_observations
    assert scalar_observations[0]["account"].shape == (10,)
    assert scalar_fsm_result["trades"].empty
    assert scalar_fsm_result["entry_state_diagnostics"]["entry_state_machine"] is True
    assert scalar_fsm_result["observation_inputs"]["feature_validity_channels"] is False
    assert (
        reconcile_policy_decisions(
            scalar_fsm_result["policy_decisions"],
            scalar_fsm_result["trades"],
            scalar_fsm_result["breach_events"],
        )["status"]
        == "matched"
    )

    with pytest.raises(ValueError, match="normalize_account=True"):
        run_backtest(
            bars,
            features,
            no_trade,
            obs_window=1,
            trade_setup_actions=True,
            trade_setup_action_schema=action_schema,
            observation_schema=observation_schema,
            normalize_account=False,
        )


def test_scalar_backtest_entry_state_tracks_causal_candidate_and_arming() -> None:
    index = pd.date_range("2025-01-06 14:30", periods=6, freq="1min", tz="UTC")
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
    features = pd.DataFrame(0.0, index=index, columns=["sweep_low", "sweep_high"])
    features.loc[index[1], "sweep_low"] = 1.0
    observations: list[dict[str, Array]] = []

    def hold(observation: Any) -> int:
        observations.append(observation)
        return 0

    result = run_backtest(
        bars,
        features,
        hold,
        obs_window=1,
        observation_schema=build_observation_schema(
            OBSERVATION_SCHEMA_V1, entry_state_visibility=True
        ),
        entry_state_machine=True,
        strategy=BaselineStrategy(),
        hold_on_zero=True,
    )

    states = [
        tuple(int(value) for value in observation["account"][6:]) for observation in observations
    ]
    assert entry_state_one_hot("FLAT") in states
    assert entry_state_one_hot("CANDIDATE") in states
    assert entry_state_one_hot("ARMED") in states
    assert result["entry_state_diagnostics"]["candidate_created"] == 1
    assert result["entry_state_diagnostics"]["entered"] == 0


def test_setup_backtest_optional_observation_inputs_match_trading_env() -> None:
    from datetime import date
    from types import SimpleNamespace

    import torch

    from decisioning.regime_observations import REGIME_FEATURES, regime_observation_schema

    index = pd.date_range("2025-01-06 14:30", periods=24, freq="1min", tz="UTC")
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
    columns = [name for _, name in trade_setup_candidate_feature_columns()]
    features = pd.DataFrame(
        0.0, index=index, columns=columns + ["M1_signal", "M5_bias", *REGIME_FEATURES]
    )
    features["M1_signal"] = np.arange(len(index), dtype=np.float32)
    features["M5_bias"] = np.repeat(np.arange(5, dtype=np.float32), 5)[: len(index)]
    features["D1_ret_5"] = np.linspace(-1.0, 1.0, len(index), dtype=np.float32)
    features.loc[index[1], "D1_adx"] = np.nan
    costs = CostModel(spread_points=0.0, point_size=0.01)
    action_schema = build_trade_setup_action_schema()
    action = np.zeros(action_schema.width, dtype=np.float32)
    action[action_schema.indices["trade_setup"]] = trade_setup_center(0)
    pre_ny = {date(2025, 1, 6): np.arange(6, dtype=np.float32).reshape(3, 2)}

    class _VAE(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.encoder = SimpleNamespace(latent_dim=2, seq_len=3, n_features=2)
            self.scale = torch.nn.Parameter(torch.ones(2))

        def encode(self, values: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
            mean = values.mean(dim=1) * self.scale
            return mean, torch.zeros_like(mean)

    vae = _VAE()

    env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=2,
        strategy_actions=True,
        trade_setup_actions=True,
        mtf=True,
        mtf_windows={"m5": 2},
        regime_observation=True,
        feature_validity_channels=True,
        use_vae=True,
        vae=vae,
        pre_ny_by_date=pre_ny,
        cost_model=costs,
        block_overnight=False,
        max_episode_steps=len(bars),
        episodic=False,
    )
    env.reset(seed=11)
    env.step_idx = 2
    expected = env._get_observation()

    captured: dict[str, Array] = {}

    def policy(observation: Any) -> Array:
        if not captured:
            captured.update(observation)
        return action

    result = run_backtest(
        bars,
        features,
        policy,
        obs_window=2,
        cost_model=costs,
        hold_on_zero=True,
        block_overnight=False,
        trade_setup_actions=True,
        trade_setup_action_schema=action_schema,
        regime_observation=True,
        mtf_observation=True,
        mtf_windows={"m5": 2},
        feature_validity_channels=True,
        vae=vae,
        pre_ny_by_date=pre_ny,
    )

    assert captured.keys() == expected.keys()
    for key in captured:
        np.testing.assert_array_equal(captured[key], expected[key], err_msg=key)
    assert result["observation_inputs"]["regime"] == regime_observation_schema()
    assert result["observation_inputs"]["mtf"]["enabled"] is True
    assert result["observation_inputs"]["feature_validity_channels"] is True
    assert result["observation_inputs"]["vae"]["enabled"] is True
