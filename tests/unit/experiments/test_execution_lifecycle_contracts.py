"""A completed fake worker is admitted and recorded against its run identity."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from experiments.runs import execution


@pytest.mark.parametrize(
    ("exit_code", "verified", "expected_status", "expected_return"),
    [
        (0, True, "succeeded", 0),
        (1, True, "failed", 1),
        (0, False, "failed", 1),
    ],
)
def test_fake_worker_attempt_records_provenance_and_exit_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    exit_code: int,
    verified: bool,
    expected_status: str,
    expected_return: int,
) -> None:
    repository = tmp_path / "repo"
    config_dir = repository / "config"
    config_dir.mkdir(parents=True)
    base_dir = config_dir / "base"
    base_dir.mkdir()
    run_config_dir = config_dir / "experiment_runs"
    run_config_dir.mkdir()
    (config_dir / "experiments.yaml").write_text(
        "variants:\n  - name: sample_variant\n", encoding="utf-8"
    )
    (base_dir / "default.yaml").write_text(
        "data:\n  raw_dir: data\n  cache_dir: null\n  split:\n    train_end: '2025-12-31'\n"
        "    test_start: '2026-01-01'\n",
        encoding="utf-8",
    )
    (repository / "variants.txt").write_text("sample_variant\n", encoding="utf-8")
    spec = run_config_dir / "sample.yaml"
    spec.write_text(
        "experiment_run_id: sample-run\n"
        "variant_file: variants.txt\n"
        "variants: [sample_variant]\n"
        "seeds: [7]\n"
        "timesteps: 100\n"
        "data_source: frames\n"
        "split:\n  train_end: '2025-12-31'\n  test_start: '2026-01-01'\n"
        "evaluation:\n  locked_oos_role: final_report_only\n"
        "  selection_allowed: false\n  deterministic: true\n"
        "config_overrides:\n  data.cache_dir: profiled-cache\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(execution, "ROOT", repository)
    monkeypatch.setattr(
        execution,
        "runtime_metadata",
        lambda: {
            "python": "3.test",
            "machine": "test-machine",
            "packages": {},
        },
    )
    monkeypatch.setattr(
        execution,
        "experiment_run_source_files",
        lambda _root, _spec: [config_dir / "experiments.yaml", repository / "variants.txt"],
    )
    monkeypatch.setattr(
        execution,
        "write_experiment_run_source_snapshot",
        lambda *_args, **_kwargs: {
            "path": "source_snapshot.zip",
            "sha256": "a" * 64,
            "manifest_sha256": "b" * 64,
            "file_count": 2,
        },
    )
    monkeypatch.setattr(
        execution,
        "available_resources",
        lambda: {"cpu_affinity": 4, "memory_limit_bytes": 128 * 1024**3},
    )
    monkeypatch.setattr(execution, "sample_resources", lambda *_args, **_kwargs: None)
    captured_data_inputs: list[str] = []

    def data_inputs(data: dict[str, Any]) -> dict[str, str]:
        captured_data_inputs.append(str(data["cache_dir"]))
        return {"cache_dir": str(data["cache_dir"])}

    monkeypatch.setattr(execution, "experiment_run_data_inputs", data_inputs)
    if not verified:
        monkeypatch.setenv("SLURM_JOB_ID", "test-allocation")
        monkeypatch.setattr(
            execution,
            "verify_run_artifacts",
            lambda *_args, **_kwargs: (False, "artifact manifest missing"),
        )
    monkeypatch.setattr(execution, "resolve_worker_nodes", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(execution.__dict__["signal"], "signal", lambda *_args, **_kwargs: None)

    def git_output(
        command: list[str], *, cwd: Path | None = None, text: bool = False
    ) -> str | bytes:
        assert cwd in (None, repository)
        if command[0:3] == ["git", "rev-parse", "HEAD"] or command[-2:] == [
            "rev-parse",
            "HEAD",
        ]:
            return "a" * 40 if text else b"a" * 40
        if "status" in command:
            return "" if text else b""
        if "diff" in command:
            return b""
        raise AssertionError(f"unexpected subprocess command: {command}")

    monkeypatch.setattr(execution.__dict__["subprocess"], "check_output", git_output)
    worker_calls: list[dict[str, Any]] = []

    class CompletedProcess:
        pid = 2468

        def poll(self) -> int:
            return exit_code

    def start_process(
        command: list[str], *, cwd: Path, env: dict[str, str], stdout: Any, **kwargs: Any
    ) -> CompletedProcess:
        worker_calls.append({"command": command, "cwd": cwd, "env": env, **kwargs})
        return CompletedProcess()

    monkeypatch.setattr(execution.__dict__["subprocess"], "Popen", start_process)
    monkeypatch.setattr(
        execution.__dict__["subprocess"],
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="summary", stderr=""),
    )
    argv = [
        "experiment_run_controller.py",
        "--experiment-run-spec",
        str(spec),
        "--workers",
        "1",
        "--n-envs",
        "4",
        "--benchmark",
    ]
    if verified:
        argv.extend(["--test-worker", "/test/fake-worker"])
    monkeypatch.setattr(sys, "argv", argv)

    assert execution.main() == expected_return

    run_dir = repository / "outputs" / "gpu_experiment_runs" / "sample-run"
    manifest = json.loads((run_dir / "experiment_run.json").read_text(encoding="utf-8"))
    provenance = json.loads(
        (
            run_dir
            / "runs"
            / "attempts"
            / "sample_variant__seed7"
            / "attempt1"
            / "attempt_provenance.json"
        ).read_text(encoding="utf-8")
    )
    assert manifest["jobs"][0]["status"] == expected_status
    assert manifest["jobs"][0]["attempts"] == 1
    assert manifest["source_snapshot"]["path"] == "source_snapshot.zip"
    assert manifest["config_overrides"] == {"data.cache_dir": "profiled-cache"}
    assert manifest["data_inputs"] == {"cache_dir": "profiled-cache"}
    assert captured_data_inputs == ["profiled-cache"]
    assert provenance["experiment_run_fingerprint"] == manifest["fingerprint"]
    assert provenance["identity"]["jobs"] == ["sample_variant__seed7"]
    marker = run_dir / "markers" / "sample_variant__seed7.done"
    assert marker.is_file() is (expected_status == "succeeded")
    with (run_dir / "reports" / "benchmarks.csv").open(encoding="utf-8") as stream:
        benchmark_rows = list(csv.reader(stream))
    assert len(benchmark_rows) == 1
    assert benchmark_rows[0][1:4] == ["1", "4", "100"]
    if exit_code != 0:
        assert manifest["jobs"][0]["failure_reason"] == "worker exited with code 1"
    elif not verified:
        assert manifest["jobs"][0]["failure_reason"] == "artifact manifest missing"
    assert worker_calls[0]["command"] == (
        ["/test/fake-worker", "sample_variant__seed7"]
        if verified
        else [sys.executable, "-m", execution.VARIANT_WORKER_MODULE]
    )
    assert worker_calls[0]["env"]["STEPS"] == "100"
    assert "summary" in capsys.readouterr().out

    if expected_status == "succeeded":
        with pytest.raises(RuntimeError, match="experiment run exists: use --resume"):
            execution.main()

        monkeypatch.setattr(execution, "verify_run_artifacts", lambda *_args, **_kwargs: (True, ""))
        monkeypatch.setattr(
            execution,
            "verify_experiment_run_source_snapshot",
            lambda *_args, **_kwargs: (True, ""),
        )
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "experiment_run_controller.py",
                "--experiment-run-spec",
                str(spec),
                "--workers",
                "1",
                "--n-envs",
                "4",
                "--benchmark",
                "--resume",
                "--test-worker",
                "/test/fake-worker",
            ],
        )

        assert execution.main() == 0

        resumed = json.loads((run_dir / "experiment_run.json").read_text(encoding="utf-8"))
        assert resumed["jobs"][0]["status"] == "succeeded"
        assert resumed["jobs"][0]["attempts"] == 1
        assert len(worker_calls) == 1


def test_worker_slot_allocator_fairly_falls_back_to_capacity_and_refuses_overflow() -> None:
    assert execution.distribute_worker_slots(3, {"node-b": 2, "node-a": 1}) == {
        "node-a": 1,
        "node-b": 2,
    }
    with pytest.raises(ValueError, match="exceeds the resource-derived capacity"):
        execution.distribute_worker_slots(4, {"node-a": 1, "node-b": 2})


def test_auto_worker_plan_assigns_distinct_nodes_and_cpu_masks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = tmp_path / "repo"
    config_dir = repository / "config"
    base_dir = config_dir / "base"
    base_dir.mkdir(parents=True)
    run_config_dir = config_dir / "experiment_runs"
    run_config_dir.mkdir()
    (config_dir / "experiments.yaml").write_text(
        "variants:\n  - name: sample_variant\n", encoding="utf-8"
    )
    (base_dir / "default.yaml").write_text(
        "data:\n  raw_dir: data\n  split:\n    train_end: '2025-12-31'\n"
        "    test_start: '2026-01-01'\n",
        encoding="utf-8",
    )
    variant_file = run_config_dir / "variants.txt"
    variant_file.write_text("sample_variant\n", encoding="utf-8")
    spec = run_config_dir / "probe.yaml"
    spec.write_text(
        "experiment_run_id: multi-node-probe\n"
        "variant_file: config/experiment_runs/variants.txt\n"
        "variants: [sample_variant]\n"
        "seeds: [7, 11]\n"
        "timesteps: 100\n"
        "data_source: frames\n"
        "split:\n  train_end: '2025-12-31'\n  test_start: '2026-01-01'\n"
        "evaluation:\n  locked_oos_role: final_report_only\n"
        "  selection_allowed: false\n  deterministic: true\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(execution, "ROOT", repository)
    monkeypatch.setattr(
        execution, "runtime_metadata", lambda: {"python": "test", "machine": "test", "packages": {}}
    )
    monkeypatch.setattr(
        execution,
        "experiment_run_source_files",
        lambda _root, _spec: [config_dir / "experiments.yaml", variant_file],
    )
    monkeypatch.setattr(
        execution,
        "write_experiment_run_source_snapshot",
        lambda *_args, **_kwargs: {"path": "snapshot.zip", "sha256": "a" * 64},
    )
    monkeypatch.setattr(
        execution,
        "available_resources",
        lambda: {"cpu_affinity": 8, "memory_limit_bytes": 128 * 1024**3},
    )
    monkeypatch.setattr(
        execution, "resolve_worker_nodes", lambda *_args, **_kwargs: ["node-a", "node-b"]
    )
    monkeypatch.setattr(
        execution,
        "worker_node_resources",
        lambda _queue, _job, _node: {
            "cpu_ids": list(range(9)),
            "memory_limit_bytes": 128 * 1024**3,
            "gpu_memory": {"0": 16_000},
        },
    )
    monkeypatch.setattr(
        execution,
        "plan_worker_capacity",
        lambda resources, **_kwargs: {
            "workers": len(resources),
            "nodes": {node: {"workers": 1} for node in resources},
        },
    )
    monkeypatch.setattr(
        execution,
        "cpu_mask_for_slot",
        lambda cpu_ids, _count, _slot: ("sampler-mask", [cpu_ids[-1]]),
    )
    monkeypatch.setattr(
        execution,
        "cpu_mask_for_range",
        lambda cpu_ids, start, count: ("worker-mask", cpu_ids[start : start + count]),
    )
    worker_commands: list[tuple[str, list[str]]] = []

    def build_command(command: list[str], *, node: str, **_kwargs: Any) -> list[str]:
        worker_commands.append((node, command))
        return command

    monkeypatch.setattr(execution, "worker_command", build_command)
    monkeypatch.setattr(
        execution.__dict__["subprocess"], "check_output", lambda *_args, **_kwargs: "a" * 40
    )
    monkeypatch.setattr(execution.__dict__["signal"], "signal", lambda *_args, **_kwargs: None)

    class CompletedProcess:
        pid = 2468

        def poll(self) -> int:
            return 0

        def wait(self, *, timeout: int) -> int:
            assert timeout == 60
            return 0

    monkeypatch.setattr(
        execution.__dict__["subprocess"],
        "Popen",
        lambda *_args, **_kwargs: CompletedProcess(),
    )
    monkeypatch.setattr(
        execution.__dict__["subprocess"],
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="summary", stderr=""),
    )
    monkeypatch.setenv("SLURM_JOB_ID", "test-allocation")
    monkeypatch.setenv("EXPERIMENT_RUN_WORKER_QUEUE", str(tmp_path / "worker-queue"))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "experiment_run_controller.py",
            "--experiment-run-spec",
            str(spec),
            "--worker-nodes",
            "node-a,node-b",
            "--workers",
            "auto",
            "--worker-cpus",
            "auto",
            "--test-worker",
            "/test/fake-worker",
        ],
    )

    assert execution.main() == 0

    manifest_path = (
        repository / "outputs" / "gpu_experiment_runs" / "multi-node-probe" / "experiment_run.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    worker_starts = [
        (node, command) for node, command in worker_commands if command[0] == "/test/fake-worker"
    ]
    assert [node for node, _ in worker_starts] == ["node-a", "node-b"]
    assert [job["worker_node"] for job in manifest["jobs"]] == ["node-a", "node-b"]
    assert all(len(job["worker_cpu_ids"]) == 8 for job in manifest["jobs"])
    assert manifest["worker_allocation_plan"]["workers_selected"] == 2
    assert "summary" in capsys.readouterr().out


def test_sigterm_marks_active_job_interrupted_without_completion_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A stop during an active worker records interruption and preserves resumability."""
    repository = tmp_path / "repo"
    config = repository / "config"
    (config / "base").mkdir(parents=True)
    (config / "experiments.yaml").write_text("variants:\n  - name: stop_probe\n", encoding="utf-8")
    (config / "base" / "default.yaml").write_text(
        "data:\n  raw_dir: data\n  split:\n"
        "    train_end: '2025-12-31'\n    test_start: '2026-01-01'\n",
        encoding="utf-8",
    )
    variant_file = repository / "variants.txt"
    variant_file.write_text("stop_probe\n", encoding="utf-8")
    monkeypatch.setattr(execution, "ROOT", repository)
    monkeypatch.setattr(execution, "STOP", False)
    monkeypatch.setattr(
        execution,
        "runtime_metadata",
        lambda: {"python": "test", "machine": "test", "packages": {}},
    )
    source_files = [config / "experiments.yaml", variant_file]
    monkeypatch.setattr(execution, "experiment_run_source_files", lambda *_args: source_files)
    monkeypatch.setattr(
        execution,
        "write_experiment_run_source_snapshot",
        lambda *_args, **_kwargs: {
            "path": "source_snapshot.zip",
            "sha256": "a" * 64,
            "manifest_sha256": "b" * 64,
            "file_count": 2,
        },
    )
    monkeypatch.setattr(
        execution,
        "available_resources",
        lambda: {"cpu_affinity": 4, "memory_limit_bytes": 128 * 1024**3},
    )
    monkeypatch.setattr(execution, "sample_resources", lambda *_args: None)
    monkeypatch.setattr(execution, "resolve_worker_nodes", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(execution.__dict__["signal"], "signal", lambda *_args: None)
    monkeypatch.setattr(
        execution.__dict__["subprocess"],
        "check_output",
        lambda *_args, **_kwargs: "a" * 40,
    )
    monkeypatch.setattr(
        execution,
        "verify_run_artifacts",
        lambda *_args, **_kwargs: (True, ""),
    )
    monkeypatch.setattr(
        execution.__dict__["subprocess"],
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )
    kill_calls: list[tuple[int, int]] = []
    monkeypatch.setattr(
        execution.__dict__["os"], "killpg", lambda pid, sig: kill_calls.append((pid, sig))
    )

    class TerminatedWorker:
        pid = 5678
        polls = iter([None, None, -15])

        def poll(self) -> int | None:
            return next(self.polls)

    monkeypatch.setattr(
        execution.__dict__["subprocess"],
        "Popen",
        lambda *_args, **_kwargs: TerminatedWorker(),
    )

    def request_stop(_seconds: float) -> None:
        execution.STOP = True

    monkeypatch.setattr(execution.__dict__["time"], "sleep", request_stop)
    monkeypatch.setenv("SLURM_JOB_ID", "test-allocation")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "experiment_run_controller.py",
            "--variant-file",
            str(variant_file),
            "--seeds",
            "7",
            "--timesteps",
            "100",
            "--workers",
            "1",
            "--n-envs",
            "4",
            "--experiment-run-id",
            "stop-probe",
        ],
    )

    assert execution.main() == 1

    run_dir = repository / "outputs" / "gpu_experiment_runs" / "stop-probe"
    manifest = json.loads((run_dir / "experiment_run.json").read_text(encoding="utf-8"))
    job = manifest["jobs"][0]
    assert manifest["stopping"] is True
    assert job["status"] == "interrupted"
    assert job["exit_code"] == -15
    assert job["attempts"] == 1
    assert kill_calls == [(5678, execution.__dict__["signal"].SIGTERM)]
    assert not (run_dir / "markers" / "stop_probe__seed7.done").exists()
    events = [
        json.loads(line)
        for line in (run_dir / "queue.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [event["event"] for event in events] == ["start", "interrupted"]
