from __future__ import annotations

import pytest
import torch

from learning.rl.candidate_geometry import (
    CANDIDATE_GEOMETRY_FEATURE_NAMES,
    CandidateGeometryActorHeads,
    apply_candidate_eligibility_mask,
)


def _actor() -> CandidateGeometryActorHeads:
    torch.manual_seed(41)
    return CandidateGeometryActorHeads(
        market_latent_dim=6,
        candidate_feature_dim=len(CANDIDATE_GEOMETRY_FEATURE_NAMES),
        action_dim=4,
        candidate_count=109,
        candidate_feature_names=CANDIDATE_GEOMETRY_FEATURE_NAMES,
        embedding_dim=8,
        hidden_dim=16,
    )


def test_candidate_actor_scores_each_proposal_from_history_semantics_and_geometry() -> None:
    actor = _actor()
    history = torch.zeros((1, 6))
    candidate_ids = torch.tensor([[0, 12, 12]])
    features = torch.zeros((1, 3, len(CANDIDATE_GEOMETRY_FEATURE_NAMES)))
    features[0, 1, 2] = 0.25
    features[0, 2, 2] = 0.75

    scores, actions = actor(history, candidate_ids, features)

    assert scores.shape == (1, 3)
    assert actions.shape == (1, 3, 4)
    assert not torch.equal(scores[:, 1], scores[:, 2])
    assert not torch.equal(actions[:, 1], actions[:, 2])

    changed_history = history.clone()
    changed_history[0, 2] = 1.0
    changed_scores, _ = actor(changed_history, candidate_ids, features)
    assert not torch.equal(scores, changed_scores)


def test_candidate_actor_backpropagates_through_candidate_geometry() -> None:
    actor = _actor()
    history = torch.randn(2, 6)
    candidate_ids = torch.tensor([[0, 3], [0, 7]])
    features = torch.randn(2, 2, len(CANDIDATE_GEOMETRY_FEATURE_NAMES), requires_grad=True)

    scores, actions = actor(history, candidate_ids, features)
    (scores.sum() + actions.sum()).backward()

    assert features.grad is not None
    assert torch.isfinite(features.grad).all()
    assert features.grad.abs().sum() > 0


def test_candidate_actor_rejects_bad_shapes_ids_and_nonfinite_inputs() -> None:
    actor = _actor()
    history = torch.zeros((1, 6))
    ids = torch.tensor([[0, 1]])
    features = torch.zeros((1, 2, len(CANDIDATE_GEOMETRY_FEATURE_NAMES)))

    with pytest.raises(ValueError, match="integer tensor dtype"):
        actor(history, ids.float(), features)
    with pytest.raises(ValueError, match="outside the configured"):
        actor(history, torch.tensor([[0, 109]]), features)
    with pytest.raises(ValueError, match="must be finite"):
        actor(history, ids, features.fill_(float("nan")))


def test_eligibility_mask_keeps_no_trade_and_assigns_no_probability_to_invalid_rows() -> None:
    scores = torch.tensor([[0.0, 1.0, 2.0], [3.0, 4.0, 5.0]])
    eligible = torch.tensor([[True, False, True], [True, True, False]])

    masked = apply_candidate_eligibility_mask(scores, eligible)

    probabilities = torch.softmax(masked, dim=-1)
    assert torch.equal(probabilities[~eligible], torch.zeros_like(probabilities[~eligible]))
    assert torch.allclose(probabilities.sum(dim=1), torch.ones(2))


@pytest.mark.parametrize(
    ("eligible", "message"),
    [
        (torch.tensor([[False, True]]), "no-trade candidate must be eligible"),
        (torch.tensor([[True, False]], dtype=torch.float32), "must be a boolean tensor"),
    ],
)
def test_eligibility_mask_rejects_invalid_no_trade_contract(
    eligible: torch.Tensor, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        apply_candidate_eligibility_mask(torch.zeros((1, 2)), eligible)
