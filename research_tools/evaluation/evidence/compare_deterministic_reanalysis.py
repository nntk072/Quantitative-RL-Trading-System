#!/usr/bin/env python3
"""Compare two immutable deterministic checkpoint-reanalysis packages."""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import os
from pathlib import Path
from typing import Any

IDENTITY_FIELDS = (
    "artifact_role",
    "historical_holdout_inspected",
    "evaluation_provenance",
    "source_run",
    "source_config_sha256",
    "reanalysis_config_sha256",
    "checkpoint",
    "checkpoint_sha256",
    "checkpoint_manifest_hash_disposition",
    "action_schema_version",
    "action_layout_key",
    "action_schema",
    "observation_schema",
    "sequence_feature_schema",
    "sequence_feature_schema_disposition",
    "legacy_sequence_columns_used",
    "legacy_action_schema_opt_in",
    "legacy_observation_schema_opt_in",
    "legacy_sequence_schema_opt_in",
    "legacy_stop_schema_opt_in",
    "legacy_data_provenance_opt_in",
    "legacy_action_layout_selected",
    "stop_schema_disposition",
    "stop_candidate_schema",
    "feature_cache_identity",
    "feature_cache_hash",
    "feature_cache_file_sha256",
    "source_feature_cache_replay_path",
    "source_feature_cache",
    "feature_cache_disposition",
    "source_datasets",
    "evaluated_datasets",
    "dataset_parity_disposition",
    "training_data_source",
    "evaluation_backend",
    "backend_parity_disposition",
    "train_end",
    "test_start",
    "seed",
    "execution_seed",
    "metrics_protocol",
    "policy_action_mode",
)
SPLITS = ("training", "testing")
NUMERICAL_ARTIFACTS = (
    "equity.csv",
    "trades.csv",
    "fills.csv",
    "positions.csv",
    "metrics.json",
    "evaluation_diagnostics.json",
)
TRAIN_ONLY_IDENTITY_FIELDS = (
    "evaluation_provenance",
    "source_run",
    "source_run_manifest_sha256",
    "source_config_sha256",
    "checkpoint",
    "checkpoint_sha256",
    "checkpoint_manifest_hash_disposition",
    "training_split",
    "training_input_identity",
    "dataset_parity_disposition",
    "tick_identity_scope",
    "feature_cache",
    "source_feature_cache",
    "train_feature_snapshot",
    "evaluation_protocol",
)
TRAIN_ONLY_REQUIRED_LEDGER_ARTIFACTS = frozenset(
    {
        "equity",
        "trades",
        "policy_decisions",
        "account_state_trace",
        "breaches",
        "breach_events",
        "cycle_events",
        "payout_events",
    }
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _reconciliation_is_clean(report: Any) -> bool:
    """Accept only a matched report with an explicit integer zero failure count."""
    if not isinstance(report, dict):
        return False
    failure_count = report.get("failure_count")
    return (
        report.get("status") == "matched"
        and isinstance(failure_count, int)
        and not isinstance(failure_count, bool)
        and failure_count == 0
    )


def _read_manifest(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "reanalysis_manifest.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"reanalysis manifest must be an object: {path}")
    if value.get("artifact_role") != "historical_reanalysis":
        raise ValueError(f"unsupported artifact role in {path}")
    if value.get("policy_action_mode") != "deterministic":
        raise ValueError(f"reanalysis is not deterministic: {path}")
    provenance = value.get("evaluation_provenance")
    if (
        not isinstance(provenance, dict)
        or not isinstance(provenance.get("source"), dict)
        or not isinstance(provenance.get("runtime"), dict)
        or not isinstance(provenance.get("python_executable"), str)
    ):
        raise ValueError(f"evaluation implementation/runtime provenance is incomplete: {path}")
    source = provenance["source"]
    runtime = provenance["runtime"]
    if (
        source.get("available") is not True
        or not isinstance(source.get("head"), str)
        or not source["head"]
        or not isinstance(runtime.get("python"), str)
        or not isinstance(runtime.get("platform"), str)
    ):
        raise ValueError(f"evaluation source/runtime identity is incomplete: {path}")
    if "python_hash_seed_env" not in runtime or (
        runtime["python_hash_seed_env"] is not None
        and not isinstance(runtime["python_hash_seed_env"], str)
    ):
        raise ValueError(f"evaluation PYTHONHASHSEED provenance is missing or invalid: {path}")
    for field in (
        "legacy_sequence_columns_used",
        "legacy_action_schema_opt_in",
        "legacy_observation_schema_opt_in",
        "legacy_sequence_schema_opt_in",
        "legacy_stop_schema_opt_in",
        "legacy_data_provenance_opt_in",
    ):
        if type(value.get(field)) is not bool:
            raise ValueError(f"legacy mode field {field!r} is missing or invalid: {path}")
    if value.get("legacy_action_layout_selected") is not None and not isinstance(
        value.get("legacy_action_layout_selected"), str
    ):
        raise ValueError(f"legacy action layout is invalid: {path}")
    return value


def _source_manifest_errors(
    label: str,
    source_run: Path,
    reanalysis_manifest: dict[str, Any],
) -> list[str]:
    """Bind copied reanalysis provenance to the original training manifest."""
    errors: list[str] = []
    path = source_run / "run_manifest.json"
    if not path.is_file():
        return [f"{label} original run manifest is missing"]
    source_manifest = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(source_manifest, dict):
        return [f"{label} original run manifest is not an object"]

    config = source_manifest.get("config")
    if not isinstance(config, dict) or config.get("sha256") != reanalysis_manifest.get(
        "source_config_sha256"
    ):
        errors.append(f"{label} source config hash differs from original run manifest")

    checkpoint = source_manifest.get("checkpoint")
    if not isinstance(checkpoint, dict) or checkpoint.get("sha256") != reanalysis_manifest.get(
        "checkpoint_sha256"
    ):
        errors.append(f"{label} checkpoint hash differs from original run manifest")

    source_cache = source_manifest.get("feature_cache")
    replay_cache = reanalysis_manifest.get("source_feature_cache")
    if not isinstance(source_cache, dict) or not isinstance(replay_cache, dict):
        errors.append(f"{label} feature-cache record is missing from an original manifest")
    else:
        for field in ("identity", "sha256", "file_sha256"):
            if source_cache.get(field) != replay_cache.get(field):
                errors.append(f"{label} source feature-cache {field} differs from original")
        evaluated_cache_fields = {
            "identity": "feature_cache_identity",
            "sha256": "feature_cache_hash",
            "file_sha256": "feature_cache_file_sha256",
        }
        for source_field, evaluated_field in evaluated_cache_fields.items():
            if source_cache.get(source_field) != reanalysis_manifest.get(evaluated_field):
                errors.append(f"{label} evaluated feature cache {source_field} differs from source")

    source_datasets = source_manifest.get("datasets")
    replay_datasets = reanalysis_manifest.get("source_datasets")
    if not isinstance(source_datasets, dict) or not isinstance(replay_datasets, dict):
        errors.append(f"{label} dataset records are missing from an original manifest")
    elif set(source_datasets) != set(replay_datasets):
        errors.append(f"{label} dataset set differs from original run manifest")
    else:
        for name, source_record in source_datasets.items():
            replay_record = replay_datasets[name]
            if (
                not isinstance(source_record, dict)
                or not isinstance(replay_record, dict)
                or source_record.get("sha256") != replay_record.get("sha256")
            ):
                errors.append(f"{label} dataset hash differs from original: {name}")

                # The numerical-report verifier applies these same compatibility gates.
                # Repeatability is meaningless if both replays silently used a different
                # action, observation, stop, or sequence-feature contract than training.
    for schema_key in ("action_schema", "observation_schema"):
        original_schema = source_manifest.get(schema_key)
        replay_schema = reanalysis_manifest.get(schema_key)
        if not isinstance(original_schema, dict):
            errors.append(f"{label} original run manifest {schema_key} is missing")
            continue
        if not isinstance(replay_schema, dict):
            errors.append(f"{label} reanalysis {schema_key} is missing")
            continue
        replay_contract = (
            {key: value for key, value in replay_schema.items() if key != "checkpoint_metadata"}
            if schema_key == "action_schema"
            else replay_schema
        )
        if replay_contract != original_schema:
            errors.append(f"{label} reanalysis {schema_key} differs from original run manifest")

    original_sequence_schema = source_manifest.get("sequence_feature_schema")
    replay_sequence_schema = reanalysis_manifest.get("sequence_feature_schema")
    sequence_disposition = reanalysis_manifest.get("sequence_feature_schema_disposition")
    if isinstance(original_sequence_schema, dict):
        if replay_sequence_schema != original_sequence_schema:
            errors.append(f"{label} sequence-feature schema differs from original run manifest")
        if sequence_disposition != "verified":
            errors.append(f"{label} sequence-feature schema is not verified")
        if reanalysis_manifest.get("legacy_sequence_schema_opt_in") is not False:
            errors.append(f"{label} sequence-feature schema used legacy opt-in")
        if reanalysis_manifest.get("legacy_sequence_columns_used") is not False:
            errors.append(f"{label} replay used legacy sequence columns")
    else:
        if sequence_disposition != "legacy_unverified":
            errors.append(f"{label} missing source sequence schema is not marked legacy")
        if reanalysis_manifest.get("legacy_sequence_schema_opt_in") is not True:
            errors.append(f"{label} missing source sequence schema lacks explicit opt-in")
        if reanalysis_manifest.get("legacy_sequence_columns_used") is not True:
            errors.append(f"{label} missing source sequence schema did not use legacy columns")

    if reanalysis_manifest.get("checkpoint_manifest_hash_disposition") != "verified":
        errors.append(f"{label} checkpoint manifest hash is not verified")
    for opt_in in (
        "legacy_action_schema_opt_in",
        "legacy_observation_schema_opt_in",
    ):
        if reanalysis_manifest.get(opt_in) is not False:
            errors.append(f"{label} used unsupported legacy schema opt-in: {opt_in}")

    original_stop_schema = source_manifest.get("stop_candidate_schema")
    replay_stop_schema = reanalysis_manifest.get("stop_candidate_schema")
    stop_disposition = reanalysis_manifest.get("stop_schema_disposition")
    legacy_stop_opt_in = reanalysis_manifest.get("legacy_stop_schema_opt_in")
    if isinstance(original_stop_schema, dict):
        if replay_stop_schema != original_stop_schema:
            errors.append(f"{label} stop-candidate schema differs from original run manifest")
        if stop_disposition != "versioned":
            errors.append(f"{label} stop-candidate schema is not versioned")
        if legacy_stop_opt_in is not False:
            errors.append(
                f"{label} used unsupported legacy schema opt-in: legacy_stop_schema_opt_in"
            )
    else:
        if replay_stop_schema is not None:
            errors.append(f"{label} replay claims a stop-candidate schema absent from the source")
        if stop_disposition != "legacy_opt_in":
            errors.append(f"{label} missing source stop-candidate schema is not marked legacy")
        if legacy_stop_opt_in is not True:
            errors.append(f"{label} missing source stop-candidate schema lacks explicit opt-in")
    original_protocol = source_manifest.get("execution_protocol")
    if not isinstance(original_protocol, dict) or original_protocol.get(
        "data_source"
    ) != reanalysis_manifest.get("training_data_source"):
        errors.append(f"{label} training backend differs from original run manifest")
    return errors


def compare_reanalyses(first_dir: Path, second_dir: Path) -> dict[str, Any]:
    """Require shared provenance and byte-identical numerical outputs."""
    first = first_dir.resolve()
    second = second_dir.resolve()
    first_manifest = _read_manifest(first)
    second_manifest = _read_manifest(second)
    errors: list[str] = []

    identity: dict[str, Any] = {}
    for field in IDENTITY_FIELDS:
        left = first_manifest.get(field)
        right = second_manifest.get(field)
        identity[field] = left
        # PYTHONHASHSEED is an intentional independent variable in a crossed
        # hash-seed replay. Require both records, but compare the remaining
        # evaluator/runtime provenance exactly.
        left_identity = left
        right_identity = right
        if field == "evaluation_provenance":
            left_identity = copy.deepcopy(left)
            right_identity = copy.deepcopy(right)
            for provenance in (left_identity, right_identity):
                if isinstance(provenance, dict) and isinstance(provenance.get("runtime"), dict):
                    provenance["runtime"].pop("python_hash_seed_env", None)
        if left_identity != right_identity:
            errors.append(f"reanalysis identity differs: {field}")
    if first_manifest.get("dataset_parity_disposition") != "verified":
        errors.append("first reanalysis does not have verified dataset parity")
    if second_manifest.get("dataset_parity_disposition") != "verified":
        errors.append("second reanalysis does not have verified dataset parity")
    if first_manifest.get("checkpoint_manifest_hash_disposition") != "verified":
        errors.append("first reanalysis checkpoint is not hash-verified")
    if second_manifest.get("checkpoint_manifest_hash_disposition") != "verified":
        errors.append("second reanalysis checkpoint is not hash-verified")

    first_config = first / "config.yaml"
    second_config = second / "config.yaml"
    if not first_config.is_file() or not second_config.is_file():
        errors.append("one or both reanalysis config snapshots are missing")
        config_hashes: dict[str, str | None] = {
            "first": _sha256(first_config) if first_config.is_file() else None,
            "second": _sha256(second_config) if second_config.is_file() else None,
        }
    else:
        config_hashes = {"first": _sha256(first_config), "second": _sha256(second_config)}
        if config_hashes["first"] != config_hashes["second"]:
            errors.append("reanalysis config snapshots differ")
        if first_manifest.get("reanalysis_config_sha256") != config_hashes["first"]:
            errors.append("first reanalysis config hash differs from its manifest")
        if second_manifest.get("reanalysis_config_sha256") != config_hashes["second"]:
            errors.append("second reanalysis config hash differs from its manifest")

    for label, manifest in (("first", first_manifest), ("second", second_manifest)):
        source_run = manifest.get("source_run")
        source_config_hash = manifest.get("source_config_sha256")
        checkpoint_path = manifest.get("checkpoint")
        checkpoint_hash = manifest.get("checkpoint_sha256")
        if not isinstance(source_run, str) or not isinstance(source_config_hash, str):
            errors.append(f"{label} reanalysis lacks source config provenance")
        else:
            source_config = Path(source_run) / "config.yaml"
            if not source_config.is_file() or _sha256(source_config) != source_config_hash:
                errors.append(f"{label} source config does not match its recorded hash")
            errors.extend(_source_manifest_errors(label, Path(source_run), manifest))
        if not isinstance(checkpoint_path, str) or not isinstance(checkpoint_hash, str):
            errors.append(f"{label} reanalysis lacks checkpoint file provenance")
        else:
            checkpoint = Path(checkpoint_path)
            if not checkpoint.is_file() or _sha256(checkpoint) != checkpoint_hash:
                errors.append(f"{label} checkpoint does not match its recorded hash")
        if manifest.get("feature_cache_disposition") not in {
            "verified",
            "source_cache_replay_verified",
        }:
            errors.append(f"{label} reanalysis feature cache is not hash-verified")
        evaluated_cache_path = manifest.get("evaluated_feature_cache_path")
        evaluated_cache_hash = manifest.get("feature_cache_file_sha256")
        if not isinstance(evaluated_cache_path, str) or not isinstance(evaluated_cache_hash, str):
            errors.append(f"{label} evaluated feature cache provenance is missing")
        else:
            evaluated_cache = Path(evaluated_cache_path)
            if not evaluated_cache.is_file() or _sha256(evaluated_cache) != evaluated_cache_hash:
                errors.append(f"{label} evaluated feature cache does not match its recorded hash")
        cache_path = manifest.get("source_feature_cache_replay_path")
        cache_hash = manifest.get("feature_cache_file_sha256")
        if cache_path is not None:
            if not isinstance(cache_path, str) or not isinstance(cache_hash, str):
                errors.append(f"{label} source feature cache provenance is malformed")
            else:
                cache_file = Path(cache_path)
                if not cache_file.is_file() or _sha256(cache_file) != cache_hash:
                    errors.append(f"{label} source feature cache does not match its recorded hash")

    artifacts: list[dict[str, Any]] = []
    for split in SPLITS:
        for name in NUMERICAL_ARTIFACTS:
            first_path = first / split / name
            second_path = second / split / name
            left_hash = _sha256(first_path) if first_path.is_file() else None
            right_hash = _sha256(second_path) if second_path.is_file() else None
            same = left_hash is not None and left_hash == right_hash
            artifacts.append(
                {
                    "split": split,
                    "name": name,
                    "first_sha256": left_hash,
                    "second_sha256": right_hash,
                    "identical": same,
                }
            )
            if left_hash is None or right_hash is None:
                errors.append(f"required numerical artifact missing: {split}/{name}")
            elif not same:
                errors.append(f"numerical artifact differs: {split}/{name}")

    return {
        "schema_version": 1,
        "status": "passed" if not errors else "failed",
        "artifact_role": "deterministic_reanalysis_repeatability",
        "first_reanalysis": str(first),
        "second_reanalysis": str(second),
        "identity": identity,
        "python_hash_seed_env": {
            "first": first_manifest["evaluation_provenance"]["runtime"]["python_hash_seed_env"],
            "second": second_manifest["evaluation_provenance"]["runtime"]["python_hash_seed_env"],
        },
        "evaluated_feature_caches": {
            "first": {
                "path": first_manifest.get("evaluated_feature_cache_path"),
                "sha256": first_manifest.get("feature_cache_file_sha256"),
            },
            "second": {
                "path": second_manifest.get("evaluated_feature_cache_path"),
                "sha256": second_manifest.get("feature_cache_file_sha256"),
            },
        },
        "config_sha256": config_hashes,
        "numerical_artifacts": artifacts,
        "errors": errors,
        "interpretation_limit": (
            "Repeatability of deterministic reanalysis artifacts does not establish "
            "strategy validity, out-of-sample generalization, or confirmatory evidence."
        ),
    }


def _read_train_only_screen(directory: Path) -> dict[str, Any]:
    path = directory / "train_only_screen.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"train-only screen must be an object: {path}")
    ledger = value.get("replay_ledger")
    if not isinstance(ledger, dict) or ledger.get("complete") is not True:
        raise ValueError(f"train-only replay ledger is not complete: {path}")
    if (
        value.get("test_split_evaluated") is not False
        or ledger.get("test_split_evaluated") is not False
    ):
        raise ValueError(f"train-only screen evaluated the test split: {path}")
    protocol = value.get("evaluation_protocol")
    if not isinstance(protocol, dict) or protocol.get("policy_action_mode") != "deterministic":
        raise ValueError(f"train-only screen is not a deterministic policy replay: {path}")
    execution_seed = protocol.get("execution_seed")
    if isinstance(execution_seed, bool) or not isinstance(execution_seed, int):
        raise ValueError(f"train-only screen lacks an explicit integer execution seed: {path}")
    training_split = value.get("training_split")
    if (
        not isinstance(training_split, dict)
        or training_split.get("completed_data_split") is not True
        or isinstance(training_split.get("bar_count"), bool)
        or not isinstance(training_split.get("bar_count"), int)
        or training_split.get("bar_count", 0) <= 0
    ):
        raise ValueError(f"train-only screen did not complete a nonempty training split: {path}")
    for key in ("account_state_reconciliation", "policy_decision_reconciliation"):
        report = ledger.get(key)
        if not _reconciliation_is_clean(report):
            raise ValueError(f"train-only screen has no passing {key}: {path}")
    missing = [field for field in TRAIN_ONLY_IDENTITY_FIELDS if field not in value]
    if missing:
        raise ValueError(f"train-only screen lacks identity fields {missing}: {path}")
    artifacts = ledger.get("artifacts")
    if not isinstance(artifacts, dict) or not TRAIN_ONLY_REQUIRED_LEDGER_ARTIFACTS.issubset(
        artifacts
    ):
        raise ValueError(f"train-only screen lacks required replay ledgers: {path}")
    action_schema = value.get("action_schema")
    if (
        isinstance(action_schema, dict)
        and action_schema.get("has_trade_setup") is True
        and "trade_setup_decisions" not in artifacts
    ):
        raise ValueError(f"setup-aware train-only screen lacks trade setup decision ledger: {path}")
    n_steps = ledger.get("n_steps")
    if isinstance(n_steps, bool) or not isinstance(n_steps, int) or n_steps < 0:
        raise ValueError(f"train-only screen has an invalid rollout step count: {path}")
    for name in ("policy_decisions", "account_state_trace"):
        metadata = artifacts.get(name)
        row_count = metadata.get("row_count") if isinstance(metadata, dict) else None
        if not isinstance(row_count, int) or isinstance(row_count, bool) or row_count != n_steps:
            raise ValueError(f"train-only screen {name} rows do not match rollout steps: {path}")
    return value


def _verify_train_only_artifact(directory: Path, metadata: Any) -> tuple[bool, dict[str, Any]]:
    if not isinstance(metadata, dict):
        return False, {"valid": False, "reason": "artifact metadata is not an object"}
    relative_path = metadata.get("path")
    if not isinstance(relative_path, str) or Path(relative_path).is_absolute():
        return False, {"valid": False, "reason": "artifact path is not relative"}
    path = (directory / relative_path).resolve()
    if directory.resolve() not in path.parents:
        return False, {"valid": False, "reason": "artifact path escapes replay directory"}
    if not path.is_file():
        return False, {"valid": False, "reason": "artifact file is missing"}
    actual_hash = _sha256(path)
    with path.open(encoding="utf-8", newline="") as stream:
        actual_rows = max(0, sum(1 for _ in csv.reader(stream)) - 1)
    expected_hash = metadata.get("sha256")
    expected_rows = metadata.get("row_count")
    valid = (
        isinstance(expected_hash, str)
        and isinstance(expected_rows, int)
        and not isinstance(expected_rows, bool)
        and expected_rows >= 0
        and actual_hash == expected_hash
        and actual_rows == expected_rows
    )
    return valid, {
        "valid": valid,
        "path": relative_path,
        "expected_sha256": metadata.get("sha256"),
        "actual_sha256": actual_hash,
        "expected_rows": metadata.get("row_count"),
        "actual_rows": actual_rows,
    }


def _cached_sha256(path: Path, cache: dict[Path, str]) -> str:
    resolved = path.resolve()
    if resolved not in cache:
        cache[resolved] = _sha256(resolved)
    return cache[resolved]


def _train_only_source_errors(
    label: str, report: dict[str, Any], digest_cache: dict[Path, str]
) -> list[str]:
    """Verify checkpoint/config/data identities against their current source bytes."""
    errors: list[str] = []
    source_value = report.get("source_run")
    if not isinstance(source_value, str):
        return [f"{label} train-only replay source run path is missing"]
    source_run = Path(source_value)
    manifest_path = source_run / "run_manifest.json"
    config_path = source_run / "config.yaml"
    if not manifest_path.is_file():
        return [f"{label} source run manifest is missing"]
    try:
        source_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"{label} source run manifest cannot be read: {type(exc).__name__}"]
    if not isinstance(source_manifest, dict):
        return [f"{label} source run manifest is not an object"]
    if _cached_sha256(manifest_path, digest_cache) != report.get("source_run_manifest_sha256"):
        errors.append(f"{label} source run manifest bytes differ from replay report")
    if not config_path.is_file() or _cached_sha256(config_path, digest_cache) != report.get(
        "source_config_sha256"
    ):
        errors.append(f"{label} source config bytes differ from replay report")
    config_record = source_manifest.get("config")
    if not isinstance(config_record, dict) or config_record.get("sha256") != report.get(
        "source_config_sha256"
    ):
        errors.append(f"{label} source config hash differs from original run manifest")

    checkpoint_value = report.get("checkpoint")
    if not isinstance(checkpoint_value, str):
        errors.append(f"{label} checkpoint path is missing")
    else:
        checkpoint = Path(checkpoint_value)
        checkpoint_record = source_manifest.get("checkpoint")
        if not checkpoint.is_file() or _cached_sha256(checkpoint, digest_cache) != report.get(
            "checkpoint_sha256"
        ):
            errors.append(f"{label} checkpoint bytes differ from replay report")
        if not isinstance(checkpoint_record, dict) or checkpoint_record.get("sha256") != report.get(
            "checkpoint_sha256"
        ):
            errors.append(f"{label} checkpoint hash differs from original run manifest")
    if report.get("checkpoint_manifest_hash_disposition") != "verified":
        errors.append(f"{label} checkpoint manifest hash was not verified")

    feature_cache = report.get("feature_cache")
    if not isinstance(feature_cache, dict):
        errors.append(f"{label} evaluated feature-cache identity is missing")
    elif feature_cache.get("identity_scope") == "train_features_frame_only":
        source_cache = source_manifest.get("feature_cache")
        reported_source_cache = report.get("source_feature_cache")
        if not isinstance(source_cache, dict) or reported_source_cache != source_cache:
            errors.append(
                f"{label} source feature-cache metadata differs from original run manifest"
            )

        snapshot = report.get("train_feature_snapshot")
        if not isinstance(snapshot, dict):
            errors.append(f"{label} train-feature snapshot identity is missing")
        else:
            snapshot_path_value = snapshot.get("path")
            snapshot_hash = snapshot.get("file_sha256")
            if not isinstance(snapshot_path_value, str) or not isinstance(snapshot_hash, str):
                errors.append(f"{label} train-feature snapshot file identity is incomplete")
            else:
                snapshot_path = Path(snapshot_path_value)
                if (
                    not snapshot_path.is_file()
                    or _cached_sha256(snapshot_path, digest_cache) != snapshot_hash
                ):
                    errors.append(f"{label} train-feature snapshot bytes differ from replay report")

            source_datasets = source_manifest.get("datasets")
            training_identity = report.get("training_input_identity")
            source_features = (
                source_datasets.get("train_features") if isinstance(source_datasets, dict) else None
            )
            replay_features = (
                training_identity.get("train_features")
                if isinstance(training_identity, dict)
                else None
            )
            source_feature_hash = (
                source_features.get("sha256") if isinstance(source_features, dict) else None
            )
            if (
                snapshot.get("scope")
                != "training_split_only; original_full_cache_bytes_not_claimed"
                or snapshot.get("dataset_identity_verified") is not True
                or not isinstance(source_feature_hash, str)
                or replay_features != source_features
                or snapshot.get("train_features_sha256") != source_feature_hash
                or snapshot.get("source_run_train_features_sha256") != source_feature_hash
                or feature_cache.get("content_hash") != source_feature_hash
                or feature_cache.get("file_sha256") != snapshot.get("file_sha256")
            ):
                errors.append(
                    f"{label} train-feature snapshot does not match source dataset identity"
                )
    else:
        cache_path_value = feature_cache.get("path")
        cache_hash = feature_cache.get("file_sha256")
        content_hash = feature_cache.get("content_hash")
        if not isinstance(cache_path_value, str) or not isinstance(cache_hash, str):
            errors.append(f"{label} evaluated feature-cache file identity is incomplete")
        else:
            cache_path = Path(cache_path_value)
            sidecar_path = Path(f"{cache_path}.hash")
            if not cache_path.is_file() or _cached_sha256(cache_path, digest_cache) != cache_hash:
                errors.append(f"{label} evaluated feature-cache bytes differ from replay report")
            if (
                not isinstance(content_hash, str)
                or not sidecar_path.is_file()
                or sidecar_path.read_text(encoding="utf-8").strip() != content_hash
            ):
                errors.append(f"{label} evaluated feature-cache content identity differs")

    identity = report.get("training_input_identity")
    source_datasets = source_manifest.get("datasets")
    if not isinstance(identity, dict) or not isinstance(source_datasets, dict):
        errors.append(f"{label} training dataset identity is missing")
    else:
        for name, record in identity.items():
            if name == "primary_ticks":
                # The report fingerprints the training partition; the source
                # manifest records a broader tick extent.
                continue
            if source_datasets.get(name) != record:
                errors.append(f"{label} training dataset identity differs: {name}")
    tick_scope = report.get("tick_identity_scope")
    if (
        not isinstance(tick_scope, dict)
        or tick_scope.get("disposition") != "training_partition_only"
        or tick_scope.get("full_tick_identity_reloaded") is not False
    ):
        errors.append(f"{label} tick identity scope is not explicitly bounded to training")
    return errors


def compare_train_only_replays(first_dir: Path, second_dir: Path) -> dict[str, Any]:
    """Compare immutable train-only replay ledgers without evaluating test data."""
    first, second = first_dir.resolve(), second_dir.resolve()
    if first == second:
        raise ValueError("train-only replay directories must be distinct")
    left = _read_train_only_screen(first)
    right = _read_train_only_screen(second)
    errors = [
        f"train-only replay identity differs: {field}"
        for field in TRAIN_ONLY_IDENTITY_FIELDS
        if left.get(field) != right.get(field)
    ]
    digest_cache: dict[Path, str] = {}
    errors.extend(_train_only_source_errors("first", left, digest_cache))
    errors.extend(_train_only_source_errors("second", right, digest_cache))
    left_ledger, right_ledger = left["replay_ledger"], right["replay_ledger"]
    for key in ("account_state_reconciliation", "policy_decision_reconciliation"):
        if left_ledger.get(key) != right_ledger.get(key):
            errors.append(f"train-only replay reconciliation differs: {key}")
    left_artifacts, right_artifacts = left_ledger["artifacts"], right_ledger["artifacts"]
    artifacts: list[dict[str, Any]] = []
    for name in sorted(set(left_artifacts) | set(right_artifacts)):
        left_valid, left_record = _verify_train_only_artifact(first, left_artifacts.get(name))
        right_valid, right_record = _verify_train_only_artifact(second, right_artifacts.get(name))
        equal = (
            left_valid
            and right_valid
            and left_record.get("actual_sha256") == right_record.get("actual_sha256")
            and left_record.get("actual_rows") == right_record.get("actual_rows")
        )
        artifacts.append(
            {"name": name, "identical": equal, "first": left_record, "second": right_record}
        )
        if not equal:
            errors.append(f"train-only replay ledger differs or failed verification: {name}")
    return {
        "schema_version": 1,
        "status": "passed" if not errors else "failed",
        "artifact_role": "train_only_checkpoint_replay_repeatability",
        "first_replay": str(first),
        "second_replay": str(second),
        "test_split_evaluated": False,
        "identity": {field: left.get(field) for field in TRAIN_ONLY_IDENTITY_FIELDS},
        "reconciliations": {
            "account_state": left_ledger["account_state_reconciliation"],
            "policy_decisions": left_ledger["policy_decision_reconciliation"],
        },
        "ledgers": artifacts,
        "errors": errors,
        "interpretation_limit": (
            "Train-only deterministic repeatability and simulator reconciliation do not establish "
            "strategy validity, out-of-sample generalization, or confirmatory evidence."
        ),
    }


def write_report(report: dict[str, Any], output: Path) -> None:
    """Create a new immutable JSON report without overwriting prior evidence."""
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.link(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("first", type=Path, help="First deterministic reanalysis directory")
    parser.add_argument("second", type=Path, help="Second deterministic reanalysis directory")
    parser.add_argument(
        "--train-only-screen",
        action="store_true",
        help=(
            "Compare complete train-only screen ledgers instead of full historical "
            "reanalysis packages"
        ),
    )
    parser.add_argument("--output", type=Path, required=True, help="New comparison JSON report")
    args = parser.parse_args()
    try:
        report = (
            compare_train_only_replays(args.first, args.second)
            if args.train_only_screen
            else compare_reanalyses(args.first, args.second)
        )
        write_report(report, args.output)
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        report = {
            "schema_version": 1,
            "status": "failed",
            "artifact_role": "deterministic_reanalysis_repeatability",
            "errors": [f"comparison could not complete: {type(exc).__name__}: {exc}"],
        }
        print(json.dumps(report, indent=2, sort_keys=True))
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
