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
    balance: float,
    operating_balance: float,
    target_balance: float,
    *,
    payout_fraction: float = 1.0,
) -> PayoutDecision:
    """Evaluate payout eligibility and amount for an account balance.

    Args:
        balance: Current balance.
        operating_balance: Balance retained after a payout.
        target_balance: Balance required for payout eligibility.
        payout_fraction: Share of realized profit paid out when eligible.

    Returns:
        Decision with eligibility and nonnegative payout amount.
    """
    fraction = float(payout_fraction)
    if not 0.0 <= fraction <= 1.0:
        raise ValueError("payout_fraction must be in [0, 1]")
    due = payout_due(balance, target_balance)
    amount = payout_amount(balance, operating_balance) * fraction if due else 0.0
    return PayoutDecision(due=due, amount=amount)


def build_payout_reset_event(
    *,
    balance: float,
    policy: TradingPolicyConfig,
    cycle: int,
    event_time: Any,
    max_drawdown_mode: str,
) -> dict[str, Any] | None:
    """Build the shared realized-balance payout event when a flat cycle qualifies.

    Callers must invoke this only at an account transition boundary while flat.
    It does not mutate account or lifecycle state; the environment and backtest
    own their distinct reset, termination, reward, and reporting behavior.

    Args:
        balance: Realized account balance at the cycle boundary.
        policy: Repeated-payout thresholds and operating balance.
        cycle: Current payout-cycle number.
        event_time: Timestamp assigned to the payout event.
        max_drawdown_mode: Maximum-loss model controlling payout share.

    Returns:
        Payout reset record when due, or ``None`` when policy or balance is ineligible.
    """
    if not policy.repeated_payout:
        return None
    if max_drawdown_mode not in {"static", "eod", "intraday_trailing"}:
        raise ValueError("unsupported max_drawdown_mode for payout")
    payout_fraction = 1.0 if max_drawdown_mode == "static" else 0.5
    decision = evaluate_payout(
        balance,
        policy.operating_balance,
        policy.profit_target_balance,
        payout_fraction=payout_fraction,
    )
    if not decision.due:
        return None
    profit = float(balance) - float(policy.operating_balance)
    payout = float(decision.amount)
    post_payout_balance = float(balance) - payout
    return {
        "type": "payout_reset",
        "payout_schema_version": "payout_reset.v2",
        "time": event_time,
        "cycle": int(cycle),
        "max_drawdown_mode": max_drawdown_mode,
        "payout_fraction": payout_fraction,
        "profit_above_operating_balance": profit,
        "payout": payout,
        "retained_profit": profit - payout,
        "balance_before_reset": float(balance),
        "operating_balance": float(policy.operating_balance),
        "balance_after_reset": post_payout_balance,
    }
