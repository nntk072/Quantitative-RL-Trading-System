"""Grid coverage, gaps and off-grid event times for normalized market data (DATA-SCHEMAS).

A gap is a spacing above one grid step between consecutive event times. Its missing slots are the
grid times strictly between the two rows. A gap is classified only against a session calendar that
the caller supplies, and only when that calendar covers the whole missing interval:

- ``calendar_closed``: the calendar covers the missing interval and no trading session overlaps it.
- ``unexplained``: the calendar covers the interval and a trading session overlaps it, so bars are
  missing where the calendar says the market traded.
- ``unclassified``: no calendar was supplied, or it does not cover the interval. The gap is listed,
  never assumed to be a market closure.

The configured ``config/ny_session_schedule.csv`` is not an authoritative venue calendar and is not
read here. Event times are also checked against the grid, so a bar that is not on its timeframe
boundary is reported as off-grid.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pyarrow as pa  # type: ignore[import-untyped]

from market_data.arrow_schemas import CALENDAR_KINDS, _as_ns, _column, validate_calendar

CALENDAR_CLOSED = "calendar_closed"
UNEXPLAINED = "unexplained"
UNCLASSIFIED = "unclassified"
TRADING_KINDS = frozenset({"trading", "early_close"})


@dataclass(frozen=True, slots=True)
class Gap:
    """One interval between consecutive event times that is longer than one grid step.

    Attributes:
        start_ns: Event time of the row before the gap, in UTC nanoseconds.
        end_ns: Event time of the row after the gap, in UTC nanoseconds.
        missing_slots: Grid times strictly between the two rows.
        status: ``calendar_closed``, ``unexplained`` or ``unclassified``.
        reason: Why the status was assigned.
    """

    start_ns: int
    end_ns: int
    missing_slots: int
    status: str
    reason: str


@dataclass(frozen=True, slots=True)
class GridReport:
    """Coverage facts for one instrument and timeframe.

    Attributes:
        rows: Number of event times.
        off_grid_rows: Row positions whose event time is not on the grid.
        gaps: Every gap longer than one grid step, in time order.
    """

    rows: int
    off_grid_rows: list[int]
    gaps: list[Gap]

    @property
    def missing_slots(self) -> int:
        """Return the total number of missing grid slots across all gaps.

        Returns:
            The sum of ``missing_slots`` over every gap.
        """
        return sum(gap.missing_slots for gap in self.gaps)


def _ceil_div(numerator: int, denominator: int) -> int:
    """Return ceil(numerator / denominator) for a positive integer denominator.

    Args:
        numerator: Integer numerator, of either sign.
        denominator: Positive integer denominator.

    Returns:
        The smallest integer not less than the exact quotient.
    """
    return -((-numerator) // denominator)


def _missing_slots(start: int, end: int, spacing: int, origin: int) -> int:
    """Count the grid times strictly between two event times.

    Args:
        start: Earlier event time in nanoseconds.
        end: Later event time in nanoseconds.
        spacing: Grid step in nanoseconds.
        origin: A grid time in nanoseconds; grid times are ``origin + k * spacing``.

    Returns:
        The number of grid times t with start < t < end.
    """
    first = (start - origin) // spacing + 1
    last = _ceil_div(end - origin, spacing) - 1
    return max(0, last - first + 1)


def _calendar_intervals(calendar: pa.Table, lo: int, hi: int) -> tuple[list[tuple[int, int]], bool]:
    """Return the calendar intervals overlapping ``[lo, hi)`` and whether any is a trading session.

    Args:
        calendar: Validated calendar table with the CALENDAR_SCHEMA columns.
        lo: Interval start in nanoseconds.
        hi: Interval end in nanoseconds, exclusive.

    Returns:
        The overlapping ``(open, close)`` pairs, and True when one of them is a trading session.
    """
    open_ns = _as_ns(calendar, "session_open")
    close_ns = _as_ns(calendar, "session_close")
    kind = _column(calendar, "session_kind")
    intervals: list[tuple[int, int]] = []
    trading = False
    for i in range(calendar.num_rows):
        if kind[i] not in CALENDAR_KINDS:
            continue
        if open_ns[i] < hi and close_ns[i] > lo:
            intervals.append((int(open_ns[i]), int(close_ns[i])))
            trading = trading or kind[i] in TRADING_KINDS
    return intervals, trading


def _covers(intervals: list[tuple[int, int]], lo: int, hi: int) -> bool:
    """Return True when the union of intervals covers all of ``[lo, hi)``.

    Args:
        intervals: Half-open ``(open, close)`` pairs in nanoseconds.
        lo: Start of the interval to cover, inclusive.
        hi: End of the interval to cover, exclusive.

    Returns:
        True when every nanosecond of ``[lo, hi)`` lies in one of the intervals.
    """
    cursor = lo
    for open_ns, close_ns in sorted(intervals):
        if open_ns > cursor:
            break
        cursor = max(cursor, close_ns)
        if cursor >= hi:
            return True
    return cursor >= hi


def _classify(start: int, end: int, spacing: int, calendar: pa.Table | None) -> tuple[str, str]:
    """Assign a status to one gap from the calendar, if one is supplied.

    Args:
        start: Event time before the gap, nanoseconds.
        end: Event time after the gap, nanoseconds.
        spacing: Grid step in nanoseconds.
        calendar: Validated session calendar, or None.

    Returns:
        The status and the reason for it.
    """
    if calendar is None:
        return UNCLASSIFIED, "no authoritative session calendar supplied"
    lo = start + spacing
    intervals, trading = _calendar_intervals(calendar, lo, end)
    if not _covers(intervals, lo, end):
        return UNCLASSIFIED, "session calendar does not cover the missing interval"
    if trading:
        return UNEXPLAINED, "a trading session overlaps the missing interval"
    return CALENDAR_CLOSED, "the session calendar marks the missing interval closed"


def grid_report(
    event_ns: np.ndarray[Any, Any],
    spacing_ns: int,
    *,
    origin_ns: int = 0,
    calendar: pa.Table | None = None,
) -> GridReport:
    """Report off-grid event times and gaps for strictly increasing event times.

    Args:
        event_ns: Event times in UTC nanoseconds, strictly increasing (validate order first).
        spacing_ns: Grid step in nanoseconds, for example 60 seconds for M1 bars.
        origin_ns: A grid time; grid times are ``origin_ns + k * spacing_ns``. A daily grid anchored
            at a session open uses that instant here.
        calendar: Optional validated session calendar used to classify gaps.

    Returns:
        Off-grid rows, every gap with its missing slots and status, and the row count.

    Raises:
        ValueError: If the spacing is not positive, the calendar is invalid, or the event times are
            not strictly increasing.
    """
    if spacing_ns <= 0:
        raise ValueError("grid spacing must be positive")
    if calendar is not None:
        problems = validate_calendar(calendar)
        if problems:
            raise ValueError(
                f"invalid session calendar: {problems[0].reason} at row {problems[0].row}"
            )
    event = np.asarray(event_ns, dtype=np.int64)
    if event.size > 1 and not bool(np.all(np.diff(event) > 0)):
        raise ValueError(
            "grid coverage needs strictly increasing event times; validate order first"
        )
    off_grid = np.flatnonzero((event - origin_ns) % spacing_ns != 0).tolist()
    gaps: list[Gap] = []
    for i in np.flatnonzero(np.diff(event) > spacing_ns):
        start, end = int(event[i]), int(event[i + 1])
        # An open interval longer than one grid step always contains a grid time, so a gap has at least
        # one missing slot.
        missing = _missing_slots(start, end, spacing_ns, origin_ns)
        status, reason = _classify(start, end, spacing_ns, calendar)
        gaps.append(Gap(start, end, missing, status, reason))
    return GridReport(rows=int(event.size), off_grid_rows=off_grid, gaps=gaps)


__all__ = [
    "CALENDAR_CLOSED",
    "UNCLASSIFIED",
    "UNEXPLAINED",
    "Gap",
    "GridReport",
    "grid_report",
]
