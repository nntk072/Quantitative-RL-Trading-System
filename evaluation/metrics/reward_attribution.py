"""Reconcile the reward scalar with reported per-step reward components."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from math import fsum, isfinite


@dataclass
class RewardAttribution:
    """Accumulate reward components and preserve unreported/residual totals."""

    component_sums: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    reward_sum: float = 0.0
    unattributed_sum: float = 0.0
    reported_steps: int = 0
    unreported_steps: int = 0

    def add(self, reward: float, parts: Mapping[str, float] | None) -> None:
        """Track missing diagnostics explicitly; never infer fabricated components.

        Args:
            reward: Numeric value used for the reward.
            parts: Key-value data used for the parts.
        """
        amount = float(reward)
        if not isfinite(amount):
            raise ValueError("reward must be finite")
        local_parts = dict(parts or {})
        for name, value in local_parts.items():
            if not isfinite(float(value)):
                raise ValueError(f"reward part {name} must be finite")
        self.reward_sum += amount
        if local_parts:
            self.reported_steps += 1
        else:
            self.unreported_steps += 1
        for name, value in local_parts.items():
            self.component_sums[str(name)] += float(value)
        self.unattributed_sum += amount - fsum(float(x) for x in local_parts.values())

    def as_dict(self) -> dict[str, object]:
        """Return component totals and their reward reconciliation error.

        Returns:
            Mapping from ``str`` keys to ``object`` values.
        """
        components = dict(sorted(self.component_sums.items()))
        error = self.reward_sum - (fsum(components.values()) + self.unattributed_sum)
        return {
            "component_sums": components,
            "reward_sum": self.reward_sum,
            "unattributed_sum": self.unattributed_sum,
            "reported_steps": self.reported_steps,
            "unreported_steps": self.unreported_steps,
            "reconciliation_error": error,
        }
