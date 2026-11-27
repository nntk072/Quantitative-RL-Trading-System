"""Allocation-boundary contracts for the experiment controller."""

from __future__ import annotations

import sys
from pathlib import Path

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


def _cli(variants: Path, n_envs: int, *, data_source: str | None = None) -> list[str]:
    args = [
        "experiment_run_controller.py",
        "--variant-file",
        str(variants),
        "--seeds",
        "7",
        "--timesteps",
        "100",
        "--workers",
        "1",
        "--n-envs",
        str(n_envs),
        "--experiment-run-id",
        "allocation-boundary",
    ]
    if data_source is not None:
        args.extend(("--data-source", data_source))
    return args


def _use_local_allocation(
    monkeypatch: pytest.MonkeyPatch, root: Path, *, cpus: int, memory_bytes: int
) -> None:
    monkeypatch.setattr(execution, "ROOT", root)
    monkeypatch.setattr(execution, "resolve_worker_nodes", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        execution,
        "available_resources",
        lambda: {"cpu_affinity": cpus, "memory_limit_bytes": memory_bytes},
    )
    monkeypatch.setenv("SLURM_JOB_ID", "test-allocation")


def test_slurm_memory_fallback_enforces_local_ram_admission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, variants = _controller_repo(tmp_path)
    _use_local_allocation(monkeypatch, root, cpus=16, memory_bytes=0)
    monkeypatch.setenv("SLURM_MEM_PER_NODE", "1024")
    monkeypatch.setattr(sys, "argv", _cli(variants, 8))

    with pytest.raises(RuntimeError, match="insufficient cgroup RAM: needs >= 89 GiB"):
        execution.main()

    assert not (root / "outputs").exists()


def test_unparseable_slurm_memory_does_not_mask_cpu_environment_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, variants = _controller_repo(tmp_path)
    _use_local_allocation(monkeypatch, root, cpus=1, memory_bytes=0)
    monkeypatch.setenv("SLURM_MEM_PER_NODE", "1G")
    monkeypatch.setattr(sys, "argv", _cli(variants, 4))

    with pytest.raises(
        RuntimeError, match="requested vector environments exceed 2 per available CPU"
    ):
        execution.main()

    assert not (root / "outputs").exists()


def test_bundle_64_environment_memory_estimate_uses_bundle_worker_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, variants = _controller_repo(tmp_path)
    _use_local_allocation(monkeypatch, root, cpus=16, memory_bytes=1024**3)
    monkeypatch.delenv("SLURM_MEM_PER_NODE", raising=False)
    monkeypatch.setattr(sys, "argv", _cli(variants, 64, data_source="bundle"))

    with pytest.raises(RuntimeError, match="insufficient cgroup RAM: needs >= 104 GiB"):
        execution.main()

    assert not (root / "outputs").exists()
