"""Artifact contracts for matched setup baseline bundles."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from evaluation.metrics import compute_metrics
from evaluation.reporting import matched_setup_baseline_bundle as bundle


def test_bundle_writes_hashed_csv_and_json_artifacts_then_refuses_overwrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact_root = tmp_path / "artifacts"
    output_root = artifact_root / "matched"
    source_root = tmp_path / "source"
    (source_root / "evaluation" / "metrics").mkdir(parents=True)
    config_path = source_root / "study.yaml"
    config_path.write_text("account: {initial_balance: 100.0}\n", encoding="utf-8")
    protocol_path = source_root / "protocol.md"
    protocol_path.write_text("frozen protocol\n", encoding="utf-8")
    (source_root / "evaluation" / "metrics" / "performance.py").write_text(
        "metric source fixture\n", encoding="utf-8"
    )
    resolved_config = {
        "account": {"initial_balance": 100.0},
        "evaluation": {"periods_per_year": 10},
    }
    index = pd.date_range("2025-01-02 15:00", periods=3, freq="min", tz="UTC")
    bars = pd.DataFrame({"close": [100.0, 101.0, 102.0]}, index=index)
    features = pd.DataFrame({"atr": [1.0, 1.1, 1.2]}, index=index)
    confidence_intervals = {
        "schema": "within_trajectory_bootstrap_ci_v1",
        "metrics": {},
    }
    metadata = {
        "policy_id": "always_no_trade_v1",
        "policy_source": "deterministic_rule",
        "period_role": "synthetic",
        "resolved_config_sha256": bundle._canonical_sha256(resolved_config),
        "action_schema": {"version": "test-action-v1"},
        "input_hashes": {
            "bars": bundle._frame_record(bars)["sha256"],
            "features": bundle._frame_record(features)["sha256"],
            "tickbook": None,
        },
        "execution_seed": 42,
    }
    outputs: dict[str, dict[str, Any]] = {
        "always_no_trade": {
            "policy_metadata": metadata,
            "resolved_config": resolved_config,
            "decisions": pd.DataFrame({"action": [0, 0, 0]}, index=index),
            "trade_fill_event_ledger": pd.DataFrame(columns=["type", "time"]),
            "equity": pd.Series([100.0, 100.5, 101.0], index=index),
            "metrics": compute_metrics(
                [100.0, 100.5, 101.0],
                initial_balance=100.0,
                periods_per_year=10,
                trade_pnls=[0.0],
            ),
            "confidence_intervals": confidence_intervals,
            "evaluation": {
                "breach_events": [],
                "snapshot_time": pd.Timestamp("2025-01-02T15:01:00Z"),
                "artifact_path": tmp_path / "derived.csv",
                "vector": np.asarray([1, 2]),
                "nullable": pd.NA,
            },
        }
    }
    monkeypatch.setattr(
        bundle,
        "build_evaluation_provenance",
        lambda _root: {"source": {"available": False}, "runtime": {}},
    )

    created = bundle.write_matched_setup_baseline_bundle(
        outputs,
        resolved_config,
        bars,
        features,
        None,
        output_root=output_root,
        artifact_root=artifact_root,
        source_repository=source_root,
        config_path=config_path,
        protocol_path="protocol.md",
        regeneration_command="python -m evaluation.baselines",
        symbols=("ES",),
        timeframes=("M1",),
    )

    manifest = json.loads((created / "result_manifest.json").read_text(encoding="utf-8"))
    assert manifest["manifest_status"] == "draft"
    assert manifest["runs"][0]["status"] == "completed"
    assert (created / "always_no_trade" / "decisions.csv").is_file()
    serialized_metrics = json.loads(
        (created / "always_no_trade" / "metrics.json").read_text(encoding="utf-8")
    )
    serialized_evaluation = json.loads(
        (created / "always_no_trade" / "evaluation.json").read_text(encoding="utf-8")
    )
    assert serialized_metrics["profit_factor"] is None
    assert serialized_evaluation == {
        "breach_events": [],
        "snapshot_time": "2025-01-02T15:01:00+00:00",
        "artifact_path": str(tmp_path / "derived.csv"),
        "vector": [1, 2],
        "nullable": None,
    }
    for run in manifest["runs"]:
        for artifact in run["artifacts"]:
            artifact_path = artifact_root / artifact["path"]
            assert artifact_path.is_file()
            assert bundle.__dict__["file_sha256"](artifact_path) == artifact["sha256"]

    with pytest.raises(FileExistsError, match="immutable baseline bundle"):
        bundle.write_matched_setup_baseline_bundle(
            outputs,
            resolved_config,
            bars,
            features,
            None,
            output_root=output_root,
            artifact_root=artifact_root,
            source_repository=source_root,
            config_path=config_path,
            protocol_path="protocol.md",
            regeneration_command="python -m evaluation.baselines",
            symbols=("ES",),
            timeframes=("M1",),
        )


def test_bundle_rejects_misaligned_input_frames_before_creating_output(tmp_path: Path) -> None:
    index = pd.date_range("2025-01-02 15:00", periods=2, freq="min", tz="UTC")
    bars = pd.DataFrame({"close": [100.0, 101.0]}, index=index)
    features = pd.DataFrame({"atr": [1.0]}, index=index[:1])
    artifact_root = tmp_path / "artifacts"

    with pytest.raises(ValueError, match="identical rows and timestamps"):
        bundle.write_matched_setup_baseline_bundle(
            {"always_no_trade": {}},
            {},
            bars,
            features,
            None,
            output_root=artifact_root / "matched",
            artifact_root=artifact_root,
            source_repository=tmp_path / "source",
            config_path=tmp_path / "study.yaml",
            protocol_path="protocol.md",
            regeneration_command="python -m evaluation.baselines",
        )

    assert not artifact_root.exists()


def test_bundle_records_paired_baseline_interval_and_random_seed_lineage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact_root = tmp_path / "artifacts"
    output_root = artifact_root / "matched"
    source_root = tmp_path / "source"
    source_root.mkdir()
    performance_source = source_root / "evaluation" / "metrics" / "performance.py"
    performance_source.parent.mkdir(parents=True)
    performance_source.write_text("# synthetic metrics source identity\n", encoding="utf-8")
    config_path = source_root / "study.yaml"
    config_path.write_text("account: {initial_balance: 100.0}\n", encoding="utf-8")
    protocol_path = source_root / "protocol.md"
    protocol_path.write_text("synthetic protocol fixture\n", encoding="utf-8")
    resolved_config = {
        "account": {"initial_balance": 100.0},
        "evaluation": {"periods_per_year": 10},
    }
    index = pd.date_range("2025-01-02 15:00", periods=3, freq="min", tz="UTC")
    bars = pd.DataFrame({"close": [100.0, 101.0, 102.0]}, index=index)
    features = pd.DataFrame({"atr": [1.0, 1.1, 1.2]}, index=index)
    input_hashes = {
        "bars": bundle._frame_record(bars)["sha256"],
        "features": bundle._frame_record(features)["sha256"],
        "tickbook": None,
    }
    interval_protocol = {"n_boot": 12, "level": 0.9, "seed": 7, "block_length_bars": 1}
    confidence_intervals = {
        "schema": "within_trajectory_bootstrap_ci_v1",
        "metrics": {"total_return_pct": {"lower": -1.0, "upper": 1.0}},
    }
    evaluation = {
        "n_steps": 2,
        "breach_events": [],
    }

    def policy_metadata(policy_id: str, *, random_seed: int | None = None) -> dict[str, Any]:
        metadata = {
            "policy_id": policy_id,
            "policy_source": "deterministic_rule",
            "period_role": "synthetic",
            "resolved_config_sha256": bundle._canonical_sha256(resolved_config),
            "action_schema": {"version": "test-action-v1"},
            "input_hashes": input_hashes,
            "execution_seed": 19,
            "evaluation_start": str(index[0]),
            "evaluation_end": str(index[-1]),
            "confidence_interval_protocol": interval_protocol,
        }
        if random_seed is not None:
            metadata["random_policy_seed"] = random_seed
            metadata["policy_source"] = "randomized_control"
        return metadata

    outputs: dict[str, dict[str, Any]] = {}
    for name, values, seed in (
        ("always_no_trade", [100.0, 100.5, 101.0], None),
        ("random_eligible_setup", [100.0, 100.75, 101.5], 23),
    ):
        metadata = policy_metadata(name, random_seed=seed)
        outputs[name] = {
            "policy_metadata": metadata,
            "resolved_config": resolved_config,
            "decisions": pd.DataFrame({"action": [0, 0, 0]}, index=index),
            "trade_fill_event_ledger": pd.DataFrame(columns=["type", "time"]),
            "equity": pd.Series(values, index=index),
            "metrics": compute_metrics(values, initial_balance=100.0, periods_per_year=10),
            "confidence_intervals": confidence_intervals,
            "evaluation": evaluation,
        }

    paired_calls: list[dict[str, Any]] = []

    def paired_differences(*args: Any, **kwargs: Any) -> dict[str, Any]:
        paired_calls.append({"args": args, "kwargs": kwargs})
        return {"total_return_pct": {"estimate": 0.5, "lower": 0.25, "upper": 0.75}}

    monkeypatch.setattr(bundle, "paired_equity_metric_differences", paired_differences)
    monkeypatch.setattr(
        bundle,
        "build_evaluation_provenance",
        lambda _root: {"source": {"available": False}, "runtime": {}},
    )

    created = bundle.write_matched_setup_baseline_bundle(
        outputs,
        resolved_config,
        bars,
        features,
        None,
        output_root=output_root,
        artifact_root=artifact_root,
        source_repository=source_root,
        config_path=config_path,
        protocol_path="protocol.md",
        regeneration_command="python -m evaluation.baselines",
        symbols=("ES",),
        timeframes=("M1",),
        source_files={"metrics_source": performance_source},
    )

    input_identity = json.loads((created / "input_identity.json").read_text(encoding="utf-8"))
    assert input_identity["source_files"]["metrics_source"] == {
        "path": "evaluation/metrics/performance.py",
        "sha256": bundle.__dict__["file_sha256"](performance_source),
    }
    manifest = json.loads((created / "result_manifest.json").read_text(encoding="utf-8"))
    comparison = manifest["comparisons"][0]
    interval = comparison["paired_time_series_intervals"]
    assert comparison["comparison_id"] == "always_flat_vs_random_eligible_setup"
    assert interval["schema"] == "paired_matched_bar_metric_ci_v2"
    assert interval["status"] == "estimated"
    assert interval["paired_return_observations"] == 2
    assert interval["seed"] == 7
    assert interval["metrics"] == {
        "total_return_pct": {"estimate": 0.5, "lower": 0.25, "upper": 0.75}
    }
    assert len(paired_calls) == 1
    assert paired_calls[0]["kwargs"]["rng_seed"] == 7
    assert paired_calls[0]["kwargs"]["block_len"] == 1

    random_run = next(
        run for run in manifest["runs"] if run["variant_id"] == "random_eligible_setup"
    )
    assert random_run["role"] == "randomized_control"
    assert random_run["seed"] == 23
    assert random_run["identity"]["stochastic_eval_seed"] == 23
    assert random_run["identity"]["execution_seed"] == 19
    assert manifest["manifest_status"] == "draft"
    assert manifest["finding_status"] == "draft_synthetic_contract_validation"
    assert manifest["claims"] == []
    assert manifest["frozen_at_utc"] is None
    assert all(run["status"] == "completed" for run in manifest["runs"])

    outputs["random_eligible_setup"]["policy_metadata"]["confidence_interval_protocol"] = {
        **interval_protocol,
        "seed": 8,
    }
    rejected_root = artifact_root / "rejected"
    with pytest.raises(ValueError, match="share their bootstrap protocol"):
        bundle.write_matched_setup_baseline_bundle(
            outputs,
            resolved_config,
            bars,
            features,
            None,
            output_root=rejected_root,
            artifact_root=artifact_root,
            source_repository=source_root,
            config_path=config_path,
            protocol_path="protocol.md",
            regeneration_command="python -m evaluation.baselines",
            symbols=("ES",),
            timeframes=("M1",),
        )
    assert not rejected_root.exists()


def _minimal_bundle_case(tmp_path: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Build one synthetic policy arm and the writer's shared inputs."""
    source_root = tmp_path / "source"
    source_root.mkdir()
    config_path = source_root / "study.yaml"
    config_path.write_text("account: {initial_balance: 100.0}\n", encoding="utf-8")
    (source_root / "protocol.md").write_text("synthetic protocol\n", encoding="utf-8")
    metrics_source = source_root / "evaluation" / "metrics" / "performance.py"
    metrics_source.parent.mkdir(parents=True)
    metrics_source.write_text("# synthetic metric source\n", encoding="utf-8")
    resolved_config = {"account": {"initial_balance": 100.0}}
    index = pd.date_range("2025-03-03T15:00:00Z", periods=3, freq="min")
    bars = pd.DataFrame({"close": [100.0, 101.0, 102.0]}, index=index)
    features = pd.DataFrame({"atr": [1.0, 1.1, 1.2]}, index=index)
    metadata = {
        "policy_id": "candidate_rule_v1",
        "policy_source": "deterministic_rule",
        "period_role": "synthetic",
        "resolved_config_sha256": bundle._canonical_sha256(resolved_config),
        "action_schema": {"version": "test-action-v1"},
        "input_hashes": {
            "bars": bundle._frame_record(bars)["sha256"],
            "features": bundle._frame_record(features)["sha256"],
            "tickbook": None,
        },
        "execution_seed": 11,
    }
    outputs: dict[str, Any] = {
        "candidate_rule": {
            "policy_metadata": metadata,
            "resolved_config": resolved_config,
            "decisions": pd.DataFrame({"action": [0, 0, 0]}, index=index),
            "trade_fill_event_ledger": pd.DataFrame(columns=["type", "time"]),
            "equity": pd.Series([100.0, 100.5, 101.0], index=index),
            "metrics": compute_metrics([100.0, 100.5, 101.0], initial_balance=100.0),
            "confidence_intervals": {"schema": "within_trajectory_bootstrap_ci_v1", "metrics": {}},
            "evaluation": {},
        }
    }
    inputs = {
        "output_root": tmp_path / "artifacts" / "matched",
        "artifact_root": tmp_path / "artifacts",
        "source_repository": source_root,
        "config_path": config_path,
        "protocol_path": "protocol.md",
        "regeneration_command": "python -m evaluation.baselines",
    }
    return outputs, resolved_config, {"bars": bars, "features": features, **inputs}


def _write_minimal_bundle(
    outputs: dict[str, Any], resolved_config: dict[str, Any], inputs: dict[str, Any]
) -> Path:
    return bundle.write_matched_setup_baseline_bundle(
        outputs,
        resolved_config,
        inputs["bars"],
        inputs["features"],
        None,
        output_root=inputs["output_root"],
        artifact_root=inputs["artifact_root"],
        source_repository=inputs["source_repository"],
        config_path=inputs["config_path"],
        protocol_path=inputs["protocol_path"],
        regeneration_command=inputs["regeneration_command"],
    )


def test_bundle_rejects_missing_confidence_interval_artifact_before_output(
    tmp_path: Path,
) -> None:
    outputs, resolved_config, inputs = _minimal_bundle_case(tmp_path)
    outputs["candidate_rule"].pop("confidence_intervals")

    with pytest.raises(ValueError, match="versioned within-trajectory confidence intervals"):
        _write_minimal_bundle(outputs, resolved_config, inputs)

    assert not inputs["output_root"].exists()


def test_bundle_rejects_malformed_decision_artifact_before_output(tmp_path: Path) -> None:
    outputs, resolved_config, inputs = _minimal_bundle_case(tmp_path)
    outputs["candidate_rule"]["decisions"] = [{"action": 0}]

    with pytest.raises(TypeError, match="decisions and event ledger must be DataFrames"):
        _write_minimal_bundle(outputs, resolved_config, inputs)

    assert not inputs["output_root"].exists()


def test_bundle_manifest_keeps_deterministic_policy_lineage_explicit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outputs, resolved_config, inputs = _minimal_bundle_case(tmp_path)
    monkeypatch.setattr(
        bundle,
        "build_evaluation_provenance",
        lambda _root: {"source": {"available": False}, "runtime": {}},
    )

    created = _write_minimal_bundle(outputs, resolved_config, inputs)

    manifest = json.loads((created / "result_manifest.json").read_text(encoding="utf-8"))
    run = manifest["runs"][0]
    assert run["role"] == "deterministic_rule"
    assert run["identity"]["checkpoint_hash"] == {
        "status": "unknown",
        "reason": "deterministic baseline does not load a checkpoint",
    }
    assert run["identity"]["training_seed"]["status"] == "unknown"
    assert manifest["manifest_status"] == "draft"
    assert manifest["finding_status"] == "draft_synthetic_contract_validation"
    assert manifest["claims"] == []
    assert manifest["frozen_at_utc"] is None


def test_bundle_rejects_malformed_trained_checkpoint_lineage(tmp_path: Path) -> None:
    outputs, resolved_config, inputs = _minimal_bundle_case(tmp_path)
    outputs["candidate_rule"]["policy_metadata"].update(
        {
            "policy_source": "trained_checkpoint",
            "checkpoint_sha256": "not-a-sha256",
            "checkpoint_source_key": "checkpoint",
        }
    )

    with pytest.raises(ValueError, match="must record a SHA-256 checkpoint identity"):
        _write_minimal_bundle(outputs, resolved_config, inputs)

    assert not inputs["output_root"].exists()


def test_bundle_reports_unpaired_result_for_divergent_baseline_equity_timestamps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outputs, resolved_config, inputs = _minimal_bundle_case(tmp_path)
    baseline = outputs["candidate_rule"]
    baseline_metadata = dict(baseline["policy_metadata"])
    outputs = {
        "always_no_trade": {
            **baseline,
            "policy_metadata": {**baseline_metadata, "policy_id": "always_no_trade_v1"},
        },
        "random_eligible_setup": {
            **baseline,
            "policy_metadata": {
                **baseline_metadata,
                "policy_id": "random_eligible_setup_v1",
                "policy_source": "randomized_control",
                "random_policy_seed": 17,
            },
            "equity": baseline["equity"].copy(),
        },
    }
    outputs["random_eligible_setup"]["equity"].index = outputs["random_eligible_setup"][
        "equity"
    ].index + pd.Timedelta(minutes=1)
    monkeypatch.setattr(
        bundle,
        "build_evaluation_provenance",
        lambda _root: {"source": {"available": False}, "runtime": {}},
    )

    created = _write_minimal_bundle(outputs, resolved_config, inputs)

    manifest = json.loads((created / "result_manifest.json").read_text(encoding="utf-8"))
    interval = manifest["comparisons"][0]["paired_time_series_intervals"]
    assert interval["status"] == "not_estimable"
    assert interval["paired_return_observations"] == 0
    assert "policy equity timelines do not share an exact prefix" in interval["reason"]
