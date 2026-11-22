from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from scripts.research.analysis.evaluation.verify_matched_setup_baseline_accounting import (
    audit_bundle,
)


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _build_bundle(root: Path, *, open_candidate_eligible: bool = True) -> Path:
    bundle_id = "matched_setup_baselines_fixture"
    bundle = root / bundle_id
    bundle.mkdir()
    _write_json(bundle / "resolved_config.json", {"account": {"initial_balance": 100_000.0}})
    decision_fields = [
        "decision_id",
        "trade_setup_candidate_id",
        "eligible_trade_setup_ids",
        "trade_setup_eligible",
        "decision_time",
        "direction",
        "trade_setup_source_event_id",
        "trade_setup_event_identity_version",
        "trade_setup_source_event_identity_status",
    ]
    ledger_fields = [
        "type",
        "decision_id",
        "position_id",
        "fill_id",
        "trade_setup_candidate_id",
        "trade_setup_source_event_id",
        "trade_setup_event_identity_version",
        "trade_setup_source_event_identity_status",
        "direction",
        "time",
        "order_submission_time",
        "fill_time",
        "price",
        "sl_price",
        "tp_price",
        "net_pnl",
        "position_net_pnl",
    ]
    runs: list[dict[str, object]] = []
    common_decision_id = "episode:d1"
    decisions = {
        "always_no_trade": {
            "decision_id": common_decision_id,
            "trade_setup_candidate_id": 0,
            "eligible_trade_setup_ids": "[0]",
            "trade_setup_eligible": True,
            "decision_time": "2025-01-01T00:00:00+00:00",
            "direction": 0,
            "trade_setup_source_event_id": "",
            "trade_setup_event_identity_version": "v1",
            "trade_setup_source_event_identity_status": "not_applicable",
        },
        "one_trade": {
            "decision_id": common_decision_id,
            "trade_setup_candidate_id": 7,
            "eligible_trade_setup_ids": "[0, 7]" if open_candidate_eligible else "[0]",
            "trade_setup_eligible": True,
            "decision_time": "2025-01-01T00:00:00+00:00",
            "direction": 1,
            "trade_setup_source_event_id": "event-7",
            "trade_setup_event_identity_version": "v1",
            "trade_setup_source_event_identity_status": "identified",
        },
    }
    for arm, decision in decisions.items():
        arm_dir = bundle / arm
        arm_dir.mkdir()
        decision_path = arm_dir / "decisions.csv"
        _write_csv(decision_path, decision_fields, [decision])
        ledger_path = arm_dir / "trade_fill_event_ledger.csv"
        if arm == "always_no_trade":
            ledger_path.write_text(",,\n", encoding="utf-8")
            pnl = 0.0
            end = 100_000.0
            trades = 0
        else:
            open_row = {
                "type": "open",
                "decision_id": common_decision_id,
                "position_id": "position-1",
                "fill_id": "",
                "trade_setup_candidate_id": 7,
                "trade_setup_source_event_id": "event-7",
                "trade_setup_event_identity_version": "v1",
                "trade_setup_source_event_identity_status": "identified",
                "direction": 1,
                "time": "2025-01-01T00:00:00.100000+00:00",
                "order_submission_time": "2025-01-01T00:00:00.050000+00:00",
                "fill_time": "2025-01-01T00:00:00.100000+00:00",
                "price": 100.0,
                "sl_price": 99.0,
                "tp_price": 0.0,
                "net_pnl": "",
                "position_net_pnl": "",
            }
            close_row = {
                **open_row,
                "type": "close",
                "decision_id": "",
                "fill_id": "position-1:f1",
                "time": "2025-01-01T00:02:00+00:00",
                "net_pnl": 5.0,
                "position_net_pnl": 5.0,
            }
            _write_csv(ledger_path, ledger_fields, [open_row, close_row])
            pnl = 5.0
            end = 100_005.0
            trades = 1
        equity_path = arm_dir / "equity.csv"
        _write_csv(
            equity_path,
            ["time", "equity"],
            [{"time": "t0", "equity": 100_000.0}, {"time": "t1", "equity": end}],
        )
        metrics_path = arm_dir / "metrics.json"
        _write_json(
            metrics_path,
            {
                "total_pnl": pnl,
                "total_return_pct": pnl / 1_000.0,
                "max_drawdown": 0.0,
                "n_trades": trades,
                "breach_count": 0,
                "extras": {"incomplete_positions": 0},
            },
        )
        metadata_path = arm_dir / "policy_metadata.json"
        _write_json(metadata_path, {"input_hashes": {"bars": "abc"}})
        evaluation_path = arm_dir / "evaluation.json"
        _write_json(evaluation_path, {"n_steps": 1, "breach_events": []})
        artifact_paths = [
            (decision_path, "decision_trace"),
            (ledger_path, "trade_fill_event_ledger"),
            (equity_path, "equity_curve"),
            (metrics_path, "metrics"),
            (metadata_path, "policy_metadata"),
            (evaluation_path, "evaluation_metadata"),
        ]
        artifacts = [
            {
                "path": f"{bundle_id}/{arm}/{path.name}",
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "role": role,
            }
            for path, role in artifact_paths
        ]
        runs.append({"run_id": f"{bundle_id}/{arm}", "artifacts": artifacts})
    _write_json(bundle / "result_manifest.json", {"finding_id": bundle_id, "runs": runs})
    return bundle


def _refresh_manifest_hashes(bundle: Path) -> None:
    manifest_path = bundle / "result_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for run in manifest["runs"]:
        for artifact in run["artifacts"]:
            path = bundle.parent / artifact["path"]
            artifact["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    _write_json(manifest_path, manifest)


def _make_breached_prefix_bundle(bundle: Path) -> None:
    control_dir = bundle / "always_no_trade"
    control_rows = list(csv.DictReader((control_dir / "decisions.csv").open()))
    control_row = control_rows[0]
    for step in (2, 3):
        next_row = dict(control_row)
        next_row["decision_id"] = f"episode:d{step}"
        next_row["decision_time"] = f"2025-01-01T00:0{step - 1}:00+00:00"
        control_rows.append(next_row)
    _write_csv(control_dir / "decisions.csv", list(control_row), control_rows)
    _write_csv(
        control_dir / "equity.csv",
        ["time", "equity"],
        [{"time": f"t{step}", "equity": 100_000.0} for step in range(4)],
    )
    _write_json(
        control_dir / "evaluation.json",
        {
            "n_steps": 3,
            "breach_events": [],
            "completed_data_split": True,
            "episode_end_reason": "data_end_survived",
        },
    )

    trade_dir = bundle / "one_trade"
    trade_metrics = json.loads((trade_dir / "metrics.json").read_text(encoding="utf-8"))
    trade_metrics["breach_count"] = 1
    _write_json(trade_dir / "metrics.json", trade_metrics)
    _write_json(
        trade_dir / "evaluation.json",
        {
            "n_steps": 1,
            "breach_events": [{"reason": "daily_loss", "time": "2025-01-01T00:01:00+00:00"}],
            "completed_data_split": False,
            "episode_end_reason": "risk_breach",
        },
    )
    _refresh_manifest_hashes(bundle)


def test_audit_reconciles_matched_decisions_and_account_cashflows(tmp_path: Path) -> None:
    bundle = _build_bundle(tmp_path)

    report = audit_bundle(bundle)

    assert report["status"] == "passed"
    assert [arm["status"] for arm in report["arms"]] == ["passed", "passed"]
    assert report["arms"][1]["open_count"] == 1
    assert report["arms"][1]["opens_without_scalar_target"] == 1
    assert report["arms"][1]["realized_net_pnl"] == 5.0


def test_audit_fails_when_open_candidate_was_not_eligible(tmp_path: Path) -> None:
    bundle = _build_bundle(tmp_path, open_candidate_eligible=False)

    report = audit_bundle(bundle)

    assert report["status"] == "failed"
    trade_arm = report["arms"][1]
    assert "opened_candidate_not_in_decision_eligibility_set" in trade_arm["failures"]


def test_audit_accepts_exact_prefix_ending_on_verified_risk_breach(tmp_path: Path) -> None:
    bundle = _build_bundle(tmp_path)
    _make_breached_prefix_bundle(bundle)

    report = audit_bundle(bundle)

    assert report["status"] == "passed"
    assert [arm["status"] for arm in report["arms"]] == ["passed", "passed"]
    assert report["arms"][1]["episode_end_reason"] == "risk_breach"
    assert report["arms"][1]["decision_count"] == 1


def test_audit_rejects_decision_mismatch_inside_breach_prefix(tmp_path: Path) -> None:
    bundle = _build_bundle(tmp_path)
    _make_breached_prefix_bundle(bundle)
    trade_dir = bundle / "one_trade"
    decisions_path = trade_dir / "decisions.csv"
    trade_rows = list(csv.DictReader(decisions_path.open()))
    trade_rows[0]["decision_id"] = "episode:other"
    _write_csv(decisions_path, list(trade_rows[0]), trade_rows)
    ledger_path = trade_dir / "trade_fill_event_ledger.csv"
    ledger_rows = list(csv.DictReader(ledger_path.open()))
    ledger_rows[0]["decision_id"] = "episode:other"
    _write_csv(ledger_path, list(ledger_rows[0]), ledger_rows)
    _refresh_manifest_hashes(bundle)

    report = audit_bundle(bundle)

    assert report["status"] == "failed"
    assert "decision_sequence_differs_from_matched_arms" in report["arms"][1]["failures"]


def test_audit_rejects_decision_time_mismatch_inside_breach_prefix(tmp_path: Path) -> None:
    bundle = _build_bundle(tmp_path)
    _make_breached_prefix_bundle(bundle)
    trade_dir = bundle / "one_trade"
    decisions_path = trade_dir / "decisions.csv"
    trade_rows = list(csv.DictReader(decisions_path.open()))
    trade_rows[0]["decision_time"] = "2025-01-01T00:05:00+00:00"
    _write_csv(decisions_path, list(trade_rows[0]), trade_rows)
    _refresh_manifest_hashes(bundle)

    report = audit_bundle(bundle)

    assert report["status"] == "failed"
    assert "decision_sequence_differs_from_matched_arms" in report["arms"][1]["failures"]


def test_audit_rejects_short_arm_without_risk_breach_terminal_metadata(tmp_path: Path) -> None:
    bundle = _build_bundle(tmp_path)
    _make_breached_prefix_bundle(bundle)
    trade_dir = bundle / "one_trade"
    _write_json(
        trade_dir / "evaluation.json",
        {
            "n_steps": 1,
            "breach_events": [],
            "completed_data_split": False,
            "episode_end_reason": "truncated",
        },
    )
    metrics = json.loads((trade_dir / "metrics.json").read_text(encoding="utf-8"))
    metrics["breach_count"] = 0
    _write_json(trade_dir / "metrics.json", metrics)
    _refresh_manifest_hashes(bundle)

    report = audit_bundle(bundle)

    assert report["status"] == "failed"
    assert "short_decision_sequence_without_verified_risk_breach" in report["arms"][1]["failures"]


def test_audit_rejects_breach_terminal_with_mismatched_step_count(tmp_path: Path) -> None:
    bundle = _build_bundle(tmp_path)
    _make_breached_prefix_bundle(bundle)
    trade_dir = bundle / "one_trade"
    evaluation = json.loads((trade_dir / "evaluation.json").read_text(encoding="utf-8"))
    evaluation["n_steps"] = 2
    _write_json(trade_dir / "evaluation.json", evaluation)
    _refresh_manifest_hashes(bundle)

    report = audit_bundle(bundle)

    assert report["status"] == "failed"
    assert "decision_or_equity_rows_differ_from_evaluation_steps" in report["arms"][1]["failures"]


def test_audit_rejects_breach_terminal_with_mismatched_breach_count(tmp_path: Path) -> None:
    bundle = _build_bundle(tmp_path)
    _make_breached_prefix_bundle(bundle)
    trade_dir = bundle / "one_trade"
    metrics = json.loads((trade_dir / "metrics.json").read_text(encoding="utf-8"))
    metrics["breach_count"] = 0
    _write_json(trade_dir / "metrics.json", metrics)
    _refresh_manifest_hashes(bundle)

    report = audit_bundle(bundle)

    assert report["status"] == "failed"
    failures = report["arms"][1]["failures"]
    assert "breach_events_do_not_match_metrics_count" in failures
    assert "short_decision_sequence_without_verified_risk_breach" in failures


def test_audit_rejects_breach_terminal_without_timestamped_breach_event(tmp_path: Path) -> None:
    bundle = _build_bundle(tmp_path)
    _make_breached_prefix_bundle(bundle)
    trade_dir = bundle / "one_trade"
    evaluation = json.loads((trade_dir / "evaluation.json").read_text(encoding="utf-8"))
    evaluation["breach_events"] = [{"reason": "daily_loss"}]
    _write_json(trade_dir / "evaluation.json", evaluation)
    _refresh_manifest_hashes(bundle)

    report = audit_bundle(bundle)

    assert report["status"] == "failed"
    failures = report["arms"][1]["failures"]
    assert "breach_event_metadata_invalid" in failures
    assert "short_decision_sequence_without_verified_risk_breach" in failures
