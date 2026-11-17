"""Run only pytest paths registered by enabled non-empirical studies."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from research_tools.studies.study_audits import AUDIT_TOOL_REGISTRY
from research_tools.studies.study_catalog import build_study_plan


class StudyRunnerError(ValueError):
    """Raised when a study selection cannot be checked safely."""


def _resolve_report_dir(root: Path, output_dir: str | Path) -> Path:
    candidate = Path(output_dir).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    expected_parent = (root / "logs/agents/architect").resolve()
    try:
        relative = resolved.relative_to(expected_parent)
    except ValueError as exc:
        raise StudyRunnerError(
            "check reports must be under logs/agents/architect/<YYYYMMDD>_<task_slug>"
        ) from exc
    if (
        len(relative.parts) != 1
        or re.fullmatch(r"\d{8}_[a-z0-9][a-z0-9_-]*", relative.name) is None
    ):
        raise StudyRunnerError(
            "check report directory must use <YYYYMMDD>_<task_slug> under logs/agents/architect"
        )
    if resolved.exists():
        raise StudyRunnerError(f"refusing to overwrite check report directory: {resolved}")
    return resolved


def _plan_steps(
    studies: dict[str, dict[str, Any]], requested_ids: list[str]
) -> tuple[list[dict[str, Any]], list[str]]:
    """Order runnable prerequisites and report empirical or disabled blockers."""
    required: set[str] = set()
    blocked_by: dict[str, set[str]] = {}
    empirical_not_run: set[str] = set()

    def include(study_id: str) -> None:
        study = studies[study_id]
        if study["type"] == "empirical":
            empirical_not_run.add(study_id)
            return
        if not study["enabled"]:
            return
        required.add(study_id)
        for prerequisite_id in study.get("prerequisites", []):
            prerequisite = studies[prerequisite_id]
            if prerequisite["type"] == "empirical" or not prerequisite["enabled"]:
                blocked_by.setdefault(study_id, set()).add(prerequisite_id)
                if prerequisite["type"] == "empirical":
                    empirical_not_run.add(prerequisite_id)
                continue
            include(prerequisite_id)

    for study_id in requested_ids:
        include(study_id)

    ordered: list[str] = []
    visited: set[str] = set()

    def visit(study_id: str) -> None:
        if study_id in visited:
            return
        for prerequisite_id in studies[study_id].get("prerequisites", []):
            if prerequisite_id in required:
                visit(prerequisite_id)
        visited.add(study_id)
        ordered.append(study_id)

    for study_id in studies:
        if study_id in required:
            visit(study_id)

    steps = [
        {
            "id": study_id,
            "module_id": studies[study_id]["module_id"],
            "type": studies[study_id]["type"],
            "checks": list(studies[study_id]["checks"]),
            "audit_tool": studies[study_id].get("audit_tool"),
            "audit_execution": "not_run_by_check" if studies[study_id]["type"] == "audit" else None,
            "effective_inputs_sha256": studies[study_id]["effective_inputs_sha256"],
            "prerequisites": list(studies[study_id].get("prerequisites", [])),
            "blocked_by": sorted(blocked_by.get(study_id, set())),
            "status": "blocked" if blocked_by.get(study_id) else "planned",
        }
        for study_id in ordered
    ]
    return steps, sorted(empirical_not_run)


def _select_studies(plan: dict[str, Any], module_id: str | None, study_id: str | None) -> list[str]:
    studies = {study["id"]: study for module in plan["modules"] for study in module["studies"]}
    if module_id is not None:
        modules = {module["id"] for module in plan["modules"]}
        if module_id not in modules:
            raise StudyRunnerError(f"unknown module: {module_id}")
        return [
            study["id"]
            for study in studies.values()
            if study["module_id"] == module_id and study["enabled"] and study["type"] != "empirical"
        ]
    if study_id is not None:
        if study_id not in studies:
            raise StudyRunnerError(f"unknown study: {study_id}")
        study = studies[study_id]
        if study["type"] == "empirical":
            raise StudyRunnerError("empirical studies are registered but never executed by check")
        if not study["enabled"]:
            raise StudyRunnerError(f"study is disabled: {study_id}")
        return [study_id]
    return [
        study["id"]
        for study in studies.values()
        if study["enabled"] and study["type"] != "empirical"
    ]


def run_study_checks(
    root: str | Path,
    *,
    master_path: str | Path | None = None,
    module_id: str | None = None,
    study_id: str | None = None,
    dry_run: bool = False,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Run declared pytest checks for selected enabled non-empirical studies."""
    if module_id is not None and study_id is not None:
        raise StudyRunnerError("select either a module or a study")
    repo = Path(root).resolve()
    report_path = None
    output_path = None
    if output_dir is not None:
        output_path = _resolve_report_dir(repo, output_dir)
        report_path = output_path / "study-check-report.json"
    plan = build_study_plan(repo, master_path)
    studies = {study["id"]: study for module in plan["modules"] for study in module["studies"]}
    requested = _select_studies(plan, module_id, study_id)
    if not requested:
        raise StudyRunnerError("selection has no enabled non-empirical studies")
    steps, prerequisite_empirical = _plan_steps(studies, requested)
    unknown_audits = sorted(
        {
            step["audit_tool"]
            for step in steps
            if step["audit_tool"] is not None and step["audit_tool"] not in AUDIT_TOOL_REGISTRY
        }
    )
    if unknown_audits:
        raise StudyRunnerError(f"unregistered audit tool ID: {unknown_audits}")
    empirical_not_run = sorted(
        {
            study["id"]
            for study in studies.values()
            if study["enabled"] and study["type"] == "empirical"
        }
        | set(prerequisite_empirical)
    )
    result: dict[str, Any] = {
        "schema_version": 1,
        "repository": str(repo),
        "master_sha256": plan["master_sha256"],
        "execution": "dry_run" if dry_run else "completed",
        "check_scope": "declared_pytest_only",
        "status": "dry_run" if dry_run else "passed",
        "selected_studies": requested,
        "audit_tools_executed": [],
        "audit_studies_planned": [step["id"] for step in steps if step["type"] == "audit"],
        "audit_studies_verified_by_pytest": [],
        "pytest_batches": [],
        "empirical_studies_not_run": empirical_not_run,
        "steps": steps,
    }
    if not dry_run:
        statuses = {step["id"]: "blocked" for step in steps if step["status"] == "blocked"}
        pending = [step for step in steps if step["status"] != "blocked"]
        completed_checks: set[str] = set()
        while pending:
            ready: list[dict[str, Any]] = []
            next_pending: list[dict[str, Any]] = []
            for step in pending:
                dependencies = step["prerequisites"]
                failed_dependencies = [
                    dependency
                    for dependency in dependencies
                    if statuses.get(dependency) in {"failed", "blocked"}
                ]
                if failed_dependencies:
                    step["blocked_by"] = sorted(set(step["blocked_by"]) | set(failed_dependencies))
                    step["status"] = "blocked"
                    statuses[step["id"]] = "blocked"
                    continue
                waiting = [dependency for dependency in dependencies if dependency not in statuses]
                if waiting:
                    next_pending.append(step)
                    continue
                ready.append(step)
            if not ready:
                if next_pending:
                    for step in next_pending:
                        step["status"] = "blocked"
                        step["blocked_by"] = sorted(step["prerequisites"])
                        statuses[step["id"]] = "blocked"
                    break
                break

            checks = sorted(
                {path for step in ready for path in step["checks"] if path not in completed_checks}
            )
            command = [sys.executable, "-m", "pytest", "-q", *checks]
            if not checks:
                batch = {
                    "checks": [],
                    "command": [],
                    "returncode": 0,
                    "stdout": "all declared check paths were already executed",
                    "stderr": "",
                    "status": "passed",
                    "reused_prior_check_results": True,
                }
                result["pytest_batches"].append(batch)
                for step in ready:
                    step["status"] = "passed"
                    step["pytest_batch"] = len(result["pytest_batches"]) - 1
                    statuses[step["id"]] = "passed"
                pending = next_pending
                continue
            try:
                completed = subprocess.run(
                    command,
                    cwd=repo,
                    capture_output=True,
                    text=True,
                    check=False,
                    shell=False,
                )
            except OSError as exc:
                batch = {
                    "checks": checks,
                    "command": command,
                    "returncode": None,
                    "stdout": "",
                    "stderr": str(exc),
                    "status": "failed",
                }
                result["pytest_batches"].append(batch)
                result["status"] = "failed"
                for step in ready:
                    step["status"] = "failed"
                    step["pytest_batch"] = len(result["pytest_batches"]) - 1
                    statuses[step["id"]] = "failed"
            else:
                completed_checks.update(checks)
                batch = {
                    "checks": checks,
                    "command": command,
                    "returncode": completed.returncode,
                    "stdout": completed.stdout,
                    "stderr": completed.stderr,
                    "status": "passed" if completed.returncode == 0 else "failed",
                }
                result["pytest_batches"].append(batch)
                for step in ready:
                    step["status"] = batch["status"]
                    step["pytest_batch"] = len(result["pytest_batches"]) - 1
                    statuses[step["id"]] = step["status"]
                if batch["status"] == "failed":
                    result["status"] = "failed"
            pending = next_pending
        if result["status"] != "failed" and any(step["status"] == "blocked" for step in steps):
            result["status"] = "blocked"
        result["audit_studies_verified_by_pytest"] = [
            step["id"] for step in steps if step["type"] == "audit" and step["status"] == "passed"
        ]

    if output_path is not None and report_path is not None:
        output_path.mkdir(parents=True, exist_ok=False)
        result["report_path"] = str(report_path)
        report_path.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return result
