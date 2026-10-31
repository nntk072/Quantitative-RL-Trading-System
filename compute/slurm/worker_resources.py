"""Build CPU/GPU-bound Slurm worker requests and sample allocation resources."""

from __future__ import annotations

import csv
import datetime as dt
import json
import math
import os
import pathlib
import subprocess
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]

WORKER_CPU_AFFINITY_GUARD = ROOT / "scripts" / "compute" / "slurm" / "verify_worker_cpu_affinity.py"

__all__ = [
    "ROOT",
    "WORKER_CPU_AFFINITY_GUARD",
    "available_resources",
    "cgroup_memory_file",
    "cpu_mask_for_range",
    "cpu_mask_for_slot",
    "gpu_memory_inventory",
    "expand_slurm_hosts",
    "plan_worker_capacity",
    "resolve_worker_nodes",
    "sample_resources",
    "utc",
    "worker_command",
    "worker_node_cpu_ids",
    "worker_node_resources",
]


def utc() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


def cgroup_memory_file(name: str) -> pathlib.Path | None:
    """Locate a memory-controller file under this process's cgroup."""
    root = pathlib.Path("/sys/fs/cgroup")
    try:
        entries = pathlib.Path("/proc/self/cgroup").read_text().splitlines()
    except OSError:
        entries = []
    for entry in entries:
        parts = entry.split(":", maxsplit=2)
        if len(parts) != 3:
            continue
        _hierarchy, controllers, relative = parts
        if controllers == "":
            base = root / relative.lstrip("/")
        elif "memory" in controllers.split(","):
            base = root / "memory" / relative.lstrip("/")
        else:
            continue
        candidate = base / name
        try:
            candidate.resolve().relative_to(root.resolve())
        except (OSError, ValueError):
            continue
        if candidate.is_file():
            return candidate
    for fallback in (root / name, root / "memory" / name):
        try:
            fallback.resolve().relative_to(root.resolve())
        except (OSError, ValueError):
            continue
        if fallback.is_file():
            return fallback
    return None


def available_resources() -> dict[str, Any]:
    mem_limit = 0
    memory = cgroup_memory_file("memory.max")
    if memory is not None:
        # Slurm task cgroups often report "max" while a parent job cgroup
        # carries the actual allocation limit. Use the tightest finite limit
        # visible from this task instead of treating that allocation as unbound.
        for parent in (memory, *memory.parents):
            if not parent.is_relative_to(pathlib.Path("/sys/fs/cgroup")):
                break
            candidate = parent / "memory.max"
            try:
                value = candidate.read_text().strip()
            except OSError:
                continue
            if value.isdigit() and 0 < int(value) < 2**60:
                mem_limit = int(value) if not mem_limit else min(mem_limit, int(value))
    if not mem_limit:
        memory = cgroup_memory_file("memory.limit_in_bytes")
        if memory is not None and memory.read_text().strip().isdigit():
            legacy_value = int(memory.read_text().strip())
            if 0 < legacy_value < 2**60:
                mem_limit = legacy_value
    cpu_ids = sorted(os.sched_getaffinity(0))
    return {
        "memory_limit_bytes": mem_limit,
        "cpu_affinity": len(cpu_ids),
        "cpu_ids": cpu_ids,
    }


def gpu_memory_inventory() -> list[dict[str, Any]]:
    """Return memory capacity for GPUs visible to this Slurm task."""
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=index,uuid,memory.total,memory.free",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []
    records: list[dict[str, Any]] = []
    for line in result.stdout.splitlines():
        fields = [field.strip() for field in line.split(",")]
        if len(fields) != 4:
            continue
        try:
            records.append(
                {
                    "index": int(fields[0]),
                    "uuid": fields[1],
                    "total_bytes": int(fields[2]) * 1024**2,
                    "free_bytes": int(fields[3]) * 1024**2,
                }
            )
        except ValueError:
            continue
    visible = [item.strip() for item in os.environ.get("CUDA_VISIBLE_DEVICES", "").split(",")]
    if not visible:
        return records
    selected = [
        record
        for token in visible
        for record in records
        if token == str(record["index"]) or token == record["uuid"]
    ]
    return selected


def cpu_mask_for_slot(cpu_ids: list[int], slot: int, cpus: int) -> tuple[str, list[int]]:
    """Assign a distinct contiguous slice of allocated CPU IDs to one worker."""
    if slot < 0 or cpus <= 0:
        raise ValueError("CPU slot and worker CPU count must be non-negative/positive")
    return cpu_mask_for_range(cpu_ids, slot * cpus, cpus)


def cpu_mask_for_range(cpu_ids: list[int], start: int, cpus: int) -> tuple[str, list[int]]:
    """Assign an explicit contiguous range from the allocation CPU set."""
    if start < 0 or cpus <= 0:
        raise ValueError("CPU range start and worker CPU count must be non-negative/positive")
    selected = cpu_ids[start : start + cpus]
    if len(selected) != cpus:
        raise ValueError(f"CPU range needs {cpus} CPUs but only {len(selected)} remain")
    mask = sum(1 << cpu for cpu in selected)
    return f"0x{mask:x}", selected


def worker_node_cpu_ids(queue_root: pathlib.Path, job_id: str, node: str) -> list[int]:
    """Read the CPU set advertised by the persistent manager on one worker node."""
    ready = queue_root / job_id / node.split(".", maxsplit=1)[0] / "ready"
    try:
        metadata = json.loads(ready.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"worker manager CPU metadata is unavailable for {node}: {exc}") from exc
    node_key = node.split(".", maxsplit=1)[0]
    if metadata.get("node") != node_key or str(metadata.get("job_id")) != job_id:
        raise RuntimeError(f"worker manager CPU metadata identity mismatch for {node}")
    cpu_ids = metadata.get("cpu_ids")
    if (
        not isinstance(cpu_ids, list)
        or not cpu_ids
        or any(not isinstance(cpu, int) or cpu < 0 for cpu in cpu_ids)
        or len(set(cpu_ids)) != len(cpu_ids)
    ):
        raise RuntimeError(f"worker manager advertised an invalid CPU set for {node}")
    return sorted(cpu_ids)


def worker_node_resources(queue_root: pathlib.Path, job_id: str, node: str) -> dict[str, Any]:
    """Read validated CPU, RAM, and GPU capacity advertised by a node manager."""
    ready = queue_root / job_id / node.split(".", maxsplit=1)[0] / "ready"
    try:
        metadata = json.loads(ready.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError(
            f"worker manager resource metadata is unavailable for {node}: {exc}"
        ) from exc
    node_key = node.split(".", maxsplit=1)[0]
    if metadata.get("node") != node_key or str(metadata.get("job_id")) != job_id:
        raise RuntimeError(f"worker manager resource metadata identity mismatch for {node}")
    cpu_ids = metadata.get("cpu_ids")
    memory_limit = metadata.get("memory_limit_bytes", 0)
    gpus = metadata.get("gpu_memory", [])
    if (
        not isinstance(cpu_ids, list)
        or not cpu_ids
        or any(not isinstance(cpu, int) or cpu < 0 for cpu in cpu_ids)
        or len(set(cpu_ids)) != len(cpu_ids)
        or not isinstance(memory_limit, int)
        or memory_limit < 0
        or not isinstance(gpus, list)
        or any(
            not isinstance(gpu, dict)
            or not isinstance(gpu.get("total_bytes"), int)
            or not isinstance(gpu.get("free_bytes"), int)
            or gpu["total_bytes"] <= 0
            or gpu["free_bytes"] < 0
            for gpu in gpus
        )
    ):
        raise RuntimeError(f"worker manager advertised invalid resource metadata for {node}")
    return {
        "node": node_key,
        "cpu_ids": sorted(cpu_ids),
        "memory_limit_bytes": memory_limit,
        "gpu_memory": gpus,
    }


def plan_worker_capacity(
    node_resources: dict[str, dict[str, Any]],
    *,
    n_envs: int,
    data_source: str,
    gpus_per_node: int,
    max_workers_per_gpu: int = 9,
    gpu_memory_per_worker_gib: float = 8.0,
    gpu_memory_reserve_fraction: float = 0.2,
    cpu_reserve_per_node: int = 1,
    memory_reserve_gib: float = 64.0,
    memory_safety_factor: float = 1.35,
) -> dict[str, Any]:
    """Plan concurrent variant slots from per-node CPU, RAM, and GPU limits.

    The RAM estimates match the conservative experiment-run preflight. The GPU
    estimate reserves 20% of device memory and defaults to 8 GiB per worker;
    launchers can lower concurrency with ``max_workers_per_gpu`` when measured
    model peaks demand more headroom.
    """
    if n_envs not in {4, 8, 16, 32, 64}:
        raise ValueError("n-envs not benchmarked for memory: choose 4,8,16,32,64")
    if (
        gpus_per_node <= 0
        or max_workers_per_gpu <= 0
        or gpu_memory_per_worker_gib <= 0
        or not 0 <= gpu_memory_reserve_fraction < 1
        or cpu_reserve_per_node < 0
        or memory_reserve_gib < 0
        or memory_safety_factor < 1
    ):
        raise ValueError("worker resource planning limits are invalid")

    estimated_per_worker_gib = {4: 12, 8: 19, 16: 35, 32: 67, 64: 132}[n_envs]
    if data_source == "bundle" and n_envs == 64:
        estimated_per_worker_gib = 30
    minimum_cpus_per_worker = max(2, math.ceil(n_envs / 2))
    planned_nodes: dict[str, dict[str, Any]] = {}
    for node, resources in sorted(node_resources.items()):
        cpu_ids = list(resources.get("cpu_ids", []))
        memory_bytes = int(resources.get("memory_limit_bytes", 0))
        gpu_memory = list(resources.get("gpu_memory", []))[:gpus_per_node]
        cpu_capacity = max(
            0,
            (len(cpu_ids) - cpu_reserve_per_node) // minimum_cpus_per_worker,
        )
        if memory_bytes:
            memory_gib = memory_bytes / 1024**3
            memory_capacity = max(
                0,
                math.floor(
                    (memory_gib - memory_reserve_gib)
                    / (estimated_per_worker_gib * memory_safety_factor)
                ),
            )
        else:
            memory_gib = None
            # Without a cgroup or Slurm memory limit, admit only one worker;
            # do not mistake an unknown limit for unbounded RAM.
            memory_capacity = min(1, cpu_capacity)

        if gpu_memory:
            gpu_capacity = 0
            gpu_slots: list[int] = []
            for gpu in gpu_memory:
                total_gib = int(gpu["total_bytes"]) / 1024**3
                free_gib = int(gpu["free_bytes"]) / 1024**3
                usable_gib = min(
                    free_gib,
                    total_gib * (1.0 - gpu_memory_reserve_fraction),
                )
                slots = min(
                    max_workers_per_gpu,
                    max(0, math.floor(usable_gib / gpu_memory_per_worker_gib)),
                )
                gpu_slots.append(slots)
                gpu_capacity += slots
        else:
            # Older managers may not advertise VRAM. GH200 runs can still use
            # the configured share ceiling, while unknown types fail closed.
            gpu_capacity = (
                max_workers_per_gpu * gpus_per_node
                if str(resources.get("gpu_type", "")).lower() == "gh200"
                else gpus_per_node
            )
            gpu_slots = [gpu_capacity]
        capacity = min(cpu_capacity, memory_capacity, gpu_capacity)
        worker_cpus = (len(cpu_ids) - cpu_reserve_per_node) // capacity if capacity > 0 else 0
        if worker_cpus < minimum_cpus_per_worker:
            capacity = 0
            worker_cpus = 0
        planned_nodes[node] = {
            "workers": capacity,
            "worker_cpus": worker_cpus,
            "cpu_capacity": cpu_capacity,
            "memory_capacity": memory_capacity,
            "gpu_capacity": gpu_capacity,
            "estimated_worker_memory_gib": estimated_per_worker_gib,
            "memory_limit_gib": memory_gib,
            "gpu_slots_per_device": gpu_slots,
        }
    return {
        "workers": sum(int(item["workers"]) for item in planned_nodes.values()),
        "minimum_cpus_per_worker": minimum_cpus_per_worker,
        "memory_reserve_gib": memory_reserve_gib,
        "memory_safety_factor": memory_safety_factor,
        "gpu_memory_per_worker_gib": gpu_memory_per_worker_gib,
        "gpu_memory_reserve_fraction": gpu_memory_reserve_fraction,
        "max_workers_per_gpu": max_workers_per_gpu,
        "nodes": planned_nodes,
    }


def expand_slurm_hosts(node_list: str) -> list[str]:
    """Expand a Slurm host expression, preserving the scheduler's host order."""
    result = subprocess.run(
        ["scontrol", "show", "hostnames", node_list],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    if result.returncode != 0:
        raise ValueError(f"could not expand Slurm node list {node_list!r}: {result.stderr.strip()}")
    hosts = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not hosts or len(hosts) != len(set(hosts)):
        raise ValueError("Slurm node list expanded to no hosts or duplicate hosts")
    return hosts


def worker_command(
    command: list[str],
    *,
    node: str | None,
    gpu_type: str,
    cpus: int,
    gpu_count: int = 1,
    gpu_id: int = 0,
    available_gpu_count: int | None = None,
    cpu_mask: str | None = None,
    expected_cpu_ids: list[int] | None = None,
    step_cpus: int | None = None,
) -> list[str]:
    """Build a worker request with per-worker GPU count and allocation GPU index."""
    if node is None:
        return command
    visible_gpu_count = gpu_count if available_gpu_count is None else available_gpu_count
    if (
        gpu_count < 0
        or visible_gpu_count < 0
        or (gpu_count > 0 and visible_gpu_count == 0)
        or (visible_gpu_count > 0 and not 0 <= gpu_id < visible_gpu_count)
    ):
        raise ValueError("worker GPU count or binding index is invalid")
    if (cpu_mask is None) != (expected_cpu_ids is None):
        raise ValueError("CPU mask and expected CPU IDs must be provided together")
    allocated_cpus = cpus if step_cpus is None else step_cpus
    if allocated_cpus < cpus:
        raise ValueError("Slurm step CPU envelope cannot be smaller than the worker CPU mask")
    result = [
        "srun",
        "--overlap",
        "--nodes=1",
        "--ntasks=1",
        f"--nodelist={node}",
        f"--cpus-per-task={allocated_cpus}",
    ]
    if gpu_count:
        result.extend([f"--gpus={gpu_type}:{gpu_count}", f"--gpu-bind=map_gpu:{gpu_id}"])
    cpu_binding = f"mask_cpu:{cpu_mask}" if cpu_mask is not None else "cores"
    worker_command = command
    if cpu_mask is not None and expected_cpu_ids is not None:
        worker_command = [
            sys.executable,
            str(WORKER_CPU_AFFINITY_GUARD),
            "--expected-cpus",
            ",".join(str(cpu) for cpu in expected_cpu_ids),
            "--",
            *command,
        ]
    result.extend(
        [
            f"--cpu-bind={cpu_binding}",
            "--chdir",
            str(ROOT),
            "--export=ALL",
            *worker_command,
        ]
    )
    return result


def resolve_worker_nodes(raw: str | None, *, dry_run: bool) -> list[str]:
    if not raw:
        return []
    if dry_run:
        requested = [host.strip() for host in raw.split(",") if host.strip()]
        if not requested or len(requested) != len(set(requested)):
            raise ValueError("worker node list is empty or contains duplicates")
        return requested
    # Inside an `srun` control step SLURM_JOB_NODELIST may describe only that
    # step's nodes; SLURM_NODELIST retains the full parent allocation.
    job_node_list = os.getenv("SLURM_NODELIST") or os.getenv("SLURM_JOB_NODELIST")
    if not job_node_list:
        raise ValueError("--worker-nodes requires an existing multi-node Slurm allocation")
    allocated = set(expand_slurm_hosts(job_node_list))
    requested = expand_slurm_hosts(raw)
    outside = sorted(set(requested) - allocated)
    if outside:
        raise ValueError(f"worker nodes are outside the Slurm allocation: {outside}")
    return requested


def sample_resources(path: pathlib.Path) -> None:
    def read(name: str) -> str:
        p = cgroup_memory_file(name)
        return p.read_text().strip().replace("\n", ";") if p is not None else ""

    gpu_util = gpu_memory = ""
    try:
        gpu = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,memory.used",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if gpu.returncode == 0:
            gpu_util, _, gpu_memory = gpu.stdout.strip().partition(", ")
    except (OSError, subprocess.TimeoutExpired):
        pass
    with path.open("a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(
            [
                utc(),
                os.getloadavg()[0],
                read("memory.current"),
                read("memory.max"),
                read("memory.peak"),
                read("memory.events"),
                gpu_util,
                gpu_memory,
            ]
        )
        f.flush()
