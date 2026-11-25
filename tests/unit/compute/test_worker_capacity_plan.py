"""Worker-slot planning keeps CPU, RAM and GPU headroom; each expected value is hand-computed."""

from __future__ import annotations

from typing import Any

import pytest

from compute.slurm.worker_resources import plan_worker_capacity

GiB = 1024**3


def _node(cpus: int, *, memory_gib: float, gpu_memory: list[dict[str, Any]] | None = None) -> dict:
    return {
        "cpu_ids": list(range(cpus)),
        "memory_limit_bytes": int(memory_gib * GiB),
        "gpu_memory": gpu_memory or [],
        "gpu_type": "gh200",
    }


def test_cpu_bound_plan_keeps_one_core_and_the_minimum_worker_size() -> None:
    # n_envs=4 needs 2 CPUs per worker, so (8 - 1 reserved) // 2 = 3 CPU slots.
    # RAM: (256 - 64 reserved) / (12 GiB * 1.35) = 11.85, so 11 slots.
    # GPU (gh200 without VRAM record): 9 * 1 = 9 slots. The CPU bound of 3 wins.
    plan = plan_worker_capacity(
        {"n1": _node(8, memory_gib=256)}, n_envs=4, data_source="frames", gpus_per_node=1
    )

    node = plan["nodes"]["n1"]
    assert (node["cpu_capacity"], node["memory_capacity"], node["gpu_capacity"]) == (3, 11, 9)
    assert node["workers"] == 3
    assert node["worker_cpus"] == 2
    assert plan["workers"] == 3


def test_unknown_memory_admits_one_worker_instead_of_trusting_host_ram() -> None:
    node = _node(8, memory_gib=0)
    node["memory_limit_bytes"] = 0

    plan = plan_worker_capacity({"n1": node}, n_envs=4, data_source="frames", gpus_per_node=1)

    assert plan["nodes"]["n1"]["memory_capacity"] == 1
    assert plan["nodes"]["n1"]["workers"] == 1


def test_node_below_the_minimum_worker_cpu_count_plans_no_worker() -> None:
    # (2 - 1 reserved) // 2 CPUs per worker = 0 CPU slots.
    plan = plan_worker_capacity(
        {"n1": _node(2, memory_gib=256)}, n_envs=4, data_source="frames", gpus_per_node=1
    )

    assert plan["nodes"]["n1"]["workers"] == 0
    assert plan["nodes"]["n1"]["worker_cpus"] == 0


def test_gpu_slots_keep_twenty_percent_of_device_memory_reserved() -> None:
    # 80 GiB free and total: usable = 80 - 20% of 80 = 64 GiB; 64 // 8 GiB per worker = 8 slots.
    # Without the reserve this would be 10 slots, capped at the default 9.
    gpu = [{"total_bytes": 80 * GiB, "free_bytes": 80 * GiB}]
    plan = plan_worker_capacity(
        {"n1": _node(40, memory_gib=256, gpu_memory=gpu)},
        n_envs=4,
        data_source="frames",
        gpus_per_node=1,
    )

    node = plan["nodes"]["n1"]
    assert node["gpu_slots_per_device"] == [8]
    assert node["gpu_capacity"] == 8
    # min(cpu 19, ram 11, gpu 8) = 8 workers; (40 - 1) // 8 = 4 CPUs each.
    assert (node["workers"], node["worker_cpus"]) == (8, 4)


@pytest.mark.parametrize("n_envs", [3, 128])
def test_unbenchmarked_environment_counts_are_refused(n_envs: int) -> None:
    with pytest.raises(ValueError, match="not benchmarked"):
        plan_worker_capacity(
            {"n1": _node(8, memory_gib=256)}, n_envs=n_envs, data_source="frames", gpus_per_node=1
        )
