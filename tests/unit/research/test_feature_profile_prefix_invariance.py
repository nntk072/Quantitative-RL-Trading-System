from __future__ import annotations

import json

import pandas as pd
import pytest
from scripts.research.analysis.features.verify_feature_profile_prefix_invariance import (
    _compare_prefix,
    _feature_fingerprint,
    _resolved_feature_groups,
)


def test_compare_prefix_accepts_identical_features_and_reports_mutation() -> None:
    index = pd.date_range("2025-01-01", periods=3, freq="1min", tz="UTC")
    full = pd.DataFrame({"signal": [0.0, 1.0, 1.5]}, index=index)
    prefix = full.iloc[:2].copy()
    cutoff = index[1]

    assert _compare_prefix(full, prefix, cutoff)["passed"] is True

    prefix.iloc[1, 0] = 0.5
    result = _compare_prefix(full, prefix, cutoff)

    assert result["passed"] is False
    assert result["changed_features"] == [
        {
            "feature": "signal",
            "mismatch_rows": 1,
            "first_timestamp": index[1].isoformat(),
            "max_abs_delta": 0.5,
            "nan_mask_mismatches": 0,
        }
    ]


def test_resolved_feature_groups_require_current_profile_fingerprints(
    tmp_path,
) -> None:
    features = {"enabled": ["po3", "ifvg"], "window": 12}
    fingerprint = _feature_fingerprint(features)
    inventory = {
        "profiles": [
            {"profile_id": "profile/a", "features": features, "source_paths": []},
            {"profile_id": "profile/b", "features": features, "source_paths": []},
        ],
        "distinct_feature_configs": [
            {"feature_config_sha256": fingerprint, "profile_ids": ["profile/a", "profile/b"]}
        ],
    }
    path = tmp_path / "inventory.json"
    path.write_text(json.dumps(inventory), encoding="utf-8")

    loaded, groups, resolver_hashes = _resolved_feature_groups(path)

    assert loaded["profiles"] == inventory["profiles"]
    assert len(groups) == 1
    assert groups[0]["profile_ids"] == ["profile/a", "profile/b"]
    assert resolver_hashes == {}


def test_resolved_feature_groups_reject_stale_fingerprint(tmp_path) -> None:
    inventory = {
        "profiles": [
            {"profile_id": "profile/a", "features": {"enabled": True}, "source_paths": []}
        ],
        "distinct_feature_configs": [
            {"feature_config_sha256": "0" * 64, "profile_ids": ["profile/a"]}
        ],
    }
    path = tmp_path / "inventory.json"
    path.write_text(json.dumps(inventory), encoding="utf-8")

    with pytest.raises(ValueError, match="fingerprint does not match"):
        _resolved_feature_groups(path)
