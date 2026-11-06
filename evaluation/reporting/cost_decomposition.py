"""Reconcile midpoint returns to spread, slippage, commission, and net fills."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any, cast

import pandas as pd

from trading.execution import (
    FILL_COST_PROVENANCE_SCHEMA_VERSION,
    TRADE_CASHFLOW_SCHEMA_VERSION,
)

COST_DECOMPOSITION_SCHEMA_VERSION = "qrl.cost_decomposition.v1"
_CLOSE_TYPES = frozenset(
    {"close", "stop_close", "tp_close", "forced_close", "eod_close", "tp_partial_close"}
)


def _number(value: Any) -> float | None:
    """Return a finite non-boolean number or ``None``.

    Args:
        value: Raw value from an execution-event record.

    Returns:
        Finite float, or ``None`` when conversion is invalid.
    """
    if isinstance(value, bool) or type(value).__name__ in {"bool", "bool_"}:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def _boolean(value: Any) -> bool | None:
    """Read a typed fill-completion flag without truthiness coercion.

    Args:
        value: Raw completion flag from a fill event.

    Returns:
        Boolean flag, or ``None`` when the input is not a boolean.
    """
    if isinstance(value, bool) or type(value).__name__ in {"bool", "bool_"}:
        return bool(value)
    return None


def _expected_execution_quote(
    bid: float,
    ask: float,
    direction: float,
    slippage: float,
    *,
    opening: bool,
    mode: str,
) -> tuple[float, float]:
    """Apply a recorded adverse fill adjustment to the complete quote.

    Args:
        bid: Reference bid before execution adjustment.
        ask: Reference ask before execution adjustment.
        direction: Position direction, positive for long and negative for short.
        slippage: Adverse price adjustment in quote price units.
        opening: Whether this is an entry fill rather than an exit.
        mode: Recorded slippage contract to apply.

    Returns:
        Expected bid and ask after the execution adjustment.
    """
    if mode == "none":
        return bid, ask
    if mode == "quote_level_shift":
        shift = slippage if (direction == 1.0 if opening else direction == -1.0) else -slippage
        return bid + shift, ask + shift
    if opening:
        return (bid, ask + slippage) if direction == 1.0 else (bid - slippage, ask)
    return (bid - slippage, ask) if direction == 1.0 else (bid, ask + slippage)


def _quote_matches(
    actual_bid: float,
    actual_ask: float,
    reference_bid: float,
    reference_ask: float,
    direction: float,
    slippage: float,
    *,
    opening: bool,
    mode: str,
    tolerance: float,
) -> bool:
    """Verify both quote sides follow the declared execution adjustment.

    Args:
        actual_bid: Bid recorded on the executed fill.
        actual_ask: Ask recorded on the executed fill.
        reference_bid: Bid before the execution adjustment.
        reference_ask: Ask before the execution adjustment.
        direction: Position direction used to determine adverse movement.
        slippage: Expected adverse adjustment in price units.
        opening: Whether the fill opens a position.
        mode: Recorded slippage contract.
        tolerance: Relative and absolute comparison tolerance.

    Returns:
        Whether both executed quote sides match the expected adjustment.
    """
    expected_bid, expected_ask = _expected_execution_quote(
        reference_bid,
        reference_ask,
        direction,
        slippage,
        opening=opening,
        mode=mode,
    )
    return math.isclose(
        actual_bid, expected_bid, rel_tol=tolerance, abs_tol=tolerance
    ) and math.isclose(actual_ask, expected_ask, rel_tol=tolerance, abs_tol=tolerance)


def _unavailable(reason: str, *, fill_count: int, open_position_count: int = 0) -> dict[str, Any]:
    """Build an unavailable result while preserving observed ledger counts.

    Args:
        reason: Reason the ledger cannot support a cost decomposition.
        fill_count: Number of open and close events observed.
        open_position_count: Number of positions still open at the cutoff.

    Returns:
        Schema-versioned unavailable report with observed counts retained.
    """
    return {
        "schema_version": COST_DECOMPOSITION_SCHEMA_VERSION,
        "status": "unavailable",
        "availability_reason": reason,
        "completed_position_count": 0,
        "open_position_count": open_position_count,
        "fill_count": fill_count,
        "gross_midpoint_pnl": None,
        "gross_executed_price_pnl": None,
        "spread_cost": None,
        "slippage_cost": None,
        "commission_cost": None,
        "net_pnl": None,
        "reconciliation_residual": None,
    }


def decompose_fill_costs(
    trade_events: pd.DataFrame | Sequence[Mapping[str, Any]], *, tolerance: float = 1e-7
) -> dict[str, Any]:
    """Reconcile closed positions from pre-adjustment quotes through net cashflow.

    Only positions with an explicit complete close are summarized. Entry costs
    are allocated in proportion to the closed size, so a still-open remainder
    cannot distort the realized-position totals. Missing historical provenance
    produces an unavailable report instead of treating costs as zero.

    Args:
        trade_events: Ordered execution events as a DataFrame or row mappings.
        tolerance: Positive numeric tolerance used for quote reconciliation.

    Returns:
        Cost totals and reconciliation residual, or an unavailable report.
    """
    if not math.isfinite(tolerance) or tolerance <= 0.0:
        raise ValueError("tolerance must be finite and positive")
    if isinstance(trade_events, pd.DataFrame):
        records = cast(list[Mapping[str, Any]], trade_events.to_dict(orient="records"))
    else:
        records = list(trade_events)
    fills = [row for row in records if row.get("type") == "open" or row.get("type") in _CLOSE_TYPES]
    groups: dict[str, list[Mapping[str, Any]]] = {}
    for row in fills:
        position_id = row.get("position_id")
        if not isinstance(position_id, str) or not position_id:
            return _unavailable("position_identity_missing", fill_count=len(fills))
        groups.setdefault(position_id, []).append(row)

    totals = {
        "gross_midpoint_pnl": 0.0,
        "gross_executed_price_pnl": 0.0,
        "spread_cost": 0.0,
        "slippage_cost": 0.0,
        "commission_cost": 0.0,
        "net_pnl": 0.0,
    }
    completed_position_count = 0
    open_position_count = 0
    used_fills = 0
    for events in groups.values():
        opens = [row for row in events if row.get("type") == "open"]
        closes = [row for row in events if row.get("type") in _CLOSE_TYPES]
        if not closes or _boolean(closes[-1].get("position_complete")) is not True:
            open_position_count += 1
            continue
        if len(opens) != 1 or not events or events[0].get("type") != "open":
            return _unavailable(
                "completed_position_has_invalid_open_count",
                fill_count=len(fills),
                open_position_count=open_position_count,
            )
        opened = opens[0]
        direction = _number(opened.get("direction"))
        entry_lots = _number(opened.get("lots"))
        contract_size = _number(opened.get("contract_size"))
        entry_commission = _number(opened.get("entry_commission"))
        if (
            opened.get("cashflow_schema_version") != TRADE_CASHFLOW_SCHEMA_VERSION
            or opened.get("fill_cost_provenance_schema_version")
            != FILL_COST_PROVENANCE_SCHEMA_VERSION
            or direction not in {-1.0, 1.0}
            or entry_lots is None
            or entry_lots <= 0.0
            or contract_size is None
            or contract_size <= 0.0
            or entry_commission is None
        ):
            return _unavailable(
                "completed_position_open_cost_evidence_missing",
                fill_count=len(fills),
                open_position_count=open_position_count,
            )
        entry_pre_bid = _number(opened.get("pre_execution_quote_bid"))
        entry_pre_ask = _number(opened.get("pre_execution_quote_ask"))
        entry_broker_bid = _number(opened.get("broker_execution_quote_bid"))
        entry_broker_ask = _number(opened.get("broker_execution_quote_ask"))
        entry_slippage = _number(opened.get("slippage_points_applied_here"))
        entry_mode = opened.get("slippage_application_mode")
        if (
            entry_pre_bid is None
            or entry_pre_ask is None
            or entry_pre_ask < entry_pre_bid
            or entry_broker_bid is None
            or entry_broker_ask is None
            or entry_broker_ask < entry_broker_bid
            or entry_slippage is None
            or entry_slippage < 0.0
            or entry_mode not in {"none", "transacted_side", "quote_level_shift"}
        ):
            return _unavailable(
                "completed_position_open_quote_evidence_invalid",
                fill_count=len(fills),
                open_position_count=open_position_count,
            )
        entry_fill_price = _number(opened.get("price"))
        entry_commission_rate = _number(opened.get("commission_per_lot"))
        entry_slippage_applied = _boolean(opened.get("slippage_applied_here"))
        entry_side = entry_broker_ask if direction == 1.0 else entry_broker_bid
        if (
            entry_fill_price is None
            or entry_commission_rate is None
            or entry_commission_rate < 0.0
            or entry_side is None
            or entry_broker_bid is None
            or entry_broker_ask is None
            or entry_slippage_applied is None
            or not math.isclose(entry_fill_price, entry_side, rel_tol=tolerance, abs_tol=tolerance)
            or not _quote_matches(
                entry_broker_bid,
                entry_broker_ask,
                entry_pre_bid,
                entry_pre_ask,
                direction,
                entry_slippage,
                opening=True,
                mode=str(entry_mode),
                tolerance=tolerance,
            )
            or entry_slippage_applied != (entry_slippage > 0.0)
            or (entry_mode == "none") != (entry_slippage == 0.0)
            or not math.isclose(
                entry_commission,
                entry_commission_rate * entry_lots,
                rel_tol=tolerance,
                abs_tol=tolerance,
            )
        ):
            return _unavailable(
                "completed_position_open_execution_or_commission_does_not_reconcile",
                fill_count=len(fills),
                open_position_count=open_position_count,
            )
        entry_mid = (entry_pre_bid + entry_pre_ask) / 2.0
        closed_size = 0.0
        position_totals = {name: 0.0 for name in totals}
        used_fills += 1
        for close_index, close in enumerate(closes):
            close_size = _number(close.get("size"))
            close_contract_size = _number(close.get("contract_size"))
            close_direction = _number(close.get("direction"))
            gross_executed = _number(close.get("gross_price_pnl"))
            entry_allocated = _number(close.get("entry_commission_allocated"))
            exit_commission = _number(close.get("exit_commission"))
            net_pnl = _number(close.get("net_pnl"))
            close_complete = _boolean(close.get("position_complete"))
            close_entry_price = _number(close.get("entry_price"))
            close_commission_rate = _number(close.get("commission_per_lot"))
            pre_bid = _number(close.get("pre_execution_quote_bid"))
            pre_ask = _number(close.get("pre_execution_quote_ask"))
            broker_bid = _number(close.get("broker_execution_quote_bid"))
            broker_ask = _number(close.get("broker_execution_quote_ask"))
            exit_price = _number(close.get("price"))
            slippage = _number(close.get("slippage_points_applied_here"))
            slippage_applied = _boolean(close.get("slippage_applied_here"))
            close_mode = close.get("slippage_application_mode")
            if (
                close.get("cashflow_schema_version") != TRADE_CASHFLOW_SCHEMA_VERSION
                or close.get("fill_cost_provenance_schema_version")
                != FILL_COST_PROVENANCE_SCHEMA_VERSION
                or close_direction != direction
                or close_contract_size != contract_size
                or close_size is None
                or close_size <= 0.0
                or gross_executed is None
                or entry_allocated is None
                or exit_commission is None
                or net_pnl is None
                or close_entry_price is None
                or close_commission_rate is None
                or close_commission_rate < 0.0
                or close_complete is None
                or close_complete is not (close_index == len(closes) - 1)
                or pre_bid is None
                or pre_ask is None
                or pre_ask < pre_bid
                or broker_bid is None
                or broker_ask is None
                or broker_ask < broker_bid
                or exit_price is None
                or slippage is None
                or slippage < 0.0
                or slippage_applied is None
                or close_mode not in {"none", "transacted_side", "quote_level_shift"}
            ):
                return _unavailable(
                    "completed_position_close_cost_evidence_missing_or_invalid",
                    fill_count=len(fills),
                    open_position_count=open_position_count,
                )
            exit_side = broker_bid if direction == 1.0 else broker_ask
            expected_gross = (
                direction * (exit_price - entry_fill_price) * close_size * contract_size
            )
            expected_commission = entry_commission_rate * close_size
            if (
                not math.isclose(exit_price, exit_side, rel_tol=tolerance, abs_tol=tolerance)
                or not _quote_matches(
                    broker_bid,
                    broker_ask,
                    pre_bid,
                    pre_ask,
                    direction,
                    slippage,
                    opening=False,
                    mode=str(close_mode),
                    tolerance=tolerance,
                )
                or slippage_applied != (slippage > 0.0)
                or (close_mode == "none") != (slippage == 0.0)
                or not math.isclose(
                    close_entry_price,
                    entry_fill_price,
                    rel_tol=tolerance,
                    abs_tol=tolerance,
                )
                or not math.isclose(
                    close_commission_rate,
                    entry_commission_rate,
                    rel_tol=tolerance,
                    abs_tol=tolerance,
                )
                or not math.isclose(
                    gross_executed,
                    expected_gross,
                    rel_tol=tolerance,
                    abs_tol=tolerance,
                )
                or not math.isclose(
                    entry_allocated,
                    expected_commission,
                    rel_tol=tolerance,
                    abs_tol=tolerance,
                )
                or not math.isclose(
                    exit_commission,
                    expected_commission,
                    rel_tol=tolerance,
                    abs_tol=tolerance,
                )
                or not math.isclose(
                    net_pnl,
                    gross_executed - entry_allocated - exit_commission,
                    rel_tol=tolerance,
                    abs_tol=tolerance,
                )
            ):
                return _unavailable(
                    "completed_position_close_execution_quote_does_not_reconcile",
                    fill_count=len(fills),
                    open_position_count=open_position_count,
                )
            fill_mid = (pre_bid + pre_ask) / 2.0
            position_totals["gross_midpoint_pnl"] += (
                direction * (fill_mid - entry_mid) * close_size * contract_size
            )
            position_totals["gross_executed_price_pnl"] += gross_executed
            position_totals["spread_cost"] += (pre_ask - pre_bid) / 2.0 * close_size * contract_size
            position_totals["spread_cost"] += (
                (entry_pre_ask - entry_pre_bid) / 2.0 * close_size * contract_size
            )
            position_totals["slippage_cost"] += slippage * close_size * contract_size
            position_totals["slippage_cost"] += entry_slippage * close_size * contract_size
            position_totals["commission_cost"] += entry_allocated + exit_commission
            position_totals["net_pnl"] += net_pnl
            closed_size += close_size
            used_fills += 1
        if not math.isclose(closed_size, entry_lots, rel_tol=tolerance, abs_tol=tolerance):
            return _unavailable(
                "completed_position_size_does_not_match_open_size",
                fill_count=len(fills),
                open_position_count=open_position_count,
            )
        completed_position_count += 1
        for name, value in position_totals.items():
            totals[name] += value

    if completed_position_count == 0:
        result = _unavailable(
            "no_completed_positions",
            fill_count=len(fills),
            open_position_count=open_position_count,
        )
        result["status"] = "no_completed_positions"
        return result

    residual = (
        totals["gross_midpoint_pnl"]
        - totals["spread_cost"]
        - totals["slippage_cost"]
        - totals["commission_cost"]
        - totals["net_pnl"]
    )
    status = (
        "matched"
        if math.isclose(residual, 0.0, rel_tol=tolerance, abs_tol=tolerance)
        else "mismatch"
    )
    return {
        "schema_version": COST_DECOMPOSITION_SCHEMA_VERSION,
        "status": status,
        "availability_reason": (
            None if status == "matched" else "cost_identity_does_not_reconcile"
        ),
        "completed_position_count": completed_position_count,
        "open_position_count": open_position_count,
        "fill_count": used_fills,
        **totals,
        "reconciliation_residual": residual,
    }


__all__ = ["COST_DECOMPOSITION_SCHEMA_VERSION", "decompose_fill_costs"]
