"""Train / test date-based split for bars and features.

Prefer passing ``train_mask`` into ``build_features`` so rolling z-score is
fit-scoped (TI-4). Slicing after a fully causal build remains OK for indicators
with short windows; it is not a substitute for train-scoped normalisation under
walk-forward.
"""

from __future__ import annotations

from typing import Any, cast

import pandas as pd


def split_train_test(
    bars: pd.DataFrame,
    features: pd.DataFrame,
    train_end: str = "2025-12-31",
    test_start: str = "2026-01-01",
    train_start: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Split aligned bars + features into train (≤ *train_end*) and test (≥ *test_start*).

    Args:
        bars: Market bars indexed by timestamp.
        features: Feature rows aligned to the market bars' index.
        train_end: Last date included in the training set (inclusive, full day).
        test_start: First date included in the test set (inclusive, midnight).
        train_start: Optional first date exposed to the training environment. Earlier rows
            remain available for causal feature warmup but are not training rows.

    Returns:
        Tuple of ``train_bars``, ``test_bars``, ``train_features``, and
        ``test_features`` in that order.
    """
    # Align to common index first
    common = bars.index.intersection(features.index)
    b = bars.loc[common]
    f = features.loc[common]

    # Build timezone-aware boundary timestamps matching the index tz
    tz = cast(pd.DatetimeIndex, b.index).tz

    train_end_ts = pd.Timestamp(train_end)
    test_start_ts = pd.Timestamp(test_start)

    if tz is not None:
        if train_end_ts.tzinfo is None:
            train_end_ts = train_end_ts.tz_localize(tz)
        else:
            train_end_ts = train_end_ts.tz_convert(tz)
        if test_start_ts.tzinfo is None:
            test_start_ts = test_start_ts.tz_localize(tz)
        else:
            test_start_ts = test_start_ts.tz_convert(tz)

    # Use the next local calendar midnight as an exclusive boundary. Subtracting
    # one second omitted subsecond rows and adding a fixed 24 hours crossed the
    # wrong local date on daylight-saving transitions.
    train_end_exclusive = train_end_ts.normalize() + pd.DateOffset(days=1)

    train_mask = b.index < train_end_exclusive
    if train_start is not None:
        train_start_ts = pd.Timestamp(train_start)
        if tz is not None:
            if train_start_ts.tzinfo is None:
                train_start_ts = train_start_ts.tz_localize(tz)
            else:
                train_start_ts = train_start_ts.tz_convert(tz)
        train_mask &= b.index >= train_start_ts
    test_mask = b.index >= test_start_ts

    return b[train_mask], b[test_mask], f[train_mask], f[test_mask]


def split_bars(
    bars: pd.DataFrame,
    train_end: str = "2025-12-31",
    test_start: str = "2026-01-01",
    train_start: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split a single bar frame on the same date boundaries as ``split_train_test``.

    Args:
        bars: Market bars to process.
        train_end: Text or path value identifying the train end.
        test_start: Text or path value identifying the test start.
        train_start: Train start used by the operation described above.

    Returns:
        DataFrame returned by ``split_bars``.
    """
    train, test, _, _ = split_train_test(bars, bars, train_end, test_start, train_start)
    return train, test


def inclusive_date_exclusive_end(end_date: str, timezone: str | None) -> pd.Timestamp:
    """Return the next local midnight after an inclusive calendar date."""
    boundary = pd.Timestamp(end_date)
    if timezone is not None:
        if boundary.tzinfo is None:
            boundary = boundary.tz_localize(timezone)
        else:
            boundary = boundary.tz_convert(timezone)
    return boundary.normalize() + pd.DateOffset(days=1)


def get_split_config(cfg: Any) -> tuple[str, str]:
    """Extract *train_end* / *test_start* from config with fallback defaults.

    Args:
        cfg: Run configuration used by this operation.

    Returns:
        Values returned by ``get_split_config``, in the declared order.
    """
    try:
        train_end = str(cfg.data.split.train_end)
    except Exception:
        train_end = "2025-12-31"
    try:
        test_start = str(cfg.data.split.test_start)
    except Exception:
        test_start = "2026-01-01"
    return train_end, test_start


def get_train_start_config(cfg: Any) -> str | None:
    """Read the optional first train date without changing legacy split config.

    Args:
        cfg: Run configuration used by this operation.

    Returns:
        Result of read the optional first train date without changing legacy split config.
    """
    try:
        value = cfg.data.split.train_start
    except Exception:
        return None
    return str(value) if value is not None and str(value).strip() else None


def make_train_mask(
    index: pd.DatetimeIndex,
    train_end: str,
    train_start: str | None = None,
) -> pd.Series:
    """Boolean mask for the inclusive configured training date range.

    Args:
        index: Position or label identifying the requested item.
        train_end: Text or path value identifying the train end.
        train_start: Train start used by the operation described above.

    Returns:
        Result of boolean mask for the inclusive configured training date range.
    """
    tz = index.tz
    train_end_ts = pd.Timestamp(train_end)
    if tz is not None:
        if train_end_ts.tzinfo is None:
            train_end_ts = train_end_ts.tz_localize(tz)
        else:
            train_end_ts = train_end_ts.tz_convert(tz)
    # Match split_train_test: include the whole local calendar date without
    # imposing a one-second precision limit or assuming every date is 24 hours.
    train_end_exclusive = train_end_ts.normalize() + pd.DateOffset(days=1)
    mask = index < train_end_exclusive
    if train_start is not None:
        train_start_ts = pd.Timestamp(train_start)
        if tz is not None:
            if train_start_ts.tzinfo is None:
                train_start_ts = train_start_ts.tz_localize(tz)
            else:
                train_start_ts = train_start_ts.tz_convert(tz)
        mask &= index >= train_start_ts
    return pd.Series(mask, index=index)
