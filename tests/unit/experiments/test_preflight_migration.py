"""Tests for the guarded experiment-run identity migration preflight."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

from experiments.runs import preflight_migration as migration
from experiments.runs import source_snapshot


def _prepare_migration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, dict[str, Any]]:
    repo = tmp_path / "repo"
    run_id = "test_run"
    run_root = repo / "outputs" / "gpu_experiment_runs" / run_id
    run_root.mkdir(parents=True)
    config_root = repo / "config" / "experiment_runs"
    config_root.mkdir(parents=True)
    base_config = repo / "config" / "base"
    base_config.mkdir(parents=True)
    (base_config / "default.yaml").write_text("data: {}\n", encoding="utf-8")
    variants_path = config_root / "variants.txt"
    variants_path.write_text("variant_a\n", encoding="utf-8")
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text(
        yaml.safe_dump(
            {
                "experiment_run_id": run_id,
                "variant_file": "config/experiment_runs/variants.txt",
                "variants": ["variant_a"],
                "seeds": [42],
                "timesteps": 100,
                "n_envs": 8,
                "data_source": "frames",
                "evaluation": {},
            }
        ),
        encoding="utf-8",
    )
    source_file = config_root / "source.py"
    source_file.write_text("SOURCE = 'frozen'\n", encoding="utf-8")
    source_hash = source_snapshot.sha256_file(source_file)
    source_hashes = {source_file.relative_to(repo).as_posix(): source_hash}
    snapshot_path = run_root / "source_snapshot_original.zip"
    original_snapshot = source_snapshot.write_experiment_run_source_snapshot(
        repo,
        [source_file],
        snapshot_path,
        git_sha="a" * 40,
        expected_source_hashes=source_hashes,
    )
    manifest: dict[str, Any] = {
        "fingerprint": "old-fingerprint",
        "git_sha": "a" * 40,
        "timesteps": 100,
        "n_envs": 8,
        "data_source": "frames",
        "evaluation": {},
        "fast_reports": False,
        "jobs": [{"key": "variant_a__seed42", "status": "pending", "attempts": 0}],
        "workers": 1,
        "worker_nodes": ["gpuarm1"],
        "worker_cpus": 48,
        "source_hashes": source_hashes,
        "data_inputs": {"dataset": "fixture"},
        "source_snapshot": original_snapshot,
    }
    (run_root / "experiment_run.json").write_text(json.dumps(manifest), encoding="utf-8")

    monkeypatch.setattr(migration, "ROOT", repo)
    monkeypatch.setattr(migration, "expand_slurm_hosts", lambda _hosts: ["gpuarm1", "gpuarm2"])
    monkeypatch.setattr(migration, "validate_experiment_run_evaluation", lambda value: value)
    monkeypatch.setattr(
        migration, "experiment_run_data_inputs", lambda _config: {"dataset": "fixture"}
    )
    monkeypatch.setattr(
        migration, "experiment_run_source_files", lambda _root, _spec: [source_file]
    )
    monkeypatch.setattr(
        migration,
        "runtime_metadata",
        lambda: {"machine": "aarch64", "python": "3.12", "packages": {"torch": "test"}},
    )
    monkeypatch.setenv("SLURM_JOB_ID", "12345")
    monkeypatch.setenv("SLURM_JOB_NODELIST", "gpuarm[1-2]")
    monkeypatch.setenv("SLURM_NNODES", "2")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "preflight_migration",
            "--experiment-run-id",
            run_id,
            "--experiment-run-spec",
            str(spec_path),
            "--expected-fingerprint",
            "old-fingerprint",
            "--workers",
            "2",
            "--worker-cpus",
            "47",
            "--worker-gpu-type",
            "GH200",
            "--worker-gpus-per-node",
            "1",
        ],
    )
    return run_root, manifest


def test_main_records_preflight_migration_and_accepts_exact_rerun(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_root, original_manifest = _prepare_migration(tmp_path, monkeypatch)

    assert migration.main() == 0

    updated_manifest = json.loads((run_root / "experiment_run.json").read_text(encoding="utf-8"))
    assert updated_manifest["fingerprint"] != original_manifest["fingerprint"]
    assert updated_manifest["workers"] == 2
    assert updated_manifest["worker_nodes"] == ["gpuarm1", "gpuarm2"]
    assert updated_manifest["worker_cpus"] == 47
    assert updated_manifest["preflight_migration"].startswith("reports/")
    migration_path = run_root / updated_manifest["preflight_migration"]
    record = json.loads(migration_path.read_text(encoding="utf-8"))
    assert record["previous_fingerprint"] == "old-fingerprint"
    assert record["new_fingerprint"] == updated_manifest["fingerprint"]
    assert record["trainer_attempts_before_migration"] == 0
    assert (run_root / "reports" / "preflight_manifest_old-fingerprint.json").is_file()
    assert (run_root / "source_snapshot_preflight_old-fingerprint.zip").is_file()

    # Rerunning with the preserved old identity recognizes the exact migration.
    assert migration.main() == 0


@pytest.mark.parametrize(
    ("environment", "expected_message"),
    [
        ({"SLURM_JOB_ID": None}, "approved two-node allocation"),
        ({"SLURM_NNODES": "1"}, "approved two-node allocation"),
    ],
)
def test_main_rejects_calls_outside_approved_two_node_allocation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    environment: dict[str, str | None],
    expected_message: str,
) -> None:
    _run_root, _manifest = _prepare_migration(tmp_path, monkeypatch)
    for key, value in environment.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)

    with pytest.raises(RuntimeError, match=expected_message):
        migration.main()


def test_main_rejects_unreviewed_worker_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _run_root, _manifest = _prepare_migration(tmp_path, monkeypatch)
    argv = list(sys.argv)
    argv[argv.index("--workers") + 1] = "3"
    monkeypatch.setattr(sys, "argv", argv)

    with pytest.raises(RuntimeError, match="migration parameters differ"):
        migration.main()


def test_main_rejects_specification_with_different_run_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _run_root, _manifest = _prepare_migration(tmp_path, monkeypatch)
    spec_path = Path(sys.argv[sys.argv.index("--experiment-run-spec") + 1])
    spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    spec["experiment_run_id"] = "another_run"
    spec_path.write_text(yaml.safe_dump(spec), encoding="utf-8")

    with pytest.raises(ValueError, match="does not match the experiment run ID"):
        migration.main()


def test_main_rejects_manifest_after_a_trainer_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_root, _manifest = _prepare_migration(tmp_path, monkeypatch)
    manifest_path = run_root / "experiment_run.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["jobs"][0].update(status="running", attempts=1)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(RuntimeError, match="only before the first trainer attempt"):
        migration.main()


@pytest.mark.parametrize("artifact", ["checkpoint", "marker"])
def test_main_rejects_existing_training_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, artifact: str
) -> None:
    run_root, _manifest = _prepare_migration(tmp_path, monkeypatch)
    if artifact == "checkpoint":
        checkpoint = run_root / "runs" / "attempts" / "variant_a__seed42" / "ppo_100_steps.zip"
        checkpoint.parent.mkdir(parents=True)
        checkpoint.write_bytes(b"test checkpoint")
    else:
        marker = run_root / "markers" / "variant_a__seed42.done"
        marker.parent.mkdir(parents=True)
        marker.touch()

    with pytest.raises(RuntimeError, match="checkpoints exist|markers exist"):
        migration.main()


def test_main_rejects_invalid_preserved_source_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_root, _manifest = _prepare_migration(tmp_path, monkeypatch)
    manifest_path = run_root / "experiment_run.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["source_snapshot"]["sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(RuntimeError, match="source snapshot is invalid"):
        migration.main()
