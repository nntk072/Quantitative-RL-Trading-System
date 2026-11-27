from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from research_tools.compute.audits import pretraining_readiness_task_runner as runner
from research_tools.compute.audits.pretraining_readiness_plan import TaskSpec


def _task(*artifact_roots: Path) -> TaskSpec:
    return TaskSpec(
        task_id="quote_audit",
        lane="data_quality",
        description="Synthetic task for process-contract tests",
        depends_on=("source_scan",),
        resource_lock=None,
        command=("synthetic-tool", "--check"),
        artifact_roots=tuple(str(path) for path in artifact_roots),
    )


def test_artifact_hashing_reports_files_nested_files_and_empty_or_missing_roots(
    tmp_path: Path,
) -> None:
    direct_file = tmp_path / "direct.csv"
    direct_file.write_bytes(b"a,b\n1,2\n")
    nested_root = tmp_path / "nested"
    (nested_root / "child").mkdir(parents=True)
    nested_file = nested_root / "child" / "trace.json"
    nested_file.write_text("{}\n", encoding="utf-8")
    empty_root = tmp_path / "empty"
    empty_root.mkdir()
    missing_root = tmp_path / "missing"

    hashes = runner._artifact_hashes(
        tuple(str(path) for path in (direct_file, nested_root, empty_root, missing_root))
    )

    assert hashes[str(direct_file)] == hashlib.sha256(direct_file.read_bytes()).hexdigest()
    assert hashes[str(nested_file)] == hashlib.sha256(nested_file.read_bytes()).hexdigest()
    assert hashes[f"EMPTY::{empty_root}"] == ""
    assert hashes[f"MISSING::{missing_root}"] == ""


def test_successful_task_persists_log_hash_artifact_hash_and_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    artifact = tmp_path / "result.csv"
    artifact.write_text("value\n1\n", encoding="utf-8")
    run_root = tmp_path / "run"
    task = _task(artifact)
    calls: list[tuple[list[str], dict[str, Any]]] = []

    def successful_process(command: list[str], **kwargs: Any) -> SimpleNamespace:
        calls.append((command, kwargs))
        kwargs["stdout"].write(b"synthetic output\n")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(runner, "ROOT", root)
    monkeypatch.setattr(subprocess, "run", successful_process)

    result = runner.run_task(task, run_root)

    log_path = Path(result.log_path or "")
    result_path = run_root / "tasks" / task.task_id / "result.json"
    assert result.status == "pass"
    assert result.return_code == 0
    assert result.blocker is None
    assert (
        result.artifact_sha256[str(artifact)] == hashlib.sha256(artifact.read_bytes()).hexdigest()
    )
    assert result.log_sha256 == hashlib.sha256(log_path.read_bytes()).hexdigest()
    assert json.loads(result_path.read_text(encoding="utf-8"))["status"] == "pass"
    assert calls[0][0] == list(task.command)
    assert calls[0][1]["cwd"] == root
    assert calls[0][1].get("shell", False) is False


def test_task_fails_when_a_declared_artifact_root_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(subprocess, "run", lambda *_args, **_kwargs: SimpleNamespace(returncode=0))
    task = _task(tmp_path / "missing-output")

    result = runner.run_task(task, tmp_path / "run")

    assert result.return_code == 0
    assert result.status == "fail"
    assert result.blocker == "declared artifact root is missing or empty"
    assert result.artifact_sha256[f"MISSING::{tmp_path / 'missing-output'}"] == ""


def test_task_records_direct_process_start_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runner, "ROOT", tmp_path)

    def unavailable_process(*_args: Any, **_kwargs: Any) -> None:
        raise FileNotFoundError("synthetic executable missing")

    monkeypatch.setattr(subprocess, "run", unavailable_process)
    task = _task()

    result = runner.run_task(task, tmp_path / "run")

    assert result.status == "fail"
    assert result.return_code == 127
    assert result.blocker is not None
    assert "could not start direct child process" in result.blocker
    assert result.log_path is not None
    assert "synthetic executable missing" in Path(result.log_path).read_text(encoding="utf-8")


def test_task_records_artifact_hashing_errors_without_losing_process_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(subprocess, "run", lambda *_args, **_kwargs: SimpleNamespace(returncode=0))

    def failed_hash(_roots: tuple[str, ...]) -> dict[str, str]:
        raise PermissionError("synthetic artifact permission failure")

    monkeypatch.setattr(runner, "_artifact_hashes", failed_hash)

    result = runner.run_task(_task(tmp_path / "result.csv"), tmp_path / "run")

    assert result.return_code == 0
    assert result.status == "fail"
    assert result.artifact_sha256 == {}
    assert (
        result.blocker == "could not hash declared artifacts: synthetic artifact permission failure"
    )


def test_blocked_task_result_distinguishes_dependency_block_and_runner_failure() -> None:
    task = _task()

    blocked = runner.blocked_task_result(task, "upstream prerequisite failed")
    failed = runner.blocked_task_result(task, "invalid task setup", failed=True)

    assert blocked.status == "blocked"
    assert blocked.depends_on == ("source_scan",)
    assert blocked.blocker == "upstream prerequisite failed"
    assert failed.status == "fail"
    assert failed.return_code is None
    assert failed.log_path is None
