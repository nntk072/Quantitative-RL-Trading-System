#!/usr/bin/env python3
"""Compare the full schema and values of two candidate-outcome Parquet files."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from itertools import zip_longest
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq  # type: ignore[import-untyped]

from configuration.paths import repository_root

ROOT = repository_root(__file__)
DEFAULT_REFERENCE = ROOT / "evidence/research/candidate_outcomes/conditional_outcomes.parquet"
BATCH_SIZE = 16_384


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def compare_parquet_values(
    reference_path: Path,
    replay_path: Path,
    *,
    batch_size: int = BATCH_SIZE,
) -> dict[str, Any]:
    """Compare two Parquet schemas and every Arrow value in bounded batches.

    This establishes exact replay reproducibility only when the replay was
    produced by the same implementation. It does not independently verify the
    execution algorithm.
    """
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    reference_path = reference_path.resolve()
    replay_path = replay_path.resolve()
    if not reference_path.is_file() or not replay_path.is_file():
        raise FileNotFoundError("both reference and replay Parquet files must exist")

    started = time.monotonic()
    reference = pq.ParquetFile(reference_path)
    replay = pq.ParquetFile(replay_path)
    mismatch: dict[str, Any] | None = None
    rows_compared = 0
    batches_compared = 0

    if reference.schema_arrow.remove_metadata() != replay.schema_arrow.remove_metadata():
        mismatch = {"reason": "Arrow schemas differ"}
    elif reference.metadata.num_rows != replay.metadata.num_rows:
        mismatch = {
            "reason": "row counts differ",
            "reference_rows": reference.metadata.num_rows,
            "replay_rows": replay.metadata.num_rows,
        }
    else:
        streams = zip_longest(
            reference.iter_batches(batch_size=batch_size),
            replay.iter_batches(batch_size=batch_size),
        )
        for batch_index, (left, right) in enumerate(streams):
            if left is None or right is None:
                mismatch = {"batch": batch_index, "reason": "batch stream lengths differ"}
                break
            if left.num_rows != right.num_rows or not left.equals(right):
                mismatch = {
                    "batch": batch_index,
                    "reference_rows": left.num_rows,
                    "replay_rows": right.num_rows,
                    "reason": "Arrow values differ",
                }
                if left.schema == right.schema:
                    for name in left.schema.names:
                        if not left.column(name).equals(right.column(name)):
                            mismatch["first_different_field"] = name
                            break
                break
            rows_compared += left.num_rows
            batches_compared += 1

    script_path = Path(__file__).resolve()
    return {
        "schema_version": "candidate-outcome-full-replay-value-comparison-v1",
        "status": "all_rows_exactly_equal" if mismatch is None else "mismatch",
        "method": (
            "Arrow batch-by-batch exact schema/value comparison; this is replay "
            "reproducibility evidence, not an independent execution implementation"
        ),
        "reference_path": str(reference_path),
        "replay_path": str(replay_path),
        "reference_sha256": _sha256(reference_path),
        "replay_sha256": _sha256(replay_path),
        "reference_rows": reference.metadata.num_rows,
        "replay_rows": replay.metadata.num_rows,
        "rows_compared": rows_compared,
        "batches_compared": batches_compared,
        "batch_size": batch_size,
        "first_mismatch": mismatch,
        "script_path": str(script_path.relative_to(ROOT)),
        "script_sha256": _sha256(script_path),
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--replay", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    args = parser.parse_args()

    report_path = args.report.resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = compare_parquet_values(args.reference, args.replay, batch_size=args.batch_size)
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    checksums_path = report_path.parent / "OUTPUT_SHA256SUMS"
    prior = (
        [
            line
            for line in checksums_path.read_text(encoding="utf-8").splitlines()
            if line.split(maxsplit=1)[-1].strip() != report_path.name
        ]
        if checksums_path.exists()
        else []
    )
    prior.append(f"{_sha256(report_path)}  {report_path.name}")
    checksums_path.write_text("\n".join(sorted(prior)) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
    return 0 if report["status"] == "all_rows_exactly_equal" else 1


if __name__ == "__main__":
    raise SystemExit(main())
