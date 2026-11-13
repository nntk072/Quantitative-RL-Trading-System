#!/usr/bin/env python3
"""Enforce the V3 TODO 162 FINISHED condition from final artifacts."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from scripts.research.audits.record_pretraining_scientific_gate import file_sha256

from configuration.paths import repository_root

ROOT = repository_root(__file__)


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def verify_finished(
    *,
    progress: dict[str, Any],
    campaign: dict[str, Any],
    release_bundle: dict[str, Any],
    old_boxes: dict[str, Any],
    handoff: dict[str, Any],
    current_sha: str,
    source_clean: bool,
) -> list[str]:
    """Return every outstanding FINISHED-condition failure."""
    failures: list[str] = []
    if not source_clean:
        failures.append("working tree is dirty")
    if progress.get("schema_version") != "v3-full-progress-v1":
        failures.append("progress artifact schema is invalid")
    if progress.get("source_sha") != current_sha:
        failures.append("progress source SHA does not match current source")
    if handoff.get("final_sha") != current_sha or handoff.get("next_baseline_sha") != current_sha:
        failures.append("handoff SHA does not match current source")
    if handoff.get("branch") != "main":
        failures.append("handoff does not identify main as the final branch")
    if handoff.get("ci_status") != "success":
        failures.append("final GitHub CI is not successful")
    if release_bundle.get("status") != "pass":
        failures.append("release bundle is incomplete")
    if release_bundle.get("verdict") not in {
        "READY",
        "READY WITH SCIENTIFIC LIMITATIONS",
        "BLOCKED / NEGATIVE RESULT",
    }:
        failures.append("release verdict is invalid")
    artifacts = release_bundle.get("artifacts")
    if not isinstance(artifacts, dict) or not artifacts:
        failures.append("release bundle has no hashed artifacts")
    else:
        if release_bundle.get("artifact_count") != len(artifacts):
            failures.append("release artifact count does not match its manifest")
        if release_bundle.get("required_file_count") != len(artifacts):
            failures.append("release bundle omits required files")
        for name, record in artifacts.items():
            if not isinstance(record, dict):
                failures.append(f"malformed release artifact record: {name}")
                continue
            path = Path(str(record.get("path", "")))
            if not path.is_file():
                failures.append(f"release artifact missing: {path}")
            elif file_sha256(path) != record.get("sha256"):
                failures.append(f"release artifact hash mismatch: {path}")
            elif path.stat().st_size != record.get("bytes"):
                failures.append(f"release artifact size mismatch: {path}")
    old_items = old_boxes.get("items")
    old_items_valid = (
        isinstance(old_items, list)
        and len(old_items) == 70
        and [row.get("old_open_id") for row in old_items if isinstance(row, dict)]
        == list(range(1, 71))
        and all(
            isinstance(row, dict)
            and row.get("final_disposition") in {"COMPLETED", "DEFERRED-NO-GO"}
            for row in old_items
        )
    )
    if (
        old_boxes.get("all_terminal") is not True
        or old_boxes.get("item_count") != 70
        or not old_items_valid
    ):
        failures.append("old 70 open boxes are not fully dispositioned")
    if campaign.get("source_commit") != current_sha or campaign.get("source_clean") is not True:
        failures.append("campaign state is stale or dirty")
    if campaign.get("release_ready") is not True:
        failures.append("campaign state is not release-ready")
    tasks = progress.get("tasks")
    if not isinstance(tasks, dict):
        failures.append("progress artifact is invalid")
    else:
        if set(tasks) != {str(todo) for todo in range(1, 163)}:
            failures.append("progress artifact does not contain exactly TODO 1..162")
        counts = {status: 0 for status in ("PASS", "FAIL", "DEFERRED-NO-GO", "PENDING", "RUNNING")}
        for todo in range(1, 163):
            row = tasks.get(str(todo), {})
            if not isinstance(row, dict):
                failures.append(f"TODO {todo} record is malformed")
                continue
            status = row.get("status")
            if row.get("source_sha") != current_sha:
                failures.append(f"TODO {todo} source SHA is stale")
            if status in counts:
                counts[status] += 1
            if status in {"PASS", "DEFERRED-NO-GO"}:
                if not isinstance(row.get("result"), str) or not row["result"].strip():
                    failures.append(f"TODO {todo} has no terminal rationale")
                evidence = row.get("evidence")
                if not isinstance(evidence, list) or not evidence:
                    failures.append(f"TODO {todo} has no terminal evidence")
                else:
                    for item in evidence:
                        if not isinstance(item, dict):
                            failures.append(f"TODO {todo} evidence row is malformed")
                            continue
                        path = Path(str(item.get("path", "")))
                        if not path.is_file():
                            failures.append(f"TODO {todo} evidence missing: {path}")
                        elif file_sha256(path) != item.get("sha256"):
                            failures.append(f"TODO {todo} evidence hash mismatch: {path}")
            if todo < 162 and status not in {"PASS", "DEFERRED-NO-GO"}:
                failures.append(f"TODO {todo} is not terminal-success/no-go: {status}")
        todo162_row = tasks.get("162", {})
        todo162 = todo162_row.get("status") if isinstance(todo162_row, dict) else None
        if todo162 != "PASS":
            failures.append("TODO 162 FINISHED condition is not PASS")
        if not isinstance(todo162_row, dict):
            failures.append("TODO 162 record is malformed")
        else:
            if todo162_row.get("source_sha") != current_sha:
                failures.append("TODO 162 source SHA is stale")
            evidence = todo162_row.get("evidence")
            if not isinstance(evidence, list) or not evidence:
                failures.append("TODO 162 has no final verification evidence")
            else:
                for item in evidence:
                    if not isinstance(item, dict):
                        failures.append("TODO 162 evidence row is malformed")
                        continue
                    path = Path(str(item.get("path", "")))
                    if not path.is_file():
                        failures.append(f"TODO 162 evidence missing: {path}")
                    elif file_sha256(path) != item.get("sha256"):
                        failures.append(f"TODO 162 evidence hash mismatch: {path}")
        if handoff.get("todo_status_counts") != counts:
            failures.append("handoff TODO counts differ from progress tracker")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--progress", type=Path, required=True)
    parser.add_argument("--campaign-state", type=Path, required=True)
    parser.add_argument("--release-bundle", type=Path, required=True)
    parser.add_argument("--old-box-disposition", type=Path, required=True)
    parser.add_argument("--handoff", type=Path, required=True)
    args = parser.parse_args()
    current_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    source_clean = not subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=ROOT, text=True
    ).strip()
    failures = verify_finished(
        progress=_object(args.progress),
        campaign=_object(args.campaign_state),
        release_bundle=_object(args.release_bundle),
        old_boxes=_object(args.old_box_disposition),
        handoff=_object(args.handoff),
        current_sha=current_sha,
        source_clean=source_clean,
    )
    payload = {
        "schema_version": "v3-finished-verification-v1",
        "source_sha": current_sha,
        "status": "pass" if not failures else "fail",
        "failures": failures,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
