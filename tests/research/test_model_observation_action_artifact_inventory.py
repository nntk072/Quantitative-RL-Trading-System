"""Contract tests for run-artifact observation/action evidence extraction."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.research.analysis.models.inspect_observation_action_artifacts import (
    _inspect_json,
    _record_trace_status,
    build_report,
)


def test_run_manifest_shapes_and_action_schema_are_extracted(tmp_path: Path) -> None:
    """Extract explicit run shapes without inferring widths from configs."""
    manifest = tmp_path / "run_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "observation_space_shapes": {"seq": [60, 746], "seq_mask": [60]},
                "action_schema": {
                    "version": "setup-v1",
                    "width": 6,
                    "coordinates": ["setup", "risk"],
                },
                "checkpoint": {"path": "model/ppo_final.zip", "sha256": "abc123"},
            }
        ),
        encoding="utf-8",
    )

    result = _inspect_json(manifest, "run_manifest.json")

    assert result["parse_status"] == "parsed"
    assert result["observation_shapes"] == [
        {
            "json_path": "$",
            "shapes": {"seq": [60, 746], "seq_mask": [60]},
        }
    ]
    assert result["action_schemas"][0]["width"] == 6
    assert result["checkpoint_references"] == [
        {
            "json_path": "$.checkpoint",
            "path": "model/ppo_final.zip",
            "sha256_recorded": "abc123",
        }
    ]


def test_trade_examples_are_not_mistaken_for_per_decision_policy_traces() -> None:
    """Trade-level setup metadata cannot prove decision-level selected actions."""
    report = {
        "trade_examples": [
            {
                "decision_time": "2025-01-01T00:00:00Z",
                "entry_price": 100.0,
                "setup": {"idea": "fvg"},
            }
        ]
    }

    assert _record_trace_status(report) == (False, False, [])


def test_selected_setup_trace_requires_complete_candidate_price_geometry() -> None:
    """Separate a setup decision trace from the stronger geometry trace."""
    setup_rows = [
        {"decision_step": 10, "selected_setup_id": 4},
        {"decision_step": 11, "selected_setup_id": 7},
    ]
    geometry_rows = [
        {
            "decision_time": "2025-01-01T00:00:00Z",
            "chosen_setup_id": 4,
            "proposed_entry_price": 100.0,
            "stop_anchor": 99.0,
            "target_price": 102.0,
            "order_ttl": 5,
        }
    ]

    assert _record_trace_status({"actions": setup_rows}) == (True, False, ["$.actions"])
    assert _record_trace_status({"decisions": geometry_rows}) == (True, True, ["$.decisions"])


def test_candidate_geometry_fields_must_coexist_on_one_decision_row() -> None:
    """Fields split across decisions do not establish per-candidate geometry."""
    rows = [
        {
            "decision_id": "run-1:d1",
            "selected_setup_id": 4,
            "proposed_entry_price": 100.0,
            "stop_anchor": 99.0,
        },
        {
            "decision_id": "run-1:d2",
            "selected_setup_id": 7,
            "target_price": 102.0,
            "order_ttl": 5,
        },
    ]

    assert _record_trace_status({"decisions": rows}) == (True, False, ["$.decisions"])


def test_setup_trace_requires_populated_decision_and_candidate_values() -> None:
    """Schema-only fields with missing values do not count as a chosen setup."""
    report = {
        "actions": [
            {"decision_id": "run-1:d1", "selected_setup_id": None},
            {"decision_id": "", "selected_setup_id": 4},
        ]
    }

    assert _record_trace_status(report) == (False, False, [])


def test_root_inventory_records_absence_as_scoped_not_global(tmp_path: Path) -> None:
    """The report should delimit a negative search to its supplied root."""
    (tmp_path / "training_log.json").write_text(
        json.dumps({"action_space_width": 6}), encoding="utf-8"
    )

    report = build_report([tmp_path])

    assert report["artifact_count"] == 1
    assert report["action_schema_evidence_status"] == "found"
    assert report["per_decision_setup_trace_status"] == "not_found_in_scanned_artifacts"
    assert any("supplied roots" in limitation for limitation in report["limitations"])


def test_root_inventory_detects_named_decision_trace_files(tmp_path: Path) -> None:
    """A structured selected-setup CSV is reported with its artifact path."""
    trace = tmp_path / "policy_setup_trace.csv"
    trace.write_text("decision_step,selected_setup_id\n10,4\n", encoding="utf-8")

    report = build_report([tmp_path])

    assert report["per_decision_setup_trace_status"] == "found"
    assert report["per_decision_setup_trace_paths"] == [
        f"{tmp_path / 'policy_setup_trace.csv'}::file_rows"
    ]
    assert report["per_decision_price_geometry_trace_status"] == "not_found_in_scanned_artifacts"


def test_root_inventory_detects_canonical_trade_setup_decisions_export(tmp_path: Path) -> None:
    """The evaluator's persisted decision export is recognized by its own schema."""
    trace = tmp_path / "trade_setup_decisions.csv"
    trace.write_text(
        "decision_id,trade_setup_candidate_id,decision_time\nrun-1:d1,4,2025-01-01T00:00:00Z\n",
        encoding="utf-8",
    )

    report = build_report([tmp_path])

    assert report["per_decision_setup_trace_status"] == "found"
    assert report["per_decision_setup_trace_paths"] == [
        f"{tmp_path / 'trade_setup_decisions.csv'}::file_rows"
    ]
    assert report["per_decision_price_geometry_trace_status"] == ("not_found_in_scanned_artifacts")


def test_header_only_trade_setup_export_is_not_a_decision_trace(tmp_path: Path) -> None:
    """An empty evaluation export must not count as observed policy decisions."""
    trace = tmp_path / "trade_setup_decisions.csv"
    trace.write_text(
        "decision_id,trade_setup_candidate_id,decision_time\n",
        encoding="utf-8",
    )

    report = build_report([tmp_path])

    assert report["per_decision_setup_trace_status"] == "not_found_in_scanned_artifacts"


def test_decision_export_requires_populated_identifier_values(tmp_path: Path) -> None:
    """Columns without a decision ID and selected candidate value are insufficient."""
    trace = tmp_path / "trade_setup_decisions.csv"
    trace.write_text(
        "decision_id,trade_setup_candidate_id,decision_time\nrun-1:d1,,2025-01-01T00:00:00Z\n",
        encoding="utf-8",
    )

    report = build_report([tmp_path])

    assert report["per_decision_setup_trace_status"] == "not_found_in_scanned_artifacts"


def test_csv_geometry_fields_must_coexist_on_one_decision_row(tmp_path: Path) -> None:
    """CSV headers or different rows cannot combine into one geometry trace."""
    trace = tmp_path / "policy_candidate_trace.csv"
    trace.write_text(
        "decision_id,selected_setup_id,proposed_entry_price,stop_anchor,target_price,order_ttl\n"
        "run-1:d1,4,100,99,,\n"
        "run-1:d2,7,,,102,5\n",
        encoding="utf-8",
    )

    report = build_report([tmp_path])

    assert report["per_decision_setup_trace_status"] == "found"
    assert report["per_decision_price_geometry_trace_status"] == ("not_found_in_scanned_artifacts")
