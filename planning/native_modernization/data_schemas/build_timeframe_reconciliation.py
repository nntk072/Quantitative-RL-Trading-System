r"""Reconcile higher-timeframe MT5 exports against M1 bars resampled to the same local buckets (DATA-SCHEMAS).

Inputs are the local M1 source and the MT5 exports of M3 to D1 in ``data/`` (gitignored). Only rows
dated before the cutoff are parsed; later rows are counted by line. The output is a JSON ledger with
counts, per-field mismatch counts and labels only. It contains no prices.

    .venv-x86/bin/python planning/native_modernization/data_schemas/build_timeframe_reconciliation.py \\
        --data-dir data --window-before 2026.01.01 \\
        --out planning/native_modernization/data_schemas/timeframe_reconciliation_pre2026.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from market_data.export_window import split_export_window, window_frame  # noqa: E402
from market_data.timeframe_reconciliation import (  # noqa: E402
    TIMEFRAME_FREQ,
    compare_export_to_resampled,
    export_frame,
    resample_m1,
)

GENERATOR_RELATIVE = "planning/native_modernization/data_schemas/build_timeframe_reconciliation.py"
LEDGER = HERE / "timeframe_reconciliation_pre2026.json"
M1_GLOB = "US100.cash_M1_*.csv"


def _source_file(data_dir: Path, pattern: str) -> Path:
    matches = sorted(data_dir.glob(pattern))
    if len(matches) != 1:
        raise RuntimeError(f"expected one file for {pattern!r} in {data_dir}, found {len(matches)}")
    return matches[0]


def _load_window(path: Path, window_before: str | None) -> tuple[Any, dict[str, Any]]:
    raw = path.read_bytes()
    window = split_export_window(raw, window_before)
    frame = window_frame(window)
    accounting = {
        "file": path.name,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "body_lines_in_file": window.body_lines_in_file,
        "rows_in_window": len(frame),
        "lines_on_or_after_cutoff": window.lines_on_or_after_cutoff,
    }
    return frame, accounting


def build(data_dir: Path, window_before: str | None) -> dict[str, Any]:
    """Build the timeframe reconciliation ledger for every supported export.

    Args:
        data_dir: Directory holding the M1 and higher-timeframe exports.
        window_before: Optional ``YYYY.MM.DD`` cutoff, exclusive.

    Returns:
        The ledger dict. Raises RuntimeError when a row-accounting identity fails.
    """
    m1_path = _source_file(data_dir, M1_GLOB)
    m1_frame_raw, m1_acc = _load_window(m1_path, window_before)
    m1_local = export_frame(m1_frame_raw)
    m1_dropped = len(m1_frame_raw) - len(m1_local)
    m1 = m1_local.sort_index()
    m1_first = m1.index.min()
    m1_last = m1.index.max()

    timeframes: dict[str, Any] = {}
    for timeframe in TIMEFRAME_FREQ:
        path = _source_file(data_dir, f"US100.cash_{timeframe}_*.csv")
        frame, acc = _load_window(path, window_before)
        export = export_frame(frame)
        dropped = len(frame) - len(export)
        resampled = resample_m1(m1, timeframe)
        result = compare_export_to_resampled(export, resampled, m1_first)
        identity = len(export) + dropped == len(frame)
        if not identity:
            raise RuntimeError(f"{timeframe}: export row accounting failed")
        timeframes[timeframe] = {
            "source": acc,
            "export_rows_dropped_dst": dropped,
            "resample_frequency": TIMEFRAME_FREQ[timeframe],
            "comparison": result,
        }

    return {
        "ledger": "DATA-SCHEMAS higher-timeframe reconciliation",
        "scope": (
            "source rows dated before the cutoff only; rows on or after it were counted, not parsed; "
            "labels and counts only; not scientific evidence"
        ),
        "generator": GENERATOR_RELATIVE,
        "window_before": window_before,
        "clock": "Europe/Helsinki local wall-clock buckets",
        "m1": {
            **m1_acc,
            "rows_converted": int(len(m1)),
            "export_rows_dropped_dst": m1_dropped,
            "first_local_open": m1_first.strftime("%Y-%m-%d %H:%M"),
            "last_local_open": m1_last.strftime("%Y-%m-%d %H:%M"),
        },
        "timeframes": timeframes,
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--data-dir", type=Path, default=REPO / "data")
    parser.add_argument("--window-before", default=None, help="YYYY.MM.DD cutoff, exclusive")
    parser.add_argument("--out", type=Path, default=LEDGER)
    args = parser.parse_args(argv)
    ledger = build(args.data_dir, args.window_before)
    args.out.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")
    for tf, body in ledger["timeframes"].items():
        c = body["comparison"]
        print(
            f"{tf}: export={c['export_bars']} matched={c['matched_buckets']} "
            f"export_only={c['export_only_buckets']} resampled_only={c['resampled_only_buckets']} "
            f"all_fields_equal={c['matched_with_all_fields_equal']} "
            f"any_mismatch={c['matched_with_any_field_mismatch']}"
        )


if __name__ == "__main__":
    main()
