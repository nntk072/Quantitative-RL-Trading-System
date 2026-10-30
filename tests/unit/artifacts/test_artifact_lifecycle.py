from __future__ import annotations

import hashlib
import json
import os
import stat
from datetime import datetime
from pathlib import Path

import pytest

from artifacts.atomic import _atomic_replace, write_json_atomic, write_text_atomic
from artifacts.identity import ArtifactId, artifact_id, file_sha256
from artifacts.layout import ArtifactLayout
from artifacts.manifest import ArtifactManifest


def test_artifact_id_is_stable_for_mapping_order() -> None:
    first = artifact_id("dataset", {"symbol": "US100", "timeframe": "M1"})
    second = artifact_id("dataset", {"timeframe": "M1", "symbol": "US100"})

    assert first == second
    assert isinstance(first, ArtifactId)
    assert str(first) == f"dataset:{first.digest}"


def test_file_sha256_matches_standard_digest_for_empty_and_nonempty_files(
    tmp_path: Path,
) -> None:
    payload = b"artifact bytes\x00with boundaries"
    nonempty = tmp_path / "payload.bin"
    empty = tmp_path / "empty.bin"
    nonempty.write_bytes(payload)
    empty.write_bytes(b"")

    assert file_sha256(nonempty) == hashlib.sha256(payload).hexdigest()
    assert file_sha256(empty) == hashlib.sha256(b"").hexdigest()


def test_timestamped_run_path_keeps_existing_layout_without_creating_directory(
    tmp_path: Path,
) -> None:
    layout = ArtifactLayout(tmp_path)
    timestamp = datetime(2026, 10, 30, 12, 31, 44, 123456)

    run_path = layout.timestamped_run("rl_train_seed42_tcn", timestamp=timestamp)

    assert run_path == tmp_path / "20261030_123144_123456_rl_train_seed42_tcn"
    assert not run_path.exists()


@pytest.mark.parametrize(
    "builder, value, label",
    [
        ("run", "../outside", "run id"),
        ("experiment_run", "/tmp/experiment_run", "experiment run id"),
        ("evaluation", "nested/run", "evaluation id"),
        ("timestamped_run", "../outside", "run name"),
    ],
)
def test_artifact_layout_rejects_path_components(
    tmp_path: Path, builder: str, value: str, label: str
) -> None:
    layout = ArtifactLayout(tmp_path)

    with pytest.raises(ValueError, match=f"unsafe {label}"):
        getattr(layout, builder)(value)


def test_artifact_layout_keeps_safe_run_namespaces(tmp_path: Path) -> None:
    layout = ArtifactLayout(tmp_path)

    assert layout.run("run_seed42_tcn") == tmp_path / "runs" / "run_seed42_tcn"
    assert layout.experiment_run("experiment-run-20261030") == (
        tmp_path / "experiment_runs" / "experiment-run-20261030"
    )
    assert layout.evaluation("checkpoint-replay.v1") == (
        tmp_path / "evaluation" / "checkpoint-replay.v1"
    )


def test_gpu_experiment_run_layout_preserves_existing_paths_and_names_artifact_roles(
    tmp_path: Path,
) -> None:
    artifacts = ArtifactLayout(tmp_path).gpu_experiment_run("matrix-20261030")

    assert artifacts.root == tmp_path / "gpu_experiment_runs" / "matrix-20261030"
    assert artifacts.manifest == artifacts.root / "experiment_run.json"
    assert artifacts.worker_log("variant__seed42", 2) == (
        artifacts.root / "logs" / "workers" / "variant__seed42__attempt2.log"
    )
    assert artifacts.attempt("variant__seed42", 2) == (
        artifacts.root / "runs" / "attempts" / "variant__seed42" / "attempt2"
    )
    assert artifacts.run_attempts("variant__seed42") == (
        artifacts.root / "runs" / "attempts" / "variant__seed42"
    )
    assert artifacts.completion_marker("variant__seed42") == (
        artifacts.root / "markers" / "variant__seed42.done"
    )
    assert artifacts.report("experiment_run_status.json") == (
        artifacts.root / "reports" / "experiment_run_status.json"
    )
    assert not artifacts.root.exists()


@pytest.mark.parametrize(
    "experiment_run_id",
    ["../outside", "/tmp/experiment_run", "", "unsafe.name"],
)
def test_experiment_run_layout_rejects_unsafe_experiment_run_ids(
    tmp_path: Path, experiment_run_id: str
) -> None:
    with pytest.raises(ValueError, match="unsafe experiment run id"):
        ArtifactLayout(tmp_path).gpu_experiment_run(experiment_run_id)


def test_experiment_run_layout_rejects_unsafe_run_paths_and_report_names(tmp_path: Path) -> None:
    artifacts = ArtifactLayout(tmp_path).gpu_experiment_run("safe-experiment-run")

    with pytest.raises(ValueError, match="unsafe experiment run key"):
        artifacts.attempt("../outside", 1)
    with pytest.raises(ValueError, match="positive integer"):
        artifacts.worker_log("run__seed42", 0)
    with pytest.raises(ValueError, match="file name"):
        artifacts.report("../experiment_run.json")


def test_experiment_run_layout_creates_only_the_controller_artifact_directories(
    tmp_path: Path,
) -> None:
    artifacts = ArtifactLayout(tmp_path).gpu_experiment_run("experiment-run-1")

    artifacts.ensure_controller_directories()

    assert artifacts.worker_logs.is_dir()
    assert artifacts.failure_logs.is_dir()
    assert artifacts.runs.is_dir()
    assert artifacts.markers.is_dir()
    assert artifacts.reports.is_dir()
    assert not (artifacts.root / "runs" / "attempts").exists()


def test_experiment_run_recovery_checkpoint_must_remain_inside_experiment_run(
    tmp_path: Path,
) -> None:
    artifacts = ArtifactLayout(tmp_path).gpu_experiment_run("experiment-run-1")
    checkpoint = artifacts.attempt("variant__seed42", 1) / "model" / "checkpoint.zip"

    assert artifacts.recovery_checkpoint(checkpoint) == checkpoint.resolve()
    with pytest.raises(ValueError, match="escapes its experiment run"):
        artifacts.recovery_checkpoint(tmp_path / "outside.zip")


def test_atomic_writers_create_parent_and_replace_content(tmp_path: Path) -> None:
    text_path = tmp_path / "nested" / "report.txt"
    json_path = tmp_path / "nested" / "manifest.json"

    assert write_text_atomic(text_path, "complete\n") == text_path
    assert write_json_atomic(json_path, {"b": 2, "a": 1}) == json_path
    assert text_path.read_text(encoding="utf-8") == "complete\n"
    assert json.loads(json_path.read_text(encoding="utf-8")) == {"a": 1, "b": 2}


def test_atomic_json_replacement_preserves_existing_permissions(tmp_path: Path) -> None:
    path = tmp_path / "experiment_run.json"
    path.write_text('{"old": true}\n', encoding="utf-8")
    path.chmod(0o640)

    write_json_atomic(path, {"new": True})

    assert json.loads(path.read_text(encoding="utf-8")) == {"new": True}
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o640


def test_json_writer_can_preserve_strict_serialization(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text('{"valid": true}\n', encoding="utf-8")

    with pytest.raises(TypeError):
        write_json_atomic(path, {"unsupported": object()}, default=None)

    assert path.read_text(encoding="utf-8") == '{"valid": true}\n'


def test_json_writer_keeps_legacy_string_fallback(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"

    write_json_atomic(path, {"value": Path("run/checkpoint.pt")})

    assert json.loads(path.read_text(encoding="utf-8")) == {"value": "run/checkpoint.pt"}


@pytest.mark.parametrize(
    "values, message",
    [
        ({"kind": "", "artifact_id": "run:1"}, "kind must be non-empty"),
        ({"kind": "run", "artifact_id": ""}, "id must be non-empty"),
        (
            {"kind": "run", "artifact_id": "run:1", "schema_version": 0},
            "schema_version must be a positive integer",
        ),
        (
            {"kind": "run", "artifact_id": "run:1", "parents": ("",)},
            "parents must be non-empty",
        ),
    ],
)
def test_manifest_rejects_invalid_identity_fields(values, message) -> None:
    with pytest.raises(ValueError, match=message):
        ArtifactManifest(**values)


def test_manifest_read_requires_a_mapping_root(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="root must be a mapping"):
        ArtifactManifest.read(path)


def test_manifest_read_rejects_unknown_fields(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps({"kind": "run", "artifact_id": "run:1", "unowned_field": True}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="fields are invalid"):
        ArtifactManifest.read(path)


def test_manifest_read_rejects_non_sequence_parents(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps({"kind": "run", "artifact_id": "run:1", "parents": "run:parent"}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="parents must be a sequence"):
        ArtifactManifest.read(path)


def test_atomic_replace_preserves_destination_and_cleans_temp_on_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "manifest.json"
    destination.write_bytes(b"previous\n")

    def fail_replace(source: str | Path, target: str | Path) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr("artifacts.atomic.os.replace", fail_replace)

    with pytest.raises(OSError, match="simulated replace failure"):
        _atomic_replace(destination, b"replacement\n")

    assert destination.read_bytes() == b"previous\n"
    assert list(tmp_path.iterdir()) == [destination]
