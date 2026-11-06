"""Deterministic structure-priority policy over the eligible setup domain."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np

from decisioning.trade_setup import (
    NO_TRADE_ID,
    TRADE_SETUP_CANDIDATES,
    TRADE_SETUP_CATEGORY_COUNT,
    TRADE_SETUP_IDEAS,
    TRADE_SETUP_TIMEFRAMES,
    TradeSetupActionSchema,
    trade_setup_center,
)


class StructurePrioritySetupPolicy:
    """Select an eligible setup by declared family and timeframe precedence.

    The rule observes only the current candidate eligibility mask. It selects
    the first family/timeframe pair in the configured precedence that has an
    eligible candidate. If both directions are eligible for that pair, it
    abstains rather than imposing a directional tie-break.
    """

    def __init__(
        self,
        action_schema: TradeSetupActionSchema,
        *,
        idea_priority: Sequence[str],
        timeframe_priority: Sequence[str],
        normalized_risk: float = 0.5,
    ) -> None:
        """Bind a fixed, auditable structure precedence to an action schema.

        Args:
            action_schema: Versioned policy action schema to populate.
            idea_priority: Ordered setup families considered by the rule.
            timeframe_priority: Ordered setup timeframes considered per family.
            normalized_risk: Fixed risk coordinate emitted for every action.
        """
        if "trade_setup" not in action_schema.names or "risk" not in action_schema.names:
            raise ValueError("action schema must contain trade_setup and risk coordinates")
        ideas = tuple(idea_priority)
        timeframes = tuple(timeframe.upper() for timeframe in timeframe_priority)
        if not ideas or len(set(ideas)) != len(ideas) or set(ideas) - set(TRADE_SETUP_IDEAS):
            raise ValueError("idea_priority must contain unique supported setup families")
        if (
            not timeframes
            or len(set(timeframes)) != len(timeframes)
            or set(timeframes) - set(TRADE_SETUP_TIMEFRAMES)
        ):
            raise ValueError("timeframe_priority must contain unique supported timeframes")
        if (
            isinstance(normalized_risk, bool)
            or not np.isfinite(normalized_risk)
            or not 0.0 <= normalized_risk <= 1.0
        ):
            raise ValueError("normalized_risk must be finite and in [0, 1]")

        self.action_schema = action_schema
        self.idea_priority = ideas
        self.timeframe_priority = timeframes
        self.normalized_risk = float(normalized_risk)
        self._setup_index = action_schema.names.index("trade_setup")
        self._risk_index = action_schema.names.index("risk")
        self._action = np.zeros(action_schema.width, dtype=np.float32)
        self._action[self._risk_index] = np.float32(2.0 * self.normalized_risk - 1.0)
        if action_schema.has_entry_execution:
            # The fixed reference policy is market-only. Zero encodes a limit
            # order in this schema, so set the explicit market category.
            self._action[action_schema.indices["entry_execution"]] = np.float32(-0.5)
            self._action[action_schema.indices["limit_offset_atr"]] = np.float32(-1.0)
            self._action[action_schema.indices["limit_ttl_bars"]] = np.float32(-1.0)
        self._candidate_semantics = {
            candidate.candidate_id: candidate for candidate in TRADE_SETUP_CANDIDATES
        }

    def __call__(self, observation: dict[str, Any]) -> np.ndarray[Any, Any]:
        """Choose the first unambiguous eligible family/timeframe candidate.

        Args:
            observation: Current policy observation containing the setup mask.

        Returns:
            Action vector selecting the preferred eligible setup or no-trade.
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

        eligible_ids = np.flatnonzero(mask > 0.0)
        selected_id = NO_TRADE_ID
        for idea in self.idea_priority:
            priority_matched = False
            for timeframe in self.timeframe_priority:
                matches = [
                    int(candidate_id)
                    for candidate_id in eligible_ids
                    if candidate_id != NO_TRADE_ID
                    and self._candidate_semantics[int(candidate_id)].idea == idea
                    and self._candidate_semantics[int(candidate_id)].setup_timeframe == timeframe
                ]
                if matches:
                    if len(matches) == 1:
                        selected_id = matches[0]
                    # Long and short both active at the top priority is an
                    # ambiguous rule state, so retain NO_TRADE.
                    priority_matched = True
                    break
            if priority_matched:
                break

        action = self._action.copy()
        action[self._setup_index] = np.float32(trade_setup_center(selected_id))
        return action

    def metadata(self) -> dict[str, Any]:
        """Describe the fixed rule and the information it is permitted to use.

        Returns:
            Provenance metadata for this deterministic baseline policy.
        """
        return {
            "policy_id": "structure_priority_setup_v1",
            "baseline_tier": "tier_1_deterministic_structure_rule",
            "policy_action_mode": "deterministic",
            "permitted_information": ["current_observation.trade_setup_mask"],
            "training_performed": False,
            "selection_or_tuning_performed": False,
            "action_schema": self.action_schema.to_dict(),
            "idea_priority": list(self.idea_priority),
            "timeframe_priority": list(self.timeframe_priority),
            "normalized_risk": self.normalized_risk,
            "risk_coordinate_is_constant": True,
            "entry_execution": (
                "market" if self.action_schema.has_entry_execution else "market_default"
            ),
            "limit_order_controls": (
                "minimum_offset_and_ttl_inactive_under_market_execution"
                if self.action_schema.has_entry_execution
                else "not_in_action_schema"
            ),
            "setup_selection": "first eligible family/timeframe; abstain on direction conflict",
            "execution_and_risk_controls": "delegated to shared evaluation environment",
        }


class StructurePrioritySetupRolloutModel:
    """Expose the deterministic structure rule through the rollout interface."""

    def __init__(self, policy: StructurePrioritySetupPolicy) -> None:
        """Wrap a deterministic setup policy in the rollout model interface.

        Args:
            policy: Deterministic structure-priority policy to expose.
        """
        self._policy = policy

    @property
    def policy(self) -> StructurePrioritySetupRolloutModel:
        """Return this rollout-compatible model instance.

        Returns:
            This model wrapper.
        """
        return self

    @property
    def hybrid_action_coordinates(self) -> tuple[str, ...]:
        """Return the action coordinate names expected by the policy.

        Returns:
            Ordered names defined by the wrapped action schema.
        """
        return self._policy.action_schema.names

    @property
    def policy_metadata(self) -> dict[str, Any]:
        """Return setup-rule identity and permitted-information metadata.

        Returns:
            Provenance metadata emitted by the wrapped policy.
        """
        return self._policy.metadata()

    def predict(
        self, observation: dict[str, Any], *, deterministic: bool = True
    ) -> tuple[np.ndarray[Any, Any], None]:
        """Predict an action while matching the trained-model rollout API.

        Args:
            observation: Current environment observation.
            deterministic: Accepted for API compatibility; this policy is deterministic.

        Returns:
            Action vector and ``None`` for the unused recurrent state.
        """
        del deterministic
        return self._policy(observation), None
