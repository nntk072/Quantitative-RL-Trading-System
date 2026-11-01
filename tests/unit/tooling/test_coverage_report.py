from __future__ import annotations

from typing import Any

import pytest
from tools.quality.coverage_report import (
    aggregate_coverage,
    compare_baseline,
    require_main_baseline,
)


def _report(covered_lines: int = 8, covered_branches: int = 3) -> dict[str, Any]:
    return {
        "files": {
            "artifacts/sample.py": {
                "summary": {
                    "num_statements": 10,
                    "covered_lines": covered_lines,
                    "num_branches": 4,
                    "covered_branches": covered_branches,
                }
            }
        },
        "totals": {
            "num_statements": 10,
            "covered_lines": covered_lines,
            "num_branches": 4,
            "covered_branches": covered_branches,
        },
    }


def test_coverage_aggregates_line_and_branch_metrics() -> None:
    coverage = aggregate_coverage(_report())

    assert coverage["overall"]["line_ratio"] == 0.8
    assert coverage["overall"]["branch_ratio"] == 0.75
    assert coverage["overall"]["combined_ratio"] == 11 / 14
    assert coverage["packages"]["artifacts"]["files"] == 1


def test_coverage_ratchet_accepts_equal_main_baseline() -> None:
    coverage = aggregate_coverage(_report())
    baseline = {"overall": coverage["overall"], "packages": coverage["packages"]}

    assert compare_baseline(coverage, baseline) == []


def test_coverage_ratchet_reports_line_and_branch_regressions() -> None:
    baseline = aggregate_coverage(_report())
    current = aggregate_coverage(_report(covered_lines=7, covered_branches=2))

    errors = compare_baseline(current, baseline)

    assert "overall line coverage fell below main baseline" in errors
    assert "overall branch coverage fell below main baseline" in errors
    assert "artifacts line coverage fell below main baseline" in errors
    assert "artifacts branch coverage fell below main baseline" in errors


def test_coverage_packages_keep_nested_training_paths_separate() -> None:
    report = _report()
    nested_file = {
        "summary": {
            "num_statements": 2,
            "covered_lines": 2,
            "num_branches": 0,
            "covered_branches": 0,
        }
    }
    report["files"]["training/artifacts/__init__.py"] = nested_file
    report["totals"]["num_statements"] += 2
    report["totals"]["covered_lines"] += 2

    coverage = aggregate_coverage(report)

    assert coverage["packages"]["artifacts"]["files"] == 1
    assert coverage["packages"]["training"]["files"] == 1


def test_main_coverage_gate_rejects_a_non_main_baseline() -> None:
    require_main_baseline({"source_branch": "main"})

    with pytest.raises(ValueError, match="captured from main"):
        require_main_baseline({"source_branch": "feature/refactor"})
