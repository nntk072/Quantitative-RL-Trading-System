#!/usr/bin/env python3
"""Report package line/branch coverage and enforce the committed main baseline."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BASELINE = ROOT / "tools/quality/coverage_baseline.json"


def _ratio(covered: int, total: int) -> float | None:
    return covered / total if total else None


def aggregate_coverage(report: dict[str, Any]) -> dict[str, Any]:
    """Aggregate coverage.py JSON by first-level production package."""
    packages: dict[str, dict[str, Any]] = {}
    for source_path, details in report["files"].items():
        package = Path(source_path).parts[0]
        summary = details["summary"]
        metrics = packages.setdefault(
            package,
            {"files": 0, "statements": 0, "covered_lines": 0, "branches": 0, "covered_branches": 0},
        )
        metrics["files"] += 1
        metrics["statements"] += summary["num_statements"]
        metrics["covered_lines"] += summary["covered_lines"]
        metrics["branches"] += summary["num_branches"]
        metrics["covered_branches"] += summary["covered_branches"]
    for metrics in packages.values():
        metrics["line_ratio"] = _ratio(metrics["covered_lines"], metrics["statements"])
        metrics["branch_ratio"] = _ratio(metrics["covered_branches"], metrics["branches"])
    totals = report["totals"]
    overall = {
        "files": len(report["files"]),
        "statements": totals["num_statements"],
        "covered_lines": totals["covered_lines"],
        "branches": totals["num_branches"],
        "covered_branches": totals["covered_branches"],
        "line_ratio": _ratio(totals["covered_lines"], totals["num_statements"]),
        "branch_ratio": _ratio(totals["covered_branches"], totals["num_branches"]),
        "combined_ratio": _ratio(
            totals["covered_lines"] + totals["covered_branches"],
            totals["num_statements"] + totals["num_branches"],
        ),
    }
    return {"overall": overall, "packages": dict(sorted(packages.items()))}


def compare_baseline(current: dict[str, Any], baseline: dict[str, Any]) -> list[str]:
    """Return package/overall coverage regressions versus the main-branch floor."""
    errors: list[str] = []
    prior_overall = baseline["overall"]
    for label, ratio_key in (("line", "line_ratio"), ("branch", "branch_ratio")):
        before = prior_overall[ratio_key]
        after = current["overall"][ratio_key]
        if before is not None and (after is None or after < before):
            errors.append(f"overall {label} coverage fell below main baseline")
    current_packages = current["packages"]
    for name, prior in baseline["packages"].items():
        if name not in current_packages:
            errors.append(f"baseline package is missing from coverage report: {name}")
            continue
        now = current_packages[name]
        for label, ratio_key in (("line", "line_ratio"), ("branch", "branch_ratio")):
            before = prior[ratio_key]
            after = now[ratio_key]
            if before is not None and (after is None or after < before):
                errors.append(f"{name} {label} coverage fell below main baseline")
    return errors


def require_main_baseline(baseline_document: dict[str, Any]) -> None:
    """Reject coverage floors that were not measured from the main branch."""
    if baseline_document.get("source_branch") != "main":
        raise ValueError("coverage baseline must be captured from main")


def _percent(ratio: float | None) -> str:
    return "n/a" if ratio is None else f"{ratio * 100:.2f}%"


def _current_branch() -> str:
    """Resolve the source branch name in CI or a local checkout."""
    branch = os.environ.get("GITHUB_HEAD_REF") or os.environ.get("GITHUB_REF_NAME")
    if branch:
        return branch
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() or "detached checkout"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coverage-json", type=Path, default=ROOT / "coverage.json")
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--branch", help="label the source branch in the report")
    parser.add_argument(
        "--no-ratchet", action="store_true", help="report without comparing to baseline"
    )
    args = parser.parse_args(argv)
    report = json.loads(args.coverage_json.read_text(encoding="utf-8"))
    current = aggregate_coverage(report)
    baseline_document = json.loads(args.baseline.read_text(encoding="utf-8"))
    try:
        require_main_baseline(baseline_document)
    except ValueError as exc:
        parser.error(str(exc))
    baseline = {"overall": baseline_document["overall"], "packages": baseline_document["packages"]}
    overall = current["overall"]
    source_branch = args.branch or _current_branch()
    print(
        f"Coverage for {source_branch} against {baseline_document['source_branch']} baseline "
        f"({baseline_document['source_commit'][:8]}): "
        f"{overall['covered_lines']}/{overall['statements']} lines "
        f"({_percent(overall['line_ratio'])}), "
        f"{overall['covered_branches']}/{overall['branches']} branches "
        f"({_percent(overall['branch_ratio'])}); combined {_percent(overall['combined_ratio'])}"
    )
    print("Package                 Line       Branch")
    for name, metrics in current["packages"].items():
        print(
            f"{name:<23} {_percent(metrics['line_ratio']):>8} {_percent(metrics['branch_ratio']):>12}"
        )
    if args.no_ratchet:
        return 0
    errors = compare_baseline(current, baseline)
    if errors:
        for message in errors:
            print(f"coverage regression: {message}")
        return 1
    print(f"Coverage meets the {baseline_document['source_branch']} baseline.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
