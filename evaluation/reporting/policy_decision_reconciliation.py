"""Reconcile environment and event-backtest decisions with order lifecycles."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import pandas as pd

from decisioning.trade_setup import NO_TRADE_ID, TRADE_SETUP_CATEGORY_COUNT
from trading.risk import RISK_BREACH_EVENT_SCHEMA_V1, RISK_BREACH_EVENT_SCHEMA_V2

POLICY_DECISION_RECONCILIATION_SCHEMA = "policy_decision_reconciliation.v1"
_DECISION_SCHEMA_V1 = "event_backtest_policy_decision.v1"
_DECISION_SCHEMA = "event_backtest_policy_decision.v2"
_ENVIRONMENT_DECISION_SCHEMA_V1 = "environment_policy_decision.v1"
_ENVIRONMENT_DECISION_SCHEMA_BAR_LABEL = "environment_policy_decision.v2"
_ENVIRONMENT_DECISION_SCHEMA_COMPLETED_BAR = "environment_policy_decision.completed_bar.v1"
_ENVIRONMENT_DECISION_SCHEMAS = frozenset(
    {
        _ENVIRONMENT_DECISION_SCHEMA_BAR_LABEL,
        _ENVIRONMENT_DECISION_SCHEMA_COMPLETED_BAR,
    }
)
_SUPPORTED_DECISION_SCHEMAS = frozenset(
    {
        _DECISION_SCHEMA_V1,
        _DECISION_SCHEMA,
        _ENVIRONMENT_DECISION_SCHEMA_V1,
        *_ENVIRONMENT_DECISION_SCHEMAS,
    }
)
_OPEN_TYPES = frozenset({"open"})
_CLOSE_TYPES = frozenset(
    {"close", "stop_close", "tp_close", "forced_close", "eod_close", "tp_partial_close"}
)
_SUPPORTED_EVENT_TYPES = frozenset(
    {
        *_OPEN_TYPES,
        *_CLOSE_TYPES,
        "cycle_failure",
        "order_cancel",
        "order_fill",
        "order_submit",
        "payout_reset",
        "reject",
        "sl_update",
        "tp_update",
    }
)


def _integer(value: Any) -> int | None:
    """Parse a finite integral value without raising on malformed ledgers.

    Args:
        value: Raw ledger cell to interpret as an integer.

    Returns:
        Integral value, or ``None`` when the cell is invalid.
    """
    if isinstance(value, bool) or (
        type(value).__module__ == "numpy" and type(value).__name__ in {"bool", "bool_"}
    ):
        return None
    try:
        numeric = float(pd.to_numeric(value, errors="coerce"))
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(numeric) or not numeric.is_integer():
        return None
    return int(numeric)


def _number(value: Any) -> float | None:
    """Parse a finite numeric scalar without raising on malformed ledger data.

    Args:
        value: Raw ledger cell to interpret as a number.

    Returns:
        Finite numeric value, or ``None`` when conversion fails.
    """
    if isinstance(value, bool) or (
        type(value).__module__ == "numpy" and type(value).__name__ in {"bool", "bool_"}
    ):
        return None
    try:
        numeric = float(pd.to_numeric(value, errors="coerce"))
    except (TypeError, ValueError, OverflowError):
        return None
    return numeric if math.isfinite(numeric) else None


def _timestamp(value: Any) -> pd.Timestamp | None:
    """Parse one timestamp as UTC without accepting malformed values.

    Args:
        value: Raw event timestamp value.

    Returns:
        UTC timestamp, or ``None`` for invalid or missing input.
    """
    try:
        parsed = pd.to_datetime(value, utc=True, errors="coerce")
    except (TypeError, ValueError, OverflowError):
        return None
    if not isinstance(parsed, pd.Timestamp) or pd.isna(parsed):
        return None
    return parsed


def _first_timestamp(record: Mapping[str, Any], *keys: str) -> pd.Timestamp | None:
    """Return the first parseable timestamp when optional cells are missing.

    Args:
        record: Event fields containing optional timestamp values.
        *keys: Timestamp fields to inspect in priority order.

    Returns:
        First valid UTC timestamp, or ``None`` if no field can be parsed.
    """
    for key in keys:
        parsed = _timestamp(record.get(key))
        if parsed is not None:
            return parsed
    return None


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Return row records with string column names for the serialized schema.

    Args:
        frame: Decision or trade-event table to convert.

    Returns:
        Row mappings with normalized string keys.
    """
    return [
        {str(key): value for key, value in record.items()} for record in frame.to_dict("records")
    ]


def _is_missing(value: Any) -> bool:
    """Check scalar missing values without raising for malformed containers.

    Args:
        value: Candidate scalar or container from a ledger row.

    Returns:
        Whether the value is missing; non-scalar ambiguity is treated as present.
    """
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _boolean(value: Any) -> bool | None:
    """Parse only explicit Python or NumPy boolean ledger values.

    Args:
        value: Raw flag from the ledger.

    Returns:
        Boolean value for a typed flag, otherwise ``None``.
    """
    if isinstance(value, bool) or (
        type(value).__module__ == "numpy" and type(value).__name__ in {"bool", "bool_"}
    ):
        return bool(value)
    return None


def _truth(value: Any) -> bool:
    """Interpret a strictly typed true flag; malformed values are false.

    Args:
        value: Raw flag value.

    Returns:
        Whether the value is explicitly boolean true.
    """
    return _boolean(value) is True


def _position_complete(event: Mapping[str, Any]) -> bool | None:
    """Read a close completion flag, retaining the legacy missing-field default.

    Args:
        event: Position close event fields.

    Returns:
        Completion flag, defaulting missing fields to true; invalid types return ``None``.
    """
    value = event.get("position_complete", True)
    if _is_missing(value):
        return True
    return _boolean(value)


def reconcile_policy_decisions(
    decisions: pd.DataFrame,
    trade_events: pd.DataFrame,
    breach_events: Sequence[object] | None = None,
) -> dict[str, Any]:
    """Check decision identity, setup eligibility, order lifecycle, and closes.

    Args:
        decisions: Policy decision rows emitted by the environment or backtest.
        trade_events: Ordered order and position lifecycle event rows.
        breach_events: Optional risk-breach events to reconcile with the lifecycle.

    Returns:
        Versioned report containing completeness, invariant checks, and failures.
    """
    report: dict[str, Any] = {
        "schema_version": POLICY_DECISION_RECONCILIATION_SCHEMA,
        "status": "incomplete",
        "decision_rows": int(len(decisions)),
        "decision_schema_versions": [],
        "trade_event_rows": int(len(trade_events)),
        "breach_event_rows": 0 if breach_events is None else int(len(breach_events)),
        "checks": {},
        "failure_count": 0,
        "failures": [],
        "incomplete_reasons": [],
        "unclosed_position_ids": [],
    }
    required = {"schema_version", "decision_id", "action"}
    if decisions.empty:
        report["incomplete_reasons"].append("policy_decisions_are_empty")
    elif not required.issubset(decisions.columns):
        report["incomplete_reasons"].append("policy_decision_columns_missing")
    else:
        schema_versions = set(decisions["schema_version"].dropna().astype(str))
        report["decision_schema_versions"] = sorted(schema_versions)
        if not schema_versions or not schema_versions.issubset(_SUPPORTED_DECISION_SCHEMAS):
            report["incomplete_reasons"].append("unsupported_or_mixed_decision_schema")
        if schema_versions.intersection({_DECISION_SCHEMA, *_ENVIRONMENT_DECISION_SCHEMAS}):
            v2_required = {
                "decision_time",
                "position_direction_at_decision",
                "position_id_at_decision",
                "pending_order_id_at_decision",
            }
            has_selected_candidates = (
                "trade_setup_candidate_id" in decisions.columns
                and decisions["trade_setup_candidate_id"].notna().any()
            )
            has_selected_eligible_candidates = (
                has_selected_candidates
                and "trade_setup_eligible" in decisions.columns
                and bool(
                    (
                        decisions["trade_setup_candidate_id"].notna()
                        & decisions["trade_setup_eligible"].map(_truth)
                    ).any()
                )
            )
            if has_selected_candidates and (
                _DECISION_SCHEMA in schema_versions
                or bool(schema_versions.intersection(_ENVIRONMENT_DECISION_SCHEMAS))
            ):
                v2_required.update(
                    {
                        "eligible_candidate_count",
                        "eligible_trade_setup_ids",
                        "trade_setup_eligible",
                    }
                )
            if has_selected_eligible_candidates and (
                _DECISION_SCHEMA in schema_versions
                or bool(schema_versions.intersection(_ENVIRONMENT_DECISION_SCHEMAS))
            ):
                v2_required.update(
                    {
                        "trade_setup_source_event_id",
                        "trade_setup_source_event_identity_status",
                    }
                )
            missing_v2_columns = v2_required.difference(decisions.columns)
            if missing_v2_columns:
                if has_selected_candidates and "trade_setup_eligible" in missing_v2_columns:
                    report["incomplete_reasons"].append("selected_candidate_eligibility_missing")
                if has_selected_candidates and missing_v2_columns.intersection(
                    {
                        "trade_setup_source_event_id",
                        "trade_setup_source_event_identity_status",
                    }
                ):
                    report["incomplete_reasons"].append("eligible_setup_source_identity_missing")
                if missing_v2_columns.difference(
                    {
                        "trade_setup_eligible",
                        "trade_setup_source_event_id",
                        "trade_setup_source_event_identity_status",
                    }
                ):
                    report["incomplete_reasons"].append("decision_position_context_columns_missing")
    event_required = {"type", "decision_id"}
    if not trade_events.empty and not event_required.issubset(trade_events.columns):
        report["incomplete_reasons"].append("trade_event_decision_columns_missing")
    if report["incomplete_reasons"]:
        return report

    failures: list[dict[str, Any]] = []
    checks: dict[str, int] = {}

    def check(name: str, identity: Any, ok: bool, detail: str) -> None:
        """Count one lifecycle invariant and preserve failed identities.

        Args:
            name: Stable name of the invariant being checked.
            identity: Decision or event identity associated with the check.
            ok: Whether the invariant passed.
            detail: Explanation stored when the invariant fails.
        """
        checks[name] = checks.get(name, 0) + 1
        if not ok:
            failures.append({"identity": str(identity), "check": name, "detail": detail})

    def truth(value: Any) -> bool:
        """Interpret only explicit true flags as true.

        Args:
            value: Raw serialized flag.

        Returns:
            Whether the value is an explicit true boolean.
        """
        return _truth(value)

    decision_by_id: dict[str, dict[str, Any]] = {}
    for record in _records(decisions):
        raw_id = record.get("decision_id")
        decision_id = "" if _is_missing(raw_id) else str(raw_id)
        check(
            "decision_id_is_unique_and_nonempty",
            decision_id,
            bool(decision_id) and decision_id not in decision_by_id,
            "duplicate or empty decision id",
        )
        action = _integer(record.get("action"))
        check(
            "decision_action_is_valid",
            decision_id,
            action in {-1, 0, 1},
            "decision action is outside the supported -1, 0, 1 contract",
        )
        if decision_id:
            decision_by_id[decision_id] = record

    events = _records(trade_events)
    orders: dict[str, dict[str, Any]] = {}
    order_outcomes: dict[str, list[dict[str, Any]]] = {}
    positions: dict[str, dict[str, Any]] = {}
    position_open_event_indices: dict[str, int] = {}
    position_terminal_events: dict[str, list[dict[str, Any]]] = {}
    position_terminal_event_indices: dict[str, list[int]] = {}
    active_positions: set[str] = set()
    order_submits_by_decision: dict[str, list[dict[str, Any]]] = {}
    rejections_by_decision: dict[str, list[dict[str, Any]]] = {}
    opens_by_decision: dict[str, list[dict[str, Any]]] = {}
    for event_index, event in enumerate(events):
        event_type = str(event.get("type", ""))
        if event_type not in _SUPPORTED_EVENT_TYPES:
            report["incomplete_reasons"].append("unsupported_trade_event_type_for_policy_replay")
        raw_decision_id = event.get("decision_id")
        if not _is_missing(raw_decision_id):
            decision_id = str(raw_decision_id)
            if event_type == "order_submit":
                order_submits_by_decision.setdefault(decision_id, []).append(event)
            elif event_type == "reject":
                rejections_by_decision.setdefault(decision_id, []).append(event)
            if event_type in {
                "order_submit",
                "order_fill",
                "order_cancel",
                "open",
                "reject",
                *_CLOSE_TYPES,
            }:
                check(
                    "event_decision_id_resolves",
                    decision_id,
                    decision_id in decision_by_id,
                    "event references an unknown decision",
                )
            if event_type == "open" and not _is_missing(raw_decision_id):
                opens_by_decision.setdefault(str(raw_decision_id), []).append(event)
        if event_type == "order_submit":
            if _is_missing(raw_decision_id):
                report["incomplete_reasons"].append("submitted_order_missing_decision_id")
            raw_order_id = event.get("order_id")
            order_id = "" if _is_missing(raw_order_id) else str(raw_order_id)
            check(
                "order_id_is_unique_and_nonempty",
                order_id,
                bool(order_id) and order_id not in orders,
                "duplicate or empty order id",
            )
            if order_id:
                orders[order_id] = event
                order_outcomes.setdefault(order_id, [])
        elif event_type in {"order_fill", "order_cancel", "open", "reject"}:
            if event_type in {"order_fill", "order_cancel"} and (_is_missing(raw_decision_id)):
                report["incomplete_reasons"].append("order_lifecycle_event_missing_decision_id")
            raw_order_id = event.get("order_id")
            if not _is_missing(raw_order_id):
                order_id = str(raw_order_id)
                if event_type == "reject" and _is_missing(raw_decision_id):
                    report["incomplete_reasons"].append("order_rejection_missing_decision_id")
                check(
                    "order_event_has_submission",
                    order_id,
                    order_id in orders,
                    "order lifecycle event has no submission",
                )
                order_outcomes.setdefault(order_id, []).append(event)
            elif event_type in {"order_fill", "order_cancel"}:
                report["incomplete_reasons"].append("order_lifecycle_event_missing_order_id")

        if event_type in _OPEN_TYPES:
            raw_order_id = event.get("order_id")
            if _is_missing(raw_order_id):
                raw_decision_id = event.get("decision_id")
                decision = (
                    decision_by_id.get(str(raw_decision_id))
                    if not _is_missing(raw_decision_id)
                    else None
                )
                is_immediate_market_open = (
                    decision is not None
                    and str(decision.get("schema_version", "")) in _ENVIRONMENT_DECISION_SCHEMAS
                    and str(decision.get("execution_type", "market")) == "market"
                )
                if not is_immediate_market_open:
                    report["incomplete_reasons"].append("opened_position_missing_order_id")
            raw_id = event.get("position_id")
            position_id = "" if _is_missing(raw_id) else str(raw_id)
            if not position_id:
                report["incomplete_reasons"].append("opened_position_missing_position_id")
                continue
            check(
                "position_id_opens_once",
                position_id,
                position_id not in positions,
                "position id opened more than once",
            )
            positions[position_id] = event
            position_open_event_indices[position_id] = event_index
            active_positions.add(position_id)
            raw_open_decision_id = event.get("decision_id")
            if not _is_missing(raw_open_decision_id):
                open_decision_id = str(raw_open_decision_id)
                decision = decision_by_id.get(open_decision_id)
                if decision is not None:
                    expected_direction = _integer(decision.get("action"))
                    opened_direction = _integer(event.get("direction"))
                    check(
                        "open_direction_matches_decision",
                        position_id,
                        expected_direction in {-1, 1} and opened_direction == expected_direction,
                        "opened direction differs from selected action",
                    )
                    candidate_id = _integer(decision.get("trade_setup_candidate_id"))
                    if candidate_id is not None:
                        event_candidate_id = event.get("trade_setup_candidate_id")
                        check(
                            "open_candidate_matches_decision",
                            position_id,
                            _integer(event_candidate_id) == candidate_id,
                            "opened candidate differs from decision",
                        )
                        if truth(decision.get("trade_setup_eligible")):
                            expected_source_id = decision.get("trade_setup_source_event_id")
                            expected_source_status = decision.get(
                                "trade_setup_source_event_identity_status"
                            )
                            if (
                                str(expected_source_status) == "identified"
                                and isinstance(expected_source_id, str)
                                and expected_source_id
                            ):
                                actual_source_id = event.get("trade_setup_source_event_id")
                                actual_source_status = event.get(
                                    "trade_setup_source_event_identity_status"
                                )
                                check(
                                    "open_source_event_matches_decision",
                                    position_id,
                                    isinstance(actual_source_id, str)
                                    and actual_source_id == expected_source_id
                                    and str(actual_source_status) == "identified",
                                    "opened position source event differs from decision",
                                )
                    if _boolean(decision.get("trade_setup_eligible")) is False:
                        check(
                            "ineligible_setup_never_opens",
                            decision_id,
                            False,
                            "an ineligible candidate opened",
                        )
            else:
                report["incomplete_reasons"].append("opened_position_missing_decision_id")
        elif event_type in _CLOSE_TYPES:
            raw_id = event.get("position_id")
            position_id = "" if _is_missing(raw_id) else str(raw_id)
            if not position_id:
                report["incomplete_reasons"].append("close_event_missing_position_id")
                continue
            check(
                "close_references_active_position",
                position_id,
                position_id in active_positions,
                "close precedes open or follows completed close",
            )
            position_terminal_events.setdefault(position_id, []).append(event)
            position_complete = _position_complete(event)
            if position_complete is None:
                report["incomplete_reasons"].append("position_completion_flag_is_invalid")
                position_complete = False
            if position_complete:
                position_terminal_event_indices.setdefault(position_id, []).append(event_index)
            if position_id in active_positions and position_complete:
                active_positions.remove(position_id)

    for decision_id, decision in decision_by_id.items():
        action = _integer(decision.get("action"))
        candidate_id = _integer(decision.get("trade_setup_candidate_id"))
        eligible = decision.get("trade_setup_eligible")
        schema_version = str(decision.get("schema_version", ""))
        mask_required = schema_version in {_DECISION_SCHEMA, *_ENVIRONMENT_DECISION_SCHEMAS}
        eligibility_required = mask_required and candidate_id is not None
        if (eligibility_required or not _is_missing(eligible)) and _boolean(eligible) is None:
            report["incomplete_reasons"].append("decision_eligibility_flag_is_invalid")
        if candidate_id is not None and schema_version in {
            _DECISION_SCHEMA_V1,
            _ENVIRONMENT_DECISION_SCHEMA_V1,
        }:
            report["incomplete_reasons"].append("decision_eligibility_mask_missing_for_v1_schema")
        if mask_required and candidate_id is not None:
            raw_eligible_ids = decision.get("eligible_trade_setup_ids")
            raw_eligible_count = decision.get("eligible_candidate_count")
            try:
                eligible_values = (
                    list(raw_eligible_ids)
                    if isinstance(raw_eligible_ids, (list, tuple, set))
                    else []
                )
            except (TypeError, ValueError):
                eligible_values = []
                report["incomplete_reasons"].append(
                    "decision_eligibility_mask_is_missing_or_invalid"
                )
            eligible_ids = [_integer(value) for value in eligible_values]
            valid_ids = [value for value in eligible_ids if value is not None]
            valid_mask = (
                len(valid_ids) == len(eligible_ids)
                and len(set(valid_ids)) == len(eligible_ids)
                and all(0 <= value < TRADE_SETUP_CATEGORY_COUNT for value in valid_ids)
                and NO_TRADE_ID in valid_ids
            )
            check(
                "decision_eligibility_mask_is_valid",
                decision_id,
                valid_mask,
                "eligibility mask has invalid, duplicate, out-of-range, or missing no-trade IDs",
            )
            count = _integer(raw_eligible_count)
            check(
                "decision_eligibility_count_matches_mask",
                decision_id,
                count is not None and count == len(eligible_ids),
                "eligible candidate count differs from the recorded mask",
            )
            selected_is_in_mask = valid_mask and candidate_id in eligible_ids
            if _boolean(eligible) is not None:
                check(
                    "selected_candidate_mask_matches_eligibility_flag",
                    decision_id,
                    selected_is_in_mask == truth(eligible),
                    "selected candidate membership differs from its recorded eligibility flag",
                )
            if action in {-1, 1}:
                check(
                    "directional_action_selects_eligible_candidate",
                    decision_id,
                    selected_is_in_mask,
                    "directional action selected a candidate absent from its decision mask",
                )
        if candidate_id is not None:
            if _boolean(eligible) is not None:
                check(
                    "selected_setup_is_eligible_for_entry_action",
                    decision_id,
                    action == 0 or truth(eligible),
                    "an ineligible selected setup produced an entry direction",
                )
            raw_eligible_ids = decision.get("eligible_trade_setup_ids")
            if (
                isinstance(raw_eligible_ids, (list, tuple, set))
                and candidate_id != 0
                and _boolean(eligible) is not None
            ):
                eligible_id_set = {
                    parsed for value in raw_eligible_ids if (parsed := _integer(value)) is not None
                }
                mask_membership_matches_eligibility = (candidate_id in eligible_id_set) == truth(
                    eligible
                )
                check(
                    "selected_setup_mask_membership_matches_eligibility",
                    decision_id,
                    mask_membership_matches_eligibility,
                    "selected setup mask membership disagrees with recorded eligibility",
                )
    for order_id, submit in orders.items():
        linked = order_outcomes.get(order_id, [])
        opens = [event for event in linked if str(event.get("type", "")) == "open"]
        fills = [event for event in linked if str(event.get("type", "")) == "order_fill"]
        cancels = [event for event in linked if str(event.get("type", "")) == "order_cancel"]
        submit_decision = submit.get("decision_id")
        rejects = [event for event in linked if str(event.get("type", "")) == "reject"]
        if opens or cancels or rejects:
            check("submitted_order_has_terminal_outcome", order_id, True, "")
        else:
            report["incomplete_reasons"].append("submitted_order_has_no_terminal_event")
        if len(opens) > 1:
            check(
                "order_opens_at_most_one_position",
                order_id,
                False,
                "one order opened multiple positions",
            )
        if cancels:
            check(
                "cancelled_order_has_no_fill_or_open",
                order_id,
                not fills and not opens,
                "a canceled order later recorded a fill or opened position",
            )
        if str(submit.get("order_type", "market")) == "limit":
            if len(fills) > 1:
                check(
                    "limit_order_fills_at_most_once",
                    order_id,
                    False,
                    "one resting limit order recorded multiple fills",
                )
            if fills and not opens:
                check(
                    "limit_fill_has_matching_open",
                    order_id,
                    False,
                    "a recorded limit fill did not open a position",
                )
            elif opens and not fills:
                check(
                    "limit_open_has_matching_fill",
                    order_id,
                    False,
                    "a position opened without a recorded limit fill",
                )
            elif len(fills) == 1 and len(opens) == 1:
                fill = fills[0]
                opened = opens[0]
                fill_price = _number(fill.get("price"))
                open_price = _number(opened.get("price"))
                fill_time = _timestamp(fill.get("time", fill.get("fill_time")))
                open_time = _timestamp(opened.get("fill_time", opened.get("time")))
                if (
                    fill_price is None
                    or open_price is None
                    or fill_time is None
                    or open_time is None
                ):
                    report["incomplete_reasons"].append("limit_fill_open_link_fields_missing")
                else:
                    check(
                        "limit_fill_matches_open_price_and_time",
                        order_id,
                        math.isclose(fill_price, open_price, rel_tol=0.0, abs_tol=1e-12)
                        and fill_time == open_time,
                        "opened position price or timestamp differs from its limit fill",
                    )
                fill_direction = _integer(fill.get("direction"))
                open_direction = _integer(opened.get("direction"))
                check(
                    "limit_fill_open_direction_matches",
                    order_id,
                    fill_direction in {-1, 1} and open_direction == fill_direction,
                    "opened position direction differs from its limit fill",
                )
        if submit_decision is not None and str(submit_decision) in decision_by_id:
            decision = decision_by_id[str(submit_decision)]
            decision_action = _integer(decision.get("action"))
            submitted_direction = _integer(submit.get("direction"))
            check(
                "submitted_order_decision_is_entry_action",
                order_id,
                decision_action in {-1, 1},
                "an order submission references a no-trade or invalid decision action",
            )
            check(
                "submitted_order_direction_matches_decision",
                order_id,
                decision_action in {-1, 1} and submitted_direction == decision_action,
                "submitted order direction differs from the selected action",
            )
            selected_candidate_id = _integer(decision.get("trade_setup_candidate_id"))
            if selected_candidate_id is not None and truth(decision.get("trade_setup_eligible")):
                expected_source_id = decision.get("trade_setup_source_event_id")
                expected_source_status = decision.get("trade_setup_source_event_identity_status")
                if (
                    str(expected_source_status) == "identified"
                    and isinstance(expected_source_id, str)
                    and expected_source_id
                ):
                    actual_source_id = submit.get("trade_setup_source_event_id")
                    check(
                        "submitted_source_event_matches_decision",
                        order_id,
                        isinstance(actual_source_id, str)
                        and actual_source_id == expected_source_id
                        and str(submit.get("trade_setup_source_event_identity_status"))
                        == "identified",
                        "submitted order source event differs from decision",
                    )
            expected_order_type = decision.get("execution_type")
            if not _is_missing(expected_order_type):
                expected_order_type = str(expected_order_type)
                submitted_order_type = str(submit.get("order_type", "market"))
                check(
                    "submitted_order_type_matches_decision",
                    order_id,
                    submitted_order_type == expected_order_type,
                    f"decision selected {expected_order_type}, order submitted as "
                    f"{submitted_order_type}",
                )
                if expected_order_type == "limit":
                    limit_price = _number(submit.get("limit_price"))
                    submitted_at = _timestamp(submit.get("order_submission_time"))
                    expires_at = _timestamp(submit.get("expiry_time"))
                    check(
                        "limit_order_has_finite_positive_price",
                        order_id,
                        limit_price is not None and limit_price > 0.0,
                        "limit submission has no finite positive limit price",
                    )
                    check(
                        "limit_order_has_positive_lifetime",
                        order_id,
                        submitted_at is not None
                        and expires_at is not None
                        and expires_at > submitted_at,
                        "limit submission has no positive order lifetime",
                    )
                    for cancel in cancels:
                        if str(cancel.get("reason", "")) != "entry_rejected_at_limit_fill":
                            continue
                        trigger_time = _timestamp(cancel.get("trigger_quote_time"))
                        cancel_time = _timestamp(cancel.get("time"))
                        trigger_bid = _number(cancel.get("trigger_quote_bid"))
                        trigger_ask = _number(cancel.get("trigger_quote_ask"))
                        trigger_price = _number(cancel.get("trigger_quote_price"))
                        direction = _integer(submit.get("direction"))
                        if (
                            limit_price is None
                            or submitted_at is None
                            or expires_at is None
                            or trigger_time is None
                            or cancel_time is None
                            or trigger_bid is None
                            or trigger_ask is None
                            or trigger_price is None
                            or direction not in {-1, 1}
                        ):
                            report["incomplete_reasons"].append(
                                "rejected_limit_trigger_quote_fields_missing"
                            )
                            continue
                        executable_price = trigger_ask if direction == 1 else trigger_bid
                        check(
                            "rejected_limit_trigger_quote_is_not_crossed",
                            order_id,
                            trigger_bid <= trigger_ask,
                            "rejected limit trigger records a crossed executable quote",
                        )
                        check(
                            "rejected_limit_trigger_price_matches_quote_side",
                            order_id,
                            math.isclose(
                                trigger_price,
                                executable_price,
                                rel_tol=0.0,
                                abs_tol=1e-12,
                            ),
                            "rejected limit trigger price differs from executable ask/bid",
                        )
                        check(
                            "rejected_limit_trigger_respects_price_and_lifetime",
                            order_id,
                            (
                                executable_price <= limit_price
                                if direction == 1
                                else executable_price >= limit_price
                            )
                            and submitted_at <= trigger_time <= expires_at,
                            "rejected limit trigger is outside its price or time bounds",
                        )
                        check(
                            "rejected_limit_cancel_matches_trigger_time",
                            order_id,
                            cancel_time == trigger_time,
                            "risk-rejected limit cancellation time differs from trigger quote",
                        )
        for linked_event in linked:
            linked_decision = linked_event.get("decision_id")
            if not _is_missing(submit_decision) and not _is_missing(linked_decision):
                check(
                    "order_lifecycle_keeps_decision_id",
                    order_id,
                    str(submit_decision) == str(linked_decision),
                    "order lifecycle changed decision identity",
                )
            linked_type = str(linked_event.get("type", ""))
            submitted_candidate_id = _integer(submit.get("trade_setup_candidate_id"))
            if submitted_candidate_id is not None:
                linked_candidate_id = _integer(linked_event.get("trade_setup_candidate_id"))
                decision = decision_by_id.get(str(submit_decision), {})
                decision_schema = str(decision.get("schema_version", ""))
                if (
                    linked_type == "reject"
                    and linked_candidate_id is None
                    and decision_schema == _DECISION_SCHEMA_V1
                ):
                    report["incomplete_reasons"].append(
                        "rejection_candidate_identity_missing_for_v1_decision"
                    )
                else:
                    check(
                        "order_lifecycle_candidate_matches_submission",
                        order_id,
                        linked_candidate_id == submitted_candidate_id,
                        "order lifecycle candidate differs from its submission",
                    )
            if linked_type in {"order_fill", "order_cancel", "open"}:
                submitted_source_id = submit.get("trade_setup_source_event_id")
                if (
                    str(submit.get("trade_setup_source_event_identity_status")) == "identified"
                    and isinstance(submitted_source_id, str)
                    and submitted_source_id
                ):
                    linked_source_id = linked_event.get("trade_setup_source_event_id")
                    check_name = (
                        "cancelled_event_source_matches_submission"
                        if linked_type == "order_cancel"
                        else "filled_event_source_matches_submission"
                    )
                    check(
                        check_name,
                        order_id,
                        isinstance(linked_source_id, str)
                        and linked_source_id == submitted_source_id
                        and str(linked_event.get("trade_setup_source_event_identity_status"))
                        == "identified",
                        "order lifecycle event changed source event identity",
                    )
            if linked_type == "order_fill":
                submitted_direction = _integer(submit.get("direction"))
                filled_direction = _integer(linked_event.get("direction"))
                if submitted_direction is None or filled_direction is None:
                    report["incomplete_reasons"].append("filled_event_direction_missing")
                else:
                    check(
                        "filled_event_direction_matches_submission",
                        order_id,
                        filled_direction == submitted_direction,
                        "filled direction differs from submitted order direction",
                    )
                if str(submit.get("order_type", "market")) == "limit":
                    limit_price = _number(submit.get("limit_price"))
                    fill_price = _number(linked_event.get("price"))
                    fill_bid = _number(linked_event.get("bid"))
                    fill_ask = _number(linked_event.get("ask"))
                    fill_direction = submitted_direction
                    submitted_at = _timestamp(
                        submit.get("order_submission_time", submit.get("decision_time"))
                    )
                    expires_at = _timestamp(submit.get("expiry_time"))
                    fill_at = _timestamp(linked_event.get("time", linked_event.get("fill_time")))
                    if (
                        limit_price is None
                        or fill_price is None
                        or fill_direction not in {-1, 1}
                        or submitted_at is None
                        or expires_at is None
                        or fill_at is None
                    ):
                        report["incomplete_reasons"].append("limit_fill_contract_fields_missing")
                    else:
                        executable_quote_price = fill_ask if fill_direction == 1 else fill_bid
                        if fill_bid is None or fill_ask is None:
                            report["incomplete_reasons"].append("limit_fill_quote_fields_missing")
                        else:
                            check(
                                "limit_fill_quote_is_not_crossed",
                                order_id,
                                fill_bid <= fill_ask,
                                "limit fill records a crossed executable quote",
                            )
                        if executable_quote_price is None:
                            report["incomplete_reasons"].append(
                                "limit_fill_executable_quote_missing"
                            )
                        elif fill_price is not None:
                            check(
                                "limit_fill_price_matches_executable_quote",
                                order_id,
                                math.isclose(
                                    fill_price,
                                    executable_quote_price,
                                    rel_tol=0.0,
                                    abs_tol=1e-12,
                                ),
                                "limit fill price differs from its executable ask/bid",
                            )
                        if executable_quote_price is not None:
                            check(
                                "limit_fill_respects_price_bound",
                                order_id,
                                (
                                    executable_quote_price <= limit_price
                                    if fill_direction == 1
                                    else executable_quote_price >= limit_price
                                ),
                                "limit fill price crossed its selected price bound",
                            )
                        check(
                            "limit_fill_occurs_inside_lifetime",
                            order_id,
                            submitted_at <= fill_at <= expires_at,
                            "limit fill occurred outside the submitted order lifetime",
                        )

    rollout_reasons = {"daily_loss", "max_drawdown", "trailing_dd"}
    hard_breach_times: list[pd.Timestamp] = []
    if breach_events is None:
        report["incomplete_reasons"].append("breach_event_ledger_not_supplied")
    else:
        for breach_index, breach in enumerate(breach_events):
            if not isinstance(breach, Mapping):
                report["incomplete_reasons"].append("invalid_rollout_breach_record")
                continue
            if breach.get("schema_version") not in {
                RISK_BREACH_EVENT_SCHEMA_V1,
                RISK_BREACH_EVENT_SCHEMA_V2,
            }:
                report["incomplete_reasons"].append(
                    "unsupported_or_missing_rollout_breach_event_schema"
                )
                continue
            reason = str(breach.get("reason", ""))
            detection_time = _timestamp(breach.get("detection_time"))
            raw_event_prefix = _integer(breach.get("trade_event_count"))
            if reason not in rollout_reasons:
                report["incomplete_reasons"].append("invalid_rollout_breach_record")
                continue
            if detection_time is None:
                report["incomplete_reasons"].append("rollout_breach_detection_time_missing")
            else:
                hard_breach_times.append(detection_time)
            if raw_event_prefix is None or not 0 <= raw_event_prefix <= len(events):
                report["incomplete_reasons"].append(
                    "rollout_breach_event_prefix_missing_or_invalid"
                )
                continue
            event_prefix = int(raw_event_prefix)
            for event_index, event in enumerate(events):
                event_type = str(event.get("type", ""))
                if event_type not in {"order_submit", "order_fill", "open"}:
                    continue
                event_id = str(event.get("order_id", event.get("position_id", "")))
                is_before_detection = event_index < event_prefix
                check_name = {
                    "order_submit": "no_order_submission_after_rollout_breach",
                    "order_fill": "no_order_fill_after_rollout_breach",
                    "open": "no_position_open_after_rollout_breach",
                }[event_type]
                check(
                    check_name,
                    f"breach-{breach_index}:{event_id}",
                    is_before_detection,
                    "an order submission, fill, or open followed the hard evaluation breach",
                )
                if detection_time is None:
                    continue
                event_time = _first_timestamp(
                    event,
                    *(
                        ("order_submission_time", "decision_time", "time")
                        if event_type == "order_submit"
                        else ("fill_time", "time")
                    ),
                )
                if event_time is None:
                    report["incomplete_reasons"].append(
                        {
                            "order_submit": "submitted_order_time_missing",
                            "order_fill": "filled_order_time_missing",
                            "open": "opened_position_time_missing",
                        }[event_type]
                    )
                    continue
                check(
                    "entry_event_timestamp_matches_breach_prefix",
                    f"breach-{breach_index}:{event_id}:{event_index}",
                    (
                        event_time <= detection_time
                        if is_before_detection
                        else event_time >= detection_time
                    ),
                    "entry timestamp contradicts event order relative to breach detection",
                )

    for record in _records(decisions):
        if str(record.get("schema_version", "")) not in {
            _DECISION_SCHEMA,
            *_ENVIRONMENT_DECISION_SCHEMAS,
        }:
            continue
        decision_id = str(record.get("decision_id", ""))
        direction_at_decision = _integer(record.get("position_direction_at_decision"))
        position_id_value = record.get("position_id_at_decision")
        decision_position_id = None if _is_missing(position_id_value) else str(position_id_value)
        if direction_at_decision is None:
            report["incomplete_reasons"].append("decision_position_direction_is_invalid")
        elif direction_at_decision == 0:
            check(
                "flat_decision_has_no_position_id",
                decision_id,
                decision_position_id is None,
                "flat decision unexpectedly references a position",
            )
        else:
            position = positions.get(decision_position_id or "")
            decision_time = _timestamp(record.get("decision_time"))
            decision_event_prefix = _integer(record.get("trade_event_start_index"))
            position_open_time = (
                None
                if position is None
                else _timestamp(position.get("time", position.get("fill_time")))
            )
            terminal_times = [
                _timestamp(event.get("fill_time", event.get("time")))
                for event in position_terminal_events.get(decision_position_id or "", [])
                if _position_complete(event) is True
            ]
            if (
                schema_version in _ENVIRONMENT_DECISION_SCHEMAS
                and decision_event_prefix is not None
            ):
                # Older environment traces timestamp decisions at the bar label;
                # the completed-bar contract records the actual decision boundary.
                decision_phase_time = (
                    None
                    if decision_time is None
                    else (
                        decision_time + pd.Timedelta(minutes=1)
                        if schema_version == _ENVIRONMENT_DECISION_SCHEMA_BAR_LABEL
                        else decision_time
                    )
                )
                open_event_index = position_open_event_indices.get(decision_position_id or "")
                terminal_indices = position_terminal_event_indices.get(
                    decision_position_id or "", []
                )
                has_prior_terminal = any(
                    index < decision_event_prefix for index in terminal_indices
                )
                open_precedes_phase = (
                    open_event_index is not None
                    and open_event_index < decision_event_prefix
                    and decision_phase_time is not None
                    and position_open_time is not None
                    and position_open_time <= decision_phase_time
                )
                is_live_at_decision = (
                    position is not None
                    and _integer(position.get("direction")) == direction_at_decision
                    and open_precedes_phase
                    and not has_prior_terminal
                )
            else:
                is_live_at_decision = (
                    position is not None
                    and _integer(position.get("direction")) == direction_at_decision
                    and decision_time is not None
                    and position_open_time is not None
                    and position_open_time <= decision_time
                    and all(
                        terminal_time is not None and terminal_time > decision_time
                        for terminal_time in terminal_times
                    )
                )
            check(
                "decision_position_is_live_at_decision",
                decision_id,
                is_live_at_decision,
                "decision position context is absent or not live at the decision timestamp",
            )
        pending_order_value = record.get("pending_order_id_at_decision")
        if not _is_missing(pending_order_value):
            pending_order_id_for_context = str(pending_order_value)
            pending_submit = orders.get(pending_order_id_for_context)
            check(
                "decision_pending_order_context_resolves",
                decision_id,
                pending_submit is not None,
                "decision pending order context has no order submission",
            )
            if pending_submit is not None:
                decision_time = (
                    _timestamp(record.get("decision_time"))
                    if str(record.get("schema_version", ""))
                    == _ENVIRONMENT_DECISION_SCHEMA_COMPLETED_BAR
                    else _timestamp(record.get("decision_bar_time", record.get("decision_time")))
                )
                submission_time = _timestamp(
                    pending_submit.get("order_submission_time", pending_submit.get("decision_time"))
                )
                terminal_events = [
                    event
                    for event in order_outcomes.get(pending_order_id_for_context, [])
                    if str(event.get("type", "")) in {"order_fill", "order_cancel", "open"}
                ]
                terminal_times = [
                    _timestamp(event.get("time", event.get("fill_time")))
                    for event in terminal_events
                ]
                check(
                    "decision_pending_order_is_live_at_decision",
                    decision_id,
                    decision_time is not None
                    and submission_time is not None
                    and submission_time <= decision_time
                    and all(
                        terminal_time is not None and terminal_time > decision_time
                        for terminal_time in terminal_times
                    ),
                    "pending order is unresolved or not live at the decision timestamp",
                )

    candidate_column = decisions.get(
        "trade_setup_candidate_id", pd.Series(index=decisions.index, dtype=float)
    )
    selected_candidate_indices: list[Any] = []
    for index, value in candidate_column.items():
        if _is_missing(value):
            continue
        candidate_id = _integer(value)
        if candidate_id is None:
            report["incomplete_reasons"].append("selected_candidate_id_is_invalid")
        else:
            check(
                "selected_candidate_id_is_in_domain",
                candidate_id,
                0 <= candidate_id < TRADE_SETUP_CATEGORY_COUNT,
                "selected candidate id is outside the trade-setup catalog",
            )
            selected_candidate_indices.append(index)
    decisions_with_selected_candidates = decisions.loc[selected_candidate_indices]
    for record in _records(decisions_with_selected_candidates):
        decision_id = str(record["decision_id"])
        candidate_id = _integer(record["trade_setup_candidate_id"])
        if candidate_id is None:
            report["incomplete_reasons"].append("selected_candidate_id_is_invalid")
            continue
        eligible = record.get("trade_setup_eligible")
        action = _integer(record.get("action"))
        if _is_missing(eligible):
            report["incomplete_reasons"].append("selected_candidate_eligibility_missing")
        linked_orders = order_submits_by_decision.get(decision_id, [])
        linked_rejections = rejections_by_decision.get(decision_id, [])
        for rejected in linked_rejections:
            rejected_candidate_id = _integer(rejected.get("trade_setup_candidate_id"))
            if rejected_candidate_id is None and str(record.get("schema_version", "")) == (
                _DECISION_SCHEMA_V1
            ):
                report["incomplete_reasons"].append(
                    "rejection_candidate_identity_missing_for_v1_decision"
                )
            else:
                check(
                    "rejected_candidate_matches_decision",
                    decision_id,
                    rejected_candidate_id == candidate_id,
                    "rejection is missing or references a different selected candidate",
                )
            expected_source_status = record.get("trade_setup_source_event_identity_status")
            expected_source_id = record.get("trade_setup_source_event_id")
            if str(expected_source_status) == "identified":
                if str(record.get("schema_version", "")) == _DECISION_SCHEMA_V1 and not isinstance(
                    rejected.get("trade_setup_source_event_id"), str
                ):
                    report["incomplete_reasons"].append(
                        "rejection_source_identity_missing_for_v1_decision"
                    )
                else:
                    check(
                        "rejected_source_event_matches_decision",
                        decision_id,
                        isinstance(expected_source_id, str)
                        and isinstance(rejected.get("trade_setup_source_event_id"), str)
                        and rejected.get("trade_setup_source_event_id") == expected_source_id
                        and str(rejected.get("trade_setup_source_event_identity_status"))
                        == "identified",
                        "rejection source event differs from the selected decision setup",
                    )
        if _boolean(eligible) is False:
            check(
                "ineligible_setup_never_submits",
                decision_id,
                not linked_orders,
                "an ineligible candidate submitted an order",
            )
            check(
                "ineligible_setup_has_rejection_record",
                decision_id,
                bool(linked_rejections),
                "an ineligible selected setup has no linked rejection record",
            )
        if action in {-1, 1} and truth(eligible):
            source_event_id = record.get("trade_setup_source_event_id")
            source_identity_status = record.get("trade_setup_source_event_identity_status")
            if (
                str(source_identity_status) != "identified"
                or not isinstance(source_event_id, str)
                or not source_event_id
            ):
                report["incomplete_reasons"].append("eligible_setup_source_identity_missing")
            for submit in linked_orders:
                event_candidate = submit.get("trade_setup_candidate_id")
                check(
                    "submitted_candidate_matches_decision",
                    decision_id,
                    _integer(event_candidate) == candidate_id,
                    "submitted candidate differs from decision",
                )
        if action == 0:
            check(
                "no_trade_decision_never_submits",
                decision_id,
                not linked_orders,
                "a no-trade decision submitted an order",
            )

    for record in _records(decisions):
        decision_id = str(record.get("decision_id", ""))
        action = _integer(record.get("action"))
        linked_rejections = rejections_by_decision.get(decision_id, [])
        for rejected in linked_rejections:
            rejected_direction = _integer(rejected.get("direction"))
            if rejected_direction is None:
                report["incomplete_reasons"].append("rejection_direction_missing")
            else:
                expected_direction = action
                rejection_decision = decision_by_id.get(decision_id, {})
                candidate_direction = _integer(rejection_decision.get("trade_setup_direction"))
                if (
                    candidate_direction in {-1, 1}
                    and _integer(rejection_decision.get("trade_setup_candidate_id"))
                    not in {None, 0}
                    and not truth(rejection_decision.get("trade_setup_eligible"))
                ):
                    expected_direction = candidate_direction
                check(
                    "rejection_direction_matches_decision",
                    decision_id,
                    expected_direction in {-1, 0, 1} and rejected_direction == expected_direction,
                    "rejection direction differs from selected action",
                )
        if action not in {-1, 1}:
            continue
        linked_orders = order_submits_by_decision.get(decision_id, [])
        if linked_orders or linked_rejections or opens_by_decision.get(decision_id):
            continue
        schema_version = str(record.get("schema_version", ""))
        decision_time = (
            _timestamp(record.get("decision_time"))
            if schema_version == _ENVIRONMENT_DECISION_SCHEMA_COMPLETED_BAR
            else _first_timestamp(record, "decision_bar_time", "decision_time")
        )
        if decision_time is not None and any(
            decision_time >= breach_time for breach_time in hard_breach_times
        ):
            # After a hard account breach, a directional policy output is
            # terminally blocked by the risk guard. The order/open checks above
            # still fail if execution evidence appears after that breach.
            continue
        if str(record.get("schema_version", "")) not in {
            _DECISION_SCHEMA,
            *_ENVIRONMENT_DECISION_SCHEMAS,
        }:
            report["incomplete_reasons"].append(
                "entry_action_outcome_context_missing_for_v1_decision"
            )
            continue
        direction_at_decision = _integer(record.get("position_direction_at_decision"))
        raw_pending_order_id = record.get("pending_order_id_at_decision")
        final_pending_order_id = (
            None if _is_missing(raw_pending_order_id) else str(raw_pending_order_id)
        )
        pending_order = orders.get(final_pending_order_id or "")
        held_pending_direction = (
            pending_order is not None and _integer(pending_order.get("direction")) == action
        )
        check(
            "entry_action_has_order_rejection_or_hold",
            decision_id,
            direction_at_decision == action or held_pending_direction,
            (
                "entry action referenced a pending order with a different or unresolved direction"
                if final_pending_order_id is not None and not held_pending_direction
                else "entry action had no order, rejection, or same-direction position"
            ),
        )

    report["checks"] = checks
    report["failure_count"] = len(failures)
    report["failures"] = failures[:100]
    report["unclosed_position_ids"] = sorted(active_positions)
    if active_positions:
        report["incomplete_reasons"].append("position_ledger_ends_with_open_positions")
    if failures:
        report["status"] = "mismatch"
    elif report["incomplete_reasons"]:
        report["status"] = "incomplete"
    else:
        report["status"] = "matched"
    return report


__all__ = ["POLICY_DECISION_RECONCILIATION_SCHEMA", "reconcile_policy_decisions"]
