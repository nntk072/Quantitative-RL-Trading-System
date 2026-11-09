#!/usr/bin/env python3
"""Validate the exact 162-task V3 execution catalog and repository tool references."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from omegaconf import OmegaConf

from configuration.paths import repository_root

ROOT = repository_root(__file__)
DEFAULT_CATALOG = ROOT / "config/research/v3_full_todo_catalog.yaml"
ALLOWED_KINDS = {
    "operational",
    "provenance",
    "protocol",
    "runtime_evidence",
    "implementation",
    "diagnostic_or_benchmark",
    "experiment",
    "post_experiment_validation",
    "post_result_evidence",
    "reporting",
    "release",
}
ALLOWED_LANES = {"A", "B", "C", "D", "E", "F"}
ALLOWED_BARRIERS = {None, "B0", "B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8"}
CRITICAL_TOOL_TODOS = {
    11,
    20,
    24,
    25,
    27,
    28,
    29,
    35,
    36,
    37,
    38,
    40,
    41,
    43,
    53,
    54,
    59,
    60,
    84,
    86,
    88,
    89,
    90,
    92,
    93,
    94,
    95,
    100,
    101,
    102,
    103,
    104,
    105,
    106,
    107,
    109,
    110,
    111,
    113,
    114,
    116,
    117,
    120,
    121,
    122,
    123,
    124,
    127,
    128,
    129,
    130,
    131,
    132,
    133,
    134,
    135,
    136,
    137,
    138,
    140,
    141,
    142,
    143,
    144,
    145,
    146,
    147,
    148,
    149,
    150,
    151,
    155,
    156,
    158,
    159,
    160,
    161,
    162,
}


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a mapping")
    return value


def load_catalog(path: Path = DEFAULT_CATALOG) -> dict[str, Any]:
    value = OmegaConf.to_container(OmegaConf.load(path), resolve=True)
    root = dict(_mapping(value, "catalog"))
    if root.get("schema_version") != "v3-full-todo-catalog-v1":
        raise ValueError("unsupported V3 full TODO catalog schema")
    tasks = root.get("tasks")
    if not isinstance(tasks, list) or len(tasks) != 162:
        raise ValueError("catalog must contain exactly 162 tasks")

    ids: list[int] = []
    by_id: dict[int, dict[str, Any]] = {}
    for row_value in tasks:
        row = dict(_mapping(row_value, "task"))
        task_id = row.get("id")
        if isinstance(task_id, bool) or not isinstance(task_id, int):
            raise ValueError("task IDs must be integers")
        ids.append(task_id)
        by_id[task_id] = row
        if not str(row.get("title", "")).strip():
            raise ValueError(f"TODO {task_id} title is empty")
        if row.get("kind") not in ALLOWED_KINDS:
            raise ValueError(f"TODO {task_id} has invalid kind")
        if row.get("lane") not in ALLOWED_LANES:
            raise ValueError(f"TODO {task_id} has invalid lane")
        if row.get("barrier") not in ALLOWED_BARRIERS:
            raise ValueError(f"TODO {task_id} has invalid barrier")
        if row.get("experiment_dependent") not in {True, False}:
            raise ValueError(f"TODO {task_id} experiment_dependent must be boolean")
        if not isinstance(row.get("execution_mode"), str) or not row["execution_mode"]:
            raise ValueError(f"TODO {task_id} lacks execution_mode")
        dependencies = row.get("dependencies")
        if not isinstance(dependencies, list) or any(
            isinstance(dep, bool) or not isinstance(dep, int) for dep in dependencies
        ):
            raise ValueError(f"TODO {task_id} dependencies must be integer IDs")
        if task_id in dependencies:
            raise ValueError(f"TODO {task_id} cannot depend on itself")
        tools = row.get("canonical_tools")
        if not isinstance(tools, list) or any(not isinstance(tool, str) for tool in tools):
            raise ValueError(f"TODO {task_id} canonical_tools must be strings")
        if task_id in CRITICAL_TOOL_TODOS and not tools:
            raise ValueError(f"critical TODO {task_id} has no canonical tool")
        for tool in tools:
            if not (ROOT / tool).exists():
                raise ValueError(f"TODO {task_id} references missing repository path: {tool}")
        if not str(row.get("completion_control", "")).strip():
            raise ValueError(f"TODO {task_id} lacks completion control")
        if not str(row.get("pass_criterion", "")).strip():
            raise ValueError(f"TODO {task_id} pass criterion is empty")

    if ids != list(range(1, 163)):
        raise ValueError("catalog task IDs must be exactly 1..162 in order")
    for task_id, row in by_id.items():
        unknown = set(row["dependencies"]) - set(by_id)
        if unknown:
            raise ValueError(f"TODO {task_id} has unknown dependencies: {sorted(unknown)}")

    visiting: set[int] = set()
    visited: set[int] = set()

    def visit(task_id: int) -> None:
        if task_id in visited:
            return
        if task_id in visiting:
            raise ValueError(f"dependency cycle at TODO {task_id}")
        visiting.add(task_id)
        for dependency in by_id[task_id]["dependencies"]:
            visit(dependency)
        visiting.remove(task_id)
        visited.add(task_id)

    for task_id in by_id:
        visit(task_id)

    expected_barriers = {
        "B0": set(range(1, 8)),
        "B1": set(range(13, 25)),
        "B2": set(range(25, 63)),
        "B3": set(range(63, 83)),
        "B4": {83, 84},
        "B5": set(range(85, 107)),
        "B6": set(range(107, 115)),
        "B7": set(range(119, 127)),
        "B8": set(range(127, 152)),
    }
    barriers = _mapping(root.get("barriers"), "barriers")
    if set(barriers) != set(expected_barriers):
        raise ValueError("catalog barriers must be exactly B0 through B8")
    for barrier_id, expected in expected_barriers.items():
        raw = _mapping(barriers.get(barrier_id), barrier_id).get("requires")
        if not isinstance(raw, list) or len(raw) != len(expected) or set(raw) != expected:
            raise ValueError(f"{barrier_id} does not match the V3 contract")

    root["tasks_by_id"] = by_id
    return root


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    args = parser.parse_args()
    catalog = load_catalog(args.catalog)
    print(
        json.dumps(
            {
                "schema_version": catalog["schema_version"],
                "todo_count": len(catalog["tasks"]),
                "first_todo": catalog["tasks"][0]["id"],
                "last_todo": catalog["tasks"][-1]["id"],
                "critical_tool_todo_count": len(CRITICAL_TOOL_TODOS),
                "canonical_tool_references_valid": True,
                "dependency_graph_valid": True,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
