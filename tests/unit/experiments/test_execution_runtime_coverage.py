"""Allocation and resource fallback contracts for the run controller."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, cast

import pytest

from experiments.runs import execution


def _controller_repo(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "repo"
    config = root / "config"
    (config / "base").mkdir(parents=True)
    (config / "experiments.yaml").write_text(
        "variants:\n  - name: probe_variant\n", encoding="utf-8"
    )
    (config / "base" / "default.yaml").write_text(
        "data:\n  raw_dir: data\n  split:\n"
        "    train_end: '2025-12-31'\n    test_start: '2026-01-01'\n",
        encoding="utf-8",
    )
    variants = root / "variants.txt"
    variants.write_text("probe_variant\n", encoding="utf-8")
    return root, variants


def _node_cli(variants: Path, node: str, workers: str, worker_cpus: str) -> list[str]:
    return [
        "experiment_run_controller.py",
        "--variant-file",
        str(variants),
        "--seeds",
        "7",
        "--timesteps",
        "100",
        "--workers",
        workers,
        "--worker-cpus",
        worker_cpus,
        "--worker-nodes",
        node,
        "--experiment-run-id",
        "allocation-contract",
    ]


def test_auto_worker_capacity_uses_local_allocation_inventory_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, variants = _controller_repo(tmp_path)
    node = "controller-node.example"
    planned: dict[str, dict[str, Any]] = {}
    monkeypatch.setattr(execution, "ROOT", root)
    monkeypatch.setattr(cast(Any, execution).socket, "gethostname", lambda: "controller-node.local")
    monkeypatch.setattr(execution, "resolve_worker_nodes", lambda *_args, **_kwargs: [node])
    monkeypatch.setattr(
        execution,
        "available_resources",
        lambda: {"cpu_affinity": 8, "memory_limit_bytes": 128 * 1024**3},
    )
    monkeypatch.setattr(
        execution,
        "worker_node_resources",
        lambda *_args, **_kwargs: {
            "cpu_ids": list(range(9)),
            "memory_limit_bytes": 0,
            "gpu_memory": {},
        },
    )
    monkeypatch.setattr(execution, "gpu_memory_inventory", lambda: {"0": 80_000})

    def no_safe_capacity(resources: dict[str, dict[str, Any]], **_kwargs: Any) -> dict[str, Any]:
        planned.update(resources)
        return {"workers": 0, "nodes": {node: {"workers": 0}}}

    monkeypatch.setattr(execution, "plan_worker_capacity", no_safe_capacity)
    monkeypatch.setenv("SLURM_JOB_ID", "test-allocation")
    monkeypatch.setenv("EXPERIMENT_RUN_WORKER_QUEUE", str(tmp_path / "queue"))
    monkeypatch.setattr(sys, "argv", _node_cli(variants, node, "auto", "auto"))

    with pytest.raises(RuntimeError, match="no safe experiment worker capacity"):
        execution.main()

    assert planned[node]["memory_limit_bytes"] == 128 * 1024**3
    assert planned[node]["gpu_memory"] == {"0": 80_000}
    assert planned[node]["gpu_type"] == "gh200"
    assert not (root / "outputs").exists()


def test_explicit_worker_cpu_budget_limits_node_capacity_before_launch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, variants = _controller_repo(tmp_path)
    node = "gpu-node"
    monkeypatch.setattr(execution, "ROOT", root)
    monkeypatch.setattr(execution, "resolve_worker_nodes", lambda *_args, **_kwargs: [node])
    monkeypatch.setattr(
        execution,
        "available_resources",
        lambda: {"cpu_affinity": 8, "memory_limit_bytes": 128 * 1024**3},
    )
    monkeypatch.setattr(
        execution,
        "worker_node_resources",
        lambda *_args, **_kwargs: {
            "cpu_ids": list(range(5)),
            "memory_limit_bytes": 128 * 1024**3,
            "gpu_memory": {"0": 16_000},
        },
    )
    monkeypatch.setattr(
        execution,
        "plan_worker_capacity",
        lambda resources, **_kwargs: {
            "workers": 2,
            "nodes": {name: {"workers": 2} for name in resources},
        },
    )
    monkeypatch.setenv("SLURM_JOB_ID", "test-allocation")
    monkeypatch.setenv("EXPERIMENT_RUN_WORKER_QUEUE", str(tmp_path / "queue"))
    monkeypatch.setattr(sys, "argv", _node_cli(variants, node, "2", "4"))

    with pytest.raises(RuntimeError, match="capacity supports at most 1"):
        execution.main()

    assert not (root / "outputs").exists()
