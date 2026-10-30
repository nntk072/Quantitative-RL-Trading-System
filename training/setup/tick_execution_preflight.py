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
) -> dict[str, dict[str, Any]]:
    """Return NY decision bars and next-bar quote anchors for each split.

    ``TradingEnv`` advances through NY-eligible bars and resolves each step's
    execution/valuation quote at the following market bar. Requiring coverage
    for every overnight M1 row is unrelated to this environment's execution
    schedule and can reject otherwise complete NY-session tick data. Returned
    timestamps describe observed bars; they do not define provider publication
    expectations.
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
    test_start_ts = pd.Timestamp(test_start)
    if index.tz is not None:
        if test_start_ts.tzinfo is None:
            test_start_ts = test_start_ts.tz_localize(index.tz)
        else:
            test_start_ts = test_start_ts.tz_convert(index.tz)

    next_market = np.minimum(np.arange(len(index), dtype=np.int64) + 1, len(index) - 1)
    train_positions = np.flatnonzero(train_mask_values & ny_mask)
    test_positions = np.flatnonzero((index >= test_start_ts) & ny_mask)
    return {
        "train": {
            "decision_positions": train_positions,
            "decision_times": index[train_positions],
            "quote_anchor_positions": next_market[train_positions],
            "quote_anchor_times": index[next_market[train_positions]],
        },
        "test": {
            "decision_positions": test_positions,
            "decision_times": index[test_positions],
            "quote_anchor_positions": next_market[test_positions],
            "quote_anchor_times": index[next_market[test_positions]],
        },
    }


def tick_execution_split_coverage(
    tickbook: TickBook | None,
    index: pd.DatetimeIndex,
    train_mask: pd.Series,
    test_start: str,
    *,
    session_labels: pd.Series | None = None,
    max_latency_ns_exclusive: int,
    max_quote_wait_ms: int,
) -> dict[str, dict[str, Any]]:
    """Preflight tick quotes at timestamps used by NY environment steps."""
    schedule = tick_execution_split_schedule(
        index, train_mask, test_start, session_labels=session_labels
    )
    options = {
        "max_latency_ns_exclusive": max_latency_ns_exclusive,
        "max_quote_wait_ms": max_quote_wait_ms,
    }
    return {
        split: tick_execution_coverage(tickbook, rows["quote_anchor_times"], **options)
        for split, rows in schedule.items()
    }
