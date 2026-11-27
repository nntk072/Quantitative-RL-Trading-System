"""Remaining numerical input contracts for performance metrics."""

from __future__ import annotations

import math
from typing import Any

import pytest

from evaluation.metrics import compute_metrics, evaluation_periods_per_year


def test_nonpositive_payout_adjusted_account_value_withholds_daily_returns() -> None:
    metrics = compute_metrics(
        [100.0, 101.0],
        initial_balance=100.0,
        account_state_trace=[
            {
                "session_id": 1,
                "session_start_equity": 100.0,
                "equity": 101.0,
                "cumulative_payouts": -100.0,
            }
        ],
        breach_events=[],
        completed_data_split=True,
    )

    assert metrics.daily_return_count is None
    assert metrics.daily_return_mean_pct is None
    assert metrics.daily_return_availability == "account_state_trace_missing_or_invalid"


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_nonfinite_annualization_config_is_rejected(value: float) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        evaluation_periods_per_year({"evaluation": {"periods_per_year": value}})


def test_malformed_account_path_numbers_do_not_become_daily_returns() -> None:
    malformed: Any = "100.0"
    metrics = compute_metrics(
        [100.0, 101.0],
        initial_balance=100.0,
        account_state_trace=[
            {
                "session_id": 1,
                "session_start_equity": malformed,
                "equity": 101.0,
                "cumulative_payouts": 0.0,
            }
        ],
        breach_events=[],
        completed_data_split=True,
    )

    assert metrics.daily_return_count is None
    assert metrics.daily_return_availability == "account_state_trace_missing_or_invalid"
