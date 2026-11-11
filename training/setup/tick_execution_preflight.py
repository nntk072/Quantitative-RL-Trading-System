"""Tick-quote coverage checks aligned to the environment's execution schedule."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from market_data.loading.ticks import TickBook, tick_execution_coverage
from market_data.transforms.sessions import ny_session_mask


def tick_execution_split_schedule(
    index: pd.DatetimeIndex,
    train_mask: pd.Series,
    test_start: str,
    *,
    session_labels: pd.Series | None = None,
    include_report_only_split: bool = True,
) -> dict[str, dict[str, Any]]:
    """Return NY decision bars and next-bar quote anchors for each split.

    ``TradingEnv`` advances through NY-eligible bars and resolves each step's
    execution/valuation quote at the following market bar. Requiring coverage
    for every overnight M1 row is unrelated to this environment's execution
    schedule and can reject otherwise complete NY-session tick data. Returned
    timestamps describe observed bars; they do not define provider publication
    expectations.

    Args:
        index: Position or label identifying the requested item.
        train_mask: Boolean mask identifying rows available for fitting.
        test_start: Text or path value identifying the test start.
        session_labels: Tabular data used for the session labels.
        include_report_only_split: Whether to produce a schedule for the report-only split.

    Returns:
        Mapping from ``str`` keys to ``dict[str, Any]`` values.
    """
    if session_labels is None:
        ny_mask = ny_session_mask(index).to_numpy(dtype=bool)
    else:
        if not session_labels.index.equals(index):
            raise ValueError("session_labels index must match tick-preflight index")
        ny_mask = session_labels.astype(str).eq("ny").to_numpy(dtype=bool)

    train_mask_values = np.asarray(train_mask.to_numpy(), dtype=bool)
    if len(train_mask_values) != len(index) or not train_mask.index.equals(index):
        raise ValueError("train_mask index must match tick-preflight index")
    next_market = np.minimum(np.arange(len(index), dtype=np.int64) + 1, len(index) - 1)
    train_positions = np.flatnonzero(train_mask_values & ny_mask)
    schedule = {
        "train": {
            "decision_positions": train_positions,
            "decision_times": index[train_positions],
            "quote_anchor_positions": next_market[train_positions],
            "quote_anchor_times": index[next_market[train_positions]],
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
        schedule["test"] = {
            "decision_positions": test_positions,
            "decision_times": index[test_positions],
            "quote_anchor_positions": next_market[test_positions],
            "quote_anchor_times": index[next_market[test_positions]],
        }
    return schedule


def tick_execution_split_coverage(
    tickbook: TickBook | None,
    index: pd.DatetimeIndex,
    train_mask: pd.Series,
    test_start: str,
    *,
    session_labels: pd.Series | None = None,
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
