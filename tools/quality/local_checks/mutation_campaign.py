"""Isolate mutation campaigns and reconcile native machine-readable results."""

from __future__ import annotations

import shutil
import sys
import tomllib
from pathlib import Path
from typing import Any

from tools.quality.coverage_report import PRODUCT_PACKAGES
from tools.quality.local_checks.mutation_results import summarize_mutation_results
from tools.quality.local_checks.resources import discover_worker_capacity
from tools.quality.local_checks.run_evidence import (
    OUTPUT,
    quality_git,
    quality_source_paths,
    read_quality_json,
    run_quality_process,
    write_quality_json,
)

MUTATION_SCOPES = {
    "risk": ("trading/account/", "trading/risk/", "trading/policy/"),
    "execution": ("trading/execution/", "trading/orders/", "simulation/"),
    "temporal": ("market_data/", "features/"),
    "decisioning": ("decisioning/",),
    "learning": ("learning/", "models/"),
    "provenance": ("artifacts/", "configuration/", "experiments/"),
    "evaluation": ("evaluation/",),
}


def _mutation_configured_project(
    source: str, scope: str, tests: list[str], include_uncovered: bool
) -> str:
    """Replace only the mutmut table in the disposable checkout."""
    import json
    import re

    configured = tomllib.loads(source)["tool"]["mutmut"]
    if scope != "configured":
        prefixes = (
            tuple(p + "/" for p in PRODUCT_PACKAGES) if scope == "full" else MUTATION_SCOPES[scope]
        )
        configured["only_mutate"] = [
            p for p in quality_source_paths() if p.endswith(".py") and p.startswith(prefixes)
        ]
        if not configured["only_mutate"] or not tests:
            raise ValueError("Expanded mutation scope requires explicit relevant tests")
    if tests:
        configured["pytest_add_cli_args_test_selection"] = ["-m", "unit", *tests]
    if include_uncovered:
        configured["mutate_only_covered_lines"] = False
    table = (
        "[tool.mutmut]\n"
        + "\n".join(f"{k} = {json.dumps(v)}" for k, v in configured.items())
        + "\n\n"
    )
    value, count = re.subn(r"(?ms)^\[tool\.mutmut\]\n.*?(?=^\[|\Z)", lambda _: table, source)
    if count != 1:
        raise ValueError("Cannot isolate mutmut configuration")
    tomllib.loads(value)
    return value


def run_python_mutation(
    out: Path,
    timeout: int,
    scope: str,
    tests: list[str],
    children: int,
    include_uncovered: bool,
    patterns: list[str],
) -> dict[str, Any]:
    """Run mutmut on a clean detached worktree and import results even after timeout."""
    if scope not in {"configured", "full", *MUTATION_SCOPES} or any(
        p.startswith("-") for p in tests + patterns
    ):
        raise ValueError("Invalid mutation scope or selector")
    if quality_git("status", "--porcelain", "--untracked-files=normal"):
        return {"status": "not_run", "reason": "Mutation requires a clean committed tree"}
    capacity = discover_worker_capacity(children, 512)
    if not capacity["workers"]:
        return {"status": "insufficient_resources", "capacity": capacity}
    checkout = OUTPUT / "mutation-worktrees" / out.name
    checkout.parent.mkdir(parents=True, exist_ok=True)
    result = run_quality_process(
        ["git", "worktree", "add", "--detach", str(checkout), "HEAD"], out / "worktree.log", timeout
    )
    if result["status"] != "ok":
        return result
    project = checkout / "pyproject.toml"
    project.write_text(
        _mutation_configured_project(project.read_text(), scope, tests, include_uncovered)
    )
    config = tomllib.loads(project.read_text())["tool"]["mutmut"]
    write_quality_json(out / "mutation-scope.json", config)
    env = {
        "PYTHONPATH": str(checkout),
        "PATH": str(Path(sys.executable).parent) + ":" + __import__("os").environ.get("PATH", ""),
        "OMP_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
    }
    # Retain the worktree for explicit review/resume. Never remove a user's active checkout.
    run = run_quality_process(
        ["mutmut", "run", "--max-children", str(capacity["workers"]), *patterns],
        out / "mutation-run.log",
        timeout,
        cwd=checkout,
        env=env,
    )
    stages = {"run": run}
    if (checkout / "mutants").is_dir():
        stages["stats"] = run_quality_process(
            ["mutmut", "export-cicd-stats"],
            out / "mutation-export.log",
            timeout,
            cwd=checkout,
            env=env,
        )
        stages["details"] = run_quality_process(
            ["mutmut", "results", "--all"],
            out / "mutation-details.log",
            timeout,
            cwd=checkout,
            env=env,
        )
    report = checkout / "mutants/mutmut-cicd-stats.json"
    if not report.is_file():
        return {"status": "incomplete", "worktree": str(checkout), "stages": stages}
    shutil.copyfile(report, out / "mutmut-native.json")
    summary = summarize_mutation_results(
        read_quality_json(report),
        tool="mutmut",
        scope={
            "scope": scope,
            "covered_lines_only": config["mutate_only_covered_lines"],
            "patterns": patterns,
            "only_mutate": config["only_mutate"],
        },
        complete=run["status"] == "ok",
    )
    write_quality_json(out / "mutation-summary.json", summary)
    status = (
        "incomplete"
        if summary["status"] != "complete"
        else "findings"
        if summary["counts"]["survived"]
        else "ok"
    )
    return {
        "status": status,
        "worktree": str(checkout),
        "stages": stages,
        "summary": summary,
        "qualification": "Timeouts and untested mutants are never counted as killed.",
    }
