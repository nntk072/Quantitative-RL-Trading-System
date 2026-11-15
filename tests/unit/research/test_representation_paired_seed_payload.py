from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import pytest
from omegaconf import OmegaConf
from scripts.research.analysis.evidence.analyze_representation_paired_seed_results import (
    analyze_payload,
)
from scripts.research.analysis.evidence.build_representation_paired_seed_payload import (
    SOURCE_SCHEMA,
    build_payload,
)
from scripts.research.analysis.evidence.build_representation_paired_seed_payload import (
    main as build_payload_main,
)

from artifacts.identity import file_sha256
from decisioning.actions import build_action_schema_from_config
from training.artifacts.manifests import build_effective_policy_input_schema
from training.configuration.research_protocol import EXPECTED_TIMEFRAMES

DEV_START = "2024-12-30T00:00:00+03:00"
DEV_END = "2025-12-31T23:59:00+03:00"
EXPOSED_START = "2026-01-01T00:00:00+03:00"
EXPOSED_END = "2026-10-16T23:59:00+03:00"


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def _digest(value: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _write_run(
    root: Path,
    *,
    arm: str,
    seed: int,
    exposed: bool = False,
    liquidation: bool = False,
    payouts: float = 0.0,
) -> None:
    calendar_start, calendar_end = (EXPOSED_START, EXPOSED_END) if exposed else (DEV_START, DEV_END)
    start = calendar_start[:10] + "T01:05:00+03:00"
    first_decision = calendar_start[:10] + "T02:05:00+03:00"
    end = calendar_end[:10] + "T23:49:00+03:00"
    equity_end = calendar_end[:10] + "T23:50:00+03:00"
    decision_middle = calendar_start[:10] + "T02:06:00+03:00"
    equity_middle = calendar_start[:10] + "T02:07:00+03:00"
    history = arm == "C"
    initial = 100_000.0
    breached = seed == 42 and arm == "C"
    final = 98_000.0 if breached else initial + (1_000.0 if arm == "C" else 0.0)
    root.mkdir(parents=True, exist_ok=True)
    env = {
        "trade_setup_actions": True,
        "trade_setup_candidate_timeframes": list(EXPECTED_TIMEFRAMES),
        "completed_htf_history_enabled": history,
        "allow_agent_sl_mode": True,
        "allow_agent_tp_mode": False,
        "allow_multi_tp": False,
        "allow_simplex": True,
        "agent_entry_execution": False,
        "agent_direction_control": False,
        "feature_validity_channels": False,
        "obs_window": 1,
    }
    config = {"agent": {"arch": "mtf_reasoning"}, "env": env}
    config_path = root / "config.yaml"
    OmegaConf.save(OmegaConf.create(config), config_path)
    partition = root / "training"
    partition.mkdir(exist_ok=True)

    equity_path = partition / "equity.csv"
    with equity_path.open("w", newline="", encoding="utf-8") as stream:
        equity_writer = csv.writer(stream)
        equity_writer.writerow(["", "equity"])
        equity_writer.writerows(
            [
                [first_decision.replace("T", " ", 1), initial],
                [
                    decision_middle.replace("T", " ", 1),
                    (initial + final) / 2,
                ],
                [
                    equity_middle.replace("T", " ", 1),
                    (initial + final) / 2,
                ],
                [equity_end.replace("T", " ", 1), final],
            ]
        )
    decision_rows = [
        {
            "decision_id": str(index),
            "decision_bar_time": stamp.replace("T", " ", 1),
            "eligible_trade_setup_ids": json.dumps([0, 1]),
            "eligible_candidate_count": "2",
            "schema_version": "environment_policy_decision.completed_bar.v1",
            "action": "0",
            "trade_setup_candidate_id": "0",
            "trade_setup_eligible": "True",
            "trade_setup_source_event_id": "",
            "trade_setup_source_event_identity_status": "not_applicable",
            "decision_bar_index": str(index),
            "session_id": "1",
            "decision_time": stamp.replace("T", " ", 1),
            "position_direction_at_decision": "0",
            "position_id_at_decision": "",
            "pending_order_id_at_decision": "",
            "trade_event_start_index": "0",
            "trade_event_end_index_exclusive": "0",
        }
        for index, stamp in enumerate((first_decision, decision_middle, end), start=1)
    ]
    for filename in ("policy_decisions.csv", "trade_setup_decisions.csv"):
        with (partition / filename).open("w", newline="", encoding="utf-8") as stream:
            decision_writer = csv.DictWriter(stream, fieldnames=list(decision_rows[0]))
            decision_writer.writeheader()
            decision_writer.writerows(decision_rows)
    trace_rows: list[dict[str, Any]] = [
        {
            "rollout_step": 1,
            "initial_balance": initial,
            "equity": (initial + final) / 2,
            "cumulative_payouts": 0.0,
            "breach_reason": "",
        },
        {
            "rollout_step": 2,
            "initial_balance": initial,
            "equity": (initial + final) / 2,
            "cumulative_payouts": 0.0,
            "breach_reason": "",
        },
        {
            "rollout_step": 3,
            "initial_balance": initial,
            "equity": final,
            "cumulative_payouts": 0.0,
            "breach_reason": "max_loss" if breached else "",
        },
    ]
    trace_rows[-1]["cumulative_payouts"] = payouts
    with (partition / "account_state_trace.csv").open("w", newline="", encoding="utf-8") as stream:
        trace_writer = csv.DictWriter(stream, fieldnames=list(trace_rows[0]))
        trace_writer.writeheader()
        trace_writer.writerows(trace_rows)
    _write_json(
        partition / "account_state_reconciliation.json",
        {"status": "matched", "failure_count": 0, "trace_rows": len(trace_rows)},
    )
    _write_json(
        partition / "metrics.json",
        {
            "initial_balance": initial,
            "final_equity": final,
            "total_return_pct": 100.0 * (final - initial) / initial,
            "n_trades": 0,
        },
    )
    _write_json(
        partition / "evaluation_diagnostics.json",
        {
            "n_steps": len(decision_rows),
            "policy_decisions_rows": len(decision_rows),
            "policy_decisions_complete": True,
            "policy_decision_reconciliation_status": "matched",
            "policy_decision_reconciliation_failures": 0,
        },
    )
    with (partition / "positions.csv").open("w", newline="", encoding="utf-8") as stream:
        positions_writer = csv.DictWriter(stream, fieldnames=["exit_reason"])
        positions_writer.writeheader()
        if liquidation:
            positions_writer.writerow({"exit_reason": "data_end"})
    with (partition / "trades.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["type", "decision_id"])

    columns = ["m1_close", "m1_sweep", "m5_momentum"]
    sequence_schema = {"version": "sequence-feature-v1", "columns": columns}
    effective_schema = build_effective_policy_input_schema(
        columns,
        trade_setup_actions=True,
        completed_htf_history_enabled=history,
        validity_channels=False,
        runtime_arch="mtf_reasoning",
    )
    action_schema = build_action_schema_from_config(env).to_dict()
    run_manifest = {
        "seed": seed,
        "config": {"sha256": file_sha256(config_path)},
        "datasets": {
            "train_bars": {
                "sha256": "a" * 64,
                "rows": 4,
                "start": start.replace("T", " ", 1),
                "end": end.replace("T", " ", 1),
            },
            "train_features": {
                "sha256": "b" * 64,
                "rows": 4,
                "start": start.replace("T", " ", 1),
                "end": end.replace("T", " ", 1),
            },
        },
        "split": {"name": "registered-fixture"},
        "completed_steps": 2_000_000,
        "action_schema": action_schema,
        "observation_schema": {"effective_policy_input_schema": effective_schema},
        "sequence_feature_schema": sequence_schema,
        "training_architecture": {"arch": "mtf_reasoning"},
        "source": {
            "available": True,
            "head": "c" * 40,
            "dirty_files": [{"path": "tracked.py", "sha256": "d" * 64}],
        },
        "execution_protocol": {"fill": "next_open"},
    }
    run_manifest_path = root / "run_manifest.json"
    _write_json(run_manifest_path, run_manifest)
    artifacts = []
    for path in sorted(partition.iterdir()):
        artifacts.append({"path": f"training/{path.name}", "sha256": file_sha256(path)})
    _write_json(
        root / "evaluation_manifest.json",
        {
            "schema_version": "evaluation-artifacts-v1",
            "config_sha256": file_sha256(config_path),
            "partitions": ["training"],
            "parent_manifests": {
                "run_manifest": {
                    "path": "run_manifest.json",
                    "sha256": file_sha256(run_manifest_path),
                }
            },
            "numerical_artifacts": artifacts,
        },
    )


def _source_spec(tmp_path: Path, *, exposed: bool = False) -> dict[str, Any]:
    start, end = (EXPOSED_START, EXPOSED_END) if exposed else (DEV_START, DEV_END)
    pairs = []
    for seed in range(42, 48):
        arms = {}
        for arm in ("B", "C"):
            run_dir = tmp_path / f"{arm}-{seed}"
            _write_run(run_dir, arm=arm, seed=seed, exposed=exposed)
            arms[arm] = {"run_dir": str(run_dir), "partition": "training"}
        pairs.append({"seed": seed, **arms})
    return {
        "schema_version": SOURCE_SCHEMA,
        "comparison_id": "representation-c-minus-b",
        "purpose": "report_only" if exposed else "selection",
        "evaluation_exposure": "exposed_report_only" if exposed else "development",
        "declared_interval": {"start": start, "end_inclusive": end},
        "expected_seeds": list(range(42, 48)),
        "pairs": pairs,
    }


def _rehash_manifest(root: Path, filename: str) -> None:
    manifest_path = root / "evaluation_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    relative = f"training/{filename}"
    for record in manifest["numerical_artifacts"]:
        if record["path"] == relative:
            record["sha256"] = file_sha256(root / relative)
            break
    _write_json(manifest_path, manifest)


def _rehash_run_manifest_link(root: Path) -> None:
    manifest_path = root / "evaluation_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["parent_manifests"]["run_manifest"]["sha256"] = file_sha256(root / "run_manifest.json")
    _write_json(manifest_path, manifest)


def test_builder_derives_source_backed_contract_and_outcomes(tmp_path: Path) -> None:
    payload = build_payload(_source_spec(tmp_path))

    assert payload["schema"] == "aalto.representation_paired_seed_metrics.v3"
    assert payload["contrast"] == "C_minus_B"
    assert len(payload["pairs"]) == 6
    first = payload["pairs"][0]
    assert first["B"]["history_availability"] == "masked"
    assert first["C"]["history_availability"] == "completed_htf"
    assert (
        first["B"]["provenance"]["candidate_opportunities_sha256"]
        == first["C"]["provenance"]["candidate_opportunities_sha256"]
    )
    assert (
        first["B"]["provenance"]["legal_masks_sha256"]
        == first["C"]["provenance"]["legal_masks_sha256"]
    )
    assert first["C"]["outcome"] == "completed_after_hard_breach"
    assert first["C"]["hard_risk_gate_passed"] is False
    assert first["B"]["observed_evaluation_start"] == "2024-12-30T02:05:00+03:00"
    assert first["B"]["observed_evaluation_end"] == "2025-12-31T23:50:00+03:00"
    assert first["B"]["provenance"]["evaluation_start"] == "2024-12-30T01:05:00+03:00"
    assert first["B"]["source_identity_sha256"] == first["source_identity_sha256"]


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("action", "2", "action is outside"),
        (
            "trade_setup_candidate_id",
            "2",
            "directional policy action selects an ineligible candidate",
        ),
    ],
)
def test_action_and_candidate_are_validated_against_mask_and_execution_ledger(
    tmp_path: Path, field: str, value: str, message: str
) -> None:
    spec = _source_spec(tmp_path)
    root = Path(spec["pairs"][0]["B"]["run_dir"])
    policy_path = root / "training/policy_decisions.csv"
    rows = list(csv.DictReader(policy_path.open(encoding="utf-8", newline="")))
    rows[0][field] = value
    if field == "trade_setup_candidate_id":
        rows[0]["action"] = "1"
        rows[0]["trade_setup_eligible"] = "False"
    with policy_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    _rehash_manifest(root, "policy_decisions.csv")

    with pytest.raises(ValueError, match=message):
        build_payload(spec)


def test_execution_event_must_link_to_a_persisted_policy_decision(tmp_path: Path) -> None:
    spec = _source_spec(tmp_path)
    root = Path(spec["pairs"][0]["B"]["run_dir"])
    trades_path = root / "training/trades.csv"
    with trades_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["type", "decision_id", "order_id"])
        writer.writeheader()
        writer.writerow(
            {"type": "order_submit", "decision_id": "unknown-decision", "order_id": "order-1"}
        )
    _rehash_manifest(root, "trades.csv")

    with pytest.raises(
        ValueError, match="do not reconcile with candidate masks and execution ledger"
    ):
        build_payload(spec)


def test_analyzer_rejects_old_representation_payload_schema(tmp_path: Path) -> None:
    payload = build_payload(_source_spec(tmp_path))
    payload["schema"] = "aalto.representation_paired_seed_metrics.v2"

    with pytest.raises(ValueError, match="input schema must be"):
        analyze_payload(payload)


def test_source_spec_cannot_inject_provenance_or_outcomes(tmp_path: Path) -> None:
    spec = _source_spec(tmp_path)
    spec["pairs"][0]["B"]["candidate_opportunities_sha256"] = "f" * 64
    with pytest.raises(ValueError, match="may not supply derived evidence"):
        build_payload(spec)


def test_source_identity_is_derived_and_must_match_b_c(tmp_path: Path) -> None:
    spec = _source_spec(tmp_path)
    root = Path(spec["pairs"][0]["C"]["run_dir"])
    run_path = root / "run_manifest.json"
    manifest = json.loads(run_path.read_text(encoding="utf-8"))
    manifest["source"]["head"] = "e" * 40
    _write_json(run_path, manifest)
    _rehash_run_manifest_link(root)

    with pytest.raises(ValueError, match="source-backed B/C mismatch: source_identity_sha256"):
        build_payload(spec)


def test_manifest_checksum_detects_tampered_equity_index(tmp_path: Path) -> None:
    spec = _source_spec(tmp_path)
    equity = Path(spec["pairs"][0]["C"]["run_dir"]) / "training/equity.csv"
    equity.write_text(
        equity.read_text(encoding="utf-8").replace("2025-06-01", "2025-06-02"), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="artifact hash mismatch"):
        build_payload(spec)


def test_equity_bounds_and_policy_cohort_must_match_declared_period(tmp_path: Path) -> None:
    spec = _source_spec(tmp_path)
    root = Path(spec["pairs"][0]["C"]["run_dir"])
    equity_path = root / "training/equity.csv"
    equity_path.write_text(
        equity_path.read_text(encoding="utf-8").replace(
            "2024-12-30 02:05:00+03:00", "2024-12-29 23:05:00+00:00"
        ),
        encoding="utf-8",
    )
    _rehash_manifest(root, "equity.csv")
    with pytest.raises(ValueError, match="canonical Etc/GMT-3"):
        build_payload(spec)


def test_b_c_evaluated_row_cohort_is_computed_from_persisted_indexes(tmp_path: Path) -> None:
    spec = _source_spec(tmp_path)
    root = Path(spec["pairs"][0]["C"]["run_dir"])
    for filename in ("policy_decisions.csv", "trade_setup_decisions.csv"):
        path = root / "training" / filename
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                "2024-12-30 02:06:00+03:00", "2024-12-30 02:08:00+03:00"
            ),
            encoding="utf-8",
        )
        _rehash_manifest(root, filename)

    with pytest.raises(ValueError, match="source-backed B/C mismatch: decision_cohort_sha256"):
        build_payload(spec)


def test_middle_row_omission_is_rejected_with_original_endpoints(tmp_path: Path) -> None:
    spec = _source_spec(tmp_path)
    root = Path(spec["pairs"][0]["B"]["run_dir"])
    targets = {
        "equity.csv": "2024-12-30 02:07:00+03:00",
        "policy_decisions.csv": "2024-12-30 02:06:00+03:00",
        "trade_setup_decisions.csv": "2024-12-30 02:06:00+03:00",
        "account_state_trace.csv": "2",
    }
    for filename, timestamp in targets.items():
        path = root / "training" / filename
        if filename == "account_state_trace.csv":
            with path.open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
                fieldnames = rows[0].keys()
            rows = [row for row in rows if row["rollout_step"] != timestamp]
            with path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(fieldnames))
                writer.writeheader()
                writer.writerows(rows)
            _rehash_manifest(root, filename)
            continue
        with path.open(newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
            fieldnames = rows[0].keys()
        rows = [row for row in rows if timestamp not in row.values()]
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(fieldnames))
            writer.writeheader()
            writer.writerows(rows)
        _rehash_manifest(root, filename)
    reconciliation_path = root / "training/account_state_reconciliation.json"
    reconciliation = json.loads(reconciliation_path.read_text(encoding="utf-8"))
    reconciliation["trace_rows"] = 2
    _write_json(reconciliation_path, reconciliation)
    _rehash_manifest(root, "account_state_reconciliation.json")

    with pytest.raises(
        ValueError, match="omits a bar inside one session|policy decisions are incomplete"
    ):
        build_payload(spec)


def test_leading_decision_omission_is_rejected_even_when_ledgers_are_trimmed(
    tmp_path: Path,
) -> None:
    spec = _source_spec(tmp_path)
    root = Path(spec["pairs"][0]["B"]["run_dir"])
    for filename in ("policy_decisions.csv", "trade_setup_decisions.csv"):
        path = root / "training" / filename
        with path.open(newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
            fieldnames = rows[0].keys()
        rows = rows[1:]
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(fieldnames))
            writer.writeheader()
            writer.writerows(rows)
        _rehash_manifest(root, filename)
    equity_path = root / "training/equity.csv"
    with equity_path.open(newline="", encoding="utf-8") as stream:
        equity_csv_rows = list(csv.reader(stream))
    with equity_path.open("w", newline="", encoding="utf-8") as stream:
        csv.writer(stream).writerows([equity_csv_rows[0], *equity_csv_rows[2:]])
    _rehash_manifest(root, "equity.csv")
    trace_path = root / "training/account_state_trace.csv"
    with trace_path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    with trace_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows[1:])
    _rehash_manifest(root, "account_state_trace.csv")
    reconciliation_path = root / "training/account_state_reconciliation.json"
    reconciliation = json.loads(reconciliation_path.read_text(encoding="utf-8"))
    reconciliation["trace_rows"] = 2
    _write_json(reconciliation_path, reconciliation)
    _rehash_manifest(root, "account_state_reconciliation.json")

    with pytest.raises(ValueError, match="policy decision diagnostics"):
        build_payload(spec)


def test_session_boundary_decision_omission_is_rejected_from_source_count(
    tmp_path: Path,
) -> None:
    spec = _source_spec(tmp_path)
    root = Path(spec["pairs"][0]["B"]["run_dir"])
    policy_path = root / "training/policy_decisions.csv"
    with policy_path.open(newline="", encoding="utf-8") as stream:
        policy_rows = list(csv.DictReader(stream))
    policy_rows[1]["session_id"] = "2"
    policy_rows[2]["session_id"] = "2"
    for filename in ("policy_decisions.csv", "trade_setup_decisions.csv"):
        path = root / "training" / filename
        with path.open(newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
            fieldnames = rows[0].keys()
        rows = [policy_rows[0], policy_rows[2]]
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(fieldnames))
            writer.writeheader()
            writer.writerows(rows)
        _rehash_manifest(root, filename)
    equity_path = root / "training/equity.csv"
    with equity_path.open(newline="", encoding="utf-8") as stream:
        equity_csv_rows = list(csv.reader(stream))
    with equity_path.open("w", newline="", encoding="utf-8") as stream:
        csv.writer(stream).writerows([*equity_csv_rows[:3], equity_csv_rows[-1]])
    _rehash_manifest(root, "equity.csv")
    trace_path = root / "training/account_state_trace.csv"
    with trace_path.open(newline="", encoding="utf-8") as stream:
        trace_rows = list(csv.DictReader(stream))
    with trace_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(trace_rows[0]))
        writer.writeheader()
        writer.writerows([trace_rows[0], trace_rows[2]])
    _rehash_manifest(root, "account_state_trace.csv")
    reconciliation_path = root / "training/account_state_reconciliation.json"
    reconciliation = json.loads(reconciliation_path.read_text(encoding="utf-8"))
    reconciliation["trace_rows"] = 2
    _write_json(reconciliation_path, reconciliation)
    _rehash_manifest(root, "account_state_reconciliation.json")

    with pytest.raises(ValueError, match="policy decision diagnostics"):
        build_payload(spec)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("policy_decisions_rows", 2),
        ("policy_decisions_complete", False),
        ("policy_decision_reconciliation_status", "failed"),
        ("policy_decision_reconciliation_failures", 1),
    ],
)
def test_diagnostics_decision_evidence_must_match_checksummed_ledger(
    tmp_path: Path, field: str, value: Any
) -> None:
    spec = _source_spec(tmp_path)
    root = Path(spec["pairs"][0]["B"]["run_dir"])
    diagnostics_path = root / "training/evaluation_diagnostics.json"
    diagnostics = json.loads(diagnostics_path.read_text(encoding="utf-8"))
    diagnostics[field] = value
    _write_json(diagnostics_path, diagnostics)
    _rehash_manifest(root, "evaluation_diagnostics.json")

    with pytest.raises(ValueError, match="policy decision diagnostics"):
        build_payload(spec)


def test_manifest_and_persisted_metrics_must_reconcile(tmp_path: Path) -> None:
    spec = _source_spec(tmp_path)
    root = Path(spec["pairs"][0]["B"]["run_dir"])
    metrics_path = root / "training/metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    metrics["final_equity"] += 100
    _write_json(metrics_path, metrics)
    _rehash_manifest(root, "metrics.json")

    with pytest.raises(ValueError, match="metrics, equity, and account trace endpoints"):
        build_payload(spec)


def test_liquidation_outcome_is_derived_from_positions_and_preserves_risk_boolean(
    tmp_path: Path,
) -> None:
    spec = _source_spec(tmp_path)
    root = Path(spec["pairs"][1]["C"]["run_dir"])
    _write_run(root, arm="C", seed=43, liquidation=True)
    payload = build_payload(spec)

    assert payload["pairs"][1]["C"]["outcome"] == "completed_after_liquidation"
    assert payload["pairs"][1]["C"]["hard_risk_gate_passed"] is True


def test_net_return_reconciles_retained_equity_plus_account_payouts(tmp_path: Path) -> None:
    spec = _source_spec(tmp_path)
    root = Path(spec["pairs"][2]["C"]["run_dir"])
    _write_run(root, arm="C", seed=44, payouts=2_500.0)
    payload = build_payload(spec)

    assert payload["pairs"][2]["C"]["net_return_initial_equity_pct"] == pytest.approx(3.5)


def test_policy_candidate_mask_is_read_from_checksummed_ledgers(tmp_path: Path) -> None:
    spec = _source_spec(tmp_path)
    root = Path(spec["pairs"][0]["C"]["run_dir"])
    for name in ("policy_decisions.csv", "trade_setup_decisions.csv"):
        path = root / "training" / name
        path.write_text(
            path.read_text(encoding="utf-8").replace("[0, 1]", "[0, 2]"), encoding="utf-8"
        )
        _rehash_manifest(root, name)

    with pytest.raises(
        ValueError,
        match="source-backed B/C mismatch: candidate_opportunities_sha256|source-backed B/C mismatch: legal_masks_sha256",
    ):
        build_payload(spec)


def test_analyzer_rederives_and_rejects_edited_payload(tmp_path: Path) -> None:
    payload = build_payload(_source_spec(tmp_path))
    report = analyze_payload(payload)
    assert report["inference_status"] == "development_selection_all_six_pairs"
    payload["pairs"][0]["B"]["provenance"]["evaluation_cohort_sha256"] = "a" * 64
    with pytest.raises(ValueError, match="differs from its source-backed artifacts"):
        analyze_payload(payload)


def test_incomplete_nobreach_run_is_visible_and_blocks_inference(tmp_path: Path) -> None:
    spec = _source_spec(tmp_path)
    root = Path(spec["pairs"][0]["B"]["run_dir"])
    for filename in ("policy_decisions.csv", "trade_setup_decisions.csv"):
        path = root / "training" / filename
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                "2025-12-31 23:49:00+03:00", "2025-12-31 20:00:00+03:00"
            ),
            encoding="utf-8",
        )
        _rehash_manifest(root, filename)
    equity_path = root / "training/equity.csv"
    equity_path.write_text(
        equity_path.read_text(encoding="utf-8").replace(
            "2025-12-31 23:50:00+03:00", "2025-12-31 20:01:00+03:00"
        ),
        encoding="utf-8",
    )
    _rehash_manifest(root, "equity.csv")

    payload = build_payload(spec)
    report = analyze_payload(payload)

    assert payload["pairs"][0]["inference_eligible"] is False
    assert payload["pairs"][0]["B"]["invalid_reason"] == "incomplete_evaluation"
    assert report["excluded_scientific_invalid_pairs"] == [
        {"seed": 42, "reasons": {"B": "incomplete_evaluation"}}
    ]
    assert report["statistics"] is None


def test_exposed_period_is_report_only_and_validated_from_rows(tmp_path: Path) -> None:
    payload = build_payload(_source_spec(tmp_path, exposed=True))
    report = analyze_payload(payload)
    assert report["statistics"] is None
    assert report["inference_status"] == "descriptive_only_inference_not_performed"


def test_builder_cli_refuses_to_overwrite_existing_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "existing-payload.json"
    output.write_text("preserve this payload\n", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_representation_paired_seed_payload",
            "--source-spec",
            str(tmp_path / "missing.json"),
            "--output",
            str(output),
        ],
    )
    with pytest.raises(FileExistsError, match="refusing to replace representation payload"):
        build_payload_main()
    assert output.read_text(encoding="utf-8") == "preserve this payload\n"


def test_q0_v2_builder_contract_remains_available(tmp_path: Path) -> None:
    from scripts.research.analysis.evidence.build_primary_paired_seed_payload import (
        build_payload as build_q0_payload,
    )

    source = tmp_path / "q0-source.json"
    source.write_text("{}\n", encoding="utf-8")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    pairs = []
    for seed in range(42, 48):
        common = {
            "dataset_sha256": "a" * 64,
            "split_id": "development",
            "features_sha256": "b" * 64,
            "reward_sha256": "c" * 64,
            "costs_sha256": "d" * 64,
            "execution_sha256": "e" * 64,
            "timesteps": 2_000_000,
            "seed": seed,
            "initial_capital": 100_000.0,
            "model_settings_sha256": "f" * 64,
            "environment_sha256": "1" * 64,
            "evaluation_start": "2024-12-30T00:00:00Z",
            "evaluation_end": "2025-12-31T23:59:00Z",
        }
        sources = [{"path": str(source), "sha256": digest}]
        arms = []
        for name, policy_id, policy_hash, ending, trades in (
            ("control", "always_no_trade_v1", "2" * 64, 100_000.0, 0),
            ("treatment", "qualified_policy_v1", "3" * 64, 101_000.0, 5),
        ):
            arms.append(
                {
                    "run_id": f"{name}-{seed}",
                    "policy_id": policy_id,
                    "evaluation_complete": True,
                    "hard_risk_gate_passed": True,
                    "initial_operating_equity": 100_000.0,
                    "ending_retained_equity": ending,
                    "cumulative_payouts": 0.0,
                    "trade_count": trades,
                    "net_return_initial_equity_pct": 100.0 * (ending - 100_000.0) / 100_000.0,
                    "provenance": {**common, "policy_sha256": policy_hash},
                    "source_artifacts": sources,
                }
            )
        pairs.append({"seed": seed, "control": arms[0], "treatment": arms[1]})
    q0 = build_q0_payload(
        {
            "schema_version": "qrl.primary_pair_sources.v1",
            "comparison_id": "q0-compatibility",
            "evaluation_exposure": "development",
            "expected_seeds": list(range(42, 48)),
            "pairs": pairs,
        }
    )
    assert q0["schema"] == "aalto.paired_seed_metrics.v2"
    assert q0["primary_selection"]["contrast"] == "treatment_vs_always_no_trade"
