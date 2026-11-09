#!/usr/bin/env python3
"""Maintain the compact V3 TODO tracker and compute ready/barrier states."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from scripts.research.audits.record_pretraining_scientific_gate import file_sha256
from scripts.research.audits.v3_full_plan_registry import DEFAULT_CATALOG, load_catalog

from artifacts.atomic import write_json_atomic
from configuration.paths import repository_root

ROOT = repository_root(__file__)
STATUSES = {"PENDING", "RUNNING", "PASS", "FAIL", "DEFERRED-NO-GO"}
TERMINAL = {"PASS", "FAIL", "DEFERRED-NO-GO"}


def current_source_sha() -> str:
    """Return the exact current Git source SHA."""
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def initialize_progress(catalog: dict[str, Any], *, source_sha: str) -> dict[str, Any]:
    """Create the compact progress artifact required by the V3 plan."""
    return {
        "schema_version": "v3-full-progress-v1",
        "source_sha": source_sha,
        "tasks": {
            str(row["id"]): {
                "todo": row["id"],
                "title": row["title"],
                "status": "PENDING",
                "source_sha": source_sha,
                "result": "",
                "evidence": [],
                "next_dependency": row["dependencies"],
            }
            for row in catalog["tasks"]
        },
    }


def _load_progress(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != "v3-full-progress-v1":
        raise ValueError("invalid V3 progress file")
    return value


def mark_todo(
    progress: dict[str, Any],
    *,
    todo: int,
    status: str,
    source_sha: str,
    result: str,
    evidence_paths: list[Path],
) -> None:
    """Set one TODO status with exact-source and evidence-byte provenance."""
    if status not in STATUSES:
        raise ValueError(f"unsupported TODO status: {status}")
    key = str(todo)
    if key not in progress["tasks"]:
        raise ValueError(f"unknown TODO: {todo}")
    if status in TERMINAL and not result.strip():
        raise ValueError("terminal TODO states require a one-line result")
    if status in TERMINAL and not evidence_paths:
        raise ValueError("terminal TODO states require at least one evidence file")
    evidence: list[dict[str, str]] = []
    for raw in evidence_paths:
        path = raw.expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"TODO evidence file missing: {path}")
        evidence.append({"path": str(path), "sha256": file_sha256(path)})
    row = progress["tasks"][key]
    row.update(
        {
            "status": status,
            "source_sha": source_sha,
            "result": result.strip(),
            "evidence": evidence,
        }
    )
    progress["source_sha"] = source_sha


def ready_todos(catalog: dict[str, Any], progress: dict[str, Any]) -> list[int]:
    """Return TODOs whose hard dependencies have passed."""
    tasks = progress["tasks"]
    ready: list[int] = []
    for row in catalog["tasks"]:
        state = tasks[str(row["id"])]
        if state["status"] != "PENDING":
            continue
        if all(tasks[str(dep)]["status"] == "PASS" for dep in row["dependencies"]):
            ready.append(int(row["id"]))
    return ready


def barrier_states(catalog: dict[str, Any], progress: dict[str, Any]) -> dict[str, str]:
    """Compute current hard-barrier states from task progress."""
    tasks = progress["tasks"]
    result: dict[str, str] = {}
    for barrier_id, barrier in catalog["barriers"].items():
        required = [int(x) for x in barrier["requires"]]
        statuses = [tasks[str(todo)]["status"] for todo in required]
        if all(status == "PASS" for status in statuses):
            result[barrier_id] = "PASS"
        elif any(status == "FAIL" for status in statuses):
            result[barrier_id] = "FAIL"
        elif any(status == "DEFERRED-NO-GO" for status in statuses):
            result[barrier_id] = "DEFERRED-NO-GO"
        elif any(status == "RUNNING" for status in statuses):
            result[barrier_id] = "RUNNING"
        else:
            result[barrier_id] = "PENDING"
    return result


def main() -> int:
    """Initialize, update, inspect, or summarize the V3 progress tracker."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init")
    init.add_argument("--output", type=Path, required=True)

    mark = sub.add_parser("mark")
    mark.add_argument("--progress", type=Path, required=True)
    mark.add_argument("--todo", type=int, required=True)
    mark.add_argument("--status", choices=sorted(STATUSES), required=True)
    mark.add_argument("--result", default="")
    mark.add_argument("--evidence", type=Path, action="append", default=[])

    ready = sub.add_parser("ready")
    ready.add_argument("--progress", type=Path, required=True)

    summary = sub.add_parser("summary")
    summary.add_argument("--progress", type=Path, required=True)

    show = sub.add_parser("show")
    show.add_argument("--todo", type=int, required=True)

    args = parser.parse_args()
    catalog = load_catalog(args.catalog)

    if args.command == "init":
        progress = initialize_progress(catalog, source_sha=current_source_sha())
        args.output.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomic(args.output, progress)
        print(json.dumps({"output": str(args.output), "todo_count": 162}, indent=2))
        return 0

    if args.command == "show":
        row = catalog["tasks_by_id"].get(args.todo)
        if row is None:
            raise SystemExit(f"unknown TODO {args.todo}")
        print(json.dumps(row, indent=2, sort_keys=True))
        return 0

    progress = _load_progress(args.progress)
    if args.command == "mark":
        mark_todo(
            progress,
            todo=args.todo,
            status=args.status,
            source_sha=current_source_sha(),
            result=args.result,
            evidence_paths=args.evidence,
        )
        write_json_atomic(args.progress, progress)
        print(json.dumps(progress["tasks"][str(args.todo)], indent=2, sort_keys=True))
        return 0

    if args.command == "ready":
        print(json.dumps({"ready": ready_todos(catalog, progress)}, indent=2))
        return 0

    if args.command == "summary":
        counts = {status: 0 for status in sorted(STATUSES)}
        for row in progress["tasks"].values():
            counts[row["status"]] += 1
        print(
            json.dumps(
                {
                    "source_sha": progress["source_sha"],
                    "counts": counts,
                    "barriers": barrier_states(catalog, progress),
                    "ready": ready_todos(catalog, progress),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
