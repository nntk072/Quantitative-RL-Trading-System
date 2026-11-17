#!/usr/bin/env python3
"""Independently verify provenance, source-event identity, and reported trace comparisons."""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

from artifacts.atomic import write_json_atomic
from artifacts.identity import file_sha256
from configuration.paths import repository_root

ROOT = repository_root(__file__)
DEFAULT_REPORT = Path(
    "evidence/research/simulator_execution_parity/local_tick_action_trace_set_stratified.json"
)


def _parse_time(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp is not a string")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _same_source_decision_bar(
    environment_event: dict[str, Any], backtest_event: dict[str, Any]
) -> bool:
    """Compare bar labels while retaining each engine's separate decision phase."""
    return _parse_time(environment_event.get("decision_bar_time")) == _parse_time(
        backtest_event.get("decision_bar_time")
    )


def verify_report(report_path: Path) -> dict[str, Any]:
    """Recompute artifact identities and consistency checks from the saved report."""
    report_path = report_path.resolve()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    input_record = report.get("inputs", {})
    checked_files: dict[str, dict[str, str | bool]] = {}
    for label, path_key, hash_key in (
        ("ticks", "tick_path", "tick_sha256"),
        ("bars", "m1_bars_path", "m1_bars_sha256"),
        ("alignment", "quote_alignment_report_path", "quote_alignment_report_sha256"),
    ):
        path = Path(str(input_record.get(path_key, "")))
        if not path.is_absolute():
            path = ROOT / path
        recorded = str(input_record.get(hash_key, ""))
        current = file_sha256(path) if path.is_file() else "missing"
        checked_files[label] = {
            "path": str(path),
            "recorded_sha256": recorded,
            "current_sha256": current,
            "matches": current == recorded,
        }

    generator = report.get("generator", {})
    generator_path = Path(str(generator.get("path", "")))
    current_generator_hash = file_sha256(generator_path) if generator_path.is_file() else "missing"
    generator_matches = current_generator_hash == generator.get("sha256")

    trace_pairs = report.get("trace_pairs", [])
    used_events: set[tuple[str, str]] = set()
    unique_event_identities = True
    quote_groups_valid = True
    source_period_valid = True
    trace_fields_match = True
    account_bridge_matches = True
    paired_strata: set[tuple[str, int]] = set()
    for pair in trace_pairs:
        month = str(pair.get("stratum_month", ""))
        direction = int(pair.get("direction", 0))
        paired_strata.add((month, direction))
        if len(month) != 7 or not month.startswith("2025-"):
            source_period_valid = False
        if direction not in (-1, 1):
            source_period_valid = False
        source_evidence = pair.get("historical_quote_evidence", {})
        for event_name in ("entry", "exit"):
            event = source_evidence.get(event_name, {})
            source = event.get("event_ledger_source")
            event_id = event.get("event_id")
            if not source or event_id is None:
                unique_event_identities = False
            else:
                identity = (str(source), str(event_id))
                if identity in used_events:
                    unique_event_identities = False
                used_events.add(identity)
            if (
                event.get("raw_rows_at_timestamp") != 1
                or event.get("bid_carried") is not False
                or event.get("ask_carried") is not False
                or event.get("changed_quote_within_timestamp") is not False
            ):
                quote_groups_valid = False
            try:
                source_time = _parse_time(event.get("reported_tick_time_utc"))
                if source_time.strftime("%Y-%m") != month:
                    source_period_valid = False
                if event_name == "entry":
                    expected_side = "ask" if direction == 1 else "bid"
                    if (
                        event.get("direction") != direction
                        or event.get("required_quote_side") != expected_side
                    ):
                        quote_groups_valid = False
                else:
                    expected_side = "bid" if direction == 1 else "ask"
                    if event.get("required_quote_side") != expected_side:
                        quote_groups_valid = False
            except (TypeError, ValueError):
                quote_groups_valid = False
                source_period_valid = False

        replay = pair.get("replay", {})
        if replay.get("trace_passed") is not True:
            trace_fields_match = False
        if (
            replay.get("close_pnl_match") is not True
            or replay.get("ending_balance_match") is not True
        ):
            trace_fields_match = False
        for comparison in replay.get("entry_and_exit_comparisons", []):
            if any(
                comparison.get(field) is not True
                for field in (
                    "same_tick_source",
                    "same_fill_timestamp",
                    "same_price",
                    "same_source_decision_bar",
                )
            ):
                trace_fields_match = False
        if len(replay.get("entry_and_exit_comparisons", [])) != 2:
            trace_fields_match = False
        for leg in ("entry", "exit"):
            leg_data = replay.get(leg, {})
            environment_event = leg_data.get("environment", {})
            backtest_event = leg_data.get("backtest", {})
            try:
                same_quote = (
                    environment_event.get("fill_quote_source")
                    == backtest_event.get("fill_quote_source")
                    == "tick"
                )
                same_time = _parse_time(environment_event.get("fill_time")) == _parse_time(
                    backtest_event.get("fill_time")
                )
                same_price = math.isclose(
                    float(environment_event["price"]),
                    float(backtest_event["price"]),
                    rel_tol=0.0,
                    abs_tol=1e-8,
                )
                same_decision_bar = _same_source_decision_bar(environment_event, backtest_event)
                if not (same_quote and same_time and same_price and same_decision_bar):
                    trace_fields_match = False
            except (KeyError, TypeError, ValueError):
                trace_fields_match = False
        try:
            initial_balance = float(replay["initial_balance"])
            same_pnl = math.isclose(
                float(replay["environment_close_pnl"]),
                float(replay["backtest_close_pnl"]),
                rel_tol=0.0,
                abs_tol=1e-8,
            )
            same_balance = math.isclose(
                float(replay["environment_ending_balance"]),
                float(replay["backtest_ending_balance"]),
                rel_tol=0.0,
                abs_tol=1e-8,
            )
            if not (same_pnl and same_balance):
                trace_fields_match = False
            for engine, ending_key, pnl_key, event_pnl_key in (
                ("environment", "environment_ending_balance", "environment_close_pnl", "net_pnl"),
                ("backtest", "backtest_ending_balance", "backtest_close_pnl", "pnl"),
            ):
                close_event = replay["exit"][engine]
                close_pnl = float(replay[pnl_key])
                ending_balance = float(replay[ending_key])
                if not math.isclose(
                    float(close_event[event_pnl_key]), close_pnl, rel_tol=0.0, abs_tol=1e-8
                ) or not math.isclose(
                    ending_balance, initial_balance + close_pnl, rel_tol=0.0, abs_tol=1e-8
                ):
                    account_bridge_matches = False
        except (KeyError, TypeError, ValueError):
            trace_fields_match = False
            account_bridge_matches = False

    checks = {
        "schema_valid": report.get("schema_version") == "simulator-local-tick-action-trace-set-v1",
        "generator_hash_matches": generator_matches,
        "input_hashes_match": all(item["matches"] for item in checked_files.values()),
        "trace_count_matches": report.get("trace_pair_count") == len(trace_pairs)
        and bool(trace_pairs),
        "2025_period_and_month_metadata_match": source_period_valid
        and sorted({month for month, _ in paired_strata}) == report.get("months_covered"),
        "directions_metadata_match": sorted({direction for _, direction in paired_strata})
        == report.get("directions_covered"),
        "quote_groups_meet_unique_complete_rule": quote_groups_valid,
        "source_events_not_reused": unique_event_identities
        and report.get("source_event_reuse") is False,
        "reported_pair_fields_reconcile": trace_fields_match and report.get("trace_passed") is True,
        "single_trade_pnl_to_balance_bridge_matches": account_bridge_matches,
    }
    verification = {
        "schema_version": "simulator-local-tick-action-trace-verification-v1",
        "report_path": str(report_path),
        "report_sha256": file_sha256(report_path),
        "verifier_path": str(Path(__file__).resolve()),
        "verifier_sha256": file_sha256(Path(__file__)),
        "trace_pair_count": len(trace_pairs),
        "source_event_identities_checked": len(used_events),
        "inputs": checked_files,
        "checks": checks,
        "verification_passed": all(checks.values()),
        "scope": (
            "Independent artifact/hash and report-field consistency check; does not rerun either "
            "simulator, prove the source alignment algorithm, or establish historical policy or economic validity."
        ),
    }
    return verification


def main() -> int:
    """Write a verification record beside the trace report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=ROOT / DEFAULT_REPORT)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report_path = args.report if args.report.is_absolute() else ROOT / args.report
    verification = verify_report(report_path)
    output_path = args.out or report_path.with_name(f"{report_path.stem}_verification.json")
    if not output_path.is_absolute():
        output_path = ROOT / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(output_path, verification)
    print(
        json.dumps(
            {
                "out": str(output_path),
                "verification_passed": verification["verification_passed"],
                "checks": verification["checks"],
            },
            sort_keys=True,
        )
    )
    return 0 if verification["verification_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
