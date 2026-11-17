from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from research_tools.studies.study_runner import StudyRunnerError, _plan_steps, run_study_checks


def test_plan_steps_blocks_empirical_prerequisites_without_scheduling_them() -> None:
    studies = {
        "sample.check": {
            "id": "sample.check",
            "module_id": "sample",
            "type": "code_check",
            "enabled": True,
            "effective_inputs_sha256": "0" * 64,
            "checks": ["tests/test_contract.py"],
            "prerequisites": ["sample.study"],
        },
        "sample.study": {
            "id": "sample.study",
            "module_id": "sample",
            "type": "empirical",
            "enabled": True,
            "prerequisites": [],
        },
    }

    steps, not_run = _plan_steps(studies, ["sample.check"])

    assert [step["id"] for step in steps] == ["sample.check"]
    assert steps[0]["blocked_by"] == ["sample.study"]
    assert not_run == ["sample.study"]


def test_run_check_executes_only_declared_pytest_files_and_writes_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile_dir = tmp_path / "config/studies/profiles"
    profile_dir.mkdir(parents=True)
    (tmp_path / "source").mkdir()
    (tmp_path / "source/module.py").write_text("value = 1\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_contract.py").write_text(
        "def test_contract(): pass\n", encoding="utf-8"
    )
    (profile_dir / "sample.yaml").write_text(
        """module_id: sample
source_roots: [source]
source_scopes: [{path: source, study_ids: [sample.contract, sample.contract_second]}]
config_paths: []
test_paths: [tests/test_contract.py]
studies:
  - id: sample.contract
    type: code_check
    question: Does the declared contract hold?
    source_paths: [source/module.py]
    checks: [tests/test_contract.py]
    outputs: [pass_or_fail]
  - id: sample.contract_second
    type: code_check
    question: Does the shared declared check also hold here?
    source_paths: [source/module.py]
    checks: [tests/test_contract.py]
    outputs: [pass_or_fail]
""",
        encoding="utf-8",
    )
    master = tmp_path / "config/studies/default.yaml"
    master.write_text(
        "schema_version: 1\nprofile_dir: profiles\nmodules:\n  sample: {enabled: true}\n",
        encoding="utf-8",
    )
    calls: list[tuple[list[str], dict[str, object]]] = []

    def fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout="1 passed", stderr="")

    monkeypatch.setattr("research_tools.studies.study_runner.subprocess.run", fake_run)

    output_dir = tmp_path / "logs/agents/architect/20261117_sample-check"
    result = run_study_checks(tmp_path, output_dir=output_dir)

    assert result["status"] == "passed"
    assert result["check_scope"] == "declared_pytest_only"
    assert result["audit_tools_executed"] == []
    assert Path(result["report_path"]).is_file()
    assert json.loads(Path(result["report_path"]).read_text(encoding="utf-8"))["status"] == (
        "passed"
    )
    assert len(calls) == 1
    command, options = calls[0]
    assert command == [sys.executable, "-m", "pytest", "-q", "tests/test_contract.py"]
    assert options["cwd"] == tmp_path
    assert options["shell"] is False
    assert [step["status"] for step in result["steps"]] == ["passed", "passed"]
    with pytest.raises(StudyRunnerError, match="refusing to overwrite"):
        run_study_checks(tmp_path, output_dir=output_dir)


def test_audit_study_check_reports_pytest_only_without_running_its_tool() -> None:
    root = Path(__file__).resolve().parents[3]

    result = run_study_checks(
        root,
        study_id="market_data.raw_data_quality_and_coverage",
        dry_run=True,
    )

    assert result["audit_studies_planned"] == ["market_data.raw_data_quality_and_coverage"]
    assert result["audit_studies_verified_by_pytest"] == []
    assert result["audit_tools_executed"] == []
    assert result["steps"][0]["audit_execution"] == "not_run_by_check"
