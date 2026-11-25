from __future__ import annotations

import csv
import datetime as dt
import json
import os
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

import pytest

import experiments.runs.status as status_report
from experiments.runs.status import (
    elapsed_for_job,
    estimate_remaining_seconds,
    logged_steps,
    recent_fps,
)


def test_running_attempt_elapsed_ignores_prior_attempt_end_time() -> None:
    timezone = ZoneInfo("Europe/Helsinki")
    now = dt.datetime.fromisoformat("2026-10-19T12:31:44+00:00").astimezone(timezone)

    assert (
        elapsed_for_job(
            "2026-10-19T12:31:24+00:00",
            "2026-10-19T12:22:21+00:00",
            "running",
            now,
            timezone,
        )
        == "0:00:20"
    )


def test_recent_fps_uses_median_of_last_five_samples(tmp_path: Path) -> None:
    log = tmp_path / "worker.log"
    log.write_text(
        "\n".join(f"| fps | {value} |" for value in (100, 200, 300, 400, 500, 600)),
        encoding="utf-8",
    )

    assert recent_fps(log) == (400.0, 5)


def test_recent_fps_reports_available_sample_count(tmp_path: Path) -> None:
    log = tmp_path / "worker.log"
    log.write_text("| fps | 750 |\n", encoding="utf-8")

    assert recent_fps(log) == (750.0, 1)


def test_recent_fps_returns_none_when_no_samples_exist(tmp_path: Path) -> None:
    log = tmp_path / "worker.log"
    log.write_text("training has not started\n", encoding="utf-8")

    assert recent_fps(log) is None


def test_progress_logger_steps_and_fps_are_reported(tmp_path: Path) -> None:
    log = tmp_path / "worker.log"
    log.write_text(
        "\n".join(
            (
                "2026-10-26 03:00:00 INFO TRAIN_PROGRESS step=1,000/2,000,000 recent_fps=120.0 eta_seconds=16658",
                "2026-10-26 03:00:08 INFO TRAIN_PROGRESS step=2,000/2,000,000 recent_fps=130.5 eta_seconds=15310",
                "2026-10-26 03:00:16 INFO TRAIN_PROGRESS step=3,000/2,000,000 recent_fps=140.5 eta_seconds=14249",
            )
        ),
        encoding="utf-8",
    )

    assert logged_steps(log) == 3_000
    assert recent_fps(log) == (130.5, 3)


def test_estimated_remaining_uses_target_steps_and_recent_fps() -> None:
    assert estimate_remaining_seconds(19_000_000, 20_000_000, 100.0) == 10_000


def test_estimated_remaining_is_unavailable_without_valid_training_rate() -> None:
    assert estimate_remaining_seconds(None, 20_000_000, 100.0) is None
    assert estimate_remaining_seconds(20_000_000, 20_000_000, 100.0) is None
    assert estimate_remaining_seconds(1, 20_000_000, 0.0) is None


def test_command_returns_only_successful_bounded_stdout(monkeypatch: pytest.MonkeyPatch) -> None:
    subprocess_module: Any = vars(status_report)["subprocess"]
    monkeypatch.setattr(
        subprocess_module,
        "run",
        lambda *args, **kwargs: SimpleNamespace(stdout=" result \n", returncode=0),
    )
    assert status_report.command(["read-only-command"], timeout=3) == "result"

    monkeypatch.setattr(
        subprocess_module,
        "run",
        lambda *args, **kwargs: SimpleNamespace(stdout="ignored", returncode=1),
    )
    assert status_report.command(["read-only-command"]) == ""

    def fail_to_start(*args: object, **kwargs: object) -> None:
        raise OSError("command unavailable")

    monkeypatch.setattr(subprocess_module, "run", fail_to_start)
    assert status_report.command(["missing-command"]) == ""


def test_fields_and_node_expansion_parse_slurm_shapes() -> None:
    assert status_report.fields("JobId=91 JobState=RUNNING NodeList=gpuarm[1-2]") == {
        "JobId": "91",
        "JobState": "RUNNING",
        "NodeList": "gpuarm[1-2]",
    }
    assert status_report.expand_nodes("gpuarm[01-02,05]") == {
        "gpuarm01",
        "gpuarm02",
        "gpuarm05",
    }
    assert status_report.expand_nodes("gpuarm2,gpuarm4") == {"gpuarm2", "gpuarm4"}
    assert status_report.expand_nodes("") == set()
    assert status_report.expand_nodes("bad[3-x]") == set()


def test_scheduler_jobs_keeps_only_structured_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        status_report,
        "command",
        lambda args: "12|RUNNING|train|0:05|1:00|gpuarm1|None\nmalformed|row",
    )

    assert status_report.scheduler_jobs() == [
        {
            "id": "12",
            "state": "RUNNING",
            "name": "train",
            "elapsed": "0:05",
            "limit": "1:00",
            "nodes": "gpuarm1",
            "reason": "None",
        }
    ]


def test_find_job_id_prefers_unique_live_match_and_reports_ambiguity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        status_report,
        "scheduler_jobs",
        lambda: [
            {"id": "41", "state": "RUNNING", "nodes": "gpuarm[1-2]"},
            {"id": "42", "state": "PENDING", "nodes": "gpuarm[1-2]"},
            {"id": "43", "state": "RUNNING", "nodes": "gpuarm3"},
        ],
    )
    assert status_report.find_job_id(None, {"job_id": "old"}, ["gpuarm1", "gpuarm2"]) == (
        "41",
        "live squeue match on experiment run nodes",
    )

    monkeypatch.setattr(
        status_report,
        "scheduler_jobs",
        lambda: [
            {"id": "41", "state": "RUNNING", "nodes": "gpuarm[1-2]"},
            {"id": "44", "state": "RUNNING", "nodes": "gpuarm1,gpuarm2"},
        ],
    )
    assert status_report.find_job_id(None, {}, ["gpuarm1", "gpuarm2"]) == (
        None,
        "multiple live allocations match; pass --job-id",
    )

    assert status_report.find_job_id("explicit", {}, []) == ("explicit", "explicit argument")
    assert status_report.find_job_id(None, {"job_id": "manifest-id"}, ["gpuarm9"]) == (
        "manifest-id",
        "experiment run manifest fallback",
    )
    assert status_report.find_job_id(None, {}, ["gpuarm9"]) == (
        None,
        "experiment run manifest fallback",
    )


def test_slurm_job_and_node_helpers_handle_missing_live_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert status_report.slurm_job(None) == ({}, "not identified")
    monkeypatch.setattr(status_report, "command", lambda _args: "JobId=7 JobState=RUNNING")
    assert status_report.slurm_job("7") == (
        {"JobId": "7", "JobState": "RUNNING"},
        "live scontrol",
    )
    monkeypatch.setattr(status_report, "command", lambda _args: "")
    assert status_report.slurm_job("missing") == ({}, "unavailable from scontrol")
    assert status_report.slurm_node("gpuarm1") == {}


@pytest.mark.parametrize(
    ("value", "family", "expected"),
    [
        ("gpu:gh200:2(S:0)", None, 2),
        ("gres/gpu:h200=4(IDX:0-3)", None, 4),
        ("gres/gpu:a100=3", "h200", None),
        ("gpu:gh200:2", "gh200", 2),
        ("gpu:gh200:2", "a100", None),
        ("none", None, None),
    ],
)
def test_parse_gres_count_handles_gres_and_allocated_tres(
    value: str, family: str | None, expected: int | None
) -> None:
    assert status_report.parse_gres_count(value, family) == expected


def test_latest_resource_sample_uses_last_timestamped_row(tmp_path: Path) -> None:
    sample_path = tmp_path / "resources.csv"
    sample_path.write_text(
        "timestamp_utc,gpu_utilization_pct\n"
        "2026-10-01T00:00:00Z,35\n"
        ",ignored\n"
        "2026-10-01T00:01:00Z,60\n",
        encoding="utf-8",
    )
    assert status_report.latest_resource_sample(sample_path) == {
        "timestamp_utc": "2026-10-01T00:01:00Z",
        "gpu_utilization_pct": "60",
    }
    assert status_report.latest_resource_sample(tmp_path / "missing.csv") == {}
    empty = tmp_path / "empty.csv"
    empty.write_text("timestamp_utc,value\n,missing\n", encoding="utf-8")
    assert status_report.latest_resource_sample(empty) == {}


@pytest.mark.parametrize("error", [OSError("unreadable"), csv.Error("invalid csv")])
def test_latest_resource_sample_returns_empty_on_read_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    sample_path = tmp_path / "resources.csv"
    sample_path.write_text("timestamp_utc,value\nnow,1\n", encoding="utf-8")

    def fail_open(*_args: object, **_kwargs: object) -> None:
        raise error

    monkeypatch.setattr(Path, "open", fail_open)
    assert status_report.latest_resource_sample(sample_path) == {}


def test_manager_ready_requires_matching_job_and_node_log(tmp_path: Path) -> None:
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "worker_manager_0_123.log").write_text(
        "EXPERIMENT_RUN_NODE_MANAGER ready host=gpuarm1 pid=100\n", encoding="utf-8"
    )
    assert status_report.manager_ready(tmp_path, None, "gpuarm1") is None
    assert status_report.manager_ready(tmp_path, "123", "gpuarm1") is True
    assert status_report.manager_ready(tmp_path, "123", "gpuarm2") is False
    assert status_report.manager_ready(tmp_path, "456", "gpuarm1") is False


def test_manager_ready_skips_unreadable_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    logs = tmp_path / "logs"
    logs.mkdir()
    path = logs / "worker_manager_0_123.log"
    path.write_text("not ready", encoding="utf-8")
    read_text = Path.read_text

    def fail_one_log(target: Path, encoding: str | None = None, errors: str | None = None) -> str:
        if target == path:
            raise OSError("unreadable")
        return read_text(target, encoding=encoding, errors=errors)

    monkeypatch.setattr(Path, "read_text", fail_one_log)
    assert status_report.manager_ready(tmp_path, "123", "gpuarm1") is False


def test_variant_sort_key_orders_rungs_then_families() -> None:
    jobs = [
        {"variant": "a2_dist_baseline"},
        {"variant": "a0_po3_candidate"},
        {"variant": "a0_baseline"},
        {"variant": "unknown"},
    ]
    assert sorted(jobs, key=status_report.variant_sort_key) == [jobs[2], jobs[1], jobs[0], jobs[3]]
    assert status_report.variant_sort_key({"key": "a4b_distribution"}) == (5, 2, "a4b_distribution")


def test_logged_steps_uses_latest_progress_or_sb3_table(tmp_path: Path) -> None:
    progress = tmp_path / "progress.log"
    progress.write_text(
        "TRAIN_PROGRESS step=1,000/5,000 recent_fps=10.0\n"
        "TRAIN_PROGRESS step=2,500/5,000 recent_fps=11.0\n",
        encoding="utf-8",
    )
    assert status_report.logged_steps(progress) == 2500

    table = tmp_path / "table.log"
    table.write_text("| total_timesteps | 1000 |\n| total_timesteps | 2,000 |\n", encoding="utf-8")
    assert status_report.logged_steps(table) == 2000
    fallback = tmp_path / "fallback.log"
    fallback.write_text("| timesteps | 3,000 |\n", encoding="utf-8")
    assert status_report.logged_steps(fallback) == 3000
    assert status_report.logged_steps(tmp_path / "missing.log") is None
    assert status_report.logged_steps(tmp_path / "empty.log") is None


def test_recent_fps_reads_progress_and_returns_none_for_missing_file(tmp_path: Path) -> None:
    progress = tmp_path / "progress.log"
    progress.write_text(
        "TRAIN_PROGRESS step=1/5 recent_fps=100.5\n"
        "TRAIN_PROGRESS step=2/5 recent_fps=101.5\n"
        "TRAIN_PROGRESS step=3/5 recent_fps=102.5\n",
        encoding="utf-8",
    )
    assert status_report.recent_fps(progress, sample_count=2) == (102.0, 2)
    assert status_report.recent_fps(tmp_path / "missing.log") is None


def test_latest_checkpoint_returns_newest_valid_attempt_artifact(tmp_path: Path) -> None:
    timezone = ZoneInfo("UTC")
    now = dt.datetime(2026, 10, 1, tzinfo=timezone)
    assert status_report.latest_checkpoint(tmp_path, "../unsafe", now) == "none found"
    assert status_report.latest_checkpoint(tmp_path, "variant__seed42", now) == "none found"

    model_dir = tmp_path / "runs" / "attempts" / "variant__seed42" / "attempt1" / "model"
    model_dir.mkdir(parents=True)
    older = model_dir / "ppo_1000_steps.zip"
    newer = model_dir / "ppo_2000_steps.zip"
    older.write_bytes(b"old")
    newer.write_bytes(b"new")
    os.utime(older, (1_000_000_000, 1_000_000_000))
    os.utime(newer, (1_100_000_000, 1_100_000_000))

    assert status_report.latest_checkpoint(tmp_path, "variant__seed42", now).startswith(
        "ppo_2000_steps.zip (2004-"
    )


def test_phase_failure_detail_and_format_helpers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log = tmp_path / "worker.log"
    log.write_text("Evaluating trained model\n", encoding="utf-8")
    assert status_report.job_phase({"status": "running"}, log) == "evaluation"
    assert status_report.job_phase({"status": "pending"}, log) == "pending"
    assert status_report.job_phase({"status": "mystery"}, tmp_path / "missing") == "mystery"
    assert (
        status_report.failure_detail({"failure_reason": "manifest failure"}, log)
        == "manifest failure"
    )
    log.write_text(
        "experiment run worker dispatch error: old error\n"
        "experiment run worker dispatch error: fresh error 2026-10-01T01:02:03Z\n",
        encoding="utf-8",
    )
    assert status_report.failure_detail({}, log) == "fresh error"
    assert status_report.failure_detail({}, tmp_path / "missing") == "failed; details unavailable"

    assert status_report.fmt_time(None) == "unavailable"
    assert status_report.fmt_time("not-a-number") == "not-a-number"
    assert status_report.fmt_time("61") == "0:01:01"
    assert status_report.cell("a|b\nc") == "a\\|b c"

    monkeypatch.setattr(status_report, "command", lambda _args: "one\ntwo")
    assert status_report.get_tmux_supervisor(None) == "not identified; tmux sessions: one, two"
    assert status_report.get_tmux_supervisor("named") == "named"
    monkeypatch.setattr(status_report, "command", lambda _args: "")
    assert status_report.get_tmux_supervisor(None) == "not detected"


def test_elapsed_for_job_reports_invalid_and_completed_attempt_times() -> None:
    timezone = ZoneInfo("Europe/Helsinki")
    now = dt.datetime.fromisoformat("2026-10-19T12:31:44+00:00").astimezone(timezone)
    assert status_report.elapsed_for_job(None, None, "running", now, timezone) == "unavailable"
    assert status_report.elapsed_for_job("invalid", None, "running", now, timezone) == "unavailable"
    assert (
        status_report.elapsed_for_job(
            "2026-10-19T12:00:00+00:00",
            "2026-10-19T12:01:05+00:00",
            "succeeded",
            now,
            timezone,
        )
        == "0:01:05"
    )


def test_render_reports_mocked_allocation_node_and_variant_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = tmp_path / "experiment_run"
    logs = run_dir / "logs"
    logs.mkdir(parents=True)
    worker_log = logs / "worker.log"
    worker_log.write_text(
        "TRAIN_PROGRESS step=50/100 recent_fps=10.0\nTRAIN_PROGRESS step=75/100 recent_fps=20.0\n",
        encoding="utf-8",
    )
    evaluation_log = logs / "evaluation.log"
    evaluation_log.write_text("Evaluating trained model\n", encoding="utf-8")
    (logs / "worker_manager_0_123.log").write_text(
        "EXPERIMENT_RUN_NODE_MANAGER ready host=gpuarm1 pid=99\n", encoding="utf-8"
    )
    resources = logs / "resources_gpuarm1.csv"
    resources.write_text(
        "timestamp_utc,gpu_utilization_pct,gpu_memory_used_mib\n"
        f"{dt.datetime.now(dt.UTC).isoformat()},80,1200\n",
        encoding="utf-8",
    )
    model_dir = run_dir / "runs" / "attempts" / "variant_a0_po3" / "attempt1" / "model"
    model_dir.mkdir(parents=True)
    checkpoint = model_dir / "ppo_100_steps.zip"
    checkpoint.write_bytes(b"checkpoint")

    manifest_path = run_dir / "experiment_run.json"
    manifest_path.write_text(
        json.dumps(
            {
                "fingerprint": "abc",
                "job_id": "123",
                "timesteps": 100,
                "worker_nodes": ["gpuarm1", "gpuarm2"],
                "jobs": [
                    {
                        "key": "variant_a0_po3",
                        "variant": "variant_a0_po3",
                        "status": "running",
                        "started": "2026-10-19T12:00:00+00:00",
                        "attempts": 1,
                        "worker_node": "gpuarm1",
                        "worker_gpu_id": 0,
                        "worker_cpu_ids": [0, 1],
                        "log": str(worker_log),
                    },
                    {
                        "key": "variant_a1_failure",
                        "variant": "variant_a1_failure",
                        "status": "failed",
                        "attempts": 1,
                        "failure_reason": "worker exited",
                        "log": str(logs / "failure.log"),
                    },
                    {
                        "key": "variant_a2_evaluation",
                        "variant": "variant_a2_evaluation",
                        "status": "running",
                        "log": "experiment_run/logs/evaluation.log",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        status_report,
        "slurm_job",
        lambda _job: (
            {
                "JobId": "123",
                "JobState": "RUNNING",
                "NodeList": "gpuarm[1-2]",
                "RunTime": "60",
                "TimeLimit": "3600",
            },
            "live scontrol",
        ),
    )
    monkeypatch.setattr(
        status_report,
        "slurm_node",
        lambda node: {
            "CPUTot": "48",
            "CPUAlloc": "16",
            "CPULoad": "4.5",
            "RealMemory": "500000",
            "AllocMem": "32000",
            "Gres": "gpu:gh200:1",
            "AllocTRES": "gres/gpu:gh200=1",
        },
    )
    monkeypatch.setattr(status_report, "get_tmux_supervisor", lambda _value: "qrl-status")
    monkeypatch.setitem(vars(status_report), "ROOT", tmp_path)

    report = status_report.render(manifest_path, "123", "qrl-status")

    assert "Scheduler status: job 123 is RUNNING on gpuarm[1-2]." in report
    assert "gh200 1 / 1" in report
    assert "current: 80% / 1200 MiB used" in report
    assert "ready" in report
    assert "75 / 100" in report
    assert "15 (n=2)" in report
    assert "ppo_100_steps.zip" in report
    assert "worker exited" in report
    assert "training target reached; evaluation in progress" in report


def test_render_handles_bad_node_fields_and_valid_allocation_end_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest_path = tmp_path / "experiment_run.json"
    manifest_path.write_text(
        json.dumps({"worker_nodes": ["gpuarm9"], "jobs": []}), encoding="utf-8"
    )
    monkeypatch.setattr(
        status_report,
        "slurm_job",
        lambda _job: (
            {
                "JobId": "9",
                "JobState": "RUNNING",
                "EndTime": "2099-01-01T00:00:00",
            },
            "live scontrol",
        ),
    )
    monkeypatch.setattr(
        status_report,
        "slurm_node",
        lambda _node: {
            "CPUTot": "unknown",
            "CPUAlloc": "unknown",
            "RealMemory": "unknown",
            "AllocMem": "unknown",
        },
    )
    monkeypatch.setattr(status_report, "get_tmux_supervisor", lambda _value: "not detected")

    report = status_report.render(manifest_path, "9", None)

    assert "estimated remaining " in report
    assert "estimated remaining unavailable" not in report
    assert "unknown/unknown (?; load unavailable)" in report
    assert "unknown/unknown MiB (? MiB)" in report


def test_main_accepts_directory_and_reports_render_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    manifest = run_dir / "experiment_run.json"
    manifest.write_text(json.dumps({"jobs": [], "worker_nodes": []}), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["status.py", str(run_dir), "--job-id", "7"])
    monkeypatch.setattr(status_report, "render", lambda path, job_id, supervisor: "rendered")

    assert status_report.main() == 0
    assert capsys.readouterr().out == "rendered\n"

    monkeypatch.setattr(
        status_report, "render", lambda *_args: (_ for _ in ()).throw(ValueError("bad report"))
    )
    assert status_report.main() == 2
    assert "experiment run status report failed: bad report" in capsys.readouterr().err


def test_module_entrypoint_runs_main(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manifest = tmp_path / "experiment_run.json"
    manifest.write_text(json.dumps({"jobs": [], "worker_nodes": []}), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [str(status_report.__file__), str(manifest)])
    with pytest.raises(SystemExit, match="0"):
        runpy.run_path(str(status_report.__file__), run_name="__main__")
