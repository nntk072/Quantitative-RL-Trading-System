"""Reconcile recorded decisions, fills, and completed positions by position ID."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from typing import Any

_CLOSE_TYPES = {
    "close",
    "eod_close",
    "forced_close",
    "stop_close",
    "tp_close",
    "tp_partial_close",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames is None:
            if path.stat().st_size == 0:
                return [], []
            raise ValueError(f"CSV has no header: {path}")
        return list(reader.fieldnames), list(reader)


def _number(value: str | None) -> float | None:
    if not value:
        return None
    try:
        number = float(value)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def _payout_reconciliation(
    payout_header: list[str],
    payout_rows: list[dict[str, str]],
    evaluation_diagnostics: dict[str, Any],
    total_economic_values: list[float],
) -> dict[str, Any]:
    """Reconcile payout rows with reset amounts and reported economic value."""
    checks: Counter[str] = Counter()
    failures: Counter[str] = Counter()
    required = {"type", "time", "cycle", "payout", "balance_before_reset", "operating_balance"}
    missing = sorted(required.difference(payout_header)) if payout_rows else []
    payout_values = [_number(row.get("payout")) for row in payout_rows]
    payout_sum = (
        sum(value for value in payout_values if value is not None)
        if all(value is not None for value in payout_values)
        else None
    )
    status = "incomplete"
    if missing:
        status = "incomplete"
    elif payout_rows:
        cycles: list[int] = []
        event_times: list[datetime] = []
        for row, payout in zip(payout_rows, payout_values, strict=True):
            if row.get("type") != "payout_reset":
                failures["payout_event_type_is_reset_failed"] += 1
                continue
            checks["payout_event_type_is_reset"] += 1
            raw_cycle = _number(row.get("cycle"))
            if raw_cycle is None or not raw_cycle.is_integer():
                failures["payout_cycle_is_integer_failed"] += 1
            else:
                cycles.append(int(raw_cycle))
            event_time = _timestamp(row.get("time"))
            if event_time is None:
                failures["payout_event_time_is_timezone_aware_failed"] += 1
            else:
                event_times.append(event_time)
            before = _number(row.get("balance_before_reset"))
            operating = _number(row.get("operating_balance"))
            if (
                payout is None
                or before is None
                or operating is None
                or payout <= 0
                or operating <= 0
            ):
                failures["payout_amount_matches_balance_reset_failed"] += 1
            elif math.isclose(before - operating, payout, rel_tol=1e-9, abs_tol=1e-7):
                checks["payout_amount_matches_balance_reset"] += 1
            else:
                failures["payout_amount_matches_balance_reset_failed"] += 1
        if cycles:
            if cycles == list(range(1, len(cycles) + 1)):
                checks["payout_cycles_are_sequential"] += 1
            else:
                failures["payout_cycles_are_sequential_failed"] += 1
        if len(event_times) == len(payout_rows):
            if event_times == sorted(event_times):
                checks["payout_times_are_ordered"] += 1
            else:
                failures["payout_times_are_ordered_failed"] += 1
        status = "matched"
    elif payout_header:
        status = "matched"
    else:
        status = "not_applicable"

    reported_payouts = _number(str(evaluation_diagnostics.get("cumulative_payouts", "")))
    reported_successes = _number(str(evaluation_diagnostics.get("cycle_successes", "")))
    reported_total_value = _number(str(evaluation_diagnostics.get("total_economic_value", "")))
    if payout_rows or evaluation_diagnostics:
        if payout_sum is None:
            status = "incomplete"
        elif reported_payouts is None or reported_successes is None:
            status = "incomplete"
        else:
            if math.isclose(payout_sum, reported_payouts, rel_tol=1e-9, abs_tol=1e-7):
                checks["payout_sum_matches_reported_cumulative"] += 1
            else:
                failures["payout_sum_matches_reported_cumulative_failed"] += 1
            if reported_successes.is_integer() and int(reported_successes) == len(payout_rows):
                checks["payout_rows_match_cycle_successes"] += 1
            else:
                failures["payout_rows_match_cycle_successes_failed"] += 1
        if total_economic_values:
            if reported_total_value is None:
                status = "incomplete"
            elif math.isclose(
                total_economic_values[-1], reported_total_value, rel_tol=1e-9, abs_tol=1e-6
            ):
                checks["economic_value_curve_matches_reported_total"] += 1
            else:
                failures["economic_value_curve_matches_reported_total_failed"] += 1
    if failures:
        status = "mismatch"
    elif status not in {"incomplete", "not_applicable"}:
        status = "matched"

    return {
        "status": status,
        "event_rows": len(payout_rows),
        "payout_sum": payout_sum,
        "reported_cumulative_payouts": reported_payouts,
        "reported_cycle_successes": reported_successes,
        "reported_total_economic_value": reported_total_value,
        "ending_total_economic_value_curve": (
            total_economic_values[-1] if total_economic_values else None
        ),
        "checks": dict(sorted(checks.items())),
        "failures": dict(sorted(failures.items())),
        "failure_count": sum(failures.values()),
        "missing_columns": missing,
    }


def _cycle_reconciliation(
    cycle_header: list[str],
    cycle_rows: list[dict[str, str]],
    payout_rows: list[dict[str, str]],
    breach_header: list[str],
    breach_rows: list[dict[str, str]],
    evaluation_diagnostics: dict[str, Any],
) -> dict[str, Any]:
    """Reconcile cycle-success/failure events with payouts and run counters."""
    checks: Counter[str] = Counter()
    failures: Counter[str] = Counter()
    required = {"type", "time", "cycle", "outcome"}
    missing = sorted(required.difference(cycle_header)) if cycle_rows else []
    success_rows: dict[int, dict[str, str]] = {}
    failure_rows: dict[int, dict[str, str]] = {}
    missing_failure_link_columns: dict[str, list[str]] = {}
    event_times: list[datetime] = []
    cycle_ids: list[int] = []

    if missing:
        status = "incomplete"
    elif cycle_rows:
        status = "matched"
        for row in cycle_rows:
            outcome = row.get("outcome")
            event_type = row.get("type")
            if (outcome, event_type) == ("success", "payout_reset"):
                destination = success_rows
                checks["cycle_success_has_payout_reset_type"] += 1
            elif (outcome, event_type) == ("failure", "cycle_failure"):
                destination = failure_rows
                checks["cycle_failure_has_failure_type"] += 1
            else:
                failures["cycle_outcome_matches_event_type_failed"] += 1
                continue
            raw_cycle = _number(row.get("cycle"))
            if raw_cycle is None or not raw_cycle.is_integer() or raw_cycle <= 0:
                failures["cycle_id_is_positive_integer_failed"] += 1
                continue
            cycle = int(raw_cycle)
            if cycle in success_rows or cycle in failure_rows:
                failures["cycle_has_one_terminal_outcome_failed"] += 1
            destination[cycle] = row
            cycle_ids.append(cycle)
            event_time = _timestamp(row.get("time"))
            if event_time is None:
                failures["cycle_event_time_is_timezone_aware_failed"] += 1
            else:
                event_times.append(event_time)
        if cycle_ids and cycle_ids != list(range(1, len(cycle_ids) + 1)):
            failures["cycle_ids_are_sequential_failed"] += 1
        elif cycle_ids:
            checks["cycle_ids_are_sequential"] += 1
        if len(event_times) == len(cycle_rows) and event_times == sorted(event_times):
            checks["cycle_event_times_are_ordered"] += 1
        elif len(event_times) == len(cycle_rows):
            failures["cycle_event_times_are_ordered_failed"] += 1
        if failure_rows and max(failure_rows) != max(cycle_ids):
            failures["cycle_failure_is_terminal_failed"] += 1
    else:
        status = "not_applicable"

    reported_successes = _number(str(evaluation_diagnostics.get("cycle_successes", "")))
    reported_failures = _number(str(evaluation_diagnostics.get("cycle_failures", "")))
    reported_cycle_count = _number(str(evaluation_diagnostics.get("cycle_count", "")))
    if cycle_rows or evaluation_diagnostics.get("trading_policy_mode") == "repeated_payout":
        if reported_successes is None or reported_failures is None or reported_cycle_count is None:
            status = "incomplete"
        else:
            counts_match = (
                reported_successes.is_integer()
                and reported_failures.is_integer()
                and int(reported_successes) == len(success_rows)
                and int(reported_failures) == len(failure_rows)
            )
            if counts_match:
                checks["cycle_events_match_reported_outcomes"] += 1
            else:
                failures["cycle_events_match_reported_outcomes_failed"] += 1
            if cycle_ids:
                terminal_cycle = max(cycle_ids)
                expected_count = terminal_cycle if failure_rows else terminal_cycle + 1
            else:
                expected_count = 1
            if reported_cycle_count.is_integer() and int(reported_cycle_count) == expected_count:
                checks["cycle_count_matches_terminal_events"] += 1
            else:
                failures["cycle_count_matches_terminal_events_failed"] += 1
        if len(success_rows) != len(payout_rows):
            failures["cycle_successes_match_payout_rows_failed"] += 1
        else:
            for payout in payout_rows:
                raw_cycle = _number(payout.get("cycle"))
                if raw_cycle is None or not raw_cycle.is_integer():
                    failures["cycle_successes_match_payout_rows_failed"] += 1
                    continue
                cycle_row = success_rows.get(int(raw_cycle))
                same_event = cycle_row is not None and all(
                    cycle_row.get(key) == payout.get(key)
                    for key in ("cycle", "payout", "balance_before_reset", "operating_balance")
                )
                payout_time = _timestamp(payout.get("time"))
                cycle_time = _timestamp(None if cycle_row is None else cycle_row.get("time"))
                if same_event and payout_time == cycle_time:
                    checks["cycle_successes_match_payout_rows"] += 1
                else:
                    failures["cycle_successes_match_payout_rows_failed"] += 1
        if failure_rows:
            missing_cycle_failure = sorted({"reason", "equity"}.difference(cycle_header))
            required_breach = {"time", "reason", "equity"}
            missing_breach = sorted(required_breach.difference(breach_header))
            if missing_cycle_failure:
                missing_failure_link_columns["cycle_events.csv"] = missing_cycle_failure
            if missing_breach:
                missing_failure_link_columns["breach_events.csv"] = missing_breach
            if missing_cycle_failure or missing_breach:
                status = "incomplete"
            else:
                unmatched_breaches = list(breach_rows)
                for cycle_failure in failure_rows.values():
                    cycle_time = _timestamp(cycle_failure.get("time"))
                    cycle_equity = _number(cycle_failure.get("equity"))
                    match_index = next(
                        (
                            index
                            for index, breach in enumerate(unmatched_breaches)
                            if _timestamp(breach.get("time")) == cycle_time
                            and breach.get("reason") == cycle_failure.get("reason")
                            and (breach_equity := _number(breach.get("equity"))) is not None
                            and cycle_equity is not None
                            and math.isclose(
                                breach_equity, cycle_equity, rel_tol=1e-9, abs_tol=1e-7
                            )
                        ),
                        None,
                    )
                    if match_index is None:
                        failures["cycle_failures_match_breach_events_failed"] += 1
                    else:
                        unmatched_breaches.pop(match_index)
                        checks["cycle_failures_match_breach_events"] += 1

    if failures:
        status = "mismatch"
    elif status not in {"incomplete", "not_applicable"}:
        status = "matched"
    return {
        "status": status,
        "event_rows": len(cycle_rows),
        "success_rows": len(success_rows),
        "failure_rows": len(failure_rows),
        "reported_cycle_count": reported_cycle_count,
        "checks": dict(sorted(checks.items())),
        "failures": dict(sorted(failures.items())),
        "failure_count": sum(failures.values()),
        "missing_columns": missing,
        "missing_failure_link_columns": missing_failure_link_columns,
    }


def summarize_trade_lifecycle(run_dir: Path) -> dict[str, Any]:
    """Build a descriptive, position-ID-based reconciliation from recorded CSVs."""
    paths = {name: run_dir / name for name in ("trades.csv", "fills.csv", "positions.csv")}
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Required lifecycle inputs are missing: {missing}")

    trades_header, trades = _read_csv(paths["trades.csv"])
    fills_header, fills = _read_csv(paths["fills.csv"])
    positions_header, positions = _read_csv(paths["positions.csv"])
    metrics_path = run_dir / "metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.is_file() else {}
    payout_paths = [run_dir / name for name in ("payouts.csv", "payout_events.csv")]
    existing_payout_paths = [path for path in payout_paths if path.is_file()]
    if len(existing_payout_paths) > 1:
        raise ValueError(
            "Run directory has both payout ledger names; retain one canonical source: "
            f"{[path.name for path in existing_payout_paths]}"
        )
    payouts_path = existing_payout_paths[0] if existing_payout_paths else payout_paths[0]
    payout_header: list[str] = []
    payout_rows: list[dict[str, str]] = []
    if payouts_path.is_file():
        payout_header, payout_rows = _read_csv(payouts_path)
    cycle_events_path = run_dir / "cycle_events.csv"
    cycle_header: list[str] = []
    cycle_rows: list[dict[str, str]] = []
    if cycle_events_path.is_file():
        cycle_header, cycle_rows = _read_csv(cycle_events_path)
    breach_events_path = run_dir / "breach_events.csv"
    breach_header: list[str] = []
    breach_rows: list[dict[str, str]] = []
    if breach_events_path.is_file():
        breach_header, breach_rows = _read_csv(breach_events_path)
    diagnostics_path = run_dir / "evaluation_diagnostics.json"
    evaluation_diagnostics = (
        json.loads(diagnostics_path.read_text(encoding="utf-8"))
        if diagnostics_path.is_file()
        else {}
    )
    total_economic_value_path = run_dir / "total_economic_value.csv"
    total_economic_values: list[float] = []
    if total_economic_value_path.is_file():
        value_header, value_rows = _read_csv(total_economic_value_path)
        if "total_economic_value" in value_header:
            total_economic_values = [
                value
                for row in value_rows
                if (value := _number(row.get("total_economic_value"))) is not None
            ]
    required = {
        "trades.csv": {"type", "entry_rejection_reason", "position_id"},
        "fills.csv": {
            "type",
            "position_id",
            "time",
            "decision_time",
            "order_submission_time",
            "fill_time",
            "net_pnl",
        },
        "positions.csv": {
            "position_id",
            "entry_time",
            "exit_time",
            "holding_seconds",
            "exit_reason",
            "net_pnl",
            "fill_count",
            "completed",
        },
    }
    for name, header in (
        ("trades.csv", trades_header),
        ("fills.csv", fills_header),
        ("positions.csv", positions_header),
    ):
        absent = required[name].difference(header)
        if absent:
            raise ValueError(f"{name} lacks required columns: {sorted(absent)}")

    decision_types = Counter(row.get("type", "") for row in trades)
    rejection_reasons = Counter(
        row["entry_rejection_reason"] for row in trades if row.get("entry_rejection_reason")
    )
    events_by_position: dict[str, list[dict[str, str]]] = defaultdict(list)
    for fill in fills:
        position_id = fill.get("position_id", "")
        if position_id:
            events_by_position[position_id].append(fill)

    fill_type_counts = Counter(row.get("type", "") for row in fills)
    exit_reasons = Counter(row.get("exit_reason", "") for row in positions)
    holding_seconds = [
        value for row in positions if (value := _number(row.get("holding_seconds"))) is not None
    ]
    lifecycle_checks: Counter[str] = Counter()
    lifecycle_check_failures: Counter[str] = Counter()
    timestamp_order_checks: Counter[str] = Counter()
    pnl_checks: Counter[str] = Counter()
    decision_submission_seconds: list[float] = []
    opening_fill_count = 0
    unlinked_fill_ids = set(events_by_position).difference(
        row.get("position_id", "") for row in positions
    )
    linked_fill_count = 0
    for position in positions:
        position_id = position.get("position_id", "")
        events = events_by_position.get(position_id, [])
        linked_fill_count += len(events)
        opens = [event for event in events if event.get("type") == "open"]
        closes = [event for event in events if event.get("type") in _CLOSE_TYPES]
        opening_fill_count += len(opens)
        if len(opens) == 1 and closes:
            lifecycle_checks["one_open_and_at_least_one_close"] += 1
        elif position.get("completed", "").casefold() == "true":
            lifecycle_check_failures["completed_position_requires_one_open_and_a_close"] += 1
        if position.get("completed", "").casefold() == "true":
            lifecycle_checks["position_marked_complete"] += 1
        if _number(position.get("fill_count")) == len(events):
            lifecycle_checks["fill_count_matches_event_rows"] += 1
        else:
            lifecycle_check_failures["fill_count_matches_event_rows"] += 1

        if opens and closes:
            ordered_closes = sorted(
                closes,
                key=lambda event: _timestamp(event.get("time")) or datetime.min.replace(tzinfo=UTC),
            )
            opening_time = _timestamp(opens[0].get("fill_time") or opens[0].get("time"))
            exit_time = _timestamp(position.get("exit_time"))
            final_close_event_time = _timestamp(ordered_closes[-1].get("time"))
            entry_time = _timestamp(position.get("entry_time"))
            if opening_time and entry_time and opening_time == entry_time:
                lifecycle_checks["open_fill_matches_position_entry_time"] += 1
            if final_close_event_time and exit_time and final_close_event_time == exit_time:
                lifecycle_checks["last_close_event_time_matches_position_exit_time"] += 1

        for event in opens:
            decision = _timestamp(event.get("decision_time"))
            submission = _timestamp(event.get("order_submission_time"))
            fill_time = _timestamp(event.get("fill_time") or event.get("time"))
            if decision and submission:
                decision_submission_seconds.append((submission - decision).total_seconds())
            if decision and submission and fill_time:
                if decision <= submission <= fill_time:
                    timestamp_order_checks["decision_le_submission_le_fill"] += 1
                else:
                    timestamp_order_checks["decision_le_submission_le_fill_failed"] += 1
            else:
                timestamp_order_checks["decision_le_submission_le_fill_unavailable"] += 1

        position_net_pnl = _number(position.get("net_pnl"))
        close_net_pnl = [_number(event.get("net_pnl")) for event in closes]
        if position_net_pnl is not None and all(value is not None for value in close_net_pnl):
            if math.isclose(
                sum(value for value in close_net_pnl if value is not None),
                position_net_pnl,
                rel_tol=1e-9,
                abs_tol=1e-7,
            ):
                pnl_checks["close_fill_net_pnl_matches_position"] += 1
            else:
                pnl_checks["close_fill_net_pnl_matches_position_failed"] += 1

    position_pnls = [_number(row.get("net_pnl")) for row in positions]
    position_net_pnl_sum = (
        sum(value for value in position_pnls if value is not None)
        if all(value is not None for value in position_pnls)
        else None
    )
    reported_total_pnl = _number(str(metrics.get("total_pnl", "")))
    aggregate_pnl_reconciliation: dict[str, Any] = {
        "status": "unavailable",
        "position_net_pnl_sum": position_net_pnl_sum,
        "reported_total_pnl": reported_total_pnl,
    }
    if position_net_pnl_sum is not None and reported_total_pnl is not None:
        difference = position_net_pnl_sum - reported_total_pnl
        matched = math.isclose(difference, 0.0, rel_tol=1e-9, abs_tol=1e-6)
        aggregate_pnl_reconciliation.update(
            {"status": "matched" if matched else "mismatch", "difference": difference}
        )
        if matched:
            pnl_checks["position_net_pnl_matches_reported_total"] += 1
        else:
            pnl_checks["position_net_pnl_matches_reported_total_failed"] += 1

    initial_balance = _number(str(metrics.get("initial_balance", "")))
    final_equity = _number(str(metrics.get("final_equity", "")))
    completed_positions = all(row.get("completed", "").casefold() == "true" for row in positions)
    payout_reconciliation = _payout_reconciliation(
        payout_header,
        payout_rows,
        evaluation_diagnostics,
        total_economic_values,
    )
    cycle_reconciliation = _cycle_reconciliation(
        cycle_header,
        cycle_rows,
        payout_rows,
        breach_header,
        breach_rows,
        evaluation_diagnostics,
    )
    account_equity_reconciliation: dict[str, Any] = {
        "status": "unavailable",
        "initial_balance": initial_balance,
        "final_equity": final_equity,
        "position_net_pnl_sum": position_net_pnl_sum,
        "payout_event_rows": len(payout_rows),
        "payout_sum": payout_reconciliation["payout_sum"],
    }
    if (
        initial_balance is not None
        and final_equity is not None
        and position_net_pnl_sum is not None
        and completed_positions
        and payout_reconciliation["payout_sum"] is not None
    ):
        difference = (
            initial_balance
            + position_net_pnl_sum
            - final_equity
            - float(payout_reconciliation["payout_sum"])
        )
        matched = math.isclose(difference, 0.0, rel_tol=1e-9, abs_tol=1e-6)
        account_equity_reconciliation.update(
            {
                "status": "matched" if matched else "mismatch",
                "difference": difference,
                "basis": (
                    "initial balance + completed position net PnL = final account equity "
                    "+ recorded payouts"
                ),
            }
        )
        pnl_checks[
            "initial_plus_position_net_pnl_matches_final_equity"
            if matched
            else "initial_plus_position_net_pnl_matches_final_equity_failed"
        ] += 1
    integrity_failures = (
        sum(lifecycle_check_failures.values())
        + sum(value for key, value in pnl_checks.items() if key.endswith("_failed"))
        + sum(value for key, value in timestamp_order_checks.items() if key.endswith("_failed"))
        + int(payout_reconciliation["failure_count"])
        + int(cycle_reconciliation["failure_count"])
    )
    integrity_failures += len(unlinked_fill_ids)
    positions_complete = all(row.get("completed", "").casefold() == "true" for row in positions)
    if integrity_failures:
        integrity_status = "failed"
    elif (
        positions_complete
        and aggregate_pnl_reconciliation["status"] == "matched"
        and account_equity_reconciliation["status"] == "matched"
        and payout_reconciliation["status"] in {"matched", "not_applicable"}
        and cycle_reconciliation["status"] in {"matched", "not_applicable"}
        and not lifecycle_check_failures
        and not unlinked_fill_ids
        and not any(key.endswith("_failed") for key in timestamp_order_checks)
        and timestamp_order_checks["decision_le_submission_le_fill"] == opening_fill_count
        and lifecycle_checks["one_open_and_at_least_one_close"] == len(positions)
        and pnl_checks["close_fill_net_pnl_matches_position"] == len(positions)
    ):
        integrity_status = "matched"
    else:
        integrity_status = "incomplete"

    source_files = {
        name: {"path": path.as_posix(), "sha256": _sha256(path), "bytes": path.stat().st_size}
        for name, path in paths.items()
    }
    for optional_name, optional_path in (
        ("metrics.json", metrics_path),
        (payouts_path.name, payouts_path),
        ("cycle_events.csv", cycle_events_path),
        ("breach_events.csv", breach_events_path),
        ("evaluation_diagnostics.json", diagnostics_path),
        ("total_economic_value.csv", total_economic_value_path),
    ):
        if optional_path.is_file():
            source_files[optional_name] = {
                "path": optional_path.as_posix(),
                "sha256": _sha256(optional_path),
                "bytes": optional_path.stat().st_size,
            }
    source_manifest_path = run_dir.parent / "reanalysis_manifest.json"
    source_manifest: dict[str, Any] = {}
    if source_manifest_path.is_file():
        source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
        source_files["reanalysis_manifest.json"] = {
            "path": source_manifest_path.as_posix(),
            "sha256": _sha256(source_manifest_path),
            "bytes": source_manifest_path.stat().st_size,
        }
    available_columns = {
        "trades.csv": sorted(set(trades_header).intersection({"mfe", "mae", "MFE", "MAE"})),
        "fills.csv": sorted(set(fills_header).intersection({"mfe", "mae", "MFE", "MAE"})),
        "positions.csv": sorted(set(positions_header).intersection({"mfe", "mae", "MFE", "MAE"})),
    }
    entry_times = [
        timestamp
        for row in positions
        if (timestamp := _timestamp(row.get("entry_time"))) is not None
    ]
    exit_times = [
        timestamp
        for row in positions
        if (timestamp := _timestamp(row.get("exit_time"))) is not None
    ]
    return {
        "scope": {
            "run_directory": run_dir.as_posix(),
            "partition_name": run_dir.name,
            "position_time_range_utc": {
                "start": min(entry_times).isoformat() if entry_times else None,
                "end": max(exit_times).isoformat() if exit_times else None,
            },
            "evidence_role": "descriptive reconciliation of recorded events",
            "causal_attribution": False,
            "historical_holdout_inspected": source_manifest.get("historical_holdout_inspected"),
            "seed": source_manifest.get("seed"),
            "source_run": source_manifest.get("source_run"),
            "source_config_sha256": source_manifest.get("source_config_sha256"),
            "checkpoint_sha256": source_manifest.get("checkpoint_sha256"),
        },
        "inputs": source_files,
        "counts": {
            "decision_rows": len(trades),
            "decision_event_types": dict(sorted(decision_types.items())),
            "entry_rejection_reasons": dict(sorted(rejection_reasons.items())),
            "fill_event_rows": len(fills),
            "fill_event_types": dict(sorted(fill_type_counts.items())),
            "positions": len(positions),
            "positions_with_linked_fill_events": len(
                set(row.get("position_id", "") for row in positions).intersection(
                    events_by_position
                )
            ),
            "unlinked_fill_position_ids": len(unlinked_fill_ids),
            "completed_positions": sum(
                row.get("completed", "").casefold() == "true" for row in positions
            ),
            "positions_with_holding_seconds": len(holding_seconds),
        },
        "lifecycle_checks": dict(sorted(lifecycle_checks.items())),
        "lifecycle_check_failures": dict(sorted(lifecycle_check_failures.items())),
        "decision_order_checks": dict(sorted(timestamp_order_checks.items())),
        "decision_to_submission_seconds": {
            "count": len(decision_submission_seconds),
            "minimum": min(decision_submission_seconds) if decision_submission_seconds else None,
            "median": median(decision_submission_seconds) if decision_submission_seconds else None,
            "maximum": max(decision_submission_seconds) if decision_submission_seconds else None,
        },
        "pnl_reconciliation_checks": dict(sorted(pnl_checks.items())),
        "aggregate_pnl_reconciliation": aggregate_pnl_reconciliation,
        "account_equity_reconciliation": account_equity_reconciliation,
        "payout_reconciliation": payout_reconciliation,
        "cycle_reconciliation": cycle_reconciliation,
        "integrity_status": integrity_status,
        "integrity_failure_count": integrity_failures,
        "holding_seconds": {
            "mean": (sum(holding_seconds) / len(holding_seconds)) if holding_seconds else None,
            "median": median(holding_seconds) if holding_seconds else None,
        },
        "exit_reasons": dict(sorted(exit_reasons.items())),
        "mfe_mae_columns": available_columns,
        "limitations": [
            "Recorded decision/order/fill timestamps reconcile logged events but do not establish authoritative feed chronology or executable quote availability.",
            "Decision-to-submission gaps are descriptive; they may reflect bar-label versus completed-bar availability semantics rather than agent or network latency.",
            "Candidate detection and eligibility before recorded policy decisions are not fully linked by these CSVs.",
            "Per-position MFE and MAE are not present in the required source columns and are not derived by this report.",
            "Payout and total-economic-value reconciliation requires the recorded payout ledger and evaluation diagnostics; missing source fields are reported as incomplete.",
            "Repeated-payout cycle outcomes reconcile against payout, breach, and diagnostic ledgers when the corresponding events occur; missing linkage fields remain incomplete.",
            "This report is descriptive and does not identify causal loss mechanisms or economic superiority.",
        ],
    }


def _render_markdown(report: dict[str, Any]) -> str:
    counts = report["counts"]
    holding = report["holding_seconds"]
    scope = report["scope"]
    holdout_inspection = scope["historical_holdout_inspected"]
    if holdout_inspection is True:
        holdout_note = "The source manifest marks the associated holdout as previously inspected."
    elif holdout_inspection is False:
        holdout_note = (
            "The source manifest does not mark the associated holdout as previously inspected."
        )
    else:
        holdout_note = "Holdout-inspection status is not available in the source manifest."
    lines = [
        "# Selected policy trade lifecycle",
        "",
        f"This is a descriptive reconciliation of decision, fill, and position records in the `{scope['partition_name']}` partition. {holdout_note} It makes no causal or economic-superiority claim.",
        "",
        "## Coverage",
        "",
        f"- Recorded policy/action rows: {counts['decision_rows']:,}",
        f"- Recorded fill-event rows: {counts['fill_event_rows']:,}",
        f"- Completed positions: {counts['completed_positions']:,} / {counts['positions']:,}",
        f"- Positions with linked fill events: {counts['positions_with_linked_fill_events']:,}",
        f"- Unlinked fill position IDs: {counts['unlinked_fill_position_ids']:,}",
        f"- Positions with holding duration: {counts['positions_with_holding_seconds']:,}",
        f"- Recorded position window (UTC): {scope['position_time_range_utc']['start']} to {scope['position_time_range_utc']['end']}",
        f"- Mean / median recorded holding seconds: {holding['mean']} / {holding['median']}",
        "",
        "### Decision event types",
        "",
    ]
    lines.extend(
        f"- `{key}`: {value:,}" for key, value in report["counts"]["decision_event_types"].items()
    )
    lines.extend(["", "### Position exit reasons", ""])
    lines.extend(f"- `{key}`: {value:,}" for key, value in report["exit_reasons"].items())
    lines.extend(
        [
            "",
            "## Reconciliation checks",
            "",
            "```json",
            json.dumps(
                {
                    "lifecycle_checks": report["lifecycle_checks"],
                    "lifecycle_check_failures": report["lifecycle_check_failures"],
                    "decision_order_checks": report["decision_order_checks"],
                    "decision_to_submission_seconds": report["decision_to_submission_seconds"],
                    "pnl_reconciliation_checks": report["pnl_reconciliation_checks"],
                    "aggregate_pnl_reconciliation": report["aggregate_pnl_reconciliation"],
                    "account_equity_reconciliation": report["account_equity_reconciliation"],
                    "payout_reconciliation": report["payout_reconciliation"],
                    "cycle_reconciliation": report["cycle_reconciliation"],
                    "integrity_status": report["integrity_status"],
                    "integrity_failure_count": report["integrity_failure_count"],
                },
                indent=2,
                sort_keys=True,
            ),
            "```",
            "",
            "## Limits",
            "",
        ]
    )
    lines.extend(f"- {limitation}" for limitation in report["limitations"])
    lines.extend(
        ["", "Input hashes and source paths are recorded in `evidence_manifest.json`.", ""]
    )
    return "\n".join(lines)


def write_report(run_dir: Path, output_dir: Path) -> dict[str, Any]:
    report = summarize_trade_lifecycle(run_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "selected_policy_trade_lifecycle.json"
    markdown_path = output_dir / "selected_policy_trade_lifecycle.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(_render_markdown(report), encoding="utf-8")
    manifest = {
        "analysis_script": {
            "path": Path(__file__)
            .resolve()
            .relative_to(Path(__file__).resolve().parents[4])
            .as_posix(),
            "sha256": _sha256(Path(__file__).resolve()),
        },
        "report_files": {path.name: _sha256(path) for path in (json_path, markdown_path)},
        "input_files": report["inputs"],
        "reproduction": (
            "python scripts/research/analysis/evaluation/summarize_policy_trade_lifecycle.py "
            f"--run-dir {run_dir.as_posix()} --output-dir {output_dir.as_posix()}"
        ),
    }
    (output_dir / "evidence_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-dir", type=Path, required=True, help="Directory containing the three source CSVs"
    )
    parser.add_argument(
        "--output-dir", type=Path, required=True, help="Directory for semantic report files"
    )
    args = parser.parse_args()
    report = write_report(args.run_dir, args.output_dir)
    print(
        json.dumps(
            {
                "positions": report["counts"]["positions"],
                "linked_positions": report["counts"]["positions_with_linked_fill_events"],
                "output_dir": args.output_dir.as_posix(),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
