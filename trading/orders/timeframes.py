"""Canonical ordering and provenance for market-reference timeframes."""

from __future__ import annotations

TIMEFRAME_ORDER = ("M1", "M3", "M5", "M10", "M15", "M30", "H1", "H2", "H4", "D1", "W1")


def normalize_timeframe(timeframe: str) -> str:
    """Return the canonical uppercase timeframe label."""
    return str(timeframe).upper()


def timeframe_index(timeframe: str) -> int:
    """Return the configured chronology rank for a timeframe label."""
    return TIMEFRAME_ORDER.index(normalize_timeframe(timeframe))


def reference_timeframe(reference_name: str) -> str:
    """Infer a reference's timeframe from its canonical source name."""
    head = str(reference_name).split("|", 1)[0]
    for timeframe in TIMEFRAME_ORDER:
        if head.startswith(f"{timeframe}_"):
            return timeframe
    if head.startswith(("prev_day_", "ctx_prev_day_", "yesterday_")):
        return "D1"
    if head.startswith(("lastweek_", "ctx_prev_week_")):
        return "W1"
    if head.startswith(("asian_", "london_")):
        return "D1"
    return "M1"


def source_timeframe(reference_name: str) -> str:
    """Return a candle timeframe, leaving session/day references unlabelled.

    Reporting uses this distinction because session highs/lows have no single
    candle timeframe. Candidate eligibility uses :func:`reference_timeframe`,
    which assigns those references to their calendar timeframe for ordering.
    """
    head = str(reference_name).split("|", 1)[0]
    if not head:
        return ""
    if head.startswith(("asian_", "london_", "prev_day_", "ctx_prev_week_")):
        return ""
    return reference_timeframe(reference_name)


def reference_timeframe_index(reference_name: str) -> int:
    """Return the chronology rank for a named market reference."""
    return timeframe_index(reference_timeframe(reference_name))
