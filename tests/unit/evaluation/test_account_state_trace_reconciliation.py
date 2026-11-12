from __future__ import annotations

from typing import Any, cast

import pandas as pd
import pytest

from evaluation.reporting.account_state_trace_reconciliation import (
    reconcile_account_state_trace,
)
from trading.execution import (
    FILL_COST_PROVENANCE_SCHEMA_VERSION,
    TRADE_CASHFLOW_SCHEMA_VERSION,
)


def _open_event(
    *,
    position_id: str = "position-1",
    direction: int = 1,
    price: float = 100.0,
    lots: float = 1.0,
    contract_size: float = 1.0,
    commission_per_lot: float = 4.0,
) -> dict[str, object]:
    return {
        "type": "open",
        "position_id": position_id,
        "cashflow_schema_version": TRADE_CASHFLOW_SCHEMA_VERSION,
        "direction": direction,
        "price": price,
        "lots": lots,
        "contract_size": contract_size,
        "commission_per_lot": commission_per_lot,
        "entry_commission": lots * commission_per_lot,
    }


def _close_event(
    *,
    position_id: str = "position-1",
    direction: int = 1,
    entry_price: float = 100.0,
    exit_price: float,
    size: float = 1.0,
    contract_size: float = 1.0,
    commission_per_lot: float = 4.0,
    position_complete: bool = True,
) -> dict[str, object]:
    gross_pnl = (exit_price - entry_price) * direction * size * contract_size
    exit_commission = commission_per_lot * size
    entry_commission_allocated = commission_per_lot * size
    net_pnl = gross_pnl - exit_commission - entry_commission_allocated
    return {
        "type": "close",
        "position_id": position_id,
        "cashflow_schema_version": TRADE_CASHFLOW_SCHEMA_VERSION,
        "direction": direction,
        "entry_price": entry_price,
        "price": exit_price,
        "size": size,
        "contract_size": contract_size,
        "commission_per_lot": commission_per_lot,
        "gross_price_pnl": gross_pnl,
        "exit_commission": exit_commission,
        "entry_commission_allocated": entry_commission_allocated,
        "pnl": gross_pnl - exit_commission,
        "net_pnl": net_pnl,
        "position_complete": position_complete,
        "position_net_pnl": net_pnl if position_complete else None,
    }


def _trace_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "schema_version": "account_state_trace.v2",
        "valuation_time": "2025-01-06T15:00:00Z",
        "decision_time": "2025-01-06T15:00:00Z",
        "state_phase": "post_action_valuation",
        "session_id": 1,
        "initial_balance": 100_000.0,
        "balance": 100_003.0,
        "equity": 100_003.0,
        "open_pnl": 0.0,
        "session_start_balance": 100_000.0,
        "session_start_equity": 100_000.0,
        "daily_pnl_basis": "legacy_gross_closed_losses",
        "daily_loss": 0.0,
        "daily_loss_limit_usd": 5_000.0,
        "daily_floor_equity": 95_000.0,
        "max_loss_limit_usd": 10_000.0,
        "max_loss_floor_equity": 90_000.0,
        "max_drawdown_mode": "static",
        "max_drawdown_from_reference_usd": 0.0,
        "loss_from_initial_usd": 0.0,
        "max_drawdown_usd": 0.0,
        "peak_equity": 100_003.0,
        "peak_eod_equity": 100_000.0,
        "peak_eod_drawdown_usd": 0.0,
        "max_peak_eod_drawdown_usd": 0.0,
        "payout_drawdown_floor": None,
        "trailing_drawdown_usd": 0.0,
        "position_direction": 0,
        "position_size": 0.0,
        "position_entry_price": None,
        "position_mark_price": None,
        "contract_size": 1.0,
        "trade_event_count": 2,
        "cumulative_payouts": 0.0,
        "total_economic_value": 100_003.0,
    }
    row.update(overrides)
    return row


def test_account_trace_reconstructs_cashflows_daily_loss_and_open_mark() -> None:
    trace = pd.DataFrame(
        [
            _trace_row(
                balance=99_996.0,
                equity=99_997.0,
                total_economic_value=99_997.0,
                open_pnl=1.0,
                loss_from_initial_usd=3.0,
                max_drawdown_usd=3.0,
                position_direction=1,
                position_size=1.0,
                position_entry_price=100.0,
                position_mark_price=101.0,
                daily_pnl_basis="session_net_equity",
                daily_loss=3.0,
                max_drawdown_from_reference_usd=3.0,
                peak_equity=100_000.0,
                peak_eod_drawdown_usd=3.0,
                max_peak_eod_drawdown_usd=3.0,
                trailing_drawdown_usd=3.0,
                trade_event_count=1,
            ),
            _trace_row(
                balance=100_003.0,
                daily_loss=0.0,
                max_drawdown_usd=3.0,
                max_peak_eod_drawdown_usd=3.0,
                trade_event_count=2,
            ),
        ]
    )
    events = pd.DataFrame(
        [
            _open_event(),
            _close_event(exit_price=111.0),
        ]
    )

    result = reconcile_account_state_trace(trace, events, breach_events=[])

    assert result["status"] == "matched", result["failures"]
    assert result["failure_count"] == 0
    assert result["checks"]["event_cashflows_reconstruct_balance"] == 2
    assert result["checks"]["position_mark_reconstructs_open_pnl"] == 1
    assert result["checks"]["session_net_daily_loss_matches_equity"] == 1
    assert result["checks"]["daily_risk_anchor_matches_session_or_payout_reset"] == 2


def test_account_trace_rejects_boolean_daily_loss_amount() -> None:
    trace = pd.DataFrame(
        [
            _trace_row(
                balance=100_000.0,
                equity=100_000.0,
                total_economic_value=100_000.0,
                peak_equity=100_000.0,
                daily_loss=False,
                trade_event_count=0,
            )
        ]
    )

    result = reconcile_account_state_trace(trace, pd.DataFrame(), breach_events=[])

    assert result["status"] == "incomplete"
    assert "daily_loss_is_not_finite" in result["incomplete_reasons"]


def test_account_trace_independently_recomputes_trade_fill_cashflows() -> None:
    trace = pd.DataFrame([_trace_row()])
    close_event = _close_event(exit_price=111.0)
    close_event["gross_price_pnl"] = 12.0
    events = pd.DataFrame([_open_event(), close_event])

    result = reconcile_account_state_trace(trace, events, breach_events=[])

    assert result["status"] == "mismatch"
    assert "gross_close_pnl_matches_executable_fills" in {
        failure["check"] for failure in result["failures"]
    }
    assert "trade_fill_cashflow_replay_missing_fields" not in result["incomplete_reasons"]


def test_account_trace_checks_fill_quote_slippage_provenance() -> None:
    trace = pd.DataFrame([_trace_row()])
    open_event = _open_event(price=101.25)
    close_event = _close_event(entry_price=101.25, exit_price=112.25)
    for event, pre_quote, broker_quote, slip in (
        (open_event, (99.0, 101.0), (99.0, 101.25), 0.25),
        (close_event, (112.5, 114.5), (112.25, 114.25), 0.25),
    ):
        event.update(
            {
                "fill_cost_provenance_schema_version": FILL_COST_PROVENANCE_SCHEMA_VERSION,
                "pre_execution_quote_bid": pre_quote[0],
                "pre_execution_quote_ask": pre_quote[1],
                "broker_execution_quote_bid": broker_quote[0],
                "broker_execution_quote_ask": broker_quote[1],
                "slippage_points_applied_here": slip,
                "slippage_applied_here": True,
                "slippage_application_mode": (
                    "transacted_side" if event is open_event else "quote_level_shift"
                ),
            }
        )
    matched = reconcile_account_state_trace(
        trace, pd.DataFrame([open_event, close_event]), breach_events=[]
    )
    assert matched["fill_cost_provenance"]["status"] == "matched"
    assert matched["fill_cost_provenance"]["verified_rows"] == 2
    assert matched["checks"]["broker_quote_bid_matches_slippage_application"] == 2
    assert matched["checks"]["broker_quote_ask_matches_slippage_application"] == 2
    assert matched["checks"]["fill_price_matches_broker_quote_side"] == 2

    # Keep the modified quote internally valid (ask >= bid), so reconciliation
    # reports a provenance mismatch instead of malformed/incomplete evidence.
    close_event["broker_execution_quote_ask"] = 114.0
    mismatch = reconcile_account_state_trace(
        trace, pd.DataFrame([open_event, close_event]), breach_events=[]
    )
    assert mismatch["fill_cost_provenance"]["status"] == "mismatch"
    assert any(
        failure["check"] == "broker_quote_ask_matches_slippage_application"
        for failure in mismatch["failures"]
    )


def test_account_trace_marks_missing_trade_fill_schema_incomplete() -> None:
    trace = pd.DataFrame(
        [
            _trace_row(
                balance=100_000.0,
                equity=100_000.0,
                total_economic_value=100_000.0,
                trade_event_count=1,
                position_direction=1,
                position_size=1.0,
                position_entry_price=100.0,
                position_mark_price=100.0,
                peak_equity=100_000.0,
                trailing_drawdown_usd=0.0,
            )
        ]
    )
    events = pd.DataFrame([{"type": "open", "entry_commission": 0.0}])

    result = reconcile_account_state_trace(trace, events, breach_events=[])

    assert result["status"] == "incomplete"
    assert "trade_fill_cashflow_replay_missing_fields" in result["incomplete_reasons"]


def test_account_trace_reconciles_partial_close_cashflows_to_position_total() -> None:
    first_close = _close_event(exit_price=105.0, size=0.4, position_complete=False)
    second_close = _close_event(
        exit_price=110.0,
        size=0.6,
        position_complete=True,
    )
    second_close["position_net_pnl"] = float(cast(Any, first_close["net_pnl"])) + float(
        cast(Any, second_close["net_pnl"])
    )
    trace = pd.DataFrame(
        [
            _trace_row(
                balance=100_000.0,
                equity=100_000.0,
                total_economic_value=100_000.0,
                trade_event_count=3,
                trailing_drawdown_usd=3.0,
            )
        ]
    )
    events = pd.DataFrame([_open_event(), first_close, second_close])

    result = reconcile_account_state_trace(trace, events, breach_events=[])

    assert result["status"] == "matched", result["failures"]
    assert result["checks"]["completed_position_closes_full_open_size"] == 1
    assert result["checks"]["position_net_pnl_matches_fill_sum"] == 1


def test_account_trace_rejects_position_completion_flag_before_full_close() -> None:
    close_event = _close_event(exit_price=110.0, position_complete=False)
    trace = pd.DataFrame(
        [
            _trace_row(
                balance=100_002.0,
                equity=100_002.0,
                total_economic_value=100_002.0,
                trailing_drawdown_usd=1.0,
            )
        ]
    )
    events = pd.DataFrame([_open_event(), close_event])

    result = reconcile_account_state_trace(trace, events, breach_events=[])

    assert result["status"] == "mismatch"
    assert "open_position_retains_unclosed_size" in {
        failure["check"] for failure in result["failures"]
    }


def test_account_trace_fails_closed_on_malformed_position_direction() -> None:
    trace = pd.DataFrame(
        [
            _trace_row(
                balance=100_000.0,
                equity=100_000.0,
                total_economic_value=100_000.0,
                trade_event_count=0,
                peak_equity=100_000.0,
                trailing_drawdown_usd=0.0,
                position_direction="invalid",
            )
        ]
    )

    result = reconcile_account_state_trace(trace, pd.DataFrame(), breach_events=[])

    assert result["status"] == "incomplete"
    assert "invalid_position_state" in result["incomplete_reasons"]


def test_account_trace_marks_missing_breach_ledger_incomplete() -> None:
    trace = pd.DataFrame(
        [
            _trace_row(
                balance=100_000.0,
                equity=100_000.0,
                total_economic_value=100_000.0,
                peak_equity=100_000.0,
            )
        ]
    )
    result = reconcile_account_state_trace(trace, pd.DataFrame())

    assert result["status"] == "incomplete"
    assert "breach_event_ledger_not_supplied" in result["incomplete_reasons"]


def test_account_trace_fails_closed_on_malformed_breach_record() -> None:
    trace = pd.DataFrame(
        [
            _trace_row(
                balance=100_000.0,
                equity=100_000.0,
                total_economic_value=100_000.0,
                peak_equity=100_000.0,
            )
        ]
    )

    result = reconcile_account_state_trace(trace, pd.DataFrame(), breach_events=[cast(Any, None)])

    assert result["status"] == "incomplete"
    assert "invalid_breach_event_record" in result["incomplete_reasons"]


def test_account_trace_fails_closed_on_unknown_breach_reason() -> None:
    trace = pd.DataFrame(
        [
            _trace_row(
                balance=100_000.0,
                equity=100_000.0,
                total_economic_value=100_000.0,
                peak_equity=100_000.0,
            )
        ]
    )

    result = reconcile_account_state_trace(
        trace,
        pd.DataFrame(),
        breach_events=[
            {
                "schema_version": "risk-breach-event-v1",
                "time": "2025-01-06T15:00:00Z",
                "reason": "unknown_failure",
            }
        ],
    )

    assert result["status"] == "incomplete"
    assert "invalid_hard_breach_event_reason" in result["incomplete_reasons"]


def test_account_trace_rejects_new_entry_events_after_hard_breach() -> None:
    trace = pd.DataFrame(
        [
            _trace_row(
                decision_time="2025-01-06T14:59:00Z",
                valuation_time="2025-01-06T14:59:00Z",
                trade_event_count=1,
            ),
            _trace_row(
                decision_time="2025-01-06T15:00:00Z",
                valuation_time="2025-01-06T15:00:00Z",
                trade_event_count=1,
            ),
            _trace_row(
                decision_time="2025-01-06T15:01:00Z",
                valuation_time="2025-01-06T15:01:00Z",
                trade_event_count=3,
            ),
        ]
    )
    events = pd.DataFrame(
        [
            {"type": "open", "entry_commission": 0.0},
            {"type": "order_submit"},
            {"type": "open", "entry_commission": 0.0},
        ]
    )

    result = reconcile_account_state_trace(
        trace,
        events,
        breach_events=[
            {
                "schema_version": "risk-breach-event-v1",
                "time": "2025-01-06T15:00:00Z",
                "detection_time": "2025-01-06T15:00:00Z",
                "trade_event_count": 1,
                "reason": "daily_loss",
            }
        ],
    )

    assert result["checks"]["no_order_submission_fill_or_open_after_hard_breach"] == 1
    assert any(
        failure["check"] == "no_order_submission_fill_or_open_after_hard_breach"
        and failure["actual"] == 2.0
        for failure in result["failures"]
    )


def test_account_trace_reconciles_hard_breach_with_empty_trade_ledger() -> None:
    trace = pd.DataFrame(
        [
            _trace_row(
                balance=100_000.0,
                equity=100_000.0,
                total_economic_value=100_000.0,
                peak_equity=100_000.0,
                decision_time="2025-01-06T15:00:00Z",
                valuation_time="2025-01-06T15:00:00Z",
                trade_event_count=0,
                daily_pnl_basis="session_net_equity",
                breach_reason="daily_loss",
            )
        ]
    )

    result = reconcile_account_state_trace(
        trace,
        pd.DataFrame(),
        breach_events=[
            {
                "schema_version": "risk-breach-event-v1",
                "time": "2025-01-06T15:00:00Z",
                "detection_time": "2025-01-06T15:00:00Z",
                "trade_event_count": 0,
                "reason": "daily_loss",
            }
        ],
    )

    assert result["checks"]["no_order_submission_fill_or_open_after_hard_breach"] == 1
    assert not any(
        failure["check"] == "no_order_submission_fill_or_open_after_hard_breach"
        for failure in result["failures"]
    )


def _v2_breach(**overrides: object) -> dict[str, object]:
    event: dict[str, object] = {
        "schema_version": "risk-breach-event-v2",
        "time": "2025-01-06T15:00:00Z",
        "detection_time": "2025-01-06T15:00:00Z",
        "trade_event_count": 0,
        "session_id": 1,
        "reason": "daily_loss",
        "equity": 99_990.0,
        "daily_loss": 10.0,
        "daily_pnl_basis": "session_net_equity",
    }
    event.update(overrides)
    return event


def _v2_breach_trace(**overrides: object) -> pd.DataFrame:
    row = _trace_row(
        balance=99_990.0,
        equity=99_990.0,
        total_economic_value=99_990.0,
        peak_equity=100_000.0,
        session_start_equity=100_000.0,
        session_start_balance=100_000.0,
        daily_loss=10.0,
        daily_pnl_basis="session_net_equity",
        decision_time="2025-01-06T15:00:00Z",
        valuation_time="2025-01-06T15:01:00Z",
        breach_reason="daily_loss",
        trade_event_count=0,
    )
    row.update(overrides)
    return pd.DataFrame([row])


def test_v2_breach_recomputes_pre_close_loss_from_basis_anchor() -> None:
    result = reconcile_account_state_trace(
        _v2_breach_trace(), pd.DataFrame(), breach_events=[_v2_breach()]
    )

    assert result["checks"]["hard_breach_pre_close_daily_loss"] == 1
    assert not any(
        failure["check"] == "hard_breach_pre_close_daily_loss" for failure in result["failures"]
    )


def test_v2_breach_accepts_only_linked_account_guardrail_order_cancel_suffix() -> None:
    trace = pd.DataFrame(
        [
            _trace_row(
                decision_time="2025-01-06T14:59:00Z",
                valuation_time="2025-01-06T14:59:00Z",
                trade_event_count=1,
            ),
            _v2_breach_trace(trade_event_count=2).iloc[0].to_dict(),
        ]
    )
    ledger = pd.DataFrame(
        [
            {
                "type": "order_submit",
                "order_id": "bt:o1",
                "order_type": "limit",
                "decision_bar_time": "2025-01-06T14:59:00Z",
                "order_submission_time": "2025-01-06T14:59:00Z",
            },
            {
                "type": "order_cancel",
                "order_id": "bt:o1",
                "order_type": "limit",
                "reason": "session_blocked_before_limit_fill",
                "decision_id": "bt:d1",
                "time": "2025-01-06T15:00:30Z",
            },
        ]
    )
    for reason in (
        "session_blocked_before_limit_fill",
        "account_failed_before_limit_fill",
    ):
        ledger.loc[1, "reason"] = reason
        accepted = reconcile_account_state_trace(
            trace,
            ledger,
            breach_events=[_v2_breach(trade_event_count=1)],
        )
        assert (
            "hard_breach_prefix_suffix_has_unexpected_events" not in accepted["incomplete_reasons"]
        )

    unrelated = ledger.copy()
    unrelated.loc[1, "reason"] = "session_changed_before_limit_fill"
    rejected = reconcile_account_state_trace(
        trace,
        unrelated,
        breach_events=[_v2_breach(trade_event_count=1)],
    )
    assert "hard_breach_prefix_suffix_has_unexpected_events" in rejected["incomplete_reasons"]


def test_v2_breach_rejects_plausible_but_wrong_loss_and_basis() -> None:
    wrong_loss = reconcile_account_state_trace(
        _v2_breach_trace(),
        pd.DataFrame(),
        breach_events=[_v2_breach(daily_loss=9.0)],
    )
    assert any(
        failure["check"] == "hard_breach_pre_close_daily_loss" for failure in wrong_loss["failures"]
    )

    wrong_basis = reconcile_account_state_trace(
        _v2_breach_trace(),
        pd.DataFrame(),
        breach_events=[_v2_breach(daily_pnl_basis="ftmo_midnight_balance")],
    )
    assert "hard_breach_daily_pnl_basis_mismatch" in wrong_basis["incomplete_reasons"]


def test_v2_breach_requires_one_exact_trace_match() -> None:
    no_match = reconcile_account_state_trace(
        _v2_breach_trace(breach_reason="max_drawdown"),
        pd.DataFrame(),
        breach_events=[_v2_breach()],
    )
    assert "hard_breach_trace_match_missing_or_ambiguous" in no_match["incomplete_reasons"]

    duplicate_trace = pd.concat([_v2_breach_trace(), _v2_breach_trace()], ignore_index=True)
    ambiguous = reconcile_account_state_trace(
        duplicate_trace, pd.DataFrame(), breach_events=[_v2_breach()]
    )
    assert "hard_breach_trace_match_missing_or_ambiguous" in ambiguous["incomplete_reasons"]


def test_v2_breach_recomputes_ftmo_and_legacy_loss_from_their_own_bases() -> None:
    ftmo_trace = _v2_breach_trace(
        balance=99_985.0,
        equity=99_985.0,
        total_economic_value=99_985.0,
        daily_pnl_basis="ftmo_midnight_balance",
        session_start_balance=100_000.0,
        session_start_equity=99_995.0,
        daily_loss=15.0,
    )
    ftmo = reconcile_account_state_trace(
        ftmo_trace,
        pd.DataFrame(),
        breach_events=[
            _v2_breach(
                equity=99_985.0,
                daily_loss=15.0,
                daily_pnl_basis="ftmo_midnight_balance",
            )
        ],
    )
    assert ftmo["checks"]["hard_breach_pre_close_daily_loss"] == 1
    assert not any(
        failure["check"] == "hard_breach_pre_close_daily_loss" for failure in ftmo["failures"]
    )

    legacy_trace = pd.DataFrame(
        [
            _trace_row(
                decision_time="2025-01-06T14:59:00Z",
                valuation_time="2025-01-06T14:59:00Z",
                daily_pnl_basis="legacy_gross_closed_losses",
                trade_event_count=0,
            ),
            _trace_row(
                decision_time="2025-01-06T15:00:00Z",
                valuation_time="2025-01-06T15:01:00Z",
                daily_pnl_basis="legacy_gross_closed_losses",
                trade_event_count=1,
                breach_reason="daily_loss",
            ),
        ]
    )
    legacy_events = pd.DataFrame([{"type": "stop_close", "pnl": -10.0}])
    legacy = reconcile_account_state_trace(
        legacy_trace,
        legacy_events,
        breach_events=[
            _v2_breach(
                trade_event_count=1,
                daily_pnl_basis="legacy_gross_closed_losses",
            )
        ],
    )
    assert legacy["checks"]["hard_breach_pre_close_daily_loss"] == 1
    assert not any(
        failure["check"] == "hard_breach_pre_close_daily_loss" for failure in legacy["failures"]
    )


def test_v2_multiple_breaches_count_each_pre_close_reconciliation() -> None:
    first = _v2_breach_trace()
    second = _v2_breach_trace(
        balance=99_980.0,
        equity=99_980.0,
        total_economic_value=99_980.0,
        daily_loss=20.0,
        decision_time="2025-01-06T15:02:00Z",
        valuation_time="2025-01-06T15:03:00Z",
    )
    events = [
        _v2_breach(),
        _v2_breach(
            time="2025-01-06T15:02:00Z",
            detection_time="2025-01-06T15:02:00Z",
            equity=99_980.0,
            daily_loss=20.0,
        ),
    ]

    result = reconcile_account_state_trace(
        pd.concat([first, second], ignore_index=True), pd.DataFrame(), breach_events=events
    )

    assert result["checks"]["hard_breach_pre_close_daily_loss"] == 2
    assert not any(
        failure["check"] == "hard_breach_pre_close_daily_loss" for failure in result["failures"]
    )


def test_account_trace_rejects_v2_breach_without_daily_loss_basis() -> None:
    trace = pd.DataFrame(
        [
            _trace_row(
                decision_time="2025-01-06T15:00:00Z",
                valuation_time="2025-01-06T15:00:00Z",
                trade_event_count=0,
            )
        ]
    )

    result = reconcile_account_state_trace(
        trace,
        pd.DataFrame(),
        breach_events=[
            {
                "schema_version": "risk-breach-event-v2",
                "time": "2025-01-06T15:00:00Z",
                "detection_time": "2025-01-06T15:00:00Z",
                "trade_event_count": 0,
                "reason": "daily_loss",
                "daily_loss": 10.0,
            }
        ],
    )

    assert "hard_breach_daily_pnl_basis_is_invalid" in result["incomplete_reasons"]


def test_account_trace_rejects_pending_order_fill_after_hard_breach() -> None:
    trace = pd.DataFrame(
        [
            _trace_row(
                decision_time="2025-01-06T14:00:00Z",
                valuation_time="2025-01-06T14:00:00Z",
                trade_event_count=0,
            ),
            _trace_row(
                decision_time="2025-01-06T15:00:00Z",
                valuation_time="2025-01-06T15:00:00Z",
                trade_event_count=1,
            ),
            _trace_row(
                decision_time="2025-01-06T15:01:00Z",
                valuation_time="2025-01-06T15:01:00Z",
                trade_event_count=2,
            ),
        ]
    )
    events = pd.DataFrame(
        [
            {"type": "order_submit"},
            {"type": "order_fill"},
        ]
    )

    result = reconcile_account_state_trace(
        trace,
        events,
        breach_events=[
            {
                "schema_version": "risk-breach-event-v1",
                "time": "2025-01-06T15:00:00Z",
                "detection_time": "2025-01-06T15:00:00Z",
                "trade_event_count": 1,
                "reason": "daily_loss",
            }
        ],
    )

    assert result["checks"]["no_order_submission_fill_or_open_after_hard_breach"] == 1
    assert any(
        failure["check"] == "no_order_submission_fill_or_open_after_hard_breach"
        and failure["actual"] == 1.0
        for failure in result["failures"]
    )


def test_pre_action_trace_keeps_same_boundary_events_before_breach_latch() -> None:
    trace = pd.DataFrame(
        [
            _trace_row(
                state_phase="pre_action_valuation",
                decision_time="2025-01-06T15:00:00Z",
                valuation_time="2025-01-06T15:01:00Z",
                trade_event_count=1,
            ),
            _trace_row(
                state_phase="pre_action_valuation",
                decision_time="2025-01-06T15:01:00Z",
                valuation_time="2025-01-06T15:02:00Z",
                trade_event_count=2,
            ),
        ]
    )
    events = pd.DataFrame(
        [
            {"type": "open", "entry_commission": 0.0},
            {
                "type": "order_submit",
                "order_submission_time": "2025-01-06T15:00:00Z",
            },
        ]
    )

    result = reconcile_account_state_trace(
        trace,
        events,
        breach_events=[
            {
                "schema_version": "risk-breach-event-v1",
                "time": "2025-01-06T15:00:00Z",
                "detection_time": "2025-01-06T15:01:00Z",
                "trade_event_count": 2,
                "reason": "daily_loss",
            }
        ],
    )

    assert result["checks"]["no_order_submission_fill_or_open_after_hard_breach"] == 1
    assert not any(
        failure["check"] == "no_order_submission_fill_or_open_after_hard_breach"
        for failure in result["failures"]
    )


def test_account_trace_fails_closed_on_missing_post_breach_snapshot_time() -> None:
    trace = pd.DataFrame(
        [
            _trace_row(
                balance=100_000.0,
                equity=100_000.0,
                total_economic_value=100_000.0,
                peak_equity=100_000.0,
                decision_time="invalid-time",
            )
        ]
    )

    result = reconcile_account_state_trace(
        trace,
        pd.DataFrame(),
        breach_events=[
            {
                "schema_version": "risk-breach-event-v1",
                "time": "2025-01-06T15:00:00Z",
                "detection_time": "2025-01-06T15:01:00Z",
                "trade_event_count": 0,
                "reason": "daily_loss",
            }
        ],
    )

    assert result["status"] == "incomplete"
    assert "hard_breach_account_snapshot_time_is_invalid" in result["incomplete_reasons"]


def test_account_trace_requires_exact_breach_detection_metadata() -> None:
    trace = pd.DataFrame(
        [
            _trace_row(
                balance=100_000.0,
                equity=100_000.0,
                total_economic_value=100_000.0,
                peak_equity=100_000.0,
                decision_time="2025-01-06T15:01:00Z",
                valuation_time="2025-01-06T15:01:00Z",
                trade_event_count=0,
            )
        ]
    )
    result = reconcile_account_state_trace(
        trace,
        pd.DataFrame(),
        breach_events=[
            {
                "schema_version": "risk-breach-event-v1",
                "time": "2025-01-06T15:00:00Z",
                "reason": "daily_loss",
            }
        ],
    )

    assert result["status"] == "incomplete"
    assert "hard_breach_detection_time_is_invalid" in result["incomplete_reasons"]
    assert "hard_breach_trade_event_prefix_is_invalid" in result["incomplete_reasons"]


def test_account_trace_reconstructs_payout_reset_and_legacy_daily_loss() -> None:
    trace = pd.DataFrame(
        [
            _trace_row(
                balance=99_991.0,
                equity=99_991.0,
                total_economic_value=99_991.0,
                daily_loss=5.0,
                loss_from_initial_usd=9.0,
                max_drawdown_usd=9.0,
                max_drawdown_from_reference_usd=9.0,
                peak_equity=100_000.0,
                peak_eod_drawdown_usd=9.0,
                max_peak_eod_drawdown_usd=9.0,
                trailing_drawdown_usd=9.0,
                trade_event_count=2,
            ),
            _trace_row(
                balance=100_000.0,
                equity=100_000.0,
                session_start_balance=100_000.0,
                session_start_equity=100_000.0,
                daily_loss=0.0,
                loss_from_initial_usd=0.0,
                max_drawdown_usd=9.0,
                max_drawdown_from_reference_usd=0.0,
                peak_equity=100_003.0,
                peak_eod_drawdown_usd=0.0,
                max_peak_eod_drawdown_usd=9.0,
                trailing_drawdown_usd=3.0,
                payout_drawdown_floor=None,
                cumulative_payouts=3.0,
                total_economic_value=100_003.0,
                trade_event_count=5,
            ),
        ]
    )
    events = pd.DataFrame(
        [
            _open_event(position_id="loss", commission_per_lot=4.0),
            _close_event(position_id="loss", exit_price=99.0),
            _open_event(position_id="win", commission_per_lot=0.0),
            _close_event(
                position_id="win",
                exit_price=112.0,
                commission_per_lot=0.0,
            ),
            {
                "type": "payout_reset",
                "payout_schema_version": "payout_reset.v2",
                "max_drawdown_mode": "static",
                "payout_fraction": 1.0,
                "profit_above_operating_balance": 3.0,
                "payout": 3.0,
                "retained_profit": 0.0,
                "balance_before_reset": 100_003.0,
                "operating_balance": 100_000.0,
                "balance_after_reset": 100_000.0,
            },
        ]
    )

    result = reconcile_account_state_trace(trace, events, breach_events=[])

    assert result["status"] == "matched", result["failures"]
    assert result["checks"]["legacy_daily_loss_matches_close_events"] == 2
    assert result["checks"]["payout_events_reconstruct_cumulative_payouts"] == 2
    assert result["checks"]["daily_risk_equity_anchor_matches_session_or_payout_reset"] == 2


@pytest.mark.parametrize("mode", ["eod", "intraday_trailing"])
def test_account_trace_reconstructs_retained_profit_after_dynamic_payout(mode: str) -> None:
    trace = pd.DataFrame(
        [
            _trace_row(
                max_drawdown_mode=mode,
                balance=102_500.0,
                equity=102_500.0,
                session_start_balance=102_500.0,
                session_start_equity=102_500.0,
                daily_loss=0.0,
                daily_floor_equity=97_500.0,
                max_loss_floor_equity=100_000.0,
                max_drawdown_from_reference_usd=2_500.0,
                peak_equity=105_000.0,
                trailing_drawdown_usd=2_500.0,
                peak_eod_equity=105_000.0,
                peak_eod_drawdown_usd=2_500.0,
                max_peak_eod_drawdown_usd=0.0,
                payout_drawdown_floor=100_000.0,
                trade_event_count=3,
                cumulative_payouts=2_500.0,
                total_economic_value=105_000.0,
            )
        ]
    )
    events = pd.DataFrame(
        [
            _open_event(position_id="profit", commission_per_lot=0.0),
            _close_event(
                position_id="profit",
                exit_price=5_100.0,
                commission_per_lot=0.0,
            ),
            {
                "type": "payout_reset",
                "payout_schema_version": "payout_reset.v2",
                "max_drawdown_mode": mode,
                "payout_fraction": 0.5,
                "profit_above_operating_balance": 5_000.0,
                "payout": 2_500.0,
                "retained_profit": 2_500.0,
                "balance_before_reset": 105_000.0,
                "operating_balance": 100_000.0,
                "balance_after_reset": 102_500.0,
            },
        ]
    )

    result = reconcile_account_state_trace(trace, events, breach_events=[])

    assert result["status"] == "matched", result["failures"]


def test_account_trace_fails_closed_on_a_corrupted_cashflow() -> None:
    trace = pd.DataFrame([_trace_row(balance=99_991.0, equity=99_991.0, daily_loss=5.0)])
    events = pd.DataFrame(
        [
            {"type": "open", "entry_commission": 4.0},
            {"type": "close", "pnl": -50.0},
        ]
    )

    result = reconcile_account_state_trace(trace, events, breach_events=[])

    assert result["status"] == "mismatch"
    assert {failure["check"] for failure in result["failures"]} >= {
        "event_cashflows_reconstruct_balance",
        "legacy_daily_loss_matches_close_events",
    }


def test_maximum_drawdown_cover_check_allows_floating_point_roundoff() -> None:
    trace = pd.DataFrame(
        [
            _trace_row(
                balance=100_000.0,
                equity=99_900.0,
                open_pnl=-100.0,
                loss_from_initial_usd=100.0,
                max_drawdown_usd=100.0 - 5e-8,
                peak_equity=100_000.0,
                total_economic_value=99_900.0,
            )
        ]
    )

    result = reconcile_account_state_trace(trace, pd.DataFrame(), breach_events=[])

    assert "maximum_drawdown_covers_current_loss" not in {
        failure["check"] for failure in result["failures"]
    }


def test_account_trace_detects_payout_that_does_not_match_replayed_cash() -> None:
    trace = pd.DataFrame(
        [
            _trace_row(
                balance=100_100.0,
                equity=100_100.0,
                daily_loss=0.0,
                trade_event_count=3,
                cumulative_payouts=3.0,
                total_economic_value=100_103.0,
            )
        ]
    )
    events = pd.DataFrame(
        [
            {"type": "open", "entry_commission": 0.0},
            {"type": "close", "pnl": 3.0},
            {
                "type": "payout_reset",
                "payout": 3.0,
                "balance_before_reset": 100_103.0,
                "operating_balance": 100_100.0,
            },
        ]
    )

    result = reconcile_account_state_trace(trace, events, breach_events=[])

    assert result["status"] == "mismatch"
    assert "payout_event_matches_replayed_balance" in {
        failure["check"] for failure in result["failures"]
    }


@pytest.mark.parametrize("payout_floor", [None, 99_999.0])
def test_account_trace_detects_payout_drawdown_floor_drift(payout_floor: float | None) -> None:
    trace = pd.DataFrame(
        [
            _trace_row(
                max_drawdown_mode="eod",
                balance=100_000.0,
                equity=100_000.0,
                trade_event_count=3,
                cumulative_payouts=3.0,
                total_economic_value=100_003.0,
                payout_drawdown_floor=payout_floor,
            )
        ]
    )
    events = pd.DataFrame(
        [
            {"type": "open", "entry_commission": 0.0},
            {"type": "close", "pnl": 3.0},
            {
                "type": "payout_reset",
                "payout": 3.0,
                "balance_before_reset": 100_003.0,
                "operating_balance": 100_000.0,
            },
        ]
    )

    result = reconcile_account_state_trace(trace, events, breach_events=[])

    assert result["status"] == "mismatch"
    assert "payout_drawdown_floor_matches_initial_after_reset" in {
        failure["check"] for failure in result["failures"]
    }


def test_account_trace_rejects_payout_that_withdraws_initial_capital() -> None:
    trace = pd.DataFrame(
        [
            _trace_row(
                balance=99_998.0,
                equity=99_998.0,
                session_start_balance=99_998.0,
                session_start_equity=99_998.0,
                daily_loss=0.0,
                daily_floor_equity=94_998.0,
                loss_from_initial_usd=2.0,
                max_drawdown_usd=2.0,
                max_drawdown_from_reference_usd=2.0,
                peak_equity=100_000.0,
                peak_eod_drawdown_usd=2.0,
                max_peak_eod_drawdown_usd=2.0,
                trailing_drawdown_usd=2.0,
                payout_drawdown_floor=100_000.0,
                trade_event_count=3,
                cumulative_payouts=1.0,
                total_economic_value=99_999.0,
            )
        ]
    )
    events = pd.DataFrame(
        [
            {"type": "open", "entry_commission": 0.0},
            {"type": "close", "pnl": -1.0},
            {
                "type": "payout_reset",
                "payout": 1.0,
                "balance_before_reset": 99_999.0,
                "operating_balance": 99_998.0,
            },
        ]
    )

    result = reconcile_account_state_trace(trace, events, breach_events=[])

    assert result["status"] == "mismatch"
    assert {
        "payout_balance_exceeds_initial_operating_balance",
        "payout_resets_to_initial_operating_balance",
    } <= {failure["check"] for failure in result["failures"]}


def test_account_trace_detects_daily_anchor_drift_without_session_or_payout_reset() -> None:
    trace = pd.DataFrame(
        [
            _trace_row(),
            _trace_row(
                initial_balance=99_000.0,
                session_start_balance=99_000.0,
                session_start_equity=99_000.0,
            ),
        ]
    )

    events = pd.DataFrame(
        [
            {"type": "open", "entry_commission": 0.0},
            {"type": "close", "pnl": 3.0},
        ]
    )
    result = reconcile_account_state_trace(trace, events, breach_events=[])

    assert result["status"] == "mismatch"
    assert {failure["check"] for failure in result["failures"]} >= {
        "initial_balance_remains_constant",
        "daily_risk_anchor_matches_session_or_payout_reset",
        "daily_risk_equity_anchor_matches_session_or_payout_reset",
    }


def test_account_trace_marks_uncovered_trailing_events_incomplete() -> None:
    trace = pd.DataFrame([_trace_row()])
    events = pd.DataFrame(
        [
            {"type": "open", "entry_commission": 4.0},
            {"type": "close", "pnl": 7.0},
            {"type": "order_submit", "order_id": "o2"},
        ]
    )

    result = reconcile_account_state_trace(trace, events, breach_events=[])

    assert result["status"] == "incomplete"
    assert "trade_events_outside_snapshot_coverage" in result["incomplete_reasons"]


def test_account_trace_fails_closed_on_unsupported_cash_event_type() -> None:
    trace = pd.DataFrame([_trace_row(trade_event_count=1)])
    events = pd.DataFrame([{"type": "financing_charge", "amount": 12.0}])

    result = reconcile_account_state_trace(trace, events, breach_events=[])

    assert result["status"] == "incomplete"
    assert "unsupported_trade_event_type_for_cash_replay" in result["incomplete_reasons"]


def test_account_trace_checks_equity_high_water_marks_and_drawdown_history() -> None:
    trace = pd.DataFrame(
        [
            _trace_row(
                equity=99_000.0,
                balance=99_000.0,
                daily_loss=1_000.0,
                loss_from_initial_usd=1_000.0,
                max_drawdown_usd=1_000.0,
                peak_equity=100_000.0,
                peak_eod_equity=100_000.0,
                peak_eod_drawdown_usd=900.0,
                max_peak_eod_drawdown_usd=500.0,
                trailing_drawdown_usd=1_000.0,
                max_loss_floor_equity=90_000.0,
                daily_floor_equity=95_000.0,
                max_drawdown_from_reference_usd=1_000.0,
                trade_event_count=0,
            ),
            _trace_row(
                valuation_time="2025-01-06T14:59:00Z",
                equity=100_003.0,
                balance=100_003.0,
                daily_loss=0.0,
                loss_from_initial_usd=0.0,
                max_drawdown_usd=1_000.0,
                peak_equity=99_500.0,
                peak_eod_equity=100_000.0,
                peak_eod_drawdown_usd=0.0,
                max_peak_eod_drawdown_usd=500.0,
                trailing_drawdown_usd=0.0,
                max_loss_floor_equity=90_000.0,
                daily_floor_equity=95_000.0,
                max_drawdown_from_reference_usd=0.0,
                trade_event_count=0,
            ),
        ]
    )

    result = reconcile_account_state_trace(trace, pd.DataFrame(), breach_events=[])

    assert result["status"] == "mismatch"
    assert {failure["check"] for failure in result["failures"]} >= {
        "valuation_time_is_monotonic",
        "peak_equity_covers_current_equity",
        "peak_equity_is_monotonic",
        "eod_drawdown_matches_peak_and_equity",
    }


def test_account_trace_accepts_intrabar_peak_above_post_action_equity() -> None:
    trace = pd.DataFrame(
        [
            _trace_row(
                valuation_time="2025-01-06T15:00:00Z",
                balance=100_000.0,
                equity=100_000.0,
                total_economic_value=100_000.0,
                peak_equity=100_000.0,
                peak_eod_equity=100_000.0,
                trade_event_count=0,
            ),
            _trace_row(
                valuation_time="2025-01-06T15:01:00Z",
                balance=100_044.0,
                equity=100_044.0,
                total_economic_value=100_044.0,
                peak_equity=100_250.0,
                peak_eod_equity=100_000.0,
                max_peak_eod_drawdown_usd=0.0,
                trailing_drawdown_usd=206.0,
                trade_event_count=2,
            ),
        ]
    )

    events = pd.DataFrame([_open_event(), _close_event(exit_price=152.0)])
    result = reconcile_account_state_trace(trace, events, breach_events=[])

    assert result["status"] == "matched", result["failures"]


def test_account_trace_accepts_completed_session_high_water_mark_transition() -> None:
    trace = pd.DataFrame(
        [
            _trace_row(
                equity=100_003.0,
                balance=100_003.0,
                peak_equity=100_003.0,
                peak_eod_equity=100_003.0,
                session_id=1,
                trade_event_count=2,
            ),
            _trace_row(
                valuation_time="2025-01-07T15:00:00Z",
                equity=100_003.0,
                balance=100_003.0,
                session_start_balance=100_003.0,
                session_start_equity=100_003.0,
                daily_floor_equity=95_003.0,
                peak_equity=100_003.0,
                peak_eod_equity=100_003.0,
                session_id=2,
                trade_event_count=2,
            ),
        ]
    )

    events = pd.DataFrame(
        [
            _open_event(),
            _close_event(exit_price=111.0),
        ]
    )
    result = reconcile_account_state_trace(trace, events, breach_events=[])

    assert result["status"] == "matched", result
    assert result["checks"]["eod_peak_is_monotonic"] == 1
    assert result["checks"]["maximum_eod_drawdown_is_monotonic"] == 1
