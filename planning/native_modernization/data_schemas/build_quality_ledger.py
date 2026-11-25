"""Build the DATA-SCHEMAS quality ledger for the tracked US100 M1 example export.

Only the tracked example ``data/examples/US100.cash_M1_202412300105_202501020334.csv`` is read.
The script converts it with ``market_data.arrow_schemas.mt5_export_to_bars`` and writes
``quality_ledger.json`` next to this file. Run from any directory:

    .venv-x86/bin/python planning/native_modernization/data_schemas/build_quality_ledger.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from market_data.arrow_schemas import (  # noqa: E402
    SCHEMA_VERSION,
    SOURCE_CLOCK,
    mt5_export_to_bars,
    quarantine_mask,
)

SOURCE_RELATIVE = "data/examples/US100.cash_M1_202412300105_202501020334.csv"
SOURCE = REPO / SOURCE_RELATIVE
LEDGER = HERE / "quality_ledger.json"
GENERATOR_RELATIVE = "planning/native_modernization/data_schemas/build_quality_ledger.py"
INSTRUMENT_ID = "US100.cash"
TIMEFRAME = "M1"
SOURCE_ID = "mt5-export"
GAP_THRESHOLD = pd.Timedelta(minutes=1)
ONE_MINUTE = pd.Timedelta(minutes=1)


def _iso(value: pd.Timestamp) -> str:
    return pd.Timestamp(value).tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> None:
    raw = SOURCE.read_bytes()
    sha256 = hashlib.sha256(raw).hexdigest()

    frame = pd.read_csv(SOURCE, sep="\t", dtype=str).rename(columns=lambda n: n.strip("<>"))
    source_rows = len(frame)
    # Independent line count: every non-empty line after the header is one export row.
    text_lines = [line for line in raw.decode("ascii").splitlines() if line.strip()]
    if len(text_lines) - 1 != source_rows:
        raise RuntimeError(f"row count mismatch: parsed {source_rows}, lines {len(text_lines) - 1}")

    table, problems = mt5_export_to_bars(
        frame, instrument_id=INSTRUMENT_ID, timeframe=TIMEFRAME, source_id=SOURCE_ID
    )
    converted_rows = table.num_rows
    kept_sequences = set(table.column("source_sequence").to_pylist())
    flagged_in_table = quarantine_mask(problems, source_rows)

    quarantined = [
        {
            "source_row_index": p.row,
            "source_row_label": {
                "DATE": str(frame["DATE"].iloc[p.row]),
                "TIME": str(frame["TIME"].iloc[p.row]),
            },
            "reason": p.reason,
            "action": "retained_flagged" if p.row in kept_sequences else "excluded_from_table",
        }
        for p in problems
    ]

    event = pd.DatetimeIndex(table.column("event_time").to_pandas())
    deltas = event[1:] - event[:-1]
    strictly_increasing = bool(np.all(deltas > pd.Timedelta(0)))
    duplicate_event_times = int(event.duplicated().sum())
    gap_positions = np.flatnonzero(deltas > GAP_THRESHOLD)
    gaps: list[dict[str, Any]] = []
    for i in gap_positions:
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

    first_label = frame.iloc[0]
    last_label = frame.iloc[-1]
    ledger: dict[str, Any] = {
        "ledger": "DATA-SCHEMAS quality ledger",
        "scope": "tracked example export only; not a research dataset and not scientific evidence",
        "schema_version": SCHEMA_VERSION,
        "generator": GENERATOR_RELATIVE,
        "source": {
            "file": SOURCE_RELATIVE,
            "file_name": SOURCE.name,
            "sha256": sha256,
            "bytes": len(raw),
            "delimiter": "tab",
            "source_row_count": source_rows,
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
            "converted_row_count": converted_rows,
        },
        "reconciliation": {
            "source_rows": source_rows,
            "converted_rows": converted_rows,
            "excluded_from_table": source_rows - converted_rows,
            "flagged_in_table": int(flagged_in_table.sum()),
            "reconciles": source_rows - converted_rows
            == sum(1 for q in quarantined if q["action"] == "excluded_from_table"),
        },
        "quarantine": {
            "count": len(quarantined),
            "rule": "rows failing validate_bars or DST local-time mapping are reported with a reason",
            "rows": quarantined,
        },
        "time_coverage": {
            "first_event_time_utc": _iso(event[0]),
            "last_event_time_utc": _iso(event[-1]),
            "first_source_label": f"{first_label['DATE']} {first_label['TIME']} {SOURCE_CLOCK}",
            "last_source_label": f"{last_label['DATE']} {last_label['TIME']} {SOURCE_CLOCK}",
            "strictly_increasing": strictly_increasing,
            "duplicate_event_times": duplicate_event_times,
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
    LEDGER.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {LEDGER}")
    print(
        f"source_rows={source_rows} converted_rows={converted_rows} "
        f"quarantined={len(quarantined)} gaps={len(gaps)} "
        f"missing_bars={ledger['gaps']['total_missing_bars']}"
    )


if __name__ == "__main__":
    main()
