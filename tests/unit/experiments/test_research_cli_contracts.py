"""End-to-end command routing for the shared research CLI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from experiments.research import cli, workflow


def _read(capsys: pytest.CaptureFixture[str]) -> Any:
    return json.loads(capsys.readouterr().out)


def test_catalog_reports_components_with_stable_variants(capsys) -> None:
    assert cli.main(["catalog", "--domain", "features"]) == 0
    rows = _read(capsys)
    assert len(rows) == 1
    assert rows[0]["experiment"] == "feature_inputs"
    assert rows[0]["components"]["observations"] == ["observation_validity"]
    assert cli.main(["catalog", "--component", "opportunities"]) == 0
    rows = _read(capsys)
    assert len(rows) == 1
    assert rows[0]["variants"] == ["opportunity_census"]
    assert cli.main(["catalog", "--component", "does_not_exist"]) == 0
    assert _read(capsys) == []


def test_freeze_selects_one_component_without_creating_a_new_runner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    monkeypatch.setattr(workflow, "current_source_commit", lambda: "a" * 40)
    path = tmp_path / "feature_bundle.json"
    assert (
        cli.main(
            [
                "freeze",
                "feature_inputs",
                "--component",
                "observations",
                "--output",
                str(path),
            ]
        )
        == 0
    )
    assert _read(capsys)["commands"] == 1
    commands = json.loads(path.read_text(encoding="utf-8"))["commands"]
    assert commands[0]["variant_id"] == "observation_validity"
    with pytest.raises(ValueError, match="no matching component"):
        cli.main(
            [
                "freeze",
                "feature_inputs",
                "--component",
                "unregistered",
                "--output",
                str(tmp_path / "missing.json"),
            ]
        )
    with pytest.raises(ValueError, match="no variants"):
        cli.main(
            [
                "freeze",
                "feature_inputs",
                "--variant",
                "unregistered",
                "--output",
                str(tmp_path / "missing.json"),
            ]
        )
    with pytest.raises(ValueError, match="no matching component"):
        cli.main(
            [
                "freeze",
                "feature_inputs",
                "--component",
                "opportunities",
                "--variant",
                "observation_validity",
                "--output",
                str(tmp_path / "missing.json"),
            ]
        )


@pytest.mark.parametrize(
    ("status", "expected"),
    [("passed", 0), ("failed", 1), ("incomplete", 2)],
)
def test_execute_cli_reports_actual_status(status: str, expected: int, monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "load_bundle", lambda *_: object())
    monkeypatch.setattr(cli, "execute_command_bundle", lambda *a, **kw: {"status": status})
    result = cli.main(
        [
            "execute",
            "--bundle",
            "any.json",
            "--run-root",
            "outputs/local",
            "--max-workers",
            "2",
            "--allow-experiments",
            "--resume",
            "--retry-failed",
        ]
    )
    assert result == expected
    assert _read(capsys)["status"] == status


def test_cli_parses_source_bound_json_inputs(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.json"
    artifact.write_text(json.dumps({"status": "pass"}), encoding="utf-8")
    assert cli._named_json([f"source={artifact}"])["source"]["status"] == "pass"
    assert cli._json_object(artifact) == {"status": "pass"}
    assert cli._finalist_runs([f"42={artifact}", f"43={artifact}"]) == {
        42: artifact,
        43: artifact,
    }
    assert cli._finalist_runs(None) is None
    with pytest.raises(ValueError, match="SEED=PATH"):
        cli._finalist_runs(["bad"])
    with pytest.raises(ValueError, match="duplicate"):
        cli._finalist_runs([f"42={artifact}", f"42={artifact}"])
    with pytest.raises(ValueError, match="NAME=PATH"):
        cli._named_json(["incorrect"])
    with pytest.raises(ValueError, match="duplicate"):
        cli._named_json([f"one={artifact}", f"one={artifact}"])


def test_cli_consolidation_and_history_share_one_reporting_interface(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys,
) -> None:
    monkeypatch.setattr(
        cli, "consolidate_execution_manifests", lambda sources, output: {"sources": len(sources)}
    )
    assert (
        cli.main(
            [
                "consolidate",
                "--execution",
                "source.json",
                "--execution",
                "other.json",
                "--output",
                str(tmp_path / "combined"),
            ]
        )
        == 0
    )
    assert _read(capsys)["sources"] == 2
    monkeypatch.setattr(cli, "load_history", lambda path: ())
    output = tmp_path / "history.md"
    assert cli.main(["history", "--output", str(output)]) == 0
    assert "Historical research evidence" in capsys.readouterr().out
    assert "Historical research evidence" in output.read_text(encoding="utf-8")


def test_cli_routes_review_readiness_and_safety_without_separate_scripts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    monkeypatch.setattr(cli, "record_review", lambda **kw: {"status": "pass"})
    assert (
        cli.main(
            [
                "review",
                "--id",
                "contract",
                "--status",
                "pass",
                "--reviewed-by",
                "reviewer",
                "--note",
                "verified",
                "--evidence",
                "audit.json",
                "--output",
                str(tmp_path / "review.json"),
            ]
        )
        == 0
    )
    assert _read(capsys)["status"] == "pass"
    monkeypatch.setattr(cli, "build_readiness", lambda **kw: {"status": "pass"})
    assert cli.main(["readiness", "--output", str(tmp_path / "readiness.json")]) == 0
    assert _read(capsys)["status"] == "pass"
    assert json.loads((tmp_path / "readiness.json").read_text())["status"] == "pass"
    monkeypatch.setattr(cli, "summarize_repeatability", lambda *a: {"status": "pass"})
    assert (
        cli.main(
            [
                "repeatability",
                "--execution",
                "repeatability.json",
                "--output",
                str(tmp_path / "repeat.json"),
            ]
        )
        == 0
    )
    assert _read(capsys)["status"] == "pass"
    monkeypatch.setattr(cli, "summarize_portfolio_safety", lambda *a: {"status": "fail"})
    assert (
        cli.main(
            [
                "portfolio-safety",
                "--run",
                "42=run",
                "--output",
                str(tmp_path / "portfolio.json"),
            ]
        )
        == 1
    )
    assert _read(capsys)["status"] == "fail"
    monkeypatch.setattr(cli, "summarize_robustness", lambda *a: {"status": "pass"})
    assert (
        cli.main(
            [
                "robustness",
                "--execution",
                "account.json",
                "--output",
                str(tmp_path / "robustness.json"),
            ]
        )
        == 0
    )
    assert _read(capsys)["status"] == "pass"


def test_cli_primary_tables_budget_and_release_share_well_defined_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    input_path = tmp_path / "input.json"
    input_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(cli, "build_primary_payload", lambda value: {"schema_version": 1})
    monkeypatch.setattr(cli, "analyze_primary_payload", lambda value: {"status": "positive"})
    assert (
        cli.main(
            [
                "primary",
                "--source",
                str(input_path),
                "--payload",
                str(tmp_path / "pair.json"),
                "--analysis",
                str(tmp_path / "analysis.json"),
            ]
        )
        == 0
    )
    assert _read(capsys)["status"] == "positive"
    monkeypatch.setattr(cli, "build_research_tables", lambda *a: {"row_count": 1})
    assert cli.main(["tables", "--results", str(input_path), "--output", str(tmp_path)]) == 0
    assert _read(capsys)["row_count"] == 1
    assert (
        cli.main(
            [
                "compute-budget",
                "--decisions-per-full-path",
                "100",
                "--wf-decisions-per-full-path",
                "50",
                "50",
                "50",
                "50",
                "50",
                "--n-envs",
                "2",
                "4",
                "--rollout-steps-per-env",
                "32",
                "--batch-size",
                "32",
                "--epochs",
                "2",
                "--fps",
                "2=100",
                "--output",
                str(tmp_path / "budget.json"),
            ]
        )
        == 0
    )
    assert _read(capsys)["schema_version"] == 1
    monkeypatch.setattr(cli, "assemble_release", lambda **kw: {"source_commit": "a" * 40})
    assert (
        cli.main(
            [
                "release",
                "--results",
                "results.json",
                "--protocol",
                "protocol.yaml",
                "--output",
                str(tmp_path / "release"),
            ]
        )
        == 0
    )
    assert _read(capsys)["source_commit"] == "a" * 40
