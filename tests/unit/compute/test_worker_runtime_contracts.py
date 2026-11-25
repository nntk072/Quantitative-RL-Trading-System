"""Runtime contracts for owned child workers: cancel, completion, failure state, and no retries."""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import compute
from compute.slurm import capacity
from compute.slurm import worker_dispatch as worker_dispatch

COMPUTE_ROOT = Path(compute.__file__).resolve().parent
STATE_CHANGING_SCHEDULER_COMMANDS = {"sbatch", "salloc", "srun", "scancel"}
SUBPROCESS_CALLS = {"run", "Popen", "call", "check_call", "check_output"}
SHIM_ARGV = [
    "--nodelist=gpuarm1",
    "--cpus-per-task=2",
    "--cpu-bind=mask_cpu:0x3",
    "--nodes=1",
    "--ntasks=1",
    "--chdir",
    "/repo",
    "python",
    "run.py",
]


def _manager_environment(
    monkeypatch: pytest.MonkeyPatch, queue: Path, node: str, job_id: str, done_marker: Path
) -> None:
    monkeypatch.setenv("SLURM_JOB_ID", job_id)
    monkeypatch.setenv("EXPERIMENT_RUN_WORKER_QUEUE", str(queue))
    monkeypatch.setenv("SLURMD_NODENAME", node)
    monkeypatch.setenv("EXPERIMENT_RUN_OUT_DIR", str(done_marker.parent / "run"))
    monkeypatch.setenv("EXPERIMENT_RUN_ALLOCATION_DONE_MARKER", str(done_marker))


def test_manager_never_launches_a_request_cancelled_before_it_was_claimed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    queue = tmp_path / "queue"
    node = "gpuarm1"
    done_marker = tmp_path / "allocation.done"
    _manager_environment(monkeypatch, queue, node, "1001", done_marker)
    pending, claimed, results, _ready = worker_dispatch._paths(queue, node)
    pending.mkdir(parents=True)
    request = {
        "request_id": "pending-cancel",
        "node": node,
        "cpu_ids": [0],
        "gpu_count": 0,
        "gpu_id": 0,
        "argv": ["python", "worker.py"],
        "env": {},
        "cwd": str(tmp_path),
        "stdout_path": "",
    }
    (pending / "pending-cancel.json").write_text(json.dumps(request), encoding="utf-8")
    cancelled = pending.parent / "cancelled"
    cancelled.mkdir()
    (cancelled / "pending-cancel.cancel").touch()
    done_marker.touch()
    monkeypatch.setattr(worker_dispatch.os, "sched_getaffinity", lambda _pid: {0})
    monkeypatch.setattr(
        worker_dispatch, "available_resources", lambda: {"memory_limit_bytes": 1024}
    )
    monkeypatch.setattr(worker_dispatch, "gpu_memory_inventory", lambda: [])
    monkeypatch.setattr(
        worker_dispatch, "_launch", lambda *_args: pytest.fail("cancelled request was launched")
    )

    assert worker_dispatch._manager() == 0

    # 143 = 128 + SIGTERM, the exit status the cancelled shim already reported.
    assert json.loads((results / "pending-cancel.json").read_text(encoding="utf-8")) == {
        "returncode": 143
    }
    assert (claimed.parent / "completed" / "pending-cancel.json").is_file()


def test_real_worker_gets_thread_limits_from_granted_cores_and_failure_keeps_state_and_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    granted = sorted(os.sched_getaffinity(0))[:2]
    expected = str(len(granted))
    queue = tmp_path / "queue"
    node = "gpuarm1"
    done_marker = tmp_path / "allocation.done"
    _manager_environment(monkeypatch, queue, node, "1002", done_marker)
    pending, claimed, results, _ready = worker_dispatch._paths(queue, node)
    pending.mkdir(parents=True)
    log_path = tmp_path / "logs" / "worker.log"
    # The requester's host-level thread settings must not reach the child.
    monkeypatch.setenv("OMP_NUM_THREADS", "64")
    monkeypatch.setenv("RAYON_NUM_THREADS", "64")
    child_code = (
        "import os, sys; "
        "print(os.environ['OMP_NUM_THREADS'], os.environ['RAYON_NUM_THREADS'], "
        "os.environ['POLARS_MAX_THREADS']); sys.exit(3)"
    )
    request = {
        "request_id": "real-1",
        "node": node,
        "cpu_ids": granted,
        "gpu_count": 0,
        "gpu_id": 0,
        "argv": [sys.executable, "-c", child_code],
        "env": {},
        "cwd": str(tmp_path),
        "stdout_path": str(log_path),
    }
    (pending / "real-1.json").write_text(json.dumps(request), encoding="utf-8")
    done_marker.touch()
    monkeypatch.setattr(
        worker_dispatch, "available_resources", lambda: {"memory_limit_bytes": 1024}
    )
    monkeypatch.setattr(worker_dispatch, "gpu_memory_inventory", lambda: [])

    assert worker_dispatch._manager() == 0

    assert json.loads((results / "real-1.json").read_text(encoding="utf-8")) == {"returncode": 3}
    completed = claimed.parent / "completed" / "real-1.json"
    assert json.loads(completed.read_text(encoding="utf-8")) == request
    assert log_path.read_text(encoding="utf-8") == f"{expected} {expected} {expected}\n"


def test_shim_waits_on_one_submitted_request_without_resubmitting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    queue = tmp_path / "queue"
    monkeypatch.setenv("SLURM_JOB_ID", "1003")
    monkeypatch.setenv("EXPERIMENT_RUN_WORKER_QUEUE", str(queue))
    pending, _claimed, results, ready = worker_dispatch._paths(queue, "gpuarm1")
    ready.parent.mkdir(parents=True)
    ready.write_text("ready", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["worker_dispatch", "--srun-shim", *SHIM_ARGV])
    monkeypatch.setattr(worker_dispatch.signal, "signal", lambda *_args: None)
    monkeypatch.setattr(worker_dispatch.uuid, "uuid4", lambda: SimpleNamespace(hex="once-1"))
    monkeypatch.setattr(worker_dispatch.os, "readlink", lambda _fd: "pipe:[stdout]")
    sleeps: list[float] = []

    def sleep_then_complete(seconds: float) -> None:
        sleeps.append(seconds)
        if len(sleeps) == 3:
            results.mkdir(parents=True, exist_ok=True)
            (results / "once-1.json").write_text(json.dumps({"returncode": 0}), encoding="utf-8")

    monkeypatch.setattr(worker_dispatch.time, "sleep", sleep_then_complete)

    assert worker_dispatch._request() == 0
    # One fixed-interval poll per second and exactly one submitted request file.
    assert sleeps == [1, 1, 1]
    assert [path.name for path in pending.glob("*.json")] == ["once-1.json"]


def test_failed_scheduler_query_is_issued_once_and_never_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    issued: list[list[str]] = []

    def failing_run(args: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        issued.append(list(args))
        raise subprocess.CalledProcessError(1, args, stderr="partition unavailable")

    monkeypatch.setattr(capacity.subprocess, "run", failing_run)

    with pytest.raises(subprocess.CalledProcessError):
        capacity.available_nodes(
            "gpu-partition",
            gpu_type="gh200",
            gpus_per_node=1,
            cpus_per_node=1,
            memory_mb=1,
        )
    assert issued == [["sinfo", "-N", "-h", "-p", "gpu-partition", "-o", "%N"]]


def test_compute_never_executes_a_state_changing_scheduler_command() -> None:
    offenders: list[str] = []
    for path in sorted(COMPUTE_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in SUBPROCESS_CALLS
                and node.args
                and isinstance(node.args[0], ast.List)
                and node.args[0].elts
            ):
                continue
            head = node.args[0].elts[0]
            if isinstance(head, ast.Constant) and head.value in STATE_CHANGING_SCHEDULER_COMMANDS:
                offenders.append(f"{path.relative_to(COMPUTE_ROOT)}:{node.lineno}")

    assert offenders == []
