"""Shared candidate scorer conditioned on market history and executable geometry."""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

import torch
from torch import nn

from decisioning.trade_setup import (
    CANDIDATE_GEOMETRY_FEATURE_NAMES,
    CANDIDATE_GEOMETRY_FEATURE_VERSION,
)

CANDIDATE_GEOMETRY_FEATURE_SCHEMA_VERSION = CANDIDATE_GEOMETRY_FEATURE_VERSION


class CandidateGeometryActorHeads(nn.Module):
    """Score candidate proposals and produce candidate-conditional actions.

    ``candidate_ids`` carry stable setup semantics; ``candidate_features`` carry
    proposal-specific price, risk, timing, and evidence values. Multiple price
    proposals may therefore share a setup ID while receiving different scores
    and execution parameters.
    """

    def __init__(
        self,
        market_latent_dim: int,
        candidate_feature_dim: int,
        action_dim: int,
        *,
        candidate_count: int,
        candidate_feature_names: Sequence[str],
        candidate_feature_schema_version: str = CANDIDATE_GEOMETRY_FEATURE_SCHEMA_VERSION,
        embedding_dim: int = 32,
        hidden_dim: int = 128,
    ) -> None:
        """Initialize a candidate-geometry actor from named feature dimensions.

        Args:
            market_latent_dim: Width of the market-state representation.
            candidate_feature_dim: Width of each candidate geometry vector.
            action_dim: Width of each candidate's continuous action vector.
            candidate_count: Number of candidate slots, including no-trade.
            candidate_feature_names: Ordered names matching the feature dimension.
            candidate_feature_schema_version: Version identifying the feature contract.
            embedding_dim: Width of each setup/timeframe embedding.
            hidden_dim: Width of the shared candidate-scoring network.
        """
        super().__init__()
        dimensions = (market_latent_dim, candidate_feature_dim, action_dim, candidate_count)
        if any(isinstance(value, bool) or int(value) < 1 for value in dimensions):
            raise ValueError("candidate actor dimensions and candidate count must be positive")
        if embedding_dim < 1 or hidden_dim < 1:
            raise ValueError("candidate actor hidden dimensions must be positive")
        feature_names = tuple(str(name) for name in candidate_feature_names)
        if len(feature_names) != int(candidate_feature_dim):
            raise ValueError("candidate feature names must match the configured feature width")
        if any(not name.strip() for name in feature_names) or len(set(feature_names)) != len(
            feature_names
        ):
            raise ValueError("candidate feature names must be non-empty and unique")
        if candidate_feature_schema_version != CANDIDATE_GEOMETRY_FEATURE_SCHEMA_VERSION:
            raise ValueError("unsupported candidate geometry feature schema version")

        self.candidate_count = int(candidate_count)
        self.candidate_feature_dim = int(candidate_feature_dim)
        self.action_dim = int(action_dim)
        self.hidden_dim = int(hidden_dim)
        self.candidate_feature_names = feature_names
        self.candidate_feature_schema_version = candidate_feature_schema_version
        self.candidate_embedding = nn.Embedding(self.candidate_count, embedding_dim)
        self.geometry_encoder = nn.Sequential(
            nn.Linear(self.candidate_feature_dim, hidden_dim),
            nn.Tanh(),
            nn.Linear(hidden_dim, embedding_dim),
            nn.Tanh(),
        )
        joint_dim = int(market_latent_dim) + 2 * embedding_dim
        self.shared_candidate_body = nn.Sequential(
            nn.Linear(joint_dim, self.hidden_dim),
            nn.Tanh(),
            nn.Linear(self.hidden_dim, self.hidden_dim),
            nn.Tanh(),
        )
        self.score = nn.Linear(hidden_dim, 1)
        self.conditional_action = nn.Linear(hidden_dim, self.action_dim)

        nn.init.orthogonal_(self.score.weight, gain=0.01)
        nn.init.zeros_(self.score.bias)
        nn.init.orthogonal_(self.conditional_action.weight, gain=0.01)
        nn.init.zeros_(self.conditional_action.bias)

    def encode_candidates(
        self,
        market_latent: torch.Tensor,
        candidate_ids: torch.Tensor,
        candidate_features: torch.Tensor,
    ) -> torch.Tensor:
        """Return the shared hidden representation for every candidate slot.

        This is intentionally public inside the learning package so a
        hierarchical distribution can use exactly the same candidate
        representation for selection and for selected-candidate execution
        controls instead of rebuilding a second geometry network.
        """
        if market_latent.ndim != 2:
            raise ValueError("market_latent must have shape [batch, latent]")
        if candidate_ids.ndim != 2:
            raise ValueError("candidate_ids must have shape [batch, candidates]")
        if candidate_features.ndim != 3:
            raise ValueError("candidate_features must have shape [batch, candidates, features]")
        batch, candidate_slots = candidate_ids.shape
        if candidate_slots < 1:
            raise ValueError("candidate set must contain at least the no-trade candidate")
        if candidate_features.shape != (
            batch,
            candidate_slots,
            self.candidate_feature_dim,
        ):
            raise ValueError("candidate feature shape does not match IDs and configured width")
        if market_latent.shape[0] != batch:
            raise ValueError("market and candidate batch dimensions differ")
        if candidate_ids.dtype not in (torch.int32, torch.int64):
            raise ValueError("candidate_ids must use an integer tensor dtype")
        if bool(((candidate_ids < 0) | (candidate_ids >= self.candidate_count)).any()):
            raise ValueError("candidate ID is outside the configured semantic catalog")
        if not bool(torch.isfinite(market_latent).all()):
            raise ValueError("market_latent must be finite")
        if not bool(torch.isfinite(candidate_features).all()):
            raise ValueError("candidate_features must be finite")

        semantic = self.candidate_embedding(candidate_ids.long())
        geometry = self.geometry_encoder(candidate_features)
        context = market_latent[:, None, :].expand(-1, candidate_slots, -1)
        joint = torch.cat((context, semantic, geometry), dim=-1)
        return cast(torch.Tensor, self.shared_candidate_body(joint))

    def forward(
        self,
        market_latent: torch.Tensor,
        candidate_ids: torch.Tensor,
        candidate_features: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Return one shared score and action-parameter vector per candidate."""
        hidden = self.encode_candidates(market_latent, candidate_ids, candidate_features)
        return self.score(hidden).squeeze(-1), self.conditional_action(hidden)


def apply_candidate_eligibility_mask(
    scores: torch.Tensor,
    eligible: torch.Tensor,
    *,
    no_trade_slot: int = 0,
) -> torch.Tensor:
    """Mask invalid proposals and require the designated no-trade slot.

    Args:
        scores: Candidate scores with shape ``[batch, slots]``.
        eligible: Boolean candidate eligibility mask with the same shape.
        no_trade_slot: Slot that must remain eligible in every batch item.

    Returns:
        Scores with ineligible candidates set to the dtype's minimum value.
    """
    if scores.ndim != 2 or eligible.shape != scores.shape:
        raise ValueError("candidate scores and eligibility must have matching [batch, slots] shape")
    if eligible.dtype != torch.bool:
        raise ValueError("candidate eligibility must be a boolean tensor")
    if isinstance(no_trade_slot, bool) or not 0 <= no_trade_slot < scores.shape[1]:
        raise ValueError("no_trade_slot is outside the candidate set")
    if not bool(eligible[:, no_trade_slot].all()):
        raise ValueError("no-trade candidate must be eligible for every observation")
    if not bool(eligible.any(dim=1).all()):
        raise ValueError("each observation must have an eligible candidate")
    return scores.masked_fill(~eligible.to(device=scores.device), torch.finfo(scores.dtype).min)


__all__ = [
    "CANDIDATE_GEOMETRY_FEATURE_NAMES",
    "CANDIDATE_GEOMETRY_FEATURE_SCHEMA_VERSION",
    "CandidateGeometryActorHeads",
    "apply_candidate_eligibility_mask",
]
