from __future__ import annotations

import hashlib
import json
import subprocess
import zipfile
from pathlib import Path
from typing import Any

from scripts.research.analysis.evidence.verify_research_provenance_bytes import (
    verify_provenance_dag_bytes,
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _snapshot(root: Path) -> dict[str, Any]:
    run = root / "outputs/run"
    run.mkdir(parents=True)
    source = b"trainer = 'preserved'\n"
    source_hash = _sha(source)
    manifest_bytes = json.dumps(
        {"schema_version": 1, "git_sha": "a" * 40, "files": {"legacy/trainer.py": source_hash}},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    archive_path = run / "source_snapshot.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("source_manifest.json", manifest_bytes)
        archive.writestr("legacy/trainer.py", source)
    return {
        "path": "outputs/run/source_snapshot.zip",
        "sha256": _sha(archive_path.read_bytes()),
        "manifest_sha256": _sha(manifest_bytes),
        "file_count": 1,
    }


def _write_dag(
    path: Path,
    nodes: list[dict[str, Any]],
    *,
    edges: list[dict[str, Any]] | None = None,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"schema": "research-provenance-dag-v1", "nodes": nodes, "edges": edges or []}),
        encoding="utf-8",
    )
    return path


def _commit_source(root: Path, relative_path: str, payload: bytes) -> str:
    """Create one exact source blob in a temporary local Git repository."""
    source = root / relative_path
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(payload)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", "--", relative_path], cwd=root, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Evidence Test",
            "-c",
            "user.email=evidence@example.invalid",
            "commit",
            "-qm",
            "source fixture",
        ],
        cwd=root,
        check=True,
    )
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True
    ).stdout.strip()


def test_verifies_declared_files_and_archived_sources(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path)
    manifest = tmp_path / "outputs/run/experiment_run.json"
    manifest.write_text('{"run_id":"run"}\n', encoding="utf-8")
    data = tmp_path / "data/input.csv"
    data.parent.mkdir()
    data.write_bytes(b"timestamp,value\n1,2\n")
    artifact = tmp_path / "outputs/run/report.json"
    artifact.write_bytes(b'{"status":"complete"}\n')
    nodes = [
        {
            "id": "manifest:1",
            "kind": "manifest",
            "path": "outputs/run/experiment_run.json",
            "sha256": _sha(manifest.read_bytes()),
        },
        {
            "id": "data_input:1",
            "kind": "data_input",
            "path": "data/input.csv",
            "sha256": _sha(data.read_bytes()),
        },
        {"id": "source_snapshot:1", "kind": "source_snapshot", **snapshot},
        {
            "id": "source_file:1",
            "kind": "source_file",
            "path": "legacy/trainer.py",
            "sha256": _sha(b"trainer = 'preserved'\n"),
        },
        {
            "id": "run_artifact:1",
            "kind": "run_artifact",
            "path": "outputs/run/report.json",
            "sha256": _sha(artifact.read_bytes()),
        },
        {"id": "run:1", "kind": "run", "run_id": "run"},
        {"id": "job:1", "kind": "job", "status": "completed"},
    ]

    report = verify_provenance_dag_bytes(_write_dag(tmp_path / "dag.json", nodes), root=tmp_path)

    assert report["status"] == "verified"
    assert report["declared_hashed_nodes"] == 4
    assert report["source_snapshot_embedded_files_verified"] == 1
    assert report["failure_count"] == 0


def test_reports_hash_mismatch_without_rewriting_declared_identity(tmp_path: Path) -> None:
    changed = tmp_path / "data/input.csv"
    changed.parent.mkdir()
    changed.write_bytes(b"changed\n")
    expected_hash = _sha(b"original\n")
    dag = _write_dag(
        tmp_path / "dag.json",
        [
            {
                "id": "data_input:1",
                "kind": "data_input",
                "path": "data/input.csv",
                "sha256": expected_hash,
            }
        ],
    )

    report = verify_provenance_dag_bytes(dag, root=tmp_path)

    assert report["status"] == "mismatch"
    assert report["failures"][0]["status"] == "mismatch"
    assert report["failures"][0]["expected_sha256"] == expected_hash


def test_verifies_relocated_run_artifact_by_declared_hash(tmp_path: Path) -> None:
    payload = b"checkpoint bytes\n"
    expected_hash = _sha(payload)
    artifact = (
        tmp_path
        / "outputs/gpu_campaigns/campaign/runs/attempts/variant/attempt1/variant/run/model/ppo_final.zip"
    )
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(payload)
    dag = _write_dag(
        tmp_path / "dag.json",
        [
            {
                "id": "run_artifact:relocated",
                "kind": "run_artifact",
                "path": "outputs/gpu_campaigns/campaign/variant/run/model/ppo_final.zip",
                "sha256": expected_hash,
            }
        ],
    )

    report = verify_provenance_dag_bytes(dag, root=tmp_path)

    assert report["status"] == "verified"
    assert report["node_counts_by_kind_and_status"]["run_artifact"] == {"verified_relocated": 1}


def test_marks_changed_historical_source_as_unavailable(tmp_path: Path) -> None:
    source = tmp_path / "config/current.yaml"
    source.parent.mkdir()
    source.write_text("current: true\n", encoding="utf-8")
    dag = _write_dag(
        tmp_path / "dag.json",
        [
            {
                "id": "source_file:historical",
                "kind": "source_file",
                "path": "config/current.yaml",
                "sha256": _sha(b"historical: true\n"),
            }
        ],
    )

    report = verify_provenance_dag_bytes(dag, root=tmp_path)

    assert report["status"] == "incomplete"
    assert report["failures"][0]["status"] == "historical_source_unavailable"


def test_verifies_historical_source_blob_in_linked_run_commit(tmp_path: Path) -> None:
    relative_path = "config/historical.yaml"
    payload = b"threshold: 0.25\n"
    commit = _commit_source(tmp_path, relative_path, payload)
    (tmp_path / relative_path).unlink()
    dag = _write_dag(
        tmp_path / "dag.json",
        [
            {
                "id": "source_file:1",
                "kind": "source_file",
                "path": relative_path,
                "sha256": _sha(payload),
            },
            {
                "id": "run:1",
                "kind": "run",
                "run_id": "historical-run",
                "source_commit": commit,
            },
        ],
        edges=[{"from": "run:1", "relation": "uses_source", "to": "source_file:1"}],
    )

    report = verify_provenance_dag_bytes(dag, root=tmp_path)

    assert report["status"] == "verified"
    assert report["node_counts_by_kind_and_status"]["source_file"] == {
        "verified_in_source_commit": 1
    }
    assert (
        report["git_source_commit_verifications"][0]["verification"]["checks"][0]["status"]
        == "match"
    )


def test_keeps_mismatched_or_unlinked_git_source_blobs_incomplete(tmp_path: Path) -> None:
    relative_path = "config/historical.yaml"
    committed_payload = b"threshold: 0.25\n"
    commit = _commit_source(tmp_path, relative_path, committed_payload)
    (tmp_path / relative_path).unlink()
    source_hash = _sha(b"threshold: 0.5\n")
    run_node = {
        "id": "run:1",
        "kind": "run",
        "run_id": "historical-run",
        "source_commit": commit,
    }
    source_node = {
        "id": "source_file:1",
        "kind": "source_file",
        "path": relative_path,
        "sha256": source_hash,
    }

    linked = verify_provenance_dag_bytes(
        _write_dag(
            tmp_path / "linked.json",
            [source_node, run_node],
            edges=[{"from": "run:1", "relation": "uses_source", "to": "source_file:1"}],
        ),
        root=tmp_path,
    )
    unlinked = verify_provenance_dag_bytes(
        _write_dag(tmp_path / "unlinked.json", [source_node, run_node]),
        root=tmp_path,
    )

    assert linked["status"] == unlinked["status"] == "incomplete"
    assert linked["failures"][0]["git_source_commit_verification"]["status"] == "mismatch"
    assert unlinked["failures"][0]["git_source_commit_verification"]["status"] == "not_linked"


def test_invalid_run_source_commit_cannot_be_promoted(tmp_path: Path) -> None:
    relative_path = "config/historical.yaml"
    dag = _write_dag(
        tmp_path / "dag.json",
        [
            {
                "id": "source_file:1",
                "kind": "source_file",
                "path": relative_path,
                "sha256": _sha(b"historical: true\n"),
            },
            {"id": "run:1", "kind": "run", "run_id": "historical-run", "source_commit": "invalid"},
        ],
        edges=[{"from": "run:1", "relation": "uses_source", "to": "source_file:1"}],
    )

    report = verify_provenance_dag_bytes(dag, root=tmp_path)

    assert report["status"] == "incomplete"
    assert report["failures"][0]["git_source_commit_verification"]["checks"][0]["status"] == (
        "invalid_commit"
    )


def test_reports_missing_and_escaping_paths_as_unverified(tmp_path: Path) -> None:
    dag = _write_dag(
        tmp_path / "dag.json",
        [
            {
                "id": "missing:1",
                "kind": "data_input",
                "path": "data/missing.csv",
                "sha256": "a" * 64,
            },
            {
                "id": "escape:1",
                "kind": "run_artifact",
                "path": "../outside.bin",
                "sha256": "b" * 64,
            },
        ],
    )

    report = verify_provenance_dag_bytes(dag, root=tmp_path)

    assert report["status"] == "mismatch"
    assert {item["status"] for item in report["failures"]} == {"missing", "blocked"}
