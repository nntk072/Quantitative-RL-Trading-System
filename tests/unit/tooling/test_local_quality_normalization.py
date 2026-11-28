"""Check report schemas and prevent malformed or partial evidence from becoming passes."""

from __future__ import annotations

from pathlib import Path

import pytest
from tools.quality.local_checks.mutation_results import (
    parse_mutmut_results,
    summarize_mutation_results,
)
from tools.quality.local_checks.normalization import (
    classify_pypi_scope,
    normalize_analyzer_findings,
    partition_partial_report,
    read_analyzer_report,
)


def test_mutation_scores_do_not_treat_timeouts_as_kills() -> None:
    result = summarize_mutation_results(
        {"total": 6, "killed": 2, "survived": 1, "timeout": 1, "no_tests": 1, "suspicious": 1},
        tool="mutmut",
        scope={"covered_lines_only": True},
        complete=True,
    )
    assert result["score_killed_over_killed_plus_survived"] == pytest.approx(2 / 3)
    assert result["killed_fraction_of_generated"] == pytest.approx(2 / 6)
    assert result["counts"]["timeout"] == 1
    assert result["counts"]["no_tests"] == 1


def test_mutation_incomplete_inventory_and_unknown_states() -> None:
    result = summarize_mutation_results(
        {"total": 8, "killed": 2, "survived": 1, "timeout": 1},
        tool="mutmut",
        scope={},
        complete=False,
    )
    assert result["status"] == "incomplete"
    assert result["unclassified_count"] == 4
    assert parse_mutmut_results("pkg.x: killed\npkg.y: no tests") == {
        "pkg.x": "killed",
        "pkg.y": "no_tests",
    }
    with pytest.raises(ValueError):
        parse_mutmut_results("pkg.x: arbitrary state")


def test_sarif_failed_execution_is_not_clean(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="failed analysis"):
        normalize_analyzer_findings(
            "codeql",
            {
                "version": "2.1.0",
                "runs": [{"invocations": [{"executionSuccessful": False}], "results": []}],
            },
            tmp_path,
        )


def test_dependency_and_secret_reports_are_normalized(tmp_path: Path) -> None:
    rows = normalize_analyzer_findings(
        "pip-audit",
        {
            "dependencies": [
                {
                    "name": "example",
                    "version": "1",
                    "vulns": [{"id": "TEST-1", "description": "issue"}],
                },
            ]
        },
        tmp_path,
    )
    assert rows[0]["package"] == "example"
    assert rows[0]["checker"] == "TEST-1"
    rows = normalize_analyzer_findings(
        "trivy",
        {
            "Results": [
                {
                    "Target": "sample",
                    "Secrets": [{"RuleID": "example", "Match": "must not be copied"}],
                },
            ]
        },
        tmp_path,
    )
    assert rows[0]["message"] == "Potential secret (redacted)"
    assert "must not be copied" not in str(rows)


def test_mypy_ndjson_and_cppcheck_xml(tmp_path: Path) -> None:
    report = tmp_path / "mypy.jsonl"
    report.write_text(
        '{"file":"x.py","line":3,"message":"bad","severity":"error","code":"arg-type"}\n'
    )
    assert read_analyzer_report("mypy", report, tmp_path)[0]["line"] == 3
    report.write_text(
        '<results version="2"><errors><error id="sample" msg="bad" '
        'severity="warning"><location file="x.cpp" line="2"/></error></errors></results>'
    )
    assert read_analyzer_report("cppcheck", report, tmp_path)[0]["line"] == 2


def test_locked_mutmut_export_reconciles_unreported_statuses() -> None:
    """The locked exporter omits type-check and not-checked counts."""
    raw = {
        "total": 6,
        "killed": 1,
        "survived": 1,
        "timeout": 0,
        "no_tests": 0,
        "skipped": 1,
        "suspicious": 0,
        "check_was_interrupted_by_user": 0,
        "segfault": 1,
    }
    details = parse_mutmut_results(
        "a: killed\nb: survived\nc: skipped\nd: segfault\ne: caught by type check\nf: not checked\n"
    )
    result = summarize_mutation_results(
        raw, tool="mutmut", scope={}, complete=True, mutants=details
    )
    assert result["counts"]["type_check"] == 1
    assert result["counts"]["not_checked"] == 1
    assert result["counts"]["segfault"] == 1
    assert result["status"] == "incomplete"
    assert result["score_denominator"] == 2


def test_partial_analyzer_reports_preserve_findings(tmp_path: Path) -> None:
    """Skipped dependencies remain incomplete while assessed findings remain visible."""
    raw = {
        "dependencies": [
            {"name": "local-wheel", "skip_reason": "not indexed"},
            {"name": "sample", "version": "1", "vulns": [{"id": "TEST-1"}]},
        ],
    }
    usable, skipped = partition_partial_report("pip-audit", raw, tmp_path)
    assert skipped == [{"package": "local-wheel", "reason": "dependency_not_assessed"}]
    assert normalize_analyzer_findings("pip-audit", usable, tmp_path)[0]["checker"] == "TEST-1"
    assert len(raw["dependencies"]) == 2
    with pytest.raises(ValueError, match="skipped"):
        normalize_analyzer_findings("pip-audit", raw, tmp_path)


def test_partial_bandit_report_keeps_scan_errors_distinct(tmp_path: Path) -> None:
    """A skipped source is not a clean scan and does not erase other findings."""
    raw = {
        "errors": [{"filename": "sample.py", "reason": "could not parse"}],
        "results": [],
    }
    usable, skipped = partition_partial_report("bandit", raw, tmp_path)
    assert skipped == [{"file": "sample.py", "reason": "analyzer_reported_error"}]
    assert normalize_analyzer_findings("bandit", usable, tmp_path) == []
    with pytest.raises(ValueError, match="analysis errors"):
        normalize_analyzer_findings("bandit", raw, tmp_path)


def test_pypi_scope_only_accepts_exact_locked_non_pypi_versions() -> None:
    """Known registry limitations are distinct from unexplained package skips."""
    skipped = [{"package": "local-project"}, {"package": "torch"}, {"package": "unknown"}]
    locked = [
        {"name": "local-project", "version": "1", "source": {"editable": "."}},
        {
            "name": "torch",
            "version": "2+cu130",
            "source": {"registry": "https://download.pytorch.org/whl/cu130"},
        },
    ]
    rows = classify_pypi_scope(
        skipped, locked, {"local-project": "1", "torch": "2+cu130", "unknown": "1"}
    )
    assert [row["scope"] for row in rows] == [
        "editable_project",
        "non_pypi_accelerator_registry",
        "unassessed",
    ]
    assert classify_pypi_scope(skipped[1:2], locked, {"torch": "3"})[0]["scope"] == "unassessed"
