#!/usr/bin/env python3
"""Create one hash-pinned scientific-gate review record.

This tool records a review decision; it never infers a pass from filenames or
historical labels. Passing records require current evidence bytes and explicit
confirmation that prohibited selection/leakage states were absent.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from artifacts.atomic import write_json_atomic
from configuration.paths import repository_root

ROOT = repository_root(__file__)
SCHEMA_VERSION = "pretraining-scientific-gate-review-v1"


def file_sha256(path: Path) -> str:
    """Hash one file with bounded memory."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def current_source_sha() -> str:
    """Return the current repository commit."""
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def build_gate_record(
    *,
    gate_id: str,
    status: str,
    source_commit: str,
    reviewed_by: str,
    reviewed_at_utc: str,
    evidence_paths: list[Path],
    exposed_report_period_used_for_selection: bool,
    candidate_realized_outcomes_used_as_policy_inputs: bool,
    preregistered_thresholds_changed_post_hoc: bool,
    note: str,
) -> dict[str, Any]:
    """Build a fail-closed scientific gate review record."""
    if not gate_id.strip():
        raise ValueError("gate_id must not be empty")
    if status not in {"pass", "fail", "blocked"}:
        raise ValueError("status must be pass, fail, or blocked")
    if len(source_commit) != 40 or any(c not in "0123456789abcdef" for c in source_commit.lower()):
        raise ValueError("source_commit must be a full 40-character Git SHA")
    if not reviewed_by.strip() or not note.strip():
        raise ValueError("reviewed_by and note must not be empty")
    reviewed_at = datetime.fromisoformat(reviewed_at_utc.replace("Z", "+00:00"))
    if reviewed_at.tzinfo is None or reviewed_at.utcoffset() != UTC.utcoffset(reviewed_at):
        raise ValueError("reviewed_at_utc must be an offset-aware UTC timestamp")

    prohibited = {
        "exposed_report_period_used_for_selection": exposed_report_period_used_for_selection,
        "candidate_realized_outcomes_used_as_policy_inputs": candidate_realized_outcomes_used_as_policy_inputs,
        "preregistered_thresholds_changed_post_hoc": preregistered_thresholds_changed_post_hoc,
    }
    if status == "pass" and not evidence_paths:
        raise ValueError("passing gate review requires at least one evidence file")
    if status == "pass" and any(prohibited.values()):
        raise ValueError("passing gate review cannot declare a prohibited scientific state")

    evidence: list[dict[str, str]] = []
    for raw in evidence_paths:
        path = raw.expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"evidence file is missing: {path}")
        evidence.append({"path": str(path), "sha256": file_sha256(path)})

    return {
        "schema_version": SCHEMA_VERSION,
        "gate_id": gate_id.strip(),
        "status": status,
        "source_commit": source_commit,
        "reviewed_by": reviewed_by.strip(),
        "reviewed_at_utc": reviewed_at.isoformat().replace("+00:00", "Z"),
        "evidence": evidence,
        "prohibited_states": prohibited,
        "note": note.strip(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gate-id", required=True)
    parser.add_argument("--status", choices=("pass", "fail", "blocked"), required=True)
    parser.add_argument("--source-commit")
    parser.add_argument("--reviewed-by", required=True)
    parser.add_argument("--reviewed-at-utc", required=True)
    parser.add_argument("--evidence", type=Path, action="append", default=[])
    parser.add_argument("--exposed-selection", choices=("yes", "no"), required=True)
    parser.add_argument("--candidate-outcomes-as-inputs", choices=("yes", "no"), required=True)
    parser.add_argument("--post-hoc-threshold-change", choices=("yes", "no"), required=True)
    parser.add_argument("--note", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    record = build_gate_record(
        gate_id=args.gate_id,
        status=args.status,
        source_commit=args.source_commit or current_source_sha(),
        reviewed_by=args.reviewed_by,
        reviewed_at_utc=args.reviewed_at_utc,
        evidence_paths=args.evidence,
        exposed_report_period_used_for_selection=args.exposed_selection == "yes",
        candidate_realized_outcomes_used_as_policy_inputs=args.candidate_outcomes_as_inputs
        == "yes",
        preregistered_thresholds_changed_post_hoc=args.post_hoc_threshold_change == "yes",
        note=args.note,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(args.output, record)
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
