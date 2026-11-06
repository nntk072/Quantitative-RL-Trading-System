"""Reconstruct the historical gross realized-loss counter from saved close events."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

_CLOSE_TYPES = frozenset(
    {"close", "stop_close", "tp_close", "forced_close", "eod_close", "tp_partial_close"}
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _finite(value: str | None) -> float | None:
    try:
        parsed = float(value) if value else None
    except ValueError:
        return None
    return parsed if parsed is not None and math.isfinite(parsed) else None


def _configured_session_map(
    config: dict[str, Any], manifest: dict[str, Any], source_run: Path, dataset_name: str
) -> tuple[dict[str, int], dict[str, Any]]:
    """Recover date-derived session IDs from the run's configured local M1 file."""
    data = config.get("data")
    datasets = data.get("datasets") if isinstance(data, dict) else None
    dataset = datasets.get(dataset_name) if isinstance(datasets, dict) else None
    primary = data.get("primary") if isinstance(data, dict) else None
    data_timezone = data.get("tz") if isinstance(data, dict) else None
    if (
        not isinstance(dataset, dict)
        or not isinstance(primary, str)
        or not isinstance(data_timezone, str)
    ):
        return {}, {"status": "unavailable", "reason": "configured split M1 source is absent"}
    m1_files = dataset.get("m1_files")
    raw_dir = dataset.get("raw_dir")
    filename = m1_files.get(primary) if isinstance(m1_files, dict) else None
    if not isinstance(raw_dir, str) or not isinstance(filename, str):
        return {}, {"status": "unavailable", "reason": "configured split M1 path is incomplete"}

    repository_root = next(
        (parent for parent in source_run.parents if (parent / ".git").exists()), None
    )
    if repository_root is None:
        return {}, {"status": "unavailable", "reason": "source repository root is not recoverable"}
    source_path = Path(raw_dir) / filename
    if not source_path.is_absolute():
        source_path = repository_root / source_path
    if not source_path.is_file():
        return {}, {"status": "unavailable", "reason": "configured split M1 source file is absent"}

    try:
        tz = ZoneInfo(data_timezone)
        expected_key = "train_bars" if dataset_name == "training" else "test_bars"
        expected = manifest.get("source_datasets", {}).get(expected_key, {})
        expected_rows = expected.get("rows")
        expected_start = _parse_time(expected.get("start"))
        expected_end = _parse_time(expected.get("end"))
    except (KeyError, TypeError, ValueError):
        return {}, {"status": "unavailable", "reason": "source bar manifest is incomplete"}
    if not isinstance(expected_rows, int) or expected_start is None or expected_end is None:
        return {}, {"status": "unavailable", "reason": "source bar row count or bounds are absent"}

    with source_path.open(newline="", encoding="utf-8-sig") as source:
        reader = csv.reader(source, delimiter="\t")
        header = [value.strip().strip("<>").lower() for value in next(reader)]
        try:
            date_column, time_column = header.index("date"), header.index("time")
        except ValueError:
            return {}, {"status": "unavailable", "reason": "M1 source lacks date/time columns"}
        dates: set[str] = set()
        timestamps: set[tuple[str, str]] = set()
        first_timestamp: datetime | None = None
        last_timestamp: datetime | None = None
        source_row_count = 0
        for row in reader:
            if len(row) <= max(date_column, time_column):
                return {}, {"status": "incomplete", "reason": "M1 source contains a short row"}
            source_row_count += 1
            raw_date, raw_time = row[date_column].strip(), row[time_column].strip()
            local_time = datetime.strptime(f"{raw_date} {raw_time}", "%Y.%m.%d %H:%M:%S")
            timestamps.add((raw_date, raw_time))
            dates.add(local_time.date().isoformat())
            localized = local_time.replace(tzinfo=tz)
            first_timestamp = (
                localized if first_timestamp is None else min(first_timestamp, localized)
            )
            last_timestamp = localized if last_timestamp is None else max(last_timestamp, localized)

    expected_unique_rows = expected_rows == source_row_count == len(timestamps)
    bounds_match = first_timestamp == expected_start and last_timestamp == expected_end
    if not expected_unique_rows or not bounds_match:
        return {}, {
            "status": "mismatch",
            "source_path": source_path.as_posix(),
            "source_sha256": _sha256(source_path),
            "source_row_count": source_row_count,
            "unique_timestamp_count": len(timestamps),
            "expected_processed_bar_rows": expected_rows,
            "source_bounds": [
                first_timestamp.isoformat() if first_timestamp else None,
                last_timestamp.isoformat() if last_timestamp else None,
            ],
            "expected_processed_bar_bounds": [expected_start.isoformat(), expected_end.isoformat()],
        }

    ordered_dates = sorted(dates)
    return {day: session_id for session_id, day in enumerate(ordered_dates)}, {
        "status": "verified",
        "mapping_method": "market_data.transforms.sessions.add_session_id assigns zero-based IDs over sorted unique dates after clean; raw row count, unique timestamps, and date bounds match reanalysis source_bars manifest",
        "dataset": dataset_name,
        "source_path": source_path.as_posix(),
        "source_sha256": _sha256(source_path),
        "source_row_count": source_row_count,
        "unique_timestamp_count": len(timestamps),
        "duplicate_timestamp_count_removed_by_clean": source_row_count - len(timestamps),
        "source_date_count": len(ordered_dates),
        "first_session_date": ordered_dates[0],
        "last_session_date": ordered_dates[-1],
        "processed_bar_rows": expected_rows,
        "processed_bar_manifest_sha256": expected.get("sha256"),
        "source_timezone": data_timezone,
    }


def audit_gross_realized_loss_counter(run_dir: Path) -> dict[str, Any]:
    """Audit close-event losses against recorded daily-loss breach events.

    Close rows omit numeric session IDs. The audit recovers those IDs from the
    run's configured local M1 split only when row counts, unique timestamps, and
    source bounds match the reanalysis manifest.
    """
    root = run_dir.expanduser().resolve(strict=True)
    trades_path = root / "trades.csv"
    breaches_path = root / "breach_events.csv"
    manifest_path = root.parent / "reanalysis_manifest.json"
    if not all(path.is_file() for path in (trades_path, breaches_path, manifest_path)):
        raise FileNotFoundError(
            "trades.csv, breach_events.csv, and reanalysis_manifest.json are required"
        )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source_run = manifest.get("source_run")
    expected_config_hash = manifest.get("source_config_sha256")
    if not isinstance(source_run, str) or not isinstance(expected_config_hash, str):
        raise ValueError("reanalysis manifest lacks source_run or source_config_sha256")
    config_path = Path(source_run) / "config.yaml"
    if not config_path.is_file() or _sha256(config_path) != expected_config_hash:
        raise ValueError("source config is missing or its SHA-256 differs from reanalysis manifest")

    import yaml

    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("source config is not a mapping")
    policy = config.get("trading_policy", {}) if isinstance(config, dict) else {}
    if not isinstance(policy, dict) or policy.get("mode") != "legacy":
        raise ValueError("this audit only applies to trading_policy.mode=legacy")
    ftmo = config.get("ftmo", {})
    limit = _finite(str(ftmo.get("daily_loss_limit", ""))) if isinstance(ftmo, dict) else None
    if limit is None or limit <= 0:
        raise ValueError("source config has no positive ftmo.daily_loss_limit")

    dataset_name = root.name
    if dataset_name not in {"training", "testing"}:
        raise ValueError(f"run directory must be a training or testing split: {root}")
    session_map, session_map_report = _configured_session_map(
        config, manifest, Path(source_run), dataset_name
    )
    source_timezone = str(config.get("data", {}).get("tz", "Etc/GMT-3"))
    source_tz = ZoneInfo(source_timezone)

    close_rows: list[dict[str, Any]] = []
    invalid_close_rows: list[int] = []
    with trades_path.open(newline="", encoding="utf-8") as source:
        for row_number, row in enumerate(csv.DictReader(source), start=2):
            if row.get("type") not in _CLOSE_TYPES:
                continue
            fill_time = _parse_time(row.get("fill_time"))
            event_time = _parse_time(row.get("time"))
            pnl = _finite(row.get("pnl"))
            if fill_time is None or pnl is None:
                invalid_close_rows.append(row_number)
                continue
            session_date = fill_time.astimezone(source_tz).date().isoformat()
            close_rows.append(
                {
                    "fill_time": fill_time,
                    "event_time": event_time,
                    "pnl": pnl,
                    "type": row.get("type"),
                    "position_id": row.get("position_id"),
                    "row_number": row_number,
                    "session_date": session_date,
                    "session_id": session_map.get(session_date),
                }
            )
    close_rows.sort(key=lambda row: (row["fill_time"].astimezone(UTC), row["row_number"]))

    events: list[dict[str, Any]] = []
    with breaches_path.open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            if row.get("reason") != "daily_loss":
                continue
            event_time = _parse_time(row.get("fill_time")) or _parse_time(row.get("time"))
            if event_time is None:
                events.append({"status": "invalid_event_time", "session_id": row.get("session_id")})
                continue
            events.append(
                {
                    "time": event_time,
                    "event_time": _parse_time(row.get("time")),
                    "session_id": row.get("session_id"),
                }
            )

    grouping_is_session_exact = session_map_report.get("status") == "verified"
    grouped: dict[str | int, list[dict[str, Any]]] = defaultdict(list)
    for row in close_rows:
        group_key: str | int = (
            row["session_id"] if grouping_is_session_exact else row["session_date"]
        )
        grouped[group_key].append(row)

    event_results: list[dict[str, Any]] = []
    event_keys: set[str | int] = set()
    for event in events:
        if "time" not in event:
            event_results.append(event)
            continue
        event_time = event["time"]
        event_date = event_time.astimezone(source_tz).date().isoformat()
        parsed_session_id = _finite(event["session_id"])
        expected_session_id = session_map.get(event_date)
        session_id_matches = not grouping_is_session_exact or (
            parsed_session_id is not None and int(parsed_session_id) == expected_session_id
        )
        event_key: str | int = (
            expected_session_id
            if grouping_is_session_exact and expected_session_id is not None
            else event_date
        )
        event_keys.add(event_key)
        utc_cutoff = event_time.astimezone(UTC)
        day_rows = grouped.get(event_key, [])
        realized_loss = 0.0
        crossing: dict[str, Any] | None = None
        for row in day_rows:
            if row["fill_time"].astimezone(UTC) > utc_cutoff:
                break
            if row["pnl"] < 0:
                realized_loss += -row["pnl"]
                if crossing is None and realized_loss >= limit:
                    crossing = {
                        "fill_time": row["fill_time"].isoformat(),
                        "pnl": row["pnl"],
                        "close_type": row["type"],
                        "position_id": row["position_id"],
                    }
        event_results.append(
            {
                "status": "crossed_before_event"
                if crossing
                else "event_without_trade_ledger_crossing",
                "calendar_date": event_date,
                "session_id": event["session_id"],
                "recovered_session_id": expected_session_id,
                "session_id_matches_source_bars": session_id_matches,
                "recorded_event_fill_time": event_time.isoformat(),
                "recorded_event_time": event["event_time"].isoformat()
                if event["event_time"]
                else None,
                "gross_realized_losses_through_event_usd": realized_loss,
                "configured_limit_usd": limit,
                "first_threshold_crossing_close": crossing,
                "close_event_count_through_event": sum(
                    row["fill_time"].astimezone(UTC) <= utc_cutoff for row in day_rows
                ),
            }
        )

    crossings: list[dict[str, Any]] = []
    for group_key, day_rows in sorted(grouped.items(), key=lambda item: str(item[0])):
        realized_loss = 0.0
        crossing = None
        loss_at_crossing = None
        for row in day_rows:
            if row["pnl"] < 0:
                realized_loss += -row["pnl"]
                if crossing is None and realized_loss >= limit:
                    crossing = row
                    loss_at_crossing = realized_loss
        if crossing is not None:
            crossings.append(
                {
                    "session_id": group_key if grouping_is_session_exact else None,
                    "calendar_date": day_rows[0]["session_date"],
                    "first_crossing_close_time": crossing["fill_time"].isoformat(),
                    "gross_realized_loss_at_crossing_usd": loss_at_crossing,
                    "recorded_daily_loss_event_on_session": group_key in event_keys,
                }
            )

    unrecorded_crossing_dates = [
        row["calendar_date"] for row in crossings if not row["recorded_daily_loss_event_on_session"]
    ]
    event_mismatch = any(
        row.get("status") != "crossed_before_event"
        or not row.get("session_id_matches_source_bars", True)
        for row in event_results
    )
    status = (
        "incomplete"
        if invalid_close_rows
        else "mismatch"
        if event_mismatch or unrecorded_crossing_dates
        else "verified_session_reconciliation"
        if grouping_is_session_exact
        else "bounded_reconciliation"
    )

    return {
        "schema": "qrl.legacy_daily_loss_trade_event_audit.v1",
        "status": status,
        "claim_scope": "Historical gross realized-loss arithmetic from serialized close-event pnl values grouped by source-derived session ID when the configured local M1 split verifies against the reanalysis manifest; otherwise grouped by local date as a proxy.",
        "limitations": [
            "The audit does not replay the environment or independently validate quote fills.",
            "The saved event ledger records breach time but not the daily_loss counter value.",
        ],
        "session_id_mapping": session_map_report,
        "source_configuration": {
            "path": config_path.as_posix(),
            "sha256": expected_config_hash,
            "trading_policy_mode": policy.get("mode"),
            "daily_loss_basis": "sum of absolute negative realized close pnl values",
            "daily_loss_limit_usd": limit,
        },
        "inputs": {
            "trades_csv": {"path": trades_path.as_posix(), "sha256": _sha256(trades_path)},
            "breach_events_csv": {
                "path": breaches_path.as_posix(),
                "sha256": _sha256(breaches_path),
            },
        },
        "close_event_count": len(close_rows),
        "invalid_close_row_numbers": invalid_close_rows,
        "recorded_daily_loss_event_count": len(events),
        "event_reconciliations": event_results,
        "calendar_dates_with_gross_loss_at_or_above_limit": crossings,
        "calendar_date_crossings_without_recorded_event": unrecorded_crossing_dates,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit_gross_realized_loss_counter(args.run_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": result["status"],
                "close_event_count": result["close_event_count"],
                "daily_loss_events": result["recorded_daily_loss_event_count"],
                "calendar_date_crossings": len(
                    result["calendar_dates_with_gross_loss_at_or_above_limit"]
                ),
                "unrecorded_crossings": result["calendar_date_crossings_without_recorded_event"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
