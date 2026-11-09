#!/usr/bin/env python3
"""Record a hash-pinned V3 phase review, optionally freezing direct commands."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.research.audits.record_pretraining_scientific_gate import (
    current_source_sha,
    file_sha256,
)

from artifacts.atomic import write_json_atomic

SCHEMA_VERSION = "v3-phase-review-v2"
FORBIDDEN_EXECUTABLES = {"salloc", "sbatch", "scancel", "srun"}


def _load_optional_json(path: Path | None, expected_type: type) -> Any:
    """Load an optional JSON value with an exact root type."""
    if path is None:
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, expected_type):
        raise ValueError(f"{path} must contain {expected_type.__name__}")
    return value


def _validate_frozen_commands(commands: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate a direct-child command DAG without executing it."""
    ids: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for index, row in enumerate(commands):
        if not isinstance(row, dict):
            raise ValueError(f"commands[{index}] must be an object")
        command_id = str(row.get("id", "")).strip()
        argv = row.get("argv")
        depends_on = row.get("depends_on", [])
        if not command_id or command_id in ids:
            raise ValueError("frozen command IDs must be unique and non-empty")
        if (
            not isinstance(argv, list)
            or not argv
            or any(not isinstance(token, str) or not token for token in argv)
        ):
            raise ValueError(f"{command_id} argv must be a non-empty string list")
        if not isinstance(depends_on, list) or any(not isinstance(x, str) for x in depends_on):
            raise ValueError(f"{command_id} depends_on must be a string list")
        executable = Path(argv[0]).name.lower()
        if executable in FORBIDDEN_EXECUTABLES:
            raise ValueError(f"frozen command cannot allocate/cancel Slurm work: {executable}")
        if any(Path(token).name.lower() in FORBIDDEN_EXECUTABLES for token in argv):
            raise ValueError(f"{command_id} embeds a forbidden scheduler executable")
        ids.add(command_id)
        normalized.append(
            {
                "id": command_id,
                "argv": argv,
                "depends_on": list(depends_on),
                "resource_lock": row.get("resource_lock"),
                "artifact_roots": list(row.get("artifact_roots", [])),
                "experiment": row.get("experiment") is True,
            }
        )
    for row in normalized:
        unknown = set(row["depends_on"]) - ids
        if unknown:
            raise ValueError(f"{row['id']} has unknown dependencies: {sorted(unknown)}")
    return normalized


def build_phase_review(
    *,
    gate_id: str,
    status: str,
    source_commit: str,
    reviewed_by: str,
    reviewed_at_utc: str,
    evidence_paths: list[Path],
    exposed_report_period_used_for_selection: bool,
    preregistered_thresholds_changed_post_hoc: bool,
    incompatible_source_or_config_identity_accepted: bool,
    claim: str,
    note: str,
    frozen_commands: list[dict[str, Any]] | None = None,
    frozen_parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a post-qualification review record without inferring its verdict."""
    if not gate_id.strip() or not reviewed_by.strip() or not note.strip() or not claim.strip():
        raise ValueError("gate_id, reviewed_by, claim, and note must not be empty")
    if status not in {"pass", "fail", "blocked"}:
        raise ValueError("status must be pass, fail, or blocked")
    if len(source_commit) != 40 or any(c not in "0123456789abcdef" for c in source_commit.lower()):
        raise ValueError("source_commit must be a full Git SHA")
    reviewed_at = datetime.fromisoformat(reviewed_at_utc.replace("Z", "+00:00"))
    if reviewed_at.tzinfo is None or reviewed_at.utcoffset() != UTC.utcoffset(reviewed_at):
        raise ValueError("reviewed_at_utc must be UTC")
    prohibited = {
        "exposed_report_period_used_for_selection": exposed_report_period_used_for_selection,
        "preregistered_thresholds_changed_post_hoc": preregistered_thresholds_changed_post_hoc,
        "incompatible_source_or_config_identity_accepted": incompatible_source_or_config_identity_accepted,
    }
    if status == "pass" and (not evidence_paths or any(prohibited.values())):
        raise ValueError("passing phase review requires evidence and no prohibited state")
    evidence: list[dict[str, str]] = []
    for raw in evidence_paths:
        path = raw.expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"evidence file is missing: {path}")
        evidence.append({"path": str(path), "sha256": file_sha256(path)})
    commands = _validate_frozen_commands(frozen_commands or [])
    return {
        "schema_version": SCHEMA_VERSION,
        "gate_id": gate_id.strip(),
        "status": status,
        "source_commit": source_commit,
        "reviewed_by": reviewed_by.strip(),
        "reviewed_at_utc": reviewed_at.isoformat().replace("+00:00", "Z"),
        "claim": claim.strip(),
        "evidence": evidence,
        "prohibited_states": prohibited,
        "frozen_commands": commands,
        "frozen_parameters": frozen_parameters or {},
        "note": note.strip(),
    }


def main() -> int:
    """Write one immutable phase-review record."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gate-id", required=True)
    parser.add_argument("--status", choices=("pass", "fail", "blocked"), required=True)
    parser.add_argument("--source-commit")
    parser.add_argument("--reviewed-by", required=True)
    parser.add_argument("--reviewed-at-utc", required=True)
    parser.add_argument("--evidence", action="append", type=Path, default=[])
    parser.add_argument("--exposed-selection", choices=("yes", "no"), required=True)
    parser.add_argument("--post-hoc-threshold-change", choices=("yes", "no"), required=True)
    parser.add_argument("--accept-incompatible-identity", choices=("yes", "no"), required=True)
    parser.add_argument("--claim", required=True)
    parser.add_argument("--note", required=True)
    parser.add_argument("--commands-json", type=Path)
    parser.add_argument("--parameters-json", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    record = build_phase_review(
        gate_id=args.gate_id,
        status=args.status,
        source_commit=args.source_commit or current_source_sha(),
        reviewed_by=args.reviewed_by,
        reviewed_at_utc=args.reviewed_at_utc,
        evidence_paths=args.evidence,
        exposed_report_period_used_for_selection=args.exposed_selection == "yes",
        preregistered_thresholds_changed_post_hoc=args.post_hoc_threshold_change == "yes",
        incompatible_source_or_config_identity_accepted=args.accept_incompatible_identity == "yes",
        claim=args.claim,
        note=args.note,
        frozen_commands=_load_optional_json(args.commands_json, list),
        frozen_parameters=_load_optional_json(args.parameters_json, dict),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(args.output, record)
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
