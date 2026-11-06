"""Pair event-backtest outputs under exact-touch and trade-through fills."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import pandas as pd

LIMIT_EXECUTION_SENSITIVITY_SCHEMA = "limit_execution_sensitivity.v1"
_CLOSE_TYPES = frozenset(
    {"close", "stop_close", "tp_close", "forced_close", "eod_close", "tp_partial_close"}
)
_DECISION_FIELDS = (
    "decision_index",
    "decision_bar_time",
    "decision_time",
    "session_id",
    "action",
    "trade_setup_candidate_id",
    "trade_setup_idea",
    "trade_setup_timeframe",
    "trade_setup_eligible",
    "execution_type",
    "limit_offset_atr",
    "limit_ttl_bars",
    "selected_risk_frac",
    "selected_geometry_action",
)


def _number(value: Any) -> float | None:
    """Parse a finite numeric output field.

    Args:
        value: Raw result field to convert.

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


def _boolean(value: Any) -> bool | None:
    """Parse only explicit Python or NumPy boolean ledger values.

    Args:
        value: Raw ledger flag.

    Returns:
        Boolean value, or ``None`` when the flag is not explicitly typed.
    """
    if isinstance(value, bool) or type(value).__name__ == "bool_":
        return bool(value)
    return None


def _same_value(left: Any, right: Any) -> bool:
    """Compare nested decision values while treating paired nulls as equal.

    Args:
        left: Value from the exact-touch run.
        right: Corresponding value from the trade-through run.

    Returns:
        Whether the values match recursively, including paired missing values.
    """
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        return left.keys() == right.keys() and all(
            _same_value(left[key], right[key]) for key in left
        )
    if (
        isinstance(left, Sequence)
        and isinstance(right, Sequence)
        and not isinstance(left, (str, bytes))
    ):
        return len(left) == len(right) and all(_same_value(a, b) for a, b in zip(left, right))
    try:
        left_missing = bool(pd.isna(left))
        right_missing = bool(pd.isna(right))
    except (TypeError, ValueError):
        left_missing = right_missing = False
    if left_missing or right_missing:
        return left_missing and right_missing
    try:
        return bool(left == right)
    except (TypeError, ValueError):
        return False


def _records(frame: Any, label: str) -> list[dict[str, Any]]:
    """Return records from a required dataframe-shaped result field.

    Args:
        frame: Result field expected to contain a DataFrame.
        label: Field label used in validation errors.

    Returns:
        Rows as mappings with string column names.
    """
    if not isinstance(frame, pd.DataFrame):
        raise ValueError(f"{label} must be a pandas DataFrame")
    return [{str(key): value for key, value in row.items()} for row in frame.to_dict("records")]


def _contract(result: Mapping[str, Any], expected_trade_through: bool) -> dict[str, Any]:
    """Validate and normalize the run settings used for a paired sensitivity.

    Args:
        result: Event-backtest output and execution provenance.
        expected_trade_through: Required fill assumption for this run.

    Returns:
        Normalized contract and action/observation schema fields for comparison.
    """
    contract = result.get("execution_contract")
    if not isinstance(contract, Mapping):
        raise ValueError("run is missing its execution_contract provenance")
    if contract.get("schema_version") != "backtest_execution_contract.v1":
        raise ValueError("run has an unsupported execution_contract schema")
    limit = contract.get("limit_order")
    if not isinstance(limit, Mapping):
        raise ValueError("execution_contract is missing limit_order settings")
    trade_through = limit.get("require_trade_through")
    if not isinstance(trade_through, bool):
        raise ValueError("limit fill assumption must be explicitly recorded as a boolean")
    if trade_through is not expected_trade_through:
        assumption = "trade-through" if expected_trade_through else "exact-touch"
        raise ValueError(f"run does not declare the {assumption} fill assumption")
    action_schema = result.get("action_schema")
    if (
        not isinstance(action_schema, Mapping)
        or action_schema.get("has_entry_execution") is not True
    ):
        raise ValueError("run action schema does not declare policy-selected entry execution")
    return {
        "execution_contract": {
            **dict(contract),
            "limit_order": {
                **dict(limit),
                "require_trade_through": False,
                "fill_rule": "paired-sensitivity-normalized",
            },
        },
        "action_schema": action_schema,
        "observation_schema": result.get("observation_schema"),
        "observation_inputs": result.get("observation_inputs"),
    }


def _decision_index(frame: pd.DataFrame, label: str) -> dict[str, dict[str, Any]]:
    """Index decisions by their stable per-run identity and reject duplicates.

    Args:
        frame: Policy-decision rows to index.
        label: Run label used in validation errors.

    Returns:
        Mapping from unique decision ID to its row record.
    """
    records = _records(frame, label)
    indexed: dict[str, dict[str, Any]] = {}
    for record in records:
        raw_id = record.get("decision_id")
        if raw_id is None or pd.isna(raw_id):
            raise ValueError(f"{label} contains a decision without an identity")
        decision_id = str(raw_id)
        if decision_id in indexed:
            raise ValueError(f"{label} contains duplicate decision identity {decision_id}")
        indexed[decision_id] = record
    return indexed


def _limit_order_outcomes(
    decisions: Mapping[str, Mapping[str, Any]],
    events: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Summarize each selected limit decision through its fill or cancellation.

    Args:
        decisions: Decision records keyed by their stable IDs.
        events: Ordered order and position lifecycle events.

    Returns:
        Per-decision limit submission, fill, cancel, and close outcomes.
    """
    submissions: dict[str, dict[str, Any]] = {}
    order_ids: set[str] = set()
    for event in events:
        if (
            str(event.get("type", "")) != "order_submit"
            or str(event.get("order_type", "market")) != "limit"
            or event.get("decision_id") is None
            or pd.isna(event.get("decision_id"))
        ):
            continue
        decision_id = str(event["decision_id"])
        if decision_id in submissions:
            raise ValueError(f"decision {decision_id} submitted multiple limit orders")
        raw_order_id = event.get("order_id")
        if raw_order_id is None or pd.isna(raw_order_id):
            raise ValueError(f"limit submission for decision {decision_id} has no order id")
        order_id = str(raw_order_id)
        if order_id in order_ids:
            raise ValueError(f"duplicate limit order identity {order_id}")
        order_ids.add(order_id)
        submissions[decision_id] = event
    outputs: dict[str, dict[str, Any]] = {}
    for decision_id, decision in decisions.items():
        action = _number(decision.get("action"))
        candidate_id = _number(decision.get("trade_setup_candidate_id"))
        raw_eligible = decision.get("trade_setup_eligible")
        if raw_eligible is None or pd.isna(raw_eligible):
            eligible = False
        else:
            parsed_eligible = _boolean(raw_eligible)
            if parsed_eligible is None:
                raise ValueError(
                    f"decision {decision_id} has a non-boolean trade_setup_eligible flag"
                )
            eligible = parsed_eligible
        if (
            str(decision.get("execution_type", "market")) != "limit"
            or action not in (-1.0, 1.0)
            or candidate_id is None
            or candidate_id <= 0.0
            or not eligible
        ):
            continue
        submit = submissions.get(decision_id)
        if submit is None:
            outputs[decision_id] = {
                "status": "no_order_submitted",
                "limit_price": None,
                "fill_price": None,
            }
            continue
        raw_order_id = submit.get("order_id")
        if raw_order_id is None:
            outputs[decision_id] = {
                "status": "invalid_order_identity",
                "limit_price": None,
                "fill_price": None,
            }
            continue
        outcome_order_id = str(raw_order_id)
        linked = [
            event
            for event in events
            if event.get("order_id") is not None
            and not pd.isna(event.get("order_id"))
            and str(event.get("order_id")) == outcome_order_id
        ]
        fills = [event for event in linked if str(event.get("type", "")) == "order_fill"]
        opens = [event for event in linked if str(event.get("type", "")) == "open"]
        cancels = [event for event in linked if str(event.get("type", "")) == "order_cancel"]
        if len(fills) > 1 or len(opens) > 1 or len(cancels) > 1:
            raise ValueError(f"limit order {order_id} has duplicate lifecycle outcomes")
        if (fills or opens) and cancels:
            raise ValueError(f"limit order {order_id} is both filled and cancelled")
        status = "filled" if fills or opens else "cancelled" if cancels else "unresolved"
        fill_record = fills[0] if fills else opens[0] if opens else {}
        open_record = opens[0] if opens else {}
        position_id = open_record.get("position_id", fill_record.get("position_id"))
        close_events = [
            event
            for event in events
            if str(event.get("type", "")) in _CLOSE_TYPES
            and position_id is not None
            and event.get("position_id") is not None
            and str(event.get("position_id")) == str(position_id)
        ]
        net_values = [_number(event.get("net_pnl")) for event in close_events]
        outputs[decision_id] = {
            "status": status,
            "limit_price": _number(submit.get("limit_price")),
            "fill_price": _number(fill_record.get("price")),
            "order_id": str(order_id),
            "position_id": None if position_id is None else str(position_id),
            "position_complete": (
                _boolean(close_events[-1].get("position_complete")) if close_events else False
            ),
            "realized_net_pnl": (
                float(sum(value for value in net_values if value is not None))
                if close_events and all(value is not None for value in net_values)
                else None
            ),
        }
    return outputs


def compare_limit_execution_sensitivity(
    exact_touch_result: Mapping[str, Any],
    trade_through_result: Mapping[str, Any],
) -> dict[str, Any]:
    """Compare paired backtests that differ only in limit-fill conservatism.

    This reports implementation sensitivity and policy-path divergence. It does
    not estimate economic value or statistical uncertainty; those require
    paired independent seeds and the preregistered evaluation protocol.

    Args:
        exact_touch_result: Backtest using the exact-touch limit fill assumption.
        trade_through_result: Backtest requiring price trade through the limit.

    Returns:
        Paired sensitivity report covering contracts, decisions, orders, and outcomes.
    """
    exact_contract = _contract(exact_touch_result, expected_trade_through=False)
    strict_contract = _contract(trade_through_result, expected_trade_through=True)
    settings_match = exact_contract == strict_contract
    exact_decision_frame = exact_touch_result.get("policy_decisions")
    strict_decision_frame = trade_through_result.get("policy_decisions")
    if not isinstance(exact_decision_frame, pd.DataFrame):
        raise ValueError("exact-touch policy_decisions must be a DataFrame")
    if not isinstance(strict_decision_frame, pd.DataFrame):
        raise ValueError("trade-through policy_decisions must be a DataFrame")
    exact_decisions = _decision_index(exact_decision_frame, "exact-touch policy_decisions")
    strict_decisions = _decision_index(strict_decision_frame, "trade-through policy_decisions")
    exact_events = _records(exact_touch_result.get("trades"), "exact-touch trades")
    strict_events = _records(trade_through_result.get("trades"), "trade-through trades")
    exact_outcomes = _limit_order_outcomes(exact_decisions, exact_events)
    strict_outcomes = _limit_order_outcomes(strict_decisions, strict_events)

    common_ids = sorted(set(exact_decisions) & set(strict_decisions))
    decision_divergences = [
        {
            "decision_id": decision_id,
            "fields": [
                field
                for field in _DECISION_FIELDS
                if not _same_value(
                    exact_decisions[decision_id].get(field),
                    strict_decisions[decision_id].get(field),
                )
            ],
        }
        for decision_id in common_ids
        if any(
            not _same_value(
                exact_decisions[decision_id].get(field),
                strict_decisions[decision_id].get(field),
            )
            for field in _DECISION_FIELDS
        )
    ]
    paired_limit_ids = sorted(set(exact_outcomes) & set(strict_outcomes))
    paired_outcomes = [
        {
            "decision_id": decision_id,
            "exact_touch": exact_outcomes[decision_id],
            "trade_through": strict_outcomes[decision_id],
        }
        for decision_id in paired_limit_ids
    ]
    counts = {
        "exact_touch": {
            status: sum(outcome["status"] == status for outcome in exact_outcomes.values())
            for status in ("filled", "cancelled", "no_order_submitted", "unresolved")
        },
        "trade_through": {
            status: sum(outcome["status"] == status for outcome in strict_outcomes.values())
            for status in ("filled", "cancelled", "no_order_submitted", "unresolved")
        },
    }
    return {
        "schema_version": LIMIT_EXECUTION_SENSITIVITY_SCHEMA,
        "status": "execution_contracts_match" if settings_match else "execution_contract_mismatch",
        "execution_and_policy_schemas_match_except_fill_rule": settings_match,
        "other_run_provenance_verified": False,
        "decision_counts": {
            "exact_touch": len(exact_decisions),
            "trade_through": len(strict_decisions),
            "common": len(common_ids),
            "exact_only": len(set(exact_decisions) - set(strict_decisions)),
            "trade_through_only": len(set(strict_decisions) - set(exact_decisions)),
            "policy_divergent_common": len(decision_divergences),
        },
        "limit_order_counts": {
            "exact_touch": len(exact_outcomes),
            "trade_through": len(strict_outcomes),
            "paired": len(paired_limit_ids),
            "outcomes": counts,
        },
        "decision_divergences": decision_divergences,
        "paired_limit_outcomes": paired_outcomes,
        "economic_value_claim": "not_estimated",
        "uncertainty_claim": "not_estimated",
    }


__all__ = ["LIMIT_EXECUTION_SENSITIVITY_SCHEMA", "compare_limit_execution_sensitivity"]
