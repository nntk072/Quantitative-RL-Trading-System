"""Account loss floors and remaining risk capacity."""

from __future__ import annotations


def canonical_daily_loss(session_start_equity: float, equity: float) -> float:
    """Return session-start equity minus current equity, floored at zero.

    Args:
        session_start_equity: Equity at the start of the current loss session.
        equity: Current account equity.

    Returns:
        Nonnegative realized daily loss.
    """
    return max(0.0, float(session_start_equity) - float(equity))


def daily_floor(session_start_equity: float, daily_loss_limit: float) -> float:
    """Calculate the lowest permitted equity for the daily-loss rule.

    Args:
        session_start_equity: Equity at the start of the loss session.
        daily_loss_limit: Maximum permitted daily loss in account currency.

    Returns:
        Equity floor for the session.
    """
    return float(session_start_equity) - float(daily_loss_limit)


def remaining_daily_capacity(
    session_start_equity: float, equity: float, daily_loss_limit: float
) -> float:
    """Calculate remaining loss capacity under the daily limit.

    Args:
        session_start_equity: Equity at the start of the loss session.
        equity: Current account equity.
        daily_loss_limit: Maximum permitted daily loss.

    Returns:
        Nonnegative remaining daily capacity.
    """
    return max(0.0, float(equity) - daily_floor(session_start_equity, daily_loss_limit))


def remaining_account_capacity(equity: float, account_floor: float) -> float:
    """Calculate equity available above the account floor.

    Args:
        equity: Current account equity.
        account_floor: Minimum permitted account equity.

    Returns:
        Nonnegative capacity above the floor.
    """
    return max(0.0, float(equity) - float(account_floor))
