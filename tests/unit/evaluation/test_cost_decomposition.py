from __future__ import annotations

import pandas as pd
import pytest

from evaluation.reporting.cost_decomposition import decompose_fill_costs
from trading.execution import (
    FILL_COST_PROVENANCE_SCHEMA_VERSION,
    TRADE_CASHFLOW_SCHEMA_VERSION,
)


def _provenance(
    *,
    pre_bid: float,
    pre_ask: float,
    broker_bid: float,
    broker_ask: float,
    mode: str = "transacted_side",
) -> dict[str, object]:
    return {
        "fill_cost_provenance_schema_version": FILL_COST_PROVENANCE_SCHEMA_VERSION,
        "pre_execution_quote_bid": pre_bid,
        "pre_execution_quote_ask": pre_ask,
        "broker_execution_quote_bid": broker_bid,
        "broker_execution_quote_ask": broker_ask,
        "slippage_points_applied_here": 0.25,
        "slippage_applied_here": True,
        "slippage_application_mode": mode,
    }


def test_cost_decomposition_reconciles_midpoint_to_net_position_pnl() -> None:
    events = pd.DataFrame(
        [
            {
                "type": "open",
                "position_id": "position-1",
                "direction": 1,
                "price": 101.25,
                "lots": 1.0,
                "contract_size": 1.0,
                "commission_per_lot": 2.0,
                "entry_commission": 2.0,
                "cashflow_schema_version": TRADE_CASHFLOW_SCHEMA_VERSION,
                **_provenance(
                    pre_bid=99.0,
                    pre_ask=101.0,
                    broker_bid=99.0,
                    broker_ask=101.25,
                ),
            },
            {
                "type": "close",
                "position_id": "position-1",
                "direction": 1,
                "entry_price": 101.25,
                "price": 101.75,
                "size": 1.0,
                "contract_size": 1.0,
                "commission_per_lot": 2.0,
                "gross_price_pnl": 0.5,
                "exit_commission": 2.0,
                "entry_commission_allocated": 2.0,
                "net_pnl": -3.5,
                "position_complete": True,
                "cashflow_schema_version": TRADE_CASHFLOW_SCHEMA_VERSION,
                **_provenance(
                    pre_bid=102.0,
                    pre_ask=104.0,
                    broker_bid=101.75,
                    broker_ask=104.0,
                ),
            },
        ]
    )

    report = decompose_fill_costs(events)

    assert report["status"] == "matched"
    assert report["completed_position_count"] == 1
    assert report["fill_count"] == 2
    assert report["gross_midpoint_pnl"] == 3.0
    assert report["gross_executed_price_pnl"] == 0.5
    assert report["spread_cost"] == 2.0
    assert report["slippage_cost"] == 0.5
    assert report["commission_cost"] == 4.0
    assert report["net_pnl"] == -3.5
    assert abs(report["reconciliation_residual"]) < 1e-9

    events.loc[1, "gross_price_pnl"] = 0.6
    corrupted = decompose_fill_costs(events)
    assert corrupted["status"] == "unavailable"
    assert (
        corrupted["availability_reason"]
        == "completed_position_close_execution_quote_does_not_reconcile"
    )
    events.loc[1, "gross_price_pnl"] = 0.5
    events.loc[1, "exit_commission"] = 1.9
    corrupted_commission = decompose_fill_costs(events)
    assert corrupted_commission["status"] == "unavailable"
    assert (
        corrupted_commission["availability_reason"]
        == "completed_position_close_execution_quote_does_not_reconcile"
    )


def test_cost_decomposition_does_not_call_historical_missing_cost_zero() -> None:
    report = decompose_fill_costs(
        [
            {
                "type": "open",
                "position_id": "historical-position",
                "direction": 1,
                "price": 100.0,
                "lots": 1.0,
                "contract_size": 1.0,
                "commission_per_lot": 2.0,
                "entry_commission": 2.0,
                "cashflow_schema_version": TRADE_CASHFLOW_SCHEMA_VERSION,
            },
            {
                "type": "close",
                "position_id": "historical-position",
                "direction": 1,
                "price": 100.0,
                "size": 1.0,
                "contract_size": 1.0,
                "gross_price_pnl": 0.0,
                "exit_commission": 2.0,
                "entry_commission_allocated": 2.0,
                "net_pnl": -4.0,
                "position_complete": True,
                "cashflow_schema_version": TRADE_CASHFLOW_SCHEMA_VERSION,
            },
        ]
    )

    assert report["status"] == "unavailable"
    assert report["availability_reason"] == "completed_position_open_cost_evidence_missing"
    assert report["spread_cost"] is None
    assert report["slippage_cost"] is None
    assert report["commission_cost"] is None


def test_cost_decomposition_rejects_corruption_on_untouched_quote_side() -> None:
    events = pd.DataFrame(
        [
            {
                "type": "open",
                "position_id": "position-1",
                "direction": 1,
                "price": 101.25,
                "lots": 1.0,
                "contract_size": 1.0,
                "commission_per_lot": 2.0,
                "entry_commission": 2.0,
                "cashflow_schema_version": TRADE_CASHFLOW_SCHEMA_VERSION,
                **_provenance(
                    pre_bid=99.0,
                    pre_ask=101.0,
                    broker_bid=98.5,
                    broker_ask=101.25,
                ),
            },
            {
                "type": "close",
                "position_id": "position-1",
                "direction": 1,
                "entry_price": 101.25,
                "price": 101.75,
                "size": 1.0,
                "contract_size": 1.0,
                "commission_per_lot": 2.0,
                "gross_price_pnl": 0.5,
                "exit_commission": 2.0,
                "entry_commission_allocated": 2.0,
                "net_pnl": -3.5,
                "position_complete": True,
                "cashflow_schema_version": TRADE_CASHFLOW_SCHEMA_VERSION,
                **_provenance(
                    pre_bid=102.0,
                    pre_ask=104.0,
                    broker_bid=101.75,
                    broker_ask=104.0,
                ),
            },
        ]
    )

    report = decompose_fill_costs(events)

    assert report["status"] == "unavailable"
    assert (
        report["availability_reason"]
        == "completed_position_open_execution_or_commission_does_not_reconcile"
    )


def test_cost_decomposition_allocates_costs_across_partial_protective_and_market_closes() -> None:
    events = pd.DataFrame(
        [
            {
                "type": "open",
                "position_id": "position-1",
                "direction": 1,
                "price": 101.25,
                "lots": 1.0,
                "contract_size": 1.0,
                "commission_per_lot": 2.0,
                "entry_commission": 2.0,
                "cashflow_schema_version": TRADE_CASHFLOW_SCHEMA_VERSION,
                **_provenance(
                    pre_bid=99.0,
                    pre_ask=101.0,
                    broker_bid=99.0,
                    broker_ask=101.25,
                ),
            },
            {
                "type": "tp_partial_close",
                "position_id": "position-1",
                "direction": 1,
                "entry_price": 101.25,
                "price": 101.75,
                "size": 0.4,
                "contract_size": 1.0,
                "commission_per_lot": 2.0,
                "gross_price_pnl": 0.2,
                "exit_commission": 0.8,
                "entry_commission_allocated": 0.8,
                "net_pnl": -1.4,
                "position_complete": False,
                "cashflow_schema_version": TRADE_CASHFLOW_SCHEMA_VERSION,
                **_provenance(
                    pre_bid=102.0,
                    pre_ask=104.0,
                    broker_bid=101.75,
                    broker_ask=103.75,
                    mode="quote_level_shift",
                ),
            },
            {
                "type": "tp_close",
                "position_id": "position-1",
                "direction": 1,
                "entry_price": 101.25,
                "price": 104.75,
                "size": 0.6,
                "contract_size": 1.0,
                "commission_per_lot": 2.0,
                "gross_price_pnl": 2.1,
                "exit_commission": 1.2,
                "entry_commission_allocated": 1.2,
                "net_pnl": -0.3,
                "position_complete": True,
                "cashflow_schema_version": TRADE_CASHFLOW_SCHEMA_VERSION,
                **_provenance(
                    pre_bid=105.0,
                    pre_ask=107.0,
                    broker_bid=104.75,
                    broker_ask=107.0,
                ),
            },
        ]
    )

    report = decompose_fill_costs(events)

    assert report["status"] == "matched"
    assert report["completed_position_count"] == 1
    assert report["fill_count"] == 3
    assert report["gross_midpoint_pnl"] == pytest.approx(4.8)
    assert report["gross_executed_price_pnl"] == pytest.approx(2.3)
    assert report["spread_cost"] == pytest.approx(2.0)
    assert report["slippage_cost"] == pytest.approx(0.5)
    assert report["commission_cost"] == pytest.approx(4.0)
    assert report["net_pnl"] == pytest.approx(-1.7)
    assert abs(report["reconciliation_residual"]) < 1e-9

    events.loc[1, "position_complete"] = True
    invalid_lifecycle = decompose_fill_costs(events)
    assert invalid_lifecycle["status"] == "unavailable"
    assert (
        invalid_lifecycle["availability_reason"]
        == "completed_position_close_cost_evidence_missing_or_invalid"
    )


def test_cost_decomposition_reconciles_short_protective_quote_level_slippage() -> None:
    events = pd.DataFrame(
        [
            {
                "type": "open",
                "position_id": "short-position",
                "direction": -1,
                "price": 98.75,
                "lots": 1.0,
                "contract_size": 1.0,
                "commission_per_lot": 2.0,
                "entry_commission": 2.0,
                "cashflow_schema_version": TRADE_CASHFLOW_SCHEMA_VERSION,
                **_provenance(
                    pre_bid=99.0,
                    pre_ask=101.0,
                    broker_bid=98.75,
                    broker_ask=101.0,
                ),
            },
            {
                "type": "stop_close",
                "position_id": "short-position",
                "direction": -1,
                "entry_price": 98.75,
                "price": 104.25,
                "size": 1.0,
                "contract_size": 1.0,
                "commission_per_lot": 2.0,
                "gross_price_pnl": -5.5,
                "exit_commission": 2.0,
                "entry_commission_allocated": 2.0,
                "net_pnl": -9.5,
                "position_complete": True,
                "cashflow_schema_version": TRADE_CASHFLOW_SCHEMA_VERSION,
                **_provenance(
                    pre_bid=102.0,
                    pre_ask=104.0,
                    broker_bid=102.25,
                    broker_ask=104.25,
                    mode="quote_level_shift",
                ),
            },
        ]
    )

    report = decompose_fill_costs(events)

    assert report["status"] == "matched"
    assert report["gross_midpoint_pnl"] == pytest.approx(-3.0)
    assert report["gross_executed_price_pnl"] == pytest.approx(-5.5)
    assert report["spread_cost"] == pytest.approx(2.0)
    assert report["slippage_cost"] == pytest.approx(0.5)
    assert report["commission_cost"] == pytest.approx(4.0)
    assert report["net_pnl"] == pytest.approx(-9.5)
    assert abs(report["reconciliation_residual"]) < 1e-9
