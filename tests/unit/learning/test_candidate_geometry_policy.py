from __future__ import annotations

import torch

from decisioning.trade_setup import (
    CANDIDATE_GEOMETRY_FEATURE_NAMES,
    build_trade_setup_action_schema,
    candidate_geometry_slot,
    candidate_geometry_slot_count,
    candidate_geometry_slot_semantics,
    decode_trade_setup_execution_choice,
    trade_setup_id_from_box,
)
from learning.rl.candidate_geometry_policy import (
    CandidateGeometryConditionedActorHeads,
    CandidateGeometryHybridBoxDistribution,
)


def _candidate_ids(batch: int = 1) -> torch.Tensor:
    values = [
        candidate_geometry_slot_semantics(slot)[0]
        for slot in range(candidate_geometry_slot_count())
    ]
    return torch.tensor(values, dtype=torch.long).unsqueeze(0).repeat(batch, 1)


def _distribution() -> tuple[
    CandidateGeometryConditionedActorHeads,
    CandidateGeometryHybridBoxDistribution,
]:
    schema = build_trade_setup_action_schema(
        has_sl_mode=True,
        has_tp_mode=False,
        has_multi_tp=False,
        has_simplex=False,
        has_entry_execution=True,
    )
    actor = CandidateGeometryConditionedActorHeads(
        latent_dim=8,
        coordinates=schema.names,
        thresholds={"sl_mode": 0.1, "tp_mode": 0.1},
        embedding_dim=4,
        hidden_dim=16,
    )
    distribution = CandidateGeometryHybridBoxDistribution(
        actor,
        schema.width,
        max_limit_offset_atr=1.0,
        max_limit_ttl_bars=60,
    )
    return actor, distribution


def test_candidate_slot_packs_into_stable_trade_setup_and_execution_coordinates() -> None:
    actor, distribution = _distribution()
    schema = build_trade_setup_action_schema(
        has_sl_mode=True,
        has_tp_mode=False,
        has_multi_tp=False,
        has_simplex=False,
        has_entry_execution=True,
    )
    slot_count = candidate_geometry_slot_count()
    candidate_ids = _candidate_ids()
    features = torch.zeros(
        (1, slot_count, len(CANDIDATE_GEOMETRY_FEATURE_NAMES)), dtype=torch.float32
    )
    selected = candidate_geometry_slot(1, "limit")
    features[0, selected, CANDIDATE_GEOMETRY_FEATURE_NAMES.index("entry_price_offset_atr")] = -0.5
    features[0, selected, CANDIDATE_GEOMETRY_FEATURE_NAMES.index("limit_ttl_fraction")] = 0.25
    mask = torch.zeros((1, slot_count), dtype=torch.bool)
    mask[0, 0] = True
    mask[0, selected] = True
    latent = torch.zeros((1, 8), dtype=torch.float32)
    distribution.proba_distribution(
        latent,
        torch.zeros(len(actor.continuous_indices), dtype=torch.float32),
        candidate_ids,
        features,
        mask,
    )
    normal, categorical = distribution._selected_distributions(torch.tensor([selected]))
    classes = {name: torch.zeros(1, dtype=torch.long) for name in categorical}
    action = distribution._pack(torch.tensor([selected]), normal.mean, classes)

    setup_id = trade_setup_id_from_box(float(action[0, schema.indices["trade_setup"]].item()))
    execution = decode_trade_setup_execution_choice(
        action[0].tolist(),
        schema,
        max_limit_offset_atr=1.0,
        max_limit_ttl_bars=60,
    )

    assert setup_id == 1
    assert execution.order_type == "limit"
    assert execution.limit_offset_atr == 0.5
    assert execution.ttl_bars == 15


def test_candidate_distribution_has_finite_joint_log_prob_and_entropy() -> None:
    actor, distribution = _distribution()
    slot_count = candidate_geometry_slot_count()
    candidate_ids = _candidate_ids(2)
    features = torch.zeros(
        (2, slot_count, len(CANDIDATE_GEOMETRY_FEATURE_NAMES)), dtype=torch.float32
    )
    mask = torch.zeros((2, slot_count), dtype=torch.bool)
    mask[:, 0] = True
    mask[:, candidate_geometry_slot(1, "market")] = True
    mask[:, candidate_geometry_slot(1, "limit")] = True
    latent = torch.zeros((2, 8), dtype=torch.float32)
    distribution.proba_distribution(
        latent,
        torch.zeros(len(actor.continuous_indices), dtype=torch.float32),
        candidate_ids,
        features,
        mask,
    )
    actions = distribution.sample()
    log_prob = distribution.log_prob(actions)
    entropy = distribution.entropy()
    selected_slots = distribution._slot_ids_from_actions(actions)

    assert actions.shape[0] == 2
    assert log_prob.shape == (2,)
    assert entropy.shape == (2,)
    assert torch.isfinite(log_prob).all()
    assert torch.isfinite(entropy).all()
    assert torch.allclose(log_prob, distribution.log_prob(actions), atol=1e-6)
    assert distribution.candidate_mask is not None
    assert distribution.candidate_mask.gather(1, selected_slots[:, None]).all()
    setup_probabilities = distribution.trade_setup_probabilities()
    assert setup_probabilities.shape == (2, 109)
    assert torch.allclose(setup_probabilities.sum(dim=1), torch.ones(2), atol=1e-6)


def test_no_trade_only_has_zero_joint_entropy_and_no_inactive_log_prob() -> None:
    actor, distribution = _distribution()
    slot_count = candidate_geometry_slot_count()
    candidate_ids = _candidate_ids()
    features = torch.zeros(
        (1, slot_count, len(CANDIDATE_GEOMETRY_FEATURE_NAMES)), dtype=torch.float32
    )
    mask = torch.zeros((1, slot_count), dtype=torch.bool)
    mask[:, 0] = True
    distribution.proba_distribution(
        torch.zeros((1, 8), dtype=torch.float32),
        torch.zeros(len(actor.continuous_indices), dtype=torch.float32),
        candidate_ids,
        features,
        mask,
    )

    action = distribution.sample()

    assert distribution._slot_ids_from_actions(action).tolist() == [0]
    assert torch.allclose(distribution.log_prob(action), torch.zeros(1), atol=1e-6)
    assert torch.allclose(distribution.entropy(), torch.zeros(1), atol=1e-6)
