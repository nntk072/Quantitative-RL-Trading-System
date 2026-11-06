"""Recalculate saved performance metrics from a run's timestamped equity series."""

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

import yaml


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _finite(value: str | None) -> float | None:
    try:
        result = float(value) if value else None
    except ValueError:
        return None
    return result if result is not None and math.isfinite(result) else None


def _timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return result.astimezone(UTC) if result.tzinfo is not None else None


def _daily_loss_event_reconciliation(
    run_dir: Path,
    local_timestamps: list[datetime],
    timestamps_utc: list[datetime],
    values: list[float],
) -> dict[str, Any]:
    """Compare recorded daily-loss events with the same-date equity series."""
    breach_path = run_dir / "breach_events.csv"
    reanalysis_path = run_dir.parent / "reanalysis_manifest.json"
    if not breach_path.is_file() or not reanalysis_path.is_file():
        return {"status": "unavailable", "reason": "breach ledger or reanalysis manifest is absent"}

    reanalysis = json.loads(reanalysis_path.read_text(encoding="utf-8"))
    source_run_value = reanalysis.get("source_run")
    expected_config_hash = reanalysis.get("source_config_sha256")
    if not isinstance(source_run_value, str) or not isinstance(expected_config_hash, str):
        return {"status": "incomplete", "reason": "source run or source config hash is absent"}
    config_path = Path(source_run_value) / "config.yaml"
    if not config_path.is_file():
        return {"status": "incomplete", "reason": "source config file is unavailable"}

    actual_config_hash = _sha256(config_path)
    if actual_config_hash != expected_config_hash:
        return {
            "status": "incomplete",
            "reason": "source config hash does not match the reanalysis manifest",
            "source_config_sha256": actual_config_hash,
            "expected_source_config_sha256": expected_config_hash,
        }
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        return {"status": "incomplete", "reason": "source config is not a mapping"}
    policy = config.get("trading_policy", {})
    repeated = policy.get("repeated_payout", {}) if isinstance(policy, dict) else {}
    ftmo = config.get("ftmo", {})
    ftmo_limit = _finite(str(ftmo.get("daily_loss_limit", ""))) if isinstance(ftmo, dict) else None
    policy_limit = (
        _finite(str(repeated.get("daily_loss_limit", ""))) if isinstance(repeated, dict) else None
    )
    configured_limit = ftmo_limit if ftmo_limit is not None else policy_limit

    equity_by_timestamp = dict(zip(timestamps_utc, values, strict=True))
    daily_values: dict[Any, list[tuple[datetime, float]]] = defaultdict(list)
    for local_timestamp, timestamp_utc, value in zip(
        local_timestamps, timestamps_utc, values, strict=True
    ):
        daily_values[local_timestamp.date()].append((timestamp_utc, value))

    events: list[dict[str, Any]] = []
    with breach_path.open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            if row.get("reason") != "daily_loss":
                continue
            event_local = _timestamp(row.get("time"))
            event_time = row.get("time")
            raw_local = None
            try:
                raw_local = (
                    datetime.fromisoformat(event_time.replace("Z", "+00:00"))
                    if event_time
                    else None
                )
            except ValueError:
                pass
            event_equity = _finite(row.get("equity"))
            if event_local is None or raw_local is None or event_equity is None:
                events.append(
                    {
                        "status": "invalid_event_row",
                        "session_id": row.get("session_id"),
                        "time": event_time,
                    }
                )
                continue
            date_rows = daily_values.get(raw_local.date(), [])
            series_equity = equity_by_timestamp.get(event_local)
            first_equity = date_rows[0][1] if date_rows else None
            day_minimum = min((value for _, value in date_rows), default=None)
            event_matches_series = series_equity is not None and math.isclose(
                series_equity, event_equity, rel_tol=1e-12, abs_tol=1e-7
            )
            drawdown_from_first = first_equity - event_equity if first_equity is not None else None
            events.append(
                {
                    "status": "matched" if event_matches_series else "equity_sample_mismatch",
                    "calendar_date": raw_local.date().isoformat(),
                    "session_id": row.get("session_id"),
                    "time": event_time,
                    "event_equity": event_equity,
                    "equity_series_at_event": series_equity,
                    "first_recorded_same_date_equity": first_equity,
                    "same_date_minimum_equity": day_minimum,
                    "event_is_same_date_minimum": day_minimum is not None
                    and math.isclose(event_equity, day_minimum, rel_tol=1e-12, abs_tol=1e-7),
                    "drawdown_from_first_recorded_same_date_equity": drawdown_from_first,
                    "configured_daily_loss_limit_usd": configured_limit,
                    "drawdown_below_configured_limit_from_first_recorded_equity": (
                        drawdown_from_first is not None
                        and configured_limit is not None
                        and drawdown_from_first < configured_limit
                    ),
                }
            )

    statuses = [event["status"] for event in events]
    limits_match = (
        ftmo_limit is not None
        and policy_limit is not None
        and math.isclose(ftmo_limit, policy_limit, rel_tol=1e-12, abs_tol=1e-7)
    )
    event_status = (
        "no_events"
        if not events
        else "matched"
        if all(value == "matched" for value in statuses) and limits_match
        else "mismatch"
        if "equity_sample_mismatch" in statuses or not limits_match
        else "incomplete"
    )
    recorded_daily_loss_dates = {
        str(event["calendar_date"]) for event in events if event.get("calendar_date")
    }

    daily_samples: list[dict[str, Any]] = []
    for calendar_date, day_rows in sorted(daily_values.items()):
        first_time, first_value = day_rows[0]
        min_time, min_value = min(day_rows, key=lambda item: item[1])
        last_time, last_value = day_rows[-1]
        drop = first_value - min_value
        reaches_limit = configured_limit is not None and drop >= configured_limit
        exceeds_limit = configured_limit is not None and drop > configured_limit
        daily_samples.append(
            {
                "calendar_date": calendar_date.isoformat(),
                "observation_count": len(day_rows),
                "first_observed_time_utc": first_time.isoformat(),
                "first_observed_equity": first_value,
                "minimum_time_utc": min_time.isoformat(),
                "minimum_equity": min_value,
                "last_observed_time_utc": last_time.isoformat(),
                "last_observed_equity": last_value,
                "drawdown_from_first_observation": drop,
                "configured_daily_loss_limit_usd": configured_limit,
                "first_sample_drawdown_at_or_above_limit": reaches_limit,
                "first_sample_drawdown_exceeds_limit": exceeds_limit,
                "recorded_daily_loss_event_on_date": calendar_date.isoformat()
                in recorded_daily_loss_dates,
            }
        )
    candidate_dates = [
        row["calendar_date"]
        for row in daily_samples
        if row["first_sample_drawdown_exceeds_limit"]
        and not row["recorded_daily_loss_event_on_date"]
    ]
    return {
        "status": event_status,
        "event_count": len(events),
        "matched_event_count": statuses.count("matched"),
        "source_configuration": {
            "path": config_path.as_posix(),
            "sha256": actual_config_hash,
            "trading_policy_mode": policy.get("mode") if isinstance(policy, dict) else None,
            "ftmo_daily_loss_limit_usd": ftmo_limit,
            "repeated_payout_daily_loss_limit_usd": policy_limit,
            "limits_match": limits_match,
        },
        "basis": "calendar date from supplied equity timestamps; first recorded same-date equity is not asserted to equal the risk-reset baseline",
        "events": events,
        "sampled_day_count": len(daily_samples),
        "sampled_days_with_drawdown_at_or_above_limit": sum(
            row["first_sample_drawdown_at_or_above_limit"] for row in daily_samples
        ),
        "sampled_days_with_drawdown_exceeding_limit": sum(
            row["first_sample_drawdown_exceeds_limit"] for row in daily_samples
        ),
        "unmatched_first_sample_crossing_dates": candidate_dates,
        "daily_sample_summaries": daily_samples,
    }


def _max_loss_event_reconciliation(
    run_dir: Path,
    timestamps_utc: list[datetime],
    values: list[float],
    initial_balance: float | None,
) -> dict[str, Any]:
    """Reconcile recorded hard maximum-loss events with the pinned balance floor.

    This checks the configured initial-equity hard-loss floor. When the source
    run does not record a drawdown mode, it does not infer an EOD or trailing
    reference from current defaults.
    """
    breach_path = run_dir / "breach_events.csv"
    manifest_path = run_dir.parent / "reanalysis_manifest.json"
    if initial_balance is None or not breach_path.is_file() or not manifest_path.is_file():
        return {
            "status": "unavailable",
            "reason": "initial balance, breach ledger, or reanalysis manifest is absent",
        }

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source_run_value = manifest.get("source_run")
    expected_config_hash = manifest.get("source_config_sha256")
    if not isinstance(source_run_value, str) or not isinstance(expected_config_hash, str):
        return {"status": "incomplete", "reason": "source run or source config hash is absent"}
    config_path = Path(source_run_value) / "config.yaml"
    if not config_path.is_file():
        return {"status": "incomplete", "reason": "source config file is unavailable"}
    actual_config_hash = _sha256(config_path)
    if actual_config_hash != expected_config_hash:
        return {
            "status": "incomplete",
            "reason": "source config hash does not match the reanalysis manifest",
            "source_config_sha256": actual_config_hash,
            "expected_source_config_sha256": expected_config_hash,
        }

    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        return {"status": "incomplete", "reason": "source config is not a mapping"}
    ftmo = config.get("ftmo", {})
    if not isinstance(ftmo, dict):
        return {"status": "incomplete", "reason": "source ftmo config is not a mapping"}
    value_mode = ftmo.get("limit_value_mode", "fixed_usd")
    if value_mode == "percent_equity":
        pct = _finite(str(ftmo.get("max_loss_limit_initial_pct", "")))
        allowance = initial_balance * pct if pct is not None else None
    elif value_mode == "fixed_usd":
        allowance = _finite(str(ftmo.get("max_loss_limit", "")))
    else:
        allowance = None
    if allowance is None or allowance <= 0.0:
        return {
            "status": "incomplete",
            "reason": "source config does not resolve a positive maximum-loss allowance",
            "limit_value_mode": value_mode,
        }
    floor = initial_balance - allowance

    equity_by_timestamp = dict(zip(timestamps_utc, values, strict=True))
    first_crossing = next(
        (
            {"time_utc": timestamp.isoformat(), "equity": equity}
            for timestamp, equity in zip(timestamps_utc, values, strict=True)
            if equity < floor
        ),
        None,
    )
    events: list[dict[str, Any]] = []
    with breach_path.open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            if row.get("reason") != "max_drawdown":
                continue
            event_time = _timestamp(row.get("time"))
            fill_time = _timestamp(row.get("fill_time"))
            event_equity = _finite(row.get("equity"))
            timestamp_candidates = [
                ("fill_time", fill_time),
                ("event_time", event_time),
            ]
            matching_timestamp = next(
                (
                    (basis, timestamp, equity_by_timestamp[timestamp])
                    for basis, timestamp in timestamp_candidates
                    if timestamp is not None
                    and timestamp in equity_by_timestamp
                    and event_equity is not None
                    and math.isclose(
                        equity_by_timestamp[timestamp],
                        event_equity,
                        rel_tol=1e-12,
                        abs_tol=1e-7,
                    )
                ),
                None,
            )
            observation_basis, observation_time = (
                matching_timestamp[:2]
                if matching_timestamp is not None
                else next(
                    ((basis, timestamp) for basis, timestamp in timestamp_candidates if timestamp),
                    (None, None),
                )
            )
            series_equity = (
                matching_timestamp[2]
                if matching_timestamp is not None
                else equity_by_timestamp.get(observation_time)
                if observation_time is not None
                else None
            )
            exact_match = matching_timestamp is not None
            events.append(
                {
                    "time_utc": event_time.isoformat() if event_time is not None else None,
                    "fill_time_utc": fill_time.isoformat() if fill_time is not None else None,
                    "equity_observation_time_utc": (
                        observation_time.isoformat() if observation_time is not None else None
                    ),
                    "equity_observation_time_basis": observation_basis,
                    "event_equity": event_equity,
                    "equity_series_at_event": series_equity,
                    "event_matches_equity_sample": exact_match,
                    "below_configured_initial_equity_floor": (
                        event_equity is not None and event_equity < floor
                    ),
                }
            )

    if events:
        status = (
            "matched"
            if all(
                event["event_matches_equity_sample"]
                and event["below_configured_initial_equity_floor"]
                for event in events
            )
            else "mismatch"
        )
        if first_crossing is not None and not any(
            event["equity_observation_time_utc"] == first_crossing["time_utc"] for event in events
        ):
            status = "mismatch"
    elif first_crossing is not None:
        status = "mismatch"
    else:
        status = "no_events"

    return {
        "status": status,
        "breach_ledger": {
            "path": breach_path.as_posix(),
            "bytes": breach_path.stat().st_size,
            "sha256": _sha256(breach_path),
        },
        "source_configuration": {
            "path": config_path.as_posix(),
            "sha256": actual_config_hash,
            "limit_value_mode": value_mode,
            "max_drawdown_mode": ftmo.get("max_drawdown_mode"),
            "max_drawdown_mode_recorded": "max_drawdown_mode" in ftmo,
            "maximum_loss_allowance": allowance,
            "initial_equity_floor": floor,
        },
        "recorded_max_loss_event_count": len(events),
        "events": events,
        "first_observed_equity_below_initial_floor": first_crossing,
        "scope": "Exact event/equity linkage and the pinned initial-equity maximum-loss floor only; when drawdown mode is unrecorded, no EOD or intraday peak reference is inferred.",
    }


def _session_equity_risk_screen(
    timestamps: list[datetime],
    values: list[float],
    session_ids: list[int],
    *,
    initial_balance: float,
    daily_loss_limit_pct: float,
) -> dict[str, Any]:
    """Screen observed equity against the active session-net daily-loss rule."""
    if not (len(timestamps) == len(values) == len(session_ids)):
        return {"status": "incomplete", "reason": "equity/session row counts differ"}
    if not values:
        return {"status": "incomplete", "reason": "equity series is empty"}
    if any(current < previous for previous, current in zip(session_ids, session_ids[1:])):
        return {"status": "mismatch", "reason": "session IDs decrease in equity chronology"}

    loss_allowance = initial_balance * daily_loss_limit_pct
    rows: list[dict[str, Any]] = []
    current_session = session_ids[0]
    opening_equity = initial_balance
    minimum_equity = values[0]
    minimum_time = timestamps[0]
    first_crossing: dict[str, Any] | None = None
    previous_equity = values[0]

    def finish_session() -> None:
        rows.append(
            {
                "session_id": current_session,
                "opening_equity_anchor": opening_equity,
                "daily_loss_floor": opening_equity - loss_allowance,
                "minimum_equity": minimum_equity,
                "minimum_time_utc": minimum_time.isoformat(),
                "maximum_observed_loss": max(0.0, opening_equity - minimum_equity),
                "breached_on_observed_path": first_crossing is not None,
                "first_breach": first_crossing,
            }
        )

    for timestamp, equity, session_id in zip(
        timestamps[1:], values[1:], session_ids[1:], strict=True
    ):
        if session_id != current_session:
            finish_session()
            current_session = session_id
            # Both runtimes reset from the last account equity before processing
            # the first bar in the new supplied session.
            opening_equity = previous_equity
            minimum_equity = equity
            minimum_time = timestamp
            first_crossing = None
        if equity < minimum_equity:
            minimum_equity = equity
            minimum_time = timestamp
        if first_crossing is None and equity < opening_equity - loss_allowance:
            first_crossing = {
                "time_utc": timestamp.isoformat(),
                "equity": equity,
                "loss_from_session_open": opening_equity - equity,
            }
        previous_equity = equity
    finish_session()

    return {
        "status": "verified_observed_path",
        "basis": "session_net_equity; each new supplied session anchors to the previous equity observation before the new bar is marked to market",
        "initial_balance": initial_balance,
        "daily_loss_limit_pct_of_initial": daily_loss_limit_pct,
        "daily_loss_allowance": loss_allowance,
        "session_count": len(rows),
        "sessions_breaching_daily_limit": sum(row["breached_on_observed_path"] for row in rows),
        "sessions": rows,
        "counterfactual_limit": "This screens the preserved equity path under the current daily-loss rule. The historical run used its pinned historical policy; trades after any change in blocked-entry behavior are not reconstructed.",
    }


def _map_equity_session_ids(
    timestamps: list[datetime],
    *,
    timezone: ZoneInfo,
    date_to_session: dict[str, int],
    timestamp_to_session: dict[datetime, int],
) -> tuple[list[int], int, list[str]]:
    """Resolve bar and sub-bar equity times to the supplied date-based session IDs."""
    session_ids: list[int] = []
    exact_timestamp_matches = 0
    missing_dates: list[str] = []
    for timestamp in timestamps:
        session_id = timestamp_to_session.get(timestamp)
        if session_id is not None:
            exact_timestamp_matches += 1
        else:
            local_date = timestamp.astimezone(timezone).date().isoformat()
            session_id = date_to_session.get(local_date)
            if session_id is None:
                missing_dates.append(local_date)
                continue
        session_ids.append(session_id)
    return session_ids, exact_timestamp_matches, missing_dates


def _observed_session_equity_risk_screen(
    run_dir: Path,
    timestamps: list[datetime],
    values: list[float],
    initial_balance: float,
) -> dict[str, Any]:
    """Join saved equity observations to configured local M1 session labels."""
    manifest_path = run_dir.parent / "reanalysis_manifest.json"
    if not manifest_path.is_file():
        return {"status": "unavailable", "reason": "reanalysis manifest is absent"}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source_run_value = manifest.get("source_run")
    expected_config_hash = manifest.get("source_config_sha256")
    if not isinstance(source_run_value, str) or not isinstance(expected_config_hash, str):
        return {"status": "incomplete", "reason": "source run/config identity is absent"}
    source_run = Path(source_run_value)
    config_path = source_run / "config.yaml"
    if not config_path.is_file() or _sha256(config_path) != expected_config_hash:
        return {"status": "incomplete", "reason": "pinned source config is missing or changed"}

    import yaml

    source_config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(source_config, dict):
        return {"status": "incomplete", "reason": "pinned source config is not a mapping"}
    dataset_name = run_dir.name
    if dataset_name not in {"training", "testing"}:
        return {"status": "incomplete", "reason": "run directory is not a named split"}

    # The source map verifier checks raw row count, unique timestamps, and bounds
    # against the exact processed-bar manifest before any session IDs are used.
    from scripts.research.analysis.evaluation.audit_gross_realized_loss_counter import (
        _configured_session_map,
    )

    date_to_session, source_identity = _configured_session_map(
        source_config, manifest, source_run, dataset_name
    )
    if source_identity.get("status") != "verified":
        return {
            "status": "incomplete",
            "reason": "configured M1 source/session identity did not verify",
            "source_identity": source_identity,
        }
    data = source_config["data"]
    dataset = data["datasets"][dataset_name]
    source_path = Path(dataset["raw_dir"]) / dataset["m1_files"][data["primary"]]
    if not source_path.is_absolute():
        source_path = Path(__file__).resolve().parents[4] / source_path
    timezone = ZoneInfo(str(data["tz"]))

    timestamp_to_session: dict[datetime, int] = {}
    with source_path.open(newline="", encoding="utf-8-sig") as source:
        reader = csv.reader(source, delimiter="\t")
        header = [cell.strip().strip("<>").lower() for cell in next(reader)]
        date_column, time_column = header.index("date"), header.index("time")
        for row in reader:
            local_time = datetime.strptime(
                f"{row[date_column].strip()} {row[time_column].strip()}", "%Y.%m.%d %H:%M:%S"
            ).replace(tzinfo=timezone)
            session_id = date_to_session.get(local_time.date().isoformat())
            if session_id is not None:
                timestamp_to_session[local_time.astimezone(UTC)] = session_id

    session_ids, exact_timestamp_matches, missing_dates = _map_equity_session_ids(
        timestamps,
        timezone=timezone,
        date_to_session=date_to_session,
        timestamp_to_session=timestamp_to_session,
    )
    if missing_dates:
        return {
            "status": "incomplete",
            "reason": "some saved equity dates do not have a configured M1 session label",
            "missing_date_count": len(missing_dates),
            "missing_date_examples": sorted(set(missing_dates))[:10],
            "source_identity": source_identity,
        }

    repository_root = Path(__file__).resolve().parents[4]
    active_config_path = repository_root / "config/base/default.yaml"
    active_config = yaml.safe_load(active_config_path.read_text(encoding="utf-8"))
    ftmo = active_config.get("ftmo", {}) if isinstance(active_config, dict) else {}
    if not isinstance(ftmo, dict) or ftmo.get("limit_value_mode") != "percent_equity":
        return {
            "status": "incomplete",
            "reason": "active canonical risk config is not percentage-based",
            "active_config_path": active_config_path.as_posix(),
        }
    percentage = float(ftmo["daily_loss_limit_pct"])
    result = _session_equity_risk_screen(
        timestamps,
        values,
        session_ids,
        initial_balance=initial_balance,
        daily_loss_limit_pct=percentage,
    )
    result["source_session_identity"] = source_identity
    result["active_risk_config"] = {
        "path": active_config_path.as_posix(),
        "sha256": _sha256(active_config_path),
        "limit_value_mode": "percent_equity",
        "daily_loss_limit_pct": percentage,
    }
    result["equity_observation_count"] = len(timestamps)
    result["equity_exact_m1_timestamp_match_count"] = exact_timestamp_matches
    result["equity_subbar_or_nonbar_same_date_count"] = len(timestamps) - exact_timestamp_matches
    result["equity_date_unmatched_count"] = 0
    result["session_mapping_method"] = (
        "exact M1 timestamp when present; otherwise the verified source-local date label, "
        "because supplied session IDs are assigned from sorted unique dates"
    )
    result["m1_source"] = {
        "path": source_path.as_posix(),
        "sha256": _sha256(source_path),
    }
    return result


def audit_recorded_equity_series(run_dir: Path) -> dict[str, Any]:
    """Check chronology and recompute endpoint return and maximum drawdown."""
    root = run_dir.expanduser().resolve(strict=True)
    equity_path = root / "equity.csv"
    metrics_path = root / "metrics.json"
    if not equity_path.is_file() or not metrics_path.is_file():
        raise FileNotFoundError(f"equity.csv and metrics.json are required under {root}")

    with equity_path.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames is None or "equity" not in reader.fieldnames:
            raise ValueError("equity.csv must contain an 'equity' column")
        timestamp_column = next((name for name in reader.fieldnames if name != "equity"), None)
        if timestamp_column is None:
            raise ValueError("equity.csv must contain a timestamp index column")
        rows = list(reader)

    timestamps: list[datetime] = []
    local_timestamps: list[datetime] = []
    values: list[float] = []
    row_errors: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        raw_timestamp = row.get(timestamp_column)
        timestamp = _timestamp(raw_timestamp)
        value = _finite(row.get("equity"))
        if timestamp is None or value is None:
            row_errors.append(
                {
                    "row": index + 2,
                    "timestamp_valid": timestamp is not None,
                    "equity_valid": value is not None,
                }
            )
            continue
        timestamps.append(timestamp)
        local_timestamps.append(datetime.fromisoformat(str(raw_timestamp).replace("Z", "+00:00")))
        values.append(value)

    chronology_failures = sum(
        current <= previous for previous, current in zip(timestamps, timestamps[1:])
    )
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    initial_balance = _finite(str(metrics.get("initial_balance", "")))
    reported_final = _finite(str(metrics.get("final_equity", "")))
    reported_return = _finite(str(metrics.get("total_return_pct", "")))
    reported_drawdown = _finite(str(metrics.get("max_drawdown", "")))
    if not values:
        raise ValueError("equity.csv contains no finite, timestamped observations")

    first_equity, final_equity = values[0], values[-1]
    calculated_return = (final_equity / first_equity - 1.0) * 100.0 if first_equity else None
    peak = values[0]
    max_drawdown = 0.0
    for value in values:
        peak = max(peak, value)
        if peak > 0:
            max_drawdown = max(max_drawdown, (peak - value) / peak)

    checks: dict[str, dict[str, Any]] = {}

    def compare(name: str, actual: float | None, expected: float | None) -> None:
        difference = actual - expected if actual is not None and expected is not None else None
        matched = difference is not None and math.isclose(
            difference, 0.0, rel_tol=1e-10, abs_tol=1e-7
        )
        checks[name] = {
            "status": "matched"
            if matched
            else "mismatch"
            if difference is not None
            else "unavailable",
            "recalculated": actual,
            "reported": expected,
            "difference": difference,
        }

    compare("first_equity_matches_initial_balance", first_equity, initial_balance)
    compare("last_equity_matches_final_equity", final_equity, reported_final)
    compare("total_return_matches_equity_endpoints_pct", calculated_return, reported_return)
    compare("max_drawdown_matches_equity_series_fraction", max_drawdown, reported_drawdown)
    daily_loss_event_reconciliation = _daily_loss_event_reconciliation(
        root, local_timestamps, timestamps, values
    )
    observed_session_equity_risk_screen = (
        _observed_session_equity_risk_screen(
            root, timestamps, values, initial_balance=initial_balance
        )
        if initial_balance is not None
        else {"status": "incomplete", "reason": "initial balance is unavailable"}
    )
    max_loss_event_reconciliation = _max_loss_event_reconciliation(
        root, timestamps, values, initial_balance
    )

    statuses = [check["status"] for check in checks.values()]
    status = (
        "mismatch"
        if chronology_failures or row_errors or "mismatch" in statuses
        else ("matched" if all(value == "matched" for value in statuses) else "incomplete")
    )
    return {
        "schema": "qrl.recorded_equity_series_audit.v2",
        "status": status,
        "scope": {
            "run_directory": root.as_posix(),
            "independent_recalculation": True,
            "policy_replay_performed": False,
            "daily_account_risk_recomputed": False,
            "recorded_max_loss_event_reconciled": max_loss_event_reconciliation.get("status")
            in {"matched", "no_events"},
            "observed_session_equity_risk_screen_computed": (
                observed_session_equity_risk_screen.get("status") == "verified_observed_path"
            ),
        },
        "inputs": {
            "equity.csv": {
                "path": equity_path.as_posix(),
                "bytes": equity_path.stat().st_size,
                "sha256": _sha256(equity_path),
            },
            "metrics.json": {
                "path": metrics_path.as_posix(),
                "bytes": metrics_path.stat().st_size,
                "sha256": _sha256(metrics_path),
            },
        },
        "observation_count": len(rows),
        "valid_observation_count": len(values),
        "invalid_row_count": len(row_errors),
        "chronology_failure_count": chronology_failures,
        "time_range_utc": {"start": timestamps[0].isoformat(), "end": timestamps[-1].isoformat()},
        "equity_range": {"minimum": min(values), "maximum": max(values)},
        "calculated": {
            "first_equity": first_equity,
            "final_equity": final_equity,
            "total_return_pct": calculated_return,
            "max_drawdown_fraction": max_drawdown,
        },
        "checks": checks,
        "daily_loss_event_reconciliation": daily_loss_event_reconciliation,
        "max_loss_event_reconciliation": max_loss_event_reconciliation,
        "observed_session_equity_risk_screen": observed_session_equity_risk_screen,
        "row_errors": row_errors,
        "limitations": [
            "This recalculates serialized equity-series metrics only; it does not independently reconstruct mark-to-market equity from market data or reconcile daily risk state with fills.",
            "Recorded maximum-loss events are compared to the pinned initial-equity floor only; an unrecorded drawdown mode is not inferred from current defaults.",
            "The session equity screen maps every equity sample to the configured local M1 session ID and applies the current percentage rule to the observed historical path; it does not replay trades that would differ after a daily-risk block.",
            "A matched summary does not validate the simulator, source quotes, policy behavior, or economic merit.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit_recorded_equity_series(args.run_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {key: value for key, value in report.items() if key not in {"row_errors"}}
    daily = dict(summary["daily_loss_event_reconciliation"])
    daily.pop("daily_sample_summaries", None)
    summary["daily_loss_event_reconciliation"] = daily
    session_screen = dict(summary["observed_session_equity_risk_screen"])
    session_screen.pop("sessions", None)
    summary["observed_session_equity_risk_screen"] = session_screen
    print(json.dumps(summary, indent=2))
    return 0 if report["status"] == "matched" else 1


if __name__ == "__main__":
    raise SystemExit(main())
