"""Behavior contracts for hybrid Box action encodings."""

from __future__ import annotations

import pytest
import torch

from learning.rl.hybrid import (
    HybridActorHeads,
    HybridBoxDistribution,
    TradeSetupConditionedActorHeads,
    TradeSetupConditionedHybridBoxDistribution,
    _encoded_centers,
)


@pytest.mark.parametrize(
    ("coordinates", "message"),
    [
        (("risk",), "at least one categorical coordinate"),
        (("exit",), "at least one continuous coordinate"),
    ],
)
def test_hybrid_actor_requires_both_action_families(
    coordinates: tuple[str, ...], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        HybridActorHeads(3, coordinates, {})


def test_hybrid_actor_rejects_invalid_defer_threshold() -> None:
    with pytest.raises(ValueError, match="defer threshold"):
        HybridActorHeads(3, ("sl_mode", "risk"), {"sl_mode": 1.0 / 6.0})


def test_encoded_centers_reject_unknown_categories() -> None:
    with pytest.raises(ValueError, match="unsupported categorical action coordinate"):
        _encoded_centers("made_up_mode", 0.0)


def test_flat_distribution_samples_and_scores_non_setup_categorical_actions() -> None:
    actor = HybridActorHeads(3, ("exit", "risk"), {})
    means, logits = actor(torch.zeros((2, 3)))
    distribution = HybridBoxDistribution(actor, action_width=2)

    with pytest.raises(NotImplementedError, match="built by HybridActorHeads"):
        distribution.proba_distribution_net(3)

    actions, log_prob = distribution.log_prob_from_params(means, torch.zeros(1), logits)

    assert actions.shape == (2, 2)
    assert log_prob.shape == (2,)
    assert torch.isfinite(log_prob).all()
    assert distribution.categorical_coordinate_entropy("exit") is not None
    assert distribution.categorical_coordinate_entropy("risk") is None
    assert torch.isfinite(distribution.entropy()).all()


def test_setup_conditioned_distribution_rejects_missing_mask_and_generic_factory() -> None:
    actor = TradeSetupConditionedActorHeads(3, ("trade_setup", "risk"), {})
    distribution = TradeSetupConditionedHybridBoxDistribution(actor, action_width=2)

    with pytest.raises(NotImplementedError, match="built by TradeSetupConditionedActorHeads"):
        distribution.proba_distribution_net(3)
    with pytest.raises(ValueError, match="requires its eligibility mask"):
        distribution.proba_distribution(
            torch.zeros((1, 3)),
            torch.zeros(1),
            torch.zeros((1, len(_encoded_centers("trade_setup", 0.0)))),
        )


def test_setup_conditioned_actor_requires_continuous_execution_coordinate() -> None:
    with pytest.raises(ValueError, match="requires continuous execution coordinates"):
        TradeSetupConditionedActorHeads(3, ("trade_setup",), {})
