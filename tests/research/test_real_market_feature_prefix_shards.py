from __future__ import annotations

from typing import Any

import pytest
from scripts.research.analysis.features.merge_real_market_feature_prefix_shards import (
    merge_reports,
)
from scripts.research.analysis.features.verify_real_market_feature_prefix_invariance import (
    AUDIT_SCRIPT_SHA256,
)


def _report(index: int, *, source_hash: str = "source") -> dict[str, Any]:
    profile = f"p{index}"
    group = f"g{index}"
    cutoffs = [
        {"passed": True, "cutoff": "2025-12-15"},
        {"passed": True, "cutoff": "2026-03-09"},
        {"passed": True, "cutoff": "2026-06-15"},
    ]
    return {
        "audit": "real_market_feature_prefix_invariance",
        "profile_inventory_sha256": "inventory",
        "profile_inventory_mode": True,
        "feature_version": "v1",
        "audit_script_sha256": AUDIT_SCRIPT_SHA256,
        "source_hashes": {"source.py": source_hash},
        "resolved_profiles": ["p0", "p1"],
        "base_configs": [f"config/{index}.yaml"],
        "runtime": {"slurm_job_id": "job"},
        "profile_group_shard": {"index": index, "count": 2, "selected_groups": 1},
        "profile_groups": [
            {
                "profile_id": group,
                "profile_ids": [profile],
                "cutoffs": cutoffs,
                "summary": {"passed": 3, "failed": 0, "cutoffs": 3},
            }
        ],
        "input_files": {"bars.csv": "bars-hash"},
        "cutoffs": cutoffs,
        "summary": {"passed": 3, "failed": 0, "cutoffs": 3, "feature_profiles": 1},
    }


def test_merge_requires_full_shard_set_and_preserves_complete_groups() -> None:
    expected = {"g0": {"p0"}, "g1": {"p1"}}

    with pytest.raises(ValueError, match="does not contain every declared shard"):
        merge_reports([_report(0)], expected)

    merged = merge_reports([_report(0), _report(1)], expected)

    assert merged["profile_group_shard"] == {"merged_count": 2}
    assert [item["profile_id"] for item in merged["profile_groups"]] == ["g0", "g1"]
    assert merged["resolved_profiles"] == ["p0", "p1"]
    assert merged["summary"] == {
        "passed": 6,
        "failed": 0,
        "cutoffs": 6,
        "feature_profiles": 2,
    }


def test_merge_rejects_duplicate_or_missing_profile_groups() -> None:
    expected = {"g0": {"p0"}, "g1": {"p1"}}
    duplicate = _report(1)
    duplicate["profile_groups"][0]["profile_id"] = "g0"

    with pytest.raises(ValueError, match="duplicate feature-builder group"):
        merge_reports([_report(0), duplicate], expected)

    missing = _report(1)
    missing["profile_groups"] = []
    missing["profile_group_shard"]["selected_groups"] = 0
    with pytest.raises(ValueError, match="profile-group coverage mismatch"):
        merge_reports([_report(0), missing], expected)


def test_merge_rejects_shards_from_different_sources() -> None:
    with pytest.raises(ValueError, match="disagree on source_hashes"):
        merge_reports(
            [_report(0), _report(1, source_hash="different")], {"g0": {"p0"}, "g1": {"p1"}}
        )


def test_merge_rejects_incomplete_group_cutoff_set() -> None:
    partial = _report(1)
    partial["profile_groups"][0]["cutoffs"] = partial["profile_groups"][0]["cutoffs"][:2]

    with pytest.raises(ValueError, match="incomplete cutoff set"):
        merge_reports([_report(0), partial], {"g0": {"p0"}, "g1": {"p1"}})


def test_merge_rejects_stale_script_or_incomplete_inventory_metadata() -> None:
    stale_reports = [_report(0), _report(1)]
    for report in stale_reports:
        report["audit_script_sha256"] = "stale-script"

    with pytest.raises(ValueError, match="does not match the current source"):
        merge_reports(stale_reports, {"g0": {"p0"}, "g1": {"p1"}})

    incomplete = _report(1)
    incomplete["resolved_profiles"] = ["p1"]
    with pytest.raises(ValueError, match="complete resolved profile inventory"):
        merge_reports([_report(0), incomplete], {"g0": {"p0"}, "g1": {"p1"}})
