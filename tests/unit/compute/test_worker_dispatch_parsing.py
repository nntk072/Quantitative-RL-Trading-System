"""Parsing of the fixed srun options that the experiment-run worker command accepts."""

from __future__ import annotations

import json
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import compute.slurm.worker_dispatch as worker_dispatch
from artifacts.layout import ExperimentRunArtifactLayout
from compute.slurm.worker_dispatch import _host_key, _parse_srun

VALID = [
    "--overlap",
    "--nodelist=gpuarm1.int.triton.aalto.fi",
    "--gpus=gh200:1",
    "--gpu-bind=map_gpu:0",
    "--cpu-bind=mask_cpu:0x3",
    "--cpus-per-task=2",
    "--nodes=1",
    "--ntasks=1",
    "--chdir",
    "/repo",
    "--export=ALL",
    "python",
    "run.py",
]


def _with(replacements: dict[str, str]) -> list[str]:
    """Return the valid argv with the named option values replaced."""
    result = []
    for arg in VALID:
        key = arg.split("=", 1)[0]
        result.append(replacements.get(key, arg))
    return result


def test_host_key_keeps_the_short_host_name() -> None:
    assert _host_key("gpuarm1.int.triton.aalto.fi") == "gpuarm1"
    assert _host_key("gpuarm1") == "gpuarm1"


def test_valid_worker_command_is_parsed() -> None:
    parsed = _parse_srun(VALID)

    assert parsed == {
        "node": "gpuarm1",
        "cwd": "/repo",
        "argv": ["python", "run.py"],
        "cpu_ids": [0, 1],
        "gpu_count": 1,
        "gpu_id": 0,
    }


def test_gpu_binding_selects_the_device() -> None:
    parsed = _parse_srun(_with({"--gpu-bind": "--gpu-bind=map_gpu:2"}))

    assert parsed["gpu_id"] == 2


@pytest.mark.parametrize(
    "bad",
    [
        "--gpu-bind=other:1",
        "--gpu-bind=map_gpu:x",
        "--gpu-bind=map_gpu:-1",
    ],
)
def test_unsupported_gpu_binding_is_refused(bad: str) -> None:
    with pytest.raises(ValueError, match="unsupported experiment run GPU binding"):
        _parse_srun(_with({"--gpu-bind": bad}))


def test_unsupported_cpu_binding_is_refused() -> None:
    with pytest.raises(ValueError, match="unsupported experiment run CPU binding"):
        _parse_srun(_with({"--cpu-bind": "--cpu-bind=none"}))


def test_unknown_srun_option_is_refused() -> None:
    with pytest.raises(ValueError, match="unsupported experiment run srun option"):
        _parse_srun(["--bogus", "python", "run.py"])


def test_chdir_without_a_path_is_refused() -> None:
    with pytest.raises(ValueError, match="--chdir is missing its path"):
        _parse_srun(["--chdir"])


def test_missing_command_is_refused() -> None:
    argv = [
        "--nodelist=gpuarm1",
        "--chdir",
        "/repo",
        "--cpu-bind=mask_cpu:0x1",
        "--cpus-per-task=1",
        "--nodes=1",
        "--ntasks=1",
    ]

    with pytest.raises(ValueError, match="missing node, cwd, CPU mask, or argv"):
        _parse_srun(argv)


def test_empty_cpu_mask_is_refused() -> None:
    with pytest.raises(ValueError, match="CPU mask is empty"):
        _parse_srun(_with({"--cpu-bind": "--cpu-bind=mask_cpu:0x0"}))


def test_cpu_mask_larger_than_the_step_envelope_is_refused() -> None:
    with pytest.raises(ValueError, match="exceeds its Slurm CPU envelope"):
        _parse_srun(_with({"--cpus-per-task": "--cpus-per-task=1"}))


@pytest.mark.parametrize("count", ["--gpus=gh200:2", "--gpus=gh200:3"])
def test_more_than_one_gpu_per_node_is_refused(count: str) -> None:
    with pytest.raises(ValueError, match="one GPU per node"):
        _parse_srun(_with({"--gpus": count}))


def test_missing_single_node_single_task_is_refused() -> None:
    with pytest.raises(ValueError, match="missing node, cwd, CPU mask, or argv"):
        _parse_srun(_with({"--nodes": "--nodes=2"}))


def test_log_path_prefers_attempt_identity_then_explicit_output(tmp_path: Path) -> None:
    attempt = tmp_path / "runs" / "variant_a__seed42" / "attempt1"
    assert (
        worker_dispatch._log_path(
            {"OUT_DIR": str(attempt), "LOG_DIR": str(tmp_path / "logs")}, "/repo", []
        )
        == tmp_path / "logs" / "variant_a__seed42__attempt1.log"
    )
    assert worker_dispatch._log_path(
        {}, "/repo", ["python", "run.py", "--out", "custom.log"]
    ) == Path("custom.log")
    assert worker_dispatch._log_path({}, "/repo", ["python", "run.py"]) == Path(
        "/repo/experiment_run_worker_dispatch.log"
    )


def test_write_result_atomically_records_exit_code(tmp_path: Path) -> None:
    worker_dispatch._write_result(tmp_path, "request-1", 17)

    result = tmp_path / "request-1.json"
    assert json.loads(result.read_text(encoding="utf-8")) == {"returncode": 17}
    assert not result.with_suffix(".tmp").exists()


def test_gpu_device_selection_handles_cpu_request_and_invalid_binding() -> None:
    assert (
        worker_dispatch._gpu_device_for_request({"gpu_count": 0, "gpu_id": 99}, ["GPU-0"]) is None
    )
    assert (
        worker_dispatch._gpu_device_for_request({"gpu_count": 1, "gpu_id": 1}, ["GPU-0", "GPU-1"])
        == "GPU-1"
    )
    with pytest.raises(RuntimeError, match="allocation exposes 1 visible GPU"):
        worker_dispatch._gpu_device_for_request({"gpu_count": 1, "gpu_id": 1}, ["GPU-0"])


@pytest.mark.parametrize(
    ("gpu_count", "visible_devices", "expected_device"),
    [(0, "", None), (1, "GPU-0, GPU-1", "GPU-1")],
)
def test_launch_builds_child_environment_and_closes_log_stream(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    gpu_count: int,
    visible_devices: str,
    expected_device: str | None,
) -> None:
    log_path = tmp_path / "worker.log"
    preexec_cpu_ids: list[set[int]] = []
    captured: dict[str, Any] = {}
    os_module: Any = vars(worker_dispatch)["os"]
    subprocess_module: Any = vars(worker_dispatch)["subprocess"]
    monkeypatch.setenv("RESUME_CHECKPOINT", "parent-checkpoint")
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", visible_devices)
    monkeypatch.setattr(
        os_module,
        "sched_setaffinity",
        lambda _pid, cpus: preexec_cpu_ids.append(set(cpus)),
    )

    def fake_popen(argv: list[str], **kwargs: Any) -> SimpleNamespace:
        captured["argv"] = argv
        captured.update(kwargs)
        kwargs["preexec_fn"]()
        return SimpleNamespace(pid=1234, poll=lambda: None)

    monkeypatch.setattr(subprocess_module, "Popen", fake_popen)
    payload: dict[str, Any] = {
        "argv": ["python", "train.py"],
        "cwd": str(tmp_path),
        "cpu_ids": [3, 5],
        "gpu_count": gpu_count,
        "gpu_id": 1,
        "env": {"GPU_ID": "requested"},
        "job_id": "77",
        "request_id": "request-1",
        "stdout_path": str(log_path),
    }

    process = worker_dispatch._launch(payload, tmp_path / "results")

    child_env = captured["env"]
    assert child_env["SLURM_JOB_ID"] == "77"
    assert "RESUME_CHECKPOINT" not in child_env
    assert preexec_cpu_ids == [{3, 5}]
    assert captured["cwd"] == str(tmp_path)
    assert captured["stdout"].closed
    assert vars(process)["_experiment_run_log_path"] == str(log_path)
    assert vars(process)["_experiment_run_request_id"] == "request-1"
    if expected_device is None:
        assert "CUDA_VISIBLE_DEVICES" not in child_env
    else:
        assert child_env["CUDA_VISIBLE_DEVICES"] == expected_device
        assert child_env["GPU_ID"] == expected_device


def test_launch_rejects_gpu_request_without_slurm_device_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)
    payload: dict[str, Any] = {
        "argv": ["python", "train.py"],
        "cwd": str(tmp_path),
        "cpu_ids": [0],
        "gpu_count": 1,
        "gpu_id": 0,
        "env": {},
        "job_id": "77",
        "request_id": "request-1",
        "stdout_path": "",
    }

    with pytest.raises(RuntimeError, match="no Slurm CUDA_VISIBLE_DEVICES binding"):
        worker_dispatch._launch(payload, tmp_path / "results")


def test_request_shim_waits_for_result_and_forwards_whitelisted_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    queue = tmp_path / "queue"
    signal_module: Any = vars(worker_dispatch)["signal"]
    uuid_module: Any = vars(worker_dispatch)["uuid"]
    os_module: Any = vars(worker_dispatch)["os"]
    time_module: Any = vars(worker_dispatch)["time"]
    monkeypatch.setenv("SLURM_JOB_ID", "991")
    pending, _claimed, results, ready = worker_dispatch._paths(queue, "gpuarm1")
    ready.parent.mkdir(parents=True)
    ready.write_text("ready", encoding="utf-8")
    monkeypatch.setenv("EXPERIMENT_RUN_WORKER_QUEUE", str(queue))
    for key in worker_dispatch.ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("VARIANT", "variant_a0")
    monkeypatch.setenv("PRIVATE_TOKEN", "not-exported")
    monkeypatch.setattr(sys, "argv", ["worker_dispatch", "--srun-shim", *VALID])
    monkeypatch.setattr(signal_module, "signal", lambda *_args: None)
    monkeypatch.setattr(uuid_module, "uuid4", lambda: SimpleNamespace(hex="req-1"))
    monkeypatch.setattr(os_module, "readlink", lambda _fd: "pipe:[stdout]")

    def publish_result(_seconds: float) -> None:
        request = json.loads((pending / "req-1.json").read_text(encoding="utf-8"))
        assert request["env"] == {"VARIANT": "variant_a0"}
        results.mkdir(parents=True, exist_ok=True)
        (results / "req-1.json").write_text(json.dumps({"returncode": 23}), encoding="utf-8")

    monkeypatch.setattr(time_module, "sleep", publish_result)

    assert worker_dispatch._request() == 23
    assert (
        json.loads((pending / "req-1.json").read_text(encoding="utf-8"))["stdout_path"]
        == "pipe:[stdout]"
    )


@pytest.mark.parametrize("launch_error", [None, RuntimeError("launch refused")])
def test_manager_dispatches_requests_and_records_completion_or_launch_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, launch_error: RuntimeError | None
) -> None:
    queue = tmp_path / "queue"
    os_module: Any = vars(worker_dispatch)["os"]
    job_id = "992"
    node = "gpuarm1.domain"
    monkeypatch.setenv("SLURM_JOB_ID", job_id)
    pending, claimed, results, ready = worker_dispatch._paths(queue, node)
    pending.mkdir(parents=True)
    request = {
        "request_id": "req-2",
        "node": node,
        "cpu_ids": [2, 4],
        "gpu_count": 0,
        "gpu_id": 0,
        "argv": ["python", "worker.py"],
        "env": {},
        "cwd": str(tmp_path),
        "stdout_path": "",
    }
    (pending / "req-2.json").write_text(json.dumps(request), encoding="utf-8")
    done_marker = tmp_path / "allocation.done"
    done_marker.touch()
    monkeypatch.setenv("EXPERIMENT_RUN_WORKER_QUEUE", str(queue))
    monkeypatch.setenv("SLURMD_NODENAME", node)
    monkeypatch.setenv("EXPERIMENT_RUN_OUT_DIR", str(tmp_path / "run"))
    monkeypatch.setenv("EXPERIMENT_RUN_ALLOCATION_DONE_MARKER", str(done_marker))
    monkeypatch.setattr(os_module, "sched_getaffinity", lambda _pid: {2, 4})
    monkeypatch.setattr(
        worker_dispatch, "available_resources", lambda: {"memory_limit_bytes": 1024}
    )
    monkeypatch.setattr(worker_dispatch, "gpu_memory_inventory", lambda: ["GPU-0"])

    def launch(_payload: dict[str, Any], _results: Path) -> SimpleNamespace:
        if launch_error is not None:
            raise launch_error
        return SimpleNamespace(pid=123, poll=lambda: 5)

    monkeypatch.setattr(worker_dispatch, "_launch", launch)

    assert worker_dispatch._manager() == 0

    completed = claimed.parent / "completed" / "req-2.json"
    assert completed.is_file()
    assert json.loads((results / "req-2.json").read_text(encoding="utf-8")) == {
        "returncode": 127 if launch_error else 5
    }
    assert json.loads(ready.read_text(encoding="utf-8")) == {
        "node": "gpuarm1",
        "job_id": job_id,
        "cpu_ids": [2, 4],
        "memory_limit_bytes": 1024,
        "gpu_memory": ["GPU-0"],
    }


def test_request_requires_worker_queue_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EXPERIMENT_RUN_WORKER_QUEUE", raising=False)

    with pytest.raises(RuntimeError, match="EXPERIMENT_RUN_WORKER_QUEUE is not set"):
        worker_dispatch._request()


def test_request_times_out_when_manager_never_becomes_ready(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    queue = tmp_path / "queue"
    monotonic_values = iter([100.0, 100.0, 160.0])
    time_module: Any = vars(worker_dispatch)["time"]
    slept: list[float] = []
    monkeypatch.setenv("SLURM_JOB_ID", "993")
    monkeypatch.setenv("EXPERIMENT_RUN_WORKER_QUEUE", str(queue))
    monkeypatch.setattr(sys, "argv", ["worker_dispatch", *VALID])
    monkeypatch.setattr(time_module, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(time_module, "sleep", slept.append)

    with pytest.raises(TimeoutError, match="persistent worker manager did not become ready"):
        worker_dispatch._request()

    assert slept == [0.2]


def test_request_signal_marks_pending_request_cancelled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    queue = tmp_path / "queue"
    signal_module: Any = vars(worker_dispatch)["signal"]
    time_module: Any = vars(worker_dispatch)["time"]
    uuid_module: Any = vars(worker_dispatch)["uuid"]
    handlers: dict[int, Any] = {}
    monkeypatch.setenv("SLURM_JOB_ID", "994")
    monkeypatch.setenv("EXPERIMENT_RUN_WORKER_QUEUE", str(queue))
    _pending, _claimed, _results, ready = worker_dispatch._paths(queue, "gpuarm1")
    ready.parent.mkdir(parents=True)
    ready.touch()
    monkeypatch.setattr(sys, "argv", ["worker_dispatch", "--srun-shim", *VALID])
    monkeypatch.setattr(uuid_module, "uuid4", lambda: SimpleNamespace(hex="cancel-1"))
    monkeypatch.setattr(
        signal_module, "signal", lambda signum, handler: handlers.__setitem__(signum, handler)
    )

    def send_sigterm(_seconds: float) -> None:
        handlers[signal_module.SIGTERM](signal_module.SIGTERM, None)

    monkeypatch.setattr(time_module, "sleep", send_sigterm)

    with pytest.raises(SystemExit, match="143"):
        worker_dispatch._request()

    cancelled = ready.parent / "cancelled" / "cancel-1.cancel"
    assert cancelled.is_file()


def test_launch_uses_requested_log_when_stdout_is_a_pipe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    os_module: Any = vars(worker_dispatch)["os"]
    subprocess_module: Any = vars(worker_dispatch)["subprocess"]
    requested_log = tmp_path / "requested.log"
    captured: dict[str, Any] = {}
    monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)
    monkeypatch.setattr(os_module, "sched_setaffinity", lambda *_args: None)

    def fake_popen(argv: list[str], **kwargs: Any) -> SimpleNamespace:
        captured["argv"] = argv
        captured.update(kwargs)
        return SimpleNamespace(pid=1234, poll=lambda: None)

    monkeypatch.setattr(subprocess_module, "Popen", fake_popen)
    payload: dict[str, Any] = {
        "argv": ["python", "train.py", "--out", str(requested_log)],
        "cwd": str(tmp_path),
        "cpu_ids": [0],
        "gpu_count": 0,
        "gpu_id": 0,
        "env": {},
        "job_id": "995",
        "request_id": "pipe-1",
        "stdout_path": "pipe:[12345]",
    }

    worker_dispatch._launch(payload, tmp_path / "results")

    assert requested_log.is_file()
    assert captured["stdout"].closed


def test_launch_refuses_unresolved_gpu_device(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "GPU-0")
    monkeypatch.setattr(worker_dispatch, "_gpu_device_for_request", lambda *_args: None)
    payload: dict[str, Any] = {
        "argv": ["python", "train.py"],
        "cwd": str(tmp_path),
        "cpu_ids": [0],
        "gpu_count": 1,
        "gpu_id": 0,
        "env": {},
        "job_id": "999",
        "request_id": "unresolved-gpu",
        "stdout_path": "",
    }

    with pytest.raises(RuntimeError, match="GPU worker request resolved without a visible GPU"):
        worker_dispatch._launch(payload, tmp_path / "results")


def test_manager_cancels_running_worker_and_records_final_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    queue = tmp_path / "queue"
    os_module: Any = vars(worker_dispatch)["os"]
    signal_module: Any = vars(worker_dispatch)["signal"]
    time_module: Any = vars(worker_dispatch)["time"]
    job_id = "996"
    node = "gpuarm1"
    monkeypatch.setenv("SLURM_JOB_ID", job_id)
    pending, claimed, results, ready = worker_dispatch._paths(queue, node)
    pending.mkdir(parents=True)
    request = {
        "request_id": "cancelled-worker",
        "node": node,
        "cpu_ids": [2, 4],
        "gpu_count": 0,
        "gpu_id": 0,
        "argv": ["python", "worker.py"],
        "env": {},
        "cwd": str(tmp_path),
        "stdout_path": "",
    }
    (pending / "cancelled-worker.json").write_text(json.dumps(request), encoding="utf-8")
    cancelled = pending.parent / "cancelled"
    cancelled.mkdir()
    done_marker = tmp_path / "allocation.done"
    done_marker.touch()
    monkeypatch.setenv("EXPERIMENT_RUN_WORKER_QUEUE", str(queue))
    monkeypatch.setenv("SLURMD_NODENAME", node)
    monkeypatch.setenv("EXPERIMENT_RUN_OUT_DIR", str(tmp_path / "run"))
    monkeypatch.setenv("EXPERIMENT_RUN_ALLOCATION_DONE_MARKER", str(done_marker))
    monkeypatch.setattr(os_module, "sched_getaffinity", lambda _pid: {2, 4})
    killed_signals: list[int] = []

    def missing_process(pid: int, signum: int) -> None:
        assert pid == 234
        killed_signals.append(signum)
        raise ProcessLookupError

    monkeypatch.setattr(os_module, "killpg", missing_process)
    monkeypatch.setattr(
        worker_dispatch, "available_resources", lambda: {"memory_limit_bytes": 1024}
    )
    monkeypatch.setattr(worker_dispatch, "gpu_memory_inventory", lambda: [])
    monotonic_values = iter([100.0, 160.0])
    monkeypatch.setattr(time_module, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(time_module, "sleep", lambda _seconds: None)
    poll_values = iter([None, None, None, 9])

    def launch(_payload: dict[str, Any], _results: Path) -> SimpleNamespace:
        # The cancel arrives while the worker is running, so it is signalled only after launch.
        (cancelled / "cancelled-worker.cancel").touch()
        return SimpleNamespace(pid=234, poll=lambda: next(poll_values))

    monkeypatch.setattr(worker_dispatch, "_launch", launch)

    assert worker_dispatch._manager() == 0

    assert json.loads((results / "cancelled-worker.json").read_text(encoding="utf-8")) == {
        "returncode": 9
    }
    assert (claimed.parent / "completed" / "cancelled-worker.json").is_file()
    assert killed_signals == [signal_module.SIGTERM, signal_module.SIGKILL]


def test_main_routes_manager_and_shim_modes(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(worker_dispatch, "_manager", lambda: 6)

    def request() -> int:
        calls.append(sys.argv[:])
        return 7

    monkeypatch.setattr(worker_dispatch, "_request", request)
    monkeypatch.setattr(sys, "argv", ["worker_dispatch", "--manager"])

    assert worker_dispatch.main() == 6

    monkeypatch.setattr(sys, "argv", ["worker_dispatch", "--srun-shim", "--nodelist=gpuarm1"])
    assert worker_dispatch.main() == 7
    assert calls == [["worker_dispatch", "--nodelist=gpuarm1"]]


def test_manager_rejects_missing_queue_or_job_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("EXPERIMENT_RUN_WORKER_QUEUE", raising=False)
    monkeypatch.delenv("SLURM_JOB_ID", raising=False)

    with pytest.raises(RuntimeError, match="worker manager requires"):
        worker_dispatch._manager()


def test_manager_skips_malformed_and_misrouted_requests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    queue = tmp_path / "queue"
    os_module: Any = vars(worker_dispatch)["os"]
    job_id = "997"
    node = "gpuarm1"
    monkeypatch.setenv("SLURM_JOB_ID", job_id)
    pending, claimed, _results, ready = worker_dispatch._paths(queue, node)
    pending.mkdir(parents=True)
    malformed = pending / "a-malformed.json"
    malformed.write_text("{not json", encoding="utf-8")
    misrouted = pending / "b-other-node.json"
    misrouted.write_text(json.dumps({"node": "gpuarm2", "request_id": "foreign"}))
    done_marker = tmp_path / "allocation.done"
    done_marker.touch()
    monkeypatch.setenv("EXPERIMENT_RUN_WORKER_QUEUE", str(queue))
    monkeypatch.setenv("SLURMD_NODENAME", node)
    monkeypatch.setenv("EXPERIMENT_RUN_OUT_DIR", str(tmp_path / "run"))
    monkeypatch.setenv("EXPERIMENT_RUN_ALLOCATION_DONE_MARKER", str(done_marker))
    monkeypatch.setattr(os_module, "sched_getaffinity", lambda _pid: {0})
    monkeypatch.setattr(
        worker_dispatch, "available_resources", lambda: {"memory_limit_bytes": 1024}
    )
    monkeypatch.setattr(worker_dispatch, "gpu_memory_inventory", lambda: [])

    def remove_unclaimed_requests(_seconds: float) -> None:
        malformed.unlink()
        misrouted.unlink()

    monkeypatch.setattr(vars(worker_dispatch)["time"], "sleep", remove_unclaimed_requests)
    monkeypatch.setattr(
        worker_dispatch, "_launch", lambda *_args: pytest.fail("invalid request was launched")
    )

    assert worker_dispatch._manager() == 0

    assert ready.is_file()
    assert list(claimed.iterdir()) == []


def test_manager_uses_default_allocation_done_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    queue = tmp_path / "queue"
    output = tmp_path / "run"
    os_module: Any = vars(worker_dispatch)["os"]
    monkeypatch.setenv("SLURM_JOB_ID", "998")
    monkeypatch.setenv("EXPERIMENT_RUN_WORKER_QUEUE", str(queue))
    monkeypatch.setenv("SLURMD_NODENAME", "gpuarm1")
    monkeypatch.setenv("EXPERIMENT_RUN_OUT_DIR", str(output))
    monkeypatch.delenv("EXPERIMENT_RUN_ALLOCATION_DONE_MARKER", raising=False)
    done_marker = ExperimentRunArtifactLayout(output).root_file("allocation_controller.exit")
    done_marker.parent.mkdir(parents=True)
    done_marker.touch()
    monkeypatch.setattr(os_module, "sched_getaffinity", lambda _pid: {0})
    monkeypatch.setattr(
        worker_dispatch, "available_resources", lambda: {"memory_limit_bytes": None}
    )
    monkeypatch.setattr(worker_dispatch, "gpu_memory_inventory", lambda: [])

    assert worker_dispatch._manager() == 0

    _pending, _claimed, _results, ready = worker_dispatch._paths(queue, "gpuarm1")
    assert json.loads(ready.read_text(encoding="utf-8")) == {
        "node": "gpuarm1",
        "job_id": "998",
        "cpu_ids": [0],
        "memory_limit_bytes": None,
        "gpu_memory": [],
    }


def test_script_wraps_dispatch_errors_with_worker_exit_code(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("EXPERIMENT_RUN_WORKER_QUEUE", raising=False)
    monkeypatch.setattr(sys, "argv", ["worker_dispatch.py", "--srun-shim"])

    with pytest.raises(SystemExit, match="127"):
        runpy.run_path(str(Path(worker_dispatch.__file__)), run_name="__main__")

    assert "experiment run worker dispatch error: EXPERIMENT_RUN_WORKER_QUEUE is not set" in (
        capsys.readouterr().err
    )
