"""Input validation and dry-run safety contracts for the run controller."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from experiments.runs import execution


def _repo_with_spec(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "repo"
    config = root / "config"
    (config / "base").mkdir(parents=True)
    run_configs = config / "experiment_runs"
    run_configs.mkdir()
    (config / "base" / "default.yaml").write_text(
        "data:\n  split:\n    train_end: '2025-12-31'\n    test_start: '2026-01-01'\n",
        encoding="utf-8",
    )
    (config / "experiments.yaml").write_text(
        "variants:\n  - name: probe_variant\n", encoding="utf-8"
    )
    (run_configs / "variant_list.txt").write_text("probe_variant\n", encoding="utf-8")
    spec = run_configs / "probe.yaml"
    spec.write_text(
        "experiment_run_id: coverage_probe\n"
        "variant_file: config/experiment_runs/variant_list.txt\n"
        "variants: [probe_variant]\n"
        "seeds: [7, 11]\n"
        "timesteps: 100\n"
        "data_source: frames\n"
        "split:\n  train_end: '2025-12-31'\n  test_start: '2026-01-01'\n"
        "evaluation:\n  locked_oos_role: final_report_only\n  selection_allowed: false\n  deterministic: true\n",
        encoding="utf-8",
    )
    return root, spec


def test_main_rejects_invalid_worker_counts_before_loading_a_run_spec(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for args, message in (
        (["--workers", "many"], "--workers must be a positive integer or 'auto'"),
        (["--worker-cpus", "many"], "--worker-cpus must be a positive integer or 'auto'"),
    ):
        monkeypatch.setattr(sys, "argv", ["experiment_run_controller.py", *args])
        with pytest.raises(ValueError, match=message):
            execution.main()


def test_run_spec_rejects_cli_identity_overrides_before_reading_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _root, spec = _repo_with_spec(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "experiment_run_controller.py",
            "--experiment-run-spec",
            str(spec),
            "--timesteps",
            "200",
        ],
    )

    with pytest.raises(ValueError, match="cannot be combined with experiment run identity"):
        execution.main()


def test_auto_worker_dry_run_reports_unresolved_allocation_without_launching(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, spec = _repo_with_spec(tmp_path)
    monkeypatch.setattr(execution, "ROOT", root)
    monkeypatch.setattr(execution, "resolve_worker_nodes", lambda *_args, **_kwargs: ["cpu-node"])
    monkeypatch.setattr(
        execution,
        "available_resources",
        lambda: pytest.fail("dry-run must not inspect live allocation resources"),
    )
    monkeypatch.setattr(
        execution,
        "write_experiment_run_source_snapshot",
        lambda *_args, **_kwargs: pytest.fail("dry-run must not create a source snapshot"),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "experiment_run_controller.py",
            "--experiment-run-spec",
            str(spec),
            "--dry-run",
            "--worker-nodes",
            "cpu-node",
            "--workers",
            "auto",
            "--worker-cpus",
            "auto",
        ],
    )

    assert execution.main() == 0

    output = json.loads(capsys.readouterr().out)
    assert output["experiment_run_id"] == "coverage_probe"
    assert output["keys"] == ["probe_variant__seed7", "probe_variant__seed11"]
    assert output["workers"] == "auto (resolved inside allocation)"
    assert output["worker_cpus"] == "auto (resolved per node)"
    assert output["worker_nodes"] == ["cpu-node"]
    assert output["total_timesteps"] == 200
    assert not (root / "outputs").exists()


def test_run_spec_and_benchmark_constraints_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, spec = _repo_with_spec(tmp_path)
    monkeypatch.setattr(execution, "ROOT", root)
    monkeypatch.setattr(execution, "resolve_worker_nodes", lambda *_args, **_kwargs: [])

    spec.write_text("[]\n", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        ["experiment_run_controller.py", "--experiment-run-spec", str(spec), "--dry-run"],
    )
    with pytest.raises(ValueError, match="spec must be a YAML mapping"):
        execution.main()

    _root, spec = _repo_with_spec(tmp_path / "benchmark")
    monkeypatch.setattr(execution, "ROOT", tmp_path / "benchmark" / "repo")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "experiment_run_controller.py",
            "--experiment-run-spec",
            str(spec),
            "--dry-run",
            "--benchmark",
        ],
    )
    with pytest.raises(ValueError, match="benchmark requires one run"):
        execution.main()


@pytest.mark.parametrize(
    ("spec_update", "message"),
    [
        (
            "variant_family: family-a\ncomparison_families: [family-a]\n",
            "use either variant_family or comparison_families",
        ),
        ("variant_family: '  '\n", "variant_family must be non-empty text"),
        ("comparison_families: []\n", "comparison_families must be a nonempty list"),
        (
            "comparison_families: [family-a, family-a]\n",
            "comparison_families must not contain duplicate names",
        ),
    ],
)
def test_run_spec_rejects_invalid_comparison_family_declarations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    spec_update: str,
    message: str,
) -> None:
    root, spec = _repo_with_spec(tmp_path)
    spec.write_text(
        "experiment_run_id: coverage_probe\n"
        "seeds: [7]\n"
        "timesteps: 100\n"
        "split:\n  train_end: '2025-12-31'\n  test_start: '2026-01-01'\n" + spec_update,
        encoding="utf-8",
    )
    monkeypatch.setattr(execution, "ROOT", root)
    monkeypatch.setattr(execution, "resolve_worker_nodes", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        sys,
        "argv",
        ["experiment_run_controller.py", "--experiment-run-spec", str(spec), "--dry-run"],
    )

    with pytest.raises(ValueError, match=message):
        execution.main()


def test_comparison_family_dry_run_preserves_registered_arm_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, spec = _repo_with_spec(tmp_path)
    (root / "config" / "experiments.yaml").write_text(
        "variants:\n  - name: arm-a\n  - name: arm-b\n", encoding="utf-8"
    )
    spec.write_text(
        "experiment_run_id: coverage_probe\n"
        "variant_family: family-a\n"
        "variants: [arm-a, arm-b]\n"
        "seeds: [7]\n"
        "timesteps: 100\n"
        "split:\n  train_end: '2025-12-31'\n  test_start: '2026-01-01'\n"
        "evaluation:\n  locked_oos_role: final_report_only\n  selection_allowed: false\n  deterministic: true\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(execution, "ROOT", root)
    monkeypatch.setattr(execution, "resolve_worker_nodes", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        "experiments.variants.catalog.resolve_family",
        lambda family_id: {
            "family_id": family_id,
            "entries": [{"variant": "arm-a"}, {"variant": "arm-b"}],
        },
    )
    monkeypatch.setattr(
        execution,
        "validate_inputs",
        lambda _args, variants: [
            {"key": f"{variant}__seed7", "variant": variant, "seed": 7}
            for variant in variants or []
        ],
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["experiment_run_controller.py", "--experiment-run-spec", str(spec), "--dry-run"],
    )

    assert execution.main() == 0

    output = json.loads(capsys.readouterr().out)
    assert output["variant_family"]["family_id"] == "family-a"
    assert output["keys"] == ["arm-a__seed7", "arm-b__seed7"]
    assert output["variant_file"] is None


def test_comparison_family_dry_run_rejects_variant_order_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, spec = _repo_with_spec(tmp_path)
    spec.write_text(
        "experiment_run_id: coverage_probe\n"
        "variant_family: family-a\n"
        "variants: [arm-b, arm-a]\n"
        "seeds: [7]\n"
        "timesteps: 100\n"
        "split:\n  train_end: '2025-12-31'\n  test_start: '2026-01-01'\n"
        "evaluation:\n  locked_oos_role: final_report_only\n  selection_allowed: false\n  deterministic: true\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(execution, "ROOT", root)
    monkeypatch.setattr(execution, "resolve_worker_nodes", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        "experiments.variants.catalog.resolve_family",
        lambda _family_id: {
            "family_id": "family-a",
            "entries": [{"variant": "arm-a"}, {"variant": "arm-b"}],
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["experiment_run_controller.py", "--experiment-run-spec", str(spec), "--dry-run"],
    )

    with pytest.raises(ValueError, match="must match the configured comparison family order"):
        execution.main()


@pytest.mark.parametrize(
    ("spec_update", "message"),
    [
        (
            "variant_family: family-a\nvariant_file: variants.txt\n",
            "cannot be combined with variant_file",
        ),
        ("variants: []\n", "must contain variants or comparison families"),
        (
            "variants: [probe_variant]\nsplit: {}\n",
            "split does not match the effective base configuration",
        ),
    ],
)
def test_run_spec_rejects_conflicting_variant_and_split_inputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    spec_update: str,
    message: str,
) -> None:
    root, spec = _repo_with_spec(tmp_path)
    spec.write_text(
        "experiment_run_id: coverage_probe\n"
        "seeds: [7]\n"
        "timesteps: 100\n"
        "split:\n  train_end: '2025-12-31'\n  test_start: '2026-01-01'\n"
        "evaluation:\n  locked_oos_role: final_report_only\n  selection_allowed: false\n  deterministic: true\n"
        + spec_update,
        encoding="utf-8",
    )
    monkeypatch.setattr(execution, "ROOT", root)
    monkeypatch.setattr(execution, "resolve_worker_nodes", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        "experiments.variants.catalog.resolve_family",
        lambda family_id: {
            "family_id": family_id,
            "entries": [{"variant": "probe_variant"}],
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["experiment_run_controller.py", "--experiment-run-spec", str(spec), "--dry-run"],
    )

    with pytest.raises(ValueError, match=message):
        execution.main()


def test_run_spec_rejects_variants_that_do_not_match_authoritative_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, spec = _repo_with_spec(tmp_path)
    spec.write_text(
        "experiment_run_id: coverage_probe\n"
        "variants: [another_variant]\n"
        "seeds: [7]\n"
        "timesteps: 100\n"
        "split:\n  train_end: '2025-12-31'\n  test_start: '2026-01-01'\n"
        "evaluation:\n  locked_oos_role: final_report_only\n  selection_allowed: false\n  deterministic: true\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(execution, "ROOT", root)
    monkeypatch.setattr(execution, "resolve_worker_nodes", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        sys,
        "argv",
        ["experiment_run_controller.py", "--experiment-run-spec", str(spec), "--dry-run"],
    )

    with pytest.raises(ValueError, match="do not match its authoritative variant file"):
        execution.main()


def test_worker_controller_requires_an_existing_allocation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, spec = _repo_with_spec(tmp_path)
    monkeypatch.setattr(execution, "ROOT", root)
    monkeypatch.setattr(execution, "resolve_worker_nodes", lambda *_args, **_kwargs: [])
    monkeypatch.delenv("SLURM_JOB_ID", raising=False)
    monkeypatch.setattr(
        sys,
        "argv",
        ["experiment_run_controller.py", "--experiment-run-spec", str(spec)],
    )

    with pytest.raises(RuntimeError, match="must run inside an existing Slurm compute allocation"):
        execution.main()


def test_run_spec_rejects_initial_checkpoint_map_outside_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, spec = _repo_with_spec(tmp_path)
    outside_map = tmp_path / "initial-checkpoints.json"
    monkeypatch.setattr(execution, "ROOT", root)
    monkeypatch.setattr(execution, "resolve_worker_nodes", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "experiment_run_controller.py",
            "--experiment-run-spec",
            str(spec),
            "--initial-checkpoints",
            str(outside_map),
            "--dry-run",
        ],
    )

    with pytest.raises(
        ValueError, match="initial checkpoint map must be stored inside this repository"
    ):
        execution.main()


def test_run_spec_rejects_variants_missing_from_experiment_registry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, spec = _repo_with_spec(tmp_path)
    spec.write_text(
        "experiment_run_id: coverage_probe\n"
        "variant_file: config/experiment_runs/variant_list.txt\n"
        "variants: [unregistered_variant]\n"
        "seeds: [7]\n"
        "timesteps: 100\n"
        "split:\n  train_end: '2025-12-31'\n  test_start: '2026-01-01'\n"
        "evaluation:\n  locked_oos_role: final_report_only\n  selection_allowed: false\n  deterministic: true\n",
        encoding="utf-8",
    )
    (root / "config" / "experiment_runs" / "variant_list.txt").write_text(
        "unregistered_variant\n", encoding="utf-8"
    )
    monkeypatch.setattr(execution, "ROOT", root)
    monkeypatch.setattr(execution, "resolve_worker_nodes", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        sys,
        "argv",
        ["experiment_run_controller.py", "--experiment-run-spec", str(spec), "--dry-run"],
    )

    with pytest.raises(ValueError, match="unknown variants"):
        execution.main()


@pytest.mark.parametrize(
    ("run_id", "worker_args", "message"),
    [
        ("../unsafe", [], "unsafe experiment run id"),
        ("coverage_probe", ["--worker-gpus-per-node", "0"], "worker CPU/GPU count or GPU type"),
    ],
)
def test_run_spec_rejects_unsafe_identity_and_worker_limits(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    run_id: str,
    worker_args: list[str],
    message: str,
) -> None:
    root, spec = _repo_with_spec(tmp_path)
    contents = spec.read_text(encoding="utf-8").replace("coverage_probe", run_id)
    spec.write_text(contents, encoding="utf-8")
    monkeypatch.setattr(execution, "ROOT", root)
    monkeypatch.setattr(execution, "resolve_worker_nodes", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "experiment_run_controller.py",
            "--experiment-run-spec",
            str(spec),
            "--dry-run",
            *worker_args,
        ],
    )

    with pytest.raises(ValueError, match=message):
        execution.main()


def test_explicit_worker_count_cannot_be_lower_than_node_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, spec = _repo_with_spec(tmp_path)
    monkeypatch.setattr(execution, "ROOT", root)
    monkeypatch.setattr(
        execution, "resolve_worker_nodes", lambda *_args, **_kwargs: ["node-a", "node-b"]
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "experiment_run_controller.py",
            "--experiment-run-spec",
            str(spec),
            "--worker-nodes",
            "node-a,node-b",
            "--workers",
            "1",
        ],
    )

    with pytest.raises(
        ValueError, match="worker count must be at least the number of worker nodes"
    ):
        execution.main()


@pytest.mark.parametrize(
    ("n_envs", "memory_limit_bytes", "message"),
    [
        (3, 128 * 1024**3, "n-envs not benchmarked for memory"),
        (4, 1024**3, "insufficient cgroup RAM"),
    ],
)
def test_local_worker_preflight_rejects_unbenchmarked_or_oversized_requests(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    n_envs: int,
    memory_limit_bytes: int,
    message: str,
) -> None:
    root, spec = _repo_with_spec(tmp_path)
    monkeypatch.setattr(execution, "ROOT", root)
    monkeypatch.setattr(execution, "resolve_worker_nodes", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        execution,
        "available_resources",
        lambda: {"cpu_affinity": 16, "memory_limit_bytes": memory_limit_bytes},
    )
    monkeypatch.setenv("SLURM_JOB_ID", "test-allocation")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "experiment_run_controller.py",
            "--experiment-run-spec",
            str(spec),
            "--n-envs",
            str(n_envs),
        ],
    )

    error = ValueError if n_envs == 3 else RuntimeError
    with pytest.raises(error, match=message):
        execution.main()


def test_auto_workers_requires_worker_nodes_in_an_existing_allocation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, spec = _repo_with_spec(tmp_path)
    monkeypatch.setattr(execution, "ROOT", root)
    monkeypatch.setattr(execution, "resolve_worker_nodes", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        execution,
        "available_resources",
        lambda: {"cpu_affinity": 8, "memory_limit_bytes": 128 * 1024**3},
    )
    monkeypatch.setenv("SLURM_JOB_ID", "test-allocation")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "experiment_run_controller.py",
            "--experiment-run-spec",
            str(spec),
            "--workers",
            "auto",
        ],
    )

    with pytest.raises(ValueError, match="--workers auto requires --worker-nodes"):
        execution.main()

    assert not (root / "outputs").exists()


def test_requested_node_workers_cannot_exceed_advertised_capacity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, spec = _repo_with_spec(tmp_path)
    monkeypatch.setattr(execution, "ROOT", root)
    monkeypatch.setattr(execution, "resolve_worker_nodes", lambda *_args, **_kwargs: ["gpu-node"])
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
            "memory_limit_bytes": 128 * 1024**3,
            "gpu_memory": {"0": 16_000},
        },
    )
    monkeypatch.setattr(
        execution,
        "plan_worker_capacity",
        lambda resources, **_kwargs: {
            "workers": 1,
            "nodes": {node: {"workers": 1} for node in resources},
        },
    )
    monkeypatch.setenv("SLURM_JOB_ID", "test-allocation")
    monkeypatch.setenv("EXPERIMENT_RUN_WORKER_QUEUE", str(tmp_path / "worker-queue"))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "experiment_run_controller.py",
            "--experiment-run-spec",
            str(spec),
            "--worker-nodes",
            "gpu-node",
            "--workers",
            "2",
            "--worker-cpus",
            "4",
        ],
    )

    with pytest.raises(RuntimeError, match="capacity supports at most 1"):
        execution.main()

    assert not (root / "outputs").exists()
