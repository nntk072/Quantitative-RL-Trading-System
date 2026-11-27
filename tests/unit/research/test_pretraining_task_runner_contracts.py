from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from research_tools.compute.audits import pretraining_readiness_task_runner as runner
from research_tools.compute.audits.pretraining_readiness_plan import TaskSpec


def _task(
    tmp_path: Path,
    *,
    command: tuple[str, ...] = ("python", "-c", "pass"),
    artifacts: tuple[str, ...] = (),
) -> TaskSpec:
    return TaskSpec(
        task_id="check",
        lane="A",
        description="contract check",
        depends_on=("prerequisite",),
        resource_lock="feature_cache",
        command=command,
        artifact_roots=artifacts,
    )


def test_artifact_hashes_distinguish_files_directories_and_missing_roots(tmp_path: Path) -> None:
    artifact = tmp_path / "evidence.txt"
    artifact.write_text("evidence", encoding="utf-8")
    nested = tmp_path / "bundle" / "nested.txt"
    nested.parent.mkdir()
    nested.write_text("nested", encoding="utf-8")
    empty = tmp_path / "empty"
    empty.mkdir()

    hashes = runner._artifact_hashes(
        (str(artifact), str(nested.parent), str(empty), str(tmp_path / "missing"))
    )

    assert hashes[str(artifact)] == runner._sha256(artifact)
    assert hashes[str(nested)] == runner._sha256(nested)
    assert hashes[f"EMPTY::{empty}"] == ""
    assert hashes[f"MISSING::{tmp_path / 'missing'}"] == ""


def test_run_task_persists_success_and_hashes_artifact_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "out" / "artifact.txt"
    output.parent.mkdir()
    output.write_text("result", encoding="utf-8")
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(
        cast(Any, runner).subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=0)
    )
    task = _task(tmp_path, artifacts=(str(output.parent),))

    result = runner.run_task(task, tmp_path / "run")

    assert result.status == "pass"
    assert result.return_code == 0
    assert result.depends_on == ("prerequisite",)
    assert result.resource_lock == "feature_cache"
    assert result.artifact_sha256[str(output)] == runner._sha256(output)
    assert result.log_sha256 == runner._sha256(Path(result.log_path or ""))
    assert (tmp_path / "run/tasks/check/result.json").is_file()


def test_run_task_records_child_failure_and_missing_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(
        cast(Any, runner).subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=7)
    )
    task = _task(tmp_path, artifacts=(str(tmp_path / "absent"),))

    result = runner.run_task(task, tmp_path / "run")

    assert result.status == "fail"
    assert result.return_code == 7
    assert result.blocker == "declared artifact root is missing or empty"
    assert result.artifact_sha256 == {f"MISSING::{tmp_path / 'absent'}": ""}


def test_run_task_records_process_start_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runner, "ROOT", tmp_path)

    def fail_to_start(*args: object, **kwargs: object) -> None:
        raise OSError("executable unavailable")

    monkeypatch.setattr(cast(Any, runner).subprocess, "run", fail_to_start)

    result = runner.run_task(_task(tmp_path), tmp_path / "run")

    assert result.status == "fail"
    assert result.return_code == 127
    assert result.blocker == "could not start direct child process: executable unavailable"
    assert "could not start direct child process" in Path(result.log_path or "").read_text()


def test_run_task_records_artifact_hash_read_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(
        cast(Any, runner).subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=0)
    )

    def fail_hash(_roots: tuple[str, ...]) -> dict[str, str]:
        raise OSError("storage unavailable")

    monkeypatch.setattr(runner, "_artifact_hashes", fail_hash)

    result = runner.run_task(
        _task(tmp_path, artifacts=(str(tmp_path / "artifact"),)), tmp_path / "run"
    )

    assert result.status == "fail"
    assert result.blocker == "could not hash declared artifacts: storage unavailable"
    assert result.artifact_sha256 == {}


@pytest.mark.parametrize("failed", [False, True])
def test_blocked_task_result_preserves_contract_and_disposition(failed: bool) -> None:
    task = TaskSpec("blocked", "B", "blocked task", ("parent",), None, ("python",), ())

    result = runner.blocked_task_result(task, "dependency failed", failed=failed)

    assert result.status == ("fail" if failed else "blocked")
    assert result.blocker == "dependency failed"
    assert result.return_code is None
    assert result.elapsed_seconds is None
    assert result.log_path is None
    assert result.log_sha256 is None
    assert result.artifact_sha256 == {}
