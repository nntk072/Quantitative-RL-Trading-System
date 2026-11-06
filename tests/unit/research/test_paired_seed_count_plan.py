from __future__ import annotations

from typing import Any

import pytest
from scripts.research.analysis.evidence.plan_paired_seed_count import plan_paired_seed_count


def test_seed_count_plan_finds_smallest_pair_count_at_target_power() -> None:
    result = plan_paired_seed_count(
        minimum_effect=1.0,
        paired_standard_deviation=2.0,
        minimum_effect_source="validation_protocol.md#minimum-effect",
        paired_standard_deviation_source="pilot-seed-variance.json#paired_sd",
        target_power=0.8,
        alpha=0.05,
        minimum_pairs=6,
        maximum_pairs=100,
    )

    assert result["schema_version"] == "paired_seed_count_plan.v1"
    assert result["planned_pair_count"] >= 6
    assert result["estimated_power_at_planned_count"] >= 0.8
    assert result["confirmatory_test"] == "one-sided paired sign-flip test"
    assert result["campaign_authorized"] is False
    assert result["method"] == "one-sided paired noncentral-t power approximation"
    assert result["input_provenance"] == {
        "minimum_effect": "validation_protocol.md#minimum-effect",
        "paired_standard_deviation": "pilot-seed-variance.json#paired_sd",
    }
    if result["planned_pair_count"] > 6:
        with pytest.raises(ValueError, match="target power was not reached"):
            plan_paired_seed_count(
                minimum_effect=1.0,
                paired_standard_deviation=2.0,
                minimum_effect_source="validation_protocol.md#minimum-effect",
                paired_standard_deviation_source="pilot-seed-variance.json#paired_sd",
                target_power=0.8,
                alpha=0.05,
                minimum_pairs=6,
                maximum_pairs=result["planned_pair_count"] - 1,
            )


def test_seed_count_plan_obeys_minimum_pairs_and_zero_variance_boundary() -> None:
    result = plan_paired_seed_count(
        minimum_effect=1.0,
        paired_standard_deviation=0.0,
        minimum_effect_source="protocol#effect",
        paired_standard_deviation_source="pilot#paired-sd",
        minimum_pairs=6,
        maximum_pairs=6,
    )

    assert result["planned_pair_count"] == 6
    assert result["estimated_power_at_planned_count"] == 1.0


def test_seed_count_plan_requires_explicitly_justifiable_bounded_inputs() -> None:
    with pytest.raises(ValueError, match="minimum_effect must be positive"):
        plan_paired_seed_count(
            minimum_effect=0.0,
            paired_standard_deviation=1.0,
            minimum_effect_source="protocol#effect",
            paired_standard_deviation_source="pilot#paired-sd",
        )
    with pytest.raises(ValueError, match="provenance references must be non-empty"):
        plan_paired_seed_count(
            minimum_effect=1.0,
            paired_standard_deviation=1.0,
            minimum_effect_source=" ",
            paired_standard_deviation_source="pilot#paired-sd",
        )
    with pytest.raises(ValueError, match="at least six"):
        plan_paired_seed_count(
            minimum_effect=1.0,
            paired_standard_deviation=1.0,
            minimum_effect_source="protocol#effect",
            paired_standard_deviation_source="pilot#paired-sd",
            minimum_pairs=5,
        )
    with pytest.raises(ValueError, match="target power was not reached"):
        plan_paired_seed_count(
            minimum_effect=0.001,
            paired_standard_deviation=1.0,
            minimum_effect_source="protocol#effect",
            paired_standard_deviation_source="pilot#paired-sd",
            maximum_pairs=6,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("minimum_effect", True),
        ("paired_standard_deviation", False),
        ("target_power", True),
        ("alpha", False),
    ],
)
def test_seed_count_plan_rejects_boolean_power_inputs(field: str, value: bool) -> None:
    inputs: dict[str, Any] = {
        "minimum_effect": 1.0,
        "paired_standard_deviation": 1.0,
        "minimum_effect_source": "protocol#effect",
        "paired_standard_deviation_source": "pilot#paired-sd",
    }
    inputs[field] = value

    with pytest.raises(ValueError, match="power inputs must be finite"):
        plan_paired_seed_count(**inputs)
