from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from decisioning.trade_setup import (
    NO_TRADE_ID,
    TRADE_SETUP_CATEGORY_COUNT,
    build_trade_setup_action_schema,
    decode_trade_setup_execution_choice,
    trade_setup_id_from_box,
)
from evaluation.rollout.random_eligible_setup import (
    AlwaysNoTradePolicy,
    RandomEligibleSetupPolicy,
    RandomEligibleSetupRolloutModel,
)
from evaluation.rollout.trained_policy_rollout import make_action_fn


def _observation(*eligible_ids: int) -> dict[str, np.ndarray[Any, Any]]:
    mask = np.zeros(TRADE_SETUP_CATEGORY_COUNT, dtype=np.float32)
    mask[NO_TRADE_ID] = 1.0
    mask[list(eligible_ids)] = 1.0
    return {"trade_setup_mask": mask}


def test_random_eligible_policy_is_seeded_and_respects_mask() -> None:
    schema = build_trade_setup_action_schema()
    observation = _observation(2, 7, 31)
    first = RandomEligibleSetupPolicy(schema, seed=42)
    second = RandomEligibleSetupPolicy(schema, seed=42)

    actions_a = [first(observation) for _ in range(100)]
    actions_b = [second(observation) for _ in range(100)]

    np.testing.assert_array_equal(actions_a, actions_b)
    selected = [trade_setup_id_from_box(float(action[0])) for action in actions_a]
    assert set(selected) <= {2, 7, 31}
    assert selected


def test_random_eligible_policy_supports_abstention_and_fixed_risk() -> None:
    schema = build_trade_setup_action_schema()
    observation = _observation(9)
    policy = RandomEligibleSetupPolicy(schema, seed=4, trade_probability=0.0, normalized_risk=0.25)

    action = policy(observation)

    assert trade_setup_id_from_box(float(action[0])) == NO_TRADE_ID
    assert action[schema.names.index("risk")] == pytest.approx(-0.5)
    metadata = policy.metadata()
    assert metadata["policy_id"] == "random_eligible_trade_setup_v1"
    assert metadata["baseline_tier"] == "tier_0_accounting_and_decision_sanity"
    assert metadata["permitted_information"] == ["current_observation.trade_setup_mask"]
    assert metadata["training_performed"] is False
    assert metadata["selection_or_tuning_performed"] is False


def test_random_setup_baseline_keeps_market_execution_when_schema_offers_limits() -> None:
    schema = build_trade_setup_action_schema(has_entry_execution=True)
    policy = RandomEligibleSetupPolicy(schema, seed=42)

    action = policy(_observation(9))
    choice = decode_trade_setup_execution_choice(
        action.tolist(),
        schema,
        max_limit_offset_atr=1.0,
        max_limit_ttl_bars=60,
    )

    assert choice.order_type == "market"
    assert choice.limit_offset_atr == 0.0
    assert choice.ttl_bars == 1
    assert policy.metadata()["entry_execution"] == "market"


def test_always_no_trade_policy_is_deterministic_and_identified_as_flat_control() -> None:
    schema = build_trade_setup_action_schema()
    policy = AlwaysNoTradePolicy(schema)
    observation = _observation(2, 7, 31)

    actions = [policy(observation) for _ in range(20)]

    assert {trade_setup_id_from_box(float(action[0])) for action in actions} == {NO_TRADE_ID}
    assert all(action[schema.names.index("risk")] == -1.0 for action in actions)
    metadata = policy.metadata()
    assert metadata["policy_id"] == "always_no_trade_v1"
    assert metadata["baseline_tier"] == "tier_0_accounting_and_decision_sanity"
    assert metadata["permitted_information"] == []
    assert metadata["training_performed"] is False
    assert metadata["selection_or_tuning_performed"] is False


def test_random_eligible_rollout_model_uses_shared_action_adapter() -> None:
    schema = build_trade_setup_action_schema()
    policy = RandomEligibleSetupPolicy(schema, seed=31, normalized_risk=0.4)
    model = RandomEligibleSetupRolloutModel(policy)
    observation = _observation(2, 7, 31)
    expected = RandomEligibleSetupPolicy(schema, seed=31, normalized_risk=0.4)

    direct_action, recurrent_state = model.predict(observation, deterministic=True)
    rollout_action = make_action_fn(model, strategy_actions=True)(observation)

    np.testing.assert_array_equal(direct_action, expected(observation))
    np.testing.assert_array_equal(rollout_action, expected(observation))
    assert recurrent_state is None
    assert model.policy.hybrid_action_coordinates == schema.names
    assert model.policy_metadata["seed"] == 31
    assert model.policy_metadata["execution_and_risk_controls"] == (
        "delegated to shared evaluation environment"
    )


def test_random_eligible_policy_requires_valid_mask_contract() -> None:
    schema = build_trade_setup_action_schema()
    policy = RandomEligibleSetupPolicy(schema, seed=1)

    with pytest.raises(ValueError, match="missing trade_setup_mask"):
        policy({})
    with pytest.raises(ValueError, match="NO_TRADE must remain eligible"):
        policy({"trade_setup_mask": np.zeros(TRADE_SETUP_CATEGORY_COUNT, dtype=np.float32)})
    with pytest.raises(ValueError, match="shape"):
        policy({"trade_setup_mask": np.ones(2, dtype=np.float32)})


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"seed": -1}, "seed must be non-negative"),
        ({"seed": True}, "seed must be non-negative"),
        ({"seed": 1, "trade_probability": 1.1}, "trade_probability"),
        ({"seed": 1, "trade_probability": True}, "trade_probability"),
        ({"seed": 1, "normalized_risk": -0.1}, "normalized_risk"),
        ({"seed": 1, "normalized_risk": False}, "normalized_risk"),
    ],
)
def test_random_eligible_policy_rejects_invalid_settings(
    kwargs: dict[str, Any], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        RandomEligibleSetupPolicy(build_trade_setup_action_schema(), **kwargs)
