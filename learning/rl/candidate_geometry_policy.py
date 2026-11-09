"""Price-aware PPO policy over fixed candidate-geometry slots."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast

import torch
from stable_baselines3.common.distributions import Distribution as SB3Distribution
from torch import nn
from torch.distributions import Categorical, Normal

from decisioning.trade_setup import (
    CANDIDATE_GEOMETRY_FEATURE_NAMES,
    TRADE_SETUP_CATEGORY_COUNT,
    candidate_geometry_slot_count,
    candidate_geometry_slot_semantics,
    trade_setup_center,
)
from learning.rl.candidate_geometry import (
    CandidateGeometryActorHeads,
    apply_candidate_eligibility_mask,
)
from learning.rl.hybrid import (
    HybridClampedStdMultiInputPolicy,
    _categorical_distribution,
    _encoded_centers,
    _normal_distribution,
)
from learning.rl.ppo import clip_policy_log_std

_DETERMINISTIC_SLOT_COORDINATES = {
    "trade_setup",
    "entry_execution",
    "limit_offset_atr",
    "limit_ttl_bars",
}
_EXECUTION_CATEGORICAL_COORDINATES = {"sl_mode", "tp_mode", "exit"}


class CandidateGeometryConditionedActorHeads(nn.Module):
    """Select a 217-slot entry hypothesis then parameterize its execution controls."""

    def __init__(
        self,
        latent_dim: int,
        coordinates: Sequence[str],
        thresholds: dict[str, float],
        *,
        embedding_dim: int = 32,
        hidden_dim: int = 128,
    ) -> None:
        """Initialize candidate scoring and selected-candidate execution heads.

        Args:
            latent_dim: Width of the encoded market state.
            coordinates: Ordered continuous and categorical action coordinates.
            thresholds: Categorical defer thresholds keyed by coordinate name.
            embedding_dim: Width of setup and geometry embeddings.
            hidden_dim: Width of candidate and execution hidden layers.
        """
        super().__init__()
        self.coordinates = tuple(str(value) for value in coordinates)
        required = {
            "trade_setup",
            "entry_execution",
            "limit_offset_atr",
            "limit_ttl_bars",
        }
        missing = required.difference(self.coordinates)
        if missing:
            raise ValueError(
                "candidate-geometry policy requires setup and entry-execution coordinates: "
                f"{sorted(missing)}"
            )
        self.coordinate_indices = {name: index for index, name in enumerate(self.coordinates)}
        self.execution_categorical_indices = {
            name: index
            for index, name in enumerate(self.coordinates)
            if name in _EXECUTION_CATEGORICAL_COORDINATES
        }
        self.continuous_indices = tuple(
            index
            for index, name in enumerate(self.coordinates)
            if name not in _DETERMINISTIC_SLOT_COORDINATES
            and name not in _EXECUTION_CATEGORICAL_COORDINATES
        )
        if not self.continuous_indices:
            raise ValueError(
                "candidate-geometry policy requires stochastic continuous execution controls"
            )
        self.centers = {
            name: _encoded_centers(name, float(thresholds.get(name, 0.0)))
            for name in self.execution_categorical_indices
        }
        self.selector = CandidateGeometryActorHeads(
            market_latent_dim=int(latent_dim),
            candidate_feature_dim=len(CANDIDATE_GEOMETRY_FEATURE_NAMES),
            action_dim=1,
            candidate_count=TRADE_SETUP_CATEGORY_COUNT,
            candidate_feature_names=CANDIDATE_GEOMETRY_FEATURE_NAMES,
            embedding_dim=int(embedding_dim),
            hidden_dim=int(hidden_dim),
        )
        selector_hidden = int(self.selector.hidden_dim)
        self.execution_body = nn.Sequential(
            nn.Linear(int(latent_dim) + selector_hidden, int(hidden_dim)),
            nn.SiLU(),
            nn.Linear(int(hidden_dim), int(hidden_dim)),
            nn.SiLU(),
        )
        self.continuous_mean = nn.Linear(int(hidden_dim), len(self.continuous_indices))
        self.execution_categorical_logits = nn.ModuleDict(
            {
                name: nn.Linear(int(hidden_dim), len(self.centers[name]))
                for name in self.execution_categorical_indices
            }
        )
        self.reset_parameters()

    def reset_parameters(self) -> None:
        """Initialize execution heads with stable orthogonal weights."""
        for module in self.execution_body:
            if isinstance(module, nn.Linear):
                nn.init.orthogonal_(module.weight, gain=1.0)
                nn.init.zeros_(module.bias)
        nn.init.orthogonal_(self.continuous_mean.weight, gain=0.01)
        nn.init.zeros_(self.continuous_mean.bias)
        for layer in self.execution_categorical_logits.values():
            if not isinstance(layer, nn.Linear):
                raise TypeError("execution categorical head must be a linear layer")
            nn.init.orthogonal_(layer.weight, gain=0.01)
            nn.init.zeros_(layer.bias)

    def candidate_logits(
        self,
        market_latent: torch.Tensor,
        candidate_ids: torch.Tensor,
        candidate_features: torch.Tensor,
    ) -> torch.Tensor:
        """Score entry hypotheses with market state and causal price geometry.

        Args:
            market_latent: Encoded market state for each batch row.
            candidate_ids: Stable semantic IDs for all fixed candidate slots.
            candidate_features: Causal geometry features for every slot.

        Returns:
            Unmasked selector logits for each candidate slot.
        """
        scores, _ = self.selector(
            market_latent,
            candidate_ids.long(),
            candidate_features,
        )
        return cast(torch.Tensor, scores)

    def execution(
        self,
        market_latent: torch.Tensor,
        candidate_ids: torch.Tensor,
        candidate_features: torch.Tensor,
        selected_slots: torch.Tensor,
    ) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
        """Condition execution controls on the selected candidate geometry.

        Args:
            market_latent: Encoded market state for each batch row.
            candidate_ids: Stable semantic IDs for all fixed candidate slots.
            candidate_features: Causal geometry features for every slot.
            selected_slots: Chosen candidate slot for each batch row.

        Returns:
            Continuous means and named categorical logits for execution controls.
        """
        encoded = self.selector.encode_candidates(
            market_latent,
            candidate_ids.long(),
            candidate_features,
        )
        rows = torch.arange(
            selected_slots.shape[0],
            dtype=torch.long,
            device=selected_slots.device,
        )
        selected = encoded[rows, selected_slots.long()]
        context = self.execution_body(torch.cat((market_latent, selected), dim=-1))
        means = cast(torch.Tensor, self.continuous_mean(context))
        logits = {name: layer(context) for name, layer in self.execution_categorical_logits.items()}
        return means, logits


class CandidateGeometryHybridBoxDistribution(SB3Distribution):
    """Hierarchical distribution over candidate slot and conditional execution."""

    def __init__(
        self,
        actor: CandidateGeometryConditionedActorHeads,
        action_width: int,
        *,
        max_limit_offset_atr: float,
        max_limit_ttl_bars: int,
    ) -> None:
        """Create a hierarchical candidate and execution distribution.

        Args:
            actor: Network that scores candidates and parameterizes execution.
            action_width: Width of the environment's hybrid Box action.
            max_limit_offset_atr: Maximum encoded passive-entry offset in ATRs.
            max_limit_ttl_bars: Maximum encoded limit-order lifetime in bars.
        """
        super().__init__()  # type: ignore[no-untyped-call]
        if max_limit_offset_atr <= 0.0:
            raise ValueError("max_limit_offset_atr must be positive")
        if max_limit_ttl_bars < 1:
            raise ValueError("max_limit_ttl_bars must be positive")
        self.actor = actor
        self.action_width = int(action_width)
        self.max_limit_offset_atr = float(max_limit_offset_atr)
        self.max_limit_ttl_bars = int(max_limit_ttl_bars)
        self.market_latent: torch.Tensor | None = None
        self.log_std: torch.Tensor | None = None
        self.candidate_ids: torch.Tensor | None = None
        self.candidate_features: torch.Tensor | None = None
        self.candidate_mask: torch.Tensor | None = None
        self.candidate: Categorical | None = None
        self.categorical: dict[str, Categorical] = {}

    def proba_distribution_net(self, *args: Any, **kwargs: Any) -> nn.Module:
        """Reject SB3's flat-head construction path for this hierarchical policy.

        Args:
            *args: Positional arguments supplied by the SB3 distribution API.
            **kwargs: Keyword arguments supplied by the SB3 distribution API.

        Returns:
            A neural module; this implementation raises because heads are policy-owned.
        """
        del args, kwargs
        raise NotImplementedError("candidate-geometry hierarchical heads are built by the policy")

    def proba_distribution(
        self,
        market_latent: torch.Tensor,
        log_std: torch.Tensor,
        candidate_ids: torch.Tensor,
        candidate_features: torch.Tensor,
        candidate_mask: torch.Tensor,
    ) -> CandidateGeometryHybridBoxDistribution:
        """Bind current policy inputs and create the masked candidate selector.

        Args:
            market_latent: Encoded market state for each batch row.
            log_std: Log standard deviation for stochastic continuous controls.
            candidate_ids: Stable semantic IDs for the fixed candidate slots.
            candidate_features: Causal geometry features for each slot.
            candidate_mask: Boolean eligibility mask with no-trade enabled.

        Returns:
            This distribution with selector probabilities bound to the inputs.
        """
        if candidate_ids.ndim != 2 or candidate_ids.shape[1] != candidate_geometry_slot_count():
            raise ValueError("candidate_ids must have the versioned [batch, 217] layout")
        if candidate_ids.dtype not in (torch.int32, torch.int64):
            raise ValueError("candidate_ids must use an integer tensor dtype")
        expected_ids = torch.tensor(
            [
                candidate_geometry_slot_semantics(slot)[0]
                for slot in range(candidate_geometry_slot_count())
            ],
            dtype=torch.long,
            device=candidate_ids.device,
        )
        if not torch.equal(candidate_ids.long(), expected_ids.expand_as(candidate_ids)):
            raise ValueError("candidate_ids do not match the fixed slot semantics")
        if candidate_mask.dtype != torch.bool:
            raise ValueError("candidate_mask must use boolean eligibility values")
        if candidate_features.shape != (
            candidate_ids.shape[0],
            candidate_geometry_slot_count(),
            len(CANDIDATE_GEOMETRY_FEATURE_NAMES),
        ):
            raise ValueError("candidate_features do not match the versioned geometry schema")
        if not bool(torch.isfinite(candidate_features).all()):
            raise ValueError("candidate_features must be finite")
        self.market_latent = market_latent
        self.log_std = log_std
        self.candidate_ids = candidate_ids.long()
        self.candidate_features = candidate_features
        self.candidate_mask = candidate_mask
        logits = self.actor.candidate_logits(market_latent, self.candidate_ids, candidate_features)
        if logits.shape != self.candidate_mask.shape:
            raise ValueError("candidate geometry mask must match candidate logits")
        if not bool(self.candidate_mask.any(dim=1).all()):
            raise ValueError("candidate geometry mask must leave at least one slot")
        masked_logits = apply_candidate_eligibility_mask(
            logits,
            self.candidate_mask,
            no_trade_slot=0,
        )
        self.candidate = _categorical_distribution(masked_logits)
        return self

    def _require_context(
        self,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        """Return bound market and candidate tensors or raise before use.

        Returns:
            Market latent, log standard deviation, candidate IDs, and features.
        """
        if (
            self.market_latent is None
            or self.log_std is None
            or self.candidate_ids is None
            or self.candidate_features is None
        ):
            raise RuntimeError("call proba_distribution before using the policy")
        return (
            self.market_latent,
            self.log_std,
            self.candidate_ids,
            self.candidate_features,
        )

    def _selected_distributions(
        self, selected_slots: torch.Tensor
    ) -> tuple[Normal, dict[str, Categorical]]:
        """Build execution distributions conditioned on each selected slot.

        Args:
            selected_slots: Candidate slot index for each batch row.

        Returns:
            Continuous control distribution and named categorical distributions.
        """
        market, log_std, candidate_ids, candidate_features = self._require_context()
        means, logits = self.actor.execution(
            market, candidate_ids, candidate_features, selected_slots
        )
        normal = _normal_distribution(means, log_std.exp().expand_as(means))
        categorical = {name: _categorical_distribution(values) for name, values in logits.items()}
        self.categorical = categorical
        return normal, categorical

    @staticmethod
    def _setup_and_entry_ids(selected_slots: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Decode candidate slot indices into stable setup and entry IDs.

        Args:
            selected_slots: Fixed candidate slot indices, including no-trade zero.

        Returns:
            Setup IDs and market/limit entry IDs as integer tensors.
        """
        nonzero = selected_slots > 0
        setup_ids = torch.where(
            nonzero,
            torch.div(selected_slots - 1, 2, rounding_mode="floor") + 1,
            torch.zeros_like(selected_slots),
        )
        entry_ids = torch.where(
            nonzero,
            torch.remainder(selected_slots - 1, 2),
            torch.zeros_like(selected_slots),
        )
        return setup_ids.long(), entry_ids.long()

    def _slot_ids_from_actions(self, actions: torch.Tensor) -> torch.Tensor:
        """Recover selected slots from encoded setup and entry coordinates.

        Args:
            actions: Packed hybrid action tensor.

        Returns:
            Candidate slot index for each action row.
        """
        setup_index = self.actor.coordinate_indices["trade_setup"]
        entry_index = self.actor.coordinate_indices["entry_execution"]
        setup_centers = actions.new_tensor(
            [trade_setup_center(index) for index in range(TRADE_SETUP_CATEGORY_COUNT)]
        )
        entry_centers = actions.new_tensor((-0.5, 0.5))
        setup_ids = (
            (actions[:, setup_index : setup_index + 1] - setup_centers[None, :]).abs().argmin(dim=1)
        )
        entry_ids = (
            (actions[:, entry_index : entry_index + 1] - entry_centers[None, :]).abs().argmin(dim=1)
        )
        return torch.where(
            setup_ids == 0,
            torch.zeros_like(setup_ids),
            1 + (setup_ids - 1) * 2 + entry_ids,
        ).long()

    def _execution_class_ids(self, actions: torch.Tensor) -> dict[str, torch.Tensor]:
        """Decode categorical execution coordinates to their nearest class IDs.

        Args:
            actions: Packed hybrid action tensor.

        Returns:
            Categorical class IDs keyed by execution coordinate name.
        """
        result: dict[str, torch.Tensor] = {}
        for name, index in self.actor.execution_categorical_indices.items():
            centers = actions.new_tensor(self.actor.centers[name])
            result[name] = (actions[:, index : index + 1] - centers[None, :]).abs().argmin(dim=1)
        return result

    def _pack(
        self,
        selected_slots: torch.Tensor,
        continuous: torch.Tensor,
        classes: dict[str, torch.Tensor],
    ) -> torch.Tensor:
        """Pack selected candidate and conditional controls into Box actions.

        Args:
            selected_slots: Candidate slot index for each batch row.
            continuous: Sampled or modal continuous execution controls.
            classes: Categorical execution class IDs keyed by coordinate.

        Returns:
            Environment action tensor with deterministic slot values encoded.
        """
        market, _, _, candidate_features = self._require_context()
        output = market.new_zeros((market.shape[0], self.action_width))
        continuous_index = torch.as_tensor(
            self.actor.continuous_indices, dtype=torch.long, device=output.device
        )
        output = output.index_copy(1, continuous_index, continuous)

        setup_ids, entry_ids = self._setup_and_entry_ids(selected_slots)
        setup_centers = output.new_tensor(
            [trade_setup_center(index) for index in range(TRADE_SETUP_CATEGORY_COUNT)]
        )
        output[:, self.actor.coordinate_indices["trade_setup"]] = setup_centers[setup_ids]
        output[:, self.actor.coordinate_indices["entry_execution"]] = output.new_tensor(
            (-0.5, 0.5)
        )[entry_ids]

        rows = torch.arange(selected_slots.shape[0], device=selected_slots.device)
        offset_index = CANDIDATE_GEOMETRY_FEATURE_NAMES.index("entry_price_offset_atr")
        ttl_index = CANDIDATE_GEOMETRY_FEATURE_NAMES.index("limit_ttl_fraction")
        selected_features = candidate_features[rows, selected_slots.long()]
        offset = selected_features[:, offset_index].abs()
        offset_unit = torch.clamp(offset / self.max_limit_offset_atr, 0.0, 1.0)
        ttl_fraction = torch.clamp(selected_features[:, ttl_index], 0.0, 1.0)
        desired_ttl = torch.clamp(
            torch.round(ttl_fraction * self.max_limit_ttl_bars),
            min=1.0,
            max=float(self.max_limit_ttl_bars),
        )
        ttl_unit = (desired_ttl - 0.5) / float(self.max_limit_ttl_bars)
        output[:, self.actor.coordinate_indices["limit_offset_atr"]] = 2.0 * offset_unit - 1.0
        output[:, self.actor.coordinate_indices["limit_ttl_bars"]] = 2.0 * ttl_unit - 1.0

        for name, class_ids in classes.items():
            output[:, self.actor.execution_categorical_indices[name]] = output.new_tensor(
                self.actor.centers[name]
            )[class_ids]
        active = selected_slots > 0
        continuous_index = torch.as_tensor(
            self.actor.continuous_indices, dtype=torch.long, device=output.device
        )
        output[:, continuous_index] = torch.where(
            active[:, None],
            output.index_select(1, continuous_index),
            output.new_zeros((output.shape[0], len(self.actor.continuous_indices))),
        )
        for index in self.actor.execution_categorical_indices.values():
            output[:, index] = torch.where(active, output[:, index], 0.0)
        return output

    def sample(self) -> torch.Tensor:
        """Sample a candidate and its conditional stochastic execution controls.

        Returns:
            Packed stochastic action tensor.
        """
        if self.candidate is None:
            raise RuntimeError("call proba_distribution before sampling")
        slots = cast(torch.Tensor, self.candidate.sample())  # type: ignore[no-untyped-call]
        normal, categorical = self._selected_distributions(slots)
        classes = {
            name: cast(torch.Tensor, distribution.sample())  # type: ignore[no-untyped-call]
            for name, distribution in categorical.items()
        }
        return self._pack(slots, normal.rsample(), classes)

    def mode(self) -> torch.Tensor:
        """Select selector and conditional execution modes deterministically.

        Returns:
            Packed deterministic action tensor.
        """
        if self.candidate is None:
            raise RuntimeError("call proba_distribution before selecting a mode")
        slots = self.candidate.logits.argmax(dim=-1)
        normal, categorical = self._selected_distributions(slots)
        classes = {
            name: distribution.logits.argmax(dim=-1) for name, distribution in categorical.items()
        }
        return self._pack(slots, normal.mean, classes)

    def get_actions(self, deterministic: bool = False) -> torch.Tensor:
        """Choose deterministic mode or stochastic sample according to the flag.

        Args:
            deterministic: Whether to return the distribution mode.

        Returns:
            Packed hybrid action tensor.
        """
        return self.mode() if deterministic else self.sample()

    def actions_from_params(
        self,
        market_latent: torch.Tensor,
        log_std: torch.Tensor,
        candidate_ids: torch.Tensor,
        candidate_features: torch.Tensor,
        candidate_mask: torch.Tensor,
        deterministic: bool = False,
    ) -> torch.Tensor:
        """Bind distribution parameters and produce an action.

        Args:
            market_latent: Encoded market state for each batch row.
            log_std: Log standard deviation for continuous execution controls.
            candidate_ids: Stable semantic IDs for the fixed candidate slots.
            candidate_features: Causal geometry features for each candidate.
            candidate_mask: Boolean candidate eligibility mask.
            deterministic: Whether to choose distribution modes.

        Returns:
            Packed hybrid action tensor.
        """
        self.proba_distribution(
            market_latent,
            log_std,
            candidate_ids,
            candidate_features,
            candidate_mask,
        )
        return self.get_actions(deterministic)

    def log_prob_from_params(
        self,
        market_latent: torch.Tensor,
        log_std: torch.Tensor,
        candidate_ids: torch.Tensor,
        candidate_features: torch.Tensor,
        candidate_mask: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Sample from supplied parameters and compute the joint action log probability.

        Args:
            market_latent: Encoded market state for each batch row.
            log_std: Log standard deviation for continuous execution controls.
            candidate_ids: Stable semantic IDs for the fixed candidate slots.
            candidate_features: Causal geometry features for each candidate.
            candidate_mask: Boolean candidate eligibility mask.

        Returns:
            Sampled action and its joint log probability.
        """
        actions = self.actions_from_params(
            market_latent,
            log_std,
            candidate_ids,
            candidate_features,
            candidate_mask,
        )
        return actions, self.log_prob(actions)

    def log_prob(self, actions: torch.Tensor) -> torch.Tensor:
        """Evaluate selector and active conditional-control log probabilities.

        Args:
            actions: Packed actions whose joint likelihood is evaluated.

        Returns:
            One joint log probability per batch row.
        """
        if self.candidate is None:
            raise RuntimeError("call proba_distribution before evaluating actions")
        slots = self._slot_ids_from_actions(actions)
        normal, categorical = self._selected_distributions(slots)
        continuous_index = torch.as_tensor(
            self.actor.continuous_indices, dtype=torch.long, device=actions.device
        )
        result = cast(
            torch.Tensor,
            self.candidate.log_prob(slots),  # type: ignore[no-untyped-call]
        )
        conditional_log_prob = cast(
            torch.Tensor,
            normal.log_prob(  # type: ignore[no-untyped-call]
                actions.index_select(1, continuous_index)
            ),
        ).sum(dim=1)
        classes = self._execution_class_ids(actions)
        for name, distribution in categorical.items():
            conditional_log_prob = conditional_log_prob + cast(
                torch.Tensor,
                distribution.log_prob(classes[name]),  # type: ignore[no-untyped-call]
            )
        return result + torch.where(slots > 0, conditional_log_prob, 0.0)

    def trade_setup_entropy(self) -> torch.Tensor:
        """Return entropy of the joint setup and entry candidate selector.

        Returns:
            Selector entropy for each batch row.
        """
        if self.candidate is None:
            raise RuntimeError("call proba_distribution before reading entropy")
        return cast(torch.Tensor, self.candidate.entropy())  # type: ignore[no-untyped-call]

    def trade_setup_probabilities(self) -> torch.Tensor:
        """Aggregate joint candidate probabilities to stable setup IDs.

        Returns:
            Probability for each of the 109 setup IDs, including no-trade.
        """
        if self.candidate is None:
            raise RuntimeError("call proba_distribution before reading probabilities")
        probabilities = self.candidate.probs
        result = probabilities.new_zeros((probabilities.shape[0], TRADE_SETUP_CATEGORY_COUNT))
        result[:, 0] = probabilities[:, 0]
        paired = probabilities[:, 1:].reshape(
            probabilities.shape[0], TRADE_SETUP_CATEGORY_COUNT - 1, 2
        )
        result[:, 1:] = paired.sum(dim=-1)
        return result

    def categorical_coordinate_entropy(self, name: str) -> torch.Tensor | None:
        """Return entropy for an action categorical coordinate when available.

        Args:
            name: Categorical action coordinate name.

        Returns:
            Coordinate entropy, or ``None`` when the coordinate is not tracked.
        """
        if name == "entry_execution":
            if self.candidate is None:
                return None
            probabilities = (
                self.candidate.probs[:, 1:]
                .reshape(self.candidate.probs.shape[0], TRADE_SETUP_CATEGORY_COUNT - 1, 2)
                .sum(dim=1)
            )
            total = probabilities.sum(dim=1, keepdim=True)
            normalized = probabilities / torch.clamp(total, min=1e-12)
            return -(normalized * torch.log(torch.clamp(normalized, min=1e-12))).sum(dim=1)
        distribution = self.categorical.get(name)
        if distribution is None:
            return None
        return cast(torch.Tensor, distribution.entropy())  # type: ignore[no-untyped-call]

    def entropy(self) -> torch.Tensor:
        """Compute joint selector and candidate-weighted conditional entropy.

        Returns:
            One hierarchical entropy value per batch row.
        """
        if (
            self.candidate is None
            or self.candidate_mask is None
            or self.market_latent is None
            or self.log_std is None
            or self.candidate_ids is None
            or self.candidate_features is None
        ):
            raise RuntimeError("call proba_distribution before evaluating entropy")
        rows, slots = self.candidate_mask.nonzero(as_tuple=True)
        means, logits = self.actor.execution(
            self.market_latent[rows],
            self.candidate_ids[rows],
            self.candidate_features[rows],
            slots,
        )
        normal = _normal_distribution(means, self.log_std.exp().expand_as(means))
        conditional = cast(
            torch.Tensor,
            normal.entropy(),  # type: ignore[no-untyped-call]
        ).sum(dim=1)
        for values in logits.values():
            conditional = conditional + cast(
                torch.Tensor,
                _categorical_distribution(values).entropy(),  # type: ignore[no-untyped-call]
            )
        weighted = self.candidate.probs[rows, slots] * conditional * (slots > 0)
        by_row = weighted.new_zeros(self.market_latent.shape[0]).index_add(0, rows, weighted)
        return self.trade_setup_entropy() + by_row


class CandidateGeometryClampedStdMultiInputPolicy(HybridClampedStdMultiInputPolicy):
    """PPO policy whose primary categorical choice is a causal 217-slot candidate."""

    def __init__(
        self,
        *args: Any,
        candidate_ids_key: str = "candidate_ids",
        candidate_features_key: str = "candidate_features",
        candidate_mask_key: str = "candidate_mask",
        candidate_embedding_dim: int = 32,
        candidate_execution_hidden_dim: int = 128,
        max_limit_offset_atr: float = 1.0,
        max_limit_ttl_bars: int = 60,
        **kwargs: Any,
    ) -> None:
        """Configure PPO with candidate observation keys and geometry bounds.

        Args:
            *args: Positional constructor arguments forwarded to the base policy.
            candidate_ids_key: Observation key for stable candidate IDs.
            candidate_features_key: Observation key for candidate geometry vectors.
            candidate_mask_key: Observation key for boolean candidate eligibility.
            candidate_embedding_dim: Width of candidate semantic embeddings.
            candidate_execution_hidden_dim: Hidden width of conditional execution heads.
            max_limit_offset_atr: Maximum passive-entry offset encoded in ATRs.
            max_limit_ttl_bars: Maximum passive-entry lifetime encoded in bars.
            **kwargs: Additional base-policy constructor options.
        """
        self.candidate_ids_key = str(candidate_ids_key)
        self.candidate_features_key = str(candidate_features_key)
        self.candidate_mask_key = str(candidate_mask_key)
        self.candidate_embedding_dim = int(candidate_embedding_dim)
        self.candidate_execution_hidden_dim = int(candidate_execution_hidden_dim)
        self.max_limit_offset_atr = float(max_limit_offset_atr)
        self.max_limit_ttl_bars = int(max_limit_ttl_bars)
        self.candidate_actor: CandidateGeometryConditionedActorHeads | None = None
        self.candidate_distribution: CandidateGeometryHybridBoxDistribution | None = None
        super().__init__(*args, **kwargs)

    def _build(self, lr_schedule: Any) -> None:
        """Build candidate-conditioned heads and register optimizer parameters.

        Args:
            lr_schedule: Callable producing the learning rate at a progress value.
        """
        super(HybridClampedStdMultiInputPolicy, self)._build(lr_schedule)
        action_shape = getattr(self.action_space, "shape", None)
        if action_shape is None or len(action_shape) != 1:
            raise ValueError("candidate-geometry PPO requires a one-dimensional Box action")
        if len(self.hybrid_action_coordinates) != int(action_shape[0]):
            raise ValueError("hybrid coordinate count differs from action-space width")
        old_parameters = set(self.action_net.parameters()) | {self.log_std}
        actor = CandidateGeometryConditionedActorHeads(
            self.mlp_extractor.latent_dim_pi,
            self.hybrid_action_coordinates,
            self.hybrid_thresholds,
            embedding_dim=self.candidate_embedding_dim,
            hidden_dim=self.candidate_execution_hidden_dim,
        )
        self.action_net = actor
        self.candidate_actor = actor
        self.log_std = nn.Parameter(
            torch.full(
                (len(actor.continuous_indices),),
                float(self.log_std_init),
                device=self.device,
            )
        )
        for group in self.optimizer.param_groups:
            group["params"] = [
                parameter for parameter in group["params"] if parameter not in old_parameters
            ]
        self.optimizer.add_param_group(
            {"params": list(self.action_net.parameters()) + [self.log_std], "lr": lr_schedule(1)}
        )
        self.candidate_distribution = CandidateGeometryHybridBoxDistribution(
            actor,
            int(action_shape[0]),
            max_limit_offset_atr=self.max_limit_offset_atr,
            max_limit_ttl_bars=self.max_limit_ttl_bars,
        )

    def _set_distribution_mask(self, obs: Any) -> None:
        """Bind candidate IDs, features, and eligibility from observations.

        Args:
            obs: Dict observation containing the configured candidate keys.
        """
        if not isinstance(obs, dict):
            raise ValueError("candidate-geometry policy requires Dict observations")
        required = (
            self.candidate_ids_key,
            self.candidate_features_key,
            self.candidate_mask_key,
        )
        missing = [name for name in required if name not in obs]
        if missing:
            raise ValueError(f"candidate-geometry policy is missing observation keys: {missing}")
        self._distribution_masks = {
            "candidate_ids": obs[self.candidate_ids_key],
            "candidate_features": obs[self.candidate_features_key],
            "candidate_mask": obs[self.candidate_mask_key],
        }

    def _get_action_dist_from_latent(
        self, latent_pi: torch.Tensor
    ) -> CandidateGeometryHybridBoxDistribution:
        """Build the hierarchical action distribution for encoded observations.

        Args:
            latent_pi: Policy latent representing the current market state.

        Returns:
            Candidate selector and conditional execution distribution.
        """
        clip_policy_log_std(self, self.log_std_min, self.log_std_max)
        if self.candidate_actor is None or self.candidate_distribution is None:
            raise RuntimeError("candidate-geometry policy was not built")
        if self._distribution_masks is None:
            raise RuntimeError("candidate-geometry observations were not bound")
        distribution = self.candidate_distribution.proba_distribution(
            latent_pi,
            self.log_std,
            self._distribution_masks["candidate_ids"],
            self._distribution_masks["candidate_features"],
            self._distribution_masks["candidate_mask"],
        )
        self.last_trade_setup_entropy = distribution.trade_setup_entropy().detach()
        self.last_trade_setup_probabilities = distribution.trade_setup_probabilities().detach()
        return distribution

    def _get_constructor_parameters(self) -> dict[str, Any]:
        """Return constructor settings needed to reconstruct a saved policy.

        Returns:
            Base-policy and candidate-geometry constructor parameters.
        """
        data = super(HybridClampedStdMultiInputPolicy, self)._get_constructor_parameters()
        data.update(
            hybrid_action_coordinates=self.hybrid_action_coordinates,
            sl_mode_defer_threshold=self.hybrid_thresholds["sl_mode"],
            tp_mode_defer_threshold=self.hybrid_thresholds["tp_mode"],
            trade_setup_mask_key=self.trade_setup_mask_key,
            candidate_ids_key=self.candidate_ids_key,
            candidate_features_key=self.candidate_features_key,
            candidate_mask_key=self.candidate_mask_key,
            candidate_embedding_dim=self.candidate_embedding_dim,
            candidate_execution_hidden_dim=self.candidate_execution_hidden_dim,
            max_limit_offset_atr=self.max_limit_offset_atr,
            max_limit_ttl_bars=self.max_limit_ttl_bars,
        )
        return data


__all__ = [
    "CandidateGeometryClampedStdMultiInputPolicy",
    "CandidateGeometryConditionedActorHeads",
    "CandidateGeometryHybridBoxDistribution",
]
