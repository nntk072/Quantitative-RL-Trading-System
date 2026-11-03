"""Repeated-payout policy state transitions shared by simulation and evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from trading.account import payout_amount, payout_due
from trading.policy.config import TradingPolicyConfig


@dataclass(frozen=True, slots=True)
class PayoutDecision:
    """Result of evaluating whether an account payout is due.

    Attributes:
        due: Whether the configured target balance has been reached.
        amount: Payout amount that preserves operating balance.
    """

    due: bool
    amount: float


def evaluate_payout(
    balance: float, operating_balance: float, target_balance: float
) -> PayoutDecision:
    """Evaluate payout eligibility and amount for an account balance.

    Args:
        balance: Current balance.
        operating_balance: Balance retained after a payout.
        target_balance: Balance required for payout eligibility.

    Returns:
        Decision with eligibility and nonnegative payout amount.
    """
    due = payout_due(balance, target_balance)
    return PayoutDecision(due=due, amount=payout_amount(balance, operating_balance) if due else 0.0)


def build_payout_reset_event(
    *,
    balance: float,
    policy: TradingPolicyConfig,
    cycle: int,
    event_time: Any,
) -> dict[str, Any] | None:
    """Build the shared realized-balance payout event when a flat cycle qualifies.

    Callers must invoke this only at an account transition boundary while flat.
    It does not mutate account or lifecycle state; the environment and backtest
    own their distinct reset, termination, reward, and reporting behavior.
    """
    if not policy.repeated_payout:
        return None
    decision = evaluate_payout(
        balance,
        policy.operating_balance,
        policy.profit_target_balance,
    )
    if not decision.due:
        return None
    return {
        "type": "payout_reset",
        "time": event_time,
        "cycle": int(cycle),
        "payout": float(decision.amount),
        "balance_before_reset": float(balance),
        "operating_balance": float(policy.operating_balance),
    }
