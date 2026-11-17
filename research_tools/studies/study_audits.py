"""Run explicitly registered diagnostic tools and retain task-local reports."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from research_tools.studies.study_plan import build_study_plan

AuditHandler = Callable[[Path, Mapping[str, Any], Path], dict[str, Any]]
_TASK_DIR = re.compile(r"^\d{8}_[a-z0-9][a-z0-9_-]*$")


class StudyAuditError(ValueError):
    """Raised when an audit selection or its execution boundary is invalid."""


@dataclass(frozen=True)
class AuditToolDefinition:
    """A repository-owned audit entry point with its resource and log owner."""

    tool_id: str
    canonical_role_id: str
    resource_class: str
    handler: AuditHandler


def _run_experiment_audit(root: Path, study: Mapping[str, Any], output_dir: Path) -> dict[str, Any]:
    from research_tools.studies.study_audit_tools import audit_registered_configs

    return audit_registered_configs(root, study, output_dir)


def _run_feature_audit(root: Path, study: Mapping[str, Any], output_dir: Path) -> dict[str, Any]:
    from research_tools.studies.handlers.features import run_feature_audit

    return run_feature_audit(root, study, output_dir)


def _run_market_data_audit(
    root: Path, study: Mapping[str, Any], output_dir: Path
) -> dict[str, Any]:
    from research_tools.studies.handlers.market_data import run_market_data_audit

    return run_market_data_audit(root, study, output_dir)


def _run_repo_tooling_audit(
    root: Path, study: Mapping[str, Any], output_dir: Path
) -> dict[str, Any]:
    from research_tools.studies.handlers.repository import audit_script_migrations

    return audit_script_migrations(root, study, output_dir)


def _run_simulation_audit(root: Path, study: Mapping[str, Any], output_dir: Path) -> dict[str, Any]:
    from research_tools.studies.handlers.simulation import run_parity_checks

    return run_parity_checks(root, study, output_dir)


AUDIT_TOOL_REGISTRY: dict[str, AuditToolDefinition] = {
    "experiments.registered_research_configs": AuditToolDefinition(
        "experiments.registered_research_configs",
        "ml_engineer",
        "repository",
        _run_experiment_audit,
    ),
    "features.causal_availability": AuditToolDefinition(
        "features.causal_availability", "data_scientist_engineer", "repository", _run_feature_audit
    ),
    "features.prefix_causality": AuditToolDefinition(
        "features.prefix_causality", "data_scientist_engineer", "cpu_node", _run_feature_audit
    ),
    "features.candidate_geometry_support": AuditToolDefinition(
        "features.candidate_geometry_support",
        "data_scientist_engineer",
        "cpu_node",
        _run_feature_audit,
    ),
    "market_data.raw_data_quality": AuditToolDefinition(
        "market_data.raw_data_quality",
        "data_scientist_engineer",
        "cpu_node",
        _run_market_data_audit,
    ),
    "market_data.tick_coverage_and_quote_age": AuditToolDefinition(
        "market_data.tick_coverage_and_quote_age",
        "data_scientist_engineer",
        "cpu_node",
        _run_market_data_audit,
    ),
    "repo_tooling.script_inputs_and_output_provenance": AuditToolDefinition(
        "repo_tooling.script_inputs_and_output_provenance",
        "ci_operation_engineer",
        "repository",
        _run_repo_tooling_audit,
    ),
    "simulation.tick_execution_accounting_parity": AuditToolDefinition(
        "simulation.tick_execution_accounting_parity",
        "quantitative_trading_engineer",
        "cpu_node",
        _run_simulation_audit,
    ),
}


def _study_by_id(plan: Mapping[str, Any], study_id: str) -> dict[str, Any]:
    for module in plan["modules"]:
        for study in module["studies"]:
            if study["id"] == study_id:
                return cast(dict[str, Any], study)
    raise StudyAuditError(f"unknown study: {study_id}")


def _default_output_dir(root: Path, tool: AuditToolDefinition, study_id: str) -> Path:
    date_slug = datetime.now(UTC).strftime("%Y%m%d")
    study_slug = re.sub(r"[^a-z0-9]+", "-", study_id.lower()).strip("-")
    return root / "logs" / "agents" / tool.canonical_role_id / f"{date_slug}_qrl-study-{study_slug}"


def _resolve_output_dir(
    root: Path,
    tool: AuditToolDefinition,
    study_id: str,
    output_dir: str | Path | None,
) -> Path:
    candidate = (
        _default_output_dir(root, tool, study_id)
        if output_dir is None
        else Path(output_dir).expanduser()
    )
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    expected_parent = (root / "logs" / "agents" / tool.canonical_role_id).resolve()
    try:
        relative = resolved.relative_to(expected_parent)
    except ValueError as exc:
        raise StudyAuditError(
            "audit output must be under logs/agents/<canonical_role_id>/<YYYYMMDD>_<task_slug>"
        ) from exc
    if len(relative.parts) != 1 or _TASK_DIR.fullmatch(relative.name) is None:
        raise StudyAuditError(
            "audit output directory must use <YYYYMMDD>_<task_slug> under its canonical role"
        )
    if resolved.exists():
        raise StudyAuditError(f"refusing to overwrite audit output directory: {resolved}")
    return resolved


def run_study_audit(
    root: str | Path,
    *,
    study_id: str,
    master_path: str | Path | None = None,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Run one selected diagnostic audit, never an empirical study.

    Audit outputs are confined to the canonical role's task-log directory and
    are never written to durable evidence paths by this runner.
    """
    repo = Path(root).resolve()
    plan = build_study_plan(repo, master_path)
    study = _study_by_id(plan, study_id)
    if study["type"] != "audit":
        raise StudyAuditError("only diagnostic audit studies can run through audit")
    if not study["enabled"]:
        raise StudyAuditError(f"study is disabled: {study_id}")
    tool_id = study.get("audit_tool")
    if not isinstance(tool_id, str) or tool_id not in AUDIT_TOOL_REGISTRY:
        raise StudyAuditError(f"unregistered audit tool ID: {tool_id}")
    tool = AUDIT_TOOL_REGISTRY[tool_id]
    if tool.resource_class == "cpu_node" and not os.environ.get("SLURM_JOB_ID"):
        raise StudyAuditError(
            f"{tool_id} requires a CPU-node allocation; read .agents/rules/triton-slurm.md "
            "and run it in a suitable existing allocation"
        )
    if tool.resource_class not in {"repository", "cpu_node"}:
        raise StudyAuditError(f"invalid resource class for registered tool: {tool.resource_class}")

    destination = _resolve_output_dir(repo, tool, study_id, output_dir)
    destination.mkdir(parents=True, exist_ok=False)
    artifacts_dir = destination / "artifacts"
    artifacts_dir.mkdir()
    result: dict[str, Any] = {
        "schema_version": 1,
        "study_id": study_id,
        "module_id": study["module_id"],
        "audit_tool": tool_id,
        "canonical_role_id": tool.canonical_role_id,
        "resource_class": tool.resource_class,
        "effective_inputs_sha256": study["effective_inputs_sha256"],
        "status": "completed",
        "diagnostic_status": None,
        "diagnostic": None,
        "error": None,
    }
    try:
        result["diagnostic"] = tool.handler(repo, study, artifacts_dir)
        diagnostic = result["diagnostic"]
        result["diagnostic_status"] = (
            diagnostic.get("diagnostic_status", "completed")
            if isinstance(diagnostic, dict)
            else "completed"
        )
    except Exception as exc:  # reports retain failure context for task-local triage
        result["status"] = "failed"
        result["error"] = {"type": type(exc).__name__, "message": str(exc)}
    report_path = destination / "audit-report.json"
    result["report_path"] = report_path.relative_to(repo).as_posix()
    with report_path.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    return result
