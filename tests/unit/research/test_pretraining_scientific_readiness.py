from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from scripts.research.audits.pretraining_scientific_readiness import build_readiness

SOURCE = "a" * 40
COMMON = ["raw_data", "feature_review"]
PRICE = ["price_review"]
COMMON_BARRIERS = ["B0", "B2_IMPLEMENTATION_EVIDENCE", "COMMON_IMPLEMENTATION_RELEASE"]
PRICE_BARRIERS = ["B3_PRICE_IMPLEMENTATION", "PRICE_IMPLEMENTATION_RELEASE"]


def _plan() -> dict[str, Any]:
    return {
        "common_gates": COMMON,
        "price_gates": PRICE,
        "common_execution_barriers": COMMON_BARRIERS,
        "price_execution_barriers": PRICE_BARRIERS,
    }


def _execution(tmp_path: Path, *, price_status: str = "pass") -> dict[str, Any]:
    tasks = []
    for task_id, status in (("x", "pass"), ("px", price_status)):
        task_dir = tmp_path / "tasks" / task_id
        task_dir.mkdir(parents=True)
        log_path = task_dir / "run.log"
        log_path.write_text(f"task {status}\n", encoding="utf-8")
        task: dict[str, object] = {
            "task_id": task_id,
            "status": status,
            "return_code": 0 if status == "pass" else 1,
            "elapsed_seconds": 0.1,
            "log_path": str(log_path),
            "log_sha256": hashlib.sha256(log_path.read_bytes()).hexdigest(),
            "artifact_sha256": {},
            "blocker": None,
        }
        (task_dir / "result.json").write_text(json.dumps(task), encoding="utf-8")
        tasks.append(task)
    return {
        "schema_version": "pretraining-parallel-readiness-run-v1",
        "source_commit": SOURCE,
        "source_dirty_at_start": False,
        "execution_status": "pass" if price_status == "pass" else "fail",
        "scientific_training_authorized": False,
        "price_training_authorized": False,
        "tasks": tasks,
        "barriers": [
            {"barrier_id": "B0", "status": "pass", "requires": ["x"]},
            {"barrier_id": "B2_IMPLEMENTATION_EVIDENCE", "status": "pass", "requires": ["x"]},
            {"barrier_id": "COMMON_IMPLEMENTATION_RELEASE", "status": "pass", "requires": ["x"]},
            {"barrier_id": "B3_PRICE_IMPLEMENTATION", "status": price_status, "requires": ["px"]},
            {
                "barrier_id": "PRICE_IMPLEMENTATION_RELEASE",
                "status": price_status,
                "requires": ["px"],
            },
        ],
    }


def _record(gate_id: str, evidence: Path, *, status: str = "pass") -> dict[str, Any]:
    return {
        "schema_version": "pretraining-scientific-gate-review-v1",
        "gate_id": gate_id,
        "status": status,
        "source_commit": SOURCE,
        "reviewed_by": "reviewer",
        "reviewed_at_utc": "2026-11-09T15:00:00Z",
        "evidence": [
            {"path": str(evidence), "sha256": hashlib.sha256(evidence.read_bytes()).hexdigest()}
        ],
        "prohibited_states": {
            "exposed_report_period_used_for_selection": False,
            "candidate_realized_outcomes_used_as_policy_inputs": False,
            "preregistered_thresholds_changed_post_hoc": False,
        },
        "note": "reviewed",
    }


def test_common_readiness_can_pass_while_price_is_blocked(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence.json"
    evidence.write_text("{}\n", encoding="utf-8")
    records = {
        "raw_data": _record("raw_data", evidence),
        "feature_review": _record("feature_review", evidence),
        "price_review": _record("price_review", evidence, status="blocked"),
    }
    result = build_readiness(
        plan=_plan(),
        execution_manifest=_execution(tmp_path),
        gate_records=records,
        source_commit=SOURCE,
        source_clean=True,
    )
    assert result["status"] == "pass"
    assert result["scientific_training_authorized"] is True
    assert result["price_training_authorized"] is False


def test_price_execution_failure_does_not_block_common_readiness(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence.json"
    evidence.write_text("{}\n", encoding="utf-8")
    records = {gate: _record(gate, evidence) for gate in [*COMMON, *PRICE]}
    result = build_readiness(
        plan=_plan(),
        execution_manifest=_execution(tmp_path, price_status="fail"),
        gate_records=records,
        source_commit=SOURCE,
        source_clean=True,
    )
    assert result["scientific_training_authorized"] is True
    assert result["price_training_authorized"] is False
    assert result["errors"] == []
    assert result["price_errors"]


def test_common_failure_blocks_both_authorizations(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence.json"
    evidence.write_text("{}\n", encoding="utf-8")
    records = {gate: _record(gate, evidence) for gate in [*COMMON, *PRICE]}
    execution = _execution(tmp_path)
    execution["barriers"][1]["status"] = "fail"
    result = build_readiness(
        plan=_plan(),
        execution_manifest=execution,
        gate_records=records,
        source_commit=SOURCE,
        source_clean=True,
    )
    assert result["scientific_training_authorized"] is False
    assert result["price_training_authorized"] is False


def test_missing_price_barrier_preserves_common_authorization(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence.json"
    evidence.write_text("{}\n", encoding="utf-8")
    records = {gate: _record(gate, evidence) for gate in [*COMMON, *PRICE]}
    execution = _execution(tmp_path)
    execution["barriers"] = execution["barriers"][:-1]
    result = build_readiness(
        plan=_plan(),
        execution_manifest=execution,
        gate_records=records,
        source_commit=SOURCE,
        source_clean=True,
    )
    assert result["scientific_training_authorized"] is True
    assert result["price_training_authorized"] is False


def test_legacy_release_barrier_name_maps_to_common_release(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence.json"
    evidence.write_text("{}\n", encoding="utf-8")
    records = {gate: _record(gate, evidence) for gate in [*COMMON, *PRICE]}
    plan = _plan()
    plan["common_execution_barriers"] = [
        *COMMON_BARRIERS[:-1],
        "B4_IMPLEMENTATION_RELEASE",
    ]
    execution = _execution(tmp_path)
    execution["barriers"][2]["barrier_id"] = "B4_IMPLEMENTATION_RELEASE"
    result = build_readiness(
        plan=plan,
        execution_manifest=execution,
        gate_records=records,
        source_commit=SOURCE,
        source_clean=True,
    )
    assert result["scientific_training_authorized"] is True
    assert result["price_training_authorized"] is True


def test_forged_barrier_dependencies_fail_only_the_affected_authorization(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence.json"
    evidence.write_text("{}\n", encoding="utf-8")
    records = {gate: _record(gate, evidence) for gate in [*COMMON, *PRICE]}
    execution = _execution(tmp_path)
    expected = {
        "B0": ("x",),
        "B2_IMPLEMENTATION_EVIDENCE": ("x",),
        "COMMON_IMPLEMENTATION_RELEASE": ("x",),
        "B3_PRICE_IMPLEMENTATION": ("px",),
        "PRICE_IMPLEMENTATION_RELEASE": ("px",),
    }
    execution["barriers"][3]["requires"] = ["x"]
    result = build_readiness(
        plan=_plan(),
        execution_manifest=execution,
        gate_records=records,
        source_commit=SOURCE,
        source_clean=True,
        expected_barriers=expected,
    )
    assert result["scientific_training_authorized"] is True
    assert result["price_training_authorized"] is False

    execution["barriers"][2]["requires"] = ["px"]
    result = build_readiness(
        plan=_plan(),
        execution_manifest=execution,
        gate_records=records,
        source_commit=SOURCE,
        source_clean=True,
        expected_barriers=expected,
    )
    assert result["scientific_training_authorized"] is False
    assert result["price_training_authorized"] is False


def test_unknown_execution_task_fails_closed(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence.json"
    evidence.write_text("{}\n", encoding="utf-8")
    records = {gate: _record(gate, evidence) for gate in [*COMMON, *PRICE]}
    execution = _execution(tmp_path)
    execution["tasks"].append({"task_id": "forged_task", "status": "pass", "return_code": 0})
    result = build_readiness(
        plan=_plan(),
        execution_manifest=execution,
        gate_records=records,
        source_commit=SOURCE,
        source_clean=True,
        expected_barriers={
            "B0": ("x",),
            "B2_IMPLEMENTATION_EVIDENCE": ("x",),
            "COMMON_IMPLEMENTATION_RELEASE": ("x",),
            "B3_PRICE_IMPLEMENTATION": ("px",),
            "PRICE_IMPLEMENTATION_RELEASE": ("px",),
        },
        expected_task_ids={"x", "px"},
    )
    assert result["scientific_training_authorized"] is False
    assert result["price_training_authorized"] is False


def test_price_requires_all_price_gates(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence.json"
    evidence.write_text("{}\n", encoding="utf-8")
    records = {gate: _record(gate, evidence) for gate in [*COMMON, *PRICE]}
    result = build_readiness(
        plan=_plan(),
        execution_manifest=_execution(tmp_path),
        gate_records=records,
        source_commit=SOURCE,
        source_clean=True,
    )
    assert result["scientific_training_authorized"] is True
    assert result["price_training_authorized"] is True


def test_stale_or_modified_evidence_fails_closed(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence.json"
    evidence.write_text("{}\n", encoding="utf-8")
    records = {gate: _record(gate, evidence) for gate in [*COMMON, *PRICE]}
    evidence.write_text('{"changed": true}\n', encoding="utf-8")
    execution = _execution(tmp_path)
    execution["source_commit"] = "b" * 40
    result = build_readiness(
        plan=_plan(),
        execution_manifest=execution,
        gate_records=records,
        source_commit=SOURCE,
        source_clean=True,
    )
    assert result["status"] == "fail"
    assert result["scientific_training_authorized"] is False
    assert result["price_training_authorized"] is False


def test_execution_manifest_cannot_self_authorize(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence.json"
    evidence.write_text("{}\n", encoding="utf-8")
    records = {gate: _record(gate, evidence) for gate in [*COMMON, *PRICE]}
    execution = _execution(tmp_path)
    execution["scientific_training_authorized"] = True
    result = build_readiness(
        plan=_plan(),
        execution_manifest=execution,
        gate_records=records,
        source_commit=SOURCE,
        source_clean=True,
    )
    assert result["scientific_training_authorized"] is False


def test_changed_execution_log_blocks_scientific_readiness(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence.json"
    evidence.write_text("{}\n", encoding="utf-8")
    records = {gate: _record(gate, evidence) for gate in [*COMMON, *PRICE]}
    execution = _execution(tmp_path)
    Path(execution["tasks"][0]["log_path"]).write_text("changed\n", encoding="utf-8")
    result = build_readiness(
        plan=_plan(),
        execution_manifest=execution,
        gate_records=records,
        source_commit=SOURCE,
        source_clean=True,
    )
    assert result["scientific_training_authorized"] is False


def test_missing_review_rationale_blocks_common_readiness(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence.json"
    evidence.write_text("{}\n", encoding="utf-8")
    records = {gate: _record(gate, evidence) for gate in [*COMMON, *PRICE]}
    records["raw_data"].pop("reviewed_by")
    result = build_readiness(
        plan=_plan(),
        execution_manifest=_execution(tmp_path),
        gate_records=records,
        source_commit=SOURCE,
        source_clean=True,
    )
    assert result["scientific_training_authorized"] is False
