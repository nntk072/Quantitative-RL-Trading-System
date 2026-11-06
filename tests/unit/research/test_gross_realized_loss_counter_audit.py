"""Tests for historical gross realized-loss trade-event reconciliation."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from scripts.research.analysis.evaluation.audit_gross_realized_loss_counter import (
    audit_gross_realized_loss_counter,
)


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_audit_reconstructs_historical_gross_loss_from_raw_close_pnl(tmp_path: Path) -> None:
    source_run = tmp_path / "source"
    source_run.mkdir()
    config = source_run / "config.yaml"
    config.write_text(
        "trading_policy:\n  mode: legacy\nftmo:\n  daily_loss_limit: 5000\n",
        encoding="utf-8",
    )
    run_dir = tmp_path / "reanalysis" / "arm" / "training"
    run_dir.mkdir(parents=True)
    config_hash = hashlib.sha256(config.read_bytes()).hexdigest()
    (run_dir.parent / "reanalysis_manifest.json").write_text(
        json.dumps({"source_run": str(source_run), "source_config_sha256": config_hash}),
        encoding="utf-8",
    )
    trade_fields = ["type", "fill_time", "time", "pnl", "net_pnl", "position_id"]
    _write_csv(
        run_dir / "trades.csv",
        trade_fields,
        [
            {
                "type": "stop_close",
                "fill_time": "2025-03-06T17:00:00+00:00",
                "time": "2025-03-06T17:00:00+00:00",
                "pnl": "-3000",
                "net_pnl": "-3200",
                "position_id": "p1",
            },
            {
                "type": "tp_partial_close",
                "fill_time": "2025-03-06T17:02:00+00:00",
                "time": "2025-03-06T17:02:00+00:00",
                "pnl": "-2500",
                "net_pnl": "-2600",
                "position_id": "p2",
            },
            {
                "type": "stop_close",
                "fill_time": "2025-03-07T17:00:00+00:00",
                "time": "2025-03-07T17:00:00+00:00",
                "pnl": "-5100",
                "net_pnl": "-5200",
                "position_id": "p3",
            },
        ],
    )
    _write_csv(
        run_dir / "breach_events.csv",
        ["time", "session_id", "reason", "equity", "fill_time"],
        [
            {
                "time": "2025-03-06T17:04:00+00:00",
                "session_id": "47",
                "reason": "daily_loss",
                "equity": "90000",
                "fill_time": "2025-03-06T17:04:00+00:00",
            }
        ],
    )

    result = audit_gross_realized_loss_counter(run_dir)

    assert result["status"] == "mismatch"
    assert result["event_reconciliations"][0]["status"] == "crossed_before_event"
    assert result["event_reconciliations"][0]["gross_realized_losses_through_event_usd"] == 5500
    assert result["event_reconciliations"][0]["first_threshold_crossing_close"]["fill_time"] == (
        "2025-03-06T17:02:00+00:00"
    )
    assert result["calendar_date_crossings_without_recorded_event"] == ["2025-03-07"]
