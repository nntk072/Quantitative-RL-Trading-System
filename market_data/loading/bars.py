"""Load raw MT5 bar CSV files into DataFrames.

File format (tab-separated):
  <DATE>  <TIME>  <OPEN>  <HIGH>  <LOW>  <CLOSE>  <TICKVOL>  <VOL>  <SPREAD>

Date format: YYYY.MM.DD, time: HH:MM:SS
SPREAD is in price points.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path
from typing import cast

import numpy as np
import pandas as pd

_BAR_COLS = ["date", "time", "open", "high", "low", "close", "tickvol", "vol", "spread"]
_DAILY_BAR_COLS = ["date", "open", "high", "low", "close", "tickvol", "vol", "spread"]
_TICK_COLS = ["date", "time", "bid", "ask", "last", "volume", "flags"]
_OHLC_COLS = ["open", "high", "low", "close"]
log = logging.getLogger(__name__)


class UnorderedTickSourceError(ValueError):
    """Raised when a cutoff-bounded tick source is not chronological."""


def _bar_source_diagnostics(frame: pd.DataFrame) -> dict[str, int]:
    """Summarize source row-order and duplicate conflicts before sorting.

    Args:
        frame: Parsed bars in their original source order.

    Returns:
        Counts of inversions, duplicate rows, and conflicting timestamps.
    """
    index = cast(pd.DatetimeIndex, frame.index)
    duplicate_mask = index.duplicated(keep=False)
    duplicates = frame.loc[duplicate_mask]
    conflicting_duplicate_timestamps = int(
        duplicates.groupby(level=0, sort=False).nunique(dropna=False).gt(1).any(axis=1).sum()
    )
    return {
        "out_of_order_rows": int((index[1:] < index[:-1]).sum()),
        "duplicate_rows": int(index.duplicated(keep="first").sum()),
        "conflicting_duplicate_timestamps": conflicting_duplicate_timestamps,
    }


def _validate_bar_ohlc(frame: pd.DataFrame, path: Path) -> None:
    """Reject non-finite or internally impossible OHLC rows.

    Args:
        frame: Parsed bars whose OHLC values must be checked.
        path: Source path included in any validation error.
    """
    prices = frame[_OHLC_COLS].to_numpy(dtype=np.float64)
    invalid = ~np.isfinite(prices).all(axis=1)
    invalid |= prices[:, 1] < prices[:, 2]
    invalid |= prices[:, 0] < prices[:, 2]
    invalid |= prices[:, 0] > prices[:, 1]
    invalid |= prices[:, 3] < prices[:, 2]
    invalid |= prices[:, 3] > prices[:, 1]
    if invalid.any():
        timestamps = [str(value) for value in frame.index[invalid][:5]]
        raise ValueError(
            f"invalid OHLC rows in {path}: count={int(invalid.sum())}, timestamps={timestamps}"
        )


def load_bars(
    path: str | Path,
    start_inclusive: pd.Timestamp | None = None,
    end_exclusive: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Parse a raw MT5 bar CSV into a DataFrame with a UTC-aware DatetimeIndex.

    The returned index name is ``datetime`` and the timezone is left as read
    (naive) because the caller applies the broker timezone via the config.

    Args:
        path: Path to the input file or directory.
        start_inclusive: Optional inclusive timestamp bound in the source's local clock.
        end_exclusive: Optional exclusive timestamp bound in the source's local clock.

    Returns:
        DataFrame returned by ``load_bars``.
    """
    path = Path(path)
    with path.open(encoding="utf-8-sig") as stream:
        header = [
            value.strip().strip("<>").upper()
            for value in stream.readline().rstrip("\r\n").split("\t")
        ]
    intraday_header = [name.upper() for name in _BAR_COLS]
    daily_header = [name.upper() for name in _DAILY_BAR_COLS]
    if header == intraday_header:
        columns = _BAR_COLS
        has_time = True
    elif header == daily_header:
        columns = _DAILY_BAR_COLS
        has_time = False
    else:
        raise ValueError(f"unsupported bar CSV header in {path}: {header}")

    df = pd.read_csv(
        path,
        sep="\t",
        header=0,
        names=columns,
        dtype={
            "open": "float64",
            "high": "float64",
            "low": "float64",
            "close": "float64",
            "tickvol": "int64",
            "vol": "int64",
            "spread": "float64",
        },
        na_values=[""],
    )
    if not has_time:
        df["time"] = "00:00:00"
    df["datetime"] = pd.to_datetime(df["date"] + " " + df["time"], format="%Y.%m.%d %H:%M:%S")
    invalid_time = df["datetime"].isna()
    if invalid_time.any():
        raise ValueError(
            f"invalid bar timestamps in {path}: rows={df.index[invalid_time][:5].tolist()}"
        )
    df = df.drop(columns=["date", "time"])
    df = df.set_index("datetime")
    if start_inclusive is not None:
        if start_inclusive.tzinfo is not None:
            start_inclusive = start_inclusive.tz_localize(None)
        df = df.loc[df.index >= start_inclusive]
    if end_exclusive is not None:
        if end_exclusive.tzinfo is not None:
            end_exclusive = end_exclusive.tz_localize(None)
        df = df.loc[df.index < end_exclusive]
    spread = df["spread"].to_numpy(dtype=np.float64)
    invalid_spread = ~np.isfinite(spread) | (spread < 0.0)
    if invalid_spread.any():
        timestamps = [str(value) for value in df.index[invalid_spread][:5]]
        raise ValueError(
            f"invalid spread values in {path}: count={int(invalid_spread.sum())}, "
            f"timestamps={timestamps}"
        )
    diagnostics = _bar_source_diagnostics(df)
    df.attrs["source_diagnostics"] = diagnostics
    if any(diagnostics.values()):
        log.warning("bar source order/duplicate diagnostics for %s: %s", path, diagnostics)
    df = df.sort_index()
    _validate_bar_ohlc(df, path)
    return df


def load_ticks(path: str | Path) -> pd.DataFrame:
    """Parse a raw MT5 tick CSV (BID/ASK) into a DataFrame.

    Tick time includes milliseconds (``HH:MM:SS.fff``), unlike bar files.

    Warning:
        This function loads the full file into memory. MT5 tick exports can be
        several gigabytes, so use :func:`iter_ticks_chunks` for bounded
        streaming instead.

    Args:
        path: Path to the input file or directory.

    Returns:
        DataFrame returned by ``load_ticks``.
    """
    path = Path(path)
    df = pd.read_csv(
        path,
        sep="\t",
        header=0,
        names=_TICK_COLS,
        dtype={"bid": "float64", "ask": "float64", "last": "float64", "volume": "float64"},
        na_values=[""],
    )
    df["datetime"] = pd.to_datetime(df["date"] + " " + df["time"], format="%Y.%m.%d %H:%M:%S.%f")
    df = df.drop(columns=["date", "time"])
    df = df.set_index("datetime")
    df = df.sort_index()
    return df


def iter_ticks_chunks(
    path: str | Path,
    chunksize: int = 2_000_000,
    start_inclusive: pd.Timestamp | None = None,
    end_exclusive: pd.Timestamp | None = None,
) -> Iterator[pd.DataFrame]:
    """Stream a raw MT5 tick CSV in bounded-size chunks.

    Only the ``date``, ``time``, ``bid``, ``ask`` columns are parsed —
    ``last``/``volume``/``flags`` are skipped entirely via ``usecols`` — and
    ``bid``/``ask`` are read directly as ``float64``. This preserves the source
    quote precision used by executable stop and target comparisons. Chunking keeps peak memory
    to roughly one chunk's worth of data instead of the whole file, which
    matters for multi-GB MT5 tick exports (a naive full-file load can OOM a
    memory-constrained VM such as WSL2).

    Args:
        path: Path to the input file or directory.
        chunksize: Numeric value used for the chunksize.
        start_inclusive: Optional inclusive timestamp bound in the source's local clock.
        end_exclusive: Optional exclusive timestamp bound in the source's local clock.

    Yields:
        Raw ``DataFrame`` chunks with ``date``, ``time``, ``bid``, and ``ask``
        columns. Date and time remain strings so callers can carry forward-fill
        state across chunk boundaries while parsing timestamps.
    """
    path = Path(path)
    reader = pd.read_csv(
        path,
        sep="\t",
        header=0,
        names=_TICK_COLS,
        usecols=["date", "time", "bid", "ask"],
        dtype={"bid": "float64", "ask": "float64"},
        na_values=[""],
        chunksize=chunksize,
        engine="c",
    )
    source_end = end_exclusive
    source_start = start_inclusive
    if source_start is not None and source_start.tzinfo is not None:
        source_start = source_start.tz_localize(None)
    if source_end is not None and source_end.tzinfo is not None:
        source_end = source_end.tz_localize(None)
    previous_timestamp: pd.Timestamp | None = None
    for chunk in reader:
        if source_start is None and source_end is None:
            yield chunk
            continue
        timestamps = pd.to_datetime(
            chunk["date"].to_numpy() + " " + chunk["time"].to_numpy(),
            format="%Y.%m.%d %H:%M:%S.%f",
        )
        if not timestamps.is_monotonic_increasing or (
            previous_timestamp is not None and timestamps[0] < previous_timestamp
        ):
            raise UnorderedTickSourceError(
                "development-only tick input must be chronologically ordered"
            )
        previous_timestamp = cast(pd.Timestamp, timestamps[-1])
        reached_cutoff = False
        if source_end is not None:
            in_scope_count = int(timestamps.searchsorted(source_end, side="left"))
            reached_cutoff = in_scope_count < len(chunk)
            chunk = chunk.iloc[:in_scope_count]
            timestamps = timestamps[:in_scope_count]
        if source_start is not None and not chunk.empty:
            first_in_scope = int(timestamps.searchsorted(source_start, side="left"))
            chunk = chunk.iloc[first_in_scope:]
        if chunk.empty:
            if reached_cutoff:
                break
            continue
        yield chunk
        if reached_cutoff:
            break
