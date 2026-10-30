from __future__ import annotations

import pytest

from compute.slurm import worker_resources as resources


def test_worker_nodes_use_parent_allocation_from_nested_step(monkeypatch) -> None:
    monkeypatch.setenv("SLURM_NODELIST", "gpuarm[1-2]")
    monkeypatch.setenv("SLURM_JOB_NODELIST", "gpuarm1")
    expanded = {
        "gpuarm[1-2]": ["gpuarm1", "gpuarm2"],
        "gpuarm1,gpuarm2": ["gpuarm1", "gpuarm2"],
    }
    monkeypatch.setattr(resources, "expand_slurm_hosts", lambda value: expanded[value])

    assert resources.resolve_worker_nodes("gpuarm1,gpuarm2", dry_run=False) == [
        "gpuarm1",
        "gpuarm2",
    ]


def test_cpu_mask_selects_the_requested_slot_from_allocated_ids() -> None:
    mask, selected = resources.cpu_mask_for_slot([2, 4, 7, 9], slot=1, cpus=2)

    assert selected == [7, 9]
    assert mask == "0x280"


def test_cpu_mask_rejects_a_slot_outside_the_allocation() -> None:
    with pytest.raises(ValueError, match="only 1 remain"):
        resources.cpu_mask_for_slot([3, 5, 7], slot=1, cpus=2)


def test_worker_command_binds_requested_gpu_and_cpu_mask() -> None:
    command = resources.worker_command(
        ["python", "-m", "training.cli"],
        node="gpuarm2",
        gpu_type="gh200",
        cpus=2,
        gpu_count=1,
        gpu_id=1,
        available_gpu_count=2,
        cpu_mask="0x280",
        expected_cpu_ids=[7, 9],
    )

    assert "--nodelist=gpuarm2" in command
    assert "--gpus=gh200:1" in command
    assert "--gpu-bind=map_gpu:1" in command
    assert "--cpu-bind=mask_cpu:0x280" in command
    assert command[-3:] == ["python", "-m", "training.cli"]
