from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from scripts.research.audits.pretraining_scientific_readiness import build_readiness

SOURCE = "a" * 40
COMMON = ["raw_data", "feature_review"]
PRICE = ["price_review"]
BARRIERS = ["B0", "B4_IMPLEMENTATION_RELEASE"]


def _plan() -> dict[str, Any]:
    return {"common_gates": COMMON, "price_gates": PRICE, "required_execution_barriers": BARRIERS}


def _execution(tmp_path: Path) -> dict[str, Any]:
    task_dir = tmp_path / "tasks" / "x"
    task_dir.mkdir(parents=True)
    log_path = task_dir / "run.log"
    log_path.write_text("task passed\n", encoding="utf-8")
    task = {
        "task_id": "x",
        "status": "pass",
        "return_code": 0,
        "elapsed_seconds": 0.1,
        "log_path": str(log_path),
        "log_sha256": hashlib.sha256(log_path.read_bytes()).hexdigest(),
        "artifact_sha256": {},
        "blocker": None,
    }
    (task_dir / "result.json").write_text(json.dumps(task), encoding="utf-8")
    return {
        "schema_version": "pretraining-parallel-readiness-run-v1",
        "source_commit": SOURCE,
        "source_dirty_at_start": False,
        "execution_status": "pass",
        "scientific_training_authorized": False,
        "price_training_authorized": False,
        "tasks": [task],
        "barriers": [
            {"barrier_id": "B0", "status": "pass", "requires": ["x"]},
            {
                "barrier_id": "B4_IMPLEMENTATION_RELEASE",
                "status": "pass",
                "requires": ["x"],
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
