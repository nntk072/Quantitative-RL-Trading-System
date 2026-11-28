"""Collect exact test inventories and execute duration-balanced local test shards."""

from __future__ import annotations

import json
import math
import statistics
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from tools.quality.local_checks.receipts import read_collected_inventory, validate_test_receipts
from tools.quality.local_checks.resources import discover_worker_capacity
from tools.quality.local_checks.run_evidence import run_quality_process, write_quality_json

PLUGIN = "tools.quality.local_checks.pytest_receipts"


def collect_test_inventory(
    out: Path, timeout: int, paths: list[str], marker: str
) -> dict[str, Any]:
    """Collect exact node IDs with the project-owned pytest marker rules."""
    if not paths or any(p.startswith("-") for p in paths):
        raise ValueError("Expected explicit test paths")
    target = out / "test-inventory.json"
    run = run_quality_process(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            PLUGIN,
            "--collect-only",
            "-q",
            "-m",
            marker,
            *paths,
        ],
        out / "collection.log",
        timeout,
        env={"QRL_LOCAL_INVENTORY": str(target)},
    )
    if run["status"] != "ok":
        return {"status": "incomplete", "collection": run}
    rows = read_collected_inventory([target])
    return {"status": "ok", "inventory": rows, "count": len(rows)}


def read_test_duration_history(receipts: list[Path]) -> dict[str, float]:
    """Compute median total per-test durations across distinct supplied executions."""
    history: dict[str, list[float]] = {}
    for path in receipts:
        durations: dict[str, float] = {}
        for line in path.read_text().splitlines():
            row = json.loads(line)
            seconds = float(row["seconds"])
            if not math.isfinite(seconds) or seconds < 0:
                raise ValueError("Invalid test duration")
            node = row["nodeid"]
            durations[node] = durations.get(node, 0.0) + seconds
        for node, duration in durations.items():
            history.setdefault(node, []).append(duration)
    return {node: statistics.median(values) for node, values in history.items()}


def balance_test_shards(
    rows: list[dict[str, Any]], durations: dict[str, float], count: int, affinity: bool
) -> list[dict[str, Any]]:
    """Use longest-first balancing; keep file-level fixtures together on request."""
    nodes = [row["nodeid"] for row in rows]
    if not nodes or len(nodes) != len(set(nodes)) or count < 1:
        raise ValueError("Invalid inventory or shard count")
    if any(not math.isfinite(v) or v < 0 for v in durations.values()):
        raise ValueError("Invalid historical durations")
    groups: dict[str, list[str]] = {}
    for node in nodes:
        key = node.split("::", 1)[0] if affinity else node
        groups.setdefault(key, []).append(node)
    fallback = statistics.median(durations.values()) if durations else 1.0
    weights = {
        name: sum(durations.get(n, fallback) for n in group) for name, group in groups.items()
    }
    shards: list[dict[str, Any]] = [
        {"nodes": [], "seconds": 0.0} for _ in range(min(count, len(groups)))
    ]
    for name in sorted(groups, key=lambda key: (-weights[key], key)):
        target = min(shards, key=lambda row: (row["seconds"], len(row["nodes"])))
        target["nodes"].extend(groups[name])
        target["seconds"] += weights[name]
    if sorted(nodes) != sorted(n for row in shards for n in row["nodes"]):
        raise ValueError("Shard inventory mismatch")
    return shards


def _execute_test_shard(
    index: int, shard: dict[str, Any], out: Path, timeout: int, paths: list[str], marker: str
) -> dict[str, Any]:
    """Execute one selected shard using a selection file, then reconcile all receipts."""
    directory = out / f"shard-{index}"
    directory.mkdir()
    selection = directory / "selected-nodes.json"
    write_quality_json(selection, shard["nodes"])
    inventory = directory / "inventory.json"
    receipts = directory / "receipts.jsonl"
    run = run_quality_process(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            PLUGIN,
            "-q",
            "-m",
            marker,
            *paths,
            f"--junitxml={directory / 'junit.xml'}",
        ],
        directory / "pytest.log",
        timeout,
        findings_codes=(1,),
        env={
            "QRL_LOCAL_SELECTION": str(selection),
            "QRL_LOCAL_INVENTORY": str(inventory),
            "QRL_LOCAL_RECEIPTS": str(receipts),
            "OMP_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
        },
    )
    if run["status"] not in {"ok", "findings"}:
        return run
    rows = read_collected_inventory([inventory])
    expected = set(shard["nodes"])
    if {row["nodeid"] for row in rows} != expected:
        raise ValueError("Shard did not collect its assigned test inventory")
    outcomes = validate_test_receipts(receipts, expected)
    write_quality_json(directory / "outcomes.json", outcomes)
    return {
        **run,
        "status": "incomplete"
        if any(r["status"] == "incomplete" for r in outcomes.values())
        else "findings"
        if any(r["status"] == "failed" for r in outcomes.values())
        else "ok",
        "count": len(rows),
    }


def run_balanced_test_shards(
    out: Path,
    timeout: int,
    paths: list[str],
    marker: str,
    count: int,
    workers: int,
    memory_mib: int,
    history: list[Path],
    affinity: bool,
) -> dict[str, Any]:
    """Collect, plan and run with affinity/cgroup/memory limits and isolated receipts."""
    collected = collect_test_inventory(out, timeout, paths, marker)
    if collected["status"] != "ok":
        return collected
    shards = balance_test_shards(
        collected["inventory"], read_test_duration_history(history), count, affinity
    )
    capacity = discover_worker_capacity(workers, memory_mib)
    write_quality_json(out / "shards.json", shards)
    write_quality_json(out / "resource-budget.json", capacity)
    if capacity["workers"] == 0:
        return {"status": "insufficient_resources", "capacity": capacity}
    with ThreadPoolExecutor(max_workers=min(capacity["workers"], len(shards))) as pool:
        futures = [
            pool.submit(_execute_test_shard, i, shard, out, timeout, paths, marker)
            for i, shard in enumerate(shards)
        ]
        runs = [future.result() for future in futures]
    return {
        "status": "incomplete"
        if any(run["status"] not in {"ok", "findings"} for run in runs)
        else "findings"
        if any(run["status"] == "findings" for run in runs)
        else "ok",
        "shards": shards,
        "capacity": capacity,
        "runs": runs,
    }
