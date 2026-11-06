"""Deterministic report comparison requires shared provenance and raw outputs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from scripts.research.analysis.evidence.compare_deterministic_reanalysis import (
    IDENTITY_FIELDS,
    NUMERICAL_ARTIFACTS,
    SPLITS,
    compare_reanalyses,
    compare_train_only_replays,
)


def _write_reanalysis(path: Path) -> None:
    path.mkdir()
    source_run = path.parent / "source_run"
    source_run.mkdir(exist_ok=True)
    source_config = source_run / "config.yaml"
    source_config.write_text("source: true\n", encoding="utf-8")
    checkpoint = source_run / "checkpoint.zip"
    checkpoint.write_bytes(b"checkpoint")
    feature_cache = source_run / "features.parquet"
    feature_cache.write_bytes(b"feature-cache")
    source_feature_cache = {
        "identity": "features.parquet",
        "sha256": "feature-content-hash",
        "file_sha256": hashlib.sha256(feature_cache.read_bytes()).hexdigest(),
    }
    source_datasets = {
        "train_bars": {"sha256": "train-bars-hash"},
        "test_bars": {"sha256": "test-bars-hash"},
    }
    source_manifest = {
        "config": {"sha256": hashlib.sha256(source_config.read_bytes()).hexdigest()},
        "checkpoint": {"sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest()},
        "feature_cache": source_feature_cache,
        "datasets": source_datasets,
        "action_schema": {"version": "action-v1", "key": "test"},
        "observation_schema": {"version": "observation-v1"},
        "stop_candidate_schema": {"version": "stop-v1"},
        "sequence_feature_schema": {"columns": ["ema", "reachable_r"], "width": 2},
        "execution_protocol": {"data_source": "frames"},
    }
    (source_run / "run_manifest.json").write_text(json.dumps(source_manifest), encoding="utf-8")
    output_config = b"saved: true\n"
    (path / "config.yaml").write_bytes(output_config)
    identity: dict[str, Any] = {field: {"value": field} for field in IDENTITY_FIELDS}
    identity.update(
        {
            "artifact_role": "historical_reanalysis",
            "historical_holdout_inspected": True,
            "evaluation_provenance": {
                "source": {"available": True, "head": "test-head", "dirty_files": []},
                "runtime": {
                    "python": "3.x",
                    "platform": "test",
                    "python_hash_seed_env": None,
                },
                "python_executable": "/test/python",
            },
            "legacy_sequence_columns_used": False,
            "legacy_action_schema_opt_in": False,
            "legacy_observation_schema_opt_in": False,
            "legacy_sequence_schema_opt_in": False,
            "legacy_stop_schema_opt_in": False,
            "legacy_data_provenance_opt_in": False,
            "legacy_action_layout_selected": None,
            "dataset_parity_disposition": "verified",
            "checkpoint_manifest_hash_disposition": "verified",
            "action_schema": source_manifest["action_schema"],
            "observation_schema": source_manifest["observation_schema"],
            "stop_candidate_schema": source_manifest["stop_candidate_schema"],
            "sequence_feature_schema": source_manifest["sequence_feature_schema"],
            "sequence_feature_schema_disposition": "verified",
            "training_data_source": "frames",
            "stop_schema_disposition": "versioned",
            "policy_action_mode": "deterministic",
            "execution_seed": 50,
            "source_run": str(source_run),
            "source_config_sha256": hashlib.sha256(source_config.read_bytes()).hexdigest(),
            "checkpoint": str(checkpoint),
            "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
            "feature_cache_identity": source_feature_cache["identity"],
            "feature_cache_hash": source_feature_cache["sha256"],
            "evaluated_feature_cache_path": str(feature_cache),
            "feature_cache_file_sha256": hashlib.sha256(feature_cache.read_bytes()).hexdigest(),
            "feature_cache_disposition": "verified",
            "source_feature_cache": source_feature_cache,
            "source_datasets": source_datasets,
            "source_feature_cache_replay_path": None,
            "reanalysis_config_sha256": hashlib.sha256(output_config).hexdigest(),
        }
    )
    (path / "reanalysis_manifest.json").write_text(json.dumps(identity), encoding="utf-8")
    for split in SPLITS:
        split_path = path / split
        split_path.mkdir()
        for name in NUMERICAL_ARTIFACTS:
            (split_path / name).write_text(f"{split}:{name}\n", encoding="utf-8")


def _write_train_only_replay(
    path: Path,
    *,
    action: int = 1,
    risk_check_count: int = 1,
    action_mode: str = "deterministic",
) -> None:
    path.mkdir()
    source_run = path.parent / "source_run"
    source_run.mkdir(exist_ok=True)
    source_config = source_run / "config.yaml"
    source_config.write_text("source: test\n", encoding="utf-8")
    checkpoint = source_run / "checkpoint.zip"
    checkpoint.write_bytes(b"checkpoint-bytes")
    feature_cache = source_run / "features.parquet"
    feature_cache.write_bytes(b"feature-cache-bytes")
    Path(f"{feature_cache}.hash").write_text("cache-hash\n", encoding="utf-8")
    training_datasets = {
        "train_bars": {"rows": 1, "sha256": "bars-hash"},
        "train_features": {"rows": 1, "sha256": "features-hash"},
    }
    source_manifest = {
        "config": {"sha256": hashlib.sha256(source_config.read_bytes()).hexdigest()},
        "checkpoint": {"sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest()},
        "datasets": training_datasets,
    }
    source_manifest_path = source_run / "run_manifest.json"
    source_manifest_path.write_text(json.dumps(source_manifest), encoding="utf-8")
    ledger_contents = {
        "equity": "time,value\nt0,100\n",
        "trades": "",
        "policy_decisions": f"decision_index,action\n0,{action}\n",
        "account_state_trace": "rollout_step\n1\n",
        "breaches": "",
        "breach_events": "",
        "cycle_events": "",
        "payout_events": "",
    }
    artifacts: dict[str, dict[str, Any]] = {}
    for name, contents in ledger_contents.items():
        ledger_path = path / f"replay_{name}.csv"
        ledger_path.write_text(contents, encoding="utf-8")
        artifacts[name] = {
            "path": ledger_path.name,
            "row_count": 0 if not contents else 1,
            "sha256": hashlib.sha256(ledger_path.read_bytes()).hexdigest(),
        }
    identity: dict[str, Any] = {
        "evaluation_provenance": {"source": {"head": "test"}},
        "source_run": str(source_run),
        "source_run_manifest_sha256": hashlib.sha256(source_manifest_path.read_bytes()).hexdigest(),
        "source_config_sha256": hashlib.sha256(source_config.read_bytes()).hexdigest(),
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        "checkpoint_manifest_hash_disposition": "verified",
        "training_split": {
            "start": "t0",
            "end": "t1",
            "bar_count": 1,
            "completed_data_split": True,
        },
        "training_input_identity": training_datasets,
        "dataset_parity_disposition": "verified",
        "tick_identity_scope": {
            "disposition": "training_partition_only",
            "full_tick_identity_reloaded": False,
        },
        "feature_cache": {
            "identity": feature_cache.name,
            "path": str(feature_cache),
            "content_hash": "cache-hash",
            "file_sha256": hashlib.sha256(feature_cache.read_bytes()).hexdigest(),
        },
        "source_feature_cache": None,
        "train_feature_snapshot": None,
        "evaluation_protocol": {
            "policy_action_mode": action_mode,
            "seed": None,
            "execution_seed": 50,
        },
    }
    report = {
        **identity,
        "test_split_evaluated": False,
        "replay_ledger": {
            "complete": True,
            "test_split_evaluated": False,
            "n_steps": 1,
            "account_state_reconciliation": {
                "status": "matched",
                "failure_count": 0,
                "checks": {"daily_floor": risk_check_count},
            },
            "policy_decision_reconciliation": {"status": "matched", "failure_count": 0},
            "artifacts": artifacts,
        },
    }
    (path / "train_only_screen.json").write_text(json.dumps(report), encoding="utf-8")


def _write_train_only_snapshot_replay(path: Path, snapshot_path: Path) -> None:
    _write_train_only_replay(path)
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_bytes(b"assembled-training-feature-frame")
    snapshot_hash = hashlib.sha256(snapshot_path.read_bytes()).hexdigest()

    screen_path = path / "train_only_screen.json"
    screen = json.loads(screen_path.read_text(encoding="utf-8"))
    source_run = Path(screen["source_run"])
    manifest_path = source_run / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["feature_cache"] = {
        "identity": "historical-full-cache",
        "sha256": "historical-content-hash",
        "file_sha256": "historical-file-hash",
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    training_features = manifest["datasets"]["train_features"]
    screen["source_run_manifest_sha256"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    screen["source_feature_cache"] = manifest["feature_cache"]
    screen["training_input_identity"]["train_features"] = training_features
    screen["feature_cache"] = {
        "identity": "assembled-train-frame",
        "path": str(snapshot_path),
        "content_hash": training_features["sha256"],
        "file_sha256": snapshot_hash,
        "identity_scope": "train_features_frame_only",
    }
    screen["train_feature_snapshot"] = {
        "path": str(snapshot_path),
        "file_sha256": snapshot_hash,
        "train_features_sha256": training_features["sha256"],
        "source_run_train_features_sha256": training_features["sha256"],
        "dataset_identity_verified": True,
        "scope": "training_split_only; original_full_cache_bytes_not_claimed",
    }
    screen_path.write_text(json.dumps(screen), encoding="utf-8")


def test_reanalysis_comparator_accepts_identical_packages(tmp_path: Path) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    _write_reanalysis(first)
    _write_reanalysis(second)

    report = compare_reanalyses(first, second)

    assert report["status"] == "passed"
    assert len(report["numerical_artifacts"]) == len(SPLITS) * len(NUMERICAL_ARTIFACTS)
    assert report["errors"] == []


def test_reanalysis_comparator_accepts_complete_identical_train_only_replays(
    tmp_path: Path,
) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    _write_train_only_replay(first)
    _write_train_only_replay(second)

    report = compare_train_only_replays(first, second)

    assert report["status"] == "passed"
    assert report["test_split_evaluated"] is False
    assert len(report["ledgers"]) == 8
    assert report["errors"] == []


def test_reanalysis_comparator_accepts_verified_train_feature_snapshots(
    tmp_path: Path,
) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    snapshot = tmp_path / "assembled_train_features.parquet"
    _write_train_only_snapshot_replay(first, snapshot)
    _write_train_only_snapshot_replay(second, snapshot)

    report = compare_train_only_replays(first, second)

    assert report["status"] == "passed"
    assert report["identity"]["train_feature_snapshot"]["scope"] == (
        "training_split_only; original_full_cache_bytes_not_claimed"
    )


def test_reanalysis_comparator_rejects_changed_train_feature_snapshot_bytes(
    tmp_path: Path,
) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    first_snapshot, second_snapshot = tmp_path / "first.parquet", tmp_path / "second.parquet"
    _write_train_only_snapshot_replay(first, first_snapshot)
    _write_train_only_snapshot_replay(second, second_snapshot)
    second_snapshot.write_bytes(b"modified-frame")

    report = compare_train_only_replays(first, second)

    assert report["status"] == "failed"
    assert "second train-feature snapshot bytes differ from replay report" in report["errors"]


def test_reanalysis_comparator_rejects_snapshot_with_mismatched_source_feature_digest(
    tmp_path: Path,
) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    snapshot = tmp_path / "assembled_train_features.parquet"
    _write_train_only_snapshot_replay(first, snapshot)
    _write_train_only_snapshot_replay(second, snapshot)
    screen_path = second / "train_only_screen.json"
    screen = json.loads(screen_path.read_text(encoding="utf-8"))
    screen["train_feature_snapshot"]["train_features_sha256"] = "wrong-digest"
    screen_path.write_text(json.dumps(screen), encoding="utf-8")

    report = compare_train_only_replays(first, second)

    assert report["status"] == "failed"
    assert (
        "second train-feature snapshot does not match source dataset identity" in report["errors"]
    )


def test_reanalysis_comparator_rejects_different_train_only_action_ledgers(
    tmp_path: Path,
) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    _write_train_only_replay(first)
    _write_train_only_replay(second, action=0)

    report = compare_train_only_replays(first, second)

    assert report["status"] == "failed"
    assert (
        "train-only replay ledger differs or failed verification: policy_decisions"
        in report["errors"]
    )


def test_reanalysis_comparator_rejects_train_only_replay_without_risk_reconciliation(
    tmp_path: Path,
) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    _write_train_only_replay(first)
    _write_train_only_replay(second)
    screen_path = second / "train_only_screen.json"
    screen = json.loads(screen_path.read_text(encoding="utf-8"))
    screen["replay_ledger"]["account_state_reconciliation"]["status"] = "incomplete"
    screen_path.write_text(json.dumps(screen), encoding="utf-8")

    with pytest.raises(ValueError, match="no passing account_state_reconciliation"):
        compare_train_only_replays(first, second)


@pytest.mark.parametrize("artifact", ["cycle_events", "payout_events"])
def test_train_only_replay_requires_cash_event_ledgers(tmp_path: Path, artifact: str) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    _write_train_only_replay(first)
    _write_train_only_replay(second)
    screen_path = second / "train_only_screen.json"
    screen = json.loads(screen_path.read_text(encoding="utf-8"))
    del screen["replay_ledger"]["artifacts"][artifact]
    screen_path.write_text(json.dumps(screen), encoding="utf-8")

    with pytest.raises(ValueError, match="lacks required replay ledgers"):
        compare_train_only_replays(first, second)


def test_train_only_replay_requires_setup_ledger_when_action_schema_uses_setups(
    tmp_path: Path,
) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    _write_train_only_replay(first)
    _write_train_only_replay(second)
    screen_path = second / "train_only_screen.json"
    screen = json.loads(screen_path.read_text(encoding="utf-8"))
    screen["action_schema"] = {"has_trade_setup": True}
    screen_path.write_text(json.dumps(screen), encoding="utf-8")

    with pytest.raises(ValueError, match="lacks trade setup decision ledger"):
        compare_train_only_replays(first, second)


@pytest.mark.parametrize("failure_count", [False, 0.0, "0"])
def test_train_only_replay_rejects_malformed_reconciliation_counts(
    tmp_path: Path, failure_count: object
) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    _write_train_only_replay(first)
    _write_train_only_replay(second)
    screen_path = second / "train_only_screen.json"
    screen = json.loads(screen_path.read_text(encoding="utf-8"))
    screen["replay_ledger"]["account_state_reconciliation"]["failure_count"] = failure_count
    screen_path.write_text(json.dumps(screen), encoding="utf-8")

    with pytest.raises(ValueError, match="no passing account_state_reconciliation"):
        compare_train_only_replays(first, second)


@pytest.mark.parametrize("artifact", ["policy_decisions", "account_state_trace"])
def test_train_only_replay_rejects_boolean_rollout_row_counts(
    tmp_path: Path, artifact: str
) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    _write_train_only_replay(first)
    _write_train_only_replay(second)
    screen_path = second / "train_only_screen.json"
    screen = json.loads(screen_path.read_text(encoding="utf-8"))
    screen["replay_ledger"]["artifacts"][artifact]["row_count"] = True
    screen_path.write_text(json.dumps(screen), encoding="utf-8")

    with pytest.raises(ValueError, match="rows do not match rollout steps"):
        compare_train_only_replays(first, second)


def test_train_only_replay_rejects_boolean_row_count_on_other_ledgers(tmp_path: Path) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    _write_train_only_replay(first)
    _write_train_only_replay(second)
    screen_path = second / "train_only_screen.json"
    screen = json.loads(screen_path.read_text(encoding="utf-8"))
    screen["replay_ledger"]["artifacts"]["equity"]["row_count"] = True
    screen_path.write_text(json.dumps(screen), encoding="utf-8")

    report = compare_train_only_replays(first, second)

    assert report["status"] == "failed"
    assert any(
        "replay ledger differs or failed verification: equity" in error
        for error in report["errors"]
    )


def test_reanalysis_comparator_requires_deterministic_policy_actions(
    tmp_path: Path,
) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    _write_train_only_replay(first)
    _write_train_only_replay(second, action_mode="stochastic")

    with pytest.raises(ValueError, match="not a deterministic policy replay"):
        compare_train_only_replays(first, second)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda report: report["evaluation_protocol"].update(execution_seed=None),
            "execution seed",
        ),
        (
            lambda report: report["training_split"].update(completed_data_split=False),
            "did not complete",
        ),
        (
            lambda report: report["replay_ledger"].update(n_steps=2),
            "rows do not match rollout steps",
        ),
    ],
)
def test_reanalysis_comparator_requires_complete_seeded_train_replay(
    tmp_path: Path, mutate: Any, message: str
) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    _write_train_only_replay(first)
    _write_train_only_replay(second)
    screen_path = second / "train_only_screen.json"
    screen = json.loads(screen_path.read_text(encoding="utf-8"))
    mutate(screen)
    screen_path.write_text(json.dumps(screen), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        compare_train_only_replays(first, second)


def test_reanalysis_comparator_checks_train_only_source_bytes(tmp_path: Path) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    _write_train_only_replay(first)
    _write_train_only_replay(second)
    (tmp_path / "source_run" / "checkpoint.zip").write_bytes(b"changed-checkpoint")

    report = compare_train_only_replays(first, second)

    assert report["status"] == "failed"
    assert "first checkpoint bytes differ from replay report" in report["errors"]


def test_reanalysis_comparator_rejects_different_execution_seeds(tmp_path: Path) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    _write_reanalysis(first)
    _write_reanalysis(second)
    manifest_path = second / "reanalysis_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["execution_seed"] = 51
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report = compare_reanalyses(first, second)

    assert report["status"] == "failed"
    assert "reanalysis identity differs: execution_seed" in report["errors"]


def test_reanalysis_comparator_accepts_explicit_legacy_stop_schema(tmp_path: Path) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    _write_reanalysis(first)
    _write_reanalysis(second)
    source_manifest_path = tmp_path / "source_run" / "run_manifest.json"
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    source_manifest.pop("stop_candidate_schema")
    source_manifest_path.write_text(json.dumps(source_manifest), encoding="utf-8")
    for run_dir in (first, second):
        manifest_path = run_dir / "reanalysis_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["stop_candidate_schema"] = None
        manifest["stop_schema_disposition"] = "legacy_opt_in"
        manifest["legacy_stop_schema_opt_in"] = True
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report = compare_reanalyses(first, second)

    assert report["status"] == "passed"
    assert report["errors"] == []


def test_reanalysis_comparator_rejects_missing_stop_schema_without_opt_in(tmp_path: Path) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    _write_reanalysis(first)
    _write_reanalysis(second)
    source_manifest_path = tmp_path / "source_run" / "run_manifest.json"
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    source_manifest.pop("stop_candidate_schema")
    source_manifest_path.write_text(json.dumps(source_manifest), encoding="utf-8")
    for run_dir in (first, second):
        manifest_path = run_dir / "reanalysis_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["stop_candidate_schema"] = None
        manifest["stop_schema_disposition"] = "legacy_opt_in"
        manifest["legacy_stop_schema_opt_in"] = False
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report = compare_reanalyses(first, second)

    assert report["status"] == "failed"
    assert "first missing source stop-candidate schema lacks explicit opt-in" in report["errors"]


def test_reanalysis_comparator_rejects_changed_raw_trade_artifact(tmp_path: Path) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    _write_reanalysis(first)
    _write_reanalysis(second)
    (second / "testing" / "trades.csv").write_text("changed\n", encoding="utf-8")

    report = compare_reanalyses(first, second)

    assert report["status"] == "failed"
    assert "numerical artifact differs: testing/trades.csv" in report["errors"]


def test_reanalysis_comparator_rejects_different_checkpoint_identity(tmp_path: Path) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    _write_reanalysis(first)
    _write_reanalysis(second)
    manifest_path = second / "reanalysis_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["checkpoint_sha256"] = "different-checkpoint"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report = compare_reanalyses(first, second)

    assert report["status"] == "failed"
    assert "reanalysis identity differs: checkpoint_sha256" in report["errors"]


def test_reanalysis_comparator_rejects_different_evaluator_source_identity(
    tmp_path: Path,
) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    _write_reanalysis(first)
    _write_reanalysis(second)
    manifest_path = second / "reanalysis_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["evaluation_provenance"]["source"]["head"] = "other-head"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report = compare_reanalyses(first, second)

    assert report["status"] == "failed"
    assert "reanalysis identity differs: evaluation_provenance" in report["errors"]


def test_reanalysis_comparator_accepts_crossed_hash_seed_when_artifacts_match(
    tmp_path: Path,
) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    _write_reanalysis(first)
    _write_reanalysis(second)
    for run_dir, seed in ((first, "1"), (second, "12")):
        manifest_path = run_dir / "reanalysis_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["evaluation_provenance"]["runtime"]["python_hash_seed_env"] = seed
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report = compare_reanalyses(first, second)

    assert report["status"] == "passed"
    assert report["python_hash_seed_env"] == {"first": "1", "second": "12"}


def test_reanalysis_comparator_rejects_malformed_hash_seed_record(tmp_path: Path) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    _write_reanalysis(first)
    _write_reanalysis(second)
    manifest_path = second / "reanalysis_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["evaluation_provenance"]["runtime"]["python_hash_seed_env"] = 12
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="PYTHONHASHSEED provenance is missing or invalid"):
        compare_reanalyses(first, second)


def test_reanalysis_comparator_rejects_cache_identity_detached_from_source(
    tmp_path: Path,
) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    _write_reanalysis(first)
    _write_reanalysis(second)
    for run_dir in (first, second):
        manifest_path = run_dir / "reanalysis_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["feature_cache_hash"] = "same-but-not-source-hash"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report = compare_reanalyses(first, second)

    assert report["status"] == "failed"
    assert "first evaluated feature cache sha256 differs from source" in report["errors"]


def test_reanalysis_comparator_rejects_source_dataset_manifest_drift(
    tmp_path: Path,
) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    _write_reanalysis(first)
    _write_reanalysis(second)
    source_manifest_path = tmp_path / "source_run" / "run_manifest.json"
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    source_manifest["datasets"]["train_bars"]["sha256"] = "changed-source-data"
    source_manifest_path.write_text(json.dumps(source_manifest), encoding="utf-8")

    report = compare_reanalyses(first, second)

    assert report["status"] == "failed"
    assert "first dataset hash differs from original: train_bars" in report["errors"]


def test_reanalysis_comparator_rejects_sequence_schema_drift(tmp_path: Path) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    _write_reanalysis(first)
    _write_reanalysis(second)
    manifest_path = second / "reanalysis_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["sequence_feature_schema"] = {"columns": ["different"], "width": 1}
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report = compare_reanalyses(first, second)

    assert report["status"] == "failed"
    assert any(
        "sequence-feature schema differs from original" in error for error in report["errors"]
    )


def test_reanalysis_comparator_rejects_changed_evaluated_feature_cache(
    tmp_path: Path,
) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    _write_reanalysis(first)
    _write_reanalysis(second)
    manifest_path = second / "reanalysis_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    original_cache = Path(manifest["evaluated_feature_cache_path"])
    feature_cache = second / "features.parquet"
    feature_cache.write_bytes(original_cache.read_bytes())
    manifest["evaluated_feature_cache_path"] = str(feature_cache)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    feature_cache.write_bytes(b"changed-cache")

    report = compare_reanalyses(first, second)

    assert report["status"] == "failed"
    assert "second evaluated feature cache does not match its recorded hash" in report["errors"]
