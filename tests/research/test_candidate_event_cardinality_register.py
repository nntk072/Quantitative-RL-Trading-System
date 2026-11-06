from __future__ import annotations

import json

import pytest
from scripts.research.analysis.evidence.build_candidate_event_cardinality_register import (
    build_identity_contract,
    trace_paths_by_scope,
)

from decisioning.trade_setup import TRADE_SETUP_CANDIDATES


def test_trace_paths_separate_current_baselines_from_other_scanned_artifacts() -> None:
    trace = {
        "per_decision_setup_trace_paths": [
            "outputs/historical_run/setup_trace.csv::file_rows",
            "evidence/research/matched_setup_baselines/run/always_no_trade/decisions.csv::file_rows",
        ]
    }

    current, other = trace_paths_by_scope(trace, "per_decision_setup_trace_paths")

    assert current == [
        "evidence/research/matched_setup_baselines/run/always_no_trade/decisions.csv::file_rows"
    ]
    assert other == ["outputs/historical_run/setup_trace.csv::file_rows"]


def test_trace_scope_is_empty_when_inventory_has_no_paths() -> None:
    assert trace_paths_by_scope({}, "per_decision_price_geometry_trace_paths") == ([], [])


def test_identity_contract_covers_all_candidates_with_catalog_semantics() -> None:
    census_rows = [
        {
            "candidate_id": str(candidate.candidate_id),
            "idea": str(candidate.idea),
            "timeframe": str(candidate.setup_timeframe),
            "direction": "long" if candidate.direction == 1 else "short",
            "support_status": "supported",
            "active_m1_rows": "0",
            "distinct_source_event_ids": "0",
            "identified_identity_episode_starts": "0",
            "adjacent_active_identity_changes": "0",
            "missing_source_event_time_rows": "0",
            "identity_coverage_fraction": "",
        }
        for candidate in TRADE_SETUP_CANDIDATES[1:]
    ]

    result = build_identity_contract(census_rows)

    assert [int(row["candidate_id"]) for row in result] == list(range(1, 109))
    assert all(row["identity_version"] for row in result)
    assert all(row["required_source_time_fields"] != "[]" for row in result)
    assert all(row["numeric_candidate_id_in_serialized_key"] == "false" for row in result)
    po3_m1_long = result[0]
    fields = json.loads(po3_m1_long["required_source_time_fields"])
    assert [item["field"] for item in fields] == [
        "po3_sweep_time_ns",
        "po3_reclaim_time_ns",
        "ifvg_bull_confirmed_at_time_ns",
        "ifvg_bull_fvg_origin_time_ns",
    ]


def test_identity_contract_rejects_census_catalog_semantic_drift() -> None:
    census_rows = [
        {
            "candidate_id": str(candidate.candidate_id),
            "idea": str(candidate.idea),
            "timeframe": str(candidate.setup_timeframe),
            "direction": "long" if candidate.direction == 1 else "short",
        }
        for candidate in TRADE_SETUP_CANDIDATES[1:]
    ]
    census_rows[0]["timeframe"] = "M3"

    with pytest.raises(ValueError, match="canonical catalog"):
        build_identity_contract(census_rows)
