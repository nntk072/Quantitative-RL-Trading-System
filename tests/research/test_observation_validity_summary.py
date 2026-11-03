"""Tests for descriptive profile-wide observation-validity aggregation."""

from __future__ import annotations

import pytest
from scripts.research.analysis.features.summarize_observation_validity import (
    summarize_rows,
)


def _row(
    group: str,
    *,
    profile_ids: str = '["profile/a"]',
    sampled: int = 10,
    finite: int = 8,
    nonfinite: int = 2,
    leading: int = 1,
    interior: int = 1,
    zeros: int = 3,
    collision: str = "true",
) -> dict[str, str]:
    return {
        "profile_group": group,
        "representative_profile": group,
        "profile_ids": profile_ids,
        "timeframe": "M1",
        "feature": "example_feature",
        "sampled_rows": str(sampled),
        "finite_rows": str(finite),
        "nonfinite_rows": str(nonfinite),
        "nonfinite_fraction": str(nonfinite / sampled),
        "leading_nonfinite_rows": str(leading),
        "interior_nonfinite_rows": str(interior),
        "finite_zero_rows": str(zeros),
        "missing_collides_with_finite_zero": collision,
    }


def test_summarize_rows_aggregates_counts_and_descriptive_flags() -> None:
    summary = summarize_rows(
        [
            _row("group/a", profile_ids='["profile/a", "profile/shared"]'),
            _row(
                "group/b",
                profile_ids='["profile/b", "profile/shared"]',
                sampled=20,
                finite=20,
                nonfinite=0,
                leading=0,
                interior=0,
                zeros=4,
                collision="false",
            ),
        ]
    )

    assert summary == [
        {
            "timeframe": "M1",
            "feature": "example_feature",
            "profile_group_count": 2,
            "sampled_rows": 30,
            "finite_rows": 28,
            "nonfinite_rows": 2,
            "leading_nonfinite_rows": 1,
            "interior_nonfinite_rows": 1,
            "finite_zero_rows": 7,
            "fully_nonfinite_group_count": 0,
            "interior_missing_group_count": 1,
            "finite_zero_collision_group_count": 1,
            "groups_with_missing_values": 1,
            "profile_count": 3,
            "nonfinite_fraction": pytest.approx(2 / 30),
            "triage_flags": [
                "interior_missing_values_present",
                "missingness_varies_across_groups",
                "missing_collides_with_finite_zero",
            ],
        }
    ]


def test_summarize_rows_prioritizes_all_group_missingness() -> None:
    all_missing = _row(
        "group/a",
        sampled=10,
        finite=0,
        nonfinite=10,
        leading=0,
        interior=10,
        zeros=0,
    )
    partial = _row("group/b")
    all_missing["feature"] = "always_missing"

    summary = summarize_rows([partial, all_missing])

    assert summary[0]["feature"] == "always_missing"
    assert "fully_nonfinite_in_every_group" in summary[0]["triage_flags"]


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"finite_rows": "9"}, "finite/non-finite counts do not sum"),
        ({"interior_nonfinite_rows": "2"}, "leading/interior counts do not sum"),
        ({"profile_ids": "not-json"}, "profile_ids must be a JSON list"),
    ],
)
def test_summarize_rows_rejects_inconsistent_input(updates: dict[str, str], message: str) -> None:
    row = _row("group/a")
    row.update(updates)

    with pytest.raises(ValueError, match=message):
        summarize_rows([row])


def test_summarize_rows_rejects_duplicate_group_feature_keys() -> None:
    with pytest.raises(ValueError, match="duplicate profile-group feature key"):
        summarize_rows([_row("group/a"), _row("group/a")])
