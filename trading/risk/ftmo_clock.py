"""FTMO Challenge 2-Step daily boundaries, distinct from the NY trading session.

The broker server clock and the FTMO drawdown clock are independent.  The
Prague clock observes daylight-saving time.  Callers must fail closed for an
open position crossing midnight without a trustworthy midnight balance.
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

_PRAGUE = ZoneInfo("Europe/Prague")


class FTMOMidnightSnapshotUnavailable(RuntimeError):
    """Required midnight balance/valuation state cannot be reconstructed."""


def ftmo_trading_day(timestamp: datetime | str) -> date:
    """Return the FTMO CE(S)T calendar date of an aware timestamp.

    Args:
        timestamp: A timezone-aware event time (never an unlabelled broker time).

    Returns:
        The corresponding Prague local calendar date.
    """
    value = (
        datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if isinstance(timestamp, str)
        else timestamp
    )
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("FTMO day requires a timezone-aware event timestamp")
    return value.astimezone(_PRAGUE).date()


__all__ = ["FTMOMidnightSnapshotUnavailable", "ftmo_trading_day"]
