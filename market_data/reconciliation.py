"""Row-wise reconciliation of MT5 export rows to normalized bars, and Parquet round trips (DATA-SCHEMAS).

Every source row must end up in exactly one of two places: the converted bar table (matched by
``source_sequence``) or the quarantine list with a reason. The UTC instant and the DST class of
each source row are re-derived here with :mod:`zoneinfo` and fold semantics, independently of the
pandas path in :func:`market_data.arrow_schemas.mt5_export_to_bars`, so the two implementations
cross-check each other.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]

from market_data.arrow_schemas import SOURCE_CLOCK, RowProblem

_UTC_NS = pa.timestamp("ns", tz="UTC")

QUARANTINE_SCHEMA = pa.schema(
    [
        pa.field("source_row_index", pa.int64(), nullable=False),
        pa.field("source_date", pa.string(), nullable=False),
        pa.field("source_time", pa.string(), nullable=False),
        pa.field("reason", pa.string(), nullable=False),
        pa.field("action", pa.string(), nullable=False),
    ]
)

_DST_REASONS = {
    "nonexistent": "nonexistent local time (DST spring-forward)",
    "ambiguous": "ambiguous local time (DST fall-back)",
}


@dataclass(frozen=True, slots=True)
class OracleInstant:
    """Independent classification of one Helsinki wall-clock label."""

    utc: datetime | None
    dst_class: str  # "ok", "nonexistent" or "ambiguous"


def independent_utc_open(date_label: str, time_label: str) -> OracleInstant:
    """Map a source wall-clock label to its UTC instant using zoneinfo fold semantics.

    Args:
        date_label: Export date such as ``2025.03.30``.
        time_label: Export time such as ``03:30:00``.

    Returns:
        The UTC instant for an unambiguous label, or ``None`` with the DST class when the local
        time does not exist or repeats.
    """
    naive = datetime.strptime(f"{date_label} {time_label}", "%Y.%m.%d %H:%M:%S")  # noqa: DTZ007
    zone = ZoneInfo(SOURCE_CLOCK)

    def _round_trips(fold: int) -> bool:
        """Check whether a local label survives a UTC round trip under one fold.

        Args:
            fold: zoneinfo fold value (0 or 1) selecting the earlier or later instant.

        Returns:
            True when converting to UTC and back reproduces the same wall-clock label.
        """
        local = naive.replace(tzinfo=zone, fold=fold)
        back = local.astimezone(ZoneInfo("UTC")).astimezone(zone).replace(tzinfo=None)
        return back == naive

    early = naive.replace(tzinfo=zone, fold=0)
    late = naive.replace(tzinfo=zone, fold=1)
    if not _round_trips(0) and not _round_trips(1):
        return OracleInstant(None, "nonexistent")
    if early.utcoffset() != late.utcoffset():
        return OracleInstant(None, "ambiguous")
    return OracleInstant(early.astimezone(ZoneInfo("UTC")), "ok")


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    """Counts and mismatches from reconciling one export frame with its bar table."""

    source_rows: int
    converted_rows: int
    quarantined_rows: int
    unexplained_rows: int
    event_time_mismatches: int
    value_mismatches: int
    dst_class_mismatches: int

    @property
    def reconciles(self) -> bool:
        """Check whether the reconciliation is complete and free of disagreements.

        Returns:
            True when every source row is accounted for and no check disagrees.
        """
        return (
            self.converted_rows + self.quarantined_rows == self.source_rows
            and self.unexplained_rows == 0
            and self.event_time_mismatches == 0
            and self.value_mismatches == 0
            and self.dst_class_mismatches == 0
        )


def reconcile_export_to_bars(
    frame: pd.DataFrame, table: pa.Table, problems: list[RowProblem]
) -> ReconciliationResult:
    """Reconcile a source export frame with the bar table produced from it.

    Args:
        frame: The export frame passed to ``mt5_export_to_bars`` (string columns, file order).
        table: Converted bar table with ``source_sequence`` giving the source row index.
        problems: Problems returned with the table; ``RowProblem.row`` indexes ``frame``.

    Returns:
        Reconciliation counts. ``reconciles`` is True only when every row is explained and every
        converted row matches the independent oracle exactly.
    """
    problem_reason: dict[int, str] = {}
    for problem in problems:
        problem_reason.setdefault(problem.row, problem.reason)
    kept = dict(
        zip(table.column("source_sequence").to_pylist(), range(table.num_rows), strict=True)
    )
    event_ns = table.column("event_time").cast(pa.int64()).to_pylist()
    columns = {
        "open": ("OPEN", table.column("open").to_pylist()),
        "high": ("HIGH", table.column("high").to_pylist()),
        "low": ("LOW", table.column("low").to_pylist()),
        "close": ("CLOSE", table.column("close").to_pylist()),
        "volume": ("TICKVOL", table.column("volume").to_pylist()),
    }
    dates = frame["DATE"].astype(str).tolist()
    times = frame["TIME"].astype(str).tolist()
    source_text = {name: frame[src].astype(str).tolist() for name, (src, _) in columns.items()}

    event_mismatch = value_mismatch = dst_mismatch = unexplained = 0
    for index in range(len(frame)):
        oracle = independent_utc_open(dates[index], times[index])
        if index in kept:
            if oracle.utc is None:
                dst_mismatch += 1
                continue
            position = kept[index]
            if event_ns[position] != int(pd.Timestamp(oracle.utc).value):
                event_mismatch += 1
            if any(
                float(columns[name][1][position]) != float(source_text[name][index])
                for name in columns
            ):
                value_mismatch += 1
        elif index in problem_reason:
            expected = _DST_REASONS.get(oracle.dst_class)
            if expected is None:
                # Quarantined for an OHLC/volume rule: the label itself must map to one instant.
                if oracle.utc is None:
                    dst_mismatch += 1
            elif problem_reason[index] != expected:
                dst_mismatch += 1
        else:
            unexplained += 1
    return ReconciliationResult(
        source_rows=len(frame),
        converted_rows=table.num_rows,
        quarantined_rows=len(problem_reason),
        unexplained_rows=unexplained,
        event_time_mismatches=event_mismatch,
        value_mismatches=value_mismatch,
        dst_class_mismatches=dst_mismatch,
    )


def quarantine_table(
    frame: pd.DataFrame, problems: list[RowProblem], kept_rows: set[int]
) -> pa.Table:
    """Return the persisted quarantine record for a conversion.

    Args:
        frame: The export frame that was converted.
        problems: Problems returned with the table.
        kept_rows: Source row indices that remain in the bar table.

    Returns:
        A table with QUARANTINE_SCHEMA; one row per problem, with the action taken.
    """
    rows = [
        {
            "source_row_index": p.row,
            "source_date": str(frame["DATE"].iloc[p.row]),
            "source_time": str(frame["TIME"].iloc[p.row]),
            "reason": p.reason,
            "action": "retained_flagged" if p.row in kept_rows else "excluded_from_table",
        }
        for p in problems
    ]
    return pa.Table.from_pylist(rows, schema=QUARANTINE_SCHEMA)


@dataclass(frozen=True, slots=True)
class RoundTripResult:
    """Outcome of writing a table to Parquet and reading it back."""

    rows: int
    schema_equal: bool
    values_equal: bool


def parquet_round_trip(table: pa.Table, path: Path) -> RoundTripResult:
    """Write a table to Parquet, read it back, and compare schema and every value.

    Args:
        table: Table to persist.
        path: Destination file; overwritten.

    Returns:
        Row count and whether the schema and all values survived unchanged.
    """
    pq.write_table(table, path)
    back = pq.read_table(path)
    return RoundTripResult(
        rows=back.num_rows,
        schema_equal=back.schema.equals(table.schema),
        values_equal=back.equals(table),
    )


__all__ = [
    "QUARANTINE_SCHEMA",
    "OracleInstant",
    "ReconciliationResult",
    "RoundTripResult",
    "independent_utc_open",
    "parquet_round_trip",
    "quarantine_table",
    "reconcile_export_to_bars",
]
