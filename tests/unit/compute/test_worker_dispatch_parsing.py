"""Parsing of the fixed srun options that the experiment-run worker command accepts."""

from __future__ import annotations

import pytest

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
