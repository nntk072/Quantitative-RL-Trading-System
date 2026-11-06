from __future__ import annotations

import pytest

from decisioning.trade_setup import (
    CANDIDATE_GEOMETRY_ENTRY_TYPES,
    CANDIDATE_GEOMETRY_FEATURE_NAMES,
    candidate_geometry_observation_schema,
    candidate_geometry_slot,
    candidate_geometry_slot_count,
    candidate_geometry_slot_semantics,
)


def test_candidate_geometry_slots_round_trip_the_full_setup_entry_pair() -> None:
    assert candidate_geometry_slot_count() == 217
    assert candidate_geometry_slot_semantics(0) == (0, "market")
    for candidate_id in range(1, 109):
        for entry_type in CANDIDATE_GEOMETRY_ENTRY_TYPES:
            slot = candidate_geometry_slot(candidate_id, entry_type)
            assert candidate_geometry_slot_semantics(slot) == (candidate_id, entry_type)


@pytest.mark.parametrize(
    ("candidate_id", "entry_type"),
    [(0, "market"), (109, "market"), (2.5, "limit"), (1, "stop")],
)
def test_candidate_geometry_rejects_invalid_candidate_slot_inputs(
    candidate_id: int | float, entry_type: str
) -> None:
    with pytest.raises(ValueError):
        candidate_geometry_slot(candidate_id, entry_type)


def test_candidate_geometry_observation_schema_versions_fixed_slot_contract() -> None:
    schema = candidate_geometry_observation_schema()
    assert schema["candidate_count"] == 217
    assert schema["feature_names"] == list(CANDIDATE_GEOMETRY_FEATURE_NAMES)
    assert schema["no_trade_slot"] == 0
    assert schema["candidate_ids_key"] == "candidate_ids"
    assert schema["candidate_features_key"] == "candidate_features"
    assert schema["candidate_mask_key"] == "candidate_mask"
