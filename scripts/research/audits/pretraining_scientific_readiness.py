#!/usr/bin/env python3
"""Build the reviewed scientific-readiness manifest consumed by launch planning."""

from __future__ import annotations

import argparse
import json
import subprocess
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from omegaconf import OmegaConf
from scripts.research.audits.record_pretraining_scientific_gate import file_sha256

from artifacts.atomic import write_json_atomic
from configuration.paths import repository_root

ROOT = repository_root(__file__)
DEFAULT_PLAN = ROOT / "config/research/pretraining_scientific_readiness.yaml"
GATE_SCHEMA = "pretraining-scientific-gate-review-v1"
OUTPUT_SCHEMA = "pretraining-scientific-readiness-v1"


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"expected JSON object: {path}")
    return {str(key): item for key, item in value.items()}


def load_plan(path: Path) -> dict[str, Any]:
    value = OmegaConf.to_container(OmegaConf.load(path), resolve=True)
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError("scientific-readiness plan must be a mapping")
    if value.get("schema_version") != "pretraining-scientific-readiness-plan-v1":
        raise ValueError("unsupported scientific-readiness plan schema")
    for key in ("common_gates", "price_gates", "required_execution_barriers"):
        rows = value.get(key)
        if (
            not isinstance(rows, list)
            or not rows
            or not all(isinstance(x, str) and x for x in rows)
        ):
            raise ValueError(f"{key} must be a non-empty string list")
        if len(rows) != len(set(rows)):
            raise ValueError(f"{key} contains duplicates")
    if set(value["common_gates"]) & set(value["price_gates"]):
        raise ValueError("common and PRICE gate IDs must be disjoint")
    return {str(key): item for key, item in value.items()}


def git_state() -> tuple[str, bool]:
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()
    return sha, not dirty


def execution_errors(
    manifest: Mapping[str, Any], *, source_commit: str, required_barriers: list[str]
) -> list[str]:
    errors: list[str] = []
    if manifest.get("schema_version") != "pretraining-parallel-readiness-run-v1":
        errors.append("execution manifest schema mismatch")
    if manifest.get("source_commit") != source_commit:
        errors.append("execution manifest source_commit mismatch")
    if manifest.get("source_dirty_at_start") is not False:
        errors.append("execution manifest did not start from a clean source")
    if manifest.get("execution_status") != "pass":
        errors.append("execution manifest status is not pass")
    if manifest.get("scientific_training_authorized") is not False:
        errors.append("execution manifest illegally claims scientific authorization")
    if manifest.get("price_training_authorized") is not False:
        errors.append("execution manifest illegally claims PRICE authorization")
    tasks = manifest.get("tasks")
    task_by_id: dict[str, dict[str, Any]] = {}
    if not isinstance(tasks, list) or not tasks:
        errors.append("execution manifest has no task results")
    else:
        for row in tasks:
            if not isinstance(row, dict):
                errors.append("execution task row is malformed")
                continue
            task_id = row.get("task_id")
            if not isinstance(task_id, str) or not task_id or task_id in task_by_id:
                errors.append("execution task IDs must be unique non-empty strings")
                continue
            task_by_id[task_id] = row
            if row.get("status") != "pass" or row.get("return_code") != 0:
                errors.append(f"execution task did not pass: {task_id}")
            log_path_text, log_digest = row.get("log_path"), row.get("log_sha256")
            if not isinstance(log_path_text, str) or not isinstance(log_digest, str):
                errors.append(f"execution task log identity is missing: {task_id}")
            else:
                log_path = Path(log_path_text)
                if not log_path.is_file() or file_sha256(log_path) != log_digest:
                    errors.append(f"execution task log is missing or changed: {task_id}")
                result_path = log_path.parent / "result.json"
                try:
                    saved_result = json.loads(result_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    errors.append(f"execution task result is missing or invalid: {task_id}")
                else:
                    if saved_result != row:
                        errors.append(f"execution task result differs from manifest: {task_id}")
            artifacts = row.get("artifact_sha256")
            if not isinstance(artifacts, dict):
                errors.append(f"execution artifact hashes are missing: {task_id}")
            else:
                for path_text, digest in artifacts.items():
                    path = Path(str(path_text))
                    if not isinstance(digest, str) or not path.is_file():
                        errors.append(f"execution artifact is missing: {path}")
                    elif file_sha256(path) != digest:
                        errors.append(f"execution artifact hash mismatch: {path}")
    barrier_status: dict[str, Any] = {}
    barriers = manifest.get("barriers")
    if isinstance(barriers, list):
        for row in barriers:
            if isinstance(row, dict):
                barrier_id = str(row.get("barrier_id", ""))
                if not barrier_id or barrier_id in barrier_status:
                    errors.append("execution barrier IDs must be unique non-empty strings")
                barrier_status[barrier_id] = row
    for barrier in required_barriers:
        row = barrier_status.get(barrier)
        if not isinstance(row, dict) or row.get("status") != "pass":
            errors.append(f"required execution barrier did not pass: {barrier}")
            continue
        required_tasks = row.get("requires")
        if not isinstance(required_tasks, list) or not required_tasks:
            errors.append(f"required execution barrier has no task dependencies: {barrier}")
        elif any(
            not isinstance(task_id, str)
            or task_id not in task_by_id
            or task_by_id[task_id].get("status") != "pass"
            for task_id in required_tasks
        ):
            errors.append(f"required execution barrier has a missing or failed task: {barrier}")
    return errors


def gate_errors(
    record: Mapping[str, Any], *, expected_gate_id: str, source_commit: str
) -> list[str]:
    errors: list[str] = []
    if record.get("schema_version") != GATE_SCHEMA:
        errors.append("gate review schema mismatch")
    if record.get("gate_id") != expected_gate_id:
        errors.append("gate_id mismatch")
    if record.get("source_commit") != source_commit:
        errors.append("gate source_commit mismatch")
    if record.get("status") != "pass":
        errors.append("gate status is not pass")
    if not isinstance(record.get("reviewed_by"), str) or not record["reviewed_by"].strip():
        errors.append("gate reviewer is missing")
    reviewed_at = record.get("reviewed_at_utc")
    try:
        parsed_time = datetime.fromisoformat(str(reviewed_at).replace("Z", "+00:00"))
        if parsed_time.tzinfo is None or parsed_time.utcoffset() != UTC.utcoffset(parsed_time):
            raise ValueError
    except ValueError:
        errors.append("gate review time must be UTC")
    if not isinstance(record.get("note"), str) or not record["note"].strip():
        errors.append("gate rationale is missing")
    prohibited = record.get("prohibited_states")
    required_prohibited = (
        "exposed_report_period_used_for_selection",
        "candidate_realized_outcomes_used_as_policy_inputs",
        "preregistered_thresholds_changed_post_hoc",
    )
    if not isinstance(prohibited, dict):
        errors.append("missing prohibited_states mapping")
    elif any(prohibited.get(key) is not False for key in required_prohibited):
        errors.append("gate declares a prohibited scientific state")
    evidence = record.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        errors.append("gate has no evidence files")
    else:
        for item in evidence:
            if not isinstance(item, dict):
                errors.append("gate evidence row is malformed")
                continue
            path_text, expected_sha = item.get("path"), item.get("sha256")
            if not isinstance(path_text, str) or not isinstance(expected_sha, str):
                errors.append("gate evidence path/hash is malformed")
                continue
            path = Path(path_text)
            if not path.is_file():
                errors.append(f"gate evidence file missing: {path}")
            elif file_sha256(path) != expected_sha:
                errors.append(f"gate evidence hash mismatch: {path}")
    return errors


def build_readiness(
    *,
    plan: dict[str, Any],
    execution_manifest: dict[str, Any],
    gate_records: dict[str, dict[str, Any]],
    source_commit: str,
    source_clean: bool,
) -> dict[str, Any]:
    common = [str(x) for x in plan["common_gates"]]
    price = [str(x) for x in plan["price_gates"]]
    barriers = [str(x) for x in plan["required_execution_barriers"]]
    required = common + price
    errors: list[str] = []
    if not source_clean:
        errors.append("current source tree is dirty")
    unknown = set(gate_records) - set(required)
    missing = set(required) - set(gate_records)
    if unknown:
        errors.append(f"unknown gate records: {sorted(unknown)}")
    if missing:
        errors.append(f"missing gate records: {sorted(missing)}")
    exec_errors = execution_errors(
        execution_manifest, source_commit=source_commit, required_barriers=barriers
    )
    errors.extend(exec_errors)
    gate_results: dict[str, dict[str, Any]] = {}
    for gate_id in required:
        record = gate_records.get(gate_id)
        row_errors = (
            ["gate record missing"]
            if record is None
            else gate_errors(record, expected_gate_id=gate_id, source_commit=source_commit)
        )
        gate_results[gate_id] = {
            "status": "pass" if not row_errors else "fail",
            "errors": row_errors,
            "record": record,
        }
    common_ready = (
        source_clean
        and not exec_errors
        and all(gate_results[g]["status"] == "pass" for g in common)
    )
    price_ready = common_ready and all(gate_results[g]["status"] == "pass" for g in price)
    if not common_ready:
        errors.append("one or more common scientific gates did not pass")
    return {
        "schema_version": OUTPUT_SCHEMA,
        "status": "pass" if common_ready else "fail",
        "source_commit": source_commit,
        "source_clean": source_clean,
        "scientific_training_authorized": common_ready,
        "price_training_authorized": price_ready,
        "common_gate_ids": common,
        "price_gate_ids": price,
        "required_execution_barriers": barriers,
        "execution_manifest": execution_manifest,
        "gate_results": gate_results,
        "errors": errors,
        "interpretation": (
            "C/D authorization requires all common gates. PRICE additionally requires all "
            "PRICE-specific gates. This manifest does not start training or authorize use of "
            "the exposed report-only period for model selection."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--execution-manifest", type=Path, required=True)
    parser.add_argument("--gate-record", action="append", default=[], metavar="PATH")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan_path = args.plan if args.plan.is_absolute() else ROOT / args.plan
    plan = load_plan(plan_path)
    source_commit, source_clean = git_state()
    if not source_clean:
        raise SystemExit("scientific readiness requires a clean source tree")
    execution = _load_object(args.execution_manifest.expanduser().resolve())
    records: dict[str, dict[str, Any]] = {}
    for raw in args.gate_record:
        record = _load_object(Path(raw).expanduser().resolve())
        gate_id = str(record.get("gate_id", ""))
        if gate_id in records:
            raise ValueError(f"duplicate gate record: {gate_id}")
        records[gate_id] = record
    result = build_readiness(
        plan=plan,
        execution_manifest=execution,
        gate_records=records,
        source_commit=source_commit,
        source_clean=source_clean,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(args.output, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
