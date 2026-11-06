#!/usr/bin/env python3
"""Independently reconcile matched setup baseline decisions and account ledgers."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_PARTIAL_CLOSE_TYPES = {"tp_partial_close"}
_TERMINAL_CLOSE_TYPES = {"close", "stop_close", "eod_close", "forced_close"}
_TOLERANCE = 1e-6


def _sha256(path: Path) -> str:
    """Hash a file using bounded memory."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json(path: Path) -> dict[str, Any]:
    """Read one JSON object and reject other top-level values."""
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


def _number(value: object) -> float | None:
    """Parse a finite numeric value or return unavailable."""
    try:
        result = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _timestamp(value: object) -> datetime | None:
    """Parse an ISO timestamp only when it declares a timezone."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(UTC) if parsed.tzinfo is not None else None


def _candidate_id(value: object) -> int | None:
    """Parse an integer-valued candidate identifier."""
    number = _number(value)
    if number is None or not number.is_integer():
        return None
    return int(number)


def _read_decisions(path: Path) -> tuple[list[dict[str, str]], dict[str, dict[str, str]]]:
    """Read decision rows and index unique decision IDs."""
    rows: list[dict[str, str]] = []
    by_id: dict[str, dict[str, str]] = {}
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        required = {
            "decision_id",
            "trade_setup_candidate_id",
            "eligible_trade_setup_ids",
            "trade_setup_eligible",
            "decision_time",
        }
        missing = required.difference(reader.fieldnames or ())
        if missing:
            raise ValueError(f"decision trace is missing columns: {sorted(missing)}")
        for row in reader:
            rows.append(row)
            decision_id = row["decision_id"].strip()
            if decision_id and decision_id not in by_id:
                by_id[decision_id] = row
            elif decision_id:
                by_id[decision_id] = {}
    return rows, by_id


def _eligible_ids(value: str) -> set[int] | None:
    """Parse the serialized candidate eligibility list."""
    try:
        decoded = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(decoded, list):
        return None
    parsed = {_candidate_id(item) for item in decoded}
    if None in parsed:
        return None
    return {int(item) for item in parsed if item is not None}


def _read_ledger(path: Path) -> list[dict[str, str]]:
    """Read event rows needed for decision, position, and cashflow checks."""
    required = {
        "type",
        "decision_id",
        "position_id",
        "fill_id",
        "trade_setup_candidate_id",
        "trade_setup_source_event_id",
        "trade_setup_event_identity_version",
        "trade_setup_source_event_identity_status",
        "direction",
        "time",
        "order_submission_time",
        "fill_time",
        "price",
        "sl_price",
        "tp_price",
        "net_pnl",
        "position_net_pnl",
    }
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames:
            raise ValueError(f"event ledger has no header: {path}")
        missing = required.difference(reader.fieldnames)
        rows = list(reader)
        if not rows and missing:
            return []
        if missing:
            raise ValueError(f"event ledger is missing columns: {sorted(missing)}")
        return rows


def _audit_arm(
    *,
    arm: str,
    arm_dir: Path,
    initial_balance: float,
    common_decision_ids: list[str] | None,
    common_input_hashes: dict[str, str] | None,
) -> tuple[dict[str, Any], list[str], dict[str, str]]:
    """Reconcile one arm's decision links, realized cashflows, and summary metrics."""
    decisions_path = arm_dir / "decisions.csv"
    ledger_path = arm_dir / "trade_fill_event_ledger.csv"
    equity_path = arm_dir / "equity.csv"
    metrics_path = arm_dir / "metrics.json"
    evaluation_path = arm_dir / "evaluation.json"
    metadata_path = arm_dir / "policy_metadata.json"
    decisions, decisions_by_id = _read_decisions(decisions_path)
    ledger = _read_ledger(ledger_path)
    metrics = _json(metrics_path)
    evaluation = _json(evaluation_path)
    metadata = _json(metadata_path)
    failures: list[str] = []
    checks: Counter[str] = Counter()

    decision_ids = [row.get("decision_id", "").strip() for row in decisions]
    if any(not decision_id for decision_id in decision_ids):
        failures.append("decision_id_missing")
    if len(set(decision_ids)) != len(decision_ids):
        failures.append("decision_id_duplicate")
    if common_decision_ids is not None and decision_ids != common_decision_ids:
        failures.append("decision_sequence_differs_from_matched_arms")
    else:
        checks["decision_rows_have_unique_ids_and_match_arms"] += 1

    input_hashes = metadata.get("input_hashes")
    if not isinstance(input_hashes, dict) or not input_hashes:
        failures.append("input_hashes_missing")
        input_hashes = {}
    elif common_input_hashes is not None and input_hashes != common_input_hashes:
        failures.append("input_hashes_differ_from_matched_arms")
    else:
        checks["input_hashes_match_across_arms"] += 1

    opens = [row for row in ledger if row.get("type") == "open"]
    opens_without_scalar_target = 0
    partial_closes = [row for row in ledger if row.get("type") in _PARTIAL_CLOSE_TYPES]
    terminal_closes = [row for row in ledger if row.get("type") in _TERMINAL_CLOSE_TYPES]
    unknown_closes = [
        row
        for row in ledger
        if row.get("type", "").endswith("_close")
        and row.get("type") not in _PARTIAL_CLOSE_TYPES | _TERMINAL_CLOSE_TYPES
    ]
    if unknown_closes:
        failures.append("unclassified_close_event_type")

    opened_by_position: dict[str, dict[str, str]] = {}
    for row in opens:
        position_id = row.get("position_id", "").strip()
        if not position_id or position_id in opened_by_position:
            failures.append("open_position_id_missing_or_duplicate")
            continue
        opened_by_position[position_id] = row

        decision_id = row.get("decision_id", "").strip()
        decision = decisions_by_id.get(decision_id)
        if decision is None or not decision:
            failures.append("open_has_missing_or_duplicate_decision_id")
            continue
        open_candidate = _candidate_id(row.get("trade_setup_candidate_id"))
        selected_candidate = _candidate_id(decision.get("trade_setup_candidate_id"))
        eligible = _eligible_ids(decision.get("eligible_trade_setup_ids", ""))
        if open_candidate is None or open_candidate != selected_candidate:
            failures.append("open_candidate_differs_from_selected_candidate")
        elif eligible is None or open_candidate not in eligible:
            failures.append("opened_candidate_not_in_decision_eligibility_set")
        elif decision.get("trade_setup_eligible", "").casefold() != "true":
            failures.append("opened_decision_not_marked_eligible")
        else:
            checks["open_candidate_matches_selected_eligible_decision"] += 1

        for field in (
            "trade_setup_source_event_id",
            "trade_setup_event_identity_version",
            "trade_setup_source_event_identity_status",
        ):
            if row.get(field, "") != decision.get(field, ""):
                failures.append(f"open_{field}_differs_from_decision")
        direction = _number(row.get("direction"))
        decision_direction = _number(decision.get("direction"))
        if direction is None or decision_direction is None or direction != decision_direction:
            failures.append("open_direction_differs_from_decision")

        decision_time = _timestamp(decision.get("decision_time"))
        submission_time = _timestamp(row.get("order_submission_time"))
        fill_time = _timestamp(row.get("fill_time"))
        if (
            decision_time is None
            or submission_time is None
            or fill_time is None
            or not decision_time <= submission_time <= fill_time
        ):
            failures.append("decision_submission_fill_chronology_invalid")
        else:
            checks["decision_submission_fill_chronology"] += 1
        price = _number(row.get("price"))
        stop = _number(row.get("sl_price"))
        target = _number(row.get("tp_price"))
        if price is None or stop is None:
            failures.append("open_entry_price_or_stop_missing")
        elif direction is not None and (
            (direction > 0 and stop >= price) or (direction < 0 and stop <= price)
        ):
            failures.append("open_stop_is_not_on_protective_side")
        else:
            checks["open_stop_is_on_protective_side"] += 1
        if target is None or target == 0.0:
            opens_without_scalar_target += 1
        elif price is None or direction is None:
            failures.append("defined_target_has_no_entry_price_or_direction")
        elif (
            target < 0.0
            or (direction > 0 and target <= price)
            or (direction < 0 and target >= price)
        ):
            failures.append("defined_target_is_not_on_favorable_side")
        else:
            checks["defined_target_is_on_favorable_side"] += 1

    closes_by_position: dict[str, list[dict[str, str]]] = defaultdict(list)
    terminal_count_by_position: Counter[str] = Counter()
    fill_ids: list[str] = []
    for row in partial_closes + terminal_closes:
        position_id = row.get("position_id", "").strip()
        if not position_id:
            failures.append("close_position_id_missing")
            continue
        closes_by_position[position_id].append(row)
        if row.get("type") in _TERMINAL_CLOSE_TYPES:
            terminal_count_by_position[position_id] += 1
        fill_id = row.get("fill_id", "").strip()
        if not fill_id:
            failures.append("close_fill_id_missing")
        else:
            fill_ids.append(fill_id)
        if _number(row.get("net_pnl")) is None:
            failures.append("close_net_pnl_missing_or_nonfinite")
    if len(set(fill_ids)) != len(fill_ids):
        failures.append("close_fill_id_duplicate")

    if set(opened_by_position) != set(terminal_count_by_position):
        failures.append("opened_and_terminally_closed_position_sets_differ")
    else:
        checks["all_open_positions_have_terminal_close"] += 1
    if any(count != 1 for count in terminal_count_by_position.values()):
        failures.append("position_has_other_than_one_terminal_close")

    total_realized = 0.0
    position_pnl_mismatch_count = 0
    for position_id, event_rows in closes_by_position.items():
        event_pnl_values = [_number(row.get("net_pnl")) for row in event_rows]
        if any(value is None for value in event_pnl_values):
            continue
        position_pnl = sum(float(value) for value in event_pnl_values if value is not None)
        total_realized += position_pnl
        terminal_rows = [row for row in event_rows if row.get("type") in _TERMINAL_CLOSE_TYPES]
        if len(terminal_rows) == 1:
            terminal_total = _number(terminal_rows[0].get("position_net_pnl"))
            if terminal_total is None or not math.isclose(
                position_pnl, terminal_total, rel_tol=1e-9, abs_tol=_TOLERANCE
            ):
                position_pnl_mismatch_count += 1
    if position_pnl_mismatch_count:
        failures.append("position_cashflows_do_not_match_terminal_position_pnl")
    else:
        checks["position_cashflows_match_terminal_position_pnl"] += len(terminal_closes)

    metrics_total_pnl = _number(metrics.get("total_pnl"))
    if metrics_total_pnl is None or not math.isclose(
        total_realized, metrics_total_pnl, rel_tol=1e-9, abs_tol=_TOLERANCE
    ):
        failures.append("realized_cashflows_do_not_match_metrics_total_pnl")
    else:
        checks["realized_cashflows_match_metrics_total_pnl"] += 1

    if int(metrics.get("n_trades", -1)) != len(opens):
        failures.append("open_positions_do_not_match_metrics_trade_count")
    else:
        checks["open_positions_match_metrics_trade_count"] += 1
    extras = metrics.get("extras", {})
    if isinstance(extras, dict) and _number(extras.get("incomplete_positions")) != 0.0:
        failures.append("metrics_report_incomplete_positions")

    equity_rows: list[float] = []
    with equity_path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or "equity" not in reader.fieldnames:
            raise ValueError(f"equity curve is missing its equity column: {equity_path}")
        for row in reader:
            value = _number(row.get("equity"))
            if value is None:
                failures.append("equity_curve_contains_nonfinite_value")
                continue
            equity_rows.append(value)
    if len(equity_rows) < 2:
        failures.append("equity_curve_too_short")
        ending_equity = None
    else:
        if not math.isclose(equity_rows[0], initial_balance, rel_tol=1e-9, abs_tol=_TOLERANCE):
            failures.append("equity_curve_start_differs_from_initial_balance")
        ending_equity = equity_rows[-1]
        expected_end = initial_balance + total_realized
        if not math.isclose(ending_equity, expected_end, rel_tol=1e-9, abs_tol=_TOLERANCE):
            failures.append("initial_balance_plus_realized_cashflows_differs_from_final_equity")
        else:
            checks["initial_balance_plus_realized_cashflows_matches_final_equity"] += 1
        total_return_pct = (ending_equity / equity_rows[0] - 1.0) * 100.0
        reported_return = _number(metrics.get("total_return_pct"))
        if reported_return is None or not math.isclose(
            total_return_pct, reported_return, rel_tol=1e-9, abs_tol=_TOLERANCE
        ):
            failures.append("equity_total_return_differs_from_metrics")
        else:
            checks["equity_total_return_matches_metrics"] += 1
        peak = equity_rows[0]
        maximum_drawdown = 0.0
        for value in equity_rows[1:]:
            peak = max(peak, value)
            maximum_drawdown = max(maximum_drawdown, (peak - value) / peak)
        reported_drawdown = _number(metrics.get("max_drawdown"))
        if reported_drawdown is None or not math.isclose(
            maximum_drawdown, reported_drawdown, rel_tol=1e-9, abs_tol=_TOLERANCE
        ):
            failures.append("equity_max_drawdown_differs_from_metrics")
        else:
            checks["equity_max_drawdown_matches_metrics"] += 1
        expected_steps = _number(evaluation.get("n_steps"))
        if expected_steps is None or not expected_steps.is_integer():
            failures.append("evaluation_step_count_missing")
        elif int(expected_steps) != len(decisions) or int(expected_steps) != len(equity_rows) - 1:
            failures.append("decision_or_equity_rows_differ_from_evaluation_steps")
        else:
            checks["decision_and_equity_rows_match_evaluation_steps"] += 1

    breach_events = evaluation.get("breach_events")
    if not isinstance(breach_events, list) or int(metrics.get("breach_count", -1)) != len(
        breach_events
    ):
        failures.append("breach_events_do_not_match_metrics_count")
    else:
        checks["breach_events_match_metrics_count"] += 1

    for code in input_hashes:
        if not isinstance(code, str):
            failures.append("input_hash_key_invalid")

    result = {
        "arm": arm,
        "status": "failed" if failures else "passed",
        "decision_count": len(decisions),
        "open_count": len(opens),
        "opens_without_scalar_target": opens_without_scalar_target,
        "partial_close_count": len(partial_closes),
        "terminal_close_count": len(terminal_closes),
        "distinct_closed_positions": len(closes_by_position),
        "close_fill_id_count": len(fill_ids),
        "initial_balance": initial_balance,
        "realized_net_pnl": total_realized,
        "ending_equity": ending_equity,
        "breach_event_count": len(breach_events) if isinstance(breach_events, list) else None,
        "input_hashes": input_hashes,
        "checks": dict(sorted(checks.items())),
        "failures": sorted(set(failures)),
    }
    return result, decision_ids, input_hashes


def audit_bundle(bundle_dir: Path) -> dict[str, Any]:
    """Audit all runs in one immutable matched setup baseline bundle."""
    bundle_dir = bundle_dir.resolve()
    manifest_path = bundle_dir / "result_manifest.json"
    manifest = _json(manifest_path)
    config = _json(bundle_dir / "resolved_config.json")
    account = config.get("account")
    if not isinstance(account, dict):
        raise ValueError("resolved_config.json must declare an account object")
    initial_balance = _number(account.get("initial_balance"))
    runs = manifest.get("runs")
    if initial_balance is None or not isinstance(runs, list) or not runs:
        raise ValueError("bundle needs a finite initial balance and at least one run")
    reports: list[dict[str, Any]] = []
    common_decision_ids: list[str] | None = None
    common_input_hashes: dict[str, str] | None = None
    for run in runs:
        if not isinstance(run, dict):
            raise ValueError("bundle run record must be an object")
        run_id = run.get("run_id")
        if not isinstance(run_id, str):
            raise ValueError("bundle run record is missing run_id")
        run_parts = Path(run_id).parts
        if len(run_parts) != 2 or run_parts[0] != bundle_dir.name:
            raise ValueError(f"run ID is outside the bundle directory: {run_id}")
        arm = run_parts[1]
        arm_dir = (bundle_dir.parent / run_id).resolve()
        try:
            arm_dir.relative_to(bundle_dir)
        except ValueError as exc:
            raise ValueError(f"run path escapes the bundle: {run_id}") from exc
        artifact_map: dict[str, dict[str, str]] = {}
        for artifact in run.get("artifacts", []):
            if not isinstance(artifact, dict):
                raise ValueError(f"invalid artifact record in {run_id}")
            path_value = artifact.get("path")
            digest_value = artifact.get("sha256")
            role_value = artifact.get("role")
            if (
                not isinstance(path_value, str)
                or not isinstance(digest_value, str)
                or not isinstance(role_value, str)
            ):
                raise ValueError(f"incomplete artifact record in {run_id}")
            path = (bundle_dir.parent / path_value).resolve()
            try:
                path.relative_to(bundle_dir)
            except ValueError as exc:
                raise ValueError(f"artifact path escapes the bundle: {path_value}") from exc
            actual_hash = _sha256(path)
            if actual_hash != digest_value:
                raise ValueError(f"artifact hash mismatch: {path_value}")
            artifact_map[role_value] = {"path": path_value, "sha256": actual_hash}
        required_roles = {
            "decision_trace",
            "trade_fill_event_ledger",
            "equity_curve",
            "metrics",
            "policy_metadata",
            "evaluation_metadata",
        }
        if required_roles.difference(artifact_map):
            raise ValueError(f"run {run_id} is missing required artifacts")
        arm_report, decision_ids, input_hashes = _audit_arm(
            arm=arm,
            arm_dir=arm_dir,
            initial_balance=initial_balance,
            common_decision_ids=common_decision_ids,
            common_input_hashes=common_input_hashes,
        )
        if common_decision_ids is None:
            common_decision_ids = decision_ids
        if common_input_hashes is None:
            common_input_hashes = input_hashes
        arm_report["artifacts"] = artifact_map
        reports.append(arm_report)
    return {
        "schema": "matched_setup_baseline_accounting_audit_v1",
        "bundle_id": manifest.get("finding_id"),
        "bundle_path": bundle_dir.as_posix(),
        "initial_balance": initial_balance,
        "arms": reports,
        "status": "passed" if all(row["status"] == "passed" for row in reports) else "failed",
        "manifest_sha256": _sha256(manifest_path),
        "resolved_config_sha256": _sha256(bundle_dir / "resolved_config.json"),
        "verifier_source_sha256": _sha256(Path(__file__).resolve()),
    }


def write_packet(bundle_dir: Path, output_dir: Path) -> dict[str, Any]:
    """Write an immutable audit packet with a report and output checksums."""
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite existing audit packet: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    report = audit_bundle(bundle_dir)
    report_path = output_dir / "accounting_reconciliation.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    readme_path = output_dir / "README.md"
    arm_lines = [
        f"| {row['arm']} | {row['status']} | {row['decision_count']} | {row['open_count']} | "
        f"{row['realized_net_pnl']:.6f} | {row['ending_equity']} | {row['breach_event_count']} |"
        for row in report["arms"]
    ]
    readme_path.write_text(
        "# Matched setup baseline accounting reconciliation\n\n"
        "This independently checks the preserved matched-baseline result bundle's "
        "decision-to-open links, candidate eligibility, event chronology, position "
        "cashflows, equity summary, and breach counts. It validates accounting and "
        "telemetry consistency for these recorded runs; it does not validate broker "
        "fills, establish a historical policy replay, or make an economic-edge claim.\n\n"
        f"- Bundle: `{report['bundle_id']}`\n"
        f"- Initial balance: ${report['initial_balance']:,.2f}\n"
        f"- Verifier status: **{report['status']}**\n\n"
        "| Arm | Status | Decisions | Opens | Realized net PnL | Ending equity | Breaches |\n"
        "|---|---:|---:|---:|---:|---:|---:|\n"
        + "\n".join(arm_lines)
        + "\n\nReproduce from the repository root inside a compatible Python environment:\n\n"
        "```bash\n"
        ".venv/bin/python -m scripts.research.analysis.evaluation.verify_matched_setup_baseline_accounting \\\n"
        f"  --bundle-dir {report['bundle_path']} \\\n"
        f"  --output-dir {output_dir.as_posix()}\n"
        "```\n",
        encoding="utf-8",
    )
    checksums = [
        f"{_sha256(path)}  {path.name}"
        for path in sorted((report_path, readme_path), key=lambda item: item.name)
    ]
    (output_dir / "OUTPUT_SHA256SUMS").write_text("\n".join(checksums) + "\n", encoding="utf-8")
    return report


def main() -> int:
    """Run the audit and write a checksum-manifested evidence packet."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    report = write_packet(args.bundle_dir, args.output_dir)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
