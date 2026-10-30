"""Categorical modes plus Gaussian continuous coordinates for PPO Box actions."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast

import torch
from stable_baselines3.common.distributions import Distribution as SB3Distribution
from torch import nn
from torch.distributions import Categorical, Normal

from decisioning.thesis import THESIS_CATEGORY_COUNT, thesis_center
from learning.rl.ppo import ClampedStdMultiInputPolicy, clip_policy_log_std

_CATEGORICAL_COORDINATES = {"thesis", "sl_mode", "tp_mode", "exit"}


def _normal_distribution(means: torch.Tensor, scales: torch.Tensor) -> Normal:
    """Normalize version-dependent Torch stubs at the distribution boundary."""
    constructor: Any = Normal
    return cast(Normal, constructor(means, scales))


def _categorical_distribution(logits: torch.Tensor) -> Categorical:
    """Normalize version-dependent Torch stubs at the distribution boundary."""
    constructor: Any = Categorical
    return cast(Categorical, constructor(logits=logits))


def _encoded_centers(name: str, threshold: float) -> tuple[float, ...]:
    """Return normalized raw-Box values that the existing env decoder maps exactly."""
    if name == "thesis":
        return tuple(thesis_center(candidate_id) for candidate_id in range(THESIS_CATEGORY_COUNT))
    if name == "exit":
        return (-0.5, 0.5)  # structural, EMA-21
    if name in {"sl_mode", "tp_mode"}:
        if not 0.0 <= threshold < (1.0 / 6.0 - 1e-3):
            raise ValueError(f"hybrid {name} requires a defer threshold below 1/6, got {threshold}")
            # The center category means defer to the configured environment mode.
            # The breakeven value sits just outside the defer band but still decodes
            # to bucket one in the existing three-mode decoder.
        breakeven_u = 0.5 - threshold - 1e-3
        unit_values = (1.0 / 6.0, breakeven_u, 0.5, 5.0 / 6.0)
        return tuple(2.0 * value - 1.0 for value in unit_values)
    raise ValueError(f"unsupported categorical action coordinate: {name!r}")


class HybridActorHeads(nn.Module):
    """Separate categorical logits and Gaussian means over semantic coordinates."""

    def __init__(
        self, latent_dim: int, coordinates: Sequence[str], thresholds: dict[str, float]
    ) -> None:
        super().__init__()
        self.coordinates = tuple(str(value) for value in coordinates)
        self.categorical_indices = {
            name: index
            for index, name in enumerate(self.coordinates)
            if name in _CATEGORICAL_COORDINATES
        }
        if not self.categorical_indices:
            raise ValueError("hybrid distribution requires sl_mode, tp_mode, or exit coordinates")
        self.continuous_indices = tuple(
            index
            for index, name in enumerate(self.coordinates)
            if name not in self.categorical_indices
        )
        if not self.continuous_indices:
            raise ValueError("hybrid distribution requires at least one continuous coordinate")
        self.centers = {
            name: _encoded_centers(name, float(thresholds.get(name, 0.0)))
            for name in self.categorical_indices
        }
        self.continuous_mean = nn.Linear(latent_dim, len(self.continuous_indices))
        self.categorical_logits = nn.ModuleDict(
            {name: nn.Linear(latent_dim, len(centers)) for name, centers in self.centers.items()}
        )
        self.reset_parameters()

    def reset_parameters(self) -> None:
        nn.init.orthogonal_(self.continuous_mean.weight, gain=0.01)
        nn.init.zeros_(self.continuous_mean.bias)
        for layer in self.categorical_logits.values():
            if not isinstance(layer, nn.Linear):
                raise TypeError("categorical action head must be a linear layer")
            nn.init.orthogonal_(layer.weight, gain=0.01)
            nn.init.zeros_(layer.bias)

    def forward(self, latent: torch.Tensor) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
        logits = {name: layer(latent) for name, layer in self.categorical_logits.items()}
        return self.continuous_mean(latent), logits


class HybridBoxDistribution(SB3Distribution):
    """Factorized categorical/Gaussian distribution encoded in the env's Box schema."""

    def __init__(self, actor: HybridActorHeads, action_width: int):
        super().__init__()  # type: ignore[no-untyped-call]
        self.actor = actor
        self.action_width = int(action_width)
        self.mean: torch.Tensor | None = None
        self.normal: Normal | None = None
        self.categorical: dict[str, Categorical] = {}

    def proba_distribution_net(self, *args: Any, **kwargs: Any) -> nn.Module:
        del args, kwargs
        raise NotImplementedError("hybrid heads are built by HybridActorHeads")

    def proba_distribution(
        self,
        means: torch.Tensor,
        log_std: torch.Tensor,
        logits: dict[str, torch.Tensor],
        masks: dict[str, torch.Tensor] | None = None,
    ) -> HybridBoxDistribution:
        self.mean = means
        self.normal = _normal_distribution(means, log_std.exp().expand_as(means))
        self.categorical = {}
        for name, values in logits.items():
            if name == "thesis":
                if masks is None or name not in masks:
                    raise ValueError("thesis categorical distribution requires thesis_mask")
                mask = masks[name].to(device=values.device) > 0.0
                if mask.shape != values.shape or not bool(mask.any(dim=1).all()):
                    raise ValueError(
                        "thesis_mask must match logits and allow at least one category"
                    )
                values = values.masked_fill(~mask, torch.finfo(values.dtype).min)
            self.categorical[name] = _categorical_distribution(values)
        return self

    def _pack(self, continuous: torch.Tensor, classes: dict[str, torch.Tensor]) -> torch.Tensor:
        if self.mean is None:
            raise RuntimeError("call proba_distribution before sampling actions")
        output = self.mean.new_zeros((self.mean.shape[0], self.action_width))
        continuous_index = torch.as_tensor(
            self.actor.continuous_indices, dtype=torch.long, device=output.device
        )
        output = output.index_copy(1, continuous_index, continuous)
        for name, class_ids in classes.items():
            centers = self.actor.centers[name]
            center_tensor = output.new_tensor(centers)
            output[:, self.actor.categorical_indices[name]] = center_tensor[class_ids]
        return output

    def sample(self) -> torch.Tensor:
        if self.normal is None:
            raise RuntimeError("call proba_distribution before sampling actions")
        continuous = self.normal.rsample()
        classes = {
            name: cast(torch.Tensor, dist.sample())  # type: ignore[no-untyped-call]
            for name, dist in self.categorical.items()
        }
        return self._pack(continuous, classes)

    def mode(self) -> torch.Tensor:
        if self.normal is None:
            raise RuntimeError("call proba_distribution before choosing actions")
        classes = {name: dist.logits.argmax(dim=-1) for name, dist in self.categorical.items()}
        return self._pack(self.normal.mean, classes)

    def get_actions(self, deterministic: bool = False) -> torch.Tensor:
        return self.mode() if deterministic else self.sample()

    def log_prob(self, actions: torch.Tensor) -> torch.Tensor:
        if self.normal is None:
            raise RuntimeError("call proba_distribution before evaluating actions")
        continuous_index = torch.as_tensor(
            self.actor.continuous_indices, dtype=torch.long, device=actions.device
        )
        result = cast(
            torch.Tensor,
            self.normal.log_prob(  # type: ignore[no-untyped-call]
                actions.index_select(1, continuous_index)
            ),
        ).sum(dim=1)
        for name, dist in self.categorical.items():
            index = self.actor.categorical_indices[name]
            centers = actions.new_tensor(self.actor.centers[name])
            classes = (actions[:, index : index + 1] - centers[None, :]).abs().argmin(dim=1)
            result = result + cast(
                torch.Tensor,
                dist.log_prob(classes),  # type: ignore[no-untyped-call]
            )
        return result

    def entropy(self) -> torch.Tensor:
        if self.normal is None:
            raise RuntimeError("call proba_distribution before evaluating entropy")
        result = cast(
            torch.Tensor,
            self.normal.entropy(),  # type: ignore[no-untyped-call]
        ).sum(dim=1)
        for dist in self.categorical.values():
            result = result + cast(
                torch.Tensor,
                dist.entropy(),  # type: ignore[no-untyped-call]
            )
        return result

    def thesis_entropy(self) -> torch.Tensor:
        """Return the masked primary-thesis entropy when this is a thesis policy."""
        if "thesis" not in self.categorical:
            raise RuntimeError("distribution has no primary-thesis categorical head")
        return cast(
            torch.Tensor,
            self.categorical["thesis"].entropy(),  # type: ignore[no-untyped-call]
        )

    def actions_from_params(
        self,
        means: torch.Tensor,
        log_std: torch.Tensor,
        logits: dict[str, torch.Tensor],
        deterministic: bool = False,
    ) -> torch.Tensor:
        self.proba_distribution(means, log_std, logits)
        return self.get_actions(deterministic)

    def log_prob_from_params(
        self,
        means: torch.Tensor,
        log_std: torch.Tensor,
        logits: dict[str, torch.Tensor],
    ) -> tuple[torch.Tensor, torch.Tensor]:
        actions = self.actions_from_params(means, log_std, logits)
        return actions, self.log_prob(actions)


class HybridClampedStdMultiInputPolicy(ClampedStdMultiInputPolicy):
    """SB3 PPO policy with categorical SL/TP/exit modes and Gaussian remainder."""

    def __init__(
        self,
        *args: Any,
        hybrid_action_coordinates: Sequence[str],
        sl_mode_defer_threshold: float = 0.1,
        tp_mode_defer_threshold: float = 0.1,
        thesis_mask_key: str | None = None,
        **kwargs: Any,
    ) -> None:
        self.hybrid_action_coordinates = tuple(str(value) for value in hybrid_action_coordinates)
        self.hybrid_thresholds = {
            "sl_mode": float(sl_mode_defer_threshold),
            "tp_mode": float(tp_mode_defer_threshold),
        }
        self.thesis_mask_key = thesis_mask_key
        self._distribution_masks: dict[str, torch.Tensor] | None = None
        self.last_thesis_entropy: torch.Tensor | None = None
        super().__init__(*args, **kwargs)

    def _build(self, lr_schedule: Any) -> None:
        super()._build(lr_schedule)
        action_shape = getattr(self.action_space, "shape", None)
        if action_shape is None or len(action_shape) != 1:
            raise ValueError("hybrid PPO requires a one-dimensional Box action space")
        if len(self.hybrid_action_coordinates) != int(action_shape[0]):
            raise ValueError("hybrid coordinate count differs from action-space width")
        old_parameters = set(self.action_net.parameters()) | {self.log_std}
        actor_heads = HybridActorHeads(
            self.mlp_extractor.latent_dim_pi,
            self.hybrid_action_coordinates,
            self.hybrid_thresholds,
        )
        self.action_net = actor_heads
        continuous_count = len(actor_heads.continuous_indices)
        self.log_std = nn.Parameter(
            torch.full((continuous_count,), float(self.log_std_init), device=self.device)
        )
        for group in self.optimizer.param_groups:
            group["params"] = [
                parameter for parameter in group["params"] if parameter not in old_parameters
            ]
        self.optimizer.add_param_group(
            {"params": list(self.action_net.parameters()) + [self.log_std], "lr": lr_schedule(1)}
        )
        self.hybrid_distribution = HybridBoxDistribution(actor_heads, int(action_shape[0]))

    def _get_action_dist_from_latent(self, latent_pi: torch.Tensor) -> SB3Distribution:
        clip_policy_log_std(self, self.log_std_min, self.log_std_max)
        means, logits = self.action_net(latent_pi)
        distribution = self.hybrid_distribution.proba_distribution(
            means, self.log_std, logits, masks=self._distribution_masks
        )
        self.last_thesis_entropy = (
            distribution.thesis_entropy().detach()
            if "thesis" in self.hybrid_action_coordinates
            else None
        )
        return distribution

    def _set_distribution_mask(self, obs: Any) -> None:
        if "thesis" not in self.hybrid_action_coordinates:
            self._distribution_masks = None
            return
        if not isinstance(obs, dict) or self.thesis_mask_key not in obs:
            raise ValueError("thesis hybrid policy requires the thesis_mask observation")
        self._distribution_masks = {"thesis": obs[self.thesis_mask_key]}

    def forward(
        self, obs: Any, deterministic: bool = False
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        self._set_distribution_mask(obs)
        try:
            return super().forward(obs, deterministic=deterministic)
        finally:
            self._distribution_masks = None

    def evaluate_actions(
        self, obs: Any, actions: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor | None]:
        self._set_distribution_mask(obs)
        try:
            return super().evaluate_actions(obs, actions)
        finally:
            self._distribution_masks = None

    def get_distribution(self, obs: Any) -> SB3Distribution:
        self._set_distribution_mask(obs)
        try:
            return super().get_distribution(obs)
        finally:
            self._distribution_masks = None

    def _get_constructor_parameters(self) -> dict[str, Any]:
        data = super()._get_constructor_parameters()
        data.update(
            hybrid_action_coordinates=self.hybrid_action_coordinates,
            sl_mode_defer_threshold=self.hybrid_thresholds["sl_mode"],
            tp_mode_defer_threshold=self.hybrid_thresholds["tp_mode"],
            thesis_mask_key=self.thesis_mask_key,
        )
        return data


class ThesisConditionedActorHeads(nn.Module):
    """Market-only thesis selector with an execution actor conditioned on that thesis."""

    def __init__(
        self,
        latent_dim: int,
        coordinates: Sequence[str],
        thresholds: dict[str, float],
        embedding_dim: int = 32,
        hidden_dim: int = 128,
    ) -> None:
        super().__init__()
        self.coordinates = tuple(str(value) for value in coordinates)
        self.categorical_indices = {
            name: index
            for index, name in enumerate(self.coordinates)
            if name in _CATEGORICAL_COORDINATES
        }
        if "thesis" not in self.categorical_indices:
            raise ValueError("thesis-conditioned policy requires a thesis action coordinate")
        self.execution_categorical_indices = {
            name: index for name, index in self.categorical_indices.items() if name != "thesis"
        }
        self.continuous_indices = tuple(
            index
            for index, name in enumerate(self.coordinates)
            if name not in self.categorical_indices
        )
        if not self.continuous_indices:
            raise ValueError("thesis-conditioned policy requires continuous execution coordinates")
        self.centers = {
            name: _encoded_centers(name, float(thresholds.get(name, 0.0)))
            for name in self.categorical_indices
        }
        self.latent_dim = int(latent_dim)
        self.embedding_dim = int(embedding_dim)
        self.hidden_dim = int(hidden_dim)
        self.thesis_logits = nn.Linear(latent_dim, THESIS_CATEGORY_COUNT)
        self.thesis_embedding = nn.Embedding(THESIS_CATEGORY_COUNT, embedding_dim)
        self.execution_body = nn.Sequential(
            nn.Linear(latent_dim + embedding_dim, hidden_dim),
            nn.SiLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.SiLU(),
        )
        self.continuous_mean = nn.Linear(hidden_dim, len(self.continuous_indices))
        self.execution_categorical_logits = nn.ModuleDict(
            {
                name: nn.Linear(hidden_dim, len(self.centers[name]))
                for name in self.execution_categorical_indices
            }
        )
        self.reset_parameters()

    def reset_parameters(self) -> None:
        for output_layer in (self.thesis_logits, self.continuous_mean):
            nn.init.orthogonal_(output_layer.weight, gain=0.01)
            nn.init.zeros_(output_layer.bias)
        nn.init.normal_(self.thesis_embedding.weight, mean=0.0, std=0.02)
        for module in self.execution_body:
            if isinstance(module, nn.Linear):
                nn.init.orthogonal_(module.weight, gain=1.0)
                nn.init.zeros_(module.bias)
        for module in self.execution_categorical_logits.values():
            if not isinstance(module, nn.Linear):
                raise TypeError("execution categorical head must be a linear layer")
            nn.init.orthogonal_(module.weight, gain=0.01)
            nn.init.zeros_(module.bias)

    def thesis(self, market_latent: torch.Tensor) -> torch.Tensor:
        """Compute thesis logits from market state only."""
        return cast(torch.Tensor, self.thesis_logits(market_latent))

    def execution(
        self, market_latent: torch.Tensor, thesis_ids: torch.Tensor
    ) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
        """Compute execution parameters for the selected primary thesis."""
        context = torch.cat((market_latent, self.thesis_embedding(thesis_ids.long())), dim=-1)
        latent = self.execution_body(context)
        logits = {name: layer(latent) for name, layer in self.execution_categorical_logits.items()}
        return cast(torch.Tensor, self.continuous_mean(latent)), logits


class ThesisConditionedHybridBoxDistribution(SB3Distribution):
    """Hierarchical Box distribution: select thesis, then condition execution on it."""

    def __init__(self, actor: ThesisConditionedActorHeads, action_width: int):
        super().__init__()  # type: ignore[no-untyped-call]
        self.actor = actor
        self.action_width = int(action_width)
        self.market_latent: torch.Tensor | None = None
        self.log_std: torch.Tensor | None = None
        self.thesis: Categorical | None = None
        self.normal: Normal | None = None
        self.categorical: dict[str, Categorical] = {}
        self.mask: torch.Tensor | None = None

    def proba_distribution_net(self, *args: Any, **kwargs: Any) -> nn.Module:
        del args, kwargs
        raise NotImplementedError("hierarchical heads are built by ThesisConditionedActorHeads")

    def proba_distribution(
        self,
        market_latent: torch.Tensor,
        log_std: torch.Tensor,
        thesis_logits: torch.Tensor,
        masks: dict[str, torch.Tensor] | None = None,
    ) -> ThesisConditionedHybridBoxDistribution:
        self.market_latent = market_latent
        self.log_std = log_std
        if masks is None or "thesis" not in masks:
            raise ValueError("thesis-conditioned distribution requires thesis_mask")
        mask = masks["thesis"].to(device=thesis_logits.device) > 0.0
        if mask.shape != thesis_logits.shape or not bool(mask.any(dim=1).all()):
            raise ValueError("thesis_mask must match logits and allow at least one category")
        self.mask = mask
        self.thesis = _categorical_distribution(
            thesis_logits.masked_fill(~mask, torch.finfo(thesis_logits.dtype).min)
        )
        return self

    def _selected_distributions(
        self, thesis_ids: torch.Tensor
    ) -> tuple[Normal, dict[str, Categorical]]:
        if self.market_latent is None or self.log_std is None:
            raise RuntimeError("call proba_distribution before evaluating the policy")
        means, logits = self.actor.execution(self.market_latent, thesis_ids)
        normal = _normal_distribution(means, self.log_std.exp().expand_as(means))
        categorical = {name: _categorical_distribution(values) for name, values in logits.items()}
        return normal, categorical

    def _class_ids(self, actions: torch.Tensor) -> dict[str, torch.Tensor]:
        result: dict[str, torch.Tensor] = {}
        for name, index in self.actor.categorical_indices.items():
            centers = actions.new_tensor(self.actor.centers[name])
            result[name] = (actions[:, index : index + 1] - centers[None, :]).abs().argmin(dim=1)
        return result

    def _pack(self, continuous: torch.Tensor, classes: dict[str, torch.Tensor]) -> torch.Tensor:
        if self.market_latent is None:
            raise RuntimeError("call proba_distribution before packing actions")
        output = self.market_latent.new_zeros((self.market_latent.shape[0], self.action_width))
        continuous_index = torch.as_tensor(
            self.actor.continuous_indices, dtype=torch.long, device=output.device
        )
        output = output.index_copy(1, continuous_index, continuous)
        for name, class_ids in classes.items():
            index = self.actor.categorical_indices[name]
            output[:, index] = output.new_tensor(self.actor.centers[name])[class_ids]
        return output

    def sample(self) -> torch.Tensor:
        if self.thesis is None:
            raise RuntimeError("call proba_distribution before sampling actions")
        thesis_ids = cast(torch.Tensor, self.thesis.sample())  # type: ignore[no-untyped-call]
        normal, categorical = self._selected_distributions(thesis_ids)
        classes = {"thesis": thesis_ids}
        classes.update(
            {name: cast(torch.Tensor, dist.sample()) for name, dist in categorical.items()}  # type: ignore[no-untyped-call]
        )
        return self._pack(normal.rsample(), classes)

    def mode(self) -> torch.Tensor:
        if self.thesis is None:
            raise RuntimeError("call proba_distribution before selecting an action")
        thesis_ids = self.thesis.logits.argmax(dim=-1)
        normal, categorical = self._selected_distributions(thesis_ids)
        classes = {"thesis": thesis_ids}
        classes.update({name: dist.logits.argmax(dim=-1) for name, dist in categorical.items()})
        return self._pack(normal.mean, classes)

    def get_actions(self, deterministic: bool = False) -> torch.Tensor:
        return self.mode() if deterministic else self.sample()

    def actions_from_params(
        self,
        market_latent: torch.Tensor,
        log_std: torch.Tensor,
        thesis_logits: torch.Tensor,
        masks: dict[str, torch.Tensor] | None = None,
        deterministic: bool = False,
    ) -> torch.Tensor:
        self.proba_distribution(market_latent, log_std, thesis_logits, masks=masks)
        return self.get_actions(deterministic)

    def log_prob_from_params(
        self,
        market_latent: torch.Tensor,
        log_std: torch.Tensor,
        thesis_logits: torch.Tensor,
        masks: dict[str, torch.Tensor] | None = None,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        actions = self.actions_from_params(market_latent, log_std, thesis_logits, masks=masks)
        return actions, self.log_prob(actions)

    def log_prob(self, actions: torch.Tensor) -> torch.Tensor:
        if self.thesis is None:
            raise RuntimeError("call proba_distribution before evaluating actions")
        classes = self._class_ids(actions)
        thesis_ids = classes["thesis"]
        normal, categorical = self._selected_distributions(thesis_ids)
        continuous_index = torch.as_tensor(
            self.actor.continuous_indices, dtype=torch.long, device=actions.device
        )
        result = cast(
            torch.Tensor,
            self.thesis.log_prob(thesis_ids),  # type: ignore[no-untyped-call]
        )
        result = result + cast(
            torch.Tensor,
            normal.log_prob(actions.index_select(1, continuous_index)),  # type: ignore[no-untyped-call]
        ).sum(dim=1)
        for name, dist in categorical.items():
            result = result + cast(
                torch.Tensor,
                dist.log_prob(classes[name]),  # type: ignore[no-untyped-call]
            )
        return result

    def thesis_entropy(self) -> torch.Tensor:
        if self.thesis is None:
            raise RuntimeError("call proba_distribution before evaluating entropy")
        return cast(
            torch.Tensor,
            self.thesis.entropy(),  # type: ignore[no-untyped-call]
        )

    def entropy(self) -> torch.Tensor:
        """Exact entropy of the hierarchical policy via the chain rule."""
        if (
            self.thesis is None
            or self.market_latent is None
            or self.log_std is None
            or self.mask is None
        ):
            raise RuntimeError("call proba_distribution before evaluating entropy")
        batch = self.market_latent.shape[0]
        row_ids, thesis_ids = self.mask.nonzero(as_tuple=True)
        means, logits = self.actor.execution(self.market_latent[row_ids], thesis_ids)
        normal = _normal_distribution(means, self.log_std.exp().expand_as(means))
        conditional = cast(torch.Tensor, normal.entropy()).sum(dim=1)  # type: ignore[no-untyped-call]
        for values in logits.values():
            dist = _categorical_distribution(values)
            conditional = conditional + cast(
                torch.Tensor,
                dist.entropy(),  # type: ignore[no-untyped-call]
            )
        conditional_weight = self.thesis.probs[row_ids, thesis_ids] * conditional
        conditional_by_row = conditional_weight.new_zeros(batch).index_add(
            0, row_ids, conditional_weight
        )
        return self.thesis_entropy() + conditional_by_row


class ThesisConditionedClampedStdMultiInputPolicy(HybridClampedStdMultiInputPolicy):
    """PPO policy with a market-only thesis head and thesis-conditioned execution."""

    def __init__(
        self,
        *args: Any,
        thesis_embedding_dim: int = 32,
        thesis_execution_hidden_dim: int = 128,
        **kwargs: Any,
    ) -> None:
        self.thesis_embedding_dim = int(thesis_embedding_dim)
        self.thesis_execution_hidden_dim = int(thesis_execution_hidden_dim)
        self.conditioned_actor: ThesisConditionedActorHeads | None = None
        self.conditioned_distribution: ThesisConditionedHybridBoxDistribution | None = None
        super().__init__(*args, **kwargs)

    def _build(self, lr_schedule: Any) -> None:
        # Build the shared critic and extractor; replace the temporary legacy actor.
        super(HybridClampedStdMultiInputPolicy, self)._build(lr_schedule)
        action_shape = getattr(self.action_space, "shape", None)
        if action_shape is None or len(action_shape) != 1:
            raise ValueError("thesis-conditioned PPO requires a one-dimensional Box action space")
        if len(self.hybrid_action_coordinates) != int(action_shape[0]):
            raise ValueError("hybrid coordinate count differs from action-space width")
        old_parameters = set(self.action_net.parameters()) | {self.log_std}
        actor_heads = ThesisConditionedActorHeads(
            self.mlp_extractor.latent_dim_pi,
            self.hybrid_action_coordinates,
            self.hybrid_thresholds,
            self.thesis_embedding_dim,
            self.thesis_execution_hidden_dim,
        )
        self.action_net = actor_heads
        self.conditioned_actor = actor_heads
        self.log_std = nn.Parameter(
            torch.full(
                (len(actor_heads.continuous_indices),), float(self.log_std_init), device=self.device
            )
        )
        for group in self.optimizer.param_groups:
            group["params"] = [p for p in group["params"] if p not in old_parameters]
        self.optimizer.add_param_group(
            {"params": list(self.action_net.parameters()) + [self.log_std], "lr": lr_schedule(1)}
        )
        self.conditioned_distribution = ThesisConditionedHybridBoxDistribution(
            actor_heads, int(action_shape[0])
        )

    def _get_action_dist_from_latent(
        self, latent_pi: torch.Tensor
    ) -> ThesisConditionedHybridBoxDistribution:
        clip_policy_log_std(self, self.log_std_min, self.log_std_max)
        if self.conditioned_actor is None or self.conditioned_distribution is None:
            raise RuntimeError("thesis-conditioned policy was not built")
        thesis_logits = self.conditioned_actor.thesis(latent_pi)
        distribution = self.conditioned_distribution.proba_distribution(
            latent_pi, self.log_std, thesis_logits, masks=self._distribution_masks
        )
        self.last_thesis_entropy = distribution.thesis_entropy().detach()
        return distribution

    def _get_constructor_parameters(self) -> dict[str, Any]:
        data = super(HybridClampedStdMultiInputPolicy, self)._get_constructor_parameters()
        data.update(
            hybrid_action_coordinates=self.hybrid_action_coordinates,
            sl_mode_defer_threshold=self.hybrid_thresholds["sl_mode"],
            tp_mode_defer_threshold=self.hybrid_thresholds["tp_mode"],
            thesis_mask_key=self.thesis_mask_key,
            thesis_embedding_dim=self.thesis_embedding_dim,
            thesis_execution_hidden_dim=self.thesis_execution_hidden_dim,
        )
        return data


__all__ = [
    "HybridActorHeads",
    "HybridBoxDistribution",
    "HybridClampedStdMultiInputPolicy",
    "ThesisConditionedActorHeads",
    "ThesisConditionedHybridBoxDistribution",
    "ThesisConditionedClampedStdMultiInputPolicy",
]
