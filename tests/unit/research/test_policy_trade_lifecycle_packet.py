"""Tests for the selected policy lifecycle packet aggregator."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from scripts.research.analysis.evaluation.build_policy_trade_lifecycle_packet import build_packet
from scripts.research.analysis.evaluation.summarize_policy_trade_lifecycle import write_report


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _source_run(run_dir: Path) -> None:
    run_dir.mkdir(parents=True)
    _write_csv(
        run_dir / "trades.csv",
        ["type", "entry_rejection_reason", "position_id"],
        [{"type": "open", "entry_rejection_reason": "", "position_id": "p1"}],
    )
    _write_csv(
        run_dir / "fills.csv",
        [
            "type",
            "position_id",
            "time",
            "decision_time",
            "order_submission_time",
            "fill_time",
            "pnl",
            "net_pnl",
            "entry_commission_allocated",
            "equity",
            "position_complete",
        ],
        [
            {
                "type": "open",
                "position_id": "p1",
                "time": "2025-01-02T12:00:02Z",
                "decision_time": "2025-01-02T12:00:00Z",
                "order_submission_time": "2025-01-02T12:00:01Z",
                "fill_time": "2025-01-02T12:00:02Z",
                "pnl": "",
                "net_pnl": "",
                "entry_commission_allocated": "",
                "equity": "100.0",
                "position_complete": "False",
            },
            {
                "type": "stop_close",
                "position_id": "p1",
                "time": "2025-01-02T12:01:02Z",
                "decision_time": "",
                "order_submission_time": "",
                "fill_time": "2025-01-02T12:01:02Z",
                "pnl": "5.0",
                "net_pnl": "5.0",
                "entry_commission_allocated": "0.0",
                "equity": "105.0",
                "position_complete": "True",
            },
        ],
    )
    _write_csv(
        run_dir / "positions.csv",
        [
            "position_id",
            "entry_time",
            "exit_time",
            "holding_seconds",
            "exit_reason",
            "net_pnl",
            "fill_count",
            "completed",
        ],
        [
            {
                "position_id": "p1",
                "entry_time": "2025-01-02T12:00:02Z",
                "exit_time": "2025-01-02T12:01:02Z",
                "holding_seconds": "60",
                "exit_reason": "structure_sl",
                "net_pnl": "5.0",
                "fill_count": "2",
                "completed": "True",
            }
        ],
    )
    (run_dir / "metrics.json").write_text(
        json.dumps({"initial_balance": 100.0, "final_equity": 105.0, "total_pnl": 5.0}),
        encoding="utf-8",
    )
    _write_csv(run_dir / "payouts.csv", ["amount"], [])


def test_packet_aggregator_verifies_partition_inputs_and_output_hashes(tmp_path: Path) -> None:
    packet_dir = tmp_path / "packet"
    partition_dir = packet_dir / "a4a_training"
    source_dir = tmp_path / "run"
    _source_run(source_dir)
    write_report(source_dir, partition_dir)

    report = build_packet(packet_dir, partitions=("a4a_training",))

    assert report["status"] == "matched"
    assert report["failure_count"] == 0
    assert report["totals"]["positions"] == 1
    assert report["partitions"]["a4a_training"]["completed_close_equity_checks"] == 1
    assert report["partitions"]["a4a_training"]["close_fill_charge_checks"] == 1

    (source_dir / "fills.csv").write_text("changed\n", encoding="utf-8")
    stale = build_packet(packet_dir, partitions=("a4a_training",))
    assert stale["status"] == "mismatch"
    assert any(
        "input_hash_mismatch:fills.csv" in failure["reason"] for failure in stale["failures"]
    )
