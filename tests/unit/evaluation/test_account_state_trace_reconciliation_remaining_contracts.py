"""Legacy cashflow traces still reconcile adverse short-side fills."""

from __future__ import annotations

import pandas as pd

from evaluation.reporting.account_state_trace_reconciliation import (
    reconcile_account_state_trace,
)
from trading.execution import FILL_COST_PROVENANCE_SCHEMA_VERSION


def test_legacy_short_cashflow_uses_unit_point_value_and_adverse_close_quote() -> None:
    trace = pd.DataFrame(
        [
            {
                "schema_version": "account_state_trace.v3",
                "valuation_time": "2025-01-06T15:00:00Z",
                "decision_time": "2025-01-06T15:00:00Z",
                "state_phase": "post_action_valuation",
                "session_id": 1,
                "initial_balance": 100_000.0,
                "balance": 99_989.5,
                "equity": 99_989.5,
                "open_pnl": 0.0,
                "session_start_balance": 100_000.0,
                "session_start_equity": 100_000.0,
                "daily_pnl_basis": "legacy_gross_closed_losses",
                "daily_loss": 6.5,
                "daily_loss_limit_usd": 5_000.0,
                "daily_floor_equity": 95_000.0,
                "max_loss_limit_usd": 10_000.0,
                "max_loss_floor_equity": 90_000.0,
                "max_drawdown_mode": "static",
                "max_drawdown_from_reference_usd": 10.5,
                "loss_from_initial_usd": 10.5,
                "max_drawdown_usd": 10.5,
                "peak_equity": 100_000.0,
                "peak_eod_equity": 100_000.0,
                "peak_eod_drawdown_usd": 10.5,
                "max_peak_eod_drawdown_usd": 10.5,
                "payout_drawdown_floor": None,
                "trailing_drawdown_usd": 10.5,
                "position_direction": 0,
                "position_size": 0.0,
                "position_entry_price": None,
                "position_mark_price": None,
                "contract_size": 1.0,
                "point_value": 1.0,
                "trade_event_count": 2,
                "cumulative_payouts": 0.0,
                "total_economic_value": 99_989.5,
            }
        ]
    )
    open_event = {
        "type": "open",
        "position_id": "short-1",
        "cashflow_schema_version": "trade_fill_cashflow.v1",
        "direction": -1,
        "price": 98.75,
        "lots": 1.0,
        "contract_size": 1.0,
        "commission_per_lot": 4.0,
        "entry_commission": 4.0,
        "fill_cost_provenance_schema_version": FILL_COST_PROVENANCE_SCHEMA_VERSION,
        "pre_execution_quote_bid": 99.0,
        "pre_execution_quote_ask": 101.0,
        "broker_execution_quote_bid": 98.75,
        "broker_execution_quote_ask": 101.0,
        "slippage_points_applied_here": 0.25,
        "slippage_applied_here": True,
        "slippage_application_mode": "transacted_side",
    }
    close_event = {
        "type": "close",
        "position_id": "short-1",
        "cashflow_schema_version": "trade_fill_cashflow.v1",
        "direction": -1,
        "entry_price": 98.75,
        "price": 101.25,
        "size": 1.0,
        "contract_size": 1.0,
        "commission_per_lot": 4.0,
        "gross_price_pnl": -2.5,
        "exit_commission": 4.0,
        "entry_commission_allocated": 4.0,
        "pnl": -6.5,
        "net_pnl": -10.5,
        "position_complete": True,
        "position_net_pnl": -10.5,
        "fill_cost_provenance_schema_version": FILL_COST_PROVENANCE_SCHEMA_VERSION,
        "pre_execution_quote_bid": 99.0,
        "pre_execution_quote_ask": 101.0,
        "broker_execution_quote_bid": 99.0,
        "broker_execution_quote_ask": 101.25,
        "slippage_points_applied_here": 0.25,
        "slippage_applied_here": True,
        "slippage_application_mode": "transacted_side",
    }

    report = reconcile_account_state_trace(
        trace, pd.DataFrame([open_event, close_event]), breach_events=[]
    )

    assert report["status"] == "matched", report["failures"]
    assert report["checks"]["gross_close_pnl_matches_executable_fills"] == 1
    assert report["checks"]["fill_price_matches_broker_quote_side"] == 2
    assert report["checks"]["event_cashflows_reconstruct_balance"] == 1
    assert report["fill_cost_provenance"]["verified_rows"] == 2
