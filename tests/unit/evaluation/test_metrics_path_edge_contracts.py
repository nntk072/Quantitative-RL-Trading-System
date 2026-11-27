"""Path metrics retain daily outcomes when breach timing is untraced."""

from __future__ import annotations

from typing import Any

import pytest

from evaluation.metrics import compute_metrics


def _session(session_id: int, *, start: float, end: float) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "session_start_equity": start,
        "equity": end,
        "cumulative_payouts": 0.0,
    }


def test_untraced_breach_keeps_daily_returns_but_withholds_ruin_timing() -> None:
    metrics = compute_metrics(
        [100.0, 102.0, 101.0],
        initial_balance=100.0,
        account_state_trace=[
            _session(4, start=100.0, end=102.0),
            _session(5, start=102.0, end=101.0),
        ],
        breach_events=[{"session_id": 99, "reason": "daily_loss"}],
        completed_data_split=True,
    )

    assert metrics.daily_return_count == 2
    assert metrics.daily_return_mean_pct == pytest.approx((2.0 - 100.0 / 102.0) / 2)
    assert metrics.time_to_ruin_sessions is None
    assert metrics.ruin_event_observed is None
    assert metrics.time_to_ruin_availability == "breach_session_not_in_account_trace"


def test_interleaved_account_sessions_invalidate_daily_path_evidence() -> None:
    metrics = compute_metrics(
        [100.0, 101.0],
        initial_balance=100.0,
        account_state_trace=[
            _session(4, start=100.0, end=100.5),
            _session(5, start=100.5, end=101.0),
            _session(4, start=100.0, end=101.0),
        ],
        breach_events=[],
        completed_data_split=True,
    )

    assert metrics.daily_return_count is None
    assert metrics.daily_return_availability == "account_state_trace_missing_or_invalid"
    assert metrics.time_to_ruin_sessions is None
