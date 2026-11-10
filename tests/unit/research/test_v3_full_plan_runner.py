from pathlib import Path

import pytest
from scripts.research.audits.v3_full_plan_registry import load_catalog
from scripts.research.audits.v3_full_plan_runner import (
    barrier_states,
    dependency_readiness_report,
    dependency_ready_todos,
    initialize_progress,
    mark_todo,
    ready_todos,
)


def test_progress_initialization_and_barrier_state(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[3]
    catalog = load_catalog(root / "config/research/v3_full_todo_catalog.yaml")
    progress = initialize_progress(catalog, source_sha="a" * 40)
    assert len(progress["tasks"]) == 162
    assert 1 in dependency_ready_todos(catalog, progress)
    assert ready_todos(catalog, progress) == dependency_ready_todos(catalog, progress)
    evidence = tmp_path / "evidence.json"
    evidence.write_text("{}\n", encoding="utf-8")
    for todo in range(1, 8):
        mark_todo(
            progress,
            todo=todo,
            status="PASS",
            source_sha="a" * 40,
            result="passed",
            evidence_paths=[evidence],
        )
    assert barrier_states(catalog, progress)["B0"] == "PASS"
    assert 8 in dependency_ready_todos(catalog, progress)
    assert 13 in dependency_ready_todos(catalog, progress)


def test_dependency_readiness_does_not_claim_conditional_or_scientific_authorization() -> None:
    root = Path(__file__).resolve().parents[3]
    catalog = load_catalog(root / "config/research/v3_full_todo_catalog.yaml")
    progress = initialize_progress(catalog, source_sha="a" * 40)
    progress["tasks"]["106"]["status"] = "PASS"
    progress["tasks"]["108"]["status"] = "DEFERRED-NO-GO"
    progress["tasks"]["82"]["status"] = "PASS"

    report = dependency_readiness_report(catalog, progress)

    assert 109 in report["dependency_ready_todos"]
    assert 114 in report["conditional_gate_todos_not_evaluated"]
    assert report["authorization_checked"] is False
    assert report["ready"] == dependency_ready_todos(catalog, progress)


def test_terminal_todo_status_requires_evidence() -> None:
    root = Path(__file__).resolve().parents[3]
    catalog = load_catalog(root / "config/research/v3_full_todo_catalog.yaml")
    progress = initialize_progress(catalog, source_sha="a" * 40)
    with pytest.raises(ValueError, match="at least one evidence file"):
        mark_todo(
            progress,
            todo=1,
            status="PASS",
            source_sha="a" * 40,
            result="completed",
            evidence_paths=[],
        )
