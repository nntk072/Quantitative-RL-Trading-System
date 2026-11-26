"""Transition record contract for PPO rollouts and SAC replay.

A record stores what the environment actually executed, not what a
deterministic head would have chosen. The log-probability must come from the
same distribution that sampled the executed action, and the setup category it
names must have been eligible under the stored mask.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

TRANSITION_SCHEMA_VERSION = "learner-transition-v1"


@dataclass(frozen=True, slots=True)
class TransitionRecord:
    """One environment transition as the learner must consume it.

    Attributes:
        policy_version_id: Identity of the policy that produced the action.
        executed_action: Encoded Box action actually sent to the environment.
        log_prob: Joint log-probability of ``executed_action`` under the sampling
            distribution.
        old_value: Value estimate recorded when the action was sampled.
        setup_mask: Boolean eligibility per trade-setup category, or ``None``
            when the action family has no setup head.
        setup_class: Trade-setup category index named by ``executed_action``,
            or ``None`` when there is no setup head.
        terminated: Whether the episode ended on this transition.
        truncated: Whether the episode was cut by a time limit on this transition.
        terminal_observation: Observation after the transition when the episode
            ended or was truncated, used for bootstrapping; otherwise ``None``.
        recurrent_state: Recurrent hidden state entering this transition, or
            ``None`` for feed-forward policies.
    """

    policy_version_id: str
    executed_action: np.ndarray[Any, Any]
    log_prob: float
    old_value: float
    setup_mask: np.ndarray[Any, Any] | None
    setup_class: int | None
    terminated: bool
    truncated: bool
    terminal_observation: np.ndarray[Any, Any] | None = None
    recurrent_state: np.ndarray[Any, Any] | None = None

    def __post_init__(self) -> None:
        """Validate the record before it can enter a rollout or replay buffer."""
        if not self.policy_version_id or not self.policy_version_id.strip():
            raise ValueError("transition policy_version_id is required")
        action = np.asarray(self.executed_action)
        if action.ndim != 1 or action.size == 0:
            raise ValueError("executed_action must be a non-empty 1-D array")
        if not np.all(np.isfinite(action.astype(np.float64))):
            raise ValueError("executed_action must be finite")
        if not math.isfinite(float(self.log_prob)):
            raise ValueError("log_prob must be finite; masked or impossible actions are invalid")
        if not math.isfinite(float(self.old_value)):
            raise ValueError("old_value must be finite")
        if self.terminated and self.truncated:
            raise ValueError("a transition cannot be both terminated and truncated")
        ended = self.terminated or self.truncated
        if ended and self.terminal_observation is None:
            raise ValueError("ended or truncated transitions must carry the terminal observation")
        if not ended and self.terminal_observation is not None:
            raise ValueError("terminal observation is only allowed on ended transitions")
        if (self.setup_mask is None) != (self.setup_class is None):
            raise ValueError("setup_mask and setup_class must be provided together")
        if self.setup_mask is not None:
            mask = np.asarray(self.setup_mask)
            if mask.ndim != 1 or mask.size == 0:
                raise ValueError("setup_mask must be a non-empty 1-D array")
            if mask.dtype != np.bool_:
                raise ValueError("setup_mask must be boolean, True for eligible categories")
            if not bool(mask.any()):
                raise ValueError("setup_mask must allow at least one category")
            index = int(self.setup_class)  # type: ignore[arg-type]
            if not 0 <= index < mask.size:
                raise ValueError("setup_class is outside the setup mask")
            if not bool(mask[index]):
                raise ValueError("executed setup category was not eligible under its mask")


__all__ = ["TRANSITION_SCHEMA_VERSION", "TransitionRecord"]
