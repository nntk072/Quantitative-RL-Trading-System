"""Feature-module diagnostics exposed through the study audit registry."""

from __future__ import annotations

import csv
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any


def _write_json(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def _causal_availability(root: Path, output_dir: Path) -> dict[str, Any]:
    from research_tools.features.features.build_feature_causality_matrix import (
        FIELDS,
        build_matrix,
    )

    census_dir = root / "evidence/research/trade_setup_opportunity_census"
    try:
        rows, summary = build_matrix(census_dir)
    except FileNotFoundError as exc:
        return {
            "diagnostic_status": "blocked_missing_input",
            "required_input": (
                "candidate census files under "
                f"{census_dir} (candidate_summary.csv and "
                "candidate_event_identity_summary.csv)"
            ),
            "reason": str(exc),
        }
    matrix_path = output_dir / "feature_causality_matrix.csv"
    with matrix_path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    _write_json(output_dir / "feature_causality_summary.json", summary)
    return {
        "diagnostic_status": summary["acceptance_status"],
        "matrix_row_count": len(rows),
        "summary": summary,
        "matrix_path": matrix_path.name,
    }


def _prefix_causality(root: Path, output_dir: Path) -> dict[str, Any]:
    from research_tools.features.features.build_feature_configuration_inventory import (
        build_inventory,
    )
    from research_tools.features.features.verify_feature_profile_prefix_invariance import (
        run_audit,
    )

    inventory_path = output_dir / "feature_configuration_inventory.json"
    _write_json(inventory_path, build_inventory())
    report = run_audit(inventory_path=inventory_path, rows=3600, cutoff_row=2400)
    _write_json(output_dir / "feature_profile_prefix_invariance.json", report)
    return {
        "diagnostic_status": "passed" if report["summary"]["failed"] == 0 else "failed",
        "report_path": "feature_profile_prefix_invariance.json",
        "summary": report["summary"],
        "scope_note": report["scope_note"],
        "inventory_sha256": report["inventory_sha256"],
        "repository_root": str(root),
    }


def _candidate_geometry(root: Path, output_dir: Path) -> dict[str, Any]:
    from configuration.configuration_loader import load_config
    from research_tools.features.evaluation.build_candidate_proposal_ledger import build_ledger
    from research_tools.features.features.candidate_geometry_support import build_report
    from research_tools.features.features.training_context import DEFAULT_CONFIG

    config_path = DEFAULT_CONFIG
    cfg = load_config(config_path=config_path)
    cfg.features.entry_ideas.enabled = True
    report_dir = output_dir / "candidate_geometry_support"
    try:
        report = build_report(cfg, report_dir, config_path=config_path)
    except FileNotFoundError as exc:
        return {
            "diagnostic_status": "blocked_missing_input",
            "required_input": str(exc.filename or exc),
            "reason": str(exc),
        }
    proposal_dir = output_dir / "candidate_proposal_ledger"
    proposal_cfg = load_config(config_path=config_path)
    try:
        proposal = build_ledger(proposal_cfg, proposal_dir, config_path=config_path)
    except FileNotFoundError as exc:
        return {
            "diagnostic_status": "blocked_missing_input",
            "geometry_report_dir": report_dir.name,
            "required_input": str(exc.filename or exc),
            "reason": str(exc),
        }
    return {
        "diagnostic_status": "completed_preflight_only",
        "geometry_support": {
            "status": report["status"],
            "report_dir": report_dir.name,
            "training_rows": report["training_rows"],
            "candidate_count": report["candidate_count"],
            "training_input_sha256": report["training_input_sha256"],
            "interpretation": report["interpretation"],
        },
        "proposal_coverage": {
            "report_dir": proposal_dir.name,
            "candidate_event_count": proposal["candidate_event_count"],
            "policy_eligible_candidate_event_count": proposal[
                "policy_eligible_candidate_event_count"
            ],
            "proposal_event_count": proposal["proposal_event_count"],
            "proposal_count": proposal["proposal_count"],
            "outcome_replay": proposal["outcome_replay"],
        },
        "excluded_claims": [
            "proposal outcome replay and censoring dispositions",
            "matched policy comparison or economic value",
        ],
    }


def run_feature_audit(root: Path, study: Mapping[str, Any], output_dir: Path) -> dict[str, Any]:
    """Dispatch only feature audit IDs declared in the Python registry."""
    tool_id = study["audit_tool"]
    if tool_id == "features.causal_availability":
        return _causal_availability(root, output_dir)
    if tool_id == "features.prefix_causality":
        return _prefix_causality(root, output_dir)
    if tool_id == "features.candidate_geometry_support":
        return _candidate_geometry(root, output_dir)
    raise ValueError(f"unsupported feature audit tool: {tool_id}")
