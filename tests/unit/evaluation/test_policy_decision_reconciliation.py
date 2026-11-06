from __future__ import annotations

from typing import Any, cast

import pandas as pd

from decisioning.trade_setup import TRADE_SETUP_CATEGORY_COUNT
from evaluation.reporting.policy_decision_reconciliation import (
    _integer,
    _number,
    reconcile_policy_decisions,
)


def _decision(*, eligible: bool = True) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "schema_version": "event_backtest_policy_decision.v2",
                "decision_id": "d1",
                "decision_time": "2025-01-01T00:02:00Z",
                "action": 1,
                "trade_setup_candidate_id": 5,
                "trade_setup_eligible": eligible,
                "eligible_candidate_count": 2,
                "eligible_trade_setup_ids": [0, 5],
                "trade_setup_source_event_id": "source-event-5",
                "trade_setup_source_event_identity_status": "identified",
                "position_direction_at_decision": 0,
                "position_id_at_decision": None,
                "pending_order_id_at_decision": None,
            }
        ]
    )


def _events(*, include_open: bool = True) -> pd.DataFrame:
    rows: list[dict[str, object]] = [
        {
            "type": "order_submit",
            "order_id": "o1",
            "decision_id": "d1",
            "trade_setup_candidate_id": 5,
            "direction": 1,
            "trade_setup_source_event_id": "source-event-5",
            "trade_setup_source_event_identity_status": "identified",
        }
    ]
    if include_open:
        rows.append(
            {
                "type": "order_fill",
                "order_id": "o1",
                "decision_id": "d1",
                "direction": 1,
                "price": 99.5,
                "time": "2025-01-01T00:03:00Z",
                "trade_setup_candidate_id": 5,
                "trade_setup_source_event_id": "source-event-5",
                "trade_setup_source_event_identity_status": "identified",
            }
        )
        rows.append(
            {
                "type": "open",
                "order_id": "o1",
                "position_id": "p1",
                "decision_id": "d1",
                "trade_setup_candidate_id": 5,
                "direction": 1,
                "price": 99.5,
                "fill_time": "2025-01-01T00:03:00Z",
                "trade_setup_source_event_id": "source-event-5",
                "trade_setup_source_event_identity_status": "identified",
            }
        )
        rows.append(
            {
                "type": "close",
                "position_id": "p1",
                "position_complete": True,
            }
        )
    return pd.DataFrame(rows)


def _environment_decision(*, action: int = 1) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "schema_version": "environment_policy_decision.v2",
                "decision_id": "env:d1",
                "decision_time": "2025-01-01T00:02:00Z",
                "action": action,
                "execution_type": "market",
                "position_direction_at_decision": 0,
                "position_id_at_decision": None,
                "pending_order_id_at_decision": None,
                "trade_setup_candidate_id": 5,
                "trade_setup_eligible": True,
                "eligible_candidate_count": 2,
                "eligible_trade_setup_ids": [0, 5],
                "trade_setup_source_event_id": "source-event-5",
                "trade_setup_source_event_identity_status": "identified",
            }
        ]
    )


def _environment_market_events(*, direction: int = 1) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "type": "open",
                "position_id": "env:p1",
                "decision_id": "env:d1",
                "direction": direction,
                "time": "2025-01-01T00:03:00Z",
                "fill_time": "2025-01-01T00:03:00Z",
                "trade_setup_candidate_id": 5,
                "trade_setup_source_event_id": "source-event-5",
                "trade_setup_source_event_identity_status": "identified",
            },
            {
                "type": "close",
                "position_id": "env:p1",
                "position_complete": True,
                "time": "2025-01-01T00:04:00Z",
                "trade_setup_candidate_id": 5,
                "trade_setup_source_event_id": "source-event-5",
                "trade_setup_source_event_identity_status": "identified",
            },
        ]
    )


def test_policy_reconciliation_rejects_boolean_action_as_integer_one() -> None:
    decision = _decision().astype({"action": object})
    decision.at[0, "action"] = True

    result = reconcile_policy_decisions(decision, _events(), [])

    assert result["status"] != "matched"
    assert "decision_action_is_valid" in {failure["check"] for failure in result["failures"]}


def test_policy_reconciliation_rejects_boolean_numeric_values() -> None:
    assert _number(False) is None
    assert _number(True) is None
    numpy_bool = pd.Series([True]).iloc[0]
    assert _integer(numpy_bool) is None
    assert _number(numpy_bool) is None


def test_policy_reconciliation_rejects_string_setup_eligibility_flag() -> None:
    decision = _decision().astype({"trade_setup_eligible": object})
    decision.at[0, "trade_setup_eligible"] = "false"

    result = reconcile_policy_decisions(decision, _events(), [])

    assert result["status"] == "incomplete"
    assert "decision_eligibility_flag_is_invalid" in result["incomplete_reasons"]


def test_policy_reconciliation_rejects_string_position_completion_flag() -> None:
    events = _events()
    cast(Any, events).at[3, "position_complete"] = "false"

    result = reconcile_policy_decisions(_decision(), events, [])

    assert result["status"] == "incomplete"
    assert "position_completion_flag_is_invalid" in result["incomplete_reasons"]


def test_policy_reconciliation_links_eligible_decision_through_completed_position() -> None:
    result = reconcile_policy_decisions(_decision(), _events(), [])

    assert result["status"] == "matched", {
        "failures": result["failures"],
        "incomplete_reasons": result["incomplete_reasons"],
    }
    assert result["failure_count"] == 0, result["failures"]
    assert result["unclosed_position_ids"] == []
    assert result["checks"]["open_candidate_matches_decision"] == 1
    assert result["checks"]["submitted_source_event_matches_decision"] == 1
    assert result["checks"]["open_source_event_matches_decision"] == 1
    assert result["checks"]["filled_event_source_matches_submission"] == 2


def test_environment_policy_reconciliation_accepts_immediate_market_open() -> None:
    result = reconcile_policy_decisions(
        _environment_decision(),
        _environment_market_events(),
        [],
    )

    assert result["status"] == "matched", result
    assert result["checks"]["open_direction_matches_decision"] == 1
    assert "opened_position_missing_order_id" not in result["incomplete_reasons"]


def test_environment_policy_reconciliation_rejects_open_direction_drift() -> None:
    result = reconcile_policy_decisions(
        _environment_decision(action=-1),
        _environment_market_events(direction=1),
        [],
    )

    assert result["status"] == "mismatch"
    assert "open_direction_matches_decision" in {failure["check"] for failure in result["failures"]}


def test_policy_reconciliation_checks_limit_fill_price_and_lifetime() -> None:
    decision = _decision()
    decision["execution_type"] = "limit"
    events = _events()
    events.loc[0, "order_type"] = "limit"
    events.loc[0, "limit_price"] = 100.0
    events.loc[0, "decision_time"] = "2025-01-01T00:02:00Z"
    events.loc[0, "order_submission_time"] = "2025-01-01T00:02:00Z"
    events.loc[0, "expiry_time"] = "2025-01-01T00:05:00Z"
    events.loc[1, "order_type"] = "limit"
    events.loc[1, "bid"] = 99.25
    events.loc[1, "ask"] = 99.5
    events.loc[1, "price"] = 99.5
    events.loc[1, "time"] = "2025-01-01T00:03:00Z"
    events.loc[2, "time"] = "2025-01-01T00:03:00Z"
    events.loc[3, "time"] = "2025-01-01T00:04:00Z"

    result = reconcile_policy_decisions(decision, events, [])

    assert result["status"] == "matched", result
    assert result["checks"]["limit_fill_respects_price_bound"] == 1
    assert result["checks"]["limit_fill_occurs_inside_lifetime"] == 1
    assert result["checks"]["limit_fill_price_matches_executable_quote"] == 1
    assert result["checks"]["limit_fill_matches_open_price_and_time"] == 1

    events.loc[1, "bid"] = 99.75
    crossed_quote = reconcile_policy_decisions(decision, events, [])
    assert "limit_fill_quote_is_not_crossed" in {
        failure["check"] for failure in crossed_quote["failures"]
    }
    events.loc[1, "bid"] = 99.25

    events.loc[2, "price"] = 99.75
    open_price_mismatch = reconcile_policy_decisions(decision, events, [])
    assert "limit_fill_matches_open_price_and_time" in {
        failure["check"] for failure in open_price_mismatch["failures"]
    }
    events.loc[2, "price"] = 99.5

    short_decision = _decision().drop(
        columns=[
            "trade_setup_candidate_id",
            "trade_setup_eligible",
            "trade_setup_source_event_id",
            "trade_setup_source_event_identity_status",
        ]
    )
    short_decision.loc[0, "action"] = -1
    short_decision["execution_type"] = "limit"
    short_events = pd.DataFrame(
        [
            {
                "type": "order_submit",
                "order_id": "o-short",
                "decision_id": "d1",
                "order_type": "limit",
                "direction": -1,
                "limit_price": 100.0,
                "decision_time": "2025-01-01T00:02:00Z",
                "order_submission_time": "2025-01-01T00:02:00Z",
                "expiry_time": "2025-01-01T00:05:00Z",
            },
            {
                "type": "order_fill",
                "order_id": "o-short",
                "decision_id": "d1",
                "direction": -1,
                "bid": 100.5,
                "ask": 100.75,
                "price": 100.5,
                "time": "2025-01-01T00:03:00Z",
            },
            {
                "type": "open",
                "order_id": "o-short",
                "decision_id": "d1",
                "position_id": "p-short",
                "direction": -1,
                "price": 100.5,
                "fill_time": "2025-01-01T00:03:00Z",
                "time": "2025-01-01T00:03:00Z",
            },
            {
                "type": "close",
                "position_id": "p-short",
                "position_complete": True,
                "time": "2025-01-01T00:04:00Z",
            },
        ]
    )
    short_result = reconcile_policy_decisions(short_decision, short_events, [])
    assert short_result["status"] == "matched", short_result

    events.loc[1, "ask"] = 100.01
    events.loc[1, "price"] = 100.01
    above_limit = reconcile_policy_decisions(decision, events, [])
    assert "limit_fill_respects_price_bound" in {
        failure["check"] for failure in above_limit["failures"]
    }

    events.loc[1, "ask"] = 99.5
    events.loc[1, "price"] = 99.25
    inconsistent_quote_price = reconcile_policy_decisions(decision, events, [])
    assert "limit_fill_price_matches_executable_quote" in {
        failure["check"] for failure in inconsistent_quote_price["failures"]
    }

    events.loc[1, "price"] = 99.5
    events.loc[1, "time"] = "2025-01-01T00:06:00Z"
    after_expiry = reconcile_policy_decisions(decision, events, [])
    assert "limit_fill_occurs_inside_lifetime" in {
        failure["check"] for failure in after_expiry["failures"]
    }

    events = _events()
    events.loc[0, "order_type"] = "limit"
    events.loc[0, "limit_price"] = 100.0
    events.loc[0, "order_submission_time"] = "2025-01-01T00:02:00Z"
    events.loc[0, "expiry_time"] = "2025-01-01T00:05:00Z"
    events.loc[1, "order_type"] = "limit"
    events.loc[1, "price"] = 99.5
    events.loc[1, "time"] = "2025-01-01T00:03:00Z"
    missing_quote = reconcile_policy_decisions(decision, events, [])
    assert missing_quote["status"] == "incomplete"
    assert "limit_fill_quote_fields_missing" in missing_quote["incomplete_reasons"]


def test_policy_reconciliation_verifies_quote_for_margin_rejected_limit() -> None:
    decision = _decision()
    decision["execution_type"] = "limit"
    events = _events(include_open=False)
    events.loc[0, "order_type"] = "limit"
    events.loc[0, "limit_price"] = 100.0
    events.loc[0, "order_submission_time"] = "2025-01-01T00:02:00Z"
    events.loc[0, "expiry_time"] = "2025-01-01T00:05:00Z"
    events = pd.concat(
        [
            events,
            pd.DataFrame(
                [
                    {
                        "type": "order_cancel",
                        "order_id": "o1",
                        "decision_id": "d1",
                        "order_type": "limit",
                        "reason": "entry_rejected_at_limit_fill",
                        "trade_setup_candidate_id": 5,
                        "trade_setup_source_event_id": "source-event-5",
                        "trade_setup_source_event_identity_status": "identified",
                        "trigger_quote_time": "2025-01-01T00:03:00Z",
                        "trigger_quote_bid": 99.25,
                        "trigger_quote_ask": 99.5,
                        "trigger_quote_price": 99.5,
                        "time": "2025-01-01T00:03:00Z",
                    }
                ]
            ),
        ],
        ignore_index=True,
    )

    result = reconcile_policy_decisions(decision, events, [])

    assert result["status"] == "matched", result
    assert result["checks"]["rejected_limit_trigger_respects_price_and_lifetime"] == 1
    assert result["checks"]["rejected_limit_cancel_matches_trigger_time"] == 1

    events.loc[1, "trigger_quote_ask"] = 100.01
    events.loc[1, "trigger_quote_price"] = 100.01
    invalid_trigger = reconcile_policy_decisions(decision, events, [])
    assert "rejected_limit_trigger_respects_price_and_lifetime" in {
        failure["check"] for failure in invalid_trigger["failures"]
    }

    events.loc[1, "trigger_quote_ask"] = 99.5
    events.loc[1, "trigger_quote_price"] = 99.5
    events.loc[1, "time"] = "2025-01-01T00:04:00Z"
    inconsistent_cancel_time = reconcile_policy_decisions(decision, events, [])
    assert "rejected_limit_cancel_matches_trigger_time" in {
        failure["check"] for failure in inconsistent_cancel_time["failures"]
    }


def test_policy_reconciliation_rejects_open_from_ineligible_candidate() -> None:
    result = reconcile_policy_decisions(_decision(eligible=False), _events(), [])

    assert result["status"] == "mismatch"
    assert {failure["check"] for failure in result["failures"]} >= {
        "ineligible_setup_never_submits",
        "ineligible_setup_never_opens",
    }


def test_policy_reconciliation_checks_selected_candidate_against_exact_mask() -> None:
    decision = _decision()
    cast(Any, decision).at[0, "eligible_trade_setup_ids"] = [0, 6]

    result = reconcile_policy_decisions(decision, _events(), [])

    assert result["status"] == "mismatch"
    assert {
        "selected_candidate_mask_matches_eligibility_flag",
        "directional_action_selects_eligible_candidate",
    } <= {failure["check"] for failure in result["failures"]}


def test_policy_reconciliation_checks_mask_count_and_required_no_trade_id() -> None:
    decision = _decision()
    decision.at[0, "eligible_candidate_count"] = 3
    cast(Any, decision).at[0, "eligible_trade_setup_ids"] = [5]

    result = reconcile_policy_decisions(decision, _events(), [])

    assert result["status"] == "mismatch"
    assert {
        "decision_eligibility_mask_is_valid",
        "decision_eligibility_count_matches_mask",
    } <= {failure["check"] for failure in result["failures"]}


def test_policy_reconciliation_rejects_out_of_domain_selected_candidate_ids() -> None:
    for candidate_id in (-1, TRADE_SETUP_CATEGORY_COUNT):
        decision = _decision(eligible=False)
        decision.loc[0, "action"] = 0
        decision.loc[0, "trade_setup_candidate_id"] = candidate_id
        rejection = pd.DataFrame(
            [
                {
                    "type": "reject",
                    "decision_id": "d1",
                    "direction": 0,
                    "trade_setup_candidate_id": candidate_id,
                    "trade_setup_source_event_id": "source-event-5",
                    "trade_setup_source_event_identity_status": "identified",
                }
            ]
        )

        result = reconcile_policy_decisions(decision, rejection, [])

        assert result["status"] == "mismatch", result
        assert "selected_candidate_id_is_in_domain" in {
            failure["check"] for failure in result["failures"]
        }


def test_policy_reconciliation_marks_unknown_cash_events_incomplete() -> None:
    events = pd.concat(
        [
            _events(),
            pd.DataFrame([{"type": "financing_charge", "amount": 1.25}]),
        ],
        ignore_index=True,
    )

    result = reconcile_policy_decisions(_decision(), events, [])

    assert result["status"] == "incomplete", result
    assert "unsupported_trade_event_type_for_policy_replay" in result["incomplete_reasons"]


def test_policy_reconciliation_marks_submitted_but_unresolved_order_incomplete() -> None:
    result = reconcile_policy_decisions(_decision(), _events(include_open=False), [])

    assert result["status"] == "incomplete", {
        "failures": result["failures"],
        "incomplete_reasons": result["incomplete_reasons"],
    }
    assert "submitted_order_has_no_terminal_event" in result["incomplete_reasons"]
    assert result["failure_count"] == 0


def test_policy_reconciliation_does_not_resolve_order_with_unrelated_decision_reject() -> None:
    events = _events(include_open=False)
    events = pd.concat(
        [
            events,
            pd.DataFrame(
                [
                    {
                        "type": "reject",
                        "decision_id": "d1",
                        "order_id": "different-order",
                        "reason": "unrelated",
                    }
                ]
            ),
        ],
        ignore_index=True,
    )

    result = reconcile_policy_decisions(_decision(), events, [])

    assert result["status"] == "mismatch"
    assert "submitted_order_has_no_terminal_event" in result["incomplete_reasons"]


def test_policy_reconciliation_accepts_order_specific_rejection() -> None:
    events = pd.DataFrame(
        [
            {
                "type": "order_submit",
                "order_id": "o1",
                "decision_id": "d1",
                "trade_setup_candidate_id": 5,
                "direction": 1,
                "trade_setup_source_event_id": "source-event-5",
                "trade_setup_source_event_identity_status": "identified",
            },
            {
                "type": "reject",
                "order_id": "o1",
                "decision_id": "d1",
                "reason": "risk_capacity",
                "direction": 1,
                "trade_setup_candidate_id": 5,
                "trade_setup_source_event_id": "source-event-5",
                "trade_setup_source_event_identity_status": "identified",
            },
        ]
    )

    result = reconcile_policy_decisions(_decision(), events, [])

    assert result["status"] == "matched", result


def test_policy_reconciliation_rejects_wrong_candidate_rejection() -> None:
    events = _events(include_open=False)
    events = pd.concat(
        [
            events,
            pd.DataFrame(
                [
                    {
                        "type": "reject",
                        "order_id": "o1",
                        "decision_id": "d1",
                        "reason": "risk_capacity",
                        "direction": 1,
                        "trade_setup_candidate_id": 6,
                        "trade_setup_source_event_id": "source-event-5",
                        "trade_setup_source_event_identity_status": "identified",
                    }
                ]
            ),
        ],
        ignore_index=True,
    )

    result = reconcile_policy_decisions(_decision(), events, [])

    assert result["status"] == "mismatch"
    assert "rejected_candidate_matches_decision" in {
        failure["check"] for failure in result["failures"]
    }


def test_policy_reconciliation_rejects_wrong_source_event_rejection() -> None:
    events = pd.DataFrame(
        [
            {
                "type": "reject",
                "decision_id": "d1",
                "reason": "risk_capacity",
                "direction": 1,
                "trade_setup_candidate_id": 5,
                "trade_setup_source_event_id": "other-source-event",
                "trade_setup_source_event_identity_status": "identified",
            }
        ]
    )

    result = reconcile_policy_decisions(_decision(), events, [])

    assert result["status"] == "mismatch"
    assert "rejected_source_event_matches_decision" in {
        failure["check"] for failure in result["failures"]
    }


def test_policy_reconciliation_rejects_wrong_direction_rejection() -> None:
    events = pd.DataFrame(
        [
            {
                "type": "reject",
                "decision_id": "d1",
                "reason": "risk_capacity",
                "direction": -1,
                "trade_setup_candidate_id": 5,
                "trade_setup_source_event_id": "source-event-5",
                "trade_setup_source_event_identity_status": "identified",
            }
        ]
    )

    result = reconcile_policy_decisions(_decision(), events, [])

    assert result["status"] == "mismatch"
    assert "rejection_direction_matches_decision" in {
        failure["check"] for failure in result["failures"]
    }


def test_policy_reconciliation_rejects_order_rejection_with_wrong_decision_id() -> None:
    events = pd.DataFrame(
        [
            {
                "type": "order_submit",
                "order_id": "o1",
                "decision_id": "d1",
                "trade_setup_candidate_id": 5,
                "direction": 1,
                "trade_setup_source_event_id": "source-event-5",
                "trade_setup_source_event_identity_status": "identified",
            },
            {
                "type": "reject",
                "order_id": "o1",
                "decision_id": "other-decision",
                "reason": "risk_capacity",
            },
        ]
    )

    result = reconcile_policy_decisions(_decision(), events, [])

    assert result["status"] == "mismatch"
    assert "order_lifecycle_keeps_decision_id" in {
        failure["check"] for failure in result["failures"]
    }


def test_policy_reconciliation_rejects_position_open_after_daily_failure() -> None:
    decisions = _decision()
    events = pd.DataFrame(
        [
            {
                "type": "order_submit",
                "order_id": "o1",
                "decision_id": "d1",
                "trade_setup_candidate_id": 5,
                "direction": 1,
                "trade_setup_source_event_id": "source-event-5",
                "trade_setup_source_event_identity_status": "identified",
            },
            {
                "type": "open",
                "order_id": "o1",
                "position_id": "p1",
                "decision_id": "d1",
                "trade_setup_candidate_id": 5,
                "direction": 1,
                "trade_setup_source_event_id": "source-event-5",
                "trade_setup_source_event_identity_status": "identified",
                "time": "2025-01-06T16:00:00Z",
                "fill_time": "2025-01-06T16:00:00Z",
            },
        ]
    )
    breaches = [
        {
            "schema_version": "risk-breach-event-v1",
            "reason": "daily_loss",
            "time": "2025-01-06T15:00:00Z",
            "detection_time": "2025-01-06T15:00:00Z",
            "trade_event_count": 0,
            "session_id": 1,
        }
    ]

    result = reconcile_policy_decisions(decisions, events, breaches)

    assert result["status"] == "mismatch"
    assert "no_position_open_after_rollout_breach" in {
        failure["check"] for failure in result["failures"]
    }


def test_policy_reconciliation_allows_same_bar_tick_fill_that_causes_breach() -> None:
    decisions = _decision()
    decision_time = "2025-01-06T15:00:00Z"
    fill_time = "2025-01-06T15:00:00.218Z"
    decisions.loc[:, "decision_time"] = decision_time
    events = _events()
    events.loc[events["type"].eq("order_submit"), "order_submission_time"] = decision_time
    events.loc[events["type"].eq("order_fill"), "time"] = fill_time
    events.loc[events["type"].eq("order_fill"), "fill_time"] = None
    events.loc[events["type"].eq("open"), "decision_time"] = decision_time
    events.loc[events["type"].eq("open"), "time"] = fill_time
    events.loc[events["type"].eq("open"), "fill_time"] = fill_time
    breaches = [
        {
            "schema_version": "risk-breach-event-v1",
            "reason": "max_drawdown",
            "time": "2025-01-06T15:00:00Z",
            "detection_time": fill_time,
            "trade_event_count": 3,
            "session_id": 1,
        }
    ]

    result = reconcile_policy_decisions(decisions, events, breaches)

    assert result["status"] == "matched", {
        "failures": result["failures"],
        "incomplete_reasons": result["incomplete_reasons"],
        "checks": result["checks"],
    }


def test_policy_reconciliation_rejects_order_submission_after_daily_failure() -> None:
    decisions = _decision()
    events = pd.DataFrame(
        [
            {
                "type": "order_submit",
                "order_id": "o1",
                "decision_id": "d1",
                "trade_setup_candidate_id": 5,
                "direction": 1,
                "trade_setup_source_event_id": "source-event-5",
                "trade_setup_source_event_identity_status": "identified",
                "time": "2025-01-06T16:00:00Z",
                "order_submission_time": "2025-01-06T16:00:00Z",
            },
            {
                "type": "order_cancel",
                "order_id": "o1",
                "decision_id": "d1",
                "time": "2025-01-06T16:01:00Z",
            },
        ]
    )
    breaches = [
        {
            "schema_version": "risk-breach-event-v1",
            "reason": "daily_loss",
            "time": "2025-01-06T15:00:00Z",
            "detection_time": "2025-01-06T15:00:00Z",
            "trade_event_count": 0,
            "session_id": 1,
        }
    ]

    result = reconcile_policy_decisions(decisions, events, breaches)

    assert result["status"] == "mismatch"
    assert "no_order_submission_after_rollout_breach" in {
        failure["check"] for failure in result["failures"]
    }


def test_policy_reconciliation_rejects_pending_order_fill_after_daily_failure() -> None:
    events = pd.DataFrame(
        [
            {
                "type": "order_submit",
                "order_id": "o1",
                "decision_id": "d1",
                "trade_setup_candidate_id": 5,
                "direction": 1,
                "trade_setup_source_event_id": "source-event-5",
                "trade_setup_source_event_identity_status": "identified",
                "time": "2025-01-06T14:00:00Z",
                "order_submission_time": "2025-01-06T14:00:00Z",
            },
            {
                "type": "order_fill",
                "order_id": "o1",
                "decision_id": "d1",
                "trade_setup_candidate_id": 5,
                "direction": 1,
                "trade_setup_source_event_id": "source-event-5",
                "trade_setup_source_event_identity_status": "identified",
                "time": "2025-01-06T15:00:00.400Z",
                "fill_time": "2025-01-06T15:00:00.400Z",
            },
        ]
    )
    events.loc[events["type"].eq("order_submit"), "order_submission_time"] = "2025-01-06T14:00:00Z"
    breaches = [
        {
            "schema_version": "risk-breach-event-v1",
            "reason": "daily_loss",
            "time": "2025-01-06T15:00:00Z",
            "detection_time": "2025-01-06T15:00:00.218Z",
            "trade_event_count": 1,
            "session_id": 1,
        }
    ]

    result = reconcile_policy_decisions(_decision(), events, breaches)

    assert result["status"] == "mismatch"
    assert "no_order_fill_after_rollout_breach" in {
        failure["check"] for failure in result["failures"]
    }


def test_policy_reconciliation_fails_closed_on_malformed_breach_record() -> None:
    result = reconcile_policy_decisions(_decision(), _events(), [None])

    assert result["status"] == "incomplete"
    assert "invalid_rollout_breach_record" in result["incomplete_reasons"]


def test_policy_reconciliation_requires_exact_breach_detection_metadata() -> None:
    result = reconcile_policy_decisions(
        _decision(),
        _events(),
        [
            {
                "schema_version": "risk-breach-event-v1",
                "reason": "daily_loss",
                "time": "2025-01-01T00:03:00Z",
            }
        ],
    )

    assert result["status"] == "incomplete"
    assert "rollout_breach_detection_time_missing" in result["incomplete_reasons"]
    assert "rollout_breach_event_prefix_missing_or_invalid" in result["incomplete_reasons"]


def test_policy_reconciliation_rejects_submitted_direction_mismatch() -> None:
    events = _events(include_open=False)
    events.loc[0, "direction"] = -1
    events = pd.concat(
        [
            events,
            pd.DataFrame(
                [
                    {
                        "type": "order_cancel",
                        "order_id": "o1",
                        "decision_id": "d1",
                    }
                ]
            ),
        ],
        ignore_index=True,
    )

    result = reconcile_policy_decisions(_decision(), events, [])

    assert result["status"] == "mismatch"
    assert "submitted_order_direction_matches_decision" in {
        failure["check"] for failure in result["failures"]
    }


def test_policy_reconciliation_fails_closed_on_malformed_open_direction() -> None:
    events = _events()
    events.loc[events["type"].eq("open"), "direction"] = "invalid"

    result = reconcile_policy_decisions(_decision(), events, [])

    assert result["status"] == "mismatch"
    assert "open_direction_matches_decision" in {failure["check"] for failure in result["failures"]}


def test_policy_reconciliation_rejects_changed_source_event_on_submission() -> None:
    events = _events(include_open=False)
    events.loc[0, "trade_setup_source_event_id"] = "replacement-source-event"
    events = pd.concat(
        [
            events,
            pd.DataFrame(
                [
                    {
                        "type": "order_cancel",
                        "order_id": "o1",
                        "decision_id": "d1",
                    }
                ]
            ),
        ],
        ignore_index=True,
    )

    result = reconcile_policy_decisions(_decision(), events, [])

    assert result["status"] == "mismatch"
    assert "submitted_source_event_matches_decision" in {
        failure["check"] for failure in result["failures"]
    }


def test_policy_reconciliation_rejects_changed_source_event_at_fill() -> None:
    events = _events()
    fill_index = events.index[events["type"].eq("order_fill")][0]
    events.loc[fill_index, "trade_setup_source_event_id"] = "replacement-source-event"

    result = reconcile_policy_decisions(_decision(), events, [])

    assert result["status"] == "mismatch"
    assert "filled_event_source_matches_submission" in {
        failure["check"] for failure in result["failures"]
    }


def test_policy_reconciliation_rejects_cancel_with_changed_setup_identity() -> None:
    events = _events(include_open=False)
    events = pd.concat(
        [
            events,
            pd.DataFrame(
                [
                    {
                        "type": "order_cancel",
                        "order_id": "o1",
                        "decision_id": "d1",
                        "trade_setup_candidate_id": 5,
                        "trade_setup_source_event_id": "replacement-source-event",
                        "trade_setup_source_event_identity_status": "identified",
                    }
                ]
            ),
        ],
        ignore_index=True,
    )

    result = reconcile_policy_decisions(_decision(), events, [])

    assert result["status"] == "mismatch"
    assert "cancelled_event_source_matches_submission" in {
        failure["check"] for failure in result["failures"]
    }


def test_policy_reconciliation_rejects_submission_from_no_trade_decision() -> None:
    decision = _decision()
    decision.loc[0, "action"] = 0

    result = reconcile_policy_decisions(decision, _events(), [])

    assert result["status"] == "mismatch"
    assert "submitted_order_decision_is_entry_action" in {
        failure["check"] for failure in result["failures"]
    }
    assert "no_trade_decision_never_submits" in {failure["check"] for failure in result["failures"]}


def test_policy_reconciliation_rejects_out_of_contract_decision_action() -> None:
    decisions = _decision()
    decisions.loc[0, "action"] = 2

    result = reconcile_policy_decisions(decisions, pd.DataFrame(), [])

    assert result["status"] == "mismatch"
    assert "decision_action_is_valid" in {failure["check"] for failure in result["failures"]}


def test_policy_reconciliation_fails_closed_on_malformed_action_cell() -> None:
    decisions = _decision()
    decisions["action"] = decisions["action"].astype(object)
    cast(Any, decisions).at[0, "action"] = [1, 0]

    result = reconcile_policy_decisions(decisions, pd.DataFrame(), [])

    assert result["status"] == "mismatch"
    assert "decision_action_is_valid" in {failure["check"] for failure in result["failures"]}


def test_policy_reconciliation_marks_malformed_candidate_cell_incomplete() -> None:
    decisions = _decision()
    decisions["trade_setup_candidate_id"] = decisions["trade_setup_candidate_id"].astype(object)
    cast(Any, decisions).at[0, "trade_setup_candidate_id"] = [5, 6]

    result = reconcile_policy_decisions(decisions, pd.DataFrame(), [])

    assert "selected_candidate_id_is_invalid" in result["incomplete_reasons"]


def test_policy_reconciliation_marks_missing_selected_eligibility_incomplete() -> None:
    decisions = _decision().drop(columns="trade_setup_eligible")

    result = reconcile_policy_decisions(decisions, pd.DataFrame(), [])

    assert result["status"] == "incomplete"
    assert "selected_candidate_eligibility_missing" in result["incomplete_reasons"]


def test_policy_reconciliation_marks_missing_source_identity_incomplete() -> None:
    decisions = _decision().drop(
        columns=[
            "trade_setup_source_event_id",
            "trade_setup_source_event_identity_status",
        ]
    )

    result = reconcile_policy_decisions(decisions, pd.DataFrame(), [])

    assert result["status"] == "incomplete"
    assert "eligible_setup_source_identity_missing" in result["incomplete_reasons"]


def test_policy_reconciliation_accepts_same_direction_position_hold() -> None:
    decision = _decision()
    decision.loc[0, "position_direction_at_decision"] = 1
    decision.loc[0, "position_id_at_decision"] = "p-existing"
    prior_decision = _decision().iloc[0:1].copy()
    prior_decision.loc[:, "decision_id"] = "d0"
    prior_decision.loc[:, "action"] = 1
    prior_decision.loc[:, "trade_setup_candidate_id"] = None
    prior_decision.loc[:, "trade_setup_eligible"] = None
    prior_decision.loc[:, "trade_setup_source_event_id"] = None
    prior_decision.loc[:, "trade_setup_source_event_identity_status"] = None
    decisions = pd.concat([prior_decision, decision], ignore_index=True)
    events = pd.DataFrame(
        [
            {"type": "order_submit", "decision_id": "d0", "order_id": "o0", "direction": 1},
            {
                "type": "order_fill",
                "decision_id": "d0",
                "order_id": "o0",
                "direction": 1,
            },
            {
                "type": "open",
                "decision_id": "d0",
                "order_id": "o0",
                "position_id": "p-existing",
                "direction": 1,
                "time": "2025-01-01T00:01:00Z",
            },
            {
                "type": "close",
                "position_id": "p-existing",
                "position_complete": True,
                "time": "2025-01-01T00:04:00Z",
            },
        ]
    )

    result = reconcile_policy_decisions(decisions, events, [])

    assert result["failure_count"] == 0, result["failures"]
    assert result["checks"]["entry_action_has_order_rejection_or_hold"] == 1
    assert result["status"] == "matched"
    assert "entry_action_has_order_rejection_or_hold" not in {
        failure["check"] for failure in result["failures"]
    }

    events.loc[events["type"] == "close", "time"] = "2025-01-01T00:01:30Z"
    stale_position = reconcile_policy_decisions(decisions, events, [])

    assert stale_position["status"] == "mismatch"
    assert "decision_position_is_live_at_decision" in {
        failure["check"] for failure in stale_position["failures"]
    }


def test_environment_v2_same_direction_hold_has_complete_outcome_context() -> None:
    prior_decision = _environment_decision()
    prior_decision.loc[0, "decision_id"] = "env:d0"
    prior_decision.loc[0, "decision_time"] = "2025-01-01T00:00:00Z"
    decision = _environment_decision()
    decision.loc[0, "decision_time"] = "2025-01-01T00:02:00Z"
    decision.loc[0, "position_direction_at_decision"] = 1
    decision.loc[0, "position_id_at_decision"] = "p-existing"
    decision.loc[0, "trade_event_start_index"] = 3
    decisions = pd.concat([prior_decision, decision], ignore_index=True)
    events = pd.DataFrame(
        [
            {
                "type": "order_submit",
                "order_id": "o-existing",
                "decision_id": "env:d0",
                "direction": 1,
                "trade_setup_candidate_id": 5,
                "trade_setup_source_event_id": "source-event-5",
                "trade_setup_source_event_identity_status": "identified",
            },
            {
                "type": "order_fill",
                "order_id": "o-existing",
                "decision_id": "env:d0",
                "direction": 1,
                "time": "2025-01-01T00:01:00Z",
                "trade_setup_candidate_id": 5,
                "trade_setup_source_event_id": "source-event-5",
                "trade_setup_source_event_identity_status": "identified",
            },
            {
                "type": "open",
                "order_id": "o-existing",
                "position_id": "p-existing",
                "decision_id": "env:d0",
                "direction": 1,
                "time": "2025-01-01T00:01:00Z",
                "fill_time": "2025-01-01T00:01:00Z",
                "trade_setup_candidate_id": 5,
                "trade_setup_source_event_id": "source-event-5",
                "trade_setup_source_event_identity_status": "identified",
            },
            {
                "type": "close",
                "position_id": "p-existing",
                "position_complete": True,
                "time": "2025-01-01T00:04:00Z",
            },
        ]
    )

    result = reconcile_policy_decisions(decisions, events, [])

    assert result["status"] == "matched", {
        "failures": result["failures"],
        "incomplete_reasons": result["incomplete_reasons"],
    }
    assert result["checks"]["entry_action_has_order_rejection_or_hold"] == 1


def test_environment_decision_phase_accepts_same_bar_tick_fill() -> None:
    prior = _environment_decision()
    prior.loc[0, "decision_id"] = "env:d0"
    prior.loc[0, "trade_event_start_index"] = 0
    prior.loc[0, "trade_event_end_index_exclusive"] = 1
    hold = _environment_decision(action=0)
    hold.loc[0, "position_direction_at_decision"] = 1
    hold.loc[0, "position_id_at_decision"] = "env:p1"
    hold.loc[0, "trade_event_start_index"] = 2
    hold.loc[0, "trade_event_end_index_exclusive"] = 2
    decisions = pd.concat([prior, hold], ignore_index=True)
    events = pd.DataFrame(
        [
            {
                "type": "open",
                "position_id": "env:p1",
                "decision_id": "env:d0",
                "direction": 1,
                "time": "2025-01-01T00:02:00.100Z",
                "fill_time": "2025-01-01T00:02:00.100Z",
                "trade_setup_candidate_id": 5,
                "trade_setup_source_event_id": "source-event-5",
                "trade_setup_source_event_identity_status": "identified",
            },
            {
                "type": "tp_partial_close",
                "position_id": "env:p1",
                "position_complete": False,
                "time": "2025-01-01T00:02:30Z",
            },
            {
                "type": "close",
                "position_id": "env:p1",
                "position_complete": True,
                "time": "2025-01-01T00:04:00Z",
            },
        ]
    )

    result = reconcile_policy_decisions(decisions, events, [])

    assert result["status"] == "matched", result

    decisions.loc[1, "trade_event_start_index"] = 3
    closed_before_decision = reconcile_policy_decisions(decisions, events, [])
    assert closed_before_decision["status"] == "mismatch"
    assert "decision_position_is_live_at_decision" in {
        failure["check"] for failure in closed_before_decision["failures"]
    }


def test_policy_reconciliation_rejects_flat_entry_without_order_or_rejection() -> None:
    result = reconcile_policy_decisions(_decision(), pd.DataFrame(), [])

    assert result["status"] == "mismatch"
    assert "entry_action_has_order_rejection_or_hold" in {
        failure["check"] for failure in result["failures"]
    }


def test_policy_reconciliation_checks_entry_action_without_selected_candidate() -> None:
    decision = _decision().drop(
        columns=[
            "trade_setup_candidate_id",
            "trade_setup_eligible",
            "trade_setup_source_event_id",
            "trade_setup_source_event_identity_status",
        ]
    )

    result = reconcile_policy_decisions(decision, pd.DataFrame(), [])

    assert result["status"] == "mismatch"
    assert "entry_action_has_order_rejection_or_hold" in {
        failure["check"] for failure in result["failures"]
    }

    wrong_direction = reconcile_policy_decisions(
        decision,
        pd.DataFrame([{"type": "reject", "decision_id": "d1", "direction": -1}]),
        [],
    )

    assert "rejection_direction_matches_decision" in {
        failure["check"] for failure in wrong_direction["failures"]
    }


def test_policy_reconciliation_accepts_matching_pending_order_hold() -> None:
    decision = _decision()
    decision.loc[0, "pending_order_id_at_decision"] = "o-existing"
    prior_decision = _decision().iloc[0:1].copy()
    prior_decision.loc[:, "decision_id"] = "d0"
    prior_decision.loc[:, "action"] = 1
    prior_decision.loc[:, "trade_setup_candidate_id"] = None
    prior_decision.loc[:, "trade_setup_eligible"] = None
    prior_decision.loc[:, "trade_setup_source_event_id"] = None
    prior_decision.loc[:, "trade_setup_source_event_identity_status"] = None
    decisions = pd.concat([prior_decision, decision], ignore_index=True)
    events = pd.DataFrame(
        [
            {
                "type": "order_submit",
                "order_id": "o-existing",
                "decision_id": "d0",
                "order_submission_time": "2025-01-01T00:00:00Z",
                "direction": 1,
            },
            {
                "type": "order_cancel",
                "order_id": "o-existing",
                "decision_id": "d0",
                "time": "2025-01-01T00:03:00Z",
            },
        ]
    )

    result = reconcile_policy_decisions(decisions, events, [])

    assert result["failure_count"] == 0
    assert result["checks"]["entry_action_has_order_rejection_or_hold"] == 1
    assert "entry_action_has_order_rejection_or_hold" not in {
        failure["check"] for failure in result["failures"]
    }


def test_policy_reconciliation_rejects_pending_order_with_different_direction() -> None:
    decision = _decision()
    decision.loc[0, "pending_order_id_at_decision"] = "o-existing"
    prior_decision = _decision().iloc[0:1].copy()
    prior_decision.loc[:, "decision_id"] = "d0"
    prior_decision.loc[:, "action"] = 1
    prior_decision.loc[:, "trade_setup_candidate_id"] = None
    prior_decision.loc[:, "trade_setup_eligible"] = None
    prior_decision.loc[:, "trade_setup_source_event_id"] = None
    prior_decision.loc[:, "trade_setup_source_event_identity_status"] = None
    decisions = pd.concat([prior_decision, decision], ignore_index=True)
    events = pd.DataFrame(
        [
            {
                "type": "order_submit",
                "order_id": "o-existing",
                "decision_id": "d0",
                "order_submission_time": "2025-01-01T00:00:00Z",
                "direction": -1,
            }
        ]
    )

    result = reconcile_policy_decisions(decisions, events, [])

    assert result["status"] == "mismatch"
    assert "entry_action_has_order_rejection_or_hold" in {
        failure["check"] for failure in result["failures"]
    }


def test_policy_reconciliation_rejects_pending_order_cancelled_before_decision() -> None:
    decision = _decision()
    decision.loc[0, "pending_order_id_at_decision"] = "o-existing"
    prior_decision = _decision().iloc[0:1].copy()
    prior_decision.loc[:, "decision_id"] = "d0"
    prior_decision.loc[:, "action"] = 1
    prior_decision.loc[:, "trade_setup_candidate_id"] = None
    prior_decision.loc[:, "trade_setup_eligible"] = None
    prior_decision.loc[:, "trade_setup_source_event_id"] = None
    prior_decision.loc[:, "trade_setup_source_event_identity_status"] = None
    decisions = pd.concat([prior_decision, decision], ignore_index=True)
    events = pd.DataFrame(
        [
            {
                "type": "order_submit",
                "order_id": "o-existing",
                "decision_id": "d0",
                "order_submission_time": "2025-01-01T00:00:00Z",
                "direction": 1,
            },
            {
                "type": "order_cancel",
                "order_id": "o-existing",
                "decision_id": "d0",
                "time": "2025-01-01T00:01:00Z",
            },
        ]
    )

    result = reconcile_policy_decisions(decisions, events, [])

    assert result["status"] == "mismatch"
    assert "decision_pending_order_is_live_at_decision" in {
        failure["check"] for failure in result["failures"]
    }


def test_policy_reconciliation_fails_closed_on_malformed_pending_order_id() -> None:
    decision = _decision()
    cast(Any, decision).at[0, "pending_order_id_at_decision"] = ["o-invalid"]

    result = reconcile_policy_decisions(decision, pd.DataFrame(), [])

    assert result["status"] == "mismatch"
    assert "decision_pending_order_context_resolves" in {
        failure["check"] for failure in result["failures"]
    }


def test_policy_reconciliation_accepts_complete_no_action_run_with_empty_ledger() -> None:
    decisions = pd.DataFrame(
        [
            {
                "schema_version": "event_backtest_policy_decision.v1",
                "decision_id": "d1",
                "action": 0,
            }
        ]
    )

    result = reconcile_policy_decisions(decisions, pd.DataFrame(), [])

    assert result["status"] == "matched"


def test_policy_reconciliation_marks_v1_entry_without_outcome_context_incomplete() -> None:
    decision = _decision()
    decision.loc[0, "schema_version"] = "event_backtest_policy_decision.v1"
    decision = decision.drop(
        columns=[
            "position_direction_at_decision",
            "position_id_at_decision",
            "pending_order_id_at_decision",
        ]
    )

    result = reconcile_policy_decisions(decision, pd.DataFrame(), [])

    assert result["status"] == "incomplete"
    assert "entry_action_outcome_context_missing_for_v1_decision" in result["incomplete_reasons"]


def test_policy_reconciliation_marks_v1_rejection_identity_gap_incomplete() -> None:
    decision = _decision()
    decision.loc[0, "schema_version"] = "event_backtest_policy_decision.v1"
    decision = decision.drop(
        columns=[
            "decision_time",
            "position_direction_at_decision",
            "position_id_at_decision",
            "pending_order_id_at_decision",
        ]
    )
    events = _events(include_open=False)
    events = pd.concat(
        [
            events,
            pd.DataFrame(
                [
                    {
                        "type": "reject",
                        "order_id": "o1",
                        "decision_id": "d1",
                        "reason": "risk_capacity",
                    }
                ]
            ),
        ],
        ignore_index=True,
    )

    result = reconcile_policy_decisions(decision, events, [])

    assert result["status"] == "incomplete", {
        "failures": result["failures"],
        "incomplete_reasons": result["incomplete_reasons"],
    }
    assert "rejection_candidate_identity_missing_for_v1_decision" in result["incomplete_reasons"]
    assert "rejection_source_identity_missing_for_v1_decision" in result["incomplete_reasons"]


def test_policy_reconciliation_checks_selected_limit_order_contract() -> None:
    decision = _decision()
    decision.loc[0, "decision_time"] = "2025-01-06T14:59:00Z"
    decision["execution_type"] = "limit"
    events = _events()
    events.loc[0, "order_type"] = "limit"
    events.loc[0, "limit_price"] = 100.0
    events.loc[0, "order_submission_time"] = "2025-01-06T15:00:00Z"
    events.loc[0, "expiry_time"] = "2025-01-06T16:00:00Z"
    events.loc[1, "bid"] = 99.0
    events.loc[1, "ask"] = 99.5
    events.loc[1, "fill_time"] = "2025-01-06T15:30:00Z"
    events.loc[1, "time"] = "2025-01-06T15:30:00Z"
    events.loc[2, "fill_time"] = "2025-01-06T15:30:00Z"
    events.loc[2, "time"] = "2025-01-06T15:30:00Z"
    events.loc[3, "time"] = "2025-01-06T15:45:00Z"

    result = reconcile_policy_decisions(decision, events, [])

    assert result["status"] == "matched", {
        "failures": result["failures"],
        "incomplete_reasons": result["incomplete_reasons"],
    }
    assert result["checks"]["submitted_order_type_matches_decision"] == 1
    assert result["checks"]["limit_order_has_finite_positive_price"] == 1
    assert result["checks"]["limit_order_has_positive_lifetime"] == 1


def test_policy_reconciliation_rejects_fill_after_source_expiry_cancellation() -> None:
    decision = _decision()
    decision["execution_type"] = "limit"
    events = _events()
    events.loc[0, "order_type"] = "limit"
    events.loc[0, "limit_price"] = 100.0
    events.loc[0, "order_submission_time"] = "2025-01-01T00:02:00Z"
    events.loc[0, "expiry_time"] = "2025-01-01T00:05:00Z"
    cancellation = pd.DataFrame(
        [
            {
                "type": "order_cancel",
                "order_id": "o1",
                "decision_id": "d1",
                "order_type": "limit",
                "reason": "source_setup_invalidated",
                "time": "2025-01-01T00:02:30Z",
                "trade_setup_candidate_id": 5,
                "trade_setup_source_event_id": "source-event-5",
                "trade_setup_source_event_identity_status": "identified",
            }
        ]
    )
    events = pd.concat([events.iloc[:1], cancellation, events.iloc[1:]], ignore_index=True)

    result = reconcile_policy_decisions(decision, events, [])

    assert result["status"] == "mismatch"
    assert "cancelled_order_has_no_fill_or_open" in {
        failure["check"] for failure in result["failures"]
    }


def test_policy_reconciliation_rejects_limit_decision_submitted_as_market() -> None:
    decision = _decision()
    decision["execution_type"] = "limit"
    events = _events()
    events.loc[0, "order_type"] = "market"

    result = reconcile_policy_decisions(decision, events, [])

    assert result["status"] == "mismatch"
    assert "submitted_order_type_matches_decision" in {
        failure["check"] for failure in result["failures"]
    }
