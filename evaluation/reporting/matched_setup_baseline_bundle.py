"""Persist matched setup controls, rules, and policies as an immutable evidence bundle."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import re
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from omegaconf import OmegaConf

from artifacts.atomic import write_bytes_atomic, write_json_atomic
from artifacts.identity import file_sha256
from evaluation.metrics.matched_comparison import (
    _paired_equity_return_observation_count,
    paired_equity_metric_differences,
)
from evaluation.metrics.performance import METRIC_DEFINITION_VERSION, evaluation_periods_per_year
from evaluation.reporting.run_manifest import build_evaluation_provenance, dataframe_sha256
from features.pipeline.feature_cache_identity import FEATURE_CACHE_VERSION
from market_data.loading.ticks import TickBook

BASELINE_NAMES = ("always_no_trade", "random_eligible_setup")


def _json_value(value: Any) -> Any:
    """Convert result values into strict JSON primitives.

    Args:
        value: Nested result value that may include pandas, NumPy, or dataclass objects.

    Returns:
        JSON-compatible value with non-finite numbers represented as null.
    """
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _json_value(dataclasses.asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _json_value(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(child) for child in value]
    if isinstance(value, np.ndarray):
        return _json_value(value.tolist())
    if isinstance(value, np.generic):
        return _json_value(value.item())
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if value is pd.NA:
        return None
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def _canonical_sha256(value: Any) -> str:
    """Hash the canonical JSON representation of a value.

    Args:
        value: Value to normalize and encode as canonical JSON.

    Returns:
        Lowercase hexadecimal SHA-256 digest.
    """
    encoded = json.dumps(
        _json_value(value), sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _unknown(reason: str) -> dict[str, str]:
    """Build an explicit unknown-status record with its reason.

    Args:
        reason: Explanation for why the evidence state cannot be established.

    Returns:
        Mapping with ``status`` set to ``unknown`` and the supplied reason.
    """
    return {"status": "unknown", "reason": reason}


def _frame_record(frame: pd.DataFrame) -> dict[str, Any]:
    """Describe a frame's shape, index bounds, and content digest.

    Args:
        frame: DataFrame whose structure and content are recorded.

    Returns:
        Row count, column names, index bounds, and content digest.
    """
    return {
        "rows": int(len(frame)),
        "columns": [str(column) for column in frame.columns],
        "start": str(frame.index.min()) if len(frame) else None,
        "end": str(frame.index.max()) if len(frame) else None,
        "sha256": dataframe_sha256(frame),
    }


def _artifact(
    path: Path,
    root: Path,
    role: str,
    notes: str = "",
    *,
    published_path: Path | None = None,
) -> dict[str, Any]:
    """Describe a persisted artifact and its repository-relative identity.

    Args:
        path: On-disk file whose bytes are hashed.
        root: Repository root used to form a relative artifact path.
        role: Evidence role assigned to this artifact.
        notes: Optional human-readable artifact context.
        published_path: Optional path to publish when storage is staged elsewhere.

    Returns:
        Artifact metadata containing its path, digest, role, and media type.
    """
    relative = (published_path or path).resolve().relative_to(root.resolve()).as_posix()
    record: dict[str, Any] = {
        "path": relative,
        "sha256": file_sha256(path),
        "role": role,
        "storage_scope": "repository",
        "media_type": "application/json" if path.suffix == ".json" else "text/csv",
    }
    if notes:
        record["notes"] = notes
    return record


def _write_frame(frame: pd.DataFrame, path: Path) -> None:
    """Atomically persist a frame using the bundle's canonical CSV format.

    Args:
        frame: Tabular evidence to serialize.
        path: Destination CSV path.
    """
    payload = _frame_csv_bytes(frame)
    write_bytes_atomic(path, payload)


def _frame_csv_bytes(frame: pd.DataFrame) -> bytes:
    """Return the exact deterministic representation persisted for an output frame.

    Args:
        frame: Output evidence frame to serialize.

    Returns:
        UTF-8 CSV bytes with a stable newline convention.
    """
    return frame.to_csv(index=True, lineterminator="\n").encode("utf-8")


def _tickbook_record(tickbook: TickBook | None) -> dict[str, Any] | None:
    """Describe a tickbook by row count and content digest when available.

    Args:
        tickbook: Tick data used by the matched evaluation, if available.

    Returns:
        Tick row count and digest, or ``None`` when no tickbook was supplied.
    """
    if tickbook is None:
        return None
    return {
        "rows": len(tickbook),
        "sha256": tickbook.content_sha256(),
    }


def _paired_interval_record(
    outputs: Mapping[str, Mapping[str, Any]],
    treatment_name: str,
    control_name: str,
    resolved_cfg: Mapping[str, Any],
) -> dict[str, Any]:
    """Build a versioned paired interval record from matched equity paths.

    Args:
        outputs: Completed policy results keyed by policy name.
        treatment_name: Policy whose metrics are compared with the control.
        control_name: Reference policy name for the paired comparison.
        resolved_cfg: Shared resolved account and evaluation configuration.

    Returns:
        Versioned record describing the paired confidence interval estimate.
    """
    treatment_metadata = outputs[treatment_name]["policy_metadata"]
    control_metadata = outputs[control_name]["policy_metadata"]
    treatment_protocol = treatment_metadata.get("confidence_interval_protocol", {})
    control_protocol = control_metadata.get("confidence_interval_protocol", {})
    if treatment_protocol != control_protocol:
        raise ValueError("paired policies must share their bootstrap protocol")
    account = resolved_cfg.get("account", {})
    if not isinstance(account, Mapping) or "initial_balance" not in account:
        raise ValueError("resolved config must declare account.initial_balance")
    equity = outputs[treatment_name]["equity"]
    control_equity = outputs[control_name]["equity"]
    treatment_eval = outputs[treatment_name].get("evaluation", {})
    control_eval = outputs[control_name].get("evaluation", {})
    treatment_policy = outputs[treatment_name]["policy_metadata"]
    control_policy = outputs[control_name]["policy_metadata"]
    step_aligned = (
        not equity.index.equals(control_equity.index)
        and isinstance(treatment_eval, Mapping)
        and isinstance(control_eval, Mapping)
        and treatment_eval.get("n_steps") == control_eval.get("n_steps")
        and treatment_policy.get("evaluation_start") == control_policy.get("evaluation_start")
        and treatment_policy.get("evaluation_end") == control_policy.get("evaluation_end")
        and treatment_policy.get("evaluation_start") is not None
        and treatment_policy.get("evaluation_end") is not None
        and treatment_eval.get("n_steps") == len(equity) - 1 == len(control_equity) - 1
        and treatment_policy.get("input_hashes") == control_policy.get("input_hashes")
    )
    if step_aligned:
        equity = pd.Series(equity.to_numpy(), index=pd.RangeIndex(len(equity)), dtype=float)
        control_equity = pd.Series(
            control_equity.to_numpy(), index=pd.RangeIndex(len(control_equity)), dtype=float
        )
    try:
        paired_observations = _paired_equity_return_observation_count(
            equity,
            control_equity,
            initial_balance=float(account["initial_balance"]),
        )
    except ValueError as exc:
        if "Paired equity indexes" not in str(exc):
            raise
        treatment_index = equity.index
        control_index = control_equity.index
        shared_count = min(len(equity), len(control_equity))
        first_mismatch = next(
            (
                index
                for index in range(shared_count)
                if treatment_index[index] != control_index[index]
            ),
            shared_count,
        )
        treatment_time = (
            treatment_index[first_mismatch].isoformat()
            if first_mismatch < len(treatment_index)
            else "<ended>"
        )
        control_time = (
            control_index[first_mismatch].isoformat()
            if first_mismatch < len(control_index)
            else "<ended>"
        )
        return {
            "schema": "paired_matched_bar_metric_ci_v2",
            "method": "paired_moving_block_bar_return_bootstrap",
            "treatment": treatment_name,
            "control": control_name,
            "paired_return_observations": 0,
            "n_boot": int(treatment_protocol.get("n_boot", 2000)),
            "level": float(treatment_protocol.get("level", 0.95)),
            "seed": int(treatment_protocol.get("seed", 42)),
            "block_length_bars": int(treatment_protocol.get("block_length_bars", 8)),
            "scope": "no paired estimate; policy equity timestamps diverged",
            "difference_direction": "treatment_minus_control",
            "status": "not_estimable",
            "reason": (
                "policy equity timelines do not share an exact prefix at offset "
                f"{first_mismatch}: {treatment_name}={treatment_time}, "
                f"{control_name}={control_time}; available lengths are "
                f"{len(equity)} and {len(control_equity)}"
            ),
            "metrics": {},
        }
    interval_record: dict[str, Any] = {
        "schema": "paired_matched_bar_metric_ci_v2",
        "method": "paired_moving_block_bar_return_bootstrap",
        "treatment": treatment_name,
        "control": control_name,
        "paired_return_observations": int(paired_observations),
        "n_boot": int(treatment_protocol.get("n_boot", 2000)),
        "level": float(treatment_protocol.get("level", 0.95)),
        "seed": int(treatment_protocol.get("seed", 42)),
        "block_length_bars": int(treatment_protocol.get("block_length_bars", 8)),
        "scope": (
            "paired within-trajectory uncertainty over the exact shared environment-step path; "
            "valuation timestamps may differ because execution fills occur within a bar; not "
            "between-seed uncertainty"
        ),
        "difference_direction": "treatment_minus_control",
    }
    if paired_observations < 2:
        interval_record.update(
            {
                "status": "not_estimable",
                "reason": "paired bootstrap requires at least two aligned bar returns",
                "metrics": {},
            }
        )
        return interval_record

    intervals = paired_equity_metric_differences(
        equity,
        control_equity,
        initial_balance=float(account["initial_balance"]),
        periods_per_year=evaluation_periods_per_year(resolved_cfg),
        n_boot=int(treatment_protocol.get("n_boot", 2000)),
        level=float(treatment_protocol.get("level", 0.95)),
        rng_seed=int(treatment_protocol.get("seed", 42)),
        block_len=int(treatment_protocol.get("block_length_bars", 8)),
    )
    interval_record.update({"status": "estimated", "metrics": _json_value(intervals)})
    return interval_record


def write_matched_setup_baseline_bundle(
    outputs: Mapping[str, Mapping[str, Any]],
    cfg: Any,
    bars: pd.DataFrame,
    features: pd.DataFrame,
    tickbook: TickBook | None,
    *,
    output_root: Path,
    artifact_root: Path,
    source_repository: Path,
    config_path: Path,
    protocol_path: str,
    regeneration_command: str,
    symbols: Sequence[str] | None = None,
    timeframes: Sequence[str] | None = None,
    source_files: Mapping[str, Path] | None = None,
) -> Path:
    """Write one content-addressed setup-baseline bundle and a draft manifest v2.

    Raw bars, features, and ticks are never copied into the bundle. Their
    in-memory content hashes and any caller-supplied source-file hashes are
    recorded so the caller can later bind a market-data result to its inputs.
    Existing bundle paths are immutable and cause ``FileExistsError``.

    Args:
        outputs: Completed results for the baseline and candidate policy arms.
        cfg: Resolved configuration shared by all policy arms.
        bars: Market bars used for evaluation.
        features: Feature rows aligned one-to-one with ``bars``.
        tickbook: Optional tick data used to model execution.
        output_root: Directory under ``artifact_root`` for the new bundle.
        artifact_root: Root that owns all generated evidence artifacts.
        source_repository: Repository root containing source config and protocol.
        config_path: Existing source configuration file to record.
        protocol_path: Repository-relative evaluation protocol document.
        regeneration_command: Command that reproduces this bundle.
        symbols: Optional market symbols represented in the evidence.
        timeframes: Optional timeframe labels represented in the evidence.
        source_files: Optional named source files whose hashes bind the inputs.

    Returns:
        Path to the newly written immutable evidence bundle.
    """
    if not outputs:
        raise ValueError("outputs must contain at least one completed policy arm")
    policy_names = tuple(
        name
        for name in (*BASELINE_NAMES, *sorted(set(outputs) - set(BASELINE_NAMES)))
        if name in outputs
    )
    if any(not re.fullmatch(r"[a-z][a-z0-9_]*", name) for name in policy_names):
        raise ValueError("policy output names must be lowercase identifiers")
    if len(bars) != len(features) or not bars.index.equals(features.index):
        raise ValueError("bars and features must have identical rows and timestamps")
    if not config_path.is_file():
        raise FileNotFoundError(f"baseline source config is missing: {config_path}")
    if not protocol_path or not regeneration_command:
        raise ValueError("protocol_path and regeneration_command must be recorded")
    repository_root = source_repository.resolve()
    protocol_file = (repository_root / protocol_path).resolve()
    try:
        relative_protocol_path = protocol_file.relative_to(repository_root).as_posix()
    except ValueError as exc:
        raise ValueError("protocol_path must resolve inside source_repository") from exc
    if not protocol_file.is_file():
        raise FileNotFoundError(f"baseline protocol is missing: {protocol_file}")

    root = artifact_root.resolve()
    output_base = output_root.resolve()
    try:
        output_base.relative_to(root)
    except ValueError as exc:
        raise ValueError("output_root must be inside artifact_root") from exc

    metadata = {name: dict(outputs[name]["policy_metadata"]) for name in policy_names}
    period_roles = {str(metadata[name].get("period_role")) for name in policy_names}
    config_hashes = {str(metadata[name].get("resolved_config_sha256")) for name in policy_names}
    action_schemas = {
        json.dumps(metadata[name].get("action_schema"), sort_keys=True) for name in policy_names
    }
    if len(period_roles) != 1 or len(config_hashes) != 1 or len(action_schemas) != 1:
        raise ValueError(
            "matched policies must share period role, resolved config, and action schema"
        )
    period_role = next(iter(period_roles))
    resolved_config_hash = next(iter(config_hashes))

    source_file_records: dict[str, dict[str, str]] = {}
    for name, path in sorted((source_files or {}).items()):
        if not path.is_file():
            raise FileNotFoundError(f"baseline source file is missing: {path}")
        resolved_path = path.resolve()
        try:
            recorded_path = resolved_path.relative_to(source_repository.resolve()).as_posix()
        except ValueError:
            recorded_path = str(resolved_path)
        source_file_records[name] = {"path": recorded_path, "sha256": file_sha256(path)}

    for name in policy_names:
        if name in BASELINE_NAMES:
            continue
        policy_metadata = metadata[name]
        if policy_metadata.get("policy_source") == "deterministic_rule":
            if any(
                policy_metadata.get(key) is not None
                for key in ("checkpoint_sha256", "checkpoint_source_key")
            ):
                raise ValueError(f"{name} deterministic rule must not claim a checkpoint")
            continue
        if policy_metadata.get("policy_source") != "trained_checkpoint":
            raise ValueError(
                f"{name} must declare a trained checkpoint or deterministic rule source"
            )
        checkpoint_hash = policy_metadata.get("checkpoint_sha256")
        source_key = policy_metadata.get("checkpoint_source_key")
        if not isinstance(checkpoint_hash, str) or not re.fullmatch(
            r"[0-9a-f]{64}", checkpoint_hash
        ):
            raise ValueError(f"{name} must record a SHA-256 checkpoint identity")
        source_record = source_file_records.get(str(source_key))
        if source_record is None or source_record["sha256"] != checkpoint_hash:
            raise ValueError(f"{name} checkpoint hash must match its named source file")

    bars_record = _frame_record(bars)
    features_record = _frame_record(features)
    tickbook_record = _tickbook_record(tickbook)
    recorded_configs = [outputs[name].get("resolved_config") for name in policy_names]
    if any(value is not None for value in recorded_configs):
        if any(value is None for value in recorded_configs):
            raise ValueError("all matched policies must record the effective resolved config")
        if any(
            _canonical_sha256(value) != _canonical_sha256(recorded_configs[0])
            for value in recorded_configs[1:]
        ):
            raise ValueError("matched policies recorded different effective resolved configs")
        resolved_cfg = recorded_configs[0]
    else:
        resolved_cfg = (
            OmegaConf.to_container(cfg, resolve=True) if OmegaConf.is_config(cfg) else cfg
        )
    if _canonical_sha256(resolved_cfg) != resolved_config_hash:
        raise ValueError("recorded effective config does not match its resolved config hash")
    if not isinstance(resolved_cfg, Mapping):
        raise TypeError("resolved config must be a mapping")
    config_digest = file_sha256(config_path)
    input_identity = {
        "period_role": period_role,
        "resolved_config_sha256": resolved_config_hash,
        "config_file": {
            "path": config_path.resolve().relative_to(source_repository.resolve()).as_posix()
            if config_path.resolve().is_relative_to(source_repository.resolve())
            else str(config_path.resolve()),
            "sha256": config_digest,
        },
        "protocol_file": {
            "path": relative_protocol_path,
            "sha256": file_sha256(protocol_file),
        },
        "bars": bars_record,
        "features": features_record,
        "tickbook": tickbook_record,
        "source_files": source_file_records,
    }
    run_identity_seed = {
        "input_identity": input_identity,
        "policy_metadata": metadata,
    }
    provenance = build_evaluation_provenance(source_repository)
    source_record = provenance.get("source", {})
    source_tree_hash = (
        _canonical_sha256(source_record)
        if isinstance(source_record, Mapping) and source_record.get("available")
        else None
    )
    output_identity: dict[str, dict[str, Any]] = {}
    expected_input_hashes = {
        "bars": bars_record["sha256"],
        "features": features_record["sha256"],
        "tickbook": tickbook_record["sha256"] if tickbook_record is not None else None,
    }
    for name in policy_names:
        result = outputs[name]
        policy_metadata = metadata[name]
        if policy_metadata.get("input_hashes") != expected_input_hashes:
            raise ValueError(f"{name} input hashes do not match the supplied baseline inputs")
        decisions = result["decisions"]
        ledger = result["trade_fill_event_ledger"]
        equity = result["equity"]
        confidence_intervals = result.get("confidence_intervals")
        if (
            not isinstance(confidence_intervals, Mapping)
            or confidence_intervals.get("schema") != "within_trajectory_bootstrap_ci_v1"
            or not isinstance(confidence_intervals.get("metrics"), Mapping)
        ):
            raise ValueError(
                f"{name} must include versioned within-trajectory confidence intervals"
            )
        if not isinstance(decisions, pd.DataFrame) or not isinstance(ledger, pd.DataFrame):
            raise TypeError("baseline decisions and event ledger must be DataFrames")
        if isinstance(equity, pd.Series):
            equity_frame = equity.rename("equity").to_frame()
        elif isinstance(equity, pd.DataFrame) and equity.shape[1] == 1:
            equity_frame = equity.copy()
            equity_frame.columns = ["equity"]
        else:
            raise TypeError("baseline equity must be a Series or one-column DataFrame")
        output_identity[name] = {
            "decisions_sha256": hashlib.sha256(_frame_csv_bytes(decisions)).hexdigest(),
            "event_ledger_sha256": hashlib.sha256(_frame_csv_bytes(ledger)).hexdigest(),
            "equity_sha256": hashlib.sha256(_frame_csv_bytes(equity_frame)).hexdigest(),
            "metrics": _json_value(result["metrics"]),
            "confidence_intervals": _json_value(confidence_intervals),
            "evaluation": _json_value(result.get("evaluation", {})),
        }

    paired_comparison_intervals: dict[str, Any] = {}
    if {"always_no_trade", "random_eligible_setup"}.issubset(outputs):
        paired_comparison_intervals["always_flat_vs_random_eligible_setup"] = (
            _paired_interval_record(
                outputs, "always_no_trade", "random_eligible_setup", resolved_cfg
            )
        )
    if "random_eligible_setup" in outputs:
        paired_comparison_intervals.update(
            {
                f"{name}_vs_random_eligible_setup": _paired_interval_record(
                    outputs, name, "random_eligible_setup", resolved_cfg
                )
                for name in policy_names
                if name not in BASELINE_NAMES
            }
        )
    output_identity["paired_comparison_intervals"] = _json_value(paired_comparison_intervals)

    bundle_hash = _canonical_sha256(
        {
            **run_identity_seed,
            "source_tree_hash": source_tree_hash,
            "output_identity": output_identity,
        }
    )
    bundle_id = f"matched_setup_baselines_{bundle_hash[:16]}"
    final_dir = output_base / bundle_id
    if final_dir.exists():
        raise FileExistsError(f"refusing to overwrite immutable baseline bundle: {final_dir}")

    source_identity = {
        **provenance,
        "source_tree_hash": source_tree_hash,
    }

    output_base.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix=f".{bundle_id}.", dir=output_base))
    try:
        resolved_config_path = temp_dir / "resolved_config.json"
        source_identity_path = temp_dir / "source_identity.json"
        input_identity_path = temp_dir / "input_identity.json"
        write_json_atomic(resolved_config_path, _json_value(resolved_cfg), default=None)
        write_json_atomic(source_identity_path, _json_value(source_identity), default=None)
        write_json_atomic(input_identity_path, _json_value(input_identity), default=None)

        runs = []
        comparison_metrics = []
        run_ids = []
        for name in policy_names:
            result = outputs[name]
            policy_metadata = metadata[name]
            run_dir = temp_dir / name
            run_dir.mkdir()
            decisions = result["decisions"]
            ledger = result["trade_fill_event_ledger"]
            equity = result["equity"]
            if not isinstance(decisions, pd.DataFrame) or not isinstance(ledger, pd.DataFrame):
                raise TypeError("baseline decisions and event ledger must be DataFrames")
            if isinstance(equity, pd.Series):
                equity_frame = equity.rename("equity").to_frame()
            elif isinstance(equity, pd.DataFrame) and equity.shape[1] == 1:
                equity_frame = equity.copy()
                equity_frame.columns = ["equity"]
            else:
                raise TypeError("baseline equity must be a Series or one-column DataFrame")
            confidence_intervals = result.get("confidence_intervals")
            if (
                not isinstance(confidence_intervals, Mapping)
                or confidence_intervals.get("schema") != "within_trajectory_bootstrap_ci_v1"
                or not isinstance(confidence_intervals.get("metrics"), Mapping)
            ):
                raise ValueError(
                    f"{name} must include versioned within-trajectory confidence intervals"
                )

            artifact_files = []
            for frame, filename, role in (
                (decisions, "decisions.csv", "decision_trace"),
                (ledger, "trade_fill_event_ledger.csv", "trade_fill_event_ledger"),
                (equity_frame, "equity.csv", "equity_curve"),
            ):
                path = run_dir / filename
                _write_frame(frame, path)
                artifact_files.append(
                    _artifact(
                        path,
                        root,
                        role,
                        published_path=final_dir / path.relative_to(temp_dir),
                    )
                )
            for value, filename, role in (
                (result["metrics"], "metrics.json", "metrics"),
                (confidence_intervals, "confidence_intervals.json", "confidence_intervals"),
                (policy_metadata, "policy_metadata.json", "policy_metadata"),
                (result.get("evaluation", {}), "evaluation.json", "evaluation_metadata"),
            ):
                path = run_dir / filename
                write_json_atomic(path, _json_value(value), default=None)
                artifact_files.append(
                    _artifact(
                        path,
                        root,
                        role,
                        published_path=final_dir / path.relative_to(temp_dir),
                    )
                )

            run_id = f"{bundle_id}/{name}"
            run_ids.append(run_id)
            run_seed = policy_metadata.get("random_policy_seed")
            if run_seed is None:
                run_seed = policy_metadata.get("training_seed")
            if run_seed is None:
                run_seed = policy_metadata.get("policy_action_seed")
            metrics = result["metrics"]
            end_equity = float(equity_frame["equity"].iloc[-1]) if len(equity_frame) else 0.0
            breach_events = result.get("evaluation", {}).get("breach_events", [])
            comparison_metrics.append(
                {
                    "run_id": run_id,
                    "completed_positions": int(metrics.n_trades),
                    "net_return_pct": float(metrics.total_return_pct),
                    "aggregate_end_equity": end_equity,
                    "breach_events": len(breach_events),
                    "survival_gate": "passed" if not breach_events else "failed",
                    "confidence_intervals": _json_value(confidence_intervals),
                }
            )

            runtime = provenance.get("runtime", {})
            source_commit = source_record.get("head") if source_record.get("available") else None
            action_schema = policy_metadata["action_schema"]
            action_version = action_schema.get("version", action_schema.get("schema_version"))
            risk_sizing = policy_metadata.get("risk_sizing", {})
            dataset_hashes = [
                f"bars_dataframe:{bars_record['sha256']}",
                f"features_dataframe:{features_record['sha256']}",
            ]
            if tickbook_record is not None:
                dataset_hashes.append(f"tickbook_arrays:{tickbook_record['sha256']}")
            dataset_hashes.extend(
                f"{key}:{record['sha256']}" for key, record in sorted(source_file_records.items())
            )
            input_unknown = (
                "raw source files were not supplied; only in-memory dataset hashes are available"
            )
            identity = {
                "source_commit": source_commit or _unknown("Git source state was unavailable"),
                "source_tree_hash": source_tree_hash
                or _unknown("Git source tree hash unavailable"),
                "config_file_hash": config_digest,
                "resolved_config_hash": resolved_config_hash,
                "environment_lock_hash": (
                    file_sha256(source_repository / "uv.lock")
                    if (source_repository / "uv.lock").is_file()
                    else _unknown("uv.lock was not available")
                ),
                "python_version": runtime.get("python") or _unknown("Python version unavailable"),
                "cuda_version": policy_metadata.get("cuda_version")
                or _unknown("policy evaluation CUDA version was not recorded"),
                "torch_version": runtime.get("torch") or _unknown("Torch is not installed"),
                "dataset_file_hashes": dataset_hashes,
                "feature_cache_version": FEATURE_CACHE_VERSION,
                "feature_cache_content_hash": features_record["sha256"],
                "split_fold_ids": [f"{period_role}:{bars_record['start']}..{bars_record['end']}"],
                "exposure_roles": [period_role],
                "schema_versions": [
                    f"action:{action_version or _canonical_sha256(action_schema)}",
                    f"feature_cache:{FEATURE_CACHE_VERSION}",
                    "result_manifest:v2",
                ],
                "checkpoint_hash": (
                    str(policy_metadata["checkpoint_sha256"])
                    if policy_metadata.get("checkpoint_sha256") is not None
                    else _unknown("deterministic baseline does not load a checkpoint")
                ),
                "training_seed": (
                    int(policy_metadata["training_seed"])
                    if policy_metadata.get("policy_source") == "trained_checkpoint"
                    and policy_metadata.get("training_seed") is not None
                    else _unknown("deterministic baseline is not trained")
                ),
                "stochastic_eval_seed": (
                    int(policy_metadata["random_policy_seed"])
                    if policy_metadata.get("random_policy_seed") is not None
                    else int(policy_metadata["policy_action_seed"])
                    if policy_metadata.get("policy_action_seed") is not None
                    else _unknown("policy action was evaluated deterministically")
                ),
                "execution_seed": int(policy_metadata["execution_seed"]),
                "training_total_steps": int(policy_metadata.get("training_total_steps", 0)),
                "training_effective_steps": int(policy_metadata.get("training_effective_steps", 0)),
                "n_envs": int(policy_metadata.get("n_envs", 1)),
                "rollout_geometry": "one non-episodic TradingEnv; one action per input bar",
                "action_mode": str(
                    policy_metadata.get("policy_action_mode")
                    or action_version
                    or "trade_setup_action_schema"
                ),
                "symbols": list(symbols)
                if symbols
                else _unknown("symbol identity was not supplied"),
                "timeframes": (
                    list(timeframes)
                    if timeframes
                    else _unknown("timeframe inventory was not supplied")
                ),
                "timezone_session_schedule": _unknown(
                    "input index/session labels are recorded; authoritative timezone/calendar "
                    "semantics were not assessed"
                ),
                "broker_cost_risk_assumptions": [
                    "resolved config SHA-256: " + resolved_config_hash,
                    "risk sizing settings: "
                    + json.dumps(_json_value(risk_sizing), sort_keys=True, separators=(",", ":")),
                    "execution and cost semantics are from the recorded resolved configuration",
                    "period role: " + period_role,
                ],
                "metric_calculator_revision": (
                    f"{METRIC_DEFINITION_VERSION}:"
                    f"{file_sha256(source_repository / 'evaluation/metrics/performance.py')}"
                ),
                "sample_denominators": [
                    f"bars={len(bars)}",
                    f"features={len(features)}",
                    f"decisions={len(decisions)}",
                    f"event_rows={len(ledger)}",
                    f"completed_positions={int(metrics.n_trades)}",
                ],
                "missing_assets": [] if source_file_records else [input_unknown],
                "limitations": [
                    "Draft bundle; no independent rerun or external review is claimed.",
                    "A synthetic period role is implementation validation, not economic evidence.",
                    "Unknown source rights, timestamp authority, and calendar semantics remain unassessed.",
                ],
                "claimed_reproduction_level": (
                    "Draft local reproducibility record; hashes bind in-memory inputs and outputs, "
                    "but raw data are not copied into the bundle."
                ),
                "regeneration_command": regeneration_command,
                "reviewer_check_status": "automated artifact hashes; independent review not performed",
            }
            runs.append(
                {
                    "run_id": run_id,
                    "variant_id": str(policy_metadata["policy_id"]),
                    "seed": int(run_seed or 0),
                    "role": (
                        "control"
                        if name == "always_no_trade"
                        else "randomized_control"
                        if name == "random_eligible_setup"
                        else "deterministic_rule"
                        if policy_metadata.get("policy_source") == "deterministic_rule"
                        else "trained_policy"
                    ),
                    "status": "completed",
                    "identity": identity,
                    "artifacts": artifact_files,
                }
            )

        shared_artifacts = [
            _artifact(
                resolved_config_path,
                root,
                "resolved_config",
                published_path=final_dir / resolved_config_path.relative_to(temp_dir),
            ),
            _artifact(
                source_identity_path,
                root,
                "source_hash_manifest",
                published_path=final_dir / source_identity_path.relative_to(temp_dir),
            ),
            _artifact(
                input_identity_path,
                root,
                "input_identity",
                published_path=final_dir / input_identity_path.relative_to(temp_dir),
            ),
        ]
        manifest = {
            "schema": "qrl.research_result_manifest.v2",
            "manifest_status": "draft",
            "created_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "frozen_at_utc": None,
            "finding_id": "matched_setup_policy_evaluation",
            "research_question": (
                "How do the declared policies behave under one configured evaluation path?"
            ),
            "hypothesis": (
                "The shared evaluator records each policy with explicit action, execution, risk, "
                "period, source, and input identities."
            ),
            "finding_status": "draft_synthetic_contract_validation"
            if period_role == "synthetic"
            else "draft_descriptive_evaluation",
            "evidence_grade": "draft_ungraded",
            "protocol_path": protocol_path,
            "runs": runs,
            "comparisons": (
                [
                    {
                        "comparison_id": "always_flat_vs_random_eligible_setup",
                        "question": "What absolute outcomes do the two Tier 0 controls record?",
                        "run_ids": [
                            f"{bundle_id}/always_no_trade",
                            f"{bundle_id}/random_eligible_setup",
                        ],
                        "evidence_role": period_role,
                        "status": "draft_descriptive",
                        "result": (
                            "Per-policy absolute metrics are recorded below. This bundle does not "
                            "make an inferential, causal, or deployment claim."
                        ),
                        "metrics": [
                            item
                            for item in comparison_metrics
                            if item["run_id"]
                            in {
                                f"{bundle_id}/always_no_trade",
                                f"{bundle_id}/random_eligible_setup",
                            }
                        ],
                        "paired_time_series_intervals": paired_comparison_intervals[
                            "always_flat_vs_random_eligible_setup"
                        ],
                        "limitations": [
                            "Paired time-series intervals are conditional on one evaluation path and action seeds; no between-seed uncertainty is reported.",
                            "Recorded risk controls do not establish matched realized-risk distributions.",
                        ],
                    }
                ]
                if "always_flat_vs_random_eligible_setup" in paired_comparison_intervals
                else []
            )
            + [
                {
                    "comparison_id": f"{name}_vs_random_eligible_setup",
                    "question": f"What absolute outcomes does {name} record relative to the random eligible-setup control?",
                    "run_ids": [f"{bundle_id}/{name}", f"{bundle_id}/random_eligible_setup"],
                    "evidence_role": period_role,
                    "status": "draft_descriptive",
                    "result": (
                        "Per-policy absolute metrics are recorded below. This bundle does not "
                        "make an inferential, causal, or deployment claim."
                    ),
                    "metrics": [
                        item
                        for item in comparison_metrics
                        if item["run_id"]
                        in {f"{bundle_id}/{name}", f"{bundle_id}/random_eligible_setup"}
                    ],
                    "paired_time_series_intervals": paired_comparison_intervals[
                        f"{name}_vs_random_eligible_setup"
                    ],
                    "limitations": [
                        "Paired time-series intervals are conditional on one evaluation path and action seeds; no between-seed uncertainty is reported.",
                        "Recorded risk caps do not establish matched realized-risk distributions.",
                    ],
                }
                for name in policy_names
                if name not in BASELINE_NAMES
                and f"{name}_vs_random_eligible_setup" in paired_comparison_intervals
            ],
            "claims": [],
            "supporting_artifacts": shared_artifacts,
            "limitations": [
                "Raw bars, features, and ticks are not copied into the bundle.",
                "No market-data economic claim is supported by synthetic contract tests.",
                "Provider/license status and authoritative timestamp/session semantics are not assessed.",
            ],
        }
        manifest_path = temp_dir / "result_manifest.json"
        write_json_atomic(manifest_path, manifest, default=None)
        os.rename(temp_dir, final_dir)
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
    return final_dir
