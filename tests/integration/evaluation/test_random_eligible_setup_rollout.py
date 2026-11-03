from __future__ import annotations

from typing import Any

import numpy as np
import numpy.typing as npt
import pandas as pd
import pytest

from decisioning.trade_setup import (
    NO_TRADE_ID,
    TRADE_SETUP_ACTION_VERSION,
    TRADE_SETUP_CATEGORY_COUNT,
    TradeSetupActionSchema,
    trade_setup_candidate_id,
    trade_setup_center,
    trade_setup_id_from_box,
)
from evaluation.metrics.performance import calculate_metrics
from evaluation.reporting.run_artifact_writer import save_run
from evaluation.rollout.random_eligible_setup import (
    AlwaysNoTradePolicy,
    AlwaysNoTradeRolloutModel,
    RandomEligibleSetupPolicy,
    RandomEligibleSetupRolloutModel,
)
from evaluation.rollout.trained_policy_rollout import evaluate_model
from features.context.trade_setup_candidates import trade_setup_candidate_feature_columns
from simulation.environment.env import TradingEnv


class _FixedSetupPolicy:
    def __init__(
        self,
        schema: TradeSetupActionSchema,
        candidate_id: int,
        probabilities: npt.NDArray[Any] | None = None,
    ) -> None:
        self.hybrid_action_coordinates = schema.names
        self._action = np.zeros(schema.width, dtype=np.float32)
        self._action[schema.indices["trade_setup"]] = trade_setup_center(candidate_id)
        self.last_trade_setup_probabilities = (
            None
            if probabilities is None
            else np.asarray(probabilities, dtype=np.float32).reshape(1, -1)
        )


class _FixedSetupModel:
    def __init__(
        self,
        schema: TradeSetupActionSchema,
        candidate_id: int,
        probabilities: npt.NDArray[Any] | None = None,
    ) -> None:
        self.policy = _FixedSetupPolicy(schema, candidate_id, probabilities)

    def predict(self, _observation: object, *, deterministic: bool = True):
        del deterministic
        return self.policy._action.copy(), None


def test_random_setup_baseline_uses_shared_rollout_decision_trace() -> None:
    index = pd.date_range("2025-01-06 16:30", periods=24, freq="1min", tz="Etc/GMT-3")
    close = np.full(len(index), 20_000.0)
    bars = pd.DataFrame(
        {
            "open": close,
            "high": close + 2.0,
            "low": close - 2.0,
            "close": close,
            "spread": 0.6,
            "session_id": 0,
        },
        index=index,
    )
    features = pd.DataFrame(
        0.0,
        index=index,
        columns=[name for _, name in trade_setup_candidate_feature_columns()],
    )
    features["entry_idea_fvg_retest_M5_long"] = 1.0
    features["M5_fvg_bull_retest_confirmed_at_time_ns"] = float(index[0].value)
    features["M5_fvg_bull_retest_origin_time_ns"] = float(index[0].value - 300_000_000_000)
    features["last_swing_low"] = close - 20.0
    features["last_swing_high"] = close + 40.0

    env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=5,
        strategy_actions=True,
        trade_setup_actions=True,
        max_episode_steps=4,
        episodic=False,
    )
    schema = env.action_schema
    assert isinstance(schema, TradeSetupActionSchema)
    assert schema.names[0] == "trade_setup"
    model = RandomEligibleSetupRolloutModel(
        RandomEligibleSetupPolicy(schema, seed=17, trade_probability=1.0)
    )

    result = evaluate_model(
        model,
        bars,
        features,
        env=env,
        strategy_actions=True,
        trade_setup_actions=True,
    )

    decisions = result["trade_setup_decisions"]
    assert len(decisions) == 4
    assert decisions["decision_id"].notna().all()
    assert decisions["decision_id"].is_unique
    assert decisions["trade_setup_schema_version"].eq(TRADE_SETUP_ACTION_VERSION).all()
    assert decisions["trade_setup_action_schema_version"].eq(schema.version).all()
    assert decisions["trade_setup_eligible"].all()
    assert decisions["selected_idea"].eq("fvg_retest").all()
    assert decisions["selected_timeframe"].eq("M5").all()
    assert decisions["selected_direction"].eq(1).all()
    assert decisions["action_trade_setup"].notna().all()
    assert decisions.apply(
        lambda row: (
            trade_setup_id_from_box(float(row["action_trade_setup"]))
            == int(row["trade_setup_candidate_id"])
        ),
        axis=1,
    ).all()

    assert decisions["trade_setup_source_event_identity_status"].eq("identified").all()
    assert decisions["trade_setup_source_event_id"].nunique() == 1
    assert decisions["decision_bar_index"].notna().all()
    for _, row in decisions.iterrows():
        decision_time = bars.index[int(row["decision_bar_index"])]
        assert pd.Timestamp(row["decision_time"]) == decision_time
        assert pd.Timestamp(row["time"]) == decision_time
        assert pd.Timestamp(row["valuation_time"]) >= decision_time
    assert decisions["trade_event_start_index"].iloc[0] == 0
    assert decisions["trade_event_end_index_exclusive"].iloc[-1] == len(result["trades"])
    previous_event_end = 0
    for _, row in decisions.iterrows():
        event_start = int(row["trade_event_start_index"])
        event_end = int(row["trade_event_end_index_exclusive"])
        assert 0 <= event_start <= event_end <= len(result["trades"])
        assert event_start == previous_event_end
        assert isinstance(row["entry_rejection_reason"], str)
        assert isinstance(row["position_open_after_step"], (bool, np.bool_))
        step_events = result["trades"].iloc[event_start:event_end]
        open_events = step_events.loc[step_events["type"].eq("open")]
        if not open_events.empty:
            assert open_events["bar"].eq(row["decision_bar_index"]).all()
            assert open_events["trade_setup_candidate_id"].eq(row["trade_setup_candidate_id"]).all()
            assert open_events["decision_id"].eq(row["decision_id"]).all()
        previous_event_end = event_end
    assert decisions["selection_valid"].all()
    assert decisions["eligible_trade_setup_count"].eq(2).all()
    assert decisions["trade_setup_selected_probability"].isna().all()
    assert decisions["trade_setup_no_trade_probability"].isna().all()
    assert decisions["trade_setup_max_trade_probability"].isna().all()
    assert decisions["trade_setup_max_trade_candidate_id"].isna().all()
    assert decisions.apply(
        lambda row: (
            row["trade_setup_candidate_id"]
            in [
                candidate_id
                for candidate_id in row["eligible_trade_setup_ids"]
                if candidate_id != NO_TRADE_ID
            ]
        ),
        axis=1,
    ).all()
    assert result["trade_setup_policy_metrics"]["policy_class"] == (
        "RandomEligibleSetupRolloutModel"
    )
    assert result["policy_metadata"]["seed"] == 17
    assert result["policy_metadata"]["trade_probability"] == 1.0


def test_model_choice_probabilities_survive_rollout_and_artifact_export(
    tmp_path,
) -> None:
    index = pd.date_range("2025-01-06 16:30", periods=24, freq="1min", tz="Etc/GMT-3")
    close = np.full(len(index), 20_000.0)
    bars = pd.DataFrame(
        {
            "open": close,
            "high": close + 2.0,
            "low": close - 2.0,
            "close": close,
            "spread": 0.6,
            "session_id": 0,
        },
        index=index,
    )
    features = pd.DataFrame(
        0.0,
        index=index,
        columns=[name for _, name in trade_setup_candidate_feature_columns()],
    )
    features["entry_idea_fvg_retest_M5_long"] = 1.0
    features["M5_fvg_bull_retest_confirmed_at_time_ns"] = float(index[0].value)
    features["M5_fvg_bull_retest_origin_time_ns"] = float(index[0].value - 300_000_000_000)
    features["last_swing_low"] = close - 20.0
    features["last_swing_high"] = close + 40.0
    env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=5,
        strategy_actions=True,
        trade_setup_actions=True,
        max_episode_steps=1,
        episodic=False,
    )
    schema = env.action_schema
    assert isinstance(schema, TradeSetupActionSchema)
    candidate_id = trade_setup_candidate_id("fvg_retest", "M5", 1)
    probabilities = np.zeros(TRADE_SETUP_CATEGORY_COUNT, dtype=np.float32)
    probabilities[[NO_TRADE_ID, candidate_id]] = [0.25, 0.75]

    result = evaluate_model(
        _FixedSetupModel(schema, candidate_id, probabilities),
        bars,
        features,
        env=env,
        strategy_actions=True,
        trade_setup_actions=True,
    )
    run_dir = save_run(
        run_dir=tmp_path / "model-choice-trace",
        train_result=result,
        train_metrics=calculate_metrics(
            result["equity"],
            trades=result["trades"],
            initial_balance=100_000.0,
        ),
        train_bars=bars,
        save_plots=False,
        save_html=False,
        save_csv=True,
        report_profile="experiment_run_fast",
    )

    saved = pd.read_csv(run_dir / "training" / "trade_setup_decisions.csv")
    assert len(saved) == 1
    saved_candidate_id = saved["trade_setup_candidate_id"].to_numpy(dtype=np.int64)[0]
    assert int(saved_candidate_id) == candidate_id
    assert saved.loc[0, "trade_setup_selected_probability"] == pytest.approx(0.75)
    assert saved.loc[0, "trade_setup_no_trade_probability"] == pytest.approx(0.25)
    assert saved.loc[0, "trade_setup_max_trade_probability"] == pytest.approx(0.75)
    saved_max_candidate_id = saved["trade_setup_max_trade_candidate_id"].to_numpy(dtype=np.int64)[0]
    assert int(saved_max_candidate_id) == candidate_id


def test_always_no_trade_baseline_uses_shared_rollout_without_positions() -> None:
    index = pd.date_range("2025-01-06 16:30", periods=12, freq="1min", tz="Etc/GMT-3")
    close = np.full(len(index), 20_000.0)
    bars = pd.DataFrame(
        {
            "open": close,
            "high": close + 2.0,
            "low": close - 2.0,
            "close": close,
            "spread": 0.6,
            "session_id": 0,
        },
        index=index,
    )
    features = pd.DataFrame(
        0.0,
        index=index,
        columns=[name for _, name in trade_setup_candidate_feature_columns()],
    )
    features["entry_idea_fvg_retest_M5_long"] = 1.0
    features["last_swing_low"] = close - 20.0
    features["last_swing_high"] = close + 40.0

    env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=5,
        strategy_actions=True,
        trade_setup_actions=True,
        max_episode_steps=4,
        episodic=False,
    )
    schema = env.action_schema
    assert isinstance(schema, TradeSetupActionSchema)
    model = AlwaysNoTradeRolloutModel(AlwaysNoTradePolicy(schema))

    result = evaluate_model(
        model,
        bars,
        features,
        env=env,
        strategy_actions=True,
        trade_setup_actions=True,
    )

    decisions = result["trade_setup_decisions"]
    assert len(decisions) == 4
    assert decisions["trade_setup_candidate_id"].eq(NO_TRADE_ID).all()
    assert decisions["trade_setup_eligible"].all()
    assert decisions["selected_idea"].eq("no_trade").all()
    assert decisions["trade_setup_source_event_identity_status"].eq("not_applicable").all()
    assert result["trades"].empty
    assert result["policy_metadata"]["policy_id"] == "always_no_trade_v1"


def test_ineligible_setup_action_is_persisted_with_mask_outcome() -> None:
    index = pd.date_range("2025-01-06 16:30", periods=12, freq="1min", tz="Etc/GMT-3")
    close = np.full(len(index), 20_000.0)
    bars = pd.DataFrame(
        {
            "open": close,
            "high": close + 2.0,
            "low": close - 2.0,
            "close": close,
            "spread": 0.6,
            "session_id": 0,
        },
        index=index,
    )
    features = pd.DataFrame(
        0.0,
        index=index,
        columns=[name for _, name in trade_setup_candidate_feature_columns()],
    )
    features["entry_idea_fvg_retest_M5_long"] = 1.0
    features["M5_fvg_bull_retest_confirmed_at_time_ns"] = float(index[0].value)
    features["M5_fvg_bull_retest_origin_time_ns"] = float(index[0].value - 300_000_000_000)
    features["last_swing_low"] = close - 20.0
    features["last_swing_high"] = close + 40.0

    env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=5,
        strategy_actions=True,
        trade_setup_actions=True,
        max_episode_steps=1,
        episodic=False,
    )
    schema = env.action_schema
    assert isinstance(schema, TradeSetupActionSchema)
    inactive_id = trade_setup_candidate_id("fvg_retest", "M1", 1)
    result = evaluate_model(
        _FixedSetupModel(schema, inactive_id),
        bars,
        features,
        env=env,
        strategy_actions=True,
        trade_setup_actions=True,
    )

    decisions = result["trade_setup_decisions"]
    assert len(decisions) == 1
    decision = decisions.iloc[0]
    assert decision["trade_setup_candidate_id"] == inactive_id
    assert decision["selection_valid"] is False or not bool(decision["selection_valid"])
    assert decision["trade_setup_eligible"] is False or not bool(decision["trade_setup_eligible"])
    assert decision["selected_idea"] == ""
    event_start = int(decision["trade_event_start_index"])
    event_end = int(decision["trade_event_end_index_exclusive"])
    events = result["trades"].iloc[event_start:event_end]
    rejection = events.loc[events["type"].eq("reject")].iloc[0]
    assert rejection["entry_rejection_reason"] == "trade_setup_inactive"
    assert rejection["decision_id"] == decision["decision_id"]


def test_masked_setup_probabilities_are_saved_with_the_decision() -> None:
    index = pd.date_range("2025-01-06 16:30", periods=12, freq="1min", tz="Etc/GMT-3")
    close = np.full(len(index), 20_000.0)
    bars = pd.DataFrame(
        {
            "open": close,
            "high": close + 2.0,
            "low": close - 2.0,
            "close": close,
            "spread": 0.6,
            "session_id": 0,
        },
        index=index,
    )
    features = pd.DataFrame(
        0.0,
        index=index,
        columns=[name for _, name in trade_setup_candidate_feature_columns()],
    )
    features["entry_idea_fvg_retest_M5_long"] = 1.0
    features["M5_fvg_bull_retest_confirmed_at_time_ns"] = float(index[0].value)
    features["M5_fvg_bull_retest_origin_time_ns"] = float(index[0].value - 300_000_000_000)
    features["last_swing_low"] = close - 20.0
    features["last_swing_high"] = close + 40.0
    env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=5,
        strategy_actions=True,
        trade_setup_actions=True,
        max_episode_steps=1,
        episodic=False,
    )
    schema = env.action_schema
    assert isinstance(schema, TradeSetupActionSchema)
    candidate_id = trade_setup_candidate_id("fvg_retest", "M5", 1)
    probabilities = np.zeros(TRADE_SETUP_CATEGORY_COUNT, dtype=np.float32)
    probabilities[[NO_TRADE_ID, candidate_id]] = [0.25, 0.75]

    result = evaluate_model(
        _FixedSetupModel(schema, candidate_id, probabilities),
        bars,
        features,
        env=env,
        strategy_actions=True,
        trade_setup_actions=True,
    )

    decision = result["trade_setup_decisions"].iloc[0]
    assert decision["trade_setup_candidate_id"] == candidate_id
    assert decision["trade_setup_selected_probability"] == pytest.approx(0.75)
    assert decision["trade_setup_no_trade_probability"] == pytest.approx(0.25)
    assert decision["trade_setup_max_trade_probability"] == pytest.approx(0.75)
    assert decision["trade_setup_max_trade_candidate_id"] == candidate_id
