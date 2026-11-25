"""Read the resource envelope granted to this process from live cgroup, Slurm, and CUDA state.

Capacity is never inferred from host totals. Cores come from the affinity mask
and cgroup ``cpu.max``; RAM comes from the tightest finite cgroup ``memory.max``
on the path to the root; GPUs come only from ``CUDA_VISIBLE_DEVICES``. A value
that cannot be read is reported as ``None`` so admission refuses the request
rather than guessing. Only cgroup v2 is read for memory and CPU quota.
"""

from __future__ import annotations

import math
import os
import shutil
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from compute.slurm.resources import allocation_cgroup_file, cgroup_file

CGROUP_ROOT = Path("/sys/fs/cgroup")
PROC_SELF_CGROUP = Path("/proc/self/cgroup")
_NO_DEVICE_TOKENS = frozenset({"", "-1", "NoDevFiles"})
_LIMIT_CEILING = 2**60


@dataclass(frozen=True, slots=True)
class GpuDevice:
    """One CUDA device made visible to this process, with memory when it was measured."""

    token: str
    total_bytes: int | None
    free_bytes: int | None


@dataclass(frozen=True, slots=True)
class NodeInventory:
    """Resources this process can use now; ``None`` marks a value that was not measured."""

    cpu_ids: tuple[int, ...]
    cpu_quota_cores: float | None
    memory_limit_bytes: int | None
    memory_current_bytes: int | None
    memory_peak_bytes: int | None
    gpus: tuple[GpuDevice, ...]
    scratch_free_bytes: int | None
    slurm_cpus_per_task: int | None
    slurm_gpus_on_node: int | None
    slurm_cpu_bind: str | None

    @property
    def granted_cpus(self) -> int:
        """Cores this process may use: affinity, capped by cgroup quota and Slurm's CPU count.

        Returns:
            The smallest of the affinity count, the floor of the cgroup quota, and Slurm's CPU count, never below zero.
        """
        limits = [len(self.cpu_ids)]
        if self.cpu_quota_cores is not None:
            limits.append(math.floor(self.cpu_quota_cores))
        if self.slurm_cpus_per_task is not None:
            limits.append(self.slurm_cpus_per_task)
        return max(0, min(limits))


def read_inventory(
    *,
    proc_cgroup: Path | None = None,
    cgroup_root: Path | None = None,
    environ: Mapping[str, str] | None = None,
    scratch_path: Path | None = None,
    free_bytes_of: Callable[[Path], int] | None = None,
    gpu_records: Sequence[Mapping[str, Any]] = (),
) -> NodeInventory:
    """Read this process's live resource envelope.

    Args:
        proc_cgroup: Process cgroup file; defaults to ``/proc/self/cgroup``.
        cgroup_root: Cgroup mount root; defaults to ``/sys/fs/cgroup``.
        environ: Environment to read Slurm and CUDA variables from; defaults to ``os.environ``.
        scratch_path: Directory whose free space is measured, or ``None`` to leave it unknown.
        free_bytes_of: Free-space function for ``scratch_path``; defaults to ``shutil``.
        gpu_records: Per-device records (index, uuid, total_bytes, free_bytes) from nvidia-smi.

    Returns:
        The inventory. Malformed cgroup or Slurm values raise ``ValueError``.
    """
    root = cgroup_root or CGROUP_ROOT
    proc = proc_cgroup or PROC_SELF_CGROUP
    env: Mapping[str, str] = os.environ if environ is None else environ
    scratch_free: int | None = None
    if scratch_path is not None:
        scratch_free = (free_bytes_of or _disk_free)(scratch_path)
    return NodeInventory(
        cpu_ids=tuple(sorted(os.sched_getaffinity(0))),
        cpu_quota_cores=_cpu_quota_cores(proc, root),
        memory_limit_bytes=_memory_limit_bytes(proc, root),
        memory_current_bytes=_allocation_integer("memory.current", proc, root),
        memory_peak_bytes=_allocation_integer("memory.peak", proc, root),
        gpus=_gpu_devices(env, gpu_records),
        scratch_free_bytes=scratch_free,
        slurm_cpus_per_task=_optional_positive_int(env, "SLURM_CPUS_PER_TASK"),
        slurm_gpus_on_node=_optional_positive_int(env, "SLURM_GPUS_ON_NODE"),
        slurm_cpu_bind=env.get("SLURM_CPU_BIND") or None,
    )


def _ancestor_values(name: str, proc: Path, root: Path) -> list[str]:
    """Return the text of ``name`` at the process cgroup and each ancestor below the root.

    Args:
        name: Cgroup file name to look for, such as ``memory.max``.
        proc: Process cgroup file that locates the leaf directory.
        root: Cgroup mount root; the walk stops at this directory.

    Returns:
        Stripped text of each existing ``name`` file from the leaf up to the root; empty when the leaf is absent.
    """
    leaf = cgroup_file(name, proc_cgroup=proc, cgroup_root=root)
    if leaf is None:
        return []
    values: list[str] = []
    for directory in (leaf.parent, *leaf.parent.parents):
        if not directory.is_relative_to(root):
            break
        candidate = directory / name
        if candidate.is_file():
            values.append(candidate.read_text(encoding="utf-8").strip())
        if directory == root:
            break
    return values


def _memory_limit_bytes(proc: Path, root: Path) -> int | None:
    """Return the tightest finite ``memory.max`` on the path, or ``None`` when none is set.

    Args:
        proc: Process cgroup file that locates the leaf directory.
        root: Cgroup mount root.

    Returns:
        The tightest finite memory limit in bytes, or ``None`` when no finite limit is set.
    """
    finite = [
        int(text)
        for text in _ancestor_values("memory.max", proc, root)
        if text.isdigit() and 0 < int(text) < _LIMIT_CEILING
    ]
    return min(finite) if finite else None


def _cpu_quota_cores(proc: Path, root: Path) -> float | None:
    """Return the tightest ``cpu.max`` quota in cores, or ``None`` when unlimited.

    Args:
        proc: Process cgroup file that locates the leaf directory.
        root: Cgroup mount root.

    Returns:
        The smallest quota in cores across the path, or ``None`` when every level is unlimited.

    Raises:
        ValueError: If a ``cpu.max`` value is malformed or has a non-positive quota or period.
    """
    cores: list[float] = []
    for text in _ancestor_values("cpu.max", proc, root):
        parts = text.split()
        if len(parts) != 2:
            raise ValueError(f"malformed cpu.max value {text!r}")
        if parts[0] == "max":
            continue
        quota, period = int(parts[0]), int(parts[1])
        if quota <= 0 or period <= 0:
            raise ValueError(f"cpu.max quota and period must be positive: {text!r}")
        cores.append(quota / period)
    return min(cores) if cores else None


def _allocation_integer(name: str, proc: Path, root: Path) -> int | None:
    """Read a job-level counter such as ``memory.current``; ``None`` when absent.

    Args:
        name: Counter file name, such as ``memory.current``.
        proc: Process cgroup file that locates the leaf directory.
        root: Cgroup mount root.

    Returns:
        The counter value, or ``None`` when the file is absent or not a plain integer.
    """
    path = allocation_cgroup_file(name, proc_cgroup=proc, cgroup_root=root)
    if path is None:
        return None
    text = path.read_text(encoding="utf-8").strip()
    return int(text) if text.isdigit() else None


def _gpu_devices(
    env: Mapping[str, str], records: Sequence[Mapping[str, Any]]
) -> tuple[GpuDevice, ...]:
    """Map ``CUDA_VISIBLE_DEVICES`` tokens to devices, attaching measured memory when known.

    Args:
        env: Environment mapping that holds ``CUDA_VISIBLE_DEVICES``.
        records: Per-device records with index, uuid, total_bytes and free_bytes.

    Returns:
        One ``GpuDevice`` per visible token in environment order; memory is ``None`` where no record matched.
    """
    devices: list[GpuDevice] = []
    for raw in env.get("CUDA_VISIBLE_DEVICES", "").split(","):
        token = raw.strip()
        if token in _NO_DEVICE_TOKENS:
            continue
        record = next(
            (r for r in records if str(r.get("index")) == token or r.get("uuid") == token),
            None,
        )
        if record is None:
            devices.append(GpuDevice(token=token, total_bytes=None, free_bytes=None))
        else:
            devices.append(
                GpuDevice(
                    token=token,
                    total_bytes=_int_or_none(record.get("total_bytes")),
                    free_bytes=_int_or_none(record.get("free_bytes")),
                )
            )
    return tuple(devices)


def _optional_positive_int(env: Mapping[str, str], key: str) -> int | None:
    """Parse an optional Slurm integer; anything malformed or non-positive fails closed.

    Args:
        env: Environment mapping to read from.
        key: Name of the variable to parse.

    Returns:
        The positive integer value, or ``None`` when the variable is unset or empty.

    Raises:
        ValueError: If the value is not an integer or is not positive.
    """
    value = env.get(key, "")
    if not value:
        return None
    try:
        number = int(value)
    except ValueError as exc:
        raise ValueError(f"{key} must be an integer, got {value!r}") from exc
    if number <= 0:
        raise ValueError(f"{key} must be positive, got {value!r}")
    return number


def _int_or_none(value: object) -> int | None:
    """Return an integer measurement, or ``None`` when the record lacks one.

    Args:
        value: Record field to check.

    Returns:
        The value when it is an integer, otherwise ``None``.
    """
    return value if isinstance(value, int) else None


def _disk_free(path: Path) -> int:
    """Return free bytes available to unprivileged writers on ``path``'s filesystem.

    Args:
        path: Directory whose filesystem is measured.

    Returns:
        Free bytes available to unprivileged writers on that filesystem.
    """
    return shutil.disk_usage(path).free


__all__ = ["CGROUP_ROOT", "GpuDevice", "NodeInventory", "read_inventory"]
