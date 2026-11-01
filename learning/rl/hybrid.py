"""Categorical modes plus Gaussian continuous coordinates for PPO Box actions."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast

import torch
from stable_baselines3.common.distributions import Distribution as SB3Distribution
from torch import nn
from torch.distributions import Categorical, Normal

from decisioning.trade_setup import TRADE_SETUP_CATEGORY_COUNT, trade_setup_center
from learning.rl.ppo import ClampedStdMultiInputPolicy, clip_policy_log_std

_SETUP_COORDINATES = {"trade_setup"}
_CATEGORICAL_COORDINATES = {*_SETUP_COORDINATES, "sl_mode", "tp_mode", "exit"}


def _normal_distribution(means: torch.Tensor, scales: torch.Tensor) -> Normal:
    """Normalize version-dependent Torch stubs at the distribution boundary.

    Args:
        means: Means used by the operation described above.
        scales: Scales used by the operation described above.

    Returns:
        Result of normalize version-dependent Torch stubs at the distribution boundary.
    """
    constructor: Any = Normal
    return cast(Normal, constructor(means, scales))


def _categorical_distribution(logits: torch.Tensor) -> Categorical:
    """Normalize version-dependent Torch stubs at the distribution boundary.

    Args:
        logits: Logits used by the operation described above.

    Returns:
        Result of normalize version-dependent Torch stubs at the distribution boundary.
    """
    constructor: Any = Categorical
    return cast(Categorical, constructor(logits=logits))


def _encoded_centers(name: str, threshold: float) -> tuple[float, ...]:
    """Return normalized raw-Box values that the existing env decoder maps exactly.

    Args:
        name: Name used to identify the requested file, artifact, or item.
        threshold: Numeric value used for the threshold.

    Returns:
        Values returned by ``_encoded_centers``, in the declared order.
    """
    if name in _SETUP_COORDINATES:
        return tuple(
            trade_setup_center(candidate_id) for candidate_id in range(TRADE_SETUP_CATEGORY_COUNT)
        )
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
        """Initialize HybridActorHeads and its owned state.

        Args:
            latent_dim: Number of dimensions in the learned latent representation.
            coordinates: Items supplied for the coordinates, in input order.
            thresholds: Key-value data used for the thresholds.
        """
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
        """Initialize continuous means and categorical logits near neutral actions."""
        nn.init.orthogonal_(self.continuous_mean.weight, gain=0.01)
        nn.init.zeros_(self.continuous_mean.bias)
        for layer in self.categorical_logits.values():
            if not isinstance(layer, nn.Linear):
                raise TypeError("categorical action head must be a linear layer")
            nn.init.orthogonal_(layer.weight, gain=0.01)
            nn.init.zeros_(layer.bias)

    def forward(self, latent: torch.Tensor) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
        """Produce continuous means and one categorical-logit tensor per mode.

        Args:
            latent: Actor features with shape ``[batch, latent_dim]``.

        Returns:
            Continuous-coordinate means and categorical logits keyed by coordinate.
        """
        logits = {name: layer(latent) for name, layer in self.categorical_logits.items()}
        return self.continuous_mean(latent), logits


class HybridBoxDistribution(SB3Distribution):
    """Factorized categorical/Gaussian distribution encoded in the env's Box schema."""

    def __init__(self, actor: HybridActorHeads, action_width: int):
        """Initialize HybridBoxDistribution and its owned state.

        Args:
            actor: Actor used by the operation described above.
            action_width: Number specifying the action width for this operation.
        """
        super().__init__()  # type: ignore[no-untyped-call]
        self.actor = actor
        self.action_width = int(action_width)
        self.mean: torch.Tensor | None = None
        self.normal: Normal | None = None
        self.categorical: dict[str, Categorical] = {}

    def proba_distribution_net(self, *args: Any, **kwargs: Any) -> nn.Module:
        """Reject SB3's generic head factory because hybrid heads are prebuilt.

        Args:
            *args: Parsed command-line arguments for this operation.
            **kwargs: Kwargs used by the operation described above.

        Returns:
            Result of reject SB3's generic head factory because hybrid heads are prebuilt.
        """
        del args, kwargs
        raise NotImplementedError("hybrid heads are built by HybridActorHeads")

    def proba_distribution(
        self,
        means: torch.Tensor,
        log_std: torch.Tensor,
        logits: dict[str, torch.Tensor],
        masks: dict[str, torch.Tensor] | None = None,
    ) -> HybridBoxDistribution:
        """Bind Gaussian and categorical distributions for a policy batch.

        Args:
            means: Gaussian means for continuous action coordinates.
            log_std: Log standard deviations shared across the batch.
            logits: Categorical logits keyed by semantic action coordinate.
            masks: Optional eligible-category masks; setup logits require one.

        Returns:
            This initialized distribution for chained sampling and evaluation.
        """
        self.mean = means
        self.normal = _normal_distribution(means, log_std.exp().expand_as(means))
        self.categorical = {}
        for name, values in logits.items():
            if name in _SETUP_COORDINATES:
                if masks is None or name not in masks:
                    raise ValueError(
                        f"{name} categorical distribution requires its eligibility mask"
                    )
                mask = masks[name].to(device=values.device) > 0.0
                if mask.shape != values.shape or not bool(mask.any(dim=1).all()):
                    raise ValueError(
                        f"{name} eligibility mask must match logits and allow a category"
                    )
                values = values.masked_fill(~mask, torch.finfo(values.dtype).min)
            self.categorical[name] = _categorical_distribution(values)
        return self

    def _pack(self, continuous: torch.Tensor, classes: dict[str, torch.Tensor]) -> torch.Tensor:
        """Process HybridBoxDistribution.

        Args:
            continuous: Continuous used by the operation described above.
            classes: Key-value data used for the classes.

        Returns:
            Result of process HybridBoxDistribution.
        """
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
        """Sample continuous and categorical components and pack Box coordinates.

        Returns:
            Result of sample continuous and categorical components and pack Box coordinates.
        """
        if self.normal is None:
            raise RuntimeError("call proba_distribution before sampling actions")
        continuous = self.normal.rsample()
        classes = {
            name: cast(torch.Tensor, dist.sample())  # type: ignore[no-untyped-call]
            for name, dist in self.categorical.items()
        }
        return self._pack(continuous, classes)

    def mode(self) -> torch.Tensor:
        """Pack Gaussian means and categorical argmax values as a Box action.

        Returns:
            Result of pack Gaussian means and categorical argmax values as a Box action.
        """
        if self.normal is None:
            raise RuntimeError("call proba_distribution before choosing actions")
        classes = {name: dist.logits.argmax(dim=-1) for name, dist in self.categorical.items()}
        return self._pack(self.normal.mean, classes)

    def get_actions(self, deterministic: bool = False) -> torch.Tensor:
        """Choose the mode or draw a stochastic action from the bound distribution.

        Args:
            deterministic: Whether to enable or require the deterministic.

        Returns:
            Result of choose the mode or draw a stochastic action from the bound distribution.
        """
        return self.mode() if deterministic else self.sample()

    def log_prob(self, actions: torch.Tensor) -> torch.Tensor:
        """Sum component log probabilities for actions in environment Box encoding.

        Args:
            actions: Batched encoded actions with shape ``[batch, action_width]``.

        Returns:
            One joint log probability per batch row.
        """
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
        """Sum Gaussian and categorical entropies for each batch row.

        Returns:
            Result of sum Gaussian and categorical entropies for each batch row.
        """
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

    def trade_setup_entropy(self) -> torch.Tensor:
        """Return the masked categorical entropy for the setup coordinate.

        Returns:
            Result of return the masked categorical entropy for the setup coordinate.
        """
        setup_name = next((name for name in _SETUP_COORDINATES if name in self.categorical), None)
        if setup_name is None:
            raise RuntimeError("distribution has no trade-setup categorical head")
        return cast(
            torch.Tensor,
            self.categorical[setup_name].entropy(),  # type: ignore[no-untyped-call]
        )

    def actions_from_params(
        self,
        means: torch.Tensor,
        log_std: torch.Tensor,
        logits: dict[str, torch.Tensor],
        deterministic: bool = False,
    ) -> torch.Tensor:
        """Initialize component distributions and choose an encoded action.

        Args:
            means: Gaussian means for continuous coordinates.
            log_std: Log standard deviations shared across the batch.
            logits: Categorical logits keyed by semantic action coordinate.
            deterministic: Select modes instead of sampling when true.

        Returns:
            Actions encoded in the environment's Box coordinate order.
        """
        self.proba_distribution(means, log_std, logits)
        return self.get_actions(deterministic)

    def log_prob_from_params(
        self,
        means: torch.Tensor,
        log_std: torch.Tensor,
        logits: dict[str, torch.Tensor],
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Return a sampled action and its joint log probability.

        Args:
            means: Means used by the operation described above.
            log_std: Log std used by the operation described above.
            logits: Key-value data used for the logits.

        Returns:
            Values returned by ``log_prob_from_params``, in the declared order.
        """
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
        trade_setup_mask_key: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize HybridClampedStdMultiInputPolicy and its owned state.

        Args:
            *args: Parsed command-line arguments for this operation.
            hybrid_action_coordinates: Items supplied for the hybrid action coordinates, in input order.
            sl_mode_defer_threshold: Numeric value used for the sl mode defer threshold.
            tp_mode_defer_threshold: Numeric value used for the tp mode defer threshold.
            trade_setup_mask_key: Trade setup mask key used by the operation described above.
            **kwargs: Kwargs used by the operation described above.
        """
        self.hybrid_action_coordinates = tuple(str(value) for value in hybrid_action_coordinates)
        self.setup_coordinate = next(
            (name for name in ("trade_setup",) if name in self.hybrid_action_coordinates),
            None,
        )
        self.hybrid_thresholds = {
            "sl_mode": float(sl_mode_defer_threshold),
            "tp_mode": float(tp_mode_defer_threshold),
        }
        self.trade_setup_mask_key = trade_setup_mask_key or "trade_setup_mask"
        self._distribution_masks: dict[str, torch.Tensor] | None = None
        self.last_trade_setup_entropy: torch.Tensor | None = None
        super().__init__(*args, **kwargs)

    def _build(self, lr_schedule: Any) -> None:
        """Build HybridClampedStdMultiInputPolicy.

        Args:
            lr_schedule: Lr schedule used by the operation described above.
        """
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
        """Return action dist from latent.

        Args:
            latent_pi: Latent pi used by the operation described above.

        Returns:
            Result of return action dist from latent.
        """
        clip_policy_log_std(self, self.log_std_min, self.log_std_max)
        means, logits = self.action_net(latent_pi)
        distribution = self.hybrid_distribution.proba_distribution(
            means, self.log_std, logits, masks=self._distribution_masks
        )
        self.last_trade_setup_entropy = (
            distribution.trade_setup_entropy().detach()
            if self.setup_coordinate is not None
            else None
        )
        return distribution

    def _set_distribution_mask(self, obs: Any) -> None:
        """Set distribution mask.

        Args:
            obs: Obs used by the operation described above.
        """
        if self.setup_coordinate is None:
            self._distribution_masks = None
            return
        if not isinstance(obs, dict) or self.trade_setup_mask_key not in obs:
            raise ValueError("setup hybrid policy requires its configured eligibility mask")
        self._distribution_masks = {self.setup_coordinate: obs[self.trade_setup_mask_key]}

    def forward(
        self, obs: Any, deterministic: bool = False
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Run the PPO policy with the observation's setup eligibility mask.

        Args:
            obs: Obs used by the operation described above.
            deterministic: Whether to enable or require the deterministic.

        Returns:
            Values returned by ``forward``, in the declared order.
        """
        self._set_distribution_mask(obs)
        try:
            return super().forward(obs, deterministic=deterministic)
        finally:
            self._distribution_masks = None

    def evaluate_actions(
        self, obs: Any, actions: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor | None]:
        """Evaluate actions while applying and then clearing the setup mask.

        Args:
            obs: Obs used by the operation described above.
            actions: Actions to apply, in input order.

        Returns:
            Values returned by ``evaluate_actions``, in the declared order.
        """
        self._set_distribution_mask(obs)
        try:
            return super().evaluate_actions(obs, actions)
        finally:
            self._distribution_masks = None

    def get_distribution(self, obs: Any) -> SB3Distribution:
        """Build the policy distribution with the observation's setup mask.

        Args:
            obs: Obs used by the operation described above.

        Returns:
            Result of build the policy distribution with the observation's setup mask.
        """
        self._set_distribution_mask(obs)
        try:
            return super().get_distribution(obs)
        finally:
            self._distribution_masks = None

    def _get_constructor_parameters(self) -> dict[str, Any]:
        """Return constructor parameters.

        Returns:
            Mapping from ``str`` keys to ``Any`` values.
        """
        data = super()._get_constructor_parameters()
        data.update(
            hybrid_action_coordinates=self.hybrid_action_coordinates,
            sl_mode_defer_threshold=self.hybrid_thresholds["sl_mode"],
            tp_mode_defer_threshold=self.hybrid_thresholds["tp_mode"],
        )
        if self.setup_coordinate == "trade_setup":
            data["trade_setup_mask_key"] = self.trade_setup_mask_key
        return data


class TradeSetupConditionedActorHeads(nn.Module):
    """Market-only trade_setup selector with an execution actor conditioned on that trade_setup."""

    def __init__(
        self,
        latent_dim: int,
        coordinates: Sequence[str],
        thresholds: dict[str, float],
        embedding_dim: int = 32,
        hidden_dim: int = 128,
    ) -> None:
        """Initialize TradeSetupConditionedActorHeads and its owned state.

        Args:
            latent_dim: Number of dimensions in the learned latent representation.
            coordinates: Items supplied for the coordinates, in input order.
            thresholds: Key-value data used for the thresholds.
            embedding_dim: Numeric value used for the embedding dim.
            hidden_dim: Numeric value used for the hidden dim.
        """
        super().__init__()
        self.coordinates = tuple(str(value) for value in coordinates)
        self.categorical_indices = {
            name: index
            for index, name in enumerate(self.coordinates)
            if name in _CATEGORICAL_COORDINATES
        }
        setup_coordinate = "trade_setup" if "trade_setup" in self.categorical_indices else None
        if setup_coordinate is None:
            raise ValueError("setup-conditioned policy requires a setup action coordinate")
        self.setup_coordinate: str = setup_coordinate
        self.execution_categorical_indices = {
            name: index
            for name, index in self.categorical_indices.items()
            if name != self.setup_coordinate
        }
        self.continuous_indices = tuple(
            index
            for index, name in enumerate(self.coordinates)
            if name not in self.categorical_indices
        )
        if not self.continuous_indices:
            raise ValueError(
                "trade_setup-conditioned policy requires continuous execution coordinates"
            )
        self.centers = {
            name: _encoded_centers(name, float(thresholds.get(name, 0.0)))
            for name in self.categorical_indices
        }
        self.latent_dim = int(latent_dim)
        self.embedding_dim = int(embedding_dim)
        self.hidden_dim = int(hidden_dim)
        self.trade_setup_logits = nn.Linear(latent_dim, TRADE_SETUP_CATEGORY_COUNT)
        self.trade_setup_embedding = nn.Embedding(TRADE_SETUP_CATEGORY_COUNT, embedding_dim)
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
        """Initialize setup, embedding, and conditioned execution layers."""
        for output_layer in (self.trade_setup_logits, self.continuous_mean):
            nn.init.orthogonal_(output_layer.weight, gain=0.01)
            nn.init.zeros_(output_layer.bias)
        nn.init.normal_(self.trade_setup_embedding.weight, mean=0.0, std=0.02)
        for module in self.execution_body:
            if isinstance(module, nn.Linear):
                nn.init.orthogonal_(module.weight, gain=1.0)
                nn.init.zeros_(module.bias)
        for module in self.execution_categorical_logits.values():
            if not isinstance(module, nn.Linear):
                raise TypeError("execution categorical head must be a linear layer")
            nn.init.orthogonal_(module.weight, gain=0.01)
            nn.init.zeros_(module.bias)

    def trade_setup(self, market_latent: torch.Tensor) -> torch.Tensor:
        """Compute primary setup logits from market state only.

        Args:
            market_latent: Market latent used by the operation described above.

        Returns:
            Result of compute primary setup logits from market state only.
        """
        return cast(torch.Tensor, self.trade_setup_logits(market_latent))

    def execution(
        self, market_latent: torch.Tensor, trade_setup_ids: torch.Tensor
    ) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
        """Compute execution parameters for the selected primary trade_setup.

        Args:
            market_latent: Market latent used by the operation described above.
            trade_setup_ids: Trade setup ids used by the operation described above.

        Returns:
            Mapping from ``str`` keys to ``torch.Tensor]`` values.
        """
        context = torch.cat(
            (market_latent, self.trade_setup_embedding(trade_setup_ids.long())), dim=-1
        )
        latent = self.execution_body(context)
        logits = {name: layer(latent) for name, layer in self.execution_categorical_logits.items()}
        return cast(torch.Tensor, self.continuous_mean(latent)), logits


class TradeSetupConditionedHybridBoxDistribution(SB3Distribution):
    """Hierarchical Box distribution: select trade_setup, then condition execution on it."""

    def __init__(self, actor: TradeSetupConditionedActorHeads, action_width: int):
        """Initialize TradeSetupConditionedHybridBoxDistribution and its owned state.

        Args:
            actor: Actor used by the operation described above.
            action_width: Number specifying the action width for this operation.
        """
        super().__init__()  # type: ignore[no-untyped-call]
        self.actor = actor
        self.setup_coordinate = actor.setup_coordinate
        self.action_width = int(action_width)
        self.market_latent: torch.Tensor | None = None
        self.log_std: torch.Tensor | None = None
        self.trade_setup: Categorical | None = None
        self.normal: Normal | None = None
        self.categorical: dict[str, Categorical] = {}
        self.mask: torch.Tensor | None = None

    def proba_distribution_net(self, *args: Any, **kwargs: Any) -> nn.Module:
        """Reject SB3's generic head factory because hierarchical heads are prebuilt.

        Args:
            *args: Parsed command-line arguments for this operation.
            **kwargs: Kwargs used by the operation described above.

        Returns:
            Result of reject SB3's generic head factory because hierarchical heads are prebuilt.
        """
        del args, kwargs
        raise NotImplementedError("hierarchical heads are built by TradeSetupConditionedActorHeads")

    def proba_distribution(
        self,
        market_latent: torch.Tensor,
        log_std: torch.Tensor,
        trade_setup_logits: torch.Tensor,
        masks: dict[str, torch.Tensor] | None = None,
    ) -> TradeSetupConditionedHybridBoxDistribution:
        """Bind masked setup logits and retain market features for execution.

        Args:
            market_latent: Actor features used by setup and execution heads.
            log_std: Log standard deviation for continuous execution coordinates.
            trade_setup_logits: Unmasked logits for the primary setup choice.
            masks: Eligibility mask keyed by the setup coordinate.

        Returns:
            This initialized hierarchical distribution.
        """
        self.market_latent = market_latent
        self.log_std = log_std
        if masks is None or self.setup_coordinate not in masks:
            raise ValueError("setup-conditioned distribution requires its eligibility mask")
        mask = masks[self.setup_coordinate].to(device=trade_setup_logits.device) > 0.0
        if mask.shape != trade_setup_logits.shape or not bool(mask.any(dim=1).all()):
            raise ValueError("setup eligibility mask must match logits and allow a category")
        self.mask = mask
        self.trade_setup = _categorical_distribution(
            trade_setup_logits.masked_fill(~mask, torch.finfo(trade_setup_logits.dtype).min)
        )
        return self

    def _selected_distributions(
        self, trade_setup_ids: torch.Tensor
    ) -> tuple[Normal, dict[str, Categorical]]:
        """Process distributions.

        Args:
            trade_setup_ids: Trade setup ids used by the operation described above.

        Returns:
            Mapping from ``str`` keys to ``Categorical]`` values.
        """
        if self.market_latent is None or self.log_std is None:
            raise RuntimeError("call proba_distribution before evaluating the policy")
        means, logits = self.actor.execution(self.market_latent, trade_setup_ids)
        normal = _normal_distribution(means, self.log_std.exp().expand_as(means))
        categorical = {name: _categorical_distribution(values) for name, values in logits.items()}
        return normal, categorical

    def _class_ids(self, actions: torch.Tensor) -> dict[str, torch.Tensor]:
        """Process ids.

        Args:
            actions: Actions to apply, in input order.

        Returns:
            Mapping from ``str`` keys to ``torch.Tensor`` values.
        """
        result: dict[str, torch.Tensor] = {}
        for name, index in self.actor.categorical_indices.items():
            centers = actions.new_tensor(self.actor.centers[name])
            result[name] = (actions[:, index : index + 1] - centers[None, :]).abs().argmin(dim=1)
        return result

    def _pack(self, continuous: torch.Tensor, classes: dict[str, torch.Tensor]) -> torch.Tensor:
        """Process TradeSetupConditionedHybridBoxDistribution.

        Args:
            continuous: Continuous used by the operation described above.
            classes: Key-value data used for the classes.

        Returns:
            Result of process TradeSetupConditionedHybridBoxDistribution.
        """
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
        """Sample a primary setup, then sample execution conditional on that setup.

        Returns:
            Result of sample a primary setup, then sample execution conditional on that setup.
        """
        if self.trade_setup is None:
            raise RuntimeError("call proba_distribution before sampling actions")
        trade_setup_ids = cast(torch.Tensor, self.trade_setup.sample())  # type: ignore[no-untyped-call]
        normal, categorical = self._selected_distributions(trade_setup_ids)
        classes = {self.setup_coordinate: trade_setup_ids}
        classes.update(
            {name: cast(torch.Tensor, dist.sample()) for name, dist in categorical.items()}  # type: ignore[no-untyped-call]
        )
        return self._pack(normal.rsample(), classes)

    def mode(self) -> torch.Tensor:
        """Choose the most likely setup and conditional execution modes.

        Returns:
            Result of choose the most likely setup and conditional execution modes.
        """
        if self.trade_setup is None:
            raise RuntimeError("call proba_distribution before selecting an action")
        trade_setup_ids = self.trade_setup.logits.argmax(dim=-1)
        normal, categorical = self._selected_distributions(trade_setup_ids)
        classes = {self.setup_coordinate: trade_setup_ids}
        classes.update({name: dist.logits.argmax(dim=-1) for name, dist in categorical.items()})
        return self._pack(normal.mean, classes)

    def get_actions(self, deterministic: bool = False) -> torch.Tensor:
        """Choose the hierarchical mode or draw a stochastic Box action.

        Args:
            deterministic: Whether to enable or require the deterministic.

        Returns:
            Result of choose the hierarchical mode or draw a stochastic Box action.
        """
        return self.mode() if deterministic else self.sample()

    def actions_from_params(
        self,
        market_latent: torch.Tensor,
        log_std: torch.Tensor,
        trade_setup_logits: torch.Tensor,
        masks: dict[str, torch.Tensor] | None = None,
        deterministic: bool = False,
    ) -> torch.Tensor:
        """Bind hierarchical parameters and sample or select an encoded action.

        Args:
            market_latent: Market latent used by the operation described above.
            log_std: Log std used by the operation described above.
            trade_setup_logits: Trade setup logits used by the operation described above.
            masks: Key-value data used for the masks.
            deterministic: Whether to enable or require the deterministic.

        Returns:
            Result of bind hierarchical parameters and sample or select an encoded action.
        """
        self.proba_distribution(market_latent, log_std, trade_setup_logits, masks=masks)
        return self.get_actions(deterministic)

    def log_prob_from_params(
        self,
        market_latent: torch.Tensor,
        log_std: torch.Tensor,
        trade_setup_logits: torch.Tensor,
        masks: dict[str, torch.Tensor] | None = None,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Return a sampled hierarchical action and its joint log probability.

        Args:
            market_latent: Market latent used by the operation described above.
            log_std: Log std used by the operation described above.
            trade_setup_logits: Trade setup logits used by the operation described above.
            masks: Key-value data used for the masks.

        Returns:
            Values returned by ``log_prob_from_params``, in the declared order.
        """
        actions = self.actions_from_params(market_latent, log_std, trade_setup_logits, masks=masks)
        return actions, self.log_prob(actions)

    def log_prob(self, actions: torch.Tensor) -> torch.Tensor:
        """Evaluate setup and conditional execution log probabilities.

        Args:
            actions: Batched Box-encoded actions in configured coordinate order.

        Returns:
            One joint hierarchical log probability per batch row.
        """
        if self.trade_setup is None:
            raise RuntimeError("call proba_distribution before evaluating actions")
        classes = self._class_ids(actions)
        trade_setup_ids = classes[self.setup_coordinate]
        normal, categorical = self._selected_distributions(trade_setup_ids)
        continuous_index = torch.as_tensor(
            self.actor.continuous_indices, dtype=torch.long, device=actions.device
        )
        result = cast(
            torch.Tensor,
            self.trade_setup.log_prob(trade_setup_ids),  # type: ignore[no-untyped-call]
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

    def trade_setup_entropy(self) -> torch.Tensor:
        """Return entropy of the masked primary setup distribution.

        Returns:
            Result of return entropy of the masked primary setup distribution.
        """
        if self.trade_setup is None:
            raise RuntimeError("call proba_distribution before evaluating entropy")
        return cast(
            torch.Tensor,
            self.trade_setup.entropy(),  # type: ignore[no-untyped-call]
        )

    def entropy(self) -> torch.Tensor:
        """Exact entropy of the hierarchical policy via the chain rule.

        Returns:
            Result of exact entropy of the hierarchical policy via the chain rule.
        """
        if (
            self.trade_setup is None
            or self.market_latent is None
            or self.log_std is None
            or self.mask is None
        ):
            raise RuntimeError("call proba_distribution before evaluating entropy")
        batch = self.market_latent.shape[0]
        row_ids, trade_setup_ids = self.mask.nonzero(as_tuple=True)
        means, logits = self.actor.execution(self.market_latent[row_ids], trade_setup_ids)
        normal = _normal_distribution(means, self.log_std.exp().expand_as(means))
        conditional = cast(torch.Tensor, normal.entropy()).sum(dim=1)  # type: ignore[no-untyped-call]
        for values in logits.values():
            dist = _categorical_distribution(values)
            conditional = conditional + cast(
                torch.Tensor,
                dist.entropy(),  # type: ignore[no-untyped-call]
            )
        conditional_weight = self.trade_setup.probs[row_ids, trade_setup_ids] * conditional
        conditional_by_row = conditional_weight.new_zeros(batch).index_add(
            0, row_ids, conditional_weight
        )
        return self.trade_setup_entropy() + conditional_by_row


class TradeSetupConditionedClampedStdMultiInputPolicy(HybridClampedStdMultiInputPolicy):
    """PPO policy with a market-only trade_setup head and trade_setup-conditioned execution."""

    def __init__(
        self,
        *args: Any,
        trade_setup_embedding_dim: int = 32,
        trade_setup_execution_hidden_dim: int = 128,
        **kwargs: Any,
    ) -> None:
        """Initialize TradeSetupConditionedClampedStdMultiInputPolicy and its owned state.

        Args:
            *args: Parsed command-line arguments for this operation.
            trade_setup_embedding_dim: Numeric value used for the trade setup embedding dim.
            trade_setup_execution_hidden_dim: Numeric value used for the trade setup execution hidden dim.
            **kwargs: Kwargs used by the operation described above.
        """
        self.trade_setup_embedding_dim = int(trade_setup_embedding_dim)
        self.trade_setup_execution_hidden_dim = int(trade_setup_execution_hidden_dim)
        self.conditioned_actor: TradeSetupConditionedActorHeads | None = None
        self.conditioned_distribution: TradeSetupConditionedHybridBoxDistribution | None = None
        super().__init__(*args, **kwargs)

    def _build(self, lr_schedule: Any) -> None:
        # Build the shared critic and extractor, then install the conditioned actor.
        """Build TradeSetupConditionedClampedStdMultiInputPolicy.

        Args:
            lr_schedule: Lr schedule used by the operation described above.
        """
        super(HybridClampedStdMultiInputPolicy, self)._build(lr_schedule)
        action_shape = getattr(self.action_space, "shape", None)
        if action_shape is None or len(action_shape) != 1:
            raise ValueError(
                "trade_setup-conditioned PPO requires a one-dimensional Box action space"
            )
        if len(self.hybrid_action_coordinates) != int(action_shape[0]):
            raise ValueError("hybrid coordinate count differs from action-space width")
        old_parameters = set(self.action_net.parameters()) | {self.log_std}
        actor_heads = TradeSetupConditionedActorHeads(
            self.mlp_extractor.latent_dim_pi,
            self.hybrid_action_coordinates,
            self.hybrid_thresholds,
            self.trade_setup_embedding_dim,
            self.trade_setup_execution_hidden_dim,
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
        self.conditioned_distribution = TradeSetupConditionedHybridBoxDistribution(
            actor_heads, int(action_shape[0])
        )

    def _get_action_dist_from_latent(
        self, latent_pi: torch.Tensor
    ) -> TradeSetupConditionedHybridBoxDistribution:
        """Return action dist from latent.

        Args:
            latent_pi: Latent pi used by the operation described above.

        Returns:
            Result of return action dist from latent.
        """
        clip_policy_log_std(self, self.log_std_min, self.log_std_max)
        if self.conditioned_actor is None or self.conditioned_distribution is None:
            raise RuntimeError("trade_setup-conditioned policy was not built")
        trade_setup_logits = self.conditioned_actor.trade_setup(latent_pi)
        distribution = self.conditioned_distribution.proba_distribution(
            latent_pi, self.log_std, trade_setup_logits, masks=self._distribution_masks
        )
        self.last_trade_setup_entropy = distribution.trade_setup_entropy().detach()
        return distribution

    def _get_constructor_parameters(self) -> dict[str, Any]:
        """Return constructor parameters.

        Returns:
            Mapping from ``str`` keys to ``Any`` values.
        """
        data = super(HybridClampedStdMultiInputPolicy, self)._get_constructor_parameters()
        data.update(
            hybrid_action_coordinates=self.hybrid_action_coordinates,
            sl_mode_defer_threshold=self.hybrid_thresholds["sl_mode"],
            tp_mode_defer_threshold=self.hybrid_thresholds["tp_mode"],
        )
        data.update(
            trade_setup_mask_key=self.trade_setup_mask_key,
            trade_setup_embedding_dim=self.trade_setup_embedding_dim,
            trade_setup_execution_hidden_dim=self.trade_setup_execution_hidden_dim,
        )
        return data


__all__ = [
    "HybridActorHeads",
    "HybridBoxDistribution",
    "HybridClampedStdMultiInputPolicy",
    "TradeSetupConditionedActorHeads",
    "TradeSetupConditionedHybridBoxDistribution",
    "TradeSetupConditionedClampedStdMultiInputPolicy",
]


# Checkpoint state dictionaries use the stable ``trade_setup_*`` parameter names.
