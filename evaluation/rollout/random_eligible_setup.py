"""Seeded, mask-aware random policy for the versioned trade-setup action space."""

from __future__ import annotations

from typing import Any

import numpy as np

from decisioning.trade_setup import (
    NO_TRADE_ID,
    TRADE_SETUP_CATEGORY_COUNT,
    TradeSetupActionSchema,
    trade_setup_center,
)


class RandomEligibleSetupPolicy:
    """Choose uniformly among eligible setup IDs with an explicit trade rate.

    The policy preserves the environment's action schema, uses a private seeded
    generator, and keeps all non-setup controls fixed. The normalized risk
    coordinate is expressed within the configured environment risk interval;
    it is not an absolute account-risk percentage.
    """

    def __init__(
        self,
        action_schema: TradeSetupActionSchema,
        *,
        seed: int,
        trade_probability: float = 1.0,
        normalized_risk: float = 0.5,
    ) -> None:
        """Initialize a reproducible random-eligible policy.

        Args:
            action_schema: Exact versioned schema used by the environment.
            seed: Non-negative random seed for setup choices and trade decisions.
            trade_probability: Per-decision probability of selecting a setup
                when at least one non-NO_TRADE candidate is eligible.
            normalized_risk: Position within the environment's configured risk
                interval, from zero (minimum) to one (maximum).
        """
        if isinstance(seed, bool) or seed < 0:
            raise ValueError("seed must be non-negative")
        if (
            isinstance(trade_probability, bool)
            or not np.isfinite(trade_probability)
            or not 0.0 <= trade_probability <= 1.0
        ):
            raise ValueError("trade_probability must be finite and in [0, 1]")
        if (
            isinstance(normalized_risk, bool)
            or not np.isfinite(normalized_risk)
            or not 0.0 <= normalized_risk <= 1.0
        ):
            raise ValueError("normalized_risk must be finite and in [0, 1]")
        if "trade_setup" not in action_schema.names or "risk" not in action_schema.names:
            raise ValueError("action schema must contain trade_setup and risk coordinates")

        self.action_schema = action_schema
        self.seed = int(seed)
        self.trade_probability = float(trade_probability)
        self.normalized_risk = float(normalized_risk)
        self._rng = np.random.default_rng(self.seed)
        self._setup_index = action_schema.names.index("trade_setup")
        self._risk_index = action_schema.names.index("risk")
        self._action = np.zeros(action_schema.width, dtype=np.float32)
        self._action[self._risk_index] = np.float32(2.0 * self.normalized_risk - 1.0)
        if action_schema.has_entry_execution:
            # This reference randomizes setup choice only; execution stays
            # market-based so it does not silently add a limit-order treatment.
            self._action[action_schema.indices["entry_execution"]] = np.float32(-0.5)
            self._action[action_schema.indices["limit_offset_atr"]] = np.float32(-1.0)
            self._action[action_schema.indices["limit_ttl_bars"]] = np.float32(-1.0)

    def __call__(self, observation: dict[str, Any]) -> np.ndarray[Any, Any]:
        """Return an action selecting only a currently eligible setup.

        Args:
            observation: Environment observation containing ``trade_setup_mask``.

        Returns:
            A float32 action vector matching the configured action schema.
        """
        if "trade_setup_mask" not in observation:
            raise ValueError("observation is missing trade_setup_mask")
        mask = np.asarray(observation["trade_setup_mask"], dtype=np.float32).reshape(-1)
        if mask.shape != (TRADE_SETUP_CATEGORY_COUNT,):
            raise ValueError(
                f"trade_setup_mask has shape {mask.shape}, expected {(TRADE_SETUP_CATEGORY_COUNT,)}"
            )
        if not np.isfinite(mask).all():
            raise ValueError("trade_setup_mask must contain only finite values")
        if mask[NO_TRADE_ID] <= 0.0:
            raise ValueError("NO_TRADE must remain eligible")

        eligible = np.flatnonzero(mask > 0.0)
        eligible = eligible[eligible != NO_TRADE_ID]
        if eligible.size and self._rng.random() < self.trade_probability:
            candidate_id = int(self._rng.choice(eligible))
        else:
            candidate_id = NO_TRADE_ID

        action = self._action.copy()
        action[self._setup_index] = np.float32(trade_setup_center(candidate_id))
        return action

    def metadata(self) -> dict[str, Any]:
        """Return settings that identify and reproduce this policy instance.

        Returns:
            Tier, rationale, permitted information, fit/selection status,
            action schema, seed, trade probability, risk, and action conventions.
        """
        return {
            "policy_id": "random_eligible_trade_setup_v1",
            "baseline_tier": "tier_0_accounting_and_decision_sanity",
            "rationale": "measure chance selection among currently eligible setups",
            "permitted_information": ["current_observation.trade_setup_mask"],
            "training_performed": False,
            "selection_or_tuning_performed": False,
            "action_schema": self.action_schema.to_dict(),
            "seed": self.seed,
            "trade_probability": self.trade_probability,
            "normalized_risk": self.normalized_risk,
            "risk_coordinate_semantics": "position within configured environment risk interval",
            "setup_selection": "uniform_over_currently_eligible_non_no_trade_ids",
            "other_action_coordinates": "management coordinates fixed at zero",
            "entry_execution": (
                "market" if self.action_schema.has_entry_execution else "market_default"
            ),
            "limit_order_controls": (
                "minimum_offset_and_ttl_inactive_under_market_execution"
                if self.action_schema.has_entry_execution
                else "not_in_action_schema"
            ),
            "execution_and_risk_controls": "delegated to shared evaluation environment",
        }


class RandomEligibleSetupRolloutModel:
    """Adapt the seeded baseline to the shared trained-policy rollout API.

    The adapter supplies the SB3-style ``predict`` tuple and action-coordinate
    metadata expected by ``evaluate_model``. It does not train a model or
    change the baseline's seeded selection behavior.
    """

    def __init__(self, policy: RandomEligibleSetupPolicy) -> None:
        """Bind one random policy to the shared rollout interface.

        Args:
            policy: Seeded setup policy built with the environment's action schema.
        """
        self._policy = policy

    @property
    def policy(self) -> RandomEligibleSetupRolloutModel:
        """Expose the semantic action coordinates used by rollout diagnostics.

        Returns:
            This rollout-compatible model wrapper.
        """
        return self

    @property
    def hybrid_action_coordinates(self) -> tuple[str, ...]:
        """Return the exact action-coordinate names used by the baseline.

        Returns:
            Ordered coordinate names from the policy action schema.
        """
        return self._policy.action_schema.names

    @property
    def policy_metadata(self) -> dict[str, Any]:
        """Return seed and action semantics for a future result manifest.

        Returns:
            Baseline identity, seed, action schema, and policy semantics.
        """
        return self._policy.metadata()

    def predict(
        self,
        observation: dict[str, Any],
        *,
        deterministic: bool = True,
    ) -> tuple[np.ndarray[Any, Any], None]:
        """Return a schema-compatible random action and empty recurrent state.

        ``deterministic`` is accepted for compatibility with the rollout API;
        the policy remains random and reproducible from its private seed.

        Args:
            observation: Environment observation containing the eligible setup mask.
            deterministic: Accepted for rollout compatibility and otherwise ignored.

        Returns:
            Action vector and ``None`` recurrent state.
        """
        del deterministic
        return self._policy(observation), None


class AlwaysNoTradePolicy(RandomEligibleSetupPolicy):
    """Return the versioned NO_TRADE action for every environment decision."""

    def __init__(self, action_schema: TradeSetupActionSchema) -> None:
        """Initialize a deterministic flat control with minimum risk coordinate.

        Args:
            action_schema: Environment action schema populated by the control.
        """
        super().__init__(action_schema, seed=0, trade_probability=0.0, normalized_risk=0.0)

    def __call__(self, observation: dict[str, Any]) -> np.ndarray[Any, Any]:
        """Return NO_TRADE without reading market or eligibility fields.

        Args:
            observation: Environment observation, intentionally unused.

        Returns:
            Action vector selecting no-trade at minimum risk.
        """
        del observation
        action = self._action.copy()
        action[self._setup_index] = np.float32(trade_setup_center(NO_TRADE_ID))
        return action

    def metadata(self) -> dict[str, Any]:
        """Identify this policy as the always-flat accounting control.

        Returns:
            Provenance metadata identifying the no-trade baseline.
        """
        metadata = super().metadata()
        metadata.update(
            {
                "policy_id": "always_no_trade_v1",
                "rationale": "measure the shared environment with no entry decisions",
                "permitted_information": [],
                "setup_selection": "always_no_trade",
                "seed": None,
                "trade_probability": 0.0,
            }
        )
        return metadata


class AlwaysNoTradeRolloutModel(RandomEligibleSetupRolloutModel):
    """Run the always-flat control through the shared policy evaluator."""

    def __init__(self, policy: AlwaysNoTradePolicy) -> None:
        """Bind one deterministic no-trade policy to the rollout interface.

        Args:
            policy: Always-flat policy exposed through the rollout interface.
        """
        super().__init__(policy)
