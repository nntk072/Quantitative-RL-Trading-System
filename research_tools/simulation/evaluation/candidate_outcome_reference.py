"""Independent, array-level reference replay for candidate outcomes.

This audit path intentionally does not call the production candidate replay or
TickBook execution resolvers. It supports the current evidence contract with
zero randomized fill latency and fails closed when that contract changes.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any

import numpy as np
import pandas as pd

OUTCOME_SCHEMA = "candidate-conditional-outcome-v2"
TIME_FIELDS = (
    "evaluated_until",
    "order_expires_at",
    "fill_time",
    "exit_time",
)
NUMERIC_FIELDS = ("fill_price", "exit_price", "net_r")
COMPARE_FIELDS = (
    "status",
    "evaluated_until",
    "order_expires_at",
    "fill_time",
    "fill_price",
    "exit_time",
    "exit_price",
    "exit_reason",
    "net_r",
    "unresolved_reason",
    "outcome_id",
    "schema_version",
    "estimand",
)


def _timestamp(value: Any, name: str) -> pd.Timestamp:
    result = pd.Timestamp(value)
    if result.tz is None:
        raise ValueError(f"{name} must be timezone-aware")
    return result.tz_convert("UTC")


def _iso(value: pd.Timestamp | None) -> str | None:
    return None if value is None else value.isoformat()


def _identity(proposal_id: str, stop_choice: str, target_choice: str) -> str:
    identity = {
        "proposal_id": proposal_id,
        "stop_choice": stop_choice,
        "target_choice": target_choice,
        "schema_version": OUTCOME_SCHEMA,
    }
    digest = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return f"co2-{digest[:24]}"


def _record(
    *,
    proposal_id: str,
    status: str,
    evaluated_until: pd.Timestamp,
    expires: pd.Timestamp,
    stop_choice: str,
    target_choice: str,
    fill_time: pd.Timestamp | None = None,
    fill_price: float | None = None,
    exit_time: pd.Timestamp | None = None,
    exit_price: float | None = None,
    exit_reason: str | None = None,
    net_r: float | None = None,
    unresolved_reason: str | None = None,
) -> dict[str, Any]:
    return {
        "proposal_id": proposal_id,
        "status": status,
        "evaluated_until": _iso(evaluated_until),
        "order_expires_at": _iso(expires),
        "stop_choice": stop_choice,
        "target_choice": target_choice,
        "fill_time": _iso(fill_time),
        "fill_price": fill_price,
        "exit_time": _iso(exit_time),
        "exit_price": exit_price,
        "exit_reason": exit_reason,
        "net_r": net_r,
        "unresolved_reason": unresolved_reason,
        "outcome_id": _identity(proposal_id, stop_choice, target_choice),
        "schema_version": OUTCOME_SCHEMA,
        "estimand": "conditional_fixed_entry",
    }


def _first_quote(
    times: np.ndarray[Any, Any],
    start_ns: int,
    *,
    end_ns_inclusive: int | None = None,
    max_wait_ns: int,
) -> tuple[int, int] | None:
    """Return first quote index and timestamp, applying an independent wait bound."""
    index = int(np.searchsorted(times, start_ns, side="left"))
    if index >= len(times):
        return None
    quote_ns = int(times[index])
    if end_ns_inclusive is not None and quote_ns > end_ns_inclusive:
        return None
    if quote_ns - start_ns > max_wait_ns:
        return None
    return index, quote_ns


def _numeric_match(expected: Any, actual: Any) -> bool:
    if expected is None:
        return bool(pd.isna(actual))
    try:
        value = float(actual)
        return bool(
            np.isfinite(value) and np.isclose(float(expected), value, rtol=1e-12, atol=1e-12)
        )
    except (TypeError, ValueError):
        return False


def _time_match(expected: Any, actual: Any) -> bool:
    if expected is None:
        return bool(pd.isna(actual))
    try:
        return (
            _timestamp(expected, "expected timestamp").value
            == _timestamp(actual, "actual timestamp").value
        )
    except (TypeError, ValueError):
        return False


def independently_replay_outcomes(
    proposals: pd.DataFrame,
    outcomes: pd.DataFrame,
    tick_times_ns: np.ndarray[Any, Any],
    bids: np.ndarray[Any, Any],
    asks: np.ndarray[Any, Any],
    *,
    coverage_cutoffs: dict[str, pd.Timestamp | None],
    training_cutoff: pd.Timestamp,
    slippage_points: float,
    commission_per_lot: float,
    contract_size: float,
    max_quote_wait_ms: int,
    randomized_fill_latency_ms: float,
    limit_require_trade_through: bool,
    server_side_protective_orders: bool = False,
) -> dict[str, Any]:
    """Recompute every outcome row with a separate array-level event model.

    The candidate artifact currently uses deterministic execution (zero
    randomized latency). A nonzero latency setting is rejected rather than
    approximated because its per-event random-key contract must be independently
    added and validated first.
    """
    if randomized_fill_latency_ms != 0.0:
        raise ValueError("independent reference replay requires zero randomized latency")
    if not isinstance(max_quote_wait_ms, int) or max_quote_wait_ms <= 0:
        raise ValueError("max_quote_wait_ms must be a positive integer")
    if not np.isfinite(slippage_points) or slippage_points < 0.0:
        raise ValueError("slippage_points must be finite and non-negative")
    if not np.isfinite(commission_per_lot) or commission_per_lot < 0.0:
        raise ValueError("commission_per_lot must be finite and non-negative")
    if not np.isfinite(contract_size) or contract_size <= 0.0:
        raise ValueError("contract_size must be finite and positive")
    if not (len(tick_times_ns) == len(bids) == len(asks)):
        raise ValueError("TickBook arrays have inconsistent lengths")
    if len(tick_times_ns) and np.any(tick_times_ns[1:] < tick_times_ns[:-1]):
        raise ValueError("TickBook timestamps must be ordered")

    cutoff = _timestamp(training_cutoff, "training_cutoff")
    max_wait_ns = int(max_quote_wait_ms) * 1_000_000
    proposal_records = {
        str(row["proposal_id"]): {str(key): value for key, value in row.items()}
        for row in proposals.to_dict(orient="records")
    }
    if len(proposal_records) != len(proposals):
        raise ValueError("independent replay input contains duplicate proposal IDs")
    actual_records: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in outcomes.to_dict(orient="records"):
        key = (str(row["proposal_id"]), str(row["stop_choice"]), str(row["target_choice"]))
        if key in actual_records:
            raise ValueError("independent replay input contains duplicate outcome keys")
        actual_records[key] = {str(column): value for column, value in row.items()}

    mismatch_fields: Counter[str] = Counter()
    mismatch_rows = 0
    compared_rows = 0
    examples: list[dict[str, str]] = []
    expected_statuses: Counter[str] = Counter()
    quote_wait = max_wait_ns
    for proposal_id, proposal in proposal_records.items():
        direction = int(proposal["direction"])
        entry_type = str(proposal["entry_type"])
        if entry_type not in {"market", "limit"}:
            raise ValueError(f"unsupported independent replay entry type: {entry_type}")
        limit_price = float(proposal["proposed_entry_price"])
        eligible_fill = proposal.get("eligible_action_fill_time")
        if eligible_fill is None or pd.isna(eligible_fill):
            eligible_fill = proposal["valid_from"]
        start = _timestamp(
            eligible_fill,
            "eligible_action_fill_time",
        )
        expiry = _timestamp(proposal["expires_at"], "expires_at")
        session_close = (
            _timestamp(proposal["session_close_time"], "session_close_time")
            if proposal.get("session_close_time") is not None
            and not pd.isna(proposal.get("session_close_time"))
            else None
        )
        horizon = session_close or cutoff
        observed = cutoff
        coverage_gap = coverage_cutoffs.get(proposal_id)
        coverage_horizon = min(cutoff, horizon)
        if (
            coverage_gap is not None
            and _timestamp(coverage_gap, "coverage cutoff") < coverage_horizon
        ):
            observed = min(observed, _timestamp(coverage_gap, "coverage cutoff"))
        order_end = min(expiry, observed)

        fill_time: pd.Timestamp | None = None
        fill_price: float | None = None
        fill_status: str | None = None
        entry_index: int | None = None
        if order_end < start:
            fill_status = "censored_order_horizon"
        elif entry_type == "limit":
            i0 = int(np.searchsorted(tick_times_ns, start.value, side="left"))
            i1 = int(np.searchsorted(tick_times_ns, order_end.value, side="right"))
            if direction == 1:
                qualifies = (
                    asks[i0:i1] < limit_price
                    if limit_require_trade_through
                    else asks[i0:i1] <= limit_price
                )
            else:
                qualifies = (
                    bids[i0:i1] > limit_price
                    if limit_require_trade_through
                    else bids[i0:i1] >= limit_price
                )
            matches = np.flatnonzero(qualifies)
            if matches.size:
                entry_index = i0 + int(matches[0])
                fill_time = pd.Timestamp(int(tick_times_ns[entry_index]), unit="ns", tz="UTC")
                quote_side = asks[entry_index] if direction == 1 else bids[entry_index]
                fill_price = float(
                    min(quote_side, limit_price) if direction == 1 else max(quote_side, limit_price)
                )
                fill_status = "filled"
            else:
                fill_status = "censored_order_horizon" if observed < expiry else "unfilled_expired"
        else:
            entry = _first_quote(
                tick_times_ns,
                start.value,
                max_wait_ns=quote_wait,
            )
            if entry is None or int(tick_times_ns[entry[0]]) > order_end.value:
                fill_status = "unresolved_data"
            else:
                entry_index, entry_ns = entry
                fill_time = pd.Timestamp(entry_ns, unit="ns", tz="UTC")
                quote_side = asks[entry_index] if direction == 1 else bids[entry_index]
                fill_price = float(
                    quote_side + slippage_points if direction == 1 else quote_side - slippage_points
                )
                fill_status = "filled"

        stop_choices = json.loads(proposal["permissible_stop_choices"])
        target_choices = json.loads(proposal["permissible_target_choices"])
        for stop_choice, stop_value in stop_choices:
            stop = float(stop_value)
            for target_choice, target_value in target_choices:
                target = float(target_value)
                key = (proposal_id, str(stop_choice), str(target_choice))
                actual = actual_records.get(key)
                if actual is None:
                    raise ValueError(f"independent replay is missing outcome key {key}")
                if fill_status != "filled" or fill_time is None or fill_price is None:
                    reason = (
                        "market-entry quote unavailable within the configured quote-wait limit"
                        if fill_status == "unresolved_data"
                        else None
                    )
                    status = str(fill_status)
                    if status == "censored_order_horizon" and coverage_gap is not None:
                        status = "unresolved_data"
                        reason = "local two-sided quote coverage is incomplete before order expiry"
                    expected = _record(
                        proposal_id=proposal_id,
                        status=status,
                        evaluated_until=min(observed, expiry),
                        expires=expiry,
                        stop_choice=str(stop_choice),
                        target_choice=str(target_choice),
                        unresolved_reason=reason,
                    )
                elif direction * (fill_price - stop) <= 0.0:
                    expected = _record(
                        proposal_id=proposal_id,
                        status="unresolved_data",
                        evaluated_until=fill_time,
                        expires=expiry,
                        stop_choice=str(stop_choice),
                        target_choice=str(target_choice),
                        fill_time=fill_time,
                        fill_price=fill_price,
                        unresolved_reason="selected stop is not protective relative to the realized entry fill",
                    )
                elif direction * (target - fill_price) <= 0.0:
                    expected = _record(
                        proposal_id=proposal_id,
                        status="unresolved_data",
                        evaluated_until=fill_time,
                        expires=expiry,
                        stop_choice=str(stop_choice),
                        target_choice=str(target_choice),
                        fill_time=fill_time,
                        fill_price=fill_price,
                        unresolved_reason="selected target is not beyond the realized entry fill",
                    )
                elif session_close is not None and fill_time >= session_close:
                    expected = _record(
                        proposal_id=proposal_id,
                        status="unresolved_data",
                        evaluated_until=fill_time,
                        expires=expiry,
                        stop_choice=str(stop_choice),
                        target_choice=str(target_choice),
                        fill_time=fill_time,
                        fill_price=fill_price,
                        unresolved_reason="entry fill occurred at or after the configured session close",
                    )
                else:
                    end = min(observed, cutoff, horizon)
                    close_observed = (
                        session_close is not None
                        and session_close <= horizon
                        and session_close <= observed
                    )
                    if end < fill_time:
                        expected = _record(
                            proposal_id=proposal_id,
                            status="unresolved_data",
                            evaluated_until=fill_time,
                            expires=expiry,
                            stop_choice=str(stop_choice),
                            target_choice=str(target_choice),
                            fill_time=fill_time,
                            fill_price=fill_price,
                            unresolved_reason="entry fill occurred after the declared exit observation horizon",
                        )
                    elif end == fill_time:
                        status = "censored_exit_horizon"
                        reason = None
                        if coverage_gap is not None:
                            status = "unresolved_data"
                            reason = "local two-sided quote coverage is incomplete before exit resolution"
                        expected = _record(
                            proposal_id=proposal_id,
                            status=status,
                            evaluated_until=end,
                            expires=expiry,
                            stop_choice=str(stop_choice),
                            target_choice=str(target_choice),
                            fill_time=fill_time,
                            fill_price=fill_price,
                            unresolved_reason=reason,
                        )
                    else:
                        left = int(np.searchsorted(tick_times_ns, fill_time.value, side="left"))
                        right = int(np.searchsorted(tick_times_ns, end.value, side="left"))
                        exit_side = bids if direction == 1 else asks
                        prices = exit_side[left:right]
                        if direction == 1:
                            stop_hit = prices <= stop
                            target_hit = prices >= target
                        else:
                            stop_hit = prices >= stop
                            target_hit = prices <= target
                        hits = np.flatnonzero(stop_hit | target_hit)
                        if hits.size:
                            trigger_local = int(hits[0])
                            trigger_index = left + trigger_local
                            trigger_kind = "sl" if stop_hit[trigger_local] else "tp"
                            trigger_ns = int(tick_times_ns[trigger_index])
                            # Attached server-side protection triggers on the exact
                            # source-ordered quote that first crosses its level.
                            quote_index = (
                                trigger_index
                                if server_side_protective_orders
                                else int(np.searchsorted(tick_times_ns, trigger_ns, side="left"))
                            )
                            if (
                                quote_index >= len(tick_times_ns)
                                or int(tick_times_ns[quote_index]) - trigger_ns > quote_wait
                            ):
                                status = "unresolved_data"
                                reason = (
                                    f"{trigger_kind.upper()} triggered at "
                                    f"{pd.Timestamp(trigger_ns, unit='ns', tz='UTC')}, but no timely quote "
                                    "exists after its sampled order-arrival time"
                                )
                                expected = _record(
                                    proposal_id=proposal_id,
                                    status=status,
                                    evaluated_until=end,
                                    expires=expiry,
                                    stop_choice=str(stop_choice),
                                    target_choice=str(target_choice),
                                    fill_time=fill_time,
                                    fill_price=fill_price,
                                    unresolved_reason=reason,
                                )
                            else:
                                exit_time = pd.Timestamp(
                                    int(tick_times_ns[quote_index]), unit="ns", tz="UTC"
                                )
                                exit_quote = float(
                                    bids[quote_index] - slippage_points
                                    if direction == 1
                                    else asks[quote_index] + slippage_points
                                )
                                risk_points = abs(fill_price - stop)
                                net_r = direction * (exit_quote - fill_price) / risk_points - (
                                    2.0 * commission_per_lot / (contract_size * risk_points)
                                )
                                expected = _record(
                                    proposal_id=proposal_id,
                                    status="filled_resolved",
                                    evaluated_until=exit_time,
                                    expires=expiry,
                                    stop_choice=str(stop_choice),
                                    target_choice=str(target_choice),
                                    fill_time=fill_time,
                                    fill_price=fill_price,
                                    exit_time=exit_time,
                                    exit_price=exit_quote,
                                    exit_reason=trigger_kind,
                                    net_r=float(net_r),
                                )
                        elif close_observed and session_close is not None:
                            submission = session_close - pd.Timedelta(minutes=1)
                            closing_quote = _first_quote(
                                tick_times_ns,
                                submission.value,
                                end_ns_inclusive=session_close.value,
                                max_wait_ns=quote_wait,
                            )
                            if closing_quote is None:
                                status = "unresolved_data"
                                reason = "no timely executable quote for the forced session close"
                                evaluated_until = session_close
                                close_time = session_close
                                close_price = None
                                net_r = None
                            else:
                                close_index, close_ns = closing_quote
                                close_time = pd.Timestamp(close_ns, unit="ns", tz="UTC")
                                if close_time < fill_time:
                                    status = "unresolved_data"
                                    reason = "session-close execution quote predates the entry fill"
                                    evaluated_until = session_close
                                    close_price = None
                                    net_r = None
                                else:
                                    status = "filled_resolved"
                                    reason = None
                                    evaluated_until = close_time
                                    close_price = float(
                                        bids[close_index] - slippage_points
                                        if direction == 1
                                        else asks[close_index] + slippage_points
                                    )
                                    risk_points = abs(fill_price - stop)
                                    net_r = direction * (close_price - fill_price) / risk_points - (
                                        2.0 * commission_per_lot / (contract_size * risk_points)
                                    )
                            expected = _record(
                                proposal_id=proposal_id,
                                status=status,
                                evaluated_until=evaluated_until,
                                expires=expiry,
                                stop_choice=str(stop_choice),
                                target_choice=str(target_choice),
                                fill_time=fill_time,
                                fill_price=fill_price,
                                exit_time=close_time if status == "filled_resolved" else None,
                                exit_price=close_price if status == "filled_resolved" else None,
                                exit_reason="session_close"
                                if status == "filled_resolved"
                                else None,
                                net_r=net_r if status == "filled_resolved" else None,
                                unresolved_reason=reason,
                            )
                        else:
                            status = "censored_exit_horizon"
                            reason = None
                            if coverage_gap is not None:
                                status = "unresolved_data"
                                reason = "local two-sided quote coverage is incomplete before exit resolution"
                            expected = _record(
                                proposal_id=proposal_id,
                                status=status,
                                evaluated_until=end,
                                expires=expiry,
                                stop_choice=str(stop_choice),
                                target_choice=str(target_choice),
                                fill_time=fill_time,
                                fill_price=fill_price,
                                unresolved_reason=reason,
                            )

                expected_statuses[str(expected["status"])] += 1
                compared_rows += 1
                mismatched = []
                for field in COMPARE_FIELDS:
                    expected_value = expected[field]
                    actual_value = actual.get(field)
                    if field in NUMERIC_FIELDS:
                        field_matches = _numeric_match(expected_value, actual_value)
                    elif field in TIME_FIELDS:
                        field_matches = _time_match(expected_value, actual_value)
                    elif expected_value is None:
                        field_matches = bool(pd.isna(actual_value))
                    else:
                        field_matches = str(expected_value) == str(actual_value)
                    if not field_matches:
                        mismatch_fields[field] += 1
                        mismatched.append(field)
                if mismatched:
                    mismatch_rows += 1
                    if len(examples) < 10:
                        examples.append(
                            {
                                "outcome_id": str(actual.get("outcome_id")),
                                "fields": ",".join(mismatched),
                            }
                        )

    if compared_rows != len(outcomes):
        raise ValueError(
            f"independent replay compared {compared_rows} rows; packet has {len(outcomes)}"
        )
    return {
        "status": "verified" if mismatch_rows == 0 else "mismatch",
        "rows_checked": compared_rows,
        "mismatch_rows": mismatch_rows,
        "mismatch_fields": dict(sorted(mismatch_fields.items())),
        "expected_status_counts": dict(sorted(expected_statuses.items())),
        "first_mismatch_examples": examples,
        "scope": "all status, time, fill, exit, reason, and return fields independently recomputed from ordered TickBook arrays; zero randomized latency",
    }
