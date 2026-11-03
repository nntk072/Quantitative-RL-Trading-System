"""Reusable raw tick quote and M1 timeline scanners for market data analysis."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def scan_tick_file(path: Path, expected_sha256: str) -> dict[str, Any]:
    columns = ["<DATE>", "<TIME>", "<BID>", "<ASK>"]
    rows = invalid_time = nonfinite = nonpositive = crossed = locked = 0
    order_breaks = duplicate_rows = 0
    min_ns: int | None = None
    max_ns: int | None = None
    previous_ns: int | None = None
    bid_min = ask_min = float("inf")
    bid_max = ask_max = float("-inf")
    observed_m1_minutes: set[int] = set()

    for chunk in pd.read_csv(
        path,
        sep="\t",
        usecols=columns,
        dtype={column: "string" for column in columns},
        keep_default_na=True,
        chunksize=1_000_000,
        engine="c",
    ):
        rows += len(chunk)
        timestamps = pd.to_datetime(
            chunk["<DATE>"].astype(str).to_numpy() + " " + chunk["<TIME>"].astype(str).to_numpy(),
            format="%Y.%m.%d %H:%M:%S.%f",
            errors="coerce",
        )
        invalid_time += int(timestamps.isna().sum())
        bid = pd.to_numeric(chunk["<BID>"], errors="coerce").to_numpy(dtype=np.float64)
        ask = pd.to_numeric(chunk["<ASK>"], errors="coerce").to_numpy(dtype=np.float64)
        finite = np.isfinite(bid) & np.isfinite(ask)
        nonfinite += int((~finite).sum())
        nonpositive += int(((bid <= 0.0) | (ask <= 0.0)).sum())
        crossed += int(((ask < bid) & finite).sum())
        locked += int(((ask == bid) & finite).sum())

        valid_timestamp = ~timestamps.isna()
        usable_quote = finite & (bid > 0.0) & (ask >= bid)
        valid_quote_rows = np.asarray(valid_timestamp, dtype=bool) & usable_quote
        if valid_quote_rows.any():
            current = timestamps[valid_quote_rows].to_numpy(dtype="datetime64[ns]").astype(np.int64)
            observed_m1_minutes.update((current // 60_000_000_000).tolist())
        valid = valid_timestamp
        if valid.any():
            current = timestamps[valid].to_numpy(dtype="datetime64[ns]").astype(np.int64)
            if previous_ns is not None:
                order_breaks += int(current[0] < previous_ns)
                duplicate_rows += int(current[0] == previous_ns)
            if current.size > 1:
                delta = np.diff(current)
                order_breaks += int((delta < 0).sum())
                duplicate_rows += int((delta == 0).sum())
            previous_ns = int(current[-1])
            lower, upper = int(current.min()), int(current.max())
            min_ns = lower if min_ns is None else min(min_ns, lower)
            max_ns = upper if max_ns is None else max(max_ns, upper)

        if finite.any():
            bid_min = min(bid_min, float(bid[finite].min()))
            bid_max = max(bid_max, float(bid[finite].max()))
            ask_min = min(ask_min, float(ask[finite].min()))
            ask_max = max(ask_max, float(ask[finite].max()))

    actual_sha256 = sha256_file(path)
    return {
        "path": str(path),
        "bytes": path.stat().st_size,
        "mtime_ns": path.stat().st_mtime_ns,
        "rows": rows,
        "invalid_timestamp_rows": invalid_time,
        "nonfinite_bid_ask_rows": nonfinite,
        "nonpositive_bid_ask_rows": nonpositive,
        "crossed_quote_rows_ask_below_bid": crossed,
        "locked_quote_rows_ask_equals_bid": locked,
        "raw_order_breaks": order_breaks,
        "adjacent_duplicate_timestamp_rows": duplicate_rows,
        "min_timestamp_naive": None if min_ns is None else str(pd.Timestamp(min_ns)),
        "max_timestamp_naive": None if max_ns is None else str(pd.Timestamp(max_ns)),
        "bid_min": None if bid_min == float("inf") else bid_min,
        "bid_max": None if bid_max == float("-inf") else bid_max,
        "ask_min": None if ask_min == float("inf") else ask_min,
        "ask_max": None if ask_max == float("-inf") else ask_max,
        "sha256": actual_sha256,
        "experiment_run_expected_sha256": expected_sha256,
        "experiment_run_hash_match": actual_sha256 == expected_sha256,
        "_observed_m1_minutes": observed_m1_minutes,
    }


def load_m1_minutes(path: Path) -> set[int]:
    """Read M1 bar-start minutes as epoch-minute integers, with bounded memory."""
    result: set[int] = set()
    for chunk in pd.read_csv(
        path,
        sep="\t",
        usecols=["<DATE>", "<TIME>"],
        dtype={"<DATE>": "string", "<TIME>": "string"},
        chunksize=500_000,
        engine="c",
    ):
        timestamps = pd.to_datetime(
            chunk["<DATE>"].astype(str).to_numpy() + " " + chunk["<TIME>"].astype(str).to_numpy(),
            format="%Y.%m.%d %H:%M:%S",
            errors="coerce",
        )
        valid = ~timestamps.isna()
        if valid.any():
            current = timestamps[valid].to_numpy(dtype="datetime64[ns]").astype(np.int64)
            result.update((current // 60_000_000_000).tolist())
    return result
