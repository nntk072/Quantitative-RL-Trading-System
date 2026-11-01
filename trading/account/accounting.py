"""Reusable account accounting primitives."""

from __future__ import annotations


def payout_due(balance: float, target_balance: float) -> bool:
    """Return whether balance has reached the payout target.

    Args:
        balance: Current account balance.
        target_balance: Balance threshold that enables a payout.

    Returns:
        Whether payout due meets the requested condition.
    """
    return float(balance) >= float(target_balance)


def payout_amount(balance: float, operating_balance: float) -> float:
    """Calculate funds distributable while preserving operating balance.

    Args:
        balance: Current account balance.
        operating_balance: Balance retained in the trading account.

    Returns:
        Nonnegative amount available for payout.
    """
    return max(0.0, float(balance) - float(operating_balance))
