"""Buy-and-hold baseline strategy."""

from __future__ import annotations

import pandas as pd


def buy_and_hold_returns(bars: pd.DataFrame) -> pd.Series:
    """Return a daily equity curve for a simple buy-and-hold.

    Args:
        bars: Bar DataFrame with a ``close`` column.

    Returns:
        Result of return a daily equity curve for a simple buy-and-hold.
    """
    close = bars["close"]
    returns = close.pct_change().fillna(0.0)
    equity = (1 + returns).cumprod()
    return equity
