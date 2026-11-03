#!/usr/bin/env python3
"""Independently verify the scheduled-session-close trace and source bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

from artifacts.atomic import write_json_atomic
from configuration.paths import repository_root

ROOT = repository_root(__file__)
DEFAULT_REPORT = Path(
    "evidence/research/simulator_execution_parity/scheduled_session_close/"
    "scheduled_session_close.json"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _same_number(left: Any, right: Any, *, tolerance: float = 1e-9) -> bool:
    try:
        return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=tolerance)
    except (TypeError, ValueError):
        return False


def verify(report_path: Path) -> dict[str, Any]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    checks: dict[str, bool] = {
        "schema_and_scenario_supported": report.get("schema_version") == 1
        and report.get("scenario") == "scheduled_session_close"
    }
    fixture_bytes = json.dumps(report["fixture"], sort_keys=True, separators=(",", ":")).encode()
    checks["fixture_hash_matches"] = hashlib.sha256(fixture_bytes).hexdigest() == report.get(
        "fixture_sha256"
    )
    source_checks = {
        path: _sha256(ROOT / path) == digest
        for path, digest in report.get("source_sha256", {}).items()
    }
    checks["source_hashes_match_current_bytes"] = bool(source_checks) and all(
        source_checks.values()
    )
    checks["both_latency_scenarios_present"] = [
        item.get("randomized_fill_latency_ms") for item in report.get("scenarios", [])
    ] == [0.0, 30.0]

    fixture = report["fixture"]
    ticks = {
        pd.Timestamp(row["time"]).tz_convert("UTC").isoformat(): row for row in fixture["ticks"]
    }
    ny_bars = [row for row in fixture["bars"] if row["session"] == "ny"]
    settings = report["controlled_settings"]
    deadline = pd.Timestamp(ny_bars[-1]["time"]) + pd.Timedelta(
        seconds=int(settings["bar_duration_seconds"])
    )
    scenario_checks: list[dict[str, bool]] = []
    for scenario in report.get("scenarios", []):
        env_events = scenario.get("environment_events", [])
        backtest_events = scenario.get("backtest_events", [])
        env_open: dict[str, Any] = next(
            (event for event in env_events if event.get("type") == "open"), {}
        )
        backtest_open: dict[str, Any] = next(
            (event for event in backtest_events if event.get("type") == "open"), {}
        )
        env_close: dict[str, Any] = next(
            (event for event in env_events if event.get("reason") == "session_end"), {}
        )
        backtest_close: dict[str, Any] = next(
            (event for event in backtest_events if event.get("reason") == "session_end"),
            {},
        )
        latency_limit = float(scenario["randomized_fill_latency_ms"])

        def valid_close(event: dict[str, Any]) -> bool:
            if not event:
                return False
            submitted = pd.Timestamp(event["order_submission_time"])
            arrival = pd.Timestamp(event["execution_arrival_time"])
            actual = pd.Timestamp(event["actual_tick_time"])
            latency_ns = int(event["execution_latency_ns"])
            latency_valid = (
                latency_ns == 0
                if latency_limit == 0
                else 0 <= latency_ns < int(latency_limit * 1_000_000)
            )
            return bool(
                latency_valid
                and arrival - submitted == pd.Timedelta(latency_ns, unit="ns")
                and submitted == pd.Timestamp(ny_bars[-1]["time"])
                and actual >= arrival
                and actual <= deadline
                and event.get("fill_time") == actual.isoformat()
                and event.get("time") == submitted.isoformat()
                and event.get("fill_quote_source") == "tick"
                and actual.isoformat() in ticks
                and _same_number(event.get("price"), ticks[actual.isoformat()]["bid"])
            )

        open_fields_match = bool(env_open and backtest_open) and all(
            env_open.get(key) == backtest_open.get(key)
            for key in ("fill_time", "price", "order_submission_time", "actual_tick_time")
        )
        close_fields_match = bool(env_close and backtest_close) and all(
            env_close.get(key) == backtest_close.get(key)
            for key in ("time", "order_submission_time", "fill_time", "actual_tick_time")
        )
        close_fields_match = close_fields_match and all(
            _same_number(env_close.get(key), backtest_close.get(key)) for key in ("price", "pnl")
        )
        accounting_matches = bool(env_close and backtest_close) and all(
            _same_number(scenario.get(key), settings["initial_balance"] + float(close["pnl"]))
            for key, close in (
                ("environment_final_equity", env_close),
                ("backtest_final_equity", backtest_close),
            )
        )
        current: dict[str, bool] = {
            "one_open_and_one_scheduled_close_per_engine": len(env_events) == 2
            and len(backtest_events) == 2
            and [event.get("type") for event in env_events] == ["open", "eod_close"]
            and [event.get("type") for event in backtest_events] == ["open", "eod_close"],
            "open_fill_matches": bool(open_fields_match),
            "scheduled_close_fields_match": bool(close_fields_match),
            "environment_close_obeys_deadline": valid_close(env_close),
            "backtest_close_obeys_deadline": valid_close(backtest_close),
            "final_equity_reconciles_from_close_pnl": bool(accounting_matches),
        }
        current["scenario_passed"] = all(current.values())
        scenario_checks.append(current)

    checks["all_scenarios_independently_reconciled"] = bool(scenario_checks) and all(
        item["scenario_passed"] for item in scenario_checks
    )
    return {
        "schema_version": 1,
        "report": str(report_path.resolve().relative_to(ROOT)),
        "report_sha256": _sha256(report_path),
        "checks": checks,
        "source_hash_checks": source_checks,
        "scenario_checks": scenario_checks,
        "independent_verification_passed": all(checks.values()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", nargs="?", type=Path, default=ROOT / DEFAULT_REPORT)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = verify(args.report)
    output = args.out or args.report.with_name("scheduled_session_close_verification.json")
    write_json_atomic(output, result)
    print(json.dumps({"out": str(output), **result}, indent=2))
    if not result["independent_verification_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
