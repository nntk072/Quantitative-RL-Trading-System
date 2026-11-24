"""Tick-quote coverage checks aligned to the environment's execution schedule."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pandas as pd

from market_data.loading.ticks import TickBook, tick_execution_coverage
from market_data.transforms.sessions import ny_session_mask, session_reference_index


def registered_no_fill_quote_anchors(
    anchors_by_symbol: Mapping[str, Sequence[str]], symbol: str
) -> list[str]:
    """Return the literal-symbol allowlist without interpreting dots as config paths.

    Args:
        anchors_by_symbol: Registered unavailable quote timestamps grouped by
            exact symbol name.
        symbol: Exact symbol whose fail-closed no-fill anchors are requested.

    Returns:
        The registered timestamp strings for ``symbol``, or an empty list.
    """
    return list(anchors_by_symbol.get(symbol, ()))


def validate_registered_no_fill_anchors(
    unavailable_order_times_utc: list[str], approved_order_times_utc: list[str]
) -> None:
    """Require quote gaps to match the explicitly admitted fail-closed anchors.

    Args:
        unavailable_order_times_utc: Observed UTC order times without an
            executable quote inside the configured wait window.
        approved_order_times_utc: Registered UTC anchors explicitly accepted
            as fail-closed no-fills.
    """
    actual = sorted(
        pd.Timestamp(value).tz_convert("UTC").isoformat() for value in unavailable_order_times_utc
    )
    approved = sorted(
        pd.Timestamp(value).tz_convert("UTC").isoformat() for value in approved_order_times_utc
    )
    if actual != approved:
        unexpected = sorted(set(actual) - set(approved))
        missing = sorted(set(approved) - set(actual))
        raise ValueError(
            "tick quote gaps differ from registered fail-closed no-fill anchors; "
            f"unexpected={unexpected}, no_longer_missing={missing}"
        )


def tick_execution_split_schedule(
    index: pd.DatetimeIndex,
    train_mask: pd.Series,
    test_start: str,
    *,
    session_labels: pd.Series | None = None,
    session_timezone: str | None = None,
    source_clock_model: str = "native",
    session_start: str | None = None,
    session_end: str | None = None,
    scheduled_session_closes: dict[str, str] | None = None,
    include_report_only_split: bool = True,
) -> dict[str, dict[str, Any]]:
    """Return NY decision bars and scheduled next-minute quote anchors.

    ``TradingEnv`` submits the step's order one M1 interval after the decision
    bar, even if that M1 bar is missing. The anchor therefore stays on the
    scheduled minute; advancing it to the next observed bar would hide missing
    open-market data. Requiring coverage for every overnight M1 row is unrelated
    to this environment's execution schedule and can reject otherwise complete
    NY-session tick data.

    Args:
        index: Position or label identifying the requested item.
        train_mask: Boolean mask identifying rows available for fitting.
        test_start: Text or path value identifying the test start.
        session_labels: Tabular data used for the session labels.
        session_timezone: Exchange timezone for clock-based eligibility when labels are absent.
        source_clock_model: Interpretation of index wall times before exchange clock conversion.
        session_start: Optional inclusive NY session start in HH:MM when labels are absent.
        session_end: Optional inclusive NY session end in HH:MM when labels are absent.
        scheduled_session_closes: Optional source-clock close overrides keyed by local session date.
        include_report_only_split: Whether to produce a schedule for the report-only split.

    Returns:
        Split schedules with source positions, DST-aware decision/anchor times,
        and insertion positions for each scheduled quote anchor in the observed
        M1 index.
    """
    if session_labels is None:
        ny_mask = ny_session_mask(
            index,
            session_start,
            session_end,
            session_tz=session_timezone,
            source_clock_model=source_clock_model,
        ).to_numpy(dtype=bool)
    else:
        if not session_labels.index.equals(index):
            raise ValueError("session_labels index must match tick-preflight index")
        ny_mask = session_labels.astype(str).eq("ny").to_numpy(dtype=bool)

    train_mask_values = np.asarray(train_mask.to_numpy(), dtype=bool)
    if len(train_mask_values) != len(index) or not train_mask.index.equals(index):
        raise ValueError("train_mask index must match tick-preflight index")
    instant_index = session_reference_index(index, source_clock_model)
    if instant_index.tz is None:
        raise ValueError("tick preflight requires timezone-aware source timestamps")
    if not instant_index.is_monotonic_increasing:
        raise ValueError(
            "tick preflight source timestamps must be monotonic after clock conversion"
        )
    eligible = train_mask_values & ny_mask
    if scheduled_session_closes:
        source_tz = "Europe/Helsinki" if source_clock_model == "europe_helsinki" else str(index.tz)
        local = instant_index.tz_convert(source_tz)
        scheduled = np.zeros(len(index), dtype=bool)
        for pos in np.flatnonzero(eligible):
            session_date = local[pos].strftime("%Y-%m-%d")
            close = scheduled_session_closes.get(session_date)
            if close is None:
                scheduled[pos] = True
                continue
            close_wall = pd.Timestamp(f"{session_date} {close}")
            close_instant = close_wall.tz_localize(
                source_tz, ambiguous="raise", nonexistent="raise"
            )
            scheduled[pos] = instant_index[pos] + pd.Timedelta(minutes=1) < close_instant
        eligible &= scheduled
    train_positions = np.flatnonzero(eligible)
    instant_values = instant_index.to_numpy(dtype="datetime64[ns]").astype(np.int64)
    train_decisions = instant_index[train_positions]
    train_anchors = train_decisions + pd.Timedelta(minutes=1)
    schedule = {
        "train": {
            "decision_positions": train_positions,
            "decision_times": train_decisions,
            "quote_anchor_positions": np.searchsorted(
                instant_values,
                train_anchors.to_numpy(dtype="datetime64[ns]").astype(np.int64),
                side="left",
            ),
            "quote_anchor_times": train_anchors,
        },
    }
    if include_report_only_split:
        test_start_ts = pd.Timestamp(test_start)
        if index.tz is not None:
            if test_start_ts.tzinfo is None:
                test_start_ts = test_start_ts.tz_localize(index.tz)
            else:
                test_start_ts = test_start_ts.tz_convert(index.tz)
        test_positions = np.flatnonzero((index >= test_start_ts) & ny_mask)
        test_decisions = instant_index[test_positions]
        test_anchors = test_decisions + pd.Timedelta(minutes=1)
        schedule["test"] = {
            "decision_positions": test_positions,
            "decision_times": test_decisions,
            "quote_anchor_positions": np.searchsorted(
                instant_values,
                test_anchors.to_numpy(dtype="datetime64[ns]").astype(np.int64),
                side="left",
            ),
            "quote_anchor_times": test_anchors,
        }
    return schedule


def tick_execution_split_coverage(
    tickbook: TickBook | None,
    index: pd.DatetimeIndex,
    train_mask: pd.Series,
    test_start: str,
    *,
    session_labels: pd.Series | None = None,
    session_timezone: str | None = None,
    source_clock_model: str = "native",
    session_start: str | None = None,
    session_end: str | None = None,
    scheduled_session_closes: dict[str, str] | None = None,
    max_latency_ns_exclusive: int,
    max_quote_wait_ms: int,
    include_report_only_split: bool = True,
) -> dict[str, dict[str, Any]]:
    """Preflight tick quotes at timestamps used by NY environment steps.

    Args:
        tickbook: Tickbook used by the operation described above.
        index: Position or label identifying the requested item.
        train_mask: Boolean mask identifying rows available for fitting.
        test_start: Text or path value identifying the test start.
        session_labels: Tabular data used for the session labels.
        session_timezone: Exchange timezone for clock-based eligibility when labels are absent.
        source_clock_model: Interpretation of index wall times before exchange clock conversion.
        session_start: Optional inclusive NY session start in HH:MM when labels are absent.
        session_end: Optional inclusive NY session end in HH:MM when labels are absent.
        scheduled_session_closes: Optional source-clock close overrides keyed by local session date.
        max_latency_ns_exclusive: Numeric value used for the max latency ns exclusive.
        max_quote_wait_ms: Numeric value used for the max quote wait ms.
        include_report_only_split: Whether to check coverage for the report-only split.

    Returns:
        Mapping from ``str`` keys to ``dict[str, Any]`` values.
    """
    schedule = tick_execution_split_schedule(
        index,
        train_mask,
        test_start,
        session_labels=session_labels,
        session_timezone=session_timezone,
        source_clock_model=source_clock_model,
        session_start=session_start,
        session_end=session_end,
        scheduled_session_closes=scheduled_session_closes,
        include_report_only_split=include_report_only_split,
    )
    options = {
        "max_latency_ns_exclusive": max_latency_ns_exclusive,
        "max_quote_wait_ms": max_quote_wait_ms,
    }
    return {
        split: tick_execution_coverage(tickbook, rows["quote_anchor_times"], **options)
        for split, rows in schedule.items()
    }
