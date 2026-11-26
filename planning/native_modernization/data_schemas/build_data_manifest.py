"""Write the DATA-SCHEMAS data manifest: sources, ledgers, canonical schemas, validators and migrations.

The manifest records identities and checksums only. It holds no prices and no per-row values. Source
checksums are taken over whole files, which is the raw identity of an immutable source. The 2026
reporting interval is never parsed or used by this script.

Gitignored sources in ``data/`` are hashed only when they are present. The pre-2026 M1 and tick
identities are read from their ledgers, which were produced by the converters.

    .venv-x86/bin/python planning/native_modernization/data_schemas/build_data_manifest.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import pyarrow as pa  # type: ignore[import-untyped]

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from market_data import arrow_schemas as schemas  # noqa: E402
from market_data import event_schemas  # noqa: E402
from market_data.reconciliation import QUARANTINE_SCHEMA  # noqa: E402

MANIFEST = HERE / "data_manifest.json"
GENERATOR_RELATIVE = "planning/native_modernization/data_schemas/build_data_manifest.py"
TIMEFRAMES = ("M1", "M3", "M5", "M10", "M15", "M30", "H1", "H4", "D1")
EXAMPLE_NAME = "US100.cash_M1_202412300105_202501020334.csv"
TICK_SOURCE_NAME = "US100.cash_202412300105_202610162349.csv"
M1_SOURCE_NAME = "US100.cash_M1_202412300105_202610162349.csv"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((HERE / name).read_text(encoding="utf-8"))
    return data


def _fields(schema: pa.Schema) -> list[dict[str, Any]]:
    return [
        {"name": field.name, "type": str(field.type), "nullable": bool(field.nullable)}
        for field in schema
    ]


def schema_catalog() -> dict[str, Any]:
    """Return the canonical schema definitions as declared in code.

    Returns:
        Supported schema ids, one entry per physical table with its id and fields, the validators,
        and the migrations. Only code constants are read; no data file is opened.
    """
    tables = {
        "QUOTE_SCHEMA": ("quote-event.v1", schemas.QUOTE_SCHEMA),
        "LEGACY_QUOTE_SCHEMA": ("market-event.v1", schemas.LEGACY_QUOTE_SCHEMA),
        "BAR_SCHEMA": ("market-event.v1", schemas.BAR_SCHEMA),
        "BAR_REVISED_SCHEMA": ("market-event.v2", schemas.BAR_REVISED_SCHEMA),
        "TRADE_SCHEMA": ("market-event.v1", schemas.TRADE_SCHEMA),
        "INSTRUMENT_SCHEMA": ("instrument-metadata.v1", schemas.INSTRUMENT_SCHEMA),
        "CALENDAR_SCHEMA": ("session-calendar.v1", schemas.CALENDAR_SCHEMA),
        "NORMALIZED_EVENT_SCHEMA": ("normalized-event.v1", event_schemas.NORMALIZED_EVENT_SCHEMA),
        "FEATURE_ROW_SCHEMA": ("feature-row.v1", event_schemas.FEATURE_ROW_SCHEMA),
        "QUARANTINE_SCHEMA": (None, QUARANTINE_SCHEMA),
    }
    return {
        "supported_schema_ids": sorted(schemas.SUPPORTED_SCHEMA_IDS),
        "quote_origins": sorted(schemas.QUOTE_ORIGINS),
        "timestamp_units": sorted(schemas.TIMESTAMP_UNITS_PER_NS),
        "plausible_utc_range": {"min": "1990-01-01", "max_exclusive": "2100-01-01"},
        "tables": {
            name: {"schema_id": schema_id, "fields": _fields(schema)}
            for name, (schema_id, schema) in tables.items()
        },
        "validators": {
            "arrow_schemas": [
                "validate_quotes",
                "validate_bars",
                "validate_trades",
                "validate_instruments",
                "validate_calendar",
            ],
            "event_schemas": ["validate_normalized_events", "validate_feature_rows"],
            "schema_migration": ["validate_revised_bars"],
            "coverage": ["grid_report"],
        },
        "migrations": [
            {
                "from": "market-event.v1 (bar layout)",
                "to": "market-event.v2",
                "function": "market_data.schema_migration.migrate_bars_v1_to_v2",
                "revision": 0,
            },
            {
                "from": "market-event.v1 (legacy quote layout)",
                "to": "quote-event.v1",
                "function": "market_data.schema_migration.migrate_quotes_v1_to_quote_v1",
                "origin": "observed",
            },
        ],
    }


def build_manifest(data_dir: Path) -> dict[str, Any]:
    """Assemble the manifest from ledgers, present source files and the schema catalog.

    Args:
        data_dir: Directory holding the gitignored sources (the repository ``data/`` directory).

    Returns:
        The manifest dict, ready to be written as JSON.
    """
    example_path = data_dir / "examples" / EXAMPLE_NAME
    m1 = _load("quality_ledger_pre2026_m1.json")
    tick = _load("tick_reconciliation_pre2026.json")
    timeframe = _load("timeframe_reconciliation_pre2026.json")
    example = _load("quality_ledger.json")

    sources: list[dict[str, Any]] = [
        {
            "role": "example_m1_tracked",
            "file": EXAMPLE_NAME,
            "path": "data/examples/" + EXAMPLE_NAME,
            "sha256": _sha256(example_path) if example_path.is_file() else None,
            "bytes": example_path.stat().st_size if example_path.is_file() else None,
            "body_lines_in_file": example["source"]["body_lines_in_file"],
            "window": None,
            "scope": "tracked engineering fixture; not a research dataset",
        },
        {
            "role": "m1_pre2026",
            "file": M1_SOURCE_NAME,
            "path": "data/ (gitignored, read-only)",
            "sha256": m1["source"]["sha256"],
            "bytes": m1["source"]["bytes"],
            "body_lines_in_file": m1["source"]["body_lines_in_file"],
            "window": {
                "window_before": m1["window"]["window_before"],
                "rows_in_window": m1["window"]["rows_in_window"],
                "lines_on_or_after_cutoff": m1["window"]["lines_on_or_after_cutoff"],
            },
            "scope": "pre-2026 offline window; the ledger is the evidence",
        },
        {
            "role": "tick_pre2026",
            "file": TICK_SOURCE_NAME,
            "path": "data/ (gitignored, read-only)",
            "sha256": tick["source"]["sha256"],
            "bytes": tick["source"]["bytes"],
            "body_lines_in_file": tick["source"]["body_lines_in_file"],
            "window": {
                "window_before": tick["window_before"],
                "window_rows": tick["reconciliation"]["window_rows"],
                "lines_on_or_after_cutoff": tick["source"]["lines_on_or_after_cutoff"],
            },
            "scope": "pre-2026 offline window",
            "status": {
                "evidence_revision": "not recorded in the ledger; schema_version market-event.v1",
                "current_schema_id": "quote-event.v1",
                "rerun_required": True,
                "reason": (
                    "the tick ledger was produced before the quote-event.v1 origin tag and the "
                    "order rule; the full window needs a bounded CPU allocation to regenerate"
                ),
            },
        },
    ]
    for timeframe_name in TIMEFRAMES[1:]:
        matches = sorted(data_dir.glob(f"US100.cash_{timeframe_name}_*.csv"))
        match = matches[0] if matches else None
        sources.append(
            {
                "role": f"export_{timeframe_name}_pre2026",
                "file": match.name if match else None,
                "path": "data/ (gitignored, read-only)",
                "sha256": _sha256(match) if match else None,
                "bytes": match.stat().st_size if match else None,
                "window": {"window_before": timeframe["window_before"]},
                "scope": "pre-2026 export compared with resampled M1; counts only in the ledger",
            }
        )

    ledgers = []
    for name in (
        "quality_ledger.json",
        "quality_ledger_pre2026_m1.json",
        "tick_reconciliation_pre2026.json",
        "timeframe_reconciliation_pre2026.json",
    ):
        path = HERE / name
        data = _load(name)
        ledgers.append(
            {
                "file": name,
                "sha256": _sha256(path),
                "schema_version": data.get("schema_version")
                or data.get("conversion", {}).get("schema_id"),
            }
        )

    return {
        "manifest": "DATA-SCHEMAS data manifest",
        "scope": (
            "identities, checksums, ledgers and canonical schema definitions for the tracked example "
            "and the pre-2026 offline windows; not scientific evidence"
        ),
        "generator": GENERATOR_RELATIVE,
        "identity_policy": (
            "instrument_id and source_id come from the converter constants and the instrument registry, "
            "never from filenames"
        ),
        "raw_source_policy": "raw sources are read-only; checksums are recorded and no source is rewritten",
        "reporting_interval_policy": (
            "the 2026 interval is never parsed, converted, checked or reported; whole-file checksums and "
            "post-cutoff line counts are the only 2026 facts recorded"
        ),
        "timestamps": {
            "storage": "timestamp[ns, tz=UTC]",
            "source_clock": schemas.SOURCE_CLOCK,
            "bar_timestamp_convention": "open",
            "available_at": "bar: close_time; tick: event_time (no measured latency)",
        },
        "sources": sources,
        "ledgers": ledgers,
        "schemas": schema_catalog(),
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--data-dir", type=Path, default=REPO / "data")
    parser.add_argument("--out", type=Path, default=MANIFEST)
    args = parser.parse_args(argv)
    manifest = build_manifest(args.data_dir)
    args.out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
