#!/usr/bin/env python3
"""Independently verify saved local simulator account-transition traces.

The verifier consumes reports from
``compare_simulator_local_session_account_trace.py`` but recomputes lifecycle,
session-reset, account-balance, and provenance checks from the saved rows and
current input/source bytes. Its verification result is separate from the
trace runner's ``trace_passed`` field.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from configuration.paths import repository_root

ROOT = repository_root(__file__)
PACKET_DIR = Path("evidence/research/simulator_execution_parity/local_session_account_transition")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def close(left: float, right: float, *, atol: float = 1e-8) -> bool:
    return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=atol)


def lifecycle(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records = []
    for event in events:
        if event.get("type") in {"open", "close", "forced_close"}:
            record = dict(event)
            if record["type"] == "forced_close":
                record["event_type"] = "forced_close"
                record["type"] = "close"
            records.append(record)
    return records


def event_time(event: dict[str, Any]) -> str | None:
    return next(
        (event[key] for key in ("fill_time", "close_time", "time") if event.get(key) is not None),
        None,
    )


def event_datetime(event: dict[str, Any]) -> datetime:
    raw_time = event_time(event)
    if raw_time is None:
        raise ValueError("lifecycle event has no timestamp")
    return datetime.fromisoformat(raw_time)


def session_for(event: dict[str, Any], report: dict[str, Any]) -> int:
    raw_time = event_time(event)
    if raw_time is None:
        raise ValueError("lifecycle event has no timestamp")
    local_date = (
        datetime.fromisoformat(raw_time)
        .astimezone(ZoneInfo(report["timezone_label"]))
        .date()
        .isoformat()
    )
    matches = [
        int(session["session_id"])
        for session in report["selected_sessions"]
        if session["date"] == local_date
    ]
    if len(matches) != 1:
        raise ValueError(f"event timestamp {raw_time} does not map to one selected local session")
    return matches[0]


def verify(report_path: Path, input_hashes: dict[str, str]) -> dict[str, Any]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    checks: dict[str, bool] = {}
    details: dict[str, Any] = {}
    report_path = report_path.resolve()

    checks["schema_version_supported"] = report.get("schema_version") == 1
    env_events = lifecycle(report["environment_events"])
    backtest_events = lifecycle(report["backtest_events"])
    scenario = report.get("scenario", "account_transition")
    expected_event_count = (
        2 if scenario in {"max_loss_terminal", "daily_loss_full_evaluation_failure"} else 4
    )
    checks["lifecycle_event_counts_match"] = len(env_events) == len(backtest_events)
    checks["lifecycle_event_count_is_complete"] = len(env_events) == expected_event_count
    checks["two_selected_sessions_recorded"] = len(report["selected_sessions"]) == 2

    lifecycle_rows: list[dict[str, Any]] = []
    if len(env_events) == len(backtest_events):
        for env_event, backtest_event in zip(env_events, backtest_events, strict=True):
            event_type_matches = env_event["type"] == backtest_event["type"]
            time_matches = event_time(env_event) == event_time(backtest_event)
            session_matches = session_for(env_event, report) == session_for(backtest_event, report)
            price_matches = close(env_event["price"], backtest_event["price"])
            if env_event["type"] == "open" and backtest_event["type"] == "open":
                direction_matches = close(env_event["direction"], backtest_event["direction"])
                size_matches = close(env_event["lots"], backtest_event["lots"])
            elif env_event["type"] == "close" and backtest_event["type"] == "close":
                direction_matches = True
                size_matches = close(env_event["size"], backtest_event["size"])
            else:
                direction_matches = False
                size_matches = False
            pnl_matches = (
                close(env_event["pnl"], backtest_event["pnl"], atol=1e-9)
                if env_event["type"] == backtest_event["type"] == "close"
                else True
            )
            lifecycle_rows.append(
                {
                    "type_matches": event_type_matches,
                    "time_matches": time_matches,
                    "session_matches": session_matches,
                    "price_matches": price_matches,
                    "price_delta": float(env_event["price"]) - float(backtest_event["price"]),
                    "direction_matches": direction_matches,
                    "size_matches": size_matches,
                    "pnl_matches": pnl_matches,
                }
            )
    equality_flags = (
        "type_matches",
        "time_matches",
        "session_matches",
        "price_matches",
        "direction_matches",
        "size_matches",
        "pnl_matches",
    )
    all_lifecycle_equal = bool(lifecycle_rows) and all(
        all(row[key] for key in equality_flags) for row in lifecycle_rows
    )
    recorded_lifecycle = report["lifecycle_comparisons"]
    checks["reported_lifecycle_comparison_count_matches"] = len(recorded_lifecycle) == len(
        lifecycle_rows
    )
    if len(recorded_lifecycle) == len(lifecycle_rows):
        checks["reported_lifecycle_flags_match_recomputation"] = all(
            recorded.get("type") == env_events[index]["type"]
            and recorded.get("same_fill_time") == row["time_matches"]
            and recorded.get("same_session_id") == row["session_matches"]
            and recorded.get("same_direction") == row["direction_matches"]
            and recorded.get("same_price") == row["price_matches"]
            and close(recorded.get("price_delta", math.nan), row["price_delta"])
            for index, (recorded, row) in enumerate(
                zip(recorded_lifecycle, lifecycle_rows, strict=True)
            )
        )
    details["lifecycle_comparisons"] = lifecycle_rows

    env_closes = [event for event in env_events if event["type"] == "close"]
    backtest_closes = [event for event in backtest_events if event["type"] == "close"]
    session_ids = [int(session["session_id"]) for session in report["selected_sessions"]]
    expected_close_session_ids = (
        session_ids[:1]
        if scenario in {"max_loss_terminal", "daily_loss_full_evaluation_failure"}
        else session_ids
    )
    checks["each_engine_closes_once_per_selected_session"] = all(
        [session_for(event, report) for event in closes].count(session_id) == 1
        for closes in (env_closes, backtest_closes)
        for session_id in expected_close_session_ids
    )
    recorded_close_comparisons = report["close_comparisons"]
    recomputed_close_comparisons = []
    if len(env_closes) == len(backtest_closes):
        for env_close, backtest_close in zip(env_closes, backtest_closes, strict=True):
            pnl_delta = float(env_close["pnl"]) - float(backtest_close["pnl"])
            same_close_time = event_time(env_close) == event_time(backtest_close)
            same_session = session_for(env_close, report) == session_for(backtest_close, report)
            recomputed_close_comparisons.append(
                {
                    "same_session_id": same_session,
                    "same_close_time": same_close_time,
                    "pnl_delta": pnl_delta,
                    "same_pnl": close(env_close["pnl"], backtest_close["pnl"], atol=1e-9),
                }
            )
    checks["reported_close_comparison_count_matches"] = len(recorded_close_comparisons) == len(
        recomputed_close_comparisons
    )
    if len(recorded_close_comparisons) == len(recomputed_close_comparisons):
        checks["reported_close_comparisons_match_recomputation"] = all(
            all(
                recorded.get(key) == computed[key]
                for key in ("same_session_id", "same_close_time", "same_pnl")
            )
            and close(recorded.get("pnl_delta", math.nan), computed["pnl_delta"], atol=1e-9)
            for recorded, computed in zip(
                recorded_close_comparisons, recomputed_close_comparisons, strict=True
            )
        )
    first_session_id = session_ids[0]
    env_first_pnl = sum(
        float(event["pnl"])
        for event in env_closes
        if session_for(event, report) == first_session_id
    )
    backtest_first_pnl = sum(
        float(event["pnl"])
        for event in backtest_closes
        if session_for(event, report) == first_session_id
    )
    initial_balance = float(report["initial_balance"])
    expected_env_reset = initial_balance + env_first_pnl
    expected_backtest_reset = initial_balance + backtest_first_pnl
    checks["reported_first_session_pnl_matches_events"] = close(
        report["first_session_realized_close_pnl"]["environment"], env_first_pnl, atol=1e-9
    ) and close(
        report["first_session_realized_close_pnl"]["event_backtest"], backtest_first_pnl, atol=1e-9
    )
    reset_applicable = report.get("session_reset_check_applicable", True)
    if reset_applicable:
        checks["reported_second_session_reset_expectation_matches"] = close(
            report["expected_second_session_start_balance"]["environment"], expected_env_reset
        ) and close(
            report["expected_second_session_start_balance"]["event_backtest"],
            expected_backtest_reset,
        )
        checks["observed_session_resets_match_recomputed_expectation"] = close(
            report["environment_second_session_start_balance"], expected_env_reset
        ) and close(report["backtest_second_session_start_balance"], expected_backtest_reset)
        checks["reported_internal_reset_flags_match_recomputation"] = report[
            "session_reset_matches_within_engine"
        ]["environment"] == close(
            report["environment_second_session_start_balance"], expected_env_reset
        ) and report["session_reset_matches_within_engine"]["event_backtest"] == close(
            report["backtest_second_session_start_balance"], expected_backtest_reset
        )
    else:
        checks["terminal_scenario_marks_session_reset_not_applicable"] = (
            scenario == "max_loss_terminal"
            and report["expected_second_session_start_balance"]
            == {"environment": None, "event_backtest": None}
            and report["session_reset_matches_within_engine"]
            == {"environment": None, "event_backtest": None}
        )

    env_close_pnl = sum(float(event["pnl"]) for event in env_closes)
    backtest_close_pnl = sum(float(event["pnl"]) for event in backtest_closes)
    expected_env_balance = initial_balance + env_close_pnl
    expected_backtest_balance = initial_balance + backtest_close_pnl
    account = report["final_account"]
    checks["reported_final_balances_reconcile_to_close_pnl"] = close(
        account["environment_balance"], expected_env_balance
    ) and close(account["backtest_balance"], expected_backtest_balance)
    checks["reported_final_equity_matches_balance"] = close(
        account["environment_equity"], account["environment_balance"]
    ) and close(account["backtest_equity"], account["backtest_balance"])
    checks["reported_account_deltas_recompute"] = close(
        account["balance_delta"], account["environment_balance"] - account["backtest_balance"]
    ) and close(account["equity_delta"], account["environment_equity"] - account["backtest_equity"])
    checks["reported_daily_loss_delta_recomputes"] = close(
        account["daily_loss_delta"],
        account["environment_daily_loss"] - account["backtest_daily_loss"],
    )
    account_comparisons = [
        (account["environment_balance"], account["backtest_balance"]),
        (account["environment_equity"], account["backtest_equity"]),
    ]
    daily_loss_comparison_applicable = scenario != "max_loss_terminal"
    if daily_loss_comparison_applicable:
        account_comparisons.append(
            (account["environment_daily_loss"], account["backtest_daily_loss"])
        )
    cross_engine_account_equal = all(close(left, right) for left, right in account_comparisons)
    checks["daily_loss_comparison_scope_is_declared"] = (
        account.get("daily_loss_comparison_applicable") == daily_loss_comparison_applicable
    )
    checks["reported_cross_engine_account_flag_matches_recomputation"] = (
        account["cross_engine_account_state_matches"] == cross_engine_account_equal
    )
    risk_transition = report.get("risk_transition", {})
    env_breaches = risk_transition.get("environment_breach_events", [])
    backtest_breaches = risk_transition.get("backtest_breach_events", [])
    if scenario in {"daily_loss_full_evaluation_failure", "max_loss_terminal"}:
        first_session_id, next_session_id = session_ids
        daily_scenario = scenario == "daily_loss_full_evaluation_failure"
        expected_reason = "daily_loss" if daily_scenario else "max_drawdown"
        expected_next_session_opens = 0
        expected_limit = float(
            risk_transition["daily_loss_limit" if daily_scenario else "max_loss_limit"]
        )
        env_expected_breaches = [
            event for event in env_breaches if event.get("reason") == expected_reason
        ]
        backtest_expected_breaches = [
            event for event in backtest_breaches if event.get("reason") == expected_reason
        ]
        env_post_breach_opens = 0
        backtest_post_breach_opens = 0
        if len(env_expected_breaches) == 1:
            breach_time = datetime.fromisoformat(env_expected_breaches[0]["time"])
            env_post_breach_opens = sum(
                session_for(event, report) == first_session_id
                and event_datetime(event).astimezone(breach_time.tzinfo) > breach_time
                for event in env_events
                if event.get("type") == "open"
            )
        if len(backtest_expected_breaches) == 1:
            breach_time = datetime.fromisoformat(backtest_expected_breaches[0]["time"])
            backtest_post_breach_opens = sum(
                session_for(event, report) == first_session_id
                and event_datetime(event).astimezone(breach_time.tzinfo) > breach_time
                for event in backtest_events
                if event.get("type") == "open"
            )
        env_next_session_opens = sum(
            session_for(event, report) == next_session_id
            for event in env_events
            if event.get("type") == "open"
        )
        backtest_next_session_opens = sum(
            session_for(event, report) == next_session_id
            for event in backtest_events
            if event.get("type") == "open"
        )
        attempted_reentry = report["controlled_actions"][2:4] == [19, 1]
        attempted_next_session_entry = report["controlled_actions"][8] == 1
        breach_events_match = False
        if len(env_expected_breaches) == len(backtest_expected_breaches) == 1:
            env_breach = env_expected_breaches[0]
            backtest_breach = backtest_expected_breaches[0]
            breach_events_match = (
                env_breach.get("session_id")
                == backtest_breach.get("session_id")
                == first_session_id
                and env_breach.get("reason") == backtest_breach.get("reason") == expected_reason
                and datetime.fromisoformat(env_breach["time"])
                == datetime.fromisoformat(backtest_breach["time"])
                and close(env_breach.get("equity"), backtest_breach.get("equity"))
                and close(env_breach.get("daily_loss"), backtest_breach.get("daily_loss"))
            )
        terminal_matches = (
            (
                report["risk_transition"]["environment_terminated"] is True
                and report["risk_transition"]["environment_truncated"] is False
                and report["risk_transition"]["environment_termination_action_index"] <= 2
            )
            if scenario == "max_loss_terminal"
            else not report["risk_transition"]["environment_terminated"]
        )
        risk_transition_matches = (
            len(env_breaches) == len(backtest_breaches) == 1
            and breach_events_match
            and expected_limit > 0.0
            and env_first_pnl <= -expected_limit
            and backtest_first_pnl <= -expected_limit
            and attempted_reentry
            and env_post_breach_opens == backtest_post_breach_opens == 0
            and env_next_session_opens == backtest_next_session_opens == expected_next_session_opens
            and attempted_next_session_entry
            and terminal_matches
            and (
                not reset_applicable
                or (
                    close(report["environment_second_session_start_balance"], expected_env_reset)
                    and close(
                        report["backtest_second_session_start_balance"], expected_backtest_reset
                    )
                )
            )
        )
        risk_details = {
            "expected_breach_reason": expected_reason,
            "environment_expected_breach_count": len(env_expected_breaches),
            "backtest_expected_breach_count": len(backtest_expected_breaches),
            "breach_events_match": breach_events_match,
            "environment_same_session_post_breach_opens": env_post_breach_opens,
            "backtest_same_session_post_breach_opens": backtest_post_breach_opens,
            "environment_next_session_opens": env_next_session_opens,
            "backtest_next_session_opens": backtest_next_session_opens,
            "controlled_reentry_attempt_after_close": attempted_reentry,
            "controlled_next_session_entry_attempt": attempted_next_session_entry,
            "environment_terminal_contract_matches": terminal_matches,
        }
    else:
        risk_transition_matches = not env_breaches and not backtest_breaches
        risk_details = {
            "environment_breach_count": len(env_breaches),
            "backtest_breach_count": len(backtest_breaches),
        }
    risk_transition_fields_match = (
        risk_transition.get("risk_transition_matches") == risk_transition_matches
        and risk_transition.get("same_session_reentry_blocked")
        == (
            scenario not in {"daily_loss_full_evaluation_failure", "max_loss_terminal"}
            or risk_details.get("environment_same_session_post_breach_opens") == 0
        )
        and risk_transition.get("next_session_entry_allowed_after_reset") is False
        and risk_transition.get("max_loss_rollout_latched") == (scenario == "max_loss_terminal")
        and risk_transition.get("daily_loss_evaluation_latched")
        == (
            scenario == "daily_loss_full_evaluation_failure"
            and risk_details.get("environment_next_session_opens") == 0
            and risk_details.get("backtest_next_session_opens") == 0
        )
    )
    checks["risk_transition_matches_recomputed_events"] = risk_transition_matches
    checks["reported_risk_transition_flags_match_recomputation"] = risk_transition_fields_match
    details["risk_transition"] = risk_details
    simulator_parity = (
        all_lifecycle_equal and cross_engine_account_equal and risk_transition_matches
    )
    checks["reported_trace_verdict_matches_recomputed_parity"] = (
        bool(report["trace_passed"]) == simulator_parity
    )
    expected_status = (
        "matched"
        if simulator_parity
        else "bar_fallback_execution_difference"
        if report["execution_mode"] == "bar_fallback"
        else "tick_path_account_difference"
    )
    checks["reported_trace_status_matches_recomputed_parity"] = (
        report["trace_status"] == expected_status
    )

    for field, verified_hash in input_hashes.items():
        path_field = "input_bars" if field == "input_bars_sha256" else "input_ticks"
        input_path = ROOT / report[path_field]
        checks[f"{path_field}_current_bytes_match"] = (
            sha256(input_path) == report[field] == verified_hash
        )
    code_hash_checks = {}
    for relative_path, recorded_hash in report["code_sha256"].items():
        source_path = (
            ROOT
            / "scripts/research/analysis/evaluation/compare_simulator_local_session_account_trace.py"
            if relative_path == "generator"
            else ROOT / relative_path
        )
        matches = sha256(source_path) == recorded_hash
        code_hash_checks[relative_path] = matches
        checks[f"source_hash_{relative_path}"] = matches

    details.update(
        {
            "execution_mode": report["execution_mode"],
            "report_trace_passed": report["trace_passed"],
            "independently_recomputed_simulator_parity": simulator_parity,
            "lifecycle_fields_match_across_engines": all_lifecycle_equal,
            "expected_environment_balance": expected_env_balance,
            "expected_backtest_balance": expected_backtest_balance,
            "environment_close_pnl_sum": env_close_pnl,
            "backtest_close_pnl_sum": backtest_close_pnl,
            "independently_recomputed_account_equal": cross_engine_account_equal,
            "code_hash_checks": code_hash_checks,
            "input_hashes": input_hashes,
        }
    )
    return {
        "schema_version": 1,
        "source_report": str(report_path.relative_to(ROOT)),
        "independent_verifier": str(Path(__file__).resolve().relative_to(ROOT)),
        "independent_verifier_sha256": sha256(Path(__file__).resolve()),
        "independent_verification_passed": all(checks.values()),
        "simulator_parity_passed": simulator_parity,
        "checks": checks,
        "details": details,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reports", nargs="+", type=Path)
    args = parser.parse_args()
    input_paths: dict[str, Path] = {}
    for report_path in args.reports:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        input_paths[report["input_bars_sha256"]] = ROOT / report["input_bars"]
        if report.get("input_ticks"):
            input_paths[report["input_ticks_sha256"]] = ROOT / report["input_ticks"]
    input_hashes_by_path = {path: sha256(path) for path in input_paths.values()}
    outputs = []
    for report_path in args.reports:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        supplied_hashes = {"input_bars_sha256": input_hashes_by_path[ROOT / report["input_bars"]]}
        if report.get("input_ticks"):
            supplied_hashes["input_ticks_sha256"] = input_hashes_by_path[
                ROOT / report["input_ticks"]
            ]
        verification = verify(report_path, supplied_hashes)
        output_path = report_path.with_name(f"{report_path.stem}_verification.json")
        output_path.write_text(
            json.dumps(verification, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        outputs.append(
            {
                "report": str(report_path),
                "verification": str(output_path),
                "independent_verification_passed": verification["independent_verification_passed"],
                "simulator_parity_passed": verification["simulator_parity_passed"],
                "failed_checks": [
                    key for key, passed in verification["checks"].items() if not passed
                ],
            }
        )
    print(json.dumps({"reports": outputs}, indent=2))
    if not all(item["independent_verification_passed"] for item in outputs):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
