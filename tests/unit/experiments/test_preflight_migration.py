"""Tests for the guarded experiment-run identity migration preflight."""

from __future__ import annotations

import json
import runpy
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


def _run_initial_migration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, dict[str, Any], dict[str, Any], Path]:
    run_root, original_manifest = _prepare_migration(tmp_path, monkeypatch)
    assert migration.main() == 0
    manifest_path = run_root / "experiment_run.json"
    migrated_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    migration_path = run_root / migrated_manifest["preflight_migration"]
    return run_root, original_manifest, migrated_manifest, migration_path


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


def test_main_rejects_unexpected_p7_nodes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _run_root, _manifest = _prepare_migration(tmp_path, monkeypatch)
    monkeypatch.setattr(migration, "expand_slurm_hosts", lambda _hosts: ["gpuarm1"])

    with pytest.raises(RuntimeError, match="unexpected P7 allocation nodes"):
        migration.main()


def test_main_rejects_missing_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run_root, _manifest = _prepare_migration(tmp_path, monkeypatch)
    (run_root / "experiment_run.json").unlink()

    with pytest.raises(FileNotFoundError, match="manifest is missing"):
        migration.main()


def test_main_rejects_variant_file_that_differs_from_specification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_root, _manifest = _prepare_migration(tmp_path, monkeypatch)
    repo = run_root.parents[2]
    variants_path = repo / "config" / "experiment_runs" / "variants.txt"
    variants_path.write_text("variant_b\n", encoding="utf-8")

    with pytest.raises(ValueError, match="authoritative variant file disagree"):
        migration.main()

    assert (run_root / "experiment_run.json").is_file()


def test_main_rejects_manifest_job_keys_that_differ_from_specification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_root, _manifest = _prepare_migration(tmp_path, monkeypatch)
    manifest_path = run_root / "experiment_run.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["jobs"][0]["key"] = "other__seed42"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="differ from the frozen specification"):
        migration.main()


def test_main_rejects_frozen_manifest_configuration_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_root, _manifest = _prepare_migration(tmp_path, monkeypatch)
    manifest_path = run_root / "experiment_run.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["timesteps"] += 1
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="no longer matches the frozen P7 specification"):
        migration.main()


def test_main_rejects_unrecognized_migrated_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_root, _original, migrated, _migration_path = _run_initial_migration(tmp_path, monkeypatch)
    manifest_path = run_root / "experiment_run.json"
    migrated["workers"] = 3
    manifest_path.write_text(json.dumps(migrated), encoding="utf-8")

    with pytest.raises(RuntimeError, match="neither the preserved preflight identity"):
        migration.main()


def test_main_rejects_migrated_source_changed_after_fingerprint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_root, _original, _migrated, _migration_path = _run_initial_migration(tmp_path, monkeypatch)
    repo = run_root.parents[2]
    source_file = repo / "config" / "experiment_runs" / "source.py"
    source_file.write_text("SOURCE = 'changed'\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="source changed after fingerprint migration"):
        migration.main()


@pytest.mark.parametrize(
    ("snapshot", "expected_message"),
    [
        (None, "source snapshot record is missing"),
        ({"path": "nested/source_snapshot.zip"}, "escapes experiment run directory"),
        ({"path": "source_snapshot_missing.zip", "sha256": "bad"}, "snapshot is invalid"),
    ],
)
def test_main_rejects_unreadable_or_unsafe_migrated_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    snapshot: dict[str, Any] | None,
    expected_message: str,
) -> None:
    run_root, _original, migrated, _migration_path = _run_initial_migration(tmp_path, monkeypatch)
    manifest_path = run_root / "experiment_run.json"
    migrated["source_snapshot"] = snapshot
    manifest_path.write_text(json.dumps(migrated), encoding="utf-8")

    with pytest.raises(RuntimeError, match=expected_message):
        migration.main()


def test_main_rejects_original_worker_identity_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_root, _manifest = _prepare_migration(tmp_path, monkeypatch)
    manifest_path = run_root / "experiment_run.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["worker_cpus"] = 47
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(RuntimeError, match="original experiment run identity differs"):
        migration.main()


@pytest.mark.parametrize(
    ("snapshot", "expected_exception", "expected_message"),
    [
        (None, ValueError, "original source snapshot record is missing"),
        (
            {"path": "nested/source_snapshot_original.zip"},
            ValueError,
            "original source snapshot path escapes",
        ),
    ],
)
def test_main_rejects_missing_or_nested_original_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    snapshot: dict[str, Any] | None,
    expected_exception: type[Exception],
    expected_message: str,
) -> None:
    run_root, _original = _prepare_migration(tmp_path, monkeypatch)
    manifest_path = run_root / "experiment_run.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["source_snapshot"] = snapshot
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(expected_exception, match=expected_message):
        migration.main()


def test_main_rejects_snapshot_manifest_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_root, _original = _prepare_migration(tmp_path, monkeypatch)
    manifest_path = run_root / "experiment_run.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["source_hashes"] = {"different.py": "0" * 64}
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(RuntimeError, match="snapshot and manifest disagree"):
        migration.main()


def test_main_rejects_existing_preserved_copy_with_different_contents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_root, original, _migrated, _migration_path = _run_initial_migration(tmp_path, monkeypatch)
    preserved_manifest = run_root / "reports" / "preflight_manifest_old-fingerprint.json"
    preserved_manifest.write_text("different contents", encoding="utf-8")
    (run_root / "experiment_run.json").write_text(json.dumps(original), encoding="utf-8")

    with pytest.raises(RuntimeError, match="preserved preflight artifact differs"):
        migration.main()


@pytest.mark.parametrize(
    ("runtime_machine", "expected_message"),
    [("x86_64", "require the native GH200 architecture")],
)
def test_main_rejects_runtime_on_unsupported_architecture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    runtime_machine: str,
    expected_message: str,
) -> None:
    run_root, _manifest = _prepare_migration(tmp_path, monkeypatch)
    monkeypatch.setattr(
        migration,
        "runtime_metadata",
        lambda: {"machine": runtime_machine, "python": "3.12", "packages": {}},
    )

    with pytest.raises(RuntimeError, match=expected_message):
        migration.main()


def test_main_rejects_changed_configured_data_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _run_root, _manifest = _prepare_migration(tmp_path, monkeypatch)
    monkeypatch.setattr(migration, "experiment_run_data_inputs", lambda _config: {"dataset": "new"})

    with pytest.raises(RuntimeError, match="configured market-data inputs changed"):
        migration.main()


def test_main_accepts_matching_existing_migration_record_and_preserved_copies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_root, original, _migrated, migration_path = _run_initial_migration(tmp_path, monkeypatch)
    (run_root / "experiment_run.json").write_text(json.dumps(original), encoding="utf-8")

    assert migration.main() == 0
    assert migration_path.is_file()


def test_main_rejects_conflicting_existing_migration_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_root, original, _migrated, migration_path = _run_initial_migration(tmp_path, monkeypatch)
    migration_record = json.loads(migration_path.read_text(encoding="utf-8"))
    migration_record["previous_fingerprint"] = "conflict"
    migration_path.write_text(json.dumps(migration_record), encoding="utf-8")
    (run_root / "experiment_run.json").write_text(json.dumps(original), encoding="utf-8")

    with pytest.raises(RuntimeError, match="record conflicts with this migration"):
        migration.main()


def test_module_entrypoint_requires_cli_arguments(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["preflight_migration"])
    module_path = migration.__file__
    assert module_path is not None

    with pytest.raises(SystemExit) as raised:
        runpy.run_path(module_path, run_name="__main__")

    assert raised.value.code == 2
