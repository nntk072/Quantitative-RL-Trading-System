from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from omegaconf import OmegaConf
from research_tools.compute.audits import pretraining_readiness_task_runner as task_runner
from scripts.research.audits.pretraining_parallel_readiness import (
    _validate_run_root,
    run_plan,
)
from scripts.research.audits.pretraining_readiness_plan import load_plan, plan_summary


def _write_plan(
    path: Path,
    tasks: list[dict[str, Any]],
    barriers: list[dict[str, Any]] | None = None,
) -> Path:
    barrier_rows = barriers or [
        {"id": "COMMON_TEST", "description": "common", "requires": [tasks[0]["id"]]},
        {"id": "PRICE_TEST", "description": "PRICE", "requires": [tasks[0]["id"]]},
    ]
    OmegaConf.save(
        OmegaConf.create(
            {
                "schema_version": "pretraining-parallel-readiness-v1",
                "scientific_training_authorization": "never_from_this_plan_alone",
                "authorization_barriers": {
                    "common": [barrier_rows[0]["id"]],
                    "price": [barrier_rows[1]["id"]],
                },
                "tasks": tasks,
                "barriers": barrier_rows,
                "external_scientific_gates": ["review"],
            }
        ),
        path,
    )
    return path


def _task(
    task_id: str,
    code: str,
    *,
    depends_on: list[str] | None = None,
    resource_lock: str | None = None,
    artifact: str | None = None,
) -> dict[str, Any]:
    return {
        "id": task_id,
        "lane": "B",
        "description": task_id,
        "depends_on": depends_on or [],
        "resource_lock": resource_lock,
        "command": [sys.executable, "-c", code],
        "artifact_roots": [] if artifact is None else [artifact],
    }


def _clean_source(monkeypatch: pytest.MonkeyPatch, repository: Path, sha: str = "a" * 40) -> None:
    from research_tools.compute.audits import pretraining_parallel_readiness as runner

    repository.mkdir(parents=True)
    monkeypatch.setattr(runner, "ROOT", repository)
    monkeypatch.setattr(runner, "_is_ignored_path", lambda _path: True)
    monkeypatch.setattr(
        "research_tools.compute.audits.pretraining_parallel_readiness._git_state",
        lambda: (sha, []),
    )


def _run_root(tmp_path: Path) -> Path:
    return (
        tmp_path
        / ".pytest-readiness-repository/outputs/pre_experiment_readiness/test/execution/attempt"
    )


def test_cycle_and_scheduler_commands_are_rejected(tmp_path: Path) -> None:
    cycle = _write_plan(
        tmp_path / "cycle.yaml",
        [_task("a", "print(1)", depends_on=["b"]), _task("b", "print(2)", depends_on=["a"])],
    )
    with pytest.raises(ValueError, match="cycle detected"):
        load_plan(cycle)

    bad = _task("bad", "print('bad')")
    bad["command"] = ["srun", "echo", "bad"]
    with pytest.raises(ValueError, match="forbidden executable"):
        load_plan(_write_plan(tmp_path / "scheduler.yaml", [bad]))

    shell = tmp_path / "unsafe.sh"
    shell.write_text("#!/bin/sh\nsrun echo unsafe\n", encoding="utf-8")
    bad_shell = _task("bad_shell", "print('bad')")
    bad_shell["command"] = ["bash", str(shell)]
    with pytest.raises(ValueError, match="forbidden scheduler command"):
        load_plan(_write_plan(tmp_path / "shell.yaml", [bad_shell]))


def test_failed_task_blocks_only_dependants(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = load_plan(
        _write_plan(
            tmp_path / "plan.yaml",
            [
                _task("fails", "raise SystemExit(3)"),
                _task("blocked", "print('never')", depends_on=["fails"]),
                _task("independent", "print('ok')"),
            ],
        )
    )
    _clean_source(monkeypatch, tmp_path / ".pytest-readiness-repository")

    manifest = run_plan(plan, run_root=_run_root(tmp_path), python=sys.executable, max_workers=2)

    rows = {row["task_id"]: row for row in manifest["tasks"]}
    assert rows["fails"]["status"] == "fail"
    assert rows["blocked"]["status"] == "blocked"
    assert rows["independent"]["status"] == "pass"
    assert manifest["scientific_training_authorized"] is False
    assert manifest["price_training_authorized"] is False
    assert (_run_root(tmp_path) / "tasks/fails/result.json").is_file()
    assert (_run_root(tmp_path) / "tasks/blocked/result.json").is_file()
    assert (_run_root(tmp_path) / "tasks/independent/result.json").is_file()


def test_tasks_with_shared_resource_lock_never_overlap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    events = tmp_path / "events.txt"
    code = (
        "import time; "
        f"open({str(events)!r}, 'a').write('start\\n'); "
        "time.sleep(0.2); "
        f"open({str(events)!r}, 'a').write('finish\\n')"
    )
    plan = load_plan(
        _write_plan(
            tmp_path / "locked.yaml",
            [
                _task("first", code, resource_lock="feature_build_memory"),
                _task("second", code, resource_lock="feature_build_memory"),
            ],
        )
    )
    _clean_source(monkeypatch, tmp_path / ".pytest-readiness-repository")

    manifest = run_plan(plan, run_root=_run_root(tmp_path), python=sys.executable, max_workers=2)

    assert manifest["execution_status"] == "pass"
    assert events.read_text(encoding="utf-8").splitlines() == [
        "start",
        "finish",
        "start",
        "finish",
    ]


def test_declared_missing_artifact_fails_and_result_keeps_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact = _run_root(tmp_path) / "missing.json"
    plan = load_plan(
        _write_plan(
            tmp_path / "missing.yaml",
            [_task("producer", "print('completed')", artifact=str(artifact))],
        )
    )
    _clean_source(monkeypatch, tmp_path / ".pytest-readiness-repository", "b" * 40)

    manifest = run_plan(plan, run_root=_run_root(tmp_path), python=sys.executable, max_workers=1)

    result = manifest["tasks"][0]
    assert manifest["execution_status"] == "fail"
    assert result["status"] == "fail"
    assert result["return_code"] == 0
    assert result["log_path"] == str(_run_root(tmp_path) / "tasks/producer/run.log")
    assert len(result["log_sha256"]) == 64
    assert result["artifact_sha256"][f"MISSING::{artifact}"] == ""


def test_artifact_hash_and_dependency_closure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact = _run_root(tmp_path) / "artifact.txt"
    code = (
        "from pathlib import Path; "
        f"p=Path({str(artifact)!r}); p.parent.mkdir(parents=True, exist_ok=True); "
        "p.write_text('evidence')"
    )
    plan = load_plan(
        _write_plan(
            tmp_path / "plan.yaml",
            [
                _task("producer", code, artifact=str(artifact)),
                _task("consumer", "print('ok')", depends_on=["producer"]),
            ],
        )
    )
    _clean_source(monkeypatch, tmp_path / ".pytest-readiness-repository", "b" * 40)

    manifest = run_plan(
        plan,
        run_root=_run_root(tmp_path),
        python=sys.executable,
        max_workers=2,
        selected_tasks={"consumer"},
    )

    rows = {row["task_id"]: row for row in manifest["tasks"]}
    assert set(rows) == {"producer", "consumer"}
    assert rows["producer"]["artifact_sha256"][str(artifact)] == (
        "ee8250fb76e094b34b471f13a73dbbe51d1ae142e9df59d7c0d31ec20f0a0a8e"
    )
    saved = json.loads(
        (_run_root(tmp_path) / "pretraining_parallel_readiness_manifest.json").read_text()
    )
    assert saved["source_commit"] == "b" * 40
    assert saved["execution_status"] == "pass"
    assert saved["scientific_training_authorized"] is False
    assert saved["price_training_authorized"] is False


def test_run_root_must_be_fresh_and_under_canonical_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = load_plan(_write_plan(tmp_path / "plan.yaml", [_task("task", "print('ok')")]))
    _clean_source(monkeypatch, tmp_path / ".pytest-readiness-repository")
    from research_tools.compute.audits import pretraining_parallel_readiness as runner

    monkeypatch.setattr(runner, "ROOT", tmp_path / "repository")
    monkeypatch.setattr(runner, "_is_ignored_path", lambda _path: True)
    existing = tmp_path / "repository/outputs/pre_experiment_readiness/run/execution/existing"
    existing.mkdir(parents=True)
    with pytest.raises(ValueError, match="must not already exist"):
        run_plan(plan, run_root=existing, python=sys.executable, max_workers=1)

    repository = tmp_path / "repository"
    repository.mkdir(exist_ok=True)
    monkeypatch.setattr(runner, "ROOT", repository)
    monkeypatch.setattr(runner, "_is_ignored_path", lambda _path: True)
    valid = repository / "outputs/pre_experiment_readiness/run-1/execution/attempt-1"
    assert _validate_run_root(valid) == valid
    with pytest.raises(ValueError, match="canonical execution output"):
        _validate_run_root(
            repository / "outputs/pre_experiment_readiness/run-1/readiness/attempt-1"
        )
    with pytest.raises(ValueError, match="canonical execution output"):
        _validate_run_root(repository / "tests/run")
    with pytest.raises(ValueError, match="canonical execution output"):
        _validate_run_root(tmp_path / "outside/run")


def test_run_root_rejects_symlink_escape_and_collision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from research_tools.compute.audits import pretraining_parallel_readiness as runner

    repository = tmp_path / "repository"
    repository.mkdir()
    monkeypatch.setattr(runner, "ROOT", repository)
    monkeypatch.setattr(runner, "_is_ignored_path", lambda _path: True)
    outside = tmp_path / "outside"
    outside.mkdir()
    output = repository / "outputs"
    output.symlink_to(outside, target_is_directory=True)
    candidate = output / "pre_experiment_readiness/run/execution/task"
    with pytest.raises(ValueError, match="symlinks"):
        _validate_run_root(candidate)

    output.unlink()
    candidate = repository / "outputs/pre_experiment_readiness/run/execution/task"
    candidate.mkdir(parents=True)
    with pytest.raises(ValueError, match="must not already exist"):
        _validate_run_root(candidate)


def test_repository_plan_serializes_memory_heavy_feature_builds() -> None:
    root = Path(__file__).resolve().parents[3]
    summary = plan_summary(load_plan(root / "config/research/pretraining_parallel_readiness.yaml"))
    by_id = {row["id"]: row for row in summary["tasks"]}

    assert {
        by_id[name]["resource_lock"]
        for name in (
            "observation_validity",
            "opportunity_census",
            "candidate_geometry_support",
        )
    } == {"feature_build_memory"}
    for name in ("candidate_policy_contract", "simulator_accounting_contract"):
        assert set(by_id[name]["depends_on"]) == {"static_contract", "prospective_protocol"}
    assert by_id["common_implementation_release"]["depends_on"] == [
        "candidate_policy_contract",
        "observation_validity",
        "opportunity_census",
        "simulator_accounting_contract",
    ]
    assert by_id["price_implementation_release"]["depends_on"] == [
        "common_implementation_release",
        "candidate_geometry_support",
    ]
    closures = summary["authorization_dependency_closures"]
    assert "candidate_geometry_support" not in closures["common"]["tasks"]
    assert "candidate_geometry_support" in closures["price"]["tasks"]
    assert (
        "candidate_geometry_empirical_acceptance_review"
        not in closures["common"]["external_scientific_gates"]
    )
    assert (
        "candidate_geometry_empirical_acceptance_review"
        in closures["price"]["external_scientific_gates"]
    )
    assert summary["executes_commands"] is False
    assert summary["scientific_training_authorized"] is False
    assert summary["price_training_authorized"] is False


def test_plan_rejects_scientific_gate_shared_by_common_and_price(tmp_path: Path) -> None:
    path = _write_plan(tmp_path / "plan.yaml", [_task("task", "print('ok')")])
    config = OmegaConf.load(path)
    config.schema_version = "pretraining-parallel-readiness-v2"
    config.external_scientific_gates = {
        "common": ["shared_gate"],
        "price": ["shared_gate"],
    }
    OmegaConf.save(config, path)

    with pytest.raises(ValueError, match="must be disjoint"):
        load_plan(path)


def test_artifact_hashes_cover_nested_directory_contents(tmp_path: Path) -> None:
    directory = tmp_path / "artifacts"
    nested = directory / "nested"
    nested.mkdir(parents=True)
    empty = tmp_path / "empty"
    empty.mkdir()
    first = directory / "first.bin"
    second = nested / "second.txt"
    first.write_bytes(b"first artifact bytes")
    second.write_text("second artifact text\n", encoding="utf-8")

    hashes = task_runner._artifact_hashes((str(directory), str(empty)))

    assert hashes == {
        str(first): hashlib.sha256(b"first artifact bytes").hexdigest(),
        str(second): hashlib.sha256(b"second artifact text\n").hexdigest(),
        f"EMPTY::{empty}": "",
    }
    first.write_bytes(b"changed artifact bytes")
    changed_hashes = task_runner._artifact_hashes((str(directory), str(empty)))

    assert changed_hashes[str(first)] == hashlib.sha256(b"changed artifact bytes").hexdigest()
    assert changed_hashes[str(first)] != hashes[str(first)]
    assert changed_hashes[str(second)] == hashes[str(second)]
    assert changed_hashes[f"EMPTY::{empty}"] == ""


def test_run_task_records_child_start_failure_and_hashes_failure_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    task = load_plan(
        _write_plan(tmp_path / "spawn-failure.yaml", [_task("spawn_failure", "print('unused')")])
    ).tasks[0]

    def fail_to_start(*_args: Any, **_kwargs: Any) -> None:
        raise OSError("child executable unavailable")

    monkeypatch.setattr(subprocess, "run", fail_to_start)

    result = task_runner.run_task(task, tmp_path / "execution")

    log_path = Path(result.log_path or "")
    assert result.status == "fail"
    assert result.return_code == 127
    assert result.blocker == "could not start direct child process: child executable unavailable"
    assert "could not start direct child process: child executable unavailable" in (
        log_path.read_text(encoding="utf-8")
    )
    assert result.log_sha256 == hashlib.sha256(log_path.read_bytes()).hexdigest()


def test_run_task_fails_closed_when_declared_artifact_hashing_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact = tmp_path / "artifact.txt"
    artifact.write_text("completed artifact", encoding="utf-8")
    task = load_plan(
        _write_plan(
            tmp_path / "hash-failure.yaml",
            [_task("hash_failure", "print('completed')", artifact=str(artifact))],
        )
    ).tasks[0]

    def fail_to_hash(_roots: tuple[str, ...]) -> dict[str, str]:
        raise PermissionError("artifact read denied")

    monkeypatch.setattr(task_runner, "_artifact_hashes", fail_to_hash)

    result = task_runner.run_task(task, tmp_path / "execution")

    assert result.status == "fail"
    assert result.return_code == 0
    assert result.artifact_sha256 == {}
    assert result.blocker == "could not hash declared artifacts: artifact read denied"
