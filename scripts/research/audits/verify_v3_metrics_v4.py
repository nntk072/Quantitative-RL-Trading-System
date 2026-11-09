#!/usr/bin/env python3
"""Verify that final evaluation metric payloads use qrl.performance_metrics.v4."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from scripts.research.audits.record_pretraining_scientific_gate import file_sha256

from artifacts.atomic import write_json_atomic
from evaluation.metrics.performance import METRIC_DEFINITION_VERSION

COUNT_FIELDS = (
    "n_trades",
    "breach_count",
    "breach_event_count",
    "breach_session_count",
    "daily_return_count",
)
REQUIRED_FIELDS = (
    "metric_definition_version",
    "n_trades",
    "total_pnl",
    "breach_event_count",
    "breach_session_count",
    "breach_rate",
    "daily_return_count",
    "daily_return_mean_pct",
    "daily_return_std_pct",
    "time_to_ruin_sessions",
    "ruin_event_observed",
    "ruin_time_censored",
    "metric_availability",
)
NUMERIC_FIELDS = (
    "total_pnl",
    "breach_rate",
    "daily_return_mean_pct",
    "daily_return_std_pct",
)
RUIN_BOOLEAN_FIELDS = ("ruin_event_observed", "ruin_time_censored")


def _metric_payloads(value: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        if "metric_definition_version" in value:
            found.append(value)
        for child in value.values():
            found.extend(_metric_payloads(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_metric_payloads(child))
    return found


def verify_file(path: Path) -> dict[str, Any]:
    """Verify every metric payload embedded in one JSON artifact."""
    value = json.loads(path.read_text(encoding="utf-8"))
    payloads = _metric_payloads(value)
    if not payloads:
        raise ValueError(f"no metric-definition payload found in {path}")
    failures: list[str] = []
    for index, payload in enumerate(payloads):
        missing = [field for field in REQUIRED_FIELDS if field not in payload]
        if missing:
            failures.append(f"payload {index} missing {missing}")
            continue
        if payload["metric_definition_version"] != METRIC_DEFINITION_VERSION:
            failures.append(f"payload {index} metric version mismatch")
        availability = payload.get("metric_availability")
        if not isinstance(availability, dict):
            failures.append(f"payload {index} metric_availability is not a mapping")
            availability = {}
        for field in COUNT_FIELDS:
            value_at_field = payload.get(field)
            if value_at_field is None:
                if field not in availability:
                    failures.append(f"payload {index} unavailable {field} lacks reason")
            elif isinstance(value_at_field, bool) or not isinstance(value_at_field, int):
                failures.append(f"payload {index} {field} is not a typed integer count")
            elif value_at_field < 0:
                failures.append(f"payload {index} {field} is negative")
        for field in NUMERIC_FIELDS:
            value_at_field = payload.get(field)
            if value_at_field is None:
                if not isinstance(availability.get(field), str) or not availability[field].strip():
                    failures.append(f"payload {index} unavailable {field} lacks reason")
            elif (
                isinstance(value_at_field, bool)
                or not isinstance(value_at_field, (int, float))
                or not math.isfinite(float(value_at_field))
            ):
                failures.append(f"payload {index} {field} is not a finite typed number")
        breach_rate = payload.get("breach_rate")
        if isinstance(breach_rate, (int, float)) and not isinstance(breach_rate, bool):
            if math.isfinite(float(breach_rate)) and not 0.0 <= breach_rate <= 1.0:
                failures.append(f"payload {index} breach_rate is outside [0, 1]")
        for field in RUIN_BOOLEAN_FIELDS:
            value_at_field = payload.get(field)
            if value_at_field is None:
                if not isinstance(availability.get(field), str) or not availability[field].strip():
                    failures.append(f"payload {index} unavailable {field} lacks reason")
            elif not isinstance(value_at_field, bool):
                failures.append(f"payload {index} {field} is not a typed boolean")
        observed = payload.get("ruin_event_observed")
        censored = payload.get("ruin_time_censored")
        if isinstance(observed, bool) and isinstance(censored, bool) and observed == censored:
            failures.append(f"payload {index} ruin observed/censored flags conflict")
        ruin_sessions = payload.get("time_to_ruin_sessions")
        if ruin_sessions is not None and (
            isinstance(ruin_sessions, bool)
            or not isinstance(ruin_sessions, int)
            or ruin_sessions < 0
        ):
            failures.append(f"payload {index} time_to_ruin_sessions is not a nonnegative integer")
        if (
            payload.get("time_to_ruin_sessions") is None
            and "time_to_ruin_sessions" not in availability
        ):
            failures.append(f"payload {index} missing ruin-time availability reason")
    return {
        "path": str(path.resolve()),
        "sha256": file_sha256(path),
        "metric_payload_count": len(payloads),
        "status": "pass" if not failures else "fail",
        "failures": failures,
    }


def verify_files(paths: list[Path]) -> dict[str, Any]:
    """Verify all final metric artifacts."""
    if not paths:
        raise ValueError("at least one metric artifact is required")
    rows = [verify_file(path.expanduser().resolve()) for path in paths]
    return {
        "schema_version": "v3-metrics-v4-verification-v1",
        "metric_definition_version": METRIC_DEFINITION_VERSION,
        "status": "pass" if all(row["status"] == "pass" for row in rows) else "fail",
        "files": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evaluation-json", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = verify_files(args.evaluation_json)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(args.output, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
