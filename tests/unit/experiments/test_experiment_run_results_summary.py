from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import pytest

from experiments.runs.reporting import (
    _pnl_reconciliation,
    _write_summary_outputs,
    build_summary,
    render_markdown,
)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_experiment_run_summary_reads_metrics_logs_and_legacy_gpu_samples(tmp_path: Path) -> None:
    experiment_run_dir = tmp_path / "experiment_run"
    run_key = "variant__seed42"
    attempt_dir = experiment_run_dir / "runs" / "attempts" / run_key / "attempt1"
    run_dir = attempt_dir / run_key / "20261014_000000_run"
    log_path = experiment_run_dir / "logs" / "workers" / f"{run_key}.log"
    log_path.parent.mkdir(parents=True)
    log_path.write_text(
        "[test/report-only] Sharpe=-0.5 MaxDD=1.00% Trades=2 Return=-0.10% "
        "survived=True days=2/130\n"
        "[train/in-sample] Sharpe=-0.2 MaxDD=2.00% Trades=3 Return=-0.20% "
        "survived=True days=3/259\n",
        encoding="utf-8",
    )
    _write_json(
        experiment_run_dir / "experiment_run.json",
        {
            "created": "2026-10-14T00:00:00+00:00",
            "experiment_run_id": "history-input-study",
            "job_id": "1234",
            "git_sha": "abc",
            "fingerprint": "f" * 64,
            "timesteps": 100_000,
            "data_source": "bundle",
            "n_envs": 64,
            "worker_cpus": 6,
            "worker_gpus_per_node": 2,
            "worker_nodes": ["gpuarm2"],
            "evaluation": {
                "locked_oos_role": "selection_acknowledged",
                "locked_oos_exposure": "previously_inspected_holdout",
            },
            "variant_family": {
                "id": "control_effect",
                "domain": "data",
                "title": "Control effect",
                "comparison_type": "matched",
                "entries": [
                    {
                        "variant": "variant",
                        "label": "B",
                        "role": "treatment",
                        "changed_factors": ["history input"],
                    }
                ],
            },
            "jobs": [
                {
                    "key": run_key,
                    "variant": "variant",
                    "seed": 42,
                    "status": "failed",
                    "exit_code": 1,
                    "failure_reason": "training equity gate failed",
                    "attempts": 1,
                    "log": str(log_path),
                }
            ],
        },
    )
    _write_json(
        experiment_run_dir / "reports" / "experiment_run_status.json",
        {"timestamp": "2026-10-14T01:00:00+00:00", "statuses": {"failed": 1}},
    )
    _write_json(attempt_dir / "attempt_provenance.json", {"run_key": run_key})
    _write_json(
        run_dir / "training" / "metrics.json",
        {"total_return_pct": -0.2, "total_pnl": -200.0, "n_trades": 3},
    )
    _write_json(
        run_dir / "testing" / "metrics.json",
        {
            "total_return_pct": -0.1,
            "total_pnl": -100.0,
            "max_drawdown": 0.01,
            "sharpe": -0.5,
            "profit_factor": 0.8,
            "n_trades": 2,
        },
    )
    _write_json(
        run_dir / "train_equity_gate.json", {"ok": False, "reason": "max_loss_stopped_trading"}
    )
    episode_path = run_dir / "model" / "episode_equity.csv"
    episode_path.parent.mkdir(parents=True)
    episode_path.write_text(
        "environment_index,episode_steps,completed_data_split,episode_end_reason\n"
        "0,99504,true,data_split_end\n"
        "0,21000,false,risk_limit\n"
        "1,99504,true,data_split_end\n",
        encoding="utf-8",
    )
    (run_dir / "config.yaml").write_text(
        "account:\n  currency: USD\n  initial_balance: 100000.0\n", encoding="utf-8"
    )
    for split, equity in (("training", 99_800.0), ("testing", 99_900.0)):
        equity_path = run_dir / split / "equity.csv"
        equity_path.parent.mkdir(parents=True, exist_ok=True)
        equity_path.write_text(",equity\n2026-01-01,100000.0\n2026-01-02," + str(equity) + "\n")

    resource_path = experiment_run_dir / "logs" / "resources_gpuarm2.csv"
    resource_path.parent.mkdir(parents=True, exist_ok=True)
    with resource_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            [
                "timestamp_utc",
                "process_tree_pss_bytes",
                "experiment_run_active",
                "gpu_utilization_pct",
                "gpu_memory_used_mib",
            ]
        )
        writer.writerow(["2026-10-14T00:30:00Z", 1024**3, 1, 70, "30000\n80, 31000"])

    summary = build_summary(experiment_run_dir)
    report = render_markdown(summary)

    job = summary["jobs"][0]
    assert summary["experiment_run_id"] == "history-input-study"
    assert summary["gate_failure_count"] == 1
    assert summary["train_gate_failure_reason_counts"] == {"max_loss_stopped_trading": 1}
    assert summary["test_survived_low_activity_count"] == 1
    assert summary["pnl_reconciliation_counts"] == {
        "verified": 2,
        "mismatch": 0,
        "unavailable": 0,
    }
    assert job["account_currency"] == "USD"
    assert job["train_pnl_reconciliation"]["status"] == "verified"
    assert job["test_pnl_reconciliation"]["equity_delta"] == -100.0
    assert job["evidence_sha256"]["training/equity.csv"] is not None
    assert job["evidence_sha256"]["testing/equity.csv"] is not None
    assert job["evidence_sha256"]["episode_equity.csv"] is not None
    assert job["training_episode_coverage"]["full_split_episode_count"] == 2
    assert job["training_episode_coverage"]["environments_with_full_split_episode"] == 2
    assert summary["training_episode_coverage_summary"]["telemetry_available_runs"] == 1
    assert summary["training_episode_coverage_summary"]["full_split_episode_count"] == 2
    assert job["test_replay_report_only"]["days_traded"] == 2
    assert job["family_id"] == "control_effect"
    assert job["arm_label"] == "B"
    assert "control_effect:B" in report
    assert summary["resource_profiles"][0]["gpu_devices"][1]["mean_utilization_pct"] == 80
    assert "Train survival | Full-year episodes | Envs reached year end" in report
    assert "| variant | failed | 1 — training equity gate failed |" in report
    assert "Completed full-training-split episodes: **2** across **2 environments**" in report
    assert (
        "[episode coverage](../runs/attempts/variant__seed42/attempt1/variant__seed42/20261014_000000_run/model/episode_equity.csv)"
        in report
    )
    assert "PnL (USD)" in report
    assert "[worker log](../logs/workers/variant__seed42.log)" in report
    assert (
        "[run files](../runs/attempts/variant__seed42/attempt1/variant__seed42/20261014_000000_run)"
        in report
    )
    assert "2 verified**, **0 mismatched**, **0 unavailable" in report
    assert "Gate failure reasons (overlapping): `max_loss_stopped_trading` 1/1" in report
    assert "[the source-fidelity audit](source_fidelity_audit.md)" in report
    assert "reconstructed from the sampler's raw two-row" in report


def test_pnl_reconciliation_exposes_saved_equity_mismatch(tmp_path: Path) -> None:
    split_dir = tmp_path / "testing"
    split_dir.mkdir()
    (split_dir / "equity.csv").write_text(",equity\n2026-01-01,100000.0\n2026-01-02,99900.0\n")

    result = _pnl_reconciliation(
        tmp_path,
        "testing",
        {"total_pnl": -101.0},
        100_000.0,
    )

    assert result["status"] == "mismatch"
    assert result["difference"] == 1.0


def test_episode_coverage_reports_missing_and_legacy_telemetry(tmp_path: Path) -> None:
    from experiments.runs.reporting import _episode_coverage

    assert _episode_coverage(None)["status"] == "missing"
    legacy = tmp_path / "legacy.csv"
    legacy.write_text("environment_index,episode_steps\n0,123\n", encoding="utf-8")
    result = _episode_coverage(legacy)
    assert result["status"] == "legacy_schema"
    assert result["full_split_episode_count"] == 0
    assert "completed_data_split" in result["missing_fields"]


def test_episode_coverage_exposes_unknown_and_invalid_rows(tmp_path: Path) -> None:
    from experiments.runs.reporting import _episode_coverage

    path = tmp_path / "episodes.csv"
    path.write_text(
        "environment_index,episode_steps,completed_data_split,episode_end_reason\n"
        "0,100,true,data_split_end\n"
        "1,not-an-int,unknown,unknown\n"
        "bad,20,false,risk_limit\n",
        encoding="utf-8",
    )
    result = _episode_coverage(path)
    assert result["status"] == "available"
    assert result["episode_count"] == 3
    assert result["full_split_episode_count"] == 1
    assert result["completion_unknown_count"] == 1
    assert result["invalid_episode_rows"] == 2


def _minimal_experiment_run(tmp_path: Path, seeds: list[int | None]) -> Path:
    experiment_run_dir = tmp_path / "seed-summary"
    _write_json(
        experiment_run_dir / "experiment_run.json",
        {
            "jobs": [
                {
                    "key": f"variant_{index}",
                    "seed": seed,
                    "attempts": 1,
                }
                for index, seed in enumerate(seeds)
            ]
        },
    )
    _write_json(experiment_run_dir / "reports" / "experiment_run_status.json", {})
    return experiment_run_dir


def test_experiment_run_summary_reports_homogeneous_seed_50(tmp_path: Path) -> None:
    summary = build_summary(_minimal_experiment_run(tmp_path, [50, 50]))
    report = render_markdown(summary)

    assert summary["schema_version"] == 2
    assert summary["seed"] == 50
    assert summary["seeds"] == [50]
    assert summary["seed_metadata_complete"] is True
    assert "seeds 50;" in report


def test_experiment_run_summary_reports_mixed_seed_set_without_scalar_seed(tmp_path: Path) -> None:
    summary = build_summary(_minimal_experiment_run(tmp_path, [42, 50, 42]))
    report = render_markdown(summary)

    assert summary["seed"] is None
    assert summary["seeds"] == [42, 50]
    assert summary["seed_metadata_complete"] is True
    assert "seeds 42, 50;" in report


def test_experiment_run_summary_marks_missing_seed_metadata_incomplete(tmp_path: Path) -> None:
    summary = build_summary(_minimal_experiment_run(tmp_path, [50, None]))
    report = render_markdown(summary)

    assert summary["seed"] is None
    assert summary["seeds"] == [50]
    assert summary["seed_metadata_complete"] is False
    assert "seeds 50 (incomplete metadata);" in report


def test_experiment_run_summary_writer_preserves_existing_artifacts(tmp_path: Path) -> None:
    stem = tmp_path / "reports" / "summary"
    stem.parent.mkdir()
    json_path = stem.with_suffix(".json")
    markdown_path = stem.with_suffix(".md")
    json_path.write_text("original-json", encoding="utf-8")
    markdown_path.write_text("original-markdown", encoding="utf-8")

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        _write_summary_outputs({"schema_version": 2}, stem)

    assert json_path.read_text(encoding="utf-8") == "original-json"
    assert markdown_path.read_text(encoding="utf-8") == "original-markdown"


def test_experiment_run_summary_writes_groupable_csv(tmp_path: Path) -> None:
    stem = tmp_path / "reports" / "summary"
    _write_summary_outputs(
        {
            "schema_version": 2,
            "experiment_run_id": "history-input-study",
            "experiment_run_git_sha": "a" * 40,
            "experiment_run_fingerprint": "b" * 64,
            "experiment_run_manifest_sha256": "c" * 64,
            "data_identity_sha256": "d" * 64,
            "data_source": "frames",
            "requested_steps_per_variant": 2_000_000,
            "n_envs": 8,
            "evaluation_protocol": {"locked_oos_role": "report_only"},
            "jobs": [
                {
                    "family_id": "data_history",
                    "domain": "data",
                    "family_title": "Historical inputs",
                    "comparison_type": "matched",
                    "variant": "history_arm",
                    "arm_label": "B",
                    "arm_role": "treatment",
                    "changed_factors": ["history input"],
                    "run_key": "history_arm__seed42",
                    "seed": 42,
                    "controller_status": "failed",
                    "failure_reason": "risk limit reached",
                    "train_metrics": {"total_pnl": -100.0},
                    "test_metrics_report_only": None,
                    "test_replay_report_only": {},
                    "train_pnl_reconciliation": {"status": "verified"},
                    "test_pnl_reconciliation": {"status": "unavailable"},
                    "family_memberships": [
                        {
                            "family_id": "data_history",
                            "domain": "data",
                            "family_title": "Historical inputs",
                            "comparison_type": "matched",
                            "arm_label": "B",
                            "arm_role": "treatment",
                            "changed_factors": ["history input"],
                        },
                        {
                            "family_id": "risk_controls",
                            "domain": "trading",
                            "family_title": "Risk controls",
                            "comparison_type": "matched",
                            "arm_label": "C",
                            "arm_role": "treatment",
                            "changed_factors": ["risk limit"],
                        },
                    ],
                }
            ],
        },
        stem,
    )

    with stem.with_suffix(".csv").open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 2
    assert {row["domain"] for row in rows} == {"data", "trading"}
    assert {row["family_id"] for row in rows} == {"data_history", "risk_controls"}
    assert {row["changed_factors"] for row in rows} == {"history input", "risk limit"}
    row = rows[0]
    assert row["experiment_run_id"] == "history-input-study"
    assert row["requested_steps_per_variant"] == "2000000"
    assert row["n_envs"] == "8"
    assert row["family_id"] == "data_history"
    assert row["domain"] == "data"
    assert row["changed_factors"] == "history input"
    assert row["controller_status"] == "failed"
    assert row["train_pnl"] == "-100.0"
    assert json.loads(row["train_pnl_reconciliation"]) == {"status": "verified"}


def test_summary_falls_back_from_escaped_log_and_preserves_missing_worker_evidence(
    tmp_path: Path,
) -> None:
    experiment_run_dir = tmp_path / "summary-fallback"
    run_key = "variant__seed7"
    attempt_dir = experiment_run_dir / "runs" / "attempts" / run_key / "attempt1"
    run_dir = attempt_dir / run_key / "20261101_000000_run"
    _write_json(
        experiment_run_dir / "experiment_run.json",
        {
            "experiment_run_id": "summary-fallback",
            "jobs": [
                {
                    "key": run_key,
                    "variant": "variant",
                    "seed": 7,
                    "status": "failed",
                    "exit_code": 1,
                    "failure_reason": "worker failed after writing partial evidence",
                    "attempts": 1,
                    "log": "../outside.log",
                },
                {
                    "key": "not_started__seed11",
                    "variant": "not_started",
                    "seed": 11,
                    "status": "pending",
                    "attempts": 0,
                },
            ],
        },
    )
    _write_json(experiment_run_dir / "reports" / "experiment_run_status.json", {})
    (run_dir / "training").mkdir(parents=True)
    (run_dir / "training" / "metrics.json").write_text("{invalid json", encoding="utf-8")
    (run_dir / "config.yaml").write_text("account: [invalid yaml", encoding="utf-8")

    outside_log = tmp_path / "outside.log"
    outside_log.write_text("[test] survived=False days=0/10\n", encoding="utf-8")
    fallback_log = experiment_run_dir / "logs" / "workers" / f"{run_key}.log"
    fallback_log.parent.mkdir(parents=True)
    fallback_log.write_text(
        "[test/report-only] Sharpe=0.5 MaxDD=1.00% Trades=1 Return=0.10% survived=True days=4/10\n",
        encoding="utf-8",
    )

    summary = build_summary(experiment_run_dir)
    report = render_markdown(summary)

    failed_job, pending_job = summary["jobs"]
    assert failed_job["worker_log"] == "logs/workers/variant__seed7.log"
    assert failed_job["test_replay_report_only"] == {
        "survived_full_period": True,
        "days_traded": 4,
        "days_total": 10,
    }
    assert failed_job["train_metrics"] is None
    assert failed_job["account_currency"] is None
    assert failed_job["train_pnl_reconciliation"]["status"] == "unavailable"
    assert failed_job["evidence_sha256"]["training/metrics.json"] is not None
    assert pending_job["attempt"] == 0
    assert pending_job["run_artifact_dir"] is None
    assert "yes / 4/10" in report
    assert "worker failed after writing partial evidence" in report


@pytest.mark.parametrize(
    ("manifest_payload", "status_payload"),
    [
        (None, {}),
        ({"jobs": []}, None),
        ([], {}),
        ({"jobs": []}, "not-an-object"),
    ],
)
def test_summary_requires_readable_manifest_and_status_objects(
    tmp_path: Path,
    manifest_payload: Any,
    status_payload: Any,
) -> None:
    experiment_run_dir = tmp_path / "incomplete-summary"
    if manifest_payload is not None:
        _write_json(experiment_run_dir / "experiment_run.json", manifest_payload)
    if status_payload is not None:
        _write_json(experiment_run_dir / "reports" / "experiment_run_status.json", status_payload)

    with pytest.raises(
        ValueError, match="experiment_run.json and reports/experiment_run_status.json are required"
    ):
        build_summary(experiment_run_dir)


def test_summary_skips_malformed_records_and_preserves_partial_job_evidence(tmp_path: Path) -> None:
    experiment_run_dir = tmp_path / "malformed-partial-summary"
    _write_json(
        experiment_run_dir / "experiment_run.json",
        {
            "comparison_families": [
                None,
                {
                    "id": "family",
                    "domain": "data",
                    "title": "History inputs",
                    "comparison_type": "matched",
                    "entries": [
                        "malformed-arm",
                        {
                            "variant": "partial",
                            "label": "B",
                            "role": "treatment",
                            "changed_factors": ["history input"],
                        },
                    ],
                },
            ],
            "jobs": [
                None,
                ["not", "a", "job"],
                {"key": ""},
                {
                    "key": "not-started",
                    "variant": "not-started",
                    "attempts": 0,
                    "seed": 42,
                    "status": "pending",
                },
                {
                    "key": "partial__seed-unknown",
                    "variant": "partial",
                    "attempts": 1,
                    "seed": "unknown",
                    "status": "failed",
                    "failure_reason": "worker exited before saving metrics",
                },
            ],
        },
    )
    _write_json(experiment_run_dir / "reports" / "experiment_run_status.json", {})

    summary = build_summary(experiment_run_dir)
    report = render_markdown(summary)

    assert [job["run_key"] for job in summary["jobs"]] == [
        "not-started",
        "partial__seed-unknown",
    ]
    assert summary["seed"] is None
    assert summary["seeds"] == [42]
    assert summary["seed_metadata_complete"] is False
    pending, partial = summary["jobs"]
    assert pending["attempt"] == 0
    assert pending["run_artifact_dir"] is None
    assert partial["family_id"] == "family"
    assert partial["arm_label"] == "B"
    assert partial["family_memberships"][0]["changed_factors"] == ["history input"]
    assert partial["train_metrics"] is None
    assert partial["test_metrics_report_only"] is None
    assert partial["training_episode_coverage"]["status"] == "missing"
    assert partial["evidence_sha256"]["training/metrics.json"] is None
    assert partial["evidence_sha256"]["attempt_provenance.json"] is None
    assert partial["run_artifact_dir"] is None
    assert "worker exited before saving metrics" in report
    assert "family:B" in report
