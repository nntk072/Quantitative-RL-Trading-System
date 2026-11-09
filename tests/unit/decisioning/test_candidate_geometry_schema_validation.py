from __future__ import annotations

import pytest

from decisioning.trade_setup import (
    candidate_geometry_observation_schema,
    validate_candidate_geometry_observation_schema,
)


def test_candidate_geometry_observation_schema_round_trip_and_mismatch() -> None:
    expected = candidate_geometry_observation_schema()
    validate_candidate_geometry_observation_schema(expected, expected)

    mutated = dict(expected)
    candidate_count = expected["candidate_count"]
    assert isinstance(candidate_count, int)
    mutated["candidate_count"] = candidate_count - 1
    with pytest.raises(ValueError, match="candidate geometry observation schema"):
        validate_candidate_geometry_observation_schema(mutated, expected)


def test_candidate_geometry_schema_is_absent_for_non_price_aware_checkpoint() -> None:
    validate_candidate_geometry_observation_schema(None, None)
    with pytest.raises(ValueError, match="candidate geometry observation schema"):
        validate_candidate_geometry_observation_schema(
            None, candidate_geometry_observation_schema()
        )
