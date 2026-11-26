"""Tick/quote export to normalized quotes, reconciled row by row over a pre-cutoff window (DATA-SCHEMAS).

The MT5 tick export has ``<DATE> <TIME>`` with milliseconds (Helsinki wall clock), ``<BID>``, ``<ASK>``,
``<LAST>``, ``<VOLUME>`` and ``<FLAGS>``. A one-sided tick has an empty BID or ASK; it is kept with an
explicit null, never a zero. A row is excluded (quarantined with a reason) when its local time does
not exist or repeats (DST), its FLAGS are empty, a numeric field is not a number, or the quote fails
:func:`market_data.arrow_schemas.validate_quotes` (for example a crossed quote).

Reconciliation covers every row of the window: each row lands exactly once in the quote table or in
the quarantine record, and each kept row's UTC instant is checked against an independent zoneinfo
oracle that works on whole seconds (fold semantics) plus the row's milliseconds.

Only rows dated before the cutoff are parsed. Later lines are counted by label in a byte scan and
never converted or checked.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa  # type: ignore[import-untyped]

from market_data.arrow_schemas import (
    QUOTE_SCHEMA,
    SCHEMA_VERSION,
    SOURCE_CLOCK,
    validate_quotes,
)
from market_data.reconciliation import QUARANTINE_SCHEMA, independent_utc_open

INSTRUMENT_ID = "US100.cash"
TICK_SOURCE_ID = "mt5-tick"
_DST_REASON = {
    "nonexistent": "nonexistent local time (DST spring-forward)",
    "ambiguous": "ambiguous local time (DST fall-back)",
}
_UTC_NS = pa.timestamp("ns", tz="UTC")


@dataclass(frozen=True, slots=True)
class TickScan:
    """Line accounting of a tick export, from one byte pass over the file.

    Attributes:
        header: Header line without its terminator.
        sha256: Digest of the full file bytes.
        bytes: File size in bytes.
        body_lines: Non-empty data lines in the file.
        pre_lines: Data lines dated before the cutoff (parsed).
        post_lines: Data lines dated on or after the cutoff (counted only).
        first_label: First in-window DATE label, or None when the window is empty.
        last_label: Last in-window DATE label, or None when the window is empty.
    """

    header: str
    sha256: str
    bytes: int
    body_lines: int
    pre_lines: int
    post_lines: int
    first_label: str | None
    last_label: str | None


def scan_tick_window(path: Path, window_before: str) -> TickScan:
    """Count and hash a tick export without parsing any values.

    Args:
        path: Tick export file (tab-separated, CRLF or LF).
        window_before: ``YYYY.MM.DD`` cutoff, exclusive.

    Returns:
        Line counts for the window, the digest of the whole file, and the in-window label range.

    Raises:
        RuntimeError: If an in-window row follows an out-of-window row.
    """
    cutoff = window_before.encode("ascii")
    digest = hashlib.sha256()
    pre = post = total = 0
    first: str | None = None
    last: str | None = None
    seen_post = False
    with path.open("rb") as handle:
        header = handle.readline()
        digest.update(header)
        for line in handle:
            digest.update(line)
            if not line.strip():
                continue
            total += 1
            label = line[:10]
            if label < cutoff:
                if seen_post:
                    raise RuntimeError(
                        "tick export is not chronological: in-window row after cutoff"
                    )
                pre += 1
                text = label.decode("ascii")
                first = text if first is None else first
                last = text
            else:
                post += 1
                seen_post = True
    return TickScan(
        header=header.decode("ascii").rstrip("\r\n"),
        sha256=digest.hexdigest(),
        bytes=path.stat().st_size,
        body_lines=total,
        pre_lines=pre,
        post_lines=post,
        first_label=first,
        last_label=last,
    )


def window_chunks(path: Path, pre_lines: int, chunk_rows: int) -> Iterator[pd.DataFrame]:
    """Yield the first ``pre_lines`` data rows as string frames, in chunks.

    Args:
        path: Tick export file.
        pre_lines: Number of in-window rows from :func:`scan_tick_window`.
        chunk_rows: Rows per chunk.

    Yields:
        Frames with stripped column names. Rows after the window are never read.
    """
    reader = pd.read_csv(path, sep="\t", dtype=str, chunksize=chunk_rows, nrows=pre_lines)
    for chunk in reader:
        yield chunk.rename(columns=lambda name: name.strip("<>"))


@dataclass(slots=True)
class ChunkResult:
    """Outcome of one chunk: the kept table, quarantine rows and reconciliation counts."""

    table: pa.Table
    quarantine: pa.Table
    rows: int
    kept: int
    excluded_by_reason: dict[str, int] = field(default_factory=dict)
    first_event_ns: int | None = None
    last_event_ns: int | None = None
    inversions: int = 0
    gaps_over_hour: int = 0
    max_gap_seconds: float = 0.0
    oracle_event_mismatches: int = 0
    oracle_dst_mismatches: int = 0
    value_mismatches: int = 0
    unexplained_rows: int = 0


def _numeric(raw: pd.Series, name: str, problems: dict[int, str]) -> np.ndarray[Any, Any]:
    """Parse a numeric column; empty stays null, non-numeric text is recorded as a problem.

    Args:
        raw: String column as read from the export.
        name: Field name used in problem reasons.
        problems: Row index to reason mapping, updated in place for non-numeric text.

    Returns:
        Float array with NaN where the source is empty or non-numeric.
    """
    values = pd.to_numeric(raw, errors="coerce").to_numpy(dtype=np.float64)
    text = raw.fillna("").to_numpy()
    empty = np.array([s.strip() == "" for s in text])
    bad = ~empty & np.isnan(values)
    for i in np.flatnonzero(bad):
        problems.setdefault(int(i), f"{name} is not a number")
    return values


def convert_chunk(
    frame: pd.DataFrame, first_sequence: int, prev_event_ns: int | None
) -> ChunkResult:
    """Convert one chunk of tick rows and reconcile every row against the oracle.

    Args:
        frame: String frame from :func:`window_chunks`.
        first_sequence: Window index of the chunk's first row (the source_sequence base).
        prev_event_ns: Event time of the last row of the previous chunk, for chronology checks.

    Returns:
        Kept quote table, quarantine table and reconciliation counts for the chunk.
    """
    rows = len(frame)
    reasons: dict[int, str] = {}

    local = pd.to_datetime(frame["DATE"] + " " + frame["TIME"], format="%Y.%m.%d %H:%M:%S.%f")
    strict = local.dt.tz_localize(SOURCE_CLOCK, ambiguous="NaT", nonexistent="NaT")
    lenient = local.dt.tz_localize(SOURCE_CLOCK, ambiguous=True, nonexistent="NaT")
    dst_class = np.where(
        strict.isna().to_numpy(),
        np.where(lenient.isna().to_numpy(), "nonexistent", "ambiguous"),
        "ok",
    )
    for i in np.flatnonzero(dst_class != "ok"):
        reasons[int(i)] = _DST_REASON[str(dst_class[i])]

    flags_raw = frame["FLAGS"].fillna("").to_numpy()
    for i in np.flatnonzero(np.array([s.strip() == "" for s in flags_raw])):
        reasons.setdefault(int(i), "source_flags missing")
    bid = _numeric(frame["BID"], "bid", reasons)
    ask = _numeric(frame["ASK"], "ask", reasons)
    flags = pd.to_numeric(frame["FLAGS"], errors="coerce").to_numpy(dtype=np.float64)

    utc_ns = np.zeros(rows, dtype=np.int64)
    ok_time = strict.notna().to_numpy()
    utc_ns[ok_time] = strict[ok_time].dt.tz_convert("UTC").astype("int64").to_numpy()

    candidate = np.array(
        [i for i in range(rows) if i not in reasons and ok_time[i]], dtype=np.int64
    )
    cand_table = pa.table(
        {
            "event_time": pa.array(utc_ns[candidate], type=pa.int64()).cast(_UTC_NS),
            "available_at": pa.array(utc_ns[candidate], type=pa.int64()).cast(_UTC_NS),
            "source_sequence": pa.array(first_sequence + candidate, type=pa.int64()),
            "instrument_id": pa.array([INSTRUMENT_ID] * len(candidate), type=pa.string()),
            "source_id": pa.array([TICK_SOURCE_ID] * len(candidate), type=pa.string()),
            "schema_id": pa.array([SCHEMA_VERSION] * len(candidate), type=pa.string()),
            "bid": pa.array(
                np.where(np.isnan(bid[candidate]), 0.0, bid[candidate]),
                mask=np.isnan(bid[candidate]),
                type=pa.float64(),
            ),
            "ask": pa.array(
                np.where(np.isnan(ask[candidate]), 0.0, ask[candidate]),
                mask=np.isnan(ask[candidate]),
                type=pa.float64(),
            ),
            "bid_size": pa.nulls(len(candidate), type=pa.float64()),
            "ask_size": pa.nulls(len(candidate), type=pa.float64()),
            "source_flags": pa.array(
                np.where(np.isnan(flags[candidate]), 0, flags[candidate]).astype(np.int32),
                type=pa.int32(),
            ),
        },
        schema=QUOTE_SCHEMA,
    )
    rule_problems = validate_quotes(cand_table)
    rule_rows = {int(candidate[p.row]): p.reason for p in rule_problems}
    for index, reason in rule_rows.items():
        reasons.setdefault(index, reason)

    excluded = np.zeros(rows, dtype=bool)
    for index in reasons:
        excluded[index] = True
    kept_mask = ~excluded & ok_time
    kept_idx = np.flatnonzero(kept_mask)
    table = pa.table(
        {
            "event_time": pa.array(utc_ns[kept_idx], type=pa.int64()).cast(_UTC_NS),
            "available_at": pa.array(utc_ns[kept_idx], type=pa.int64()).cast(_UTC_NS),
            "source_sequence": pa.array(first_sequence + kept_idx, type=pa.int64()),
            "instrument_id": pa.array([INSTRUMENT_ID] * len(kept_idx), type=pa.string()),
            "source_id": pa.array([TICK_SOURCE_ID] * len(kept_idx), type=pa.string()),
            "schema_id": pa.array([SCHEMA_VERSION] * len(kept_idx), type=pa.string()),
            "bid": pa.array(
                np.where(np.isnan(bid[kept_idx]), 0.0, bid[kept_idx]),
                mask=np.isnan(bid[kept_idx]),
                type=pa.float64(),
            ),
            "ask": pa.array(
                np.where(np.isnan(ask[kept_idx]), 0.0, ask[kept_idx]),
                mask=np.isnan(ask[kept_idx]),
                type=pa.float64(),
            ),
            "bid_size": pa.nulls(len(kept_idx), type=pa.float64()),
            "ask_size": pa.nulls(len(kept_idx), type=pa.float64()),
            "source_flags": pa.array(flags[kept_idx].astype(np.int32), type=pa.int32()),
        },
        schema=QUOTE_SCHEMA,
    )

    quarantine_rows = [
        {
            "source_row_index": first_sequence + index,
            "source_date": str(frame["DATE"].iloc[index]),
            "source_time": str(frame["TIME"].iloc[index]),
            "reason": reason,
            "action": "excluded_from_table",
        }
        for index, reason in sorted(reasons.items())
    ]
    quarantine = pa.Table.from_pylist(quarantine_rows, schema=QUARANTINE_SCHEMA)

    excluded_by_reason: dict[str, int] = {}
    for reason in reasons.values():
        excluded_by_reason[reason] = excluded_by_reason.get(reason, 0) + 1

    # Independent oracle: zoneinfo instants per distinct whole second, plus the row's milliseconds.
    seconds = (frame["DATE"] + " " + frame["TIME"].str[:8]).to_numpy()
    uniq, inverse = np.unique(seconds, return_inverse=True)
    sec_ns = np.zeros(len(uniq), dtype=np.int64)
    sec_class = np.zeros(len(uniq), dtype=np.int8)
    for k, key in enumerate(uniq):
        date_label, clock = str(key).split(" ")
        oracle = independent_utc_open(date_label, clock)
        if oracle.utc is None:
            sec_class[k] = 1 if oracle.dst_class == "nonexistent" else 2
        else:
            sec_ns[k] = int(pd.Timestamp(oracle.utc).value)
    millis = frame["TIME"].str[9:12].astype(np.int64).to_numpy() * 1_000_000
    oracle_ns = sec_ns[inverse] + millis
    oracle_class = sec_class[inverse]

    pandas_dst = dst_class != "ok"
    oracle_dst = oracle_class != 0
    dst_mismatch = 0
    for i in np.flatnonzero(pandas_dst | oracle_dst):
        pandas_says = str(dst_class[i])
        oracle_says = {0: "ok", 1: "nonexistent", 2: "ambiguous"}[int(oracle_class[i])]
        if pandas_says != oracle_says:
            dst_mismatch += 1
    table_event = table.column("event_time").cast(pa.int64()).to_numpy()
    event_mismatch = int(np.count_nonzero(table_event != oracle_ns[kept_idx]))
    value_mismatch = 0
    for name, source in (("bid", bid), ("ask", ask)):
        table_values = table.column(name).to_numpy(zero_copy_only=False)
        expected = source[kept_idx]
        same = (table_values == expected) | (np.isnan(table_values) & np.isnan(expected))
        value_mismatch += int(np.count_nonzero(~same))
    # A row that is neither kept nor excluded would have no explanation (for example a timestamp the
    # parser rejects without a reason). Such rows are counted, never dropped silently.
    unexplained = int(np.count_nonzero(~ok_time & ~excluded))
    kept_event = table_event
    chain = kept_event if prev_event_ns is None else np.concatenate([[prev_event_ns], kept_event])
    diffs = np.diff(chain) if len(chain) > 1 else np.array([], dtype=np.int64)
    inversions = int(np.count_nonzero(diffs < 0))
    gap_ns = diffs[diffs > 0]
    return ChunkResult(
        table=table,
        quarantine=quarantine,
        rows=rows,
        kept=len(kept_idx),
        excluded_by_reason=excluded_by_reason,
        first_event_ns=int(kept_event[0]) if len(kept_event) else None,
        last_event_ns=int(kept_event[-1]) if len(kept_event) else None,
        inversions=inversions,
        gaps_over_hour=int(np.count_nonzero(gap_ns > 3_600_000_000_000)),
        max_gap_seconds=float(gap_ns.max() / 1e9) if len(gap_ns) else 0.0,
        oracle_event_mismatches=event_mismatch,
        oracle_dst_mismatches=dst_mismatch,
        value_mismatches=value_mismatch,
        unexplained_rows=unexplained,
    )


def _round_trip_part(table: pa.Table, path: Path) -> dict[str, Any]:
    """Write one part, read it back with PyArrow and with Polars, and compare values to the table.

    Args:
        table: Table to persist.
        path: Destination Parquet file; overwritten.

    Returns:
        Row count, file digest, and whether each reader returned the same schema and values.
    """
    import polars as pl
    import pyarrow.parquet as pq  # type: ignore[import-untyped]

    pq.write_table(table, path)
    arrow_back = pq.read_table(path)
    arrow_equal = bool(arrow_back.schema.equals(table.schema) and arrow_back.equals(table))
    polars_frame = pl.read_parquet(path)
    polars_equal = bool(polars_frame.height == table.num_rows)
    if polars_equal and table.num_rows:
        polars_equal = bool(polars_frame.to_arrow().cast(table.schema).equals(table))
    return {
        "rows": table.num_rows,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "pyarrow_round_trip_equal": arrow_equal,
        "polars_round_trip_equal": polars_equal,
    }


def reconcile_tick_export(
    path: Path,
    window_before: str,
    out_dir: Path,
    *,
    chunk_rows: int = 2_000_000,
) -> dict[str, Any]:
    """Convert and reconcile the pre-cutoff rows of a tick export, writing Parquet parts.

    Args:
        path: Tick export file.
        window_before: ``YYYY.MM.DD`` cutoff, exclusive.
        out_dir: Directory for quotes and quarantine part files and ``manifest.json``.
        chunk_rows: Rows per chunk, and per Parquet part.

    Returns:
        A ledger dict with source identity, line accounting, reconciliation counts, quarantine
        counts by reason, chronology and gap statistics, and per-part round-trip results. It holds
        counts only: no prices or per-row values.

    Raises:
        RuntimeError: If the accounting identity fails, the export is not chronological, or the
            reconciliation does not hold.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    scan = scan_tick_window(path, window_before)
    totals: dict[str, Any] = {
        "rows": 0,
        "converted": 0,
        "quarantined": 0,
        "unexplained": 0,
        "oracle_event_mismatches": 0,
        "oracle_dst_mismatches": 0,
        "value_mismatches": 0,
        "inversions": 0,
        "gaps_over_hour": 0,
        "max_gap_seconds": 0.0,
        "quarantine_rows_written": 0,
    }
    reasons_total: dict[str, int] = {}
    parts: list[dict[str, Any]] = []
    prev_ns: int | None = None
    first_ns: int | None = None
    last_ns: int | None = None
    offset = 0
    for number, frame in enumerate(window_chunks(path, scan.pre_lines, chunk_rows)):
        result = convert_chunk(frame, offset, prev_ns)
        quote_part = _round_trip_part(result.table, out_dir / f"quotes_part_{number:04d}.parquet")
        quarantine_part = _round_trip_part(
            result.quarantine, out_dir / f"quarantine_part_{number:04d}.parquet"
        )
        parts.append({"part": number, "quotes": quote_part, "quarantine": quarantine_part})
        totals["rows"] += result.rows
        totals["converted"] += result.kept
        totals["quarantined"] += result.rows - result.kept - result.unexplained_rows
        totals["unexplained"] += result.unexplained_rows
        totals["oracle_event_mismatches"] += result.oracle_event_mismatches
        totals["oracle_dst_mismatches"] += result.oracle_dst_mismatches
        totals["value_mismatches"] += result.value_mismatches
        totals["inversions"] += result.inversions
        totals["quarantine_rows_written"] += quarantine_part["rows"]
        totals["gaps_over_hour"] += result.gaps_over_hour
        totals["max_gap_seconds"] = max(totals["max_gap_seconds"], result.max_gap_seconds)
        for reason, count in result.excluded_by_reason.items():
            reasons_total[reason] = reasons_total.get(reason, 0) + count
        if result.first_event_ns is not None and first_ns is None:
            first_ns = result.first_event_ns
        if result.last_event_ns is not None:
            last_ns = result.last_event_ns
            prev_ns = result.last_event_ns
        offset += result.rows

    if totals["rows"] != scan.pre_lines:
        raise RuntimeError(f"row accounting failed: converted {totals['rows']} of {scan.pre_lines}")
    if totals["converted"] + totals["quarantined"] + totals["unexplained"] != scan.pre_lines:
        raise RuntimeError("converted + quarantined + unexplained does not equal the window rows")
    round_trips_ok = all(
        part["quotes"]["pyarrow_round_trip_equal"]
        and part["quotes"]["polars_round_trip_equal"]
        and part["quarantine"]["pyarrow_round_trip_equal"]
        and part["quarantine"]["polars_round_trip_equal"]
        for part in parts
    )
    reconciles = bool(
        totals["unexplained"] == 0
        and totals["oracle_event_mismatches"] == 0
        and totals["oracle_dst_mismatches"] == 0
        and totals["value_mismatches"] == 0
        and totals["inversions"] == 0
        and totals["quarantine_rows_written"] == totals["quarantined"]
        and totals["converted"] + totals["quarantined"] == scan.pre_lines
    )

    def _utc(value: int | None) -> str | None:
        """Format a nanosecond instant as an ISO UTC string, or None.

        Args:
            value: Nanoseconds since the epoch, or None.

        Returns:
            The instant as ``YYYY-MM-DDTHH:MM:SS.ffffffZ``, or None when value is None.
        """
        if value is None:
            return None
        return pd.Timestamp(value, unit="ns", tz="UTC").strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    import polars as pl

    ledger: dict[str, Any] = {
        "ledger": "DATA-SCHEMAS tick/quote reconciliation",
        "scope": (
            "rows dated before the cutoff; rows on or after it were counted by label, not parsed; "
            "counts only; not scientific evidence"
        ),
        "schema_version": SCHEMA_VERSION,
        "window_before": window_before,
        "source": {
            "file": path.name,
            "sha256": scan.sha256,
            "bytes": scan.bytes,
            "header": scan.header,
            "body_lines_in_file": scan.body_lines,
            "lines_on_or_after_cutoff": scan.post_lines,
            "first_label": scan.first_label,
            "last_label": scan.last_label,
        },
        "conversion": {
            "instrument_id": INSTRUMENT_ID,
            "source_id": TICK_SOURCE_ID,
            "clock": SOURCE_CLOCK,
            "timestamp": "event_time from DATE+TIME with milliseconds; available_at equals event_time",
            "one_sided_quote": "empty BID or ASK kept as an explicit null",
            "chunk_rows": chunk_rows,
            "parts": len(parts),
        },
        "reconciliation": {
            "window_rows": scan.pre_lines,
            "converted_rows": totals["converted"],
            "quarantined_rows": totals["quarantined"],
            "unexplained_rows": totals["unexplained"],
            "oracle_event_mismatches": totals["oracle_event_mismatches"],
            "oracle_dst_mismatches": totals["oracle_dst_mismatches"],
            "value_mismatches": totals["value_mismatches"],
            "reconciles": reconciles,
        },
        "quarantine_by_reason": dict(sorted(reasons_total.items())),
        "chronology": {
            "inversions": totals["inversions"],
            "strictly_ordered": totals["inversions"] == 0,
            "first_event_time_utc": _utc(first_ns),
            "last_event_time_utc": _utc(last_ns),
            "gaps_over_one_hour": totals["gaps_over_hour"],
            "max_gap_seconds": totals["max_gap_seconds"],
            "scope_note": "chronology and gaps are checked across chunk boundaries; duplicate rows are not counted",
        },
        "parquet": {
            "round_trip_all_parts_equal": bool(round_trips_ok),
            "pyarrow_version": pa.__version__,
            "polars_version": str(pl.__version__),
            "parts": parts,
        },
    }
    (out_dir / "manifest.json").write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    if not reconciles:
        raise RuntimeError(f"tick reconciliation failed: {ledger['reconciliation']}")
    return ledger
