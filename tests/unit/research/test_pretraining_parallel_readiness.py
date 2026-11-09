from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest
from omegaconf import OmegaConf
from scripts.research.audits.pretraining_parallel_readiness import (
    run_plan,
)
from scripts.research.audits.pretraining_readiness_plan import load_plan, plan_summary


def _write_plan(
    path: Path,
    tasks: list[dict[str, Any]],
    barriers: list[dict[str, Any]] | None = None,
) -> Path:
    OmegaConf.save(
        OmegaConf.create(
            {
                "schema_version": "pretraining-parallel-readiness-v1",
                "scientific_training_authorization": "never_from_this_plan_alone",
                "tasks": tasks,
                "barriers": barriers or [],
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


def _clean_source(monkeypatch: pytest.MonkeyPatch, sha: str = "a" * 40) -> None:
    monkeypatch.setattr(
        "scripts.research.audits.pretraining_parallel_readiness._git_state",
        lambda: (sha, []),
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
    _clean_source(monkeypatch)

    manifest = run_plan(plan, run_root=tmp_path / "run", python=sys.executable, max_workers=2)

    rows = {row["task_id"]: row for row in manifest["tasks"]}
    assert rows["fails"]["status"] == "fail"
    assert rows["blocked"]["status"] == "blocked"
    assert rows["independent"]["status"] == "pass"
    assert manifest["scientific_training_authorized"] is False
    assert manifest["price_training_authorized"] is False
    assert (tmp_path / "run/tasks/fails/result.json").is_file()
    assert (tmp_path / "run/tasks/blocked/result.json").is_file()
    assert (tmp_path / "run/tasks/independent/result.json").is_file()


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
    _clean_source(monkeypatch)

    manifest = run_plan(plan, run_root=tmp_path / "run", python=sys.executable, max_workers=2)

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
    artifact = tmp_path / "run" / "missing.json"
    plan = load_plan(
        _write_plan(
            tmp_path / "missing.yaml",
            [_task("producer", "print('completed')", artifact=str(artifact))],
        )
    )
    _clean_source(monkeypatch, "b" * 40)

    manifest = run_plan(plan, run_root=tmp_path / "run", python=sys.executable, max_workers=1)

    result = manifest["tasks"][0]
    assert manifest["execution_status"] == "fail"
    assert result["status"] == "fail"
    assert result["return_code"] == 0
    assert result["log_path"] == str(tmp_path / "run/tasks/producer/run.log")
    assert len(result["log_sha256"]) == 64
    assert result["artifact_sha256"][f"MISSING::{artifact}"] == ""


def test_artifact_hash_and_dependency_closure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact = tmp_path / "run" / "artifact.txt"
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
    _clean_source(monkeypatch, "b" * 40)

    manifest = run_plan(
        plan,
        run_root=tmp_path / "run",
        python=sys.executable,
        max_workers=2,
        selected_tasks={"consumer"},
    )

    rows = {row["task_id"]: row for row in manifest["tasks"]}
    assert set(rows) == {"producer", "consumer"}
    assert len(rows["producer"]["artifact_sha256"][str(artifact)]) == 64
    saved = json.loads((tmp_path / "run/pretraining_parallel_readiness_manifest.json").read_text())
    assert saved["source_commit"] == "b" * 40
    assert saved["execution_status"] == "pass"
    assert saved["scientific_training_authorized"] is False
    assert saved["price_training_authorized"] is False


def test_run_root_must_be_fresh_and_outside_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = load_plan(_write_plan(tmp_path / "plan.yaml", [_task("task", "print('ok')")]))
    _clean_source(monkeypatch)
    existing = tmp_path / "existing"
    existing.mkdir()
    with pytest.raises(ValueError, match="must not already exist"):
        run_plan(plan, run_root=existing, python=sys.executable, max_workers=1)

    repository_path = Path(__file__).resolve().parents[3] / "outputs/readiness-test"
    with pytest.raises(ValueError, match="outside the repository"):
        run_plan(plan, run_root=repository_path, python=sys.executable, max_workers=1)


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
    assert summary["executes_commands"] is False
    assert summary["scientific_training_authorized"] is False
    assert summary["price_training_authorized"] is False
