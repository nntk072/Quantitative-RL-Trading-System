"""Missing decision and order identities must never be inferred."""

from __future__ import annotations

from typing import Any

import pandas as pd
import pytest

from evaluation.reporting.policy_decision_reconciliation import reconcile_policy_decisions


def _decision(**overrides: Any) -> pd.DataFrame:
    record: dict[str, Any] = {
        "schema_version": "event_backtest_policy_decision.v2",
        "decision_id": "d1",
        "decision_time": "2025-01-01T00:02:00Z",
        "action": 1,
        "execution_type": "market",
        "trade_setup_candidate_id": 5,
        "trade_setup_eligible": True,
        "eligible_candidate_count": 1,
        "eligible_trade_setup_ids": [5],
        "trade_setup_source_event_id": "source-5",
        "trade_setup_source_event_identity_status": "identified",
        "position_direction_at_decision": 0,
        "position_id_at_decision": None,
        "pending_order_id_at_decision": None,
    }
    record.update(overrides)
    return pd.DataFrame([record])


def _order_events(*rows: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["type", "decision_id", "order_id", "position_id"])


@pytest.mark.parametrize(
    ("event", "reason"),
    [
        (
            {"type": "order_submit", "decision_id": None, "order_id": "o1"},
            "submitted_order_missing_decision_id",
        ),
        (
            {"type": "order_fill", "decision_id": None, "order_id": "o1"},
            "order_lifecycle_event_missing_decision_id",
        ),
        (
            {"type": "reject", "decision_id": None, "order_id": "o1"},
            "order_rejection_missing_decision_id",
        ),
        (
            {"type": "order_cancel", "decision_id": "d1", "order_id": None},
            "order_lifecycle_event_missing_order_id",
        ),
        (
            {"type": "close", "decision_id": "d1", "position_id": None},
            "close_event_missing_position_id",
        ),
    ],
)
def test_reconciliation_keeps_missing_order_and_event_identity_incomplete(
    event: dict[str, Any], reason: str
) -> None:
    report = reconcile_policy_decisions(_decision(), _order_events(event), [])

    assert report["status"] == "incomplete"
    assert reason in report["incomplete_reasons"]


def test_v2_decision_without_position_context_stays_incomplete() -> None:
    report = reconcile_policy_decisions(
        _decision().drop(columns="position_direction_at_decision"),
        pd.DataFrame(),
        [],
    )

    assert report["status"] == "incomplete"
    assert "decision_position_context_columns_missing" in report["incomplete_reasons"]
    assert report["checks"] == {}


def test_open_and_close_rows_require_position_and_decision_identity() -> None:
    submit = {
        "type": "order_submit",
        "decision_id": "d1",
        "order_id": "o1",
        "direction": 1,
        "trade_setup_candidate_id": 5,
        "trade_setup_source_event_id": "source-5",
        "trade_setup_source_event_identity_status": "identified",
    }
    opened_without_position_id = {
        **submit,
        "type": "open",
        "position_id": None,
        "price": 100.0,
        "time": "2025-01-01T00:03:00Z",
    }
    report = reconcile_policy_decisions(
        _decision(),
        pd.DataFrame([submit, opened_without_position_id]),
        [],
    )
    assert "opened_position_missing_position_id" in report["incomplete_reasons"]

    opened_without_decision_id = {
        **submit,
        "type": "open",
        "decision_id": None,
        "position_id": "p1",
        "price": 100.0,
        "time": "2025-01-01T00:03:00Z",
    }
    report = reconcile_policy_decisions(
        _decision(),
        pd.DataFrame([submit, opened_without_decision_id]),
        [],
    )
    assert "opened_position_missing_decision_id" in report["incomplete_reasons"]


@pytest.mark.parametrize("missing_field", ["limit_price", "expiry_time", "fill_price", "fill_time"])
def test_limit_fill_without_required_contract_field_is_incomplete(missing_field: str) -> None:
    decision = _decision(execution_type="limit")
    submit: dict[str, Any] = {
        "type": "order_submit",
        "decision_id": "d1",
        "order_id": "o1",
        "order_type": "limit",
        "direction": 1,
        "limit_price": 100.0,
        "order_submission_time": "2025-01-01T00:02:00Z",
        "expiry_time": "2025-01-01T00:05:00Z",
        "trade_setup_candidate_id": 5,
        "trade_setup_source_event_id": "source-5",
        "trade_setup_source_event_identity_status": "identified",
    }
    fill: dict[str, Any] = {
        "type": "order_fill",
        "decision_id": "d1",
        "order_id": "o1",
        "direction": 1,
        "price": 100.0,
        "bid": 99.75,
        "ask": 100.0,
        "time": "2025-01-01T00:03:00Z",
        "trade_setup_candidate_id": 5,
        "trade_setup_source_event_id": "source-5",
        "trade_setup_source_event_identity_status": "identified",
    }
    opened = {
        "type": "open",
        "decision_id": "d1",
        "order_id": "o1",
        "position_id": "p1",
        "direction": 1,
        "price": 100.0,
        "fill_time": "2025-01-01T00:03:00Z",
        "trade_setup_candidate_id": 5,
        "trade_setup_source_event_id": "source-5",
        "trade_setup_source_event_identity_status": "identified",
    }
    close = {
        "type": "close",
        "decision_id": "d1",
        "position_id": "p1",
        "position_complete": True,
        "time": "2025-01-01T00:04:00Z",
    }
    if missing_field == "limit_price":
        submit["limit_price"] = None
    elif missing_field == "expiry_time":
        submit["expiry_time"] = None
    elif missing_field == "fill_price":
        fill["price"] = None
    else:
        fill["time"] = None
        opened["fill_time"] = None

    report = reconcile_policy_decisions(decision, pd.DataFrame([submit, fill, opened, close]), [])

    assert report["status"] == "incomplete"
    assert "limit_fill_contract_fields_missing" in report["incomplete_reasons"]
