"""Resource-aware worker sizing and cache namespaces without changing host settings."""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
from pathlib import Path
from typing import Any


def _number(path: Path) -> int | None:
    """Read a cgroup integer, treating an unlimited or unavailable value as unknown."""
    try:
        value = path.read_text().strip()
        return int(value) if value != "max" else None
    except (OSError, ValueError):
        return None


def cgroup_directory(proc: Path = Path("/proc/self/cgroup")) -> Path | None:
    """Resolve the current cgroup v2 path, refusing traversal outside the mount."""
    try:
        line = next(row for row in proc.read_text().splitlines() if row.startswith("0::"))
    except (OSError, StopIteration):
        return None
    mount = Path("/sys/fs/cgroup")
    directory = (mount / line[3:].lstrip("/")).resolve()
    return directory if directory.is_relative_to(mount) and directory.is_dir() else None


def _limits(directory: Path | None) -> tuple[int | None, int | None]:
    """Collect the tightest CPU quota and memory headroom across cgroup ancestors."""
    if directory is None:
        return None, None
    cpu_limits: list[int] = []
    memory_limits: list[int] = []
    for parent in (directory, *directory.parents):
        if not parent.is_relative_to("/sys/fs/cgroup"):
            break
        try:
            quota, period = (parent / "cpu.max").read_text().split()
            if quota != "max" and int(period) > 0:
                cpu_limits.append(max(1, int(quota) // int(period)))
        except (OSError, ValueError):
            pass
        limit = _number(parent / "memory.max")
        used = _number(parent / "memory.current")
        if limit is not None and used is not None:
            memory_limits.append(max(0, limit - used))
    return min(cpu_limits, default=None), min(memory_limits, default=None)


def _host_available() -> int | None:
    """Read the host available-memory estimate when exposed."""
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        pass
    return None


def budget(
    requested: int,
    worker_mib: int,
    *,
    available_bytes: int | None,
    affinity_cpus: int,
    quota_cpus: int | None = None,
    reserve_mib: int = 512,
) -> dict[str, Any]:
    """Size workers conservatively; unknown RAM admits one worker, not unlimited work."""
    if min(requested, worker_mib, affinity_cpus) < 1 or reserve_mib < 0:
        raise ValueError("Invalid worker budget")
    cpu = min(requested, affinity_cpus, quota_cpus or affinity_cpus)
    memory = (
        1
        if available_bytes is None
        else max(0, (available_bytes // (1024 * 1024) - reserve_mib) // worker_mib)
    )
    workers = min(cpu, memory)
    return {
        "status": "ok" if workers else "insufficient_resources",
        "workers": workers,
        "cpu_limit": cpu,
        "memory_limit": memory,
        "available_bytes": available_bytes,
        "worker_mib_estimate": worker_mib,
        "reserve_mib": reserve_mib,
    }


def discover_budget(requested: int, worker_mib: int, reserve_mib: int = 512) -> dict[str, Any]:
    """Combine affinity, cgroup ancestor quotas and available host memory."""
    affinity = (
        len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else os.cpu_count() or 1
    )
    quota, cgroup_ram = _limits(cgroup_directory())
    available = min((n for n in (_host_available(), cgroup_ram) if n is not None), default=None)
    return budget(
        requested,
        worker_mib,
        available_bytes=available,
        affinity_cpus=affinity,
        quota_cpus=quota,
        reserve_mib=reserve_mib,
    )


def cache_key(lock: Path, profile: str, tool_versions: dict[str, str]) -> str:
    """Separate CPU/GPU/analyzer caches by lock, ABI, platform and actual tool versions."""
    if not profile or not tool_versions or any(not v for v in tool_versions.values()):
        raise ValueError("Cache identity requires a profile and actual tool versions")
    payload = {
        "lock": hashlib.sha256(lock.read_bytes()).hexdigest(),
        "profile": profile,
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "machine": platform.machine(),
        "system": platform.system(),
        "tools": tool_versions,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def schedule(
    groups: dict[str, tuple[float, int]], workers: int, memory_mib: int
) -> list[list[str]]:
    """Plan duration-balanced waves, respecting per-group memory and concurrent limits."""
    if workers < 1 or memory_mib < 1:
        raise ValueError("Invalid scheduling capacity")
    for seconds, ram in groups.values():
        if not math.isfinite(seconds) or seconds < 0 or not 0 < ram <= memory_mib:
            raise ValueError("Invalid group duration or memory estimate")
    waves: list[list[str]] = []
    used: list[int] = []
    for name, (_, ram) in sorted(groups.items(), key=lambda item: (-item[1][0], item[0])):
        for i, wave in enumerate(waves):
            if len(wave) < workers and used[i] + ram <= memory_mib:
                wave.append(name)
                used[i] += ram
                break
        else:
            waves.append([name])
            used.append(ram)
    return waves
