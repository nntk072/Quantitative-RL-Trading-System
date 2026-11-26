"""Explicit v1-to-v2 bar migration and the append-only correction policy (DATA-SCHEMAS).

``market-event.v1`` bars have no revision. ``market-event.v2`` bars add an integer ``revision``.
Migration is explicit: :func:`migrate_bars_v1_to_v2` reads only v1 and writes only v2, with revision 0
for every row. Any other id, including v2, is refused rather than guessed at.

Correction policy: a corrected bar is never an overwrite. :func:`append_correction` appends the
correction as a new row with the next revision for the same ``(instrument_id, event_time)``, and the
earlier rows stay in the table. :func:`latest_revision` selects the highest revision per key when a
consumer needs the current view. Source revisions and corrections therefore remain auditable.
"""

from __future__ import annotations

import numpy as np
import pyarrow as pa  # type: ignore[import-untyped]

from market_data.arrow_schemas import (
    BAR_REVISED_SCHEMA,
    BAR_REVISED_SCHEMA_ID,
    BAR_SCHEMA,
    SCHEMA_VERSION,
    RowProblem,
    require_schema_id,
    validate_bars,
)


def migrate_bars_v1_to_v2(table: pa.Table) -> pa.Table:
    """Convert a valid market-event.v1 bar table to market-event.v2 with revision 0 on every row.

    Args:
        table: Bar table with the BAR_SCHEMA columns and schema id ``market-event.v1``.

    Returns:
        A table with BAR_REVISED_SCHEMA. Prices, times and nulls are unchanged.

    Raises:
        ValueError: If the input is not exactly one v1 id, or it violates the v1 bar rules.
    """
    require_schema_id(table, accepted=frozenset({SCHEMA_VERSION}))
    problems = validate_bars(table.select(BAR_SCHEMA.names))
    if problems:
        raise ValueError(
            f"cannot migrate invalid v1 bars: {problems[0].reason} at row {problems[0].row}"
        )
    rows = table.num_rows
    columns: dict[str, pa.Array | pa.ChunkedArray] = {
        name: table.column(name) for name in BAR_SCHEMA.names if name != "schema_id"
    }
    columns["schema_id"] = pa.array([BAR_REVISED_SCHEMA_ID] * rows, type=pa.string())
    columns["revision"] = pa.array(np.zeros(rows, dtype=np.int64), type=pa.int64())
    return pa.table(columns, schema=BAR_REVISED_SCHEMA)


def _key(table: pa.Table) -> list[tuple[str, int]]:
    """Return the ``(instrument_id, event_time)`` key of every row, with event_time in nanoseconds.

    Args:
        table: Table with ``instrument_id`` and ``event_time`` columns.

    Returns:
        One key per row, in row order.
    """
    instrument = table.column("instrument_id").to_pylist()
    event = table.column("event_time").cast(pa.int64()).to_pylist()
    return list(zip(instrument, event, strict=True))


def validate_revised_bars(table: pa.Table) -> list[RowProblem]:
    """Return rule violations for a market-event.v2 bar table.

    Each row must have a non-negative revision. No ``(instrument_id, event_time, revision)`` may repeat.
    Each row must satisfy the v1 bar rules on its own; several revisions of one bar are allowed.

    Args:
        table: Table with the BAR_REVISED_SCHEMA columns.

    Returns:
        Every violation with its row index and reason; an empty list when the table is valid.

    Raises:
        ValueError: If the table is not exactly one market-event.v2 id.
    """
    require_schema_id(table, accepted=frozenset({BAR_REVISED_SCHEMA_ID}))
    problems: list[RowProblem] = []
    revisions = table.column("revision").to_pylist()
    keys = _key(table)
    seen: dict[tuple[str, int, int], int] = {}
    repeated: set[tuple[str, int, int]] = set()
    for i, (key, revision) in enumerate(zip(keys, revisions, strict=True)):
        if revision < 0:
            problems.append(RowProblem(i, "revision must be non-negative"))
        full_key = (key[0], key[1], revision)
        if full_key in seen:
            repeated.add(full_key)
        seen.setdefault(full_key, i)
    for i, (key, revision) in enumerate(zip(keys, revisions, strict=True)):
        if (key[0], key[1], revision) in repeated:
            problems.append(RowProblem(i, "duplicate (instrument, event_time, revision)"))
    for i in range(table.num_rows):
        for problem in validate_bars(table.slice(i, 1).select(BAR_SCHEMA.names)):
            if problem.reason.startswith("duplicate bar open time"):
                continue
            problems.append(RowProblem(i, problem.reason))
    return sorted(problems, key=lambda p: p.row)


def _rows(table: pa.Table) -> list[dict[str, object]]:
    """Return the table as a list of row dictionaries.

    Args:
        table: Table to convert.

    Returns:
        One dictionary per row, keyed by column name.
    """
    rows: list[dict[str, object]] = table.to_pylist()
    return rows


def append_correction(history: pa.Table, correction: pa.Table) -> pa.Table:
    """Append corrected bars as new revisions, keeping every earlier row.

    Each correction row receives the next revision for its ``(instrument_id, event_time)``: one more
    than the highest revision already present, or 0 for a new bar. Any ``revision`` value in the
    correction table is ignored and recomputed. Both tables must be market-event.v2.

    Args:
        history: Existing v2 bar table, possibly with several revisions per bar.
        correction: Corrected bars in the v2 layout; their ``revision`` column is replaced.

    Returns:
        The history rows, unchanged, followed by the appended correction rows.

    Raises:
        ValueError: If either table is not v2, or the result violates the v2 rules.
    """
    require_schema_id(history, accepted=frozenset({BAR_REVISED_SCHEMA_ID}))
    require_schema_id(correction, accepted=frozenset({BAR_REVISED_SCHEMA_ID}))
    next_revision: dict[tuple[str, int], int] = {}
    for key, revision in zip(_key(history), history.column("revision").to_pylist(), strict=True):
        next_revision[key] = max(next_revision.get(key, -1), int(revision))
    appended: list[dict[str, object]] = []
    for key, row in zip(_key(correction), _rows(correction), strict=True):
        revision = next_revision.get(key, -1) + 1
        next_revision[key] = revision
        appended.append({**row, "revision": revision})
    merged = pa.Table.from_pylist(_rows(history) + appended, schema=BAR_REVISED_SCHEMA)
    problems = validate_revised_bars(merged)
    if problems:
        raise ValueError(
            f"correction produced invalid bars: {problems[0].reason} at row {problems[0].row}"
        )
    return merged


def latest_revision(table: pa.Table) -> pa.Table:
    """Return one row per bar: the highest revision for each ``(instrument_id, event_time)``.

    Args:
        table: Existing v2 bar table.

    Returns:
        The current view, in order of first appearance of each bar.

    Raises:
        ValueError: If the table is not v2.
    """
    require_schema_id(table, accepted=frozenset({BAR_REVISED_SCHEMA_ID}))
    best: dict[tuple[str, int], int] = {}
    revisions = [int(r) for r in table.column("revision").to_pylist()]
    for i, key in enumerate(_key(table)):
        if key not in best or revisions[i] > revisions[best[key]]:
            best[key] = i
    return table.take(sorted(best.values()))
