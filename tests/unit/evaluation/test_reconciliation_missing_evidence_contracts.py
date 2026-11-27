"""Missing account and breach evidence must remain explicitly incomplete."""

from __future__ import annotations

import pandas as pd

from evaluation.reporting import account_state_trace_reconciliation as account_trace
from evaluation.reporting.policy_decision_reconciliation import reconcile_policy_decisions


def test_account_trace_with_nonfinite_initial_balance_is_incomplete() -> None:
    row: dict[str, object] = {column: None for column in account_trace._REQUIRED_TRACE_COLUMNS}
    row.update(
        {
            "schema_version": "account_state_trace.v2",
            "state_phase": "post_action_valuation",
            "session_id": 1,
            "initial_balance": float("nan"),
            "trade_event_count": 0,
            "valuation_time": "2025-05-01T15:00:00Z",
        }
    )

    report = account_trace.reconcile_account_state_trace(
        pd.DataFrame([row]), pd.DataFrame(), breach_events=[]
    )

    assert report["status"] == "incomplete"
    assert "initial_balance_is_not_finite" in report["incomplete_reasons"]
    assert report["checks"] == {}


def test_policy_reconciliation_does_not_pass_without_breach_ledger() -> None:
    decisions = pd.DataFrame(
        [
            {
                "schema_version": "event_backtest_policy_decision.v1",
                "decision_id": "d1",
                "action": 0,
            }
        ]
    )

    report = reconcile_policy_decisions(decisions, pd.DataFrame(), breach_events=None)

    assert report["status"] == "incomplete"
    assert "breach_event_ledger_not_supplied" in report["incomplete_reasons"]
    assert report["failure_count"] == 0
