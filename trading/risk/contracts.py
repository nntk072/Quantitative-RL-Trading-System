"""Backend-neutral account state and risk-policy decision contract."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final, Literal, Protocol

RiskDailyPnlBasis = Literal[
    "session_net_equity", "legacy_gross_closed_losses", "ftmo_midnight_balance"
]
RISK_STATE_SCHEMA_V1 = "risk-state-v1"
RISK_DECISION_SCHEMA_V1 = "risk-decision-v1"
RISK_BREACH_EVENT_SCHEMA_V1 = "risk-breach-event-v1"
RISK_DAILY_PNL_BASIS_SESSION_EQUITY: Final[RiskDailyPnlBasis] = "session_net_equity"
RISK_DAILY_PNL_BASIS_LEGACY_GROSS_LOSSES: Final[RiskDailyPnlBasis] = "legacy_gross_closed_losses"
RISK_DAILY_PNL_BASIS_FTMO_MIDNIGHT: Final[RiskDailyPnlBasis] = "ftmo_midnight_balance"


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
    daily_pnl_basis: RiskDailyPnlBasis
    schema_version: str = RISK_STATE_SCHEMA_V1

    def __post_init__(self) -> None:
        """Validate the versioned monetary state passed to a risk policy."""
        if self.schema_version != RISK_STATE_SCHEMA_V1:
            raise ValueError(f"unsupported risk state schema: {self.schema_version!r}")
        if self.daily_pnl_basis not in {
            RISK_DAILY_PNL_BASIS_SESSION_EQUITY,
            RISK_DAILY_PNL_BASIS_LEGACY_GROSS_LOSSES,
            RISK_DAILY_PNL_BASIS_FTMO_MIDNIGHT,
        }:
            raise ValueError(f"unsupported daily PnL basis: {self.daily_pnl_basis!r}")
        values = (self.equity, self.daily_pnl, self.open_risk, self.daily_loss_limit)
        if any(not math.isfinite(float(value)) for value in values):
            raise ValueError("risk state values must be finite")
        if self.open_risk < 0.0:
            raise ValueError("open_risk must be non-negative")
        if self.daily_loss_limit < 0.0:
            raise ValueError("daily_loss_limit must be non-negative")


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
    schema_version: str = RISK_DECISION_SCHEMA_V1

    def __post_init__(self) -> None:
        """Validate the versioned approval returned by a risk policy."""
        if self.schema_version != RISK_DECISION_SCHEMA_V1:
            raise ValueError(f"unsupported risk decision schema: {self.schema_version!r}")
        if not math.isfinite(float(self.risk_amount)) or self.risk_amount < 0.0:
            raise ValueError("risk_amount must be finite and non-negative")
        if not self.allowed and self.risk_amount != 0.0:
            raise ValueError("a denied risk decision must approve zero risk")


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


__all__ = [
    "RISK_DECISION_SCHEMA_V1",
    "RISK_DAILY_PNL_BASIS_LEGACY_GROSS_LOSSES",
    "RISK_DAILY_PNL_BASIS_SESSION_EQUITY",
    "RISK_STATE_SCHEMA_V1",
    "RiskDecision",
    "RiskDailyPnlBasis",
    "RiskPolicy",
    "RiskState",
]
