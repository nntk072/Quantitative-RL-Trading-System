"""Tests for the reusable recorded trade-lifecycle reconciliation."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest
from scripts.research.analysis.evaluation.summarize_policy_trade_lifecycle import (
    summarize_trade_lifecycle,
    write_report,
)


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _lifecycle_inputs(run_dir: Path) -> None:
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
                "equity": "100000.0",
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
                "equity": "100005.0",
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
        json.dumps({"initial_balance": 100_000.0, "final_equity": 100_005.0, "total_pnl": 5.0}),
        encoding="utf-8",
    )
    _write_csv(run_dir / "payouts.csv", ["amount"], [])


def _repeated_payout_inputs(run_dir: Path) -> None:
    _lifecycle_inputs(run_dir)
    fills_path = run_dir / "fills.csv"
    with fills_path.open(encoding="utf-8") as source:
        fills = list(csv.DictReader(source))
    fills[1]["net_pnl"] = "10.0"
    fills[1]["pnl"] = "10.0"
    fills[1]["equity"] = "110.0"
    _write_csv(fills_path, list(fills[0]), fills)
    positions_path = run_dir / "positions.csv"
    with positions_path.open(encoding="utf-8") as source:
        positions = list(csv.DictReader(source))
    positions[0]["net_pnl"] = "10.0"
    _write_csv(positions_path, list(positions[0]), positions)
    (run_dir / "metrics.json").write_text(
        json.dumps({"initial_balance": 100.0, "final_equity": 100.0, "total_pnl": 10.0}),
        encoding="utf-8",
    )
    _write_csv(
        run_dir / "payouts.csv",
        ["type", "time", "cycle", "payout", "balance_before_reset", "operating_balance"],
        [
            {
                "type": "payout_reset",
                "time": "2025-01-02T12:02:00Z",
                "cycle": "1",
                "payout": "10.0",
                "balance_before_reset": "110.0",
                "operating_balance": "100.0",
            }
        ],
    )
    _write_csv(
        run_dir / "cycle_events.csv",
        [
            "type",
            "time",
            "cycle",
            "outcome",
            "payout",
            "balance_before_reset",
            "operating_balance",
        ],
        [
            {
                "type": "payout_reset",
                "time": "2025-01-02T12:02:00Z",
                "cycle": "1",
                "outcome": "success",
                "payout": "10.0",
                "balance_before_reset": "110.0",
                "operating_balance": "100.0",
            }
        ],
    )
    (run_dir / "evaluation_diagnostics.json").write_text(
        json.dumps(
            {
                "trading_policy_mode": "repeated_payout",
                "cumulative_payouts": 10.0,
                "total_economic_value": 110.0,
                "cycle_successes": 1,
                "cycle_failures": 0,
                "cycle_count": 2,
            }
        ),
        encoding="utf-8",
    )
    _write_csv(
        run_dir / "total_economic_value.csv",
        ["total_economic_value"],
        [{"total_economic_value": "100.0"}, {"total_economic_value": "110.0"}],
    )


def test_summary_reconciles_decision_fill_and_position_records(tmp_path: Path) -> None:
    run_dir = tmp_path / "training"
    _lifecycle_inputs(run_dir)
    (tmp_path / "reanalysis_manifest.json").write_text(
        json.dumps({"seed": 50, "checkpoint_sha256": "checkpoint-hash"}),
        encoding="utf-8",
    )

    report = summarize_trade_lifecycle(run_dir)

    assert report["scope"]["seed"] == 50
    assert report["counts"]["positions_with_linked_fill_events"] == 1
    assert report["lifecycle_checks"]["one_open_and_at_least_one_close"] == 1
    assert report["lifecycle_checks"]["last_close_event_time_matches_position_exit_time"] == 1
    assert report["decision_order_checks"]["decision_le_submission_le_fill"] == 1
    assert report["decision_to_submission_seconds"] == {
        "count": 1,
        "minimum": 1.0,
        "median": 1.0,
        "maximum": 1.0,
    }
    assert report["pnl_reconciliation_checks"]["close_fill_net_pnl_matches_position"] == 1
    assert report["pnl_reconciliation_checks"]["position_net_pnl_matches_reported_total"] == 1
    assert report["aggregate_pnl_reconciliation"]["status"] == "matched"
    assert report["aggregate_pnl_reconciliation"]["difference"] == 0.0
    assert report["account_equity_reconciliation"]["status"] == "matched"
    assert report["cashflow_equity_reconciliation"]["status"] == "matched"
    assert report["cashflow_equity_reconciliation"]["completed_close_equity_checks"] == 1
    assert report["cashflow_equity_reconciliation"]["ending_reconstructed_balance"] == 100005.0
    assert report["integrity_status"] == "matched"
    assert report["integrity_failure_count"] == 0
    assert (
        report["pnl_reconciliation_checks"]["initial_plus_position_net_pnl_matches_final_equity"]
        == 1
    )
    assert report["holding_seconds"]["median"] == 60
    assert report["mfe_mae_columns"]["positions.csv"] == []


def test_summary_reconciles_empty_no_trade_ledger(tmp_path: Path) -> None:
    run_dir = tmp_path / "training"
    _lifecycle_inputs(run_dir)
    for filename in ("trades.csv", "fills.csv", "positions.csv"):
        path = run_dir / filename
        with path.open(encoding="utf-8") as source:
            fields = next(csv.reader(source))
        _write_csv(path, fields, [])
    (run_dir / "metrics.json").write_text(
        json.dumps({"initial_balance": 100_000.0, "final_equity": 100_000.0, "total_pnl": 0.0}),
        encoding="utf-8",
    )

    report = summarize_trade_lifecycle(run_dir)

    assert report["aggregate_pnl_reconciliation"]["status"] == "matched"
    assert report["account_equity_reconciliation"]["status"] == "matched"
    assert report["cashflow_equity_reconciliation"]["status"] == "matched"
    assert report["integrity_status"] == "matched"


def test_writer_records_source_and_report_hashes(tmp_path: Path) -> None:
    run_dir = tmp_path / "training"
    _lifecycle_inputs(run_dir)
    output_dir = tmp_path / "evidence"

    report = write_report(run_dir, output_dir)

    manifest = json.loads((output_dir / "evidence_manifest.json").read_text(encoding="utf-8"))
    markdown = (output_dir / "selected_policy_trade_lifecycle.md").read_text(encoding="utf-8")
    assert (output_dir / "selected_policy_trade_lifecycle.md").is_file()
    assert manifest["input_files"] == report["inputs"]
    analysis_script = Path(__file__).resolve().parents[3] / manifest["analysis_script"]["path"]
    assert analysis_script.is_file()
    assert (
        manifest["analysis_script"]["sha256"]
        == hashlib.sha256(analysis_script.read_bytes()).hexdigest()
    )
    assert "selected_policy_trade_lifecycle.json" in manifest["report_files"]
    assert "partition" in markdown
    assert "Holdout-inspection status is not available" in markdown


def test_summary_reports_aggregate_equity_mismatch(tmp_path: Path) -> None:
    run_dir = tmp_path / "training"
    _lifecycle_inputs(run_dir)
    (run_dir / "metrics.json").write_text(
        json.dumps({"initial_balance": 100_000.0, "final_equity": 100_006.0, "total_pnl": 5.0}),
        encoding="utf-8",
    )

    report = summarize_trade_lifecycle(run_dir)

    assert report["account_equity_reconciliation"]["status"] == "mismatch"
    assert report["account_equity_reconciliation"]["difference"] == -1.0
    assert report["integrity_status"] == "failed"
    assert report["integrity_failure_count"] == 1


def test_summary_reconciles_repeated_payout_cash_flows(tmp_path: Path) -> None:
    run_dir = tmp_path / "training"
    _repeated_payout_inputs(run_dir)

    report = summarize_trade_lifecycle(run_dir)

    assert report["payout_reconciliation"]["status"] == "matched"
    assert report["cashflow_equity_reconciliation"]["status"] == "matched"
    assert (
        report["cashflow_equity_reconciliation"]["checks"][
            "payout_balance_matches_cumulative_cashflows"
        ]
        == 1
    )
    assert report["payout_reconciliation"]["payout_sum"] == 10.0
    assert report["payout_reconciliation"]["checks"]["payout_amount_matches_balance_reset"] == 1
    assert (
        report["payout_reconciliation"]["checks"][
            "payout_is_positive_profit_above_operating_balance"
        ]
        == 1
    )
    assert report["payout_reconciliation"]["checks"]["payout_sum_matches_reported_cumulative"] == 1
    assert (
        report["payout_reconciliation"]["checks"]["economic_value_curve_matches_reported_total"]
        == 1
    )
    assert report["cycle_reconciliation"]["status"] == "matched"
    assert report["cycle_reconciliation"]["checks"]["cycle_successes_match_payout_rows"] == 1
    assert report["account_equity_reconciliation"]["status"] == "matched"
    assert report["account_equity_reconciliation"]["difference"] == 0.0
    assert report["integrity_status"] == "matched"


def test_summary_reconciles_partial_dynamic_drawdown_payout(tmp_path: Path) -> None:
    run_dir = tmp_path / "training"
    _repeated_payout_inputs(run_dir)
    event = {
        "type": "payout_reset",
        "payout_schema_version": "payout_reset.v2",
        "time": "2025-01-02T12:02:00Z",
        "cycle": "1",
        "max_drawdown_mode": "eod",
        "payout_fraction": "0.5",
        "profit_above_operating_balance": "10.0",
        "payout": "5.0",
        "retained_profit": "5.0",
        "balance_before_reset": "110.0",
        "operating_balance": "100.0",
        "balance_after_reset": "105.0",
    }
    _write_csv(run_dir / "payouts.csv", list(event), [event])
    cycle_event = {**event, "outcome": "success"}
    _write_csv(run_dir / "cycle_events.csv", list(cycle_event), [cycle_event])
    diagnostics_path = run_dir / "evaluation_diagnostics.json"
    diagnostics = json.loads(diagnostics_path.read_text(encoding="utf-8"))
    diagnostics["cumulative_payouts"] = 5.0
    diagnostics_path.write_text(json.dumps(diagnostics), encoding="utf-8")
    (run_dir / "metrics.json").write_text(
        json.dumps({"initial_balance": 100.0, "final_equity": 105.0, "total_pnl": 10.0}),
        encoding="utf-8",
    )

    report = summarize_trade_lifecycle(run_dir)

    assert report["payout_reconciliation"]["status"] == "matched"
    assert report["cashflow_equity_reconciliation"]["status"] == "matched"
    assert report["account_equity_reconciliation"]["status"] == "matched"
    assert report["integrity_status"] == "matched"


def test_summary_fails_closed_on_payout_reset_mismatch(tmp_path: Path) -> None:
    run_dir = tmp_path / "training"
    _repeated_payout_inputs(run_dir)
    payouts_path = run_dir / "payouts.csv"
    with payouts_path.open(encoding="utf-8") as source:
        payouts = list(csv.DictReader(source))
    payouts[0]["payout"] = "9.0"
    _write_csv(payouts_path, list(payouts[0]), payouts)

    report = summarize_trade_lifecycle(run_dir)

    assert report["payout_reconciliation"]["status"] == "mismatch"
    assert (
        report["payout_reconciliation"]["failures"]["payout_amount_matches_balance_reset_failed"]
        == 1
    )
    assert report["account_equity_reconciliation"]["status"] == "mismatch"
    assert report["integrity_status"] == "failed"


@pytest.mark.parametrize(
    ("payout", "balance_before_reset"),
    [("-1.0", "99.0"), ("0.0", "100.0"), ("1.0", "99.0")],
)
def test_summary_rejects_payout_without_positive_profit_above_operating_balance(
    tmp_path: Path, payout: str, balance_before_reset: str
) -> None:
    run_dir = tmp_path / "training"
    _repeated_payout_inputs(run_dir)
    payouts_path = run_dir / "payouts.csv"
    with payouts_path.open(encoding="utf-8") as source:
        payouts = list(csv.DictReader(source))
    payouts[0]["payout"] = payout
    payouts[0]["balance_before_reset"] = balance_before_reset
    _write_csv(payouts_path, list(payouts[0]), payouts)

    report = summarize_trade_lifecycle(run_dir)

    assert report["payout_reconciliation"]["status"] == "mismatch"
    assert (
        report["payout_reconciliation"]["failures"][
            "payout_is_positive_profit_above_operating_balance_failed"
        ]
        == 1
    )


def test_summary_fails_closed_when_cycle_failure_event_is_missing(tmp_path: Path) -> None:
    run_dir = tmp_path / "training"
    _repeated_payout_inputs(run_dir)
    diagnostics_path = run_dir / "evaluation_diagnostics.json"
    diagnostics = json.loads(diagnostics_path.read_text(encoding="utf-8"))
    diagnostics["cycle_failures"] = 1
    diagnostics_path.write_text(json.dumps(diagnostics), encoding="utf-8")

    report = summarize_trade_lifecycle(run_dir)

    assert report["cycle_reconciliation"]["status"] == "mismatch"
    assert (
        report["cycle_reconciliation"]["failures"]["cycle_events_match_reported_outcomes_failed"]
        == 1
    )
    assert report["integrity_status"] == "failed"


def test_summary_links_terminal_cycle_failure_to_account_breach(tmp_path: Path) -> None:
    run_dir = tmp_path / "training"
    _repeated_payout_inputs(run_dir)
    cycle_path = run_dir / "cycle_events.csv"
    with cycle_path.open(encoding="utf-8") as source:
        cycle_header = next(csv.reader(source))
        cycle_rows = list(csv.DictReader(source, fieldnames=cycle_header))
    cycle_header.extend(["reason", "equity"])
    cycle_rows.append(
        {
            "type": "cycle_failure",
            "time": "2025-01-02T12:03:00Z",
            "cycle": "2",
            "outcome": "failure",
            "payout": "",
            "balance_before_reset": "",
            "operating_balance": "",
            "reason": "max_drawdown",
            "equity": "99.9",
        }
    )
    _write_csv(cycle_path, cycle_header, cycle_rows)
    _write_csv(
        run_dir / "breach_events.csv",
        ["time", "session_id", "reason", "equity", "fill_time"],
        [
            {
                "time": "2025-01-02T12:03:00Z",
                "session_id": "20250102",
                "reason": "max_drawdown",
                "equity": "99.9",
                "fill_time": "2025-01-02T12:03:00Z",
            }
        ],
    )
    diagnostics_path = run_dir / "evaluation_diagnostics.json"
    diagnostics = json.loads(diagnostics_path.read_text(encoding="utf-8"))
    diagnostics["cycle_failures"] = 1
    diagnostics_path.write_text(json.dumps(diagnostics), encoding="utf-8")

    report = summarize_trade_lifecycle(run_dir)

    assert report["cycle_reconciliation"]["status"] == "matched"
    assert report["cycle_reconciliation"]["checks"]["cycle_failures_match_breach_events"] == 1
    assert report["integrity_status"] == "matched"

    breach_path = run_dir / "breach_events.csv"
    _write_csv(
        breach_path,
        ["time", "session_id", "reason", "equity", "fill_time"],
        [
            {
                "time": "2025-01-02T12:03:00Z",
                "session_id": "20250102",
                "reason": "max_drawdown",
                "equity": "99.8",
                "fill_time": "2025-01-02T12:03:00Z",
            }
        ],
    )
    mismatched = summarize_trade_lifecycle(run_dir)
    assert mismatched["cycle_reconciliation"]["status"] == "mismatch"
    assert (
        mismatched["cycle_reconciliation"]["failures"]["cycle_failures_match_breach_events_failed"]
        == 1
    )
    assert mismatched["integrity_status"] == "failed"


def test_summary_fails_closed_on_position_fill_count_mismatch(tmp_path: Path) -> None:
    run_dir = tmp_path / "training"
    _lifecycle_inputs(run_dir)
    positions_path = run_dir / "positions.csv"
    with positions_path.open(encoding="utf-8") as source:
        rows = list(csv.DictReader(source))
    rows[0]["fill_count"] = "3"
    _write_csv(
        positions_path,
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
        rows,
    )

    report = summarize_trade_lifecycle(run_dir)

    assert report["lifecycle_check_failures"] == {"fill_count_matches_event_rows": 1}
    assert report["integrity_status"] == "failed"
    assert report["integrity_failure_count"] == 1


def test_summary_fails_closed_on_close_fill_to_position_pnl_mismatch(tmp_path: Path) -> None:
    run_dir = tmp_path / "training"
    _lifecycle_inputs(run_dir)
    fills_path = run_dir / "fills.csv"
    with fills_path.open(encoding="utf-8") as source:
        rows = list(csv.DictReader(source))
    rows[1]["net_pnl"] = "4.0"
    _write_csv(
        fills_path,
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
        rows,
    )

    report = summarize_trade_lifecycle(run_dir)

    assert report["pnl_reconciliation_checks"]["close_fill_net_pnl_matches_position_failed"] == 1
    assert report["cashflow_equity_reconciliation"]["status"] == "mismatch"
    assert report["integrity_status"] == "failed"
    assert report["integrity_failure_count"] == 3


def test_summary_fails_closed_on_orphan_fill_position_id(tmp_path: Path) -> None:
    run_dir = tmp_path / "training"
    _lifecycle_inputs(run_dir)
    fills_path = run_dir / "fills.csv"
    with fills_path.open(encoding="utf-8") as source:
        rows = list(csv.DictReader(source))
    rows.append(
        {
            "type": "open",
            "position_id": "orphan",
            "time": "2025-01-02T12:02:02Z",
            "decision_time": "2025-01-02T12:02:00Z",
            "order_submission_time": "2025-01-02T12:02:01Z",
            "fill_time": "2025-01-02T12:02:02Z",
            "net_pnl": "",
        }
    )
    _write_csv(
        fills_path,
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
        rows,
    )

    report = summarize_trade_lifecycle(run_dir)

    assert report["counts"]["unlinked_fill_position_ids"] == 1
    assert report["integrity_status"] == "failed"
    assert report["integrity_failure_count"] == 1


def test_summary_fails_closed_on_decision_submission_fill_order(tmp_path: Path) -> None:
    run_dir = tmp_path / "training"
    _lifecycle_inputs(run_dir)
    fills_path = run_dir / "fills.csv"
    with fills_path.open(encoding="utf-8") as source:
        rows = list(csv.DictReader(source))
    rows[0]["decision_time"] = "2025-01-02T12:00:03Z"
    _write_csv(
        fills_path,
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
        rows,
    )

    report = summarize_trade_lifecycle(run_dir)

    assert report["decision_order_checks"]["decision_le_submission_le_fill_failed"] == 1
    assert report["integrity_status"] == "failed"
    assert report["integrity_failure_count"] == 1


def test_summary_marks_missing_fill_order_timing_incomplete(tmp_path: Path) -> None:
    run_dir = tmp_path / "training"
    _lifecycle_inputs(run_dir)
    fills_path = run_dir / "fills.csv"
    with fills_path.open(encoding="utf-8") as source:
        rows = list(csv.DictReader(source))
    rows[0]["decision_time"] = ""
    _write_csv(
        fills_path,
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
        rows,
    )

    report = summarize_trade_lifecycle(run_dir)

    assert report["decision_order_checks"]["decision_le_submission_le_fill_unavailable"] == 1
    assert report["integrity_status"] == "incomplete"
    assert report["integrity_failure_count"] == 0


def test_summary_accepts_scalar_backtest_payout_ledger_name(tmp_path: Path) -> None:
    run_dir = tmp_path / "training"
    _repeated_payout_inputs(run_dir)
    (run_dir / "payouts.csv").rename(run_dir / "payout_events.csv")

    report = summarize_trade_lifecycle(run_dir)

    assert report["payout_reconciliation"]["status"] == "matched"
    assert "payout_events.csv" in report["inputs"]
    assert "payouts.csv" not in report["inputs"]


def test_summary_rejects_ambiguous_payout_ledger_names(tmp_path: Path) -> None:
    run_dir = tmp_path / "training"
    _repeated_payout_inputs(run_dir)
    (run_dir / "payout_events.csv").write_text("same event data\n", encoding="utf-8")

    try:
        summarize_trade_lifecycle(run_dir)
    except ValueError as error:
        assert "both payout ledger names" in str(error)
    else:
        raise AssertionError("ambiguous payout inputs should fail closed")


def test_summary_accepts_empty_optional_cycle_ledger(tmp_path: Path) -> None:
    run_dir = tmp_path / "training"
    _lifecycle_inputs(run_dir)
    (run_dir / "cycle_events.csv").write_text("\n", encoding="utf-8")

    report = summarize_trade_lifecycle(run_dir)

    assert report["cycle_reconciliation"]["status"] == "not_applicable"
    assert report["integrity_status"] == "matched"
