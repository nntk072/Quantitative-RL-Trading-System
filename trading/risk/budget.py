"""Risk-request approval against policy and account capacity."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RiskBudgetDecision:
    requested_usd: float
    approved_usd: float
    policy_cap_usd: float
    execution_reserve_usd: float


def risk_budget_from_equity(equity: float, risk_fraction: float) -> float:
    """Resolve a non-negative dollar risk request from equity and a fraction."""
    return max(0.0, float(equity) * float(risk_fraction))


def approve_dynamic_risk(
    *,
    equity: float,
    risk_frac: float,
    max_agent_risk_frac: float,
    daily_capacity: float,
    account_capacity: float,
    execution_reserve_usd: float,
) -> RiskBudgetDecision:
    requested = risk_budget_from_equity(equity, risk_frac)
    policy_cap = min(
        risk_budget_from_equity(equity, max_agent_risk_frac),
        max(0.0, float(daily_capacity)),
        max(0.0, float(account_capacity)),
    )
    reserve = max(0.0, float(execution_reserve_usd))
    approved = max(0.0, min(requested, max(0.0, policy_cap - reserve)))
    return RiskBudgetDecision(requested, approved, policy_cap, reserve)
