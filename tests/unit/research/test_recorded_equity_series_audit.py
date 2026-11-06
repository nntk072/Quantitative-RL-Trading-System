"""Tests for independent saved-equity metric recalculation."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.research.analysis.evaluation.audit_recorded_equity_series import (
    _daily_loss_event_reconciliation,
    _map_equity_session_ids,
    _max_loss_event_reconciliation,
    _session_equity_risk_screen,
    audit_recorded_equity_series,
)


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _run_dir(
    root: Path,
    *,
    timestamps: list[str] | None = None,
    values: list[float] | None = None,
    max_drawdown: float = 20.0 / 110.0,
) -> Path:
    root.mkdir(parents=True)
    times = timestamps or [
        "2025-01-02T12:00:00+00:00",
        "2025-01-02T12:01:00+00:00",
        "2025-01-02T12:02:00+00:00",
        "2025-01-02T12:03:00+00:00",
    ]
    equity = values or [100.0, 110.0, 105.0, 90.0]
    with (root / "equity.csv").open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=["", "equity"])
        writer.writeheader()
        writer.writerows(
            {"": timestamp, "equity": value} for timestamp, value in zip(times, equity, strict=True)
        )
    metrics = {
        "initial_balance": 100.0,
        "final_equity": 90.0,
        "total_return_pct": -10.0,
        "max_drawdown": max_drawdown,
    }
    (root / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
    return root


def test_recalculates_saved_equity_endpoint_return_and_drawdown(tmp_path: Path) -> None:
    report = audit_recorded_equity_series(_run_dir(tmp_path / "run"))

    assert report["status"] == "matched"
    assert report["observation_count"] == 4
    assert abs(report["calculated"]["total_return_pct"] + 10.0) < 1e-10
    assert report["checks"]["max_drawdown_matches_equity_series_fraction"]["status"] == "matched"


def test_detects_disagreement_with_reported_drawdown(tmp_path: Path) -> None:
    report = audit_recorded_equity_series(_run_dir(tmp_path / "run", max_drawdown=0.2))

    assert report["status"] == "mismatch"
    assert report["checks"]["max_drawdown_matches_equity_series_fraction"]["status"] == "mismatch"


def test_detects_nonincreasing_equity_timestamps(tmp_path: Path) -> None:
    report = audit_recorded_equity_series(
        _run_dir(
            tmp_path / "run",
            timestamps=[
                "2025-01-02T12:00:00+00:00",
                "2025-01-02T12:01:00+00:00",
                "2025-01-02T12:01:00+00:00",
                "2025-01-02T12:03:00+00:00",
            ],
        )
    )

    assert report["status"] == "mismatch"
    assert report["chronology_failure_count"] == 1


def test_reconciles_daily_loss_event_to_equity_sample_and_pinned_limit(tmp_path: Path) -> None:
    run_dir = _run_dir(tmp_path / "reanalysis" / "arm" / "training")
    source_run = tmp_path / "source-run"
    source_run.mkdir()
    config_path = source_run / "config.yaml"
    config_path.write_text(
        "trading_policy:\n  mode: legacy\n  repeated_payout:\n    daily_loss_limit: 5000.0\n"
        "ftmo:\n  daily_loss_limit: 5000.0\n",
        encoding="utf-8",
    )
    source_hash = hashlib.sha256(config_path.read_bytes()).hexdigest()
    (run_dir.parent / "reanalysis_manifest.json").write_text(
        json.dumps({"source_run": str(source_run), "source_config_sha256": source_hash}),
        encoding="utf-8",
    )
    _write_csv(
        run_dir / "breach_events.csv",
        ["time", "session_id", "reason", "equity"],
        [
            {
                "time": "2025-01-02T12:03:00+00:00",
                "session_id": "1",
                "reason": "daily_loss",
                "equity": "90.0",
            }
        ],
    )

    report = audit_recorded_equity_series(run_dir)

    event_audit = report["daily_loss_event_reconciliation"]
    assert event_audit["status"] == "matched"
    assert event_audit["source_configuration"]["trading_policy_mode"] == "legacy"
    assert event_audit["events"][0]["event_is_same_date_minimum"] is True
    assert event_audit["events"][0]["drawdown_from_first_recorded_same_date_equity"] == 10.0
    assert (
        event_audit["events"][0]["drawdown_below_configured_limit_from_first_recorded_equity"]
        is True
    )
    assert event_audit["sampled_day_count"] == 1
    assert event_audit["sampled_days_with_drawdown_at_or_above_limit"] == 0


def test_daily_loss_sample_equality_is_allowed_but_strict_crossing_is_counted(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "reanalysis" / "arm" / "training"
    run_dir.mkdir(parents=True)
    source_run = tmp_path / "source-run"
    source_run.mkdir()
    config_path = source_run / "config.yaml"
    config_path.write_text(
        "trading_policy:\n  repeated_payout:\n    daily_loss_limit: 10.0\n"
        "ftmo:\n  daily_loss_limit: 10.0\n",
        encoding="utf-8",
    )
    config_hash = hashlib.sha256(config_path.read_bytes()).hexdigest()
    (run_dir.parent / "reanalysis_manifest.json").write_text(
        json.dumps({"source_run": str(source_run), "source_config_sha256": config_hash}),
        encoding="utf-8",
    )
    _write_csv(run_dir / "breach_events.csv", ["time", "reason", "equity"], [])
    timestamps = [
        datetime(2025, 1, 2, 12, tzinfo=UTC),
        datetime(2025, 1, 2, 12, 1, tzinfo=UTC),
        datetime(2025, 1, 3, 12, tzinfo=UTC),
        datetime(2025, 1, 3, 12, 1, tzinfo=UTC),
    ]

    report = _daily_loss_event_reconciliation(
        run_dir,
        [timestamp.astimezone(ZoneInfo("UTC")) for timestamp in timestamps],
        timestamps,
        [100.0, 90.0, 100.0, 89.99],
    )

    equality_day, crossing_day = report["daily_sample_summaries"]
    assert equality_day["first_sample_drawdown_at_or_above_limit"] is True
    assert equality_day["first_sample_drawdown_exceeds_limit"] is False
    assert crossing_day["first_sample_drawdown_exceeds_limit"] is True
    assert report["sampled_days_with_drawdown_at_or_above_limit"] == 2
    assert report["sampled_days_with_drawdown_exceeding_limit"] == 1
    assert report["unmatched_first_sample_crossing_dates"] == ["2025-01-03"]


def _max_loss_fixture(tmp_path: Path, events: list[dict[str, str]]) -> Path:
    run_dir = tmp_path / "reanalysis" / "arm" / "training"
    run_dir.mkdir(parents=True)
    source_run = tmp_path / "source-run"
    source_run.mkdir()
    config_path = source_run / "config.yaml"
    config_path.write_text(
        "ftmo:\n  limit_value_mode: fixed_usd\n  max_loss_limit: 10.0\n",
        encoding="utf-8",
    )
    config_hash = hashlib.sha256(config_path.read_bytes()).hexdigest()
    (run_dir.parent / "reanalysis_manifest.json").write_text(
        json.dumps({"source_run": str(source_run), "source_config_sha256": config_hash}),
        encoding="utf-8",
    )
    _write_csv(
        run_dir / "breach_events.csv",
        ["time", "reason", "equity", "fill_time"],
        events,
    )
    return run_dir


def test_reconciles_static_max_loss_event_to_exact_equity_and_floor(tmp_path: Path) -> None:
    start = datetime(2025, 1, 2, 12, 0, tzinfo=UTC)
    timestamps = [start + timedelta(minutes=index) for index in range(3)]
    run_dir = _max_loss_fixture(
        tmp_path,
        [
            {
                "time": timestamps[-1].isoformat(),
                "reason": "max_drawdown",
                "equity": "89.99",
            }
        ],
    )

    report = _max_loss_event_reconciliation(
        run_dir, timestamps, [100.0, 95.0, 89.99], initial_balance=100.0
    )

    assert report["status"] == "matched"
    assert report["source_configuration"]["initial_equity_floor"] == 90.0
    assert report["source_configuration"]["max_drawdown_mode_recorded"] is False
    assert report["events"][0]["event_matches_equity_sample"] is True
    assert report["events"][0]["below_configured_initial_equity_floor"] is True
    assert (
        report["first_observed_equity_below_initial_floor"]["time_utc"]
        == timestamps[-1].isoformat()
    )


def test_uses_liquidation_fill_time_for_post_fill_breach_equity(tmp_path: Path) -> None:
    start = datetime(2025, 1, 2, 12, 0, tzinfo=UTC)
    timestamps = [start + timedelta(minutes=index) for index in range(3)]
    run_dir = _max_loss_fixture(
        tmp_path,
        [
            {
                "time": timestamps[1].isoformat(),
                "reason": "max_drawdown",
                "equity": "89.99",
                "fill_time": timestamps[-1].isoformat(),
            }
        ],
    )

    report = _max_loss_event_reconciliation(
        run_dir, timestamps, [100.0, 95.0, 89.99], initial_balance=100.0
    )

    assert report["status"] == "matched"
    assert report["events"][0]["time_utc"] == timestamps[1].isoformat()
    assert report["events"][0]["equity_observation_time_basis"] == "fill_time"
    assert report["events"][0]["equity_observation_time_utc"] == timestamps[-1].isoformat()
    assert report["events"][0]["event_matches_equity_sample"] is True


def test_uses_event_bar_time_when_it_matches_recorded_equity(tmp_path: Path) -> None:
    start = datetime(2025, 1, 2, 12, 0, tzinfo=UTC)
    timestamps = [start + timedelta(minutes=index) for index in range(3)]
    run_dir = _max_loss_fixture(
        tmp_path,
        [
            {
                "time": timestamps[-1].isoformat(),
                "reason": "max_drawdown",
                "equity": "89.99",
                "fill_time": (timestamps[-1] + timedelta(milliseconds=110)).isoformat(),
            }
        ],
    )

    report = _max_loss_event_reconciliation(
        run_dir, timestamps, [100.0, 95.0, 89.99], initial_balance=100.0
    )

    assert report["status"] == "matched"
    assert report["events"][0]["equity_observation_time_basis"] == "event_time"
    assert report["events"][0]["equity_observation_time_utc"] == timestamps[-1].isoformat()
    assert report["events"][0]["event_matches_equity_sample"] is True


def test_allows_equality_at_static_max_loss_floor_without_breach(tmp_path: Path) -> None:
    start = datetime(2025, 1, 2, 12, 0, tzinfo=UTC)
    timestamps = [start, start + timedelta(minutes=1)]
    run_dir = _max_loss_fixture(tmp_path, [])

    report = _max_loss_event_reconciliation(
        run_dir, timestamps, [100.0, 90.0], initial_balance=100.0
    )

    assert report["status"] == "no_events"
    assert report["first_observed_equity_below_initial_floor"] is None


def test_session_equity_screen_reanchors_and_applies_percentage_limit() -> None:
    start = datetime(2025, 1, 1, tzinfo=UTC)
    timestamps = [start + timedelta(minutes=index) for index in range(6)]
    report = _session_equity_risk_screen(
        timestamps,
        [100_000.0, 102_000.0, 102_000.0, 101_000.0, 101_000.0, 96_000.0],
        [0, 0, 1, 1, 2, 2],
        initial_balance=100_000.0,
        daily_loss_limit_pct=0.05,
    )

    assert report["status"] == "verified_observed_path"
    assert report["daily_loss_allowance"] == 5_000.0
    assert report["sessions_breaching_daily_limit"] == 0
    assert report["sessions"][1]["opening_equity_anchor"] == 102_000.0
    assert report["sessions"][1]["daily_loss_floor"] == 97_000.0
    assert report["sessions"][1]["breached_on_observed_path"] is False
    assert report["sessions"][2]["opening_equity_anchor"] == 101_000.0
    assert report["sessions"][2]["daily_loss_floor"] == 96_000.0
    assert report["sessions"][2]["first_breach"] is None

    below_floor = _session_equity_risk_screen(
        [start, start + timedelta(minutes=1)],
        [100_000.0, 94_999.99],
        [0, 0],
        initial_balance=100_000.0,
        daily_loss_limit_pct=0.05,
    )
    assert below_floor["sessions_breaching_daily_limit"] == 1
    assert below_floor["sessions"][0]["first_breach"]["loss_from_session_open"] > 5_000.0


def test_session_equity_screen_rejects_decreasing_session_ids() -> None:
    start = datetime(2025, 1, 1, tzinfo=UTC)
    report = _session_equity_risk_screen(
        [start, start + timedelta(minutes=1)],
        [100_000.0, 100_000.0],
        [1, 0],
        initial_balance=100_000.0,
        daily_loss_limit_pct=0.05,
    )

    assert report["status"] == "mismatch"


def test_session_mapping_uses_verified_local_date_for_subbar_times() -> None:
    timestamps = [
        datetime(2025, 1, 1, 21, 0, tzinfo=UTC),
        datetime(2025, 1, 1, 21, 1, 30, tzinfo=UTC),
        datetime(2025, 1, 1, 21, 2, tzinfo=UTC),
    ]
    session_ids, exact_matches, missing_dates = _map_equity_session_ids(
        timestamps,
        timezone=ZoneInfo("Etc/GMT-3"),
        date_to_session={"2025-01-02": 7},
        timestamp_to_session={timestamps[0]: 7, timestamps[2]: 7},
    )

    assert session_ids == [7, 7, 7]
    assert exact_matches == 2
    assert missing_dates == []

    unresolved = _map_equity_session_ids(
        [datetime(2025, 1, 3, 21, 0, tzinfo=UTC)],
        timezone=ZoneInfo("Etc/GMT-3"),
        date_to_session={"2025-01-02": 7},
        timestamp_to_session={},
    )
    assert unresolved == ([], 0, ["2025-01-04"])
