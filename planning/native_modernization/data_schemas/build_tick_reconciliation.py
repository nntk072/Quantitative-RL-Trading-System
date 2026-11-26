r"""Reconcile the pre-2026 window of the local tick/quote export (DATA-SCHEMAS, CPU allocation run).

The source is the gitignored ``data/US100.cash_202412300105_202610162349.csv`` (about 6 GB). It is read only.
Quote Parquet parts and quarantine parts go to the git-ignored logs directory given with ``--out-dir``.
The counts-only ledger is written beside this file as ``tick_reconciliation_pre2026.json``.

Run it as one bounded step on a CPU allocation, from a named tmux session:

    srun --immediate=60 --partition=batch-skl --cpus-per-task=8 --mem=64G --time=02:00:00 \\
        .venv-x86/bin/python planning/native_modernization/data_schemas/build_tick_reconciliation.py \\
        --source data/US100.cash_202412300105_202610162349.csv --window-before 2026.01.01 \\
        --out-dir logs/agents/data_scientist_engineer/2026-11-26_data_schemas/tick_parts
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from market_data.tick_reconciliation import reconcile_tick_export  # noqa: E402

LEDGER = HERE / "tick_reconciliation_pre2026.json"
DEFAULT_SOURCE = REPO / "data" / "US100.cash_202412300105_202610162349.csv"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument(
        "--window-before", default="2026.01.01", help="YYYY.MM.DD cutoff, exclusive"
    )
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--chunk-rows", type=int, default=2_000_000)
    parser.add_argument("--ledger", type=Path, default=LEDGER)
    args = parser.parse_args(argv)

    ledger = reconcile_tick_export(
        args.source, args.window_before, args.out_dir, chunk_rows=args.chunk_rows
    )
    args.ledger.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    rec = ledger["reconciliation"]
    print(
        f"window_rows={rec['window_rows']} converted={rec['converted_rows']} "
        f"quarantined={rec['quarantined_rows']} unexplained={rec['unexplained_rows']} "
        f"reconciles={rec['reconciles']} parquet_round_trip={ledger['parquet']['round_trip_all_parts_equal']}"
    )


if __name__ == "__main__":
    main()
