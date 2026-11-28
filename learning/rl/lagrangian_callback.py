"""Lagrangian risk-cost dual update callback for SB3 PPO."""

from __future__ import annotations

import logging
from typing import Any, cast

import numpy as np

try:
    from stable_baselines3.common.callbacks import BaseCallback as _Base
except ImportError:
    _Base = object  # type: ignore[assignment,misc]
    _SB3_AVAILABLE = False
else:
    _SB3_AVAILABLE = True

log = logging.getLogger("learning.rl.callbacks")

if _SB3_AVAILABLE:

    class LagrangianRiskCallback(_Base):
        """Primal-dual PPO shaping for annual account-survival risk.

        The environment's hard account guardrails remain unchanged. This
        callback adds the largest per-step increase among daily, maximum-loss,
        and enabled trailing costs, normalized to the maximum-loss limit. Its
        default cost discount is 1 so late-year costs retain their weight. The
        budget is a fraction of the maximum-loss limit per full-split episode.
        This is a learning objective, not a risk guarantee.
        """

        _STATE_VERSION = 3

        def __init__(
            self,
            *,
            episode_cost_budget: float = 1.0,
            dual_learning_rate: float = 0.1,
            lambda_initial: float = 0.0,
            lambda_max: float = 100.0,
            gamma: float = 0.99,
            cost_discount_gamma: float | None = None,
            daily_loss_limit_usd: float = 5_000.0,
            max_loss_limit_usd: float = 10_000.0,
            trailing_dd_limit_usd: float = 0.0,
            verbose: int = 0,
        ) -> None:
            """Initialize LagrangianRiskCallback and its owned state.

            Args:
                episode_cost_budget: Numeric value used for the episode cost budget.
                dual_learning_rate: Numeric value used for the dual learning rate.
                lambda_initial: Numeric value used for the lambda initial.
                lambda_max: Numeric value used for the lambda max.
                gamma: Numeric value used for the gamma.
                cost_discount_gamma: Cost discount gamma used by the operation described above.
                daily_loss_limit_usd: Numeric value used for the daily loss limit usd.
                max_loss_limit_usd: Numeric value used for the max loss limit usd.
                trailing_dd_limit_usd: Numeric value used for the trailing dd limit usd.
                verbose: Numeric value used for the verbose.
            """
            super().__init__(verbose=verbose)
            cost_gamma = gamma if cost_discount_gamma is None else cost_discount_gamma
            configured_values = np.asarray(
                [
                    episode_cost_budget,
                    dual_learning_rate,
                    lambda_initial,
                    lambda_max,
                    gamma,
                    cost_gamma,
                    daily_loss_limit_usd,
                    max_loss_limit_usd,
                    trailing_dd_limit_usd,
                ],
                dtype=np.float64,
            )
            if not np.isfinite(configured_values).all():
                raise ValueError("Lagrangian PPO settings must all be finite")
            if episode_cost_budget < 0.0:
                raise ValueError("episode_cost_budget must be nonnegative")
            if dual_learning_rate <= 0.0:
                raise ValueError("dual_learning_rate must be positive")
            if not 0.0 < gamma <= 1.0 or not 0.0 < cost_gamma <= 1.0:
                raise ValueError("PPO gamma and cost_discount_gamma must be in (0, 1]")
            if daily_loss_limit_usd < 0.0 or max_loss_limit_usd <= 0.0:
                raise ValueError("Q5 loss limits must be nonnegative and max loss positive")
            if trailing_dd_limit_usd < 0.0:
                raise ValueError("Q5 trailing limit must be nonnegative")
            if lambda_initial < 0.0 or lambda_max <= 0.0 or lambda_initial > lambda_max:
                raise ValueError("Lagrange multiplier bounds are invalid")
            self.episode_cost_budget = float(episode_cost_budget)
            self.dual_learning_rate = float(dual_learning_rate)
            self.lambda_initial = float(lambda_initial)
            self.lambda_max = float(lambda_max)
            self.gamma = float(gamma)
            self.cost_discount_gamma = float(cost_gamma)
            self.daily_loss_limit_usd = float(daily_loss_limit_usd)
            self.max_loss_limit_usd = float(max_loss_limit_usd)
            self.trailing_dd_limit_usd = float(trailing_dd_limit_usd)
            self.lagrange_multiplier = self.lambda_initial
            self._episode_costs: np.ndarray[Any, Any] = np.zeros(0, dtype=np.float64)
            self._episode_cost_discounts: np.ndarray[Any, Any] = np.ones(0, dtype=np.float64)
            self._completed_costs: list[float] = []
            self._rollout_environment_reward = 0.0
            self._rollout_penalty = 0.0
            self._rollout_transitions = 0
            self._dual_updates = 0

        def _config_state(self) -> dict[str, float | int]:
            """Process state.

            Returns:
                Mapping from ``str`` keys to ``float | int`` values.
            """
            return {
                "version": self._STATE_VERSION,
                "episode_cost_budget": self.episode_cost_budget,
                "dual_learning_rate": self.dual_learning_rate,
                "lambda_initial": self.lambda_initial,
                "lambda_max": self.lambda_max,
                "gamma": self.gamma,
                "cost_discount_gamma": self.cost_discount_gamma,
                "daily_loss_limit_usd": self.daily_loss_limit_usd,
                "max_loss_limit_usd": self.max_loss_limit_usd,
                "trailing_dd_limit_usd": self.trailing_dd_limit_usd,
            }

        def _persist_state(self) -> None:
            """Process state."""
            cast(Any, self.model)._constrained_rl_state = {
                **self._config_state(),
                "lagrange_multiplier": self.lagrange_multiplier,
                "dual_updates": self._dual_updates,
            }

        def _on_training_start(self) -> None:
            """Process training start."""
            state = getattr(self.model, "_constrained_rl_state", None)
            if state is not None:
                expected = self._config_state()
                for key, value in expected.items():
                    if state.get(key) != value:
                        raise ValueError(
                            f"checkpoint constrained-RL setting {key!r} differs from config"
                        )
                self.lagrange_multiplier = float(state["lagrange_multiplier"])
                self._dual_updates = int(state.get("dual_updates", 0))
                if not 0.0 <= self.lagrange_multiplier <= self.lambda_max:
                    raise ValueError("checkpoint Lagrange multiplier is outside configured bounds")
            self._episode_costs = np.zeros(int(self.model.n_envs), dtype=np.float64)
            self._episode_cost_discounts = np.ones(int(self.model.n_envs), dtype=np.float64)
            self._persist_state()

        def _episode_cost(self, info: Any) -> float:
            """Process cost.

            Args:
                info: Info used by the operation described above.

            Returns:
                Numeric result returned by ``_episode_cost``.
            """
            if not isinstance(info, dict):
                return 0.0
            constraints = info.get("constraints", {})
            if not isinstance(constraints, dict):
                return 0.0
            daily_cost = max(0.0, float(constraints.get("daily_cost", 0.0)))
            max_loss_cost = max(0.0, float(constraints.get("max_loss_cost", 0.0)))
            trailing_cost = max(0.0, float(constraints.get("trailing_cost", 0.0)))
            # All episode costs use units of the configured maximum-loss limit.
            # Thus 0.10 means cumulative limit-equivalent risk increments of
            # $1,000 when the hard maximum-loss limit is $10,000.
            costs = [
                daily_cost * self.daily_loss_limit_usd / self.max_loss_limit_usd,
                max_loss_cost,
            ]
            if self.trailing_dd_limit_usd > 0.0:
                costs.append(trailing_cost * self.trailing_dd_limit_usd / self.max_loss_limit_usd)
            breached = any(
                bool(constraints.get(key, False))
                for key in ("daily_breach", "max_loss_breach", "trailing_breach")
            )
            return max([*costs, float(breached)], default=0.0)

        def _on_step(self) -> bool:
            """Process step.

            Returns:
                Whether on step meets the requested condition.
            """
            rewards = self.locals.get("rewards")
            dones = self.locals.get("dones")
            infos = self.locals.get("infos")
            if not isinstance(rewards, np.ndarray) or dones is None or infos is None:
                raise RuntimeError("Lagrangian PPO callback did not receive VecEnv step data")
            if len(rewards) != len(self._episode_costs) or len(infos) != len(rewards):
                raise RuntimeError("Lagrangian PPO callback environment batch size changed")

            self._rollout_environment_reward += float(np.sum(rewards))
            costs = np.asarray([self._episode_cost(info) for info in infos], dtype=np.float64)
            penalties = self.lagrange_multiplier * costs
            rewards -= penalties.astype(rewards.dtype, copy=False)
            self._rollout_penalty += float(np.sum(penalties))
            self._rollout_transitions += int(len(rewards))

            done_values = np.asarray(dones, dtype=bool)
            self._episode_costs += self._episode_cost_discounts * costs
            self._episode_cost_discounts *= self.cost_discount_gamma
            for index, done in enumerate(done_values):
                if done:
                    self._completed_costs.append(float(self._episode_costs[index]))
                    self._episode_costs[index] = 0.0
                    self._episode_cost_discounts[index] = 1.0
            return True

        def _on_rollout_end(self) -> None:
            """Process rollout end."""
            model: Any = self.model
            steps = max(1, self._rollout_transitions)
            model.logger.record(
                "constrained_rl/environment_reward_mean",
                self._rollout_environment_reward / steps,
            )
            model.logger.record("constrained_rl/penalty_sum", self._rollout_penalty)
            model.logger.record("constrained_rl/lambda", self.lagrange_multiplier)
            model.logger.record("constrained_rl/completed_episodes", len(self._completed_costs))
            if self._completed_costs:
                observed_cost = float(np.mean(self._completed_costs))
                self.lagrange_multiplier = float(
                    np.clip(
                        self.lagrange_multiplier
                        + self.dual_learning_rate * (observed_cost - self.episode_cost_budget),
                        0.0,
                        self.lambda_max,
                    )
                )
                self._dual_updates += 1
                model.logger.record("constrained_rl/mean_completed_episode_cost", observed_cost)
                model.logger.record("constrained_rl/dual_updates", self._dual_updates)
                self._completed_costs.clear()
            self._persist_state()
            self._rollout_environment_reward = 0.0
            self._rollout_penalty = 0.0
            self._rollout_transitions = 0
else:

    class LagrangianRiskCallback:  # type: ignore[no-redef]
        """Stub — stable-baselines3 is not installed."""

        def __init__(self, *args: object, **kwargs: object) -> None:
            """Reject construction when stable-baselines3 is unavailable.

            Args:
                *args: Positional callback configuration, ignored by this stub.
                **kwargs: Named callback configuration, ignored by this stub.
            """
            del args, kwargs
            raise ImportError("stable-baselines3 is required for LagrangianRiskCallback")
