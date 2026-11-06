from __future__ import annotations

import pandas as pd
from scripts.research.analysis.evaluation.score_rule_baselines import _period_scope


def test_exposed_interval_and_partial_overlaps_are_report_only() -> None:
    for index in (
        pd.DatetimeIndex(["2026-02-01", "2026-02-02"]),
        pd.DatetimeIndex(["2025-12-31", "2026-01-02"]),
        pd.DatetimeIndex(["2026-10-16", "2026-10-17"]),
    ):
        scope = _period_scope(index)

        assert scope["role"] == "exposed_report_only"
        assert scope["confirmatory"] is False


def test_other_intervals_are_unclassified_not_holdouts() -> None:
    scope = _period_scope(pd.DatetimeIndex(["2025-01-01", "2025-12-31"]))

    assert scope["role"] == "unclassified_non_confirmatory"
    assert scope["confirmatory"] is False


def test_empty_interval_has_no_period_claim() -> None:
    scope = _period_scope(pd.DatetimeIndex([]))

    assert scope == {
        "role": "empty",
        "confirmatory": False,
        "start": None,
        "end": None,
    }
