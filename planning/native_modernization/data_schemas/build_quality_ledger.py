"""Build the DATA-SCHEMAS quality ledger for an MT5 M1 export.

Default: the tracked example ``data/examples/US100.cash_M1_202412300105_202501020334.csv``, written to
``quality_ledger.json`` next to this file.

Pre-2026 window: ``--window-before 2026.01.01`` keeps only export rows whose DATE label is before the
cutoff. Rows on or after the cutoff are never parsed, converted or checked; they are only counted by
line, so reconciliation can show every source line is accounted for. The window is an owner-approved
offline input (BLOCKER_INVENTORY: DATA-SCHEMAS). The 2026 reporting interval is never used.

    .venv-x86/bin/python planning/native_modernization/data_schemas/build_quality_ledger.py
    .venv-x86/bin/python planning/native_modernization/data_schemas/build_quality_ledger.py \
        --source data/US100.cash_M1_202412300105_202610162349.csv --window-before 2026.01.01 \
        --out planning/native_modernization/data_schemas/quality_ledger_pre2026_m1.json \
        --parquet-dir logs/agents/data_scientist_engineer/2026-11-26_data_schemas
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from market_data.arrow_schemas import (  # noqa: E402
    BAR_SCHEMA,
    SCHEMA_VERSION,
    SOURCE_CLOCK,
    mt5_export_to_bars,
    require_schema_id,
)
from market_data.reconciliation import (  # noqa: E402
    parquet_round_trip,
    quarantine_table,
    reconcile_export_to_bars,
)

EXAMPLE_RELATIVE = "data/examples/US100.cash_M1_202412300105_202501020334.csv"
LEDGER = HERE / "quality_ledger.json"
GENERATOR_RELATIVE = "planning/native_modernization/data_schemas/build_quality_ledger.py"
INSTRUMENT_ID = "US100.cash"
TIMEFRAME = "M1"
SOURCE_ID = "mt5-export"
ONE_MINUTE = pd.Timedelta(minutes=1)


def _iso(value: pd.Timestamp) -> str:
    return pd.Timestamp(value).tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")


def _window_lines(raw: bytes, window_before: str | None) -> tuple[str, list[str], int, int]:
    """Split the export into the header, in-window body lines, and the count of lines after the cutoff.

    Raises:
        RuntimeError: If an in-window line follows an out-of-window line (the export is not
            chronological, so a prefix window is not well defined).
    """
    text_lines = [line for line in raw.decode("ascii").splitlines() if line.strip()]
    header, body = text_lines[0], text_lines[1:]
    if window_before is None:
        return header, body, 0, len(body)
    keep: list[str] = []
    after = 0
    for line in body:
        if line.split("\t", 1)[0] < window_before:
            if after:
                raise RuntimeError("export is not chronological: in-window row after cutoff")
            keep.append(line)
        else:
            after += 1
    return header, keep, after, len(body)


def build_ledger(
    source: Path, *, window_before: str | None = None, parquet_dir: Path | None = None
) -> dict[str, Any]:
    """Convert the export and return the quality ledger as a JSON-serializable dict.

    Args:
        source: MT5 M1 export (tab-separated, CRLF or LF).
        window_before: Optional ``YYYY.MM.DD`` cutoff; rows with DATE on or after it are excluded.
        parquet_dir: Optional directory for ``bars.parquet``, ``quarantine.parquet`` and
            ``manifest.json``. When None, the Parquet round trip runs in a temporary directory and
            only its outcome is recorded.

    Returns:
        The ledger dict. Raises RuntimeError when a row count or chronology check fails.
    """
    raw = source.read_bytes()
    sha256 = hashlib.sha256(raw).hexdigest()
    header, body, after_cutoff, total_body_lines = _window_lines(raw, window_before)
    if window_before is not None and len(body) + after_cutoff != total_body_lines:
        raise RuntimeError("window line accounting failed")

    frame = pd.read_csv(io.StringIO("\n".join([header, *body]) + "\n"), sep="\t", dtype=str).rename(
        columns=lambda name: name.strip("<>")
    )
    if len(frame) != len(body):
        raise RuntimeError(f"row count mismatch: parsed {len(frame)}, lines {len(body)}")

    table, problems = mt5_export_to_bars(
        frame, instrument_id=INSTRUMENT_ID, timeframe=TIMEFRAME, source_id=SOURCE_ID
    )
    source_rows = len(frame)
    kept_rows = set(table.column("source_sequence").to_pylist())
    quarantine = quarantine_table(frame, problems, kept_rows)
    reconciliation = reconcile_export_to_bars(frame, table, problems)
    if not reconciliation.reconciles:
        raise RuntimeError(f"reconciliation failed: {reconciliation}")

    schema_id = require_schema_id(table)
    with tempfile.TemporaryDirectory() as scratch:
        round_trip = parquet_round_trip(table, Path(scratch) / "bars_roundtrip.parquet")
    if not (
        round_trip.schema_equal and round_trip.values_equal and round_trip.rows == table.num_rows
    ):
        raise RuntimeError(f"parquet round trip failed: {round_trip}")
    if parquet_dir is not None:
        parquet_dir.mkdir(parents=True, exist_ok=True)
        bars_path = parquet_dir / "bars.parquet"
        quarantine_path = parquet_dir / "quarantine.parquet"
        pq.write_table(table, bars_path)
        pq.write_table(quarantine, quarantine_path)
        manifest = {
            "source_sha256": sha256,
            "schema_id": schema_id,
            "bars_parquet_sha256": hashlib.sha256(bars_path.read_bytes()).hexdigest(),
            "bars_rows": table.num_rows,
            "quarantine_parquet_sha256": hashlib.sha256(quarantine_path.read_bytes()).hexdigest(),
            "quarantine_rows": quarantine.num_rows,
        }
        (parquet_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )

    event = pd.DatetimeIndex(table.column("event_time").to_pandas())
    deltas = event[1:] - event[:-1]
    strictly_increasing = bool(np.all(deltas > pd.Timedelta(0)))
    gaps: list[dict[str, Any]] = []
    for i in np.flatnonzero(deltas > ONE_MINUTE):
        spacing = deltas[i]
        if spacing % ONE_MINUTE != pd.Timedelta(0):
            raise RuntimeError(f"non-whole-minute gap at position {i}: {spacing}")
        minutes = int(spacing // ONE_MINUTE)
        gaps.append(
            {
                "start": _iso(event[i]),
                "end": _iso(event[i + 1]),
                "gap_minutes": minutes,
                "missing_bars": minutes - 1,
            }
        )

    first_label, last_label = frame.iloc[0], frame.iloc[-1]
    quarantined = quarantine.to_pylist()
    excluded = sum(1 for q in quarantined if q["action"] == "excluded_from_table")
    return {
        "ledger": "DATA-SCHEMAS quality ledger",
        "scope": (
            "tracked example export only; not a research dataset and not scientific evidence"
            if window_before is None
            else f"source rows dated before {window_before}; rows on or after it were counted, "
            "not converted or checked; not scientific evidence"
        ),
        "schema_version": SCHEMA_VERSION,
        "generator": GENERATOR_RELATIVE,
        "source": {
            "file": source.name,
            "sha256": sha256,
            "bytes": len(raw),
            "delimiter": "tab",
            "body_lines_in_file": total_body_lines,
        },
        "window": {
            "window_before": window_before,
            "rows_in_window": source_rows,
            "lines_on_or_after_cutoff": after_cutoff,
            "rule": "lines whose DATE label is on or after the cutoff are never parsed",
            "first_source_label": f"{first_label['DATE']} {first_label['TIME']}",
            "last_source_label": f"{last_label['DATE']} {last_label['TIME']}",
        },
        "conversion": {
            "instrument_id": INSTRUMENT_ID,
            "timeframe": TIMEFRAME,
            "source_id": SOURCE_ID,
            "source_clock": SOURCE_CLOCK,
            "bar_timestamp_convention": "open",
            "close_time": "event_time + 1 minute",
            "available_at": "close_time",
            "volume_column": "TICKVOL",
            "schema_id": schema_id,
            "converted_row_count": table.num_rows,
            "bar_schema_fields": BAR_SCHEMA.names,
        },
        "reconciliation": {
            "source_rows": source_rows,
            "converted_rows": table.num_rows,
            "quarantined_rows": reconciliation.quarantined_rows,
            "excluded_from_table": excluded,
            "unexplained_rows": reconciliation.unexplained_rows,
            "event_time_mismatches_vs_independent_oracle": reconciliation.event_time_mismatches,
            "value_mismatches": reconciliation.value_mismatches,
            "dst_class_mismatches_vs_independent_oracle": reconciliation.dst_class_mismatches,
            "reconciles": reconciliation.reconciles,
            "oracle": "zoneinfo fold semantics, independent of pandas tz_localize",
        },
        "parquet_round_trip": {
            "rows": round_trip.rows,
            "schema_equal": round_trip.schema_equal,
            "values_equal": round_trip.values_equal,
            "pyarrow_version": pa.__version__,
        },
        "quarantine": {
            "count": len(quarantined),
            "rule": "rows failing validate_bars or the DST local-time mapping are reported with a reason",
            "rows": quarantined,
        },
        "time_coverage": {
            "first_event_time_utc": _iso(event[0]),
            "last_event_time_utc": _iso(event[-1]),
            "first_source_label": f"{first_label['DATE']} {first_label['TIME']} {SOURCE_CLOCK}",
            "last_source_label": f"{last_label['DATE']} {last_label['TIME']} {SOURCE_CLOCK}",
            "strictly_increasing": strictly_increasing,
            "duplicate_event_times": int(event.duplicated().sum()),
        },
        "gaps": {
            "threshold": "spacing between consecutive converted event_time values > 1 minute",
            "gap_minutes": "end - start in whole minutes (spacing between bar opens)",
            "missing_bars": "gap_minutes - 1",
            "count": len(gaps),
            "total_missing_bars": sum(g["missing_bars"] for g in gaps),
            "items": gaps,
        },
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--source", type=Path, default=REPO / EXAMPLE_RELATIVE)
    parser.add_argument("--window-before", default=None, help="YYYY.MM.DD cutoff, exclusive")
    parser.add_argument("--out", type=Path, default=LEDGER)
    parser.add_argument("--parquet-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    ledger = build_ledger(
        args.source, window_before=args.window_before, parquet_dir=args.parquet_dir
    )
    args.out.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")
    rec = ledger["reconciliation"]
    print(
        f"source_rows={rec['source_rows']} converted_rows={rec['converted_rows']} "
        f"quarantined={rec['quarantined_rows']} gaps={ledger['gaps']['count']} "
        f"missing_bars={ledger['gaps']['total_missing_bars']} reconciles={rec['reconciles']}"
    )


if __name__ == "__main__":
    main()
