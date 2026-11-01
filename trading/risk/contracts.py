"""Backend-neutral account state and risk-policy decision contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class RiskState:
    """Account risk state provided to a risk policy.

    Attributes:
        equity: Current account equity.
        daily_pnl: Profit or loss for the current session.
        open_risk: Risk already committed to open positions.
    """

    equity: float
    daily_pnl: float
    open_risk: float
    daily_loss_limit: float


@dataclass(frozen=True, slots=True)
class RiskDecision:
    """Risk-policy result for one requested trade.

    Attributes:
        risk_amount: Approved risk amount.
        reason: Optional explanation when risk is reduced or denied.
    """

    allowed: bool
    risk_amount: float
    reason: str | None = None


class RiskPolicy(Protocol):
    """Evaluate requested risk without depending on a broker or policy model."""

    def decide(self, state: RiskState, requested_risk: float) -> RiskDecision:
        """Evaluate requested risk against the current account state.

        Args:
            state: Current account and open-risk state.
            requested_risk: Agent-requested risk amount.

        Returns:
            Approved risk decision and any policy reason.
        """
        ...


__all__ = ["RiskDecision", "RiskPolicy", "RiskState"]
