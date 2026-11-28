#!/usr/bin/env python3
"""Create a checksummed, non-ranking report from an experiment run's saved run metrics."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

from artifacts.layout import ExperimentRunArtifactLayout
from experiments.runs.summary_rendering import (
    _family_metadata,
)
from experiments.runs.summary_rendering import (
    _write_summary_outputs as _write_summary_outputs,
)
from experiments.runs.summary_rendering import (
    render_markdown as render_markdown,  # noqa: F401 - retained as a public reporting helper
)


def _read_json(path: Path) -> dict[str, Any] | None:
    """Read json.

    Args:
        path: Path to the input file or directory.

    Returns:
        Mapping from ``str`` keys to ``Any`` values.
    """
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _sha256(path: Path) -> str | None:
    """Process the requested value.

    Args:
        path: Path to the input file or directory.

    Returns:
        Result of process the requested value.
    """
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def _run_dir(attempt_dir: Path, run_key: str) -> Path | None:
    """Run dir.

    Args:
        attempt_dir: Text or path value identifying the attempt dir.
        run_key: Text or path value identifying the run key.

    Returns:
        Path returned by ``_run_dir``.
    """
    candidates = sorted(
        (path for path in (attempt_dir / run_key).glob("*") if path.is_dir()),
        key=lambda path: path.name,
    )
    return candidates[-1] if candidates else None


def _account_currency(run_dir: Path | None) -> str | None:
    """Process currency.

    Args:
        run_dir: Run dir used by the operation described above.

    Returns:
        Result of process currency.
    """
    currency, _ = _account_config(run_dir)
    return currency


def _account_config(run_dir: Path | None) -> tuple[str | None, float | None]:
    """Process config.

    Args:
        run_dir: Run dir used by the operation described above.

    Returns:
        Values returned by ``_account_config``, in the declared order.
    """
    if run_dir is None:
        return None, None
    try:
        config = yaml.safe_load((run_dir / "config.yaml").read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None, None
    account = config.get("account") if isinstance(config, dict) else None
    if not isinstance(account, dict):
        return None, None
    currency = account.get("currency") if isinstance(account, dict) else None
    initial = account.get("initial_balance")
    try:
        initial_balance = float(initial) if initial is not None else None
    except (TypeError, ValueError):
        initial_balance = None
    return (str(currency) if currency is not None else None), initial_balance


def _pnl_reconciliation(
    run_dir: Path | None,
    split: str,
    metrics: dict[str, Any] | None,
    initial_balance: float | None,
) -> dict[str, Any]:
    """Check saved split PnL against its final equity value.

    Args:
        run_dir: Run dir used by the operation described above.
        split: Text or path value identifying the split.
        metrics: Key-value data used for the metrics.
        initial_balance: Initial balance used by the operation described above.

    Returns:
        Mapping from ``str`` keys to ``Any`` values.
    """
    result: dict[str, Any] = {
        "status": "unavailable",
        "initial_balance": initial_balance,
        "final_equity": None,
        "equity_delta": None,
        "reported_total_pnl": None,
        "difference": None,
        "tolerance": 0.02,
    }
    if run_dir is None or metrics is None or initial_balance is None:
        return result
    try:
        with (run_dir / split / "equity.csv").open(newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
        if not rows:
            return result
        final_equity = float(rows[-1]["equity"])
        reported_pnl = float(metrics["total_pnl"])
    except (OSError, csv.Error, KeyError, TypeError, ValueError, IndexError):
        return result
    if not math.isfinite(final_equity) or not math.isfinite(reported_pnl):
        return result
    equity_delta = final_equity - initial_balance
    difference = equity_delta - reported_pnl
    result.update(
        final_equity=final_equity,
        equity_delta=equity_delta,
        reported_total_pnl=reported_pnl,
        difference=difference,
        status="verified" if abs(difference) <= result["tolerance"] else "mismatch",
    )
    return result


def _resource_profiles(experiment_run_dir: Path) -> list[dict[str, Any]]:
    """Process profiles.

    Args:
        experiment_run_dir: Text or path value identifying the experiment run dir.

    Returns:
        Mapping from ``str`` keys to ``Any]`` values.
    """
    profiles: list[dict[str, Any]] = []
    artifacts = ExperimentRunArtifactLayout(experiment_run_dir)
    for path in sorted(artifacts.logs.glob("resources_*.csv")):
        try:
            with path.open(newline="", encoding="utf-8") as stream:
                reader = csv.DictReader(stream)
                rows = list(reader)
                header = set(reader.fieldnames or ())
        except OSError:
            continue
        active = [row for row in rows if row.get("experiment_run_active") == "1"]
        pss_values = []
        for row in active:
            try:
                pss_values.append(int(row["process_tree_pss_bytes"]))
            except (KeyError, ValueError, TypeError):
                continue
        gpu_util: list[list[int]] = [[], []]
        gpu_mem: list[list[int]] = [[], []]
        for row in active:
            parsed: list[tuple[int, int]] = []
            if "gpu_utilization_pct_by_device" in header:
                try:
                    utils = json.loads(row.get("gpu_utilization_pct_by_device", "[]"))
                    memories = json.loads(row.get("gpu_memory_used_mib_by_device", "[]"))
                    parsed = [(int(u), int(m)) for u, m in zip(utils, memories, strict=False)]
                except (ValueError, TypeError):
                    parsed = []
            elif "gpu_utilization_pct" in header and "gpu_memory_used_mib" in header:
                combined = (
                    row.get("gpu_utilization_pct", "") + "," + row.get("gpu_memory_used_mib", "")
                )
                for line in combined.splitlines():
                    fields = [field.strip() for field in line.split(",")]
                    if len(fields) == 2:
                        try:
                            parsed.append((int(fields[0]), int(fields[1])))
                        except ValueError:
                            continue
            if len(parsed) == 2:
                for index, (util, memory) in enumerate(parsed):
                    gpu_util[index].append(util)
                    gpu_mem[index].append(memory)
        profiles.append(
            {
                "resource_csv": str(path.relative_to(experiment_run_dir)),
                "sha256": _sha256(path),
                "sample_count": len(rows),
                "active_sample_count": len(active),
                "first_timestamp_utc": rows[0].get("timestamp_utc") if rows else None,
                "last_timestamp_utc": rows[-1].get("timestamp_utc") if rows else None,
                "last_experiment_run_active": rows[-1].get("experiment_run_active")
                if rows
                else None,
                "active_process_tree_pss_mean_gib": (
                    sum(pss_values) / len(pss_values) / (1024**3) if pss_values else None
                ),
                "active_process_tree_pss_peak_gib": (
                    max(pss_values) / (1024**3) if pss_values else None
                ),
                "gpu_samples_are_reconstructed_from_raw_rows": (
                    "gpu_utilization_pct_by_device" not in header
                ),
                "gpu_devices": [
                    {
                        "device_index": index,
                        "mean_utilization_pct": (
                            sum(gpu_util[index]) / len(gpu_util[index]) if gpu_util[index] else None
                        ),
                        "peak_utilization_pct": max(gpu_util[index]) if gpu_util[index] else None,
                        "mean_memory_used_mib": (
                            sum(gpu_mem[index]) / len(gpu_mem[index]) if gpu_mem[index] else None
                        ),
                        "peak_memory_used_mib": max(gpu_mem[index]) if gpu_mem[index] else None,
                        "sample_count": len(gpu_util[index]),
                    }
                    for index in range(2)
                ],
                "process_tree_cpu_time_sampled": "process_tree_cpu_time_usec" in header,
                "allocation_cgroup_scope_sampled": "cgroup_memory_scope" in header,
            }
        )
    return profiles


def _split_log(log_path: Path, label: str) -> dict[str, Any]:
    """Split log.

    Args:
        log_path: Path or filename identifying the log.
        label: Text or path value identifying the label.

    Returns:
        Mapping from ``str`` keys to ``Any`` values.
    """
    result: dict[str, Any] = {"survived_full_period": None, "days_traded": None, "days_total": None}
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return result
    pattern = re.compile(
        rf"\[{re.escape(label)}(?:/[^\]]+)?\].*?survived=(True|False)\s+days=(\d+)/(\d+)"
    )
    for line in reversed(lines):
        match = pattern.search(line)
        if match:
            result = {
                "survived_full_period": match.group(1) == "True",
                "days_traded": int(match.group(2)),
                "days_total": int(match.group(3)),
            }
            break
    return result


def _episode_coverage(path: Path | None) -> dict[str, Any]:
    """Summarize training episode completion telemetry without inferring missing rows.

    Args:
        path: Path to the input file or directory.

    Returns:
        Mapping from ``str`` keys to ``Any`` values.
    """
    result: dict[str, Any] = {
        "status": "missing",
        "artifact": str(path) if path is not None else None,
        "sha256": _sha256(path) if path is not None else None,
        "episode_count": 0,
        "full_split_episode_count": 0,
        "environments_with_full_split_episode": 0,
        "completion_unknown_count": 0,
        "invalid_episode_rows": 0,
        "per_environment": [],
    }
    if path is None or not path.is_file():
        return result
    try:
        with path.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            fields = set(reader.fieldnames or ())
            required = {
                "environment_index",
                "episode_steps",
                "completed_data_split",
                "episode_end_reason",
            }
            missing_fields = sorted(required - fields)
            if missing_fields:
                result.update(status="legacy_schema", missing_fields=missing_fields)
                return result
            rows = list(reader)
    except (OSError, csv.Error):
        result["status"] = "unreadable"
        return result

    environments: dict[int, dict[str, Any]] = {}
    unknown_completion = 0
    invalid_rows = 0
    full_split_episodes = 0
    for row in rows:
        try:
            env_index = int(row["environment_index"])
        except (KeyError, TypeError, ValueError):
            invalid_rows += 1
            continue
        coverage = environments.setdefault(
            env_index,
            {"episode_count": 0, "full_split_episode_count": 0, "max_episode_steps": None},
        )
        coverage["episode_count"] += 1
        try:
            episode_steps = int(row["episode_steps"])
        except (KeyError, TypeError, ValueError):
            episode_steps = None
            invalid_rows += 1
        if episode_steps is not None:
            current_max = coverage["max_episode_steps"]
            coverage["max_episode_steps"] = (
                episode_steps if current_max is None else max(current_max, episode_steps)
            )
        completed = str(row.get("completed_data_split", "")).strip().lower()
        if completed in {"true", "1", "yes"}:
            full_split_episodes += 1
            coverage["full_split_episode_count"] += 1
        elif completed not in {"false", "0", "no"}:
            unknown_completion += 1

    result.update(
        status="available",
        episode_count=len(rows),
        full_split_episode_count=full_split_episodes,
        environments_with_full_split_episode=sum(
            item["full_split_episode_count"] > 0 for item in environments.values()
        ),
        completion_unknown_count=unknown_completion,
        invalid_episode_rows=invalid_rows,
        per_environment=[
            {"environment_index": index, **values} for index, values in sorted(environments.items())
        ],
    )
    return result


def _finite_metrics(value: dict[str, Any] | None) -> dict[str, Any] | None:
    """Process metrics.

    Args:
        value: Value to process.

    Returns:
        Mapping from ``str`` keys to ``Any`` values.
    """
    if value is None:
        return None
    cleaned: dict[str, Any] = {}
    for key, item in value.items():
        if isinstance(item, float) and not math.isfinite(item):
            cleaned[key] = None
        else:
            cleaned[key] = item
    return cleaned


def build_summary(experiment_run_dir: Path) -> dict[str, Any]:
    """Join controller and worker artifacts into an evidence-preserving summary.

    Args:
        experiment_run_dir: Run directory containing manifest and status reports.

    Returns:
        Per-job controller, worker, evaluation, and artifact summary.
    """
    artifacts = ExperimentRunArtifactLayout(experiment_run_dir)
    experiment_run = _read_json(artifacts.manifest)
    status = _read_json(artifacts.report("experiment_run_status.json"))
    if experiment_run is None or status is None:
        raise ValueError("experiment_run.json and reports/experiment_run_status.json are required")

    families = experiment_run.get("comparison_families")
    if not isinstance(families, list):
        legacy_family = experiment_run.get("variant_family")
        families = [legacy_family] if isinstance(legacy_family, dict) else []
    families = [family for family in families if isinstance(family, dict)]
    arms: dict[str, list[dict[str, Any]]] = {}
    for family in families:
        for arm in family.get("entries", []):
            if isinstance(arm, dict):
                arms.setdefault(str(arm.get("variant")), []).append(_family_metadata(family, arm))
    jobs: list[dict[str, Any]] = []
    for job in experiment_run.get("jobs", []):
        if not isinstance(job, dict):
            continue
        run_key = str(job.get("key", ""))
        if not run_key:
            continue
        attempt_number = int(job.get("attempts", 0))
        memberships = arms.get(str(job.get("variant")), [])
        family_fields = memberships[0] if len(memberships) == 1 else {}
        if attempt_number <= 0:
            jobs.append(
                {
                    "run_key": run_key,
                    "variant": job.get("variant"),
                    **family_fields,
                    "family_memberships": memberships,
                    "seed": job.get("seed"),
                    "controller_status": job.get("status"),
                    "exit_code": job.get("exit_code"),
                    "failure_reason": job.get("failure_reason"),
                    "attempt": 0,
                    "account_currency": None,
                    "train_pnl_reconciliation": {"status": "unavailable"},
                    "test_pnl_reconciliation": {"status": "unavailable"},
                    "train_equity_gate": None,
                    "training_episode_coverage": {
                        "status": "unavailable",
                        "full_split_episode_count": 0,
                        "environments_with_full_split_episode": 0,
                    },
                    "train_metrics": None,
                    "test_metrics_report_only": None,
                    "train_replay": {},
                    "test_replay_report_only": {},
                    "evidence_sha256": {},
                    "run_artifact_dir": None,
                    "worker_log": None,
                }
            )
            continue
        attempt_dir = artifacts.attempt(run_key, attempt_number)
        run_dir = _run_dir(attempt_dir, run_key)
        episode_candidates = (
            (run_dir / "model" / "episode_equity.csv", run_dir / "episode_equity.csv")
            if run_dir
            else ()
        )
        episode_path = next((path for path in episode_candidates if path.is_file()), None)
        episode_coverage = _episode_coverage(episode_path)
        if episode_path is not None:
            episode_coverage["artifact"] = episode_path.relative_to(experiment_run_dir).as_posix()
        train_path = run_dir / "training" / "metrics.json" if run_dir else Path()
        test_path = run_dir / "testing" / "metrics.json" if run_dir else Path()
        gate_path = run_dir / "train_equity_gate.json" if run_dir else Path()
        train_metrics = _read_json(train_path) if run_dir else None
        test_metrics = _read_json(test_path) if run_dir else None
        gate = _read_json(gate_path) if run_dir else None
        account_currency, initial_balance = _account_config(run_dir)
        try:
            log_path = artifacts.resolve_recorded_path(str(job.get("log", "")))
        except ValueError:
            log_path = artifacts.worker_log(run_key, attempt_number)
        if not log_path.is_file():
            log_path = artifacts.logs / "workers" / f"{run_key}.log"
        job_report = {
            "run_key": run_key,
            "variant": job.get("variant"),
            **family_fields,
            "family_memberships": memberships,
            "seed": job.get("seed"),
            "controller_status": job.get("status"),
            "exit_code": job.get("exit_code"),
            "failure_reason": job.get("failure_reason"),
            "attempt": attempt_number,
            "account_currency": account_currency,
            "train_pnl_reconciliation": _pnl_reconciliation(
                run_dir, "training", train_metrics, initial_balance
            ),
            "test_pnl_reconciliation": _pnl_reconciliation(
                run_dir, "testing", test_metrics, initial_balance
            ),
            "train_equity_gate": gate,
            "training_episode_coverage": episode_coverage,
            "train_metrics": _finite_metrics(train_metrics),
            "test_metrics_report_only": _finite_metrics(test_metrics),
            "train_replay": _split_log(log_path, "train"),
            "test_replay_report_only": _split_log(log_path, "test"),
            "evidence_sha256": {
                "attempt_provenance.json": _sha256(attempt_dir / "attempt_provenance.json"),
                "training/metrics.json": _sha256(train_path) if run_dir else None,
                "training/equity.csv": _sha256(run_dir / "training" / "equity.csv")
                if run_dir
                else None,
                "testing/metrics.json": _sha256(test_path) if run_dir else None,
                "testing/equity.csv": _sha256(run_dir / "testing" / "equity.csv")
                if run_dir
                else None,
                "train_equity_gate.json": _sha256(gate_path) if run_dir else None,
                "episode_equity.csv": _sha256(episode_path) if episode_path else None,
                "worker_log": _sha256(log_path),
            },
            "run_artifact_dir": str(run_dir.relative_to(experiment_run_dir)) if run_dir else None,
            "worker_log": str(log_path.relative_to(experiment_run_dir))
            if log_path.is_relative_to(experiment_run_dir)
            else str(log_path),
        }
        jobs.append(job_report)

    evaluation = experiment_run.get("evaluation", {})
    counts = status.get("statuses", {})
    train_gate_failures = sum(
        item.get("train_equity_gate", {}).get("ok") is False
        for item in jobs
        if isinstance(item.get("train_equity_gate"), dict)
    )
    train_gate_reason_counts: Counter[str] = Counter()
    for item in jobs:
        gate = item.get("train_equity_gate")
        if not isinstance(gate, dict) or gate.get("ok") is not False:
            continue
        reasons = [part.strip() for part in str(gate.get("reason") or "unspecified").split(",")]
        train_gate_reason_counts.update(reason for reason in reasons if reason)
    test_not_survived = sum(
        item.get("test_replay_report_only", {}).get("survived_full_period") is False
        for item in jobs
    )
    test_low_activity = sum(
        item.get("test_replay_report_only", {}).get("survived_full_period") is True
        and isinstance(item.get("test_metrics_report_only"), dict)
        and int(item["test_metrics_report_only"].get("n_trades", 0)) <= 2
        for item in jobs
    )
    pnl_reconciliation_counts = {
        "verified": 0,
        "mismatch": 0,
        "unavailable": 0,
    }
    for item in jobs:
        for key in ("train_pnl_reconciliation", "test_pnl_reconciliation"):
            status_value = item[key]["status"]
            pnl_reconciliation_counts[status_value] += 1
    episode_coverage_summary = {
        "telemetry_available_runs": sum(
            item["training_episode_coverage"]["status"] == "available" for item in jobs
        ),
        "telemetry_unavailable_runs": sum(
            item["training_episode_coverage"]["status"] != "available" for item in jobs
        ),
        "full_split_episode_count": sum(
            item["training_episode_coverage"]["full_split_episode_count"] for item in jobs
        ),
        "environments_with_full_split_episode": sum(
            item["training_episode_coverage"]["environments_with_full_split_episode"]
            for item in jobs
        ),
    }
    declared_seed_values = [item.get("seed") for item in jobs]
    declared_seeds = sorted(
        {
            value
            for value in declared_seed_values
            if isinstance(value, int) and not isinstance(value, bool)
        }
    )
    seed_metadata_complete = bool(jobs) and all(
        isinstance(value, int) and not isinstance(value, bool) for value in declared_seed_values
    )
    homogeneous_seed = (
        declared_seeds[0] if seed_metadata_complete and len(declared_seeds) == 1 else None
    )

    return {
        "schema_version": 2,
        "experiment_run_dir": str(experiment_run_dir),
        "experiment_run_created_utc": experiment_run.get("created"),
        "experiment_run_id": experiment_run.get("experiment_run_id")
        or Path(str(experiment_run_dir)).name,
        "experiment_run_job_id": experiment_run.get("job_id"),
        "experiment_run_git_sha": experiment_run.get("git_sha"),
        "experiment_run_fingerprint": experiment_run.get("fingerprint"),
        "data_identity_sha256": hashlib.sha256(
            json.dumps(experiment_run.get("data_inputs", {}), sort_keys=True).encode()
        ).hexdigest(),
        "requested_steps_per_variant": experiment_run.get("timesteps"),
        "seed": homogeneous_seed,
        "seeds": declared_seeds,
        "seed_metadata_complete": seed_metadata_complete,
        "data_source": experiment_run.get("data_source"),
        "n_envs": experiment_run.get("n_envs"),
        "worker_cpus": experiment_run.get("worker_cpus"),
        "worker_gpus_per_node": experiment_run.get("worker_gpus_per_node"),
        "worker_nodes": experiment_run.get("worker_nodes"),
        "evaluation_protocol": evaluation,
        "variant_family": families[0] if len(families) == 1 else None,
        "comparison_families": families,
        "controller_status_as_of_utc": status.get("timestamp"),
        "controller_status_counts": counts,
        "resource_profiles": _resource_profiles(experiment_run_dir),
        "gate_failure_count": train_gate_failures,
        "train_gate_failure_reason_counts": dict(sorted(train_gate_reason_counts.items())),
        "test_non_survival_count": test_not_survived,
        "test_survived_low_activity_count": test_low_activity,
        "pnl_reconciliation_counts": pnl_reconciliation_counts,
        "training_episode_coverage_summary": episode_coverage_summary,
        "experiment_run_manifest_sha256": _sha256(artifacts.manifest),
        "controller_status_sha256": _sha256(artifacts.report("experiment_run_status.json")),
        "summary_script_sha256": _sha256(Path(__file__).resolve()),
        "jobs": jobs,
    }


def main() -> int:
    """Write JSON and Markdown result snapshots for an experiment run.

    Returns:
        Numeric result returned by ``main``.
    """
    parser = argparse.ArgumentParser(description="Summarize a multi-variant experiment run.")
    parser.add_argument("--experiment-run-dir", type=Path, required=True)
    parser.add_argument("--out-stem", type=Path, default=None)
    args = parser.parse_args()
    experiment_run_dir = args.experiment_run_dir.resolve()
    out_stem = args.out_stem or ExperimentRunArtifactLayout(experiment_run_dir).report(
        "experiment_run_results_summary"
    )
    summary = build_summary(experiment_run_dir)
    markdown_path, json_path, csv_path = _write_summary_outputs(summary, out_stem)
    print(markdown_path)
    print(json_path)
    print(csv_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
