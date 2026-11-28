"""Validate collection and per-test receipts before interpreting coverage evidence."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from tools.quality.local_checks.run_evidence import read_quality_json


def read_collected_inventory(files: list[Path]) -> list[dict[str, Any]]:
    """Reject missing, empty, duplicated or inconsistent worker inventories."""
    if not files:
        raise ValueError("No inventory files")
    result: list[dict[str, Any]] | None = None
    for path in files:
        rows = sorted(read_quality_json(path), key=lambda row: row["nodeid"])
        ids = [r["nodeid"] for r in rows]
        if not ids or len(ids) != len(set(ids)):
            raise ValueError("Empty or duplicate inventory")
        if result is not None and result != rows:
            raise ValueError("Workers collected different tests")
        result = rows
    assert result is not None
    return result


def validate_test_receipts(path: Path, expected: set[str]) -> dict[str, dict[str, Any]]:
    """Require every collected test to have a unique and valid execution receipt."""
    phases: dict[str, dict[str, dict[str, Any]]] = {}
    for line in path.read_text().splitlines():
        row = json.loads(line)
        node, phase = row["nodeid"], row["phase"]
        if node not in expected or phase not in {"setup", "call", "teardown"}:
            raise ValueError("Unexpected test or phase")
        seen = phases.setdefault(node, {})
        if phase in seen or row["outcome"] not in {"passed", "failed", "skipped"}:
            raise ValueError("Duplicate or invalid receipt")
        duration = row["seconds"]
        if not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration < 0:
            raise ValueError("Invalid test duration")
        seen[phase] = row
    if phases.keys() != expected:
        raise ValueError("Collected tests are missing execution evidence")
    result: dict[str, dict[str, Any]] = {}
    for node, seen in phases.items():
        statuses = {r["outcome"] for r in seen.values()}
        status = (
            "failed"
            if "failed" in statuses
            else "skipped"
            if "skipped" in statuses or any(r["xfail"] for r in seen.values())
            else "passed"
            if seen.keys() == {"setup", "call", "teardown"}
            else "incomplete"
        )
        result[node] = {"status": status, "seconds": sum(r["seconds"] for r in seen.values())}
    return result
