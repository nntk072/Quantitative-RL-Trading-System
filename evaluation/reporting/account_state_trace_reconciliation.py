"""Independent arithmetic checks for versioned account-state traces."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

import pandas as pd

from trading.execution import (
    FILL_COST_PROVENANCE_SCHEMA_VERSION,
    TRADE_CASHFLOW_SCHEMA_VERSION,
)
from trading.risk import RISK_BREACH_EVENT_SCHEMA_V1
from trading.risk.ftmo_clock import ftmo_trading_day

ACCOUNT_STATE_RECONCILIATION_SCHEMA = "account_state_reconciliation.v2"
_TRACE_SCHEMA = "account_state_trace.v2"
_TRADE_CASHFLOW_SCHEMA = TRADE_CASHFLOW_SCHEMA_VERSION
_CLOSE_TYPES = frozenset(
    {"close", "stop_close", "tp_close", "forced_close", "eod_close", "tp_partial_close"}
)
_NON_CASH_EVENT_TYPES = frozenset(
    {
        "cycle_failure",
        "order_cancel",
        "order_fill",
        "order_submit",
        "reject",
        "sl_update",
        "tp_update",
    }
)
_REQUIRED_TRACE_COLUMNS = frozenset(
    {
        "schema_version",
        "state_phase",
        "decision_time",
        "session_id",
        "initial_balance",
        "balance",
        "equity",
        "open_pnl",
        "session_start_balance",
        "session_start_equity",
        "daily_pnl_basis",
        "daily_loss",
        "daily_loss_limit_usd",
        "daily_floor_equity",
        "max_loss_limit_usd",
        "max_loss_floor_equity",
        "max_drawdown_mode",
        "max_drawdown_from_reference_usd",
        "loss_from_initial_usd",
        "max_drawdown_usd",
        "peak_equity",
        "peak_eod_equity",
        "peak_eod_drawdown_usd",
        "max_peak_eod_drawdown_usd",
        "payout_drawdown_floor",
        "trailing_drawdown_usd",
        "position_direction",
        "position_size",
        "position_entry_price",
        "position_mark_price",
        "contract_size",
        "trade_event_count",
        "cumulative_payouts",
        "total_economic_value",
        "valuation_time",
    }
)


def _number(value: Any) -> float | None:
    """Parse a finite numeric cell, returning ``None`` for invalid values.

    Args:
        value: Raw account or event field.

    Returns:
        Finite float, or ``None`` for invalid input.
    """
    if isinstance(value, bool) or (
        type(value).__module__ == "numpy" and type(value).__name__ in {"bool", "bool_"}
    ):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return parsed if math.isfinite(parsed) else None


def _close(actual: Any, expected: float, tolerance: float) -> bool:
    """Compare a trace cell with a recomputed value under one tolerance.

    Args:
        actual: Recorded trace value.
        expected: Recomputed value from account and event history.
        tolerance: Relative and absolute comparison tolerance.

    Returns:
        Whether the recorded value matches the recomputed value.
    """
    value = _number(actual)
    return value is not None and math.isclose(value, expected, rel_tol=tolerance, abs_tol=tolerance)


def _expected_execution_quote(
    bid: float,
    ask: float,
    direction: int,
    slippage: float,
    *,
    opening: bool,
    mode: str,
) -> tuple[float, float]:
    """Apply the recorded adverse adjustment to an executable quote.

    Args:
        bid: Reference bid before execution adjustment.
        ask: Reference ask before execution adjustment.
        direction: Trade direction, positive for long and negative for short.
        slippage: Adverse adjustment in price units.
        opening: Whether this is an entry fill.
        mode: Recorded slippage application mode.

    Returns:
        Adjusted bid and ask quote.
    """
    if mode == "none":
        return bid, ask
    if mode == "quote_level_shift":
        shift = slippage if (direction == 1 if opening else direction == -1) else -slippage
        return bid + shift, ask + shift
    if opening:
        return (bid, ask + slippage) if direction == 1 else (bid - slippage, ask)
    return (bid - slippage, ask) if direction == 1 else (bid, ask + slippage)


def reconcile_account_state_trace(
    trace: pd.DataFrame,
    trade_events: pd.DataFrame,
    *,
    tolerance: float = 1e-7,
    breach_events: pd.DataFrame | list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Recompute account and risk identities from snapshots and event prefixes.

    ``trade_event_count`` identifies the exact prefix visible at each snapshot,
    preserving the distinct pre-action and post-action valuation phases.
    Historical or custom traces without the v2 event and mark fields are reported
    as incomplete; missing evidence is never treated as a passing zero.

    Args:
        trace: Versioned account-state snapshots to recompute.
        trade_events: Ordered trade and execution event ledger.
        tolerance: Positive tolerance for numeric identity comparisons.
        breach_events: Optional risk-breach events aligned to the same timeline.

    Returns:
        Reconciliation status, arithmetic checks, and any incomplete or failed rows.
    """
    result: dict[str, Any] = {
        "schema_version": ACCOUNT_STATE_RECONCILIATION_SCHEMA,
        "status": "unavailable",
        "trace_schema": None,
        "trace_rows": int(len(trace)),
        "trade_event_rows": int(len(trade_events)),
        "breach_event_rows": 0 if breach_events is None else int(len(breach_events)),
        "phase_counts": {},
        "checks": {},
        "failure_count": 0,
        "failures": [],
        "incomplete_reasons": [],
        "fill_cost_provenance": {
            "schema_version": FILL_COST_PROVENANCE_SCHEMA_VERSION,
            "fill_rows": 0,
            "verified_rows": 0,
            "missing_rows": 0,
            "status": "unavailable",
        },
    }
    if trace.empty:
        result["incomplete_reasons"].append("account_state_trace_is_empty")
        result["status"] = "incomplete"
        return result

    phases: dict[str, int] = (
        {
            str(key): int(value)
            for key, value in trace["state_phase"]
            .dropna()
            .astype(str)
            .value_counts()
            .sort_index()
            .to_dict()
            .items()
        }
        if "state_phase" in trace.columns
        else {}
    )
    result["phase_counts"] = phases
    schemas = (
        sorted(trace["schema_version"].dropna().astype(str).unique().tolist())
        if "schema_version" in trace.columns
        else []
    )
    result["trace_schema"] = schemas[0] if len(schemas) == 1 else schemas
    missing = sorted(_REQUIRED_TRACE_COLUMNS - set(trace.columns))
    if schemas != [_TRACE_SCHEMA]:
        result["incomplete_reasons"].append("unsupported_or_mixed_trace_schema")
    if missing:
        result["incomplete_reasons"].append("missing_required_columns")
        result["missing_columns"] = missing
    if result["incomplete_reasons"]:
        result["status"] = "incomplete"
        return result
    invalid_phases = sorted(set(phases) - {"pre_action_valuation", "post_action_valuation"})
    if invalid_phases:
        result["incomplete_reasons"].append("unknown_state_phase")
        result["invalid_phases"] = invalid_phases
    if trace["state_phase"].isna().any():
        result["incomplete_reasons"].append("state_phase_is_missing")
    if trace["session_id"].isna().any():
        result["incomplete_reasons"].append("session_identity_is_missing")
    if result["incomplete_reasons"]:
        result["status"] = "incomplete"
        return result
    if tolerance <= 0.0 or not math.isfinite(tolerance):
        raise ValueError("tolerance must be finite and positive")

    checks: dict[str, int] = {}
    failures: list[dict[str, Any]] = []

    def check(row_index: Any, name: str, actual: Any, expected: float) -> None:
        """Count one recomputation and retain any numeric discrepancy.

        Args:
            row_index: Snapshot row associated with the recomputation.
            name: Stable identity name for the arithmetic check.
            actual: Value recorded in the snapshot.
            expected: Value recomputed from the event prefix.
        """
        checks[name] = checks.get(name, 0) + 1
        condition_matches = (
            actual is (expected == 1.0)
            if isinstance(actual, bool) and expected in {0.0, 1.0}
            else None
        )
        if condition_matches is not True and not _close(actual, expected, tolerance):
            failures.append(
                {
                    "row_index": str(row_index),
                    "check": name,
                    "actual": _number(actual),
                    "expected": expected,
                }
            )

    cash = _number(trace.iloc[0]["initial_balance"])
    if cash is None:
        result["status"] = "incomplete"
        result["incomplete_reasons"].append("initial_balance_is_not_finite")
        return result
    initial_balance_reference = cash
    cumulative_payouts = 0.0
    legacy_daily_loss = 0.0
    previous_event_count = 0
    previous_session: Any = object()
    previous_ftmo_day: object | None = None
    expected_session_start_balance: float | None = None
    expected_session_start_equity: float | None = None
    payout_replay_complete = True
    payout_seen = False
    cash_replay_complete = True
    trade_cashflow_replay_complete = True
    fill_cost_provenance_verified = 0
    fill_cost_provenance_missing = 0
    position_cashflows: dict[str, dict[str, float]] = {}
    prior_peak_equity: float | None = None
    prior_peak_eod_equity: float | None = None
    prior_max_drawdown: float | None = None
    prior_max_eod_drawdown: float | None = None
    prior_valuation_time: pd.Timestamp | None = None
    prior_balance: float | None = None
    prior_equity: float | None = None

    for row_index, row in trace.iterrows():
        session = row["session_id"] if "session_id" in trace.columns else None
        valuation_time = pd.to_datetime(row["valuation_time"], utc=True, errors="coerce")
        if pd.isna(valuation_time):
            result["incomplete_reasons"].append("valuation_time_is_invalid")
        elif prior_valuation_time is not None:
            check(
                row_index,
                "valuation_time_is_monotonic",
                valuation_time >= prior_valuation_time,
                1.0,
            )
        if not pd.isna(valuation_time):
            prior_valuation_time = valuation_time

        basis_at_row = str(row["daily_pnl_basis"])
        if basis_at_row == "ftmo_midnight_balance" and not pd.isna(valuation_time):
            ftmo_day = ftmo_trading_day(valuation_time)
            anchor_changed = ftmo_day != previous_ftmo_day
            previous_ftmo_day = ftmo_day
        else:
            anchor_changed = session != previous_session
        if anchor_changed:
            legacy_daily_loss = 0.0
            expected_session_start_balance = (
                initial_balance_reference if prior_balance is None else prior_balance
            )
            expected_session_start_equity = (
                initial_balance_reference if prior_equity is None else prior_equity
            )
        previous_session = session
        payout_reset_balance: float | None = None

        raw_count = _number(row["trade_event_count"])
        if (
            raw_count is None
            or not raw_count.is_integer()
            or raw_count < previous_event_count
            or raw_count > len(trade_events)
        ):
            result["incomplete_reasons"].append("invalid_trade_event_prefix")
            break
        event_count = int(raw_count)
        for event in trade_events.iloc[previous_event_count:event_count].to_dict("records"):
            event_type = str(event.get("type", ""))
            if event_type == "open" or event_type in _CLOSE_TYPES:
                result["fill_cost_provenance"]["fill_rows"] += 1
                if event.get("fill_cost_provenance_schema_version") is None:
                    fill_cost_provenance_missing += 1
                elif (
                    event.get("fill_cost_provenance_schema_version")
                    != FILL_COST_PROVENANCE_SCHEMA_VERSION
                ):
                    result["incomplete_reasons"].append("unsupported_fill_cost_provenance_schema")
                else:
                    pre_bid = _number(event.get("pre_execution_quote_bid"))
                    pre_ask = _number(event.get("pre_execution_quote_ask"))
                    broker_bid = _number(event.get("broker_execution_quote_bid"))
                    broker_ask = _number(event.get("broker_execution_quote_ask"))
                    direction = _number(event.get("direction"))
                    fill_price = _number(event.get("price"))
                    slip = _number(event.get("slippage_points_applied_here"))
                    applied = event.get("slippage_applied_here")
                    mode = event.get("slippage_application_mode")
                    if (
                        pre_bid is None
                        or pre_ask is None
                        or broker_bid is None
                        or broker_ask is None
                        or direction not in {-1.0, 1.0}
                        or fill_price is None
                        or slip is None
                        or slip < 0.0
                        or not (
                            isinstance(applied, bool)
                            or (
                                type(applied).__module__ == "numpy"
                                and type(applied).__name__ in {"bool", "bool_"}
                            )
                        )
                        or mode not in {"none", "transacted_side", "quote_level_shift"}
                        or pre_ask < pre_bid
                        or broker_ask < broker_bid
                        or (not applied and slip != 0.0)
                        or bool(applied) != (slip > 0.0)
                        or (mode == "none") != (slip == 0.0)
                    ):
                        result["incomplete_reasons"].append("invalid_fill_cost_provenance_fields")
                    else:
                        expected_bid, expected_ask = _expected_execution_quote(
                            pre_bid,
                            pre_ask,
                            int(direction),
                            slip,
                            opening=event_type == "open",
                            mode=str(mode),
                        )
                        check(
                            event.get("fill_id", event.get("position_id")),
                            "broker_quote_bid_matches_slippage_application",
                            broker_bid,
                            expected_bid,
                        )
                        check(
                            event.get("fill_id", event.get("position_id")),
                            "broker_quote_ask_matches_slippage_application",
                            broker_ask,
                            expected_ask,
                        )
                        fill_side_quote = (
                            broker_ask
                            if (event_type == "open") == (int(direction) == 1)
                            else broker_bid
                        )
                        check(
                            event.get("fill_id", event.get("position_id")),
                            "fill_price_matches_broker_quote_side",
                            fill_price,
                            fill_side_quote,
                        )
                        fill_cost_provenance_verified += 1
            if event_type == "open":
                charge = _number(event.get("entry_commission"))
                if charge is None:
                    cash_replay_complete = False
                else:
                    cash -= charge
                position_id = event.get("position_id")
                direction = _number(event.get("direction"))
                entry_price = _number(event.get("price"))
                lots = _number(event.get("lots"))
                contract_size = _number(event.get("contract_size"))
                commission_per_lot = _number(event.get("commission_per_lot"))
                if (
                    event.get("cashflow_schema_version") != _TRADE_CASHFLOW_SCHEMA
                    or not isinstance(position_id, str)
                    or not position_id
                    or direction not in {-1, 1}
                    or entry_price is None
                    or lots is None
                    or lots <= 0.0
                    or contract_size is None
                    or contract_size <= 0.0
                    or commission_per_lot is None
                    or commission_per_lot < 0.0
                    or charge is None
                ):
                    trade_cashflow_replay_complete = False
                else:
                    check(
                        row_index,
                        "entry_commission_matches_size_and_rate",
                        charge,
                        commission_per_lot * lots,
                    )
                    if position_id in position_cashflows:
                        trade_cashflow_replay_complete = False
                    else:
                        position_cashflows[position_id] = {
                            "direction": direction,
                            "entry_price": entry_price,
                            "lots": lots,
                            "contract_size": contract_size,
                            "commission_per_lot": commission_per_lot,
                            "closed_size": 0.0,
                            "net_pnl": 0.0,
                        }
            elif event_type in _CLOSE_TYPES:
                pnl = _number(event.get("pnl"))
                if pnl is None:
                    cash_replay_complete = False
                else:
                    cash += pnl
                    if pnl < 0.0:
                        legacy_daily_loss += -pnl
                position_id = event.get("position_id")
                original = position_cashflows.get(str(position_id))
                exit_price = _number(event.get("price"))
                size = _number(event.get("size"))
                gross_price_pnl = _number(event.get("gross_price_pnl"))
                exit_commission = _number(event.get("exit_commission"))
                entry_commission_allocated = _number(event.get("entry_commission_allocated"))
                net_pnl = _number(event.get("net_pnl"))
                direction = _number(event.get("direction"))
                entry_price = _number(event.get("entry_price"))
                contract_size = _number(event.get("contract_size"))
                commission_per_lot = _number(event.get("commission_per_lot"))
                raw_position_complete = event.get("position_complete")
                if isinstance(raw_position_complete, bool):
                    position_complete: bool | None = raw_position_complete
                elif type(raw_position_complete).__module__ == "numpy" and type(
                    raw_position_complete
                ).__name__ in {"bool", "bool_"}:
                    position_complete = bool(raw_position_complete)
                else:
                    position_complete = None
                if (
                    event.get("cashflow_schema_version") != _TRADE_CASHFLOW_SCHEMA
                    or original is None
                    or pnl is None
                    or exit_price is None
                    or size is None
                    or size <= 0.0
                    or gross_price_pnl is None
                    or exit_commission is None
                    or entry_commission_allocated is None
                    or net_pnl is None
                    or direction not in {-1, 1}
                    or entry_price is None
                    or contract_size is None
                    or commission_per_lot is None
                    or position_complete is None
                ):
                    trade_cashflow_replay_complete = False
                else:
                    expected_gross = (
                        (exit_price - original["entry_price"])
                        * original["direction"]
                        * size
                        * original["contract_size"]
                    )
                    expected_exit_commission = original["commission_per_lot"] * size
                    expected_entry_allocation = original["commission_per_lot"] * size
                    check(
                        row_index, "close_direction_matches_open", direction, original["direction"]
                    )
                    check(
                        row_index,
                        "close_entry_price_matches_open",
                        entry_price,
                        original["entry_price"],
                    )
                    check(
                        row_index,
                        "close_contract_size_matches_open",
                        contract_size,
                        original["contract_size"],
                    )
                    check(
                        row_index,
                        "close_commission_rate_matches_open",
                        commission_per_lot,
                        original["commission_per_lot"],
                    )
                    check(
                        row_index,
                        "gross_close_pnl_matches_executable_fills",
                        gross_price_pnl,
                        expected_gross,
                    )
                    check(
                        row_index,
                        "exit_commission_matches_size_and_rate",
                        exit_commission,
                        expected_exit_commission,
                    )
                    check(
                        row_index,
                        "close_pnl_matches_gross_less_exit_commission",
                        pnl,
                        expected_gross - expected_exit_commission,
                    )
                    check(
                        row_index,
                        "entry_commission_allocation_matches_closed_size",
                        entry_commission_allocated,
                        expected_entry_allocation,
                    )
                    check(
                        row_index,
                        "net_fill_pnl_matches_entry_and_exit_costs",
                        net_pnl,
                        expected_gross - expected_exit_commission - expected_entry_allocation,
                    )
                    original["closed_size"] += size
                    original["net_pnl"] += net_pnl
                    check(
                        row_index,
                        "position_close_size_does_not_exceed_open_size",
                        original["closed_size"] <= original["lots"] + tolerance,
                        1.0,
                    )
                    if position_complete:
                        check(
                            row_index,
                            "completed_position_closes_full_open_size",
                            original["closed_size"],
                            original["lots"],
                        )
                        check(
                            row_index,
                            "position_net_pnl_matches_fill_sum",
                            event.get("position_net_pnl"),
                            original["net_pnl"],
                        )
                    else:
                        check(
                            row_index,
                            "open_position_retains_unclosed_size",
                            original["closed_size"] < original["lots"] - tolerance,
                            1.0,
                        )
            elif event_type == "payout_reset":
                payout = _number(event.get("payout"))
                operating_balance = _number(event.get("operating_balance"))
                balance_before = _number(event.get("balance_before_reset"))
                if payout is None or operating_balance is None or balance_before is None:
                    payout_replay_complete = False
                    cash_replay_complete = False
                else:
                    payout_schema = str(event.get("payout_schema_version", "payout_reset.v1"))
                    post_reset_balance = _number(event.get("balance_after_reset"))
                    if payout_schema == "payout_reset.v2":
                        mode = str(event.get("max_drawdown_mode", ""))
                        fraction = _number(event.get("payout_fraction"))
                        retained_profit = _number(event.get("retained_profit"))
                        reported_profit = _number(event.get("profit_above_operating_balance"))
                        expected_fraction = 1.0 if mode == "static" else 0.5
                        if mode not in {"static", "eod", "intraday_trailing"}:
                            payout_replay_complete = False
                            cash_replay_complete = False
                            result["incomplete_reasons"].append("unsupported_payout_drawdown_mode")
                        else:
                            check(
                                row_index,
                                "payout_mode_matches_account_trace",
                                mode == str(row["max_drawdown_mode"]),
                                1.0,
                            )
                        if fraction is None or retained_profit is None or reported_profit is None:
                            payout_replay_complete = False
                            cash_replay_complete = False
                            result["incomplete_reasons"].append("payout_v2_fields_missing")
                        else:
                            check(
                                row_index,
                                "payout_fraction_matches_drawdown_mode",
                                fraction,
                                expected_fraction,
                            )
                            check(
                                row_index,
                                "payout_profit_matches_balance_before_reset",
                                reported_profit,
                                balance_before - operating_balance,
                            )
                            check(
                                row_index,
                                "payout_retained_profit_matches_fraction",
                                retained_profit,
                                reported_profit * (1.0 - expected_fraction),
                            )
                            check(
                                row_index,
                                "payout_amount_matches_fraction",
                                payout,
                                reported_profit * expected_fraction,
                            )
                        if post_reset_balance is None:
                            payout_replay_complete = False
                            cash_replay_complete = False
                            result["incomplete_reasons"].append("payout_post_reset_balance_missing")
                    elif payout_schema != "payout_reset.v1":
                        payout_replay_complete = False
                        cash_replay_complete = False
                        result["incomplete_reasons"].append("unsupported_payout_schema")
                    check(row_index, "payout_is_positive", payout > 0.0, 1.0)
                    check(
                        row_index,
                        "payout_operating_balance_matches_initial",
                        operating_balance,
                        initial_balance_reference,
                    )
                    check(
                        row_index,
                        "payout_balance_exceeds_initial_operating_balance",
                        balance_before > initial_balance_reference,
                        1.0,
                    )
                    if payout_schema == "payout_reset.v1":
                        check(
                            row_index,
                            "payout_resets_to_initial_operating_balance",
                            operating_balance,
                            initial_balance_reference,
                        )
                    checks["payout_event_balance_identity"] = (
                        checks.get("payout_event_balance_identity", 0) + 1
                    )
                    checks["payout_event_matches_replayed_balance"] = (
                        checks.get("payout_event_matches_replayed_balance", 0) + 1
                    )
                    if not math.isclose(
                        balance_before,
                        cash,
                        rel_tol=tolerance,
                        abs_tol=tolerance,
                    ):
                        failures.append(
                            {
                                "row_index": str(row_index),
                                "check": "payout_event_matches_replayed_balance",
                                "actual": balance_before,
                                "expected": cash,
                            }
                        )
                    expected_post_reset = (
                        operating_balance
                        if payout_schema == "payout_reset.v1"
                        else post_reset_balance
                    )
                    if expected_post_reset is None or not math.isclose(
                        balance_before - payout,
                        expected_post_reset,
                        rel_tol=tolerance,
                        abs_tol=tolerance,
                    ):
                        failures.append(
                            {
                                "row_index": str(row_index),
                                "check": "payout_event_balance_identity",
                                "actual": balance_before - payout,
                                "expected": expected_post_reset,
                            }
                        )
                    cash = float(
                        operating_balance if expected_post_reset is None else expected_post_reset
                    )
                    cumulative_payouts += payout
                    legacy_daily_loss = 0.0
                    payout_reset_balance = cash
                    payout_seen = True
            elif event_type not in _NON_CASH_EVENT_TYPES:
                cash_replay_complete = False
                result["incomplete_reasons"].append("unsupported_trade_event_type_for_cash_replay")
        previous_event_count = event_count

        if payout_seen:
            max_drawdown_mode = str(row["max_drawdown_mode"])
            check(
                row_index,
                (
                    "payout_drawdown_floor_is_unset_after_static_reset"
                    if max_drawdown_mode == "static"
                    else "payout_drawdown_floor_matches_initial_after_reset"
                ),
                (
                    _number(row["payout_drawdown_floor"]) is None
                    if max_drawdown_mode == "static"
                    else row["payout_drawdown_floor"]
                ),
                1.0 if max_drawdown_mode == "static" else initial_balance_reference,
            )
        else:
            check(
                row_index,
                "payout_drawdown_floor_is_unset_before_payout",
                _number(row["payout_drawdown_floor"]) is None,
                1.0,
            )

        if payout_reset_balance is not None:
            expected_session_start_balance = payout_reset_balance
            expected_session_start_equity = payout_reset_balance
        if expected_session_start_balance is None or expected_session_start_equity is None:
            result["incomplete_reasons"].append("daily_risk_anchor_is_not_finite")
        else:
            check(
                row_index,
                "daily_risk_anchor_matches_session_or_payout_reset",
                row["session_start_balance"],
                expected_session_start_balance,
            )
            check(
                row_index,
                "daily_risk_equity_anchor_matches_session_or_payout_reset",
                row["session_start_equity"],
                expected_session_start_equity,
            )

        initial = _number(row["initial_balance"])
        balance = _number(row["balance"])
        equity = _number(row["equity"])
        open_pnl = _number(row["open_pnl"])
        if initial is None or balance is None or equity is None or open_pnl is None:
            result["incomplete_reasons"].append("non_finite_account_amount")
            continue
        check(
            row_index,
            "initial_balance_remains_constant",
            initial,
            initial_balance_reference,
        )
        expected_loss_from_initial = max(0.0, initial - equity)
        check(
            row_index,
            "loss_from_initial_matches_equity",
            row["loss_from_initial_usd"],
            expected_loss_from_initial,
        )
        observed_max_drawdown = _number(row["max_drawdown_usd"])
        if observed_max_drawdown is None:
            result["incomplete_reasons"].append("maximum_drawdown_is_not_finite")
        else:
            check(
                row_index,
                "maximum_drawdown_covers_current_loss",
                observed_max_drawdown + tolerance >= expected_loss_from_initial,
                1.0,
            )
            if prior_max_drawdown is not None:
                check(
                    row_index,
                    "maximum_drawdown_is_monotonic",
                    observed_max_drawdown >= prior_max_drawdown,
                    1.0,
                )
            prior_max_drawdown = observed_max_drawdown

        observed_peak_equity = _number(row["peak_equity"])
        if observed_peak_equity is None:
            result["incomplete_reasons"].append("peak_equity_is_not_finite")
        else:
            check(
                row_index,
                "peak_equity_covers_current_equity",
                observed_peak_equity >= equity,
                1.0,
            )
            if prior_peak_equity is not None:
                check(
                    row_index,
                    "peak_equity_is_monotonic",
                    observed_peak_equity >= prior_peak_equity,
                    1.0,
                )
            prior_peak_equity = observed_peak_equity

        check(row_index, "balance_plus_open_pnl_equals_equity", equity, balance + open_pnl)
        prior_balance = balance
        prior_equity = equity
        if cash_replay_complete:
            check(row_index, "event_cashflows_reconstruct_balance", balance, cash)

        raw_direction = _number(row["position_direction"])
        direction = (
            int(raw_direction) if raw_direction is not None and raw_direction.is_integer() else None
        )
        size = _number(row["position_size"])
        if direction == 0:
            check(row_index, "flat_position_has_zero_open_pnl", open_pnl, 0.0)
        elif direction in (-1, 1) and size is not None:
            entry = _number(row["position_entry_price"])
            mark = _number(row["position_mark_price"])
            contract_size = _number(row["contract_size"])
            if entry is None or mark is None or contract_size is None:
                result["incomplete_reasons"].append("open_position_mark_price_missing")
            else:
                expected_open_pnl = (mark - entry) * direction * size * contract_size
                check(row_index, "position_mark_reconstructs_open_pnl", open_pnl, expected_open_pnl)
        else:
            result["incomplete_reasons"].append("invalid_position_state")

        check(
            row_index,
            "equity_plus_payouts_equals_economic_value",
            row["total_economic_value"],
            equity + float(row["cumulative_payouts"]),
        )
        if payout_replay_complete:
            check(
                row_index,
                "payout_events_reconstruct_cumulative_payouts",
                row["cumulative_payouts"],
                cumulative_payouts,
            )

        observed_peak_eod = _number(row["peak_eod_equity"])
        observed_eod_drawdown = _number(row["peak_eod_drawdown_usd"])
        observed_max_eod_drawdown = _number(row["max_peak_eod_drawdown_usd"])
        if (
            observed_peak_eod is None
            or observed_eod_drawdown is None
            or observed_max_eod_drawdown is None
        ):
            result["incomplete_reasons"].append("eod_drawdown_fields_are_not_finite")
        else:
            check(
                row_index,
                "eod_peak_covers_initial_equity",
                observed_peak_eod >= initial_balance_reference,
                1.0,
            )
            check(
                row_index,
                "eod_drawdown_matches_peak_and_equity",
                observed_eod_drawdown,
                max(0.0, observed_peak_eod - equity),
            )
            if prior_peak_eod_equity is not None:
                check(
                    row_index,
                    "eod_peak_is_monotonic",
                    observed_peak_eod >= prior_peak_eod_equity,
                    1.0,
                )
            if prior_max_eod_drawdown is not None:
                check(
                    row_index,
                    "maximum_eod_drawdown_is_monotonic",
                    observed_max_eod_drawdown >= prior_max_eod_drawdown,
                    1.0,
                )
        session_start_equity = _number(row["session_start_equity"])
        session_start_balance = _number(row["session_start_balance"])
        basis = str(row["daily_pnl_basis"])
        daily_anchor = (
            session_start_balance if basis == "ftmo_midnight_balance" else session_start_equity
        )
        daily_limit = _number(row["daily_loss_limit_usd"])
        daily_floor = _number(row["daily_floor_equity"])
        if daily_anchor is None or daily_limit is None or daily_floor is None:
            result["incomplete_reasons"].append("daily_risk_fields_missing")
        else:
            check(
                row_index,
                "daily_floor_matches_anchor_and_limit",
                daily_floor,
                daily_anchor - daily_limit,
            )
            basis = str(row["daily_pnl_basis"])
            observed_daily_loss = _number(row["daily_loss"])
            if observed_daily_loss is None:
                result["incomplete_reasons"].append("daily_loss_is_not_finite")
            elif basis == "ftmo_midnight_balance":
                expected_daily_loss = max(0.0, daily_anchor - equity)
                check(
                    row_index,
                    "ftmo_midnight_daily_loss_matches_equity",
                    observed_daily_loss,
                    expected_daily_loss,
                )
            elif basis == "session_net_equity":
                expected_daily_loss = max(0.0, daily_anchor - equity)
                check(
                    row_index,
                    "session_net_daily_loss_matches_equity",
                    observed_daily_loss,
                    expected_daily_loss,
                )
            elif (
                basis == "legacy_gross_closed_losses"
                and cash_replay_complete
                and observed_daily_loss is not None
            ):
                check(
                    row_index,
                    "legacy_daily_loss_matches_close_events",
                    observed_daily_loss,
                    legacy_daily_loss,
                )
            elif basis not in {
                "legacy_gross_closed_losses",
                "session_net_equity",
                "ftmo_midnight_balance",
            }:
                result["incomplete_reasons"].append("unknown_daily_pnl_basis")

        max_loss_limit = _number(row["max_loss_limit_usd"])
        floor = _number(row["max_loss_floor_equity"])
        peak_equity = _number(row["peak_equity"])
        peak_eod = _number(row["peak_eod_equity"])
        if max_loss_limit is None or floor is None or peak_equity is None or peak_eod is None:
            result["incomplete_reasons"].append("maximum_loss_fields_missing")
        else:
            mode = str(row["max_drawdown_mode"])
            expected_floor = initial - max_loss_limit
            reference = initial
            if mode == "eod":
                expected_floor = max(expected_floor, peak_eod - max_loss_limit)
                reference = peak_eod
            elif mode == "intraday_trailing":
                expected_floor = max(expected_floor, peak_equity - max_loss_limit)
                reference = peak_equity
            elif mode != "static":
                result["incomplete_reasons"].append("unknown_max_drawdown_mode")
            payout_floor = _number(row["payout_drawdown_floor"])
            if mode != "static" and payout_floor is not None:
                expected_floor = max(expected_floor, payout_floor)
            expected_floor = min(initial, expected_floor)
            check(row_index, "maximum_loss_floor_matches_mode", floor, expected_floor)
            check(
                row_index,
                "maximum_loss_reference_matches_equity",
                row["max_drawdown_from_reference_usd"],
                max(0.0, reference - equity),
            )
            check(
                row_index,
                "peak_to_trough_drawdown_matches_equity",
                row["trailing_drawdown_usd"],
                max(0.0, peak_equity - equity),
            )

        if observed_peak_eod is not None:
            prior_peak_eod_equity = observed_peak_eod
        if observed_max_eod_drawdown is not None:
            prior_max_eod_drawdown = observed_max_eod_drawdown
        if balance is not None:
            prior_balance = balance
        if equity is not None:
            prior_equity = equity

    if previous_event_count != len(trade_events):
        result["incomplete_reasons"].append("trade_events_outside_snapshot_coverage")

    if breach_events is None:
        result["incomplete_reasons"].append("breach_event_ledger_not_supplied")
    else:
        raw_breach_records: list[object] = list(
            breach_events.to_dict("records")
            if isinstance(breach_events, pd.DataFrame)
            else breach_events
        )
        breach_records: list[dict[str, Any]] = []
        for raw_event in raw_breach_records:
            if not isinstance(raw_event, Mapping):
                result["incomplete_reasons"].append("invalid_breach_event_record")
                continue
            breach_records.append({str(key): value for key, value in raw_event.items()})
        hard_breaches = []
        for breach_record in breach_records:
            if breach_record.get("schema_version") != RISK_BREACH_EVENT_SCHEMA_V1:
                result["incomplete_reasons"].append(
                    "unsupported_or_missing_hard_breach_event_schema"
                )
                continue
            if str(breach_record.get("reason", "")) not in {
                "daily_loss",
                "max_drawdown",
                "trailing_dd",
            }:
                result["incomplete_reasons"].append("invalid_hard_breach_event_reason")
                continue
            raw_event_time = breach_record.get("detection_time")
            event_time: pd.Timestamp | None = None
            if raw_event_time is None:
                result["incomplete_reasons"].append("hard_breach_detection_time_is_invalid")
            else:
                parsed_event_time = pd.to_datetime(raw_event_time, utc=True, errors="coerce")
                if pd.isna(parsed_event_time):
                    result["incomplete_reasons"].append("hard_breach_detection_time_is_invalid")
                else:
                    event_time = pd.Timestamp(parsed_event_time)
            raw_prefix = _number(breach_record.get("trade_event_count"))
            valid_prefix = True
            if (
                raw_prefix is None
                or not raw_prefix.is_integer()
                or raw_prefix < 0
                or raw_prefix > len(trade_events)
            ):
                result["incomplete_reasons"].append("hard_breach_trade_event_prefix_is_invalid")
                valid_prefix = False
            if event_time is None or not valid_prefix or raw_prefix is None:
                continue
            hard_breaches.append(
                {
                    **breach_record,
                    "detection_time": event_time,
                    "trade_event_count": int(raw_prefix),
                }
            )
        if hard_breaches:
            for hard_breach in hard_breaches:
                prefix = int(hard_breach["trade_event_count"])
                if not trade_events.empty and "type" not in trade_events.columns:
                    result["incomplete_reasons"].append(
                        "trade_event_types_missing_for_breach_latch_check"
                    )
                    continue
                later_types = (
                    trade_events.iloc[prefix:]["type"].astype(str)
                    if not trade_events.empty
                    else pd.Series(dtype=str)
                )
                later_entries = int(later_types.isin({"order_submit", "order_fill", "open"}).sum())
                checks["no_order_submission_fill_or_open_after_hard_breach"] = (
                    checks.get("no_order_submission_fill_or_open_after_hard_breach", 0) + 1
                )
                if later_entries:
                    failures.append(
                        {
                            "row_index": str(hard_breach["detection_time"]),
                            "check": "no_order_submission_fill_or_open_after_hard_breach",
                            "actual": float(later_entries),
                            "expected": 0.0,
                        }
                    )
            first_breach = min(
                hard_breaches, key=lambda breach: pd.Timestamp(breach["detection_time"])
            )
            first_breach_time = pd.Timestamp(first_breach["detection_time"])
            if hard_breaches:
                decision_times = pd.to_datetime(trace["decision_time"], utc=True, errors="coerce")
                if decision_times.isna().any():
                    result["incomplete_reasons"].append(
                        "hard_breach_account_snapshot_time_is_invalid"
                    )
                rows_after_breach = [
                    index
                    for index, decision_time in enumerate(decision_times)
                    if not pd.isna(decision_time) and decision_time >= first_breach_time
                ]
                if not len(rows_after_breach):
                    result["incomplete_reasons"].append(
                        "hard_breach_has_no_matching_account_snapshot"
                    )
                else:
                    breach_row_index = int(rows_after_breach[0])
                    snapshot_prefix = _number(trace.iloc[breach_row_index]["trade_event_count"])
                    if (
                        snapshot_prefix is None
                        or not snapshot_prefix.is_integer()
                        or snapshot_prefix < 0
                        or snapshot_prefix > len(trade_events)
                    ):
                        result["incomplete_reasons"].append(
                            "hard_breach_trade_event_prefix_is_invalid"
                        )
                    else:
                        check(
                            trace.index[breach_row_index],
                            "breach_event_prefix_precedes_account_snapshot",
                            float(snapshot_prefix >= int(first_breach["trade_event_count"])),
                            1.0,
                        )
    result["checks"] = checks
    result["failure_count"] = len(failures)
    result["failures"] = failures[:100]
    result["fill_cost_provenance"]["verified_rows"] = fill_cost_provenance_verified
    result["fill_cost_provenance"]["missing_rows"] = fill_cost_provenance_missing
    fill_cost_rows = result["fill_cost_provenance"]["fill_rows"]
    if fill_cost_rows == 0:
        result["fill_cost_provenance"]["status"] = "no_fills"
    elif any(
        failure.get("check", "").startswith("broker_quote_")
        or failure.get("check") == "fill_price_matches_broker_quote_side"
        for failure in failures
    ):
        result["fill_cost_provenance"]["status"] = "mismatch"
    elif fill_cost_provenance_verified == fill_cost_rows and not any(
        reason
        in {
            "unsupported_fill_cost_provenance_schema",
            "invalid_fill_cost_provenance_fields",
        }
        for reason in result["incomplete_reasons"]
    ):
        result["fill_cost_provenance"]["status"] = "matched"
    elif fill_cost_provenance_verified or fill_cost_provenance_missing:
        result["fill_cost_provenance"]["status"] = "partial"
    else:
        result["fill_cost_provenance"]["status"] = "invalid"
    if not cash_replay_complete:
        result["incomplete_reasons"].append("cash_event_replay_missing_fields")
    if not trade_cashflow_replay_complete:
        result["incomplete_reasons"].append("trade_fill_cashflow_replay_missing_fields")
    if not payout_replay_complete:
        result["incomplete_reasons"].append("payout_event_replay_missing_fields")
    if result["failure_count"]:
        result["status"] = "mismatch"
    elif result["incomplete_reasons"]:
        result["status"] = "incomplete"
    else:
        result["status"] = "matched"
    return result


__all__ = ["ACCOUNT_STATE_RECONCILIATION_SCHEMA", "reconcile_account_state_trace"]
