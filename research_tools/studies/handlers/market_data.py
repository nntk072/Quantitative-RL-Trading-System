"""Current-data diagnostics exposed through the registered study tools."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any


def _write_json(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def _raw_data_quality(root: Path, output_dir: Path) -> dict[str, Any]:
    from market_data.quality_audit import build_report

    source_manifest_path = root / "evidence/research/data_identity/raw_data_manifest.json"
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    file_rows = source_manifest.get("files")
    if not isinstance(file_rows, list) or not file_rows:
        raise ValueError("registered raw-data manifest has no files list")
    data_inputs = {
        f"raw:{row['path']}": row["sha256"]
        for row in file_rows
        if isinstance(row, dict)
        and isinstance(row.get("path"), str)
        and isinstance(row.get("sha256"), str)
    }
    if len(data_inputs) != len(file_rows):
        raise ValueError("registered raw-data manifest has malformed file identities")
    fingerprint = hashlib.sha256(source_manifest_path.read_bytes()).hexdigest()
    campaign = {"fingerprint": fingerprint, "data_inputs": data_inputs}
    campaign_path = output_dir / "registered_raw_data_inputs.json"
    _write_json(campaign_path, campaign)
    report = build_report(campaign_path)
    _write_json(output_dir / "raw_data_quality_report.json", report)
    return {
        "diagnostic_status": (
            "passed"
            if report["all_inputs_present"] and report["all_input_hashes_match"]
            else "failed"
        ),
        "input_count": report["input_count"],
        "input_bytes_scanned": report["input_bytes_scanned"],
        "all_inputs_present": report["all_inputs_present"],
        "all_input_hashes_match": report["all_input_hashes_match"],
        "report_path": "raw_data_quality_report.json",
        "scope_note": report["evidence_role"],
    }


def _tick_coverage_and_quote_age(root: Path, output_dir: Path) -> dict[str, Any]:
    from research_tools.market_data.market_data.audit_tick_quote_coverage import (
        build_coverage_audit,
    )

    report_dir = output_dir / "tick_quote_coverage"
    report = build_coverage_audit(
        config_path=root / "config/base/default.yaml",
        output_dir=report_dir,
    )
    return {
        "diagnostic_status": "incomplete_quote_age_not_measured",
        "minute_coverage_status": report["status"],
        "report_dir": report_dir.name,
        "symbol": report["symbol"],
        "m1_rows": report["m1_rows"],
        "minutes_quote_complete": report["minutes_quote_complete"],
        "minutes_quote_incomplete": report["minutes_quote_incomplete"],
        "minutes_with_tick_count_mismatch": report["minutes_with_tick_count_mismatch"],
        "raw_tick_rows_without_valid_quote": report["raw_tick_rows_without_valid_quote"],
        "quote_age_distribution": "not measured by the registered source audit",
        "dependent_fill_claims": "blocked_until_carried_side_age_is_measured",
        "scope_note": (
            "The existing audit reconciles raw tick counts and two-sided quote validity by minute. "
            "It does not measure carried-side age or an age distribution; those remain unresolved."
        ),
    }


def run_market_data_audit(root: Path, study: Mapping[str, Any], output_dir: Path) -> dict[str, Any]:
    """Run one registered market-data diagnostic without changing source data."""
    tool_id = study["audit_tool"]
    if tool_id == "market_data.raw_data_quality":
        return _raw_data_quality(root, output_dir)
    if tool_id == "market_data.tick_coverage_and_quote_age":
        return _tick_coverage_and_quote_age(root, output_dir)
    raise ValueError(f"unsupported market-data audit tool: {tool_id}")
