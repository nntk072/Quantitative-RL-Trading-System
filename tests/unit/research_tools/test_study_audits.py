from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from research_tools.studies.study_audits import (
    AUDIT_TOOL_REGISTRY,
    AuditToolDefinition,
    StudyAuditError,
    run_study_audit,
)
from research_tools.studies.study_plan import build_study_plan


def test_registry_covers_each_audit_tool_once() -> None:
    root = Path(__file__).resolve().parents[3]
    expected = {
        study["audit_tool"]
        for module in build_study_plan(root)["modules"]
        for study in module["studies"]
        if study["type"] == "audit"
    }

    assert set(AUDIT_TOOL_REGISTRY) == expected
    assert all(tool.tool_id == key for key, tool in AUDIT_TOOL_REGISTRY.items())


def test_run_study_audit_calls_registered_handler_and_writes_report_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    study = {
        "id": "sample.audit",
        "module_id": "sample",
        "type": "audit",
        "enabled": True,
        "audit_tool": "sample.audit_tool",
        "effective_inputs_sha256": "a" * 64,
        "checks": ["tests/test_sample.py"],
    }
    plan = {"modules": [{"id": "sample", "studies": [study]}], "master_sha256": "b" * 64}
    calls: list[tuple[Path, str]] = []

    def fake_handler(root: Path, selected: Mapping[str, Any], output_dir: Path) -> dict[str, Any]:
        calls.append((output_dir, str(selected["id"])))
        (output_dir / "diagnostic.json").write_text('{"rows": 3}\n', encoding="utf-8")
        return {"status": "completed", "rows": 3}

    tool = AuditToolDefinition(
        tool_id="sample.audit_tool",
        canonical_role_id="architect",
        resource_class="repository",
        handler=fake_handler,
    )
    monkeypatch.setattr(
        "research_tools.studies.study_audits.build_study_plan", lambda *_args, **_kwargs: plan
    )
    monkeypatch.setitem(AUDIT_TOOL_REGISTRY, tool.tool_id, tool)
    output_dir = tmp_path / "logs/agents/architect/20261117_sample-audit"

    result = run_study_audit(tmp_path, study_id="sample.audit", output_dir=output_dir)

    assert result["status"] == "completed"
    assert result["audit_tool"] == "sample.audit_tool"
    report_path = tmp_path / result["report_path"]
    assert report_path.is_file()
    assert calls == [(output_dir / "artifacts", "sample.audit")]
    assert json.loads(report_path.read_text(encoding="utf-8"))["diagnostic"] == {
        "status": "completed",
        "rows": 3,
    }
    with pytest.raises(StudyAuditError, match="refusing to overwrite"):
        run_study_audit(tmp_path, study_id="sample.audit", output_dir=output_dir)


def test_run_study_audit_requires_an_allocation_for_cpu_node_tools(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    study = {
        "id": "sample.audit",
        "module_id": "sample",
        "type": "audit",
        "enabled": True,
        "audit_tool": "sample.cpu_audit",
        "effective_inputs_sha256": "a" * 64,
        "checks": ["tests/test_sample.py"],
    }
    plan = {"modules": [{"id": "sample", "studies": [study]}], "master_sha256": "b" * 64}
    tool = AuditToolDefinition(
        tool_id="sample.cpu_audit",
        canonical_role_id="architect",
        resource_class="cpu_node",
        handler=lambda *_args: pytest.fail("must not execute without an allocation"),
    )
    monkeypatch.setattr(
        "research_tools.studies.study_audits.build_study_plan", lambda *_args, **_kwargs: plan
    )
    monkeypatch.setitem(AUDIT_TOOL_REGISTRY, tool.tool_id, tool)
    monkeypatch.delenv("SLURM_JOB_ID", raising=False)

    with pytest.raises(StudyAuditError, match="CPU-node allocation"):
        run_study_audit(
            tmp_path,
            study_id="sample.audit",
            output_dir=tmp_path / "logs/agents/architect/20261117_sample-audit",
        )


def test_run_study_audit_never_runs_empirical_studies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    study = {
        "id": "sample.empirical",
        "module_id": "sample",
        "type": "empirical",
        "enabled": True,
        "audit_tool": "sample.audit_tool",
        "effective_inputs_sha256": "a" * 64,
        "checks": [],
    }
    plan = {"modules": [{"id": "sample", "studies": [study]}], "master_sha256": "b" * 64}
    monkeypatch.setattr(
        "research_tools.studies.study_audits.build_study_plan", lambda *_args, **_kwargs: plan
    )

    with pytest.raises(StudyAuditError, match="only diagnostic audit studies"):
        run_study_audit(tmp_path, study_id="sample.empirical")
