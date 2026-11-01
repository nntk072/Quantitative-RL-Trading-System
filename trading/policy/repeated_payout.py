"""Repeated-payout policy state transitions shared by simulation and evaluation."""

from __future__ import annotations

from dataclasses import dataclass

from trading.account import payout_amount, payout_due


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
