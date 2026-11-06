from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from decisioning.trade_setup import (
    NO_TRADE_ID,
    TRADE_SETUP_CATEGORY_COUNT,
    build_trade_setup_action_schema,
    decode_trade_setup_execution_choice,
    trade_setup_candidate_id,
    trade_setup_id_from_box,
)
from evaluation.rollout.structure_priority_setup import (
    StructurePrioritySetupPolicy,
    StructurePrioritySetupRolloutModel,
)


def _observation(*eligible_ids: int) -> dict[str, np.ndarray[Any, Any]]:
    mask = np.zeros(TRADE_SETUP_CATEGORY_COUNT, dtype=np.float32)
    mask[NO_TRADE_ID] = 1.0
    mask[list(eligible_ids)] = 1.0
    return {"trade_setup_mask": mask}


def _policy() -> StructurePrioritySetupPolicy:
    return StructurePrioritySetupPolicy(
        build_trade_setup_action_schema(),
        idea_priority=("po3", "fvg_retest"),
        timeframe_priority=("M5", "M1"),
        normalized_risk=0.25,
    )


def test_structure_priority_uses_declared_family_then_timeframe_order() -> None:
    po3_m1 = trade_setup_candidate_id("po3", "M1", 1)
    fvg_m5 = trade_setup_candidate_id("fvg_retest", "M5", 1)
    fvg_m1 = trade_setup_candidate_id("fvg_retest", "M1", -1)

    action = _policy()(_observation(po3_m1, fvg_m5, fvg_m1))

    assert trade_setup_id_from_box(float(action[0])) == po3_m1
    assert action[2] == pytest.approx(-0.5)


def test_structure_priority_skips_inactive_higher_precedence_candidates() -> None:
    fvg_m1 = trade_setup_candidate_id("fvg_retest", "M1", -1)

    action = _policy()(_observation(fvg_m1))

    assert trade_setup_id_from_box(float(action[0])) == fvg_m1


def test_structure_priority_uses_timeframe_order_within_family() -> None:
    fvg_m5 = trade_setup_candidate_id("fvg_retest", "M5", -1)
    fvg_m1 = trade_setup_candidate_id("fvg_retest", "M1", 1)

    action = _policy()(_observation(fvg_m5, fvg_m1))

    assert trade_setup_id_from_box(float(action[0])) == fvg_m5


def test_structure_priority_abstains_when_no_preferred_setup_is_eligible() -> None:
    action = _policy()(_observation())

    assert trade_setup_id_from_box(float(action[0])) == NO_TRADE_ID


def test_structure_priority_abstains_on_direction_conflict_at_top_rank() -> None:
    po3_long = trade_setup_candidate_id("po3", "M5", 1)
    po3_short = trade_setup_candidate_id("po3", "M5", -1)
    fvg_m1 = trade_setup_candidate_id("fvg_retest", "M1", 1)
    policy = StructurePrioritySetupPolicy(
        build_trade_setup_action_schema(),
        idea_priority=("po3", "fvg_retest"),
        timeframe_priority=("M5", "M1"),
    )

    action = policy(_observation(po3_long, po3_short, fvg_m1))

    assert trade_setup_id_from_box(float(action[0])) == NO_TRADE_ID


def test_structure_priority_rollout_model_exposes_schema_and_rule_provenance() -> None:
    policy = _policy()
    model = StructurePrioritySetupRolloutModel(policy)
    candidate_id = trade_setup_candidate_id("fvg_retest", "M5", 1)

    action, recurrent_state = model.predict(_observation(candidate_id), deterministic=True)
    metadata = model.policy_metadata

    assert recurrent_state is None
    assert trade_setup_id_from_box(float(action[0])) == candidate_id
    assert model.hybrid_action_coordinates == policy.action_schema.names
    assert metadata["baseline_tier"] == "tier_1_deterministic_structure_rule"
    assert metadata["permitted_information"] == ["current_observation.trade_setup_mask"]
    assert metadata["training_performed"] is False
    assert metadata["selection_or_tuning_performed"] is False
    assert metadata["risk_coordinate_is_constant"] is True


def test_structure_priority_stays_market_only_with_execution_coordinates() -> None:
    schema = build_trade_setup_action_schema(has_entry_execution=True)
    policy = StructurePrioritySetupPolicy(
        schema,
        idea_priority=("po3",),
        timeframe_priority=("M5",),
    )
    candidate_id = trade_setup_candidate_id("po3", "M5", 1)

    action = policy(_observation(candidate_id))
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


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"idea_priority": (), "timeframe_priority": ("M1",)}, "idea_priority"),
        ({"idea_priority": ("po3", "po3"), "timeframe_priority": ("M1",)}, "idea_priority"),
        ({"idea_priority": ("po3",), "timeframe_priority": ()}, "timeframe_priority"),
        ({"idea_priority": ("unknown",), "timeframe_priority": ("M1",)}, "idea_priority"),
        ({"idea_priority": ("po3",), "timeframe_priority": ("M1", "M1")}, "timeframe_priority"),
        (
            {"idea_priority": ("po3",), "timeframe_priority": ("M1",), "normalized_risk": 1.1},
            "normalized_risk",
        ),
    ],
)
def test_structure_priority_rejects_invalid_rule_configuration(
    kwargs: dict[str, Any], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        StructurePrioritySetupPolicy(build_trade_setup_action_schema(), **kwargs)
