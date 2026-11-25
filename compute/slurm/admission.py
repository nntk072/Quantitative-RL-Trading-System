"""Admission control: grant part of one node's measured resources or refuse with a typed error.

A refused request reserves nothing. Headroom is kept back from every grant, so a
request that would consume the last reserved core, byte, or byte of scratch is
refused. Memory is admitted only against a measured cgroup limit and usage; a
node without either is refused for memory rather than sized from host RAM.
"""

from __future__ import annotations

from dataclasses import dataclass

from compute.slurm.inventory import GpuDevice, NodeInventory
from compute.slurm.worker_resources import DEFAULT_CPU_RESERVE_PER_NODE, DEFAULT_MEMORY_RESERVE_GIB

_GiB = 1024**3


@dataclass(frozen=True, slots=True)
class Headroom:
    """Resources kept back from all grants. Defaults mirror the worker planner's reserves."""

    cpus: int = DEFAULT_CPU_RESERVE_PER_NODE
    memory_bytes: int = int(DEFAULT_MEMORY_RESERVE_GIB * _GiB)
    gpu_memory_fraction: float = 0.2
    scratch_bytes: int = 0

    def __post_init__(self) -> None:
        """Reject negative reserves and a GPU fraction outside [0, 1)."""
        if self.cpus < 0 or self.memory_bytes < 0 or self.scratch_bytes < 0:
            raise ValueError("admission headroom must be non-negative")
        if not 0 <= self.gpu_memory_fraction < 1:
            raise ValueError("GPU memory headroom fraction must be in [0, 1)")


@dataclass(frozen=True, slots=True)
class ResourceRequest:
    """One request for cores, RAM, GPUs and scratch; zero GPUs means CPU-only."""

    cpus: int
    memory_bytes: int
    gpus: int = 0
    gpu_memory_bytes: int = 0
    scratch_bytes: int = 0

    def __post_init__(self) -> None:
        """Reject requests that are empty or internally inconsistent."""
        if self.cpus < 1 or self.memory_bytes < 1:
            raise ValueError("a request needs at least one CPU and at least one byte of memory")
        if self.gpus < 0 or self.gpu_memory_bytes < 0 or self.scratch_bytes < 0:
            raise ValueError("request GPU and scratch amounts must be non-negative")
        if self.gpu_memory_bytes and not self.gpus:
            raise ValueError("GPU memory was requested without a GPU count")


@dataclass(frozen=True, slots=True)
class Grant:
    """Resources reserved for one admitted request."""

    cpu_ids: tuple[int, ...]
    memory_bytes: int
    gpu_tokens: tuple[str, ...]
    scratch_bytes: int


class AdmissionError(RuntimeError):
    """A request exceeds what remains grantable; ``resource`` names the failing resource."""

    def __init__(self, resource: str, *, requested: int, available: int | None) -> None:
        """Record the refused amount and what was available, in the resource's units.

        Args:
            resource: One of ``cpu``, ``memory``, ``scratch``, ``gpu``, ``gpu_device``,
                or ``gpu_memory``.
            requested: Amount the request asked for.
            available: Amount still grantable, or ``None`` when it was never measured.
        """
        self.resource = resource
        self.requested = requested
        self.available = available
        detail = "unknown" if available is None else str(available)
        super().__init__(f"{resource} request of {requested} refused; available {detail}")


class ResourceAdmission:
    """Track one node's grantable resources across sequential requests."""

    def __init__(self, inventory: NodeInventory, headroom: Headroom | None = None) -> None:
        """Start from a measured inventory with headroom already withheld.

        Args:
            inventory: Live envelope from ``read_inventory``.
            headroom: Reserves to keep back; defaults to the planner's reserves.
        """
        reserve = headroom or Headroom()
        self._headroom = reserve
        pool = list(inventory.cpu_ids[: inventory.granted_cpus])
        self._cpus = pool[: max(0, len(pool) - reserve.cpus)]
        self._memory: int | None = None
        if inventory.memory_limit_bytes is not None and inventory.memory_current_bytes is not None:
            self._memory = max(
                0,
                inventory.memory_limit_bytes
                - inventory.memory_current_bytes
                - reserve.memory_bytes,
            )
        self._scratch: int | None = None
        if inventory.scratch_free_bytes is not None:
            self._scratch = max(0, inventory.scratch_free_bytes - reserve.scratch_bytes)
        self._gpus: list[GpuDevice] = list(inventory.gpus)

    def admit(self, request: ResourceRequest) -> Grant:
        """Reserve resources for ``request`` or raise without reserving anything.

        Args:
            request: The resources the caller needs.

        Returns:
            The reservation, with the granted core IDs and GPU tokens.

        Raises:
            AdmissionError: If any requested resource is unavailable or unmeasured.
        """
        gpus = self._select_gpus(request)
        if request.cpus > len(self._cpus):
            raise AdmissionError("cpu", requested=request.cpus, available=len(self._cpus))
        memory = self._memory
        if memory is None:
            raise AdmissionError("memory", requested=request.memory_bytes, available=None)
        if request.memory_bytes > memory:
            raise AdmissionError("memory", requested=request.memory_bytes, available=memory)
        scratch = self._scratch
        if request.scratch_bytes:
            if scratch is None:
                raise AdmissionError("scratch", requested=request.scratch_bytes, available=None)
            if request.scratch_bytes > scratch:
                raise AdmissionError("scratch", requested=request.scratch_bytes, available=scratch)

        cpu_ids = tuple(self._cpus[: request.cpus])
        del self._cpus[: request.cpus]
        self._memory = memory - request.memory_bytes
        if scratch is not None:
            self._scratch = scratch - request.scratch_bytes
        for device in gpus:
            self._gpus.remove(device)
        return Grant(
            cpu_ids=cpu_ids,
            memory_bytes=request.memory_bytes,
            gpu_tokens=tuple(device.token for device in gpus),
            scratch_bytes=request.scratch_bytes,
        )

    def _select_gpus(self, request: ResourceRequest) -> list[GpuDevice]:
        """Choose the devices that satisfy the GPU count and per-device memory request.

        Args:
            request: Request whose GPU count and per-device memory must be met.

        Returns:
            The first ``request.gpus`` eligible devices, in visible order; an empty list when no GPU is requested.

        Raises:
            AdmissionError: If too few devices are visible or eligible.
        """
        if request.gpus == 0:
            return []
        if not self._gpus:
            raise AdmissionError("gpu_device", requested=request.gpus, available=0)
        fraction = self._headroom.gpu_memory_fraction

        def fits(device: GpuDevice) -> bool:
            """Return whether ``device`` has enough usable memory for this request.

            Args:
                device: Device to test against the request's per-device memory amount.

            Returns:
                ``True`` when the device can host the requested GPU memory, or when none was requested.
            """
            if request.gpu_memory_bytes == 0:
                return True
            usable = _usable_gpu_bytes(device, fraction)
            return usable is not None and usable >= request.gpu_memory_bytes

        eligible = [device for device in self._gpus if fits(device)]
        if len(eligible) < request.gpus:
            if request.gpu_memory_bytes:
                usable = [
                    value
                    for value in (_usable_gpu_bytes(device, fraction) for device in self._gpus)
                    if value is not None
                ]
                raise AdmissionError(
                    "gpu_memory",
                    requested=request.gpu_memory_bytes,
                    available=max(usable) if usable else None,
                )
            raise AdmissionError("gpu", requested=request.gpus, available=len(eligible))
        return eligible[: request.gpus]


def _usable_gpu_bytes(device: GpuDevice, reserved_fraction: float) -> int | None:
    """Free device memory minus the reserved share of total memory; ``None`` if unmeasured.

    Args:
        device: GPU device with optional total and free memory.
        reserved_fraction: Share of total device memory kept back as headroom.

    Returns:
        Free bytes minus the reserved share, clamped at zero; ``None`` when either measurement is unknown.
    """
    if device.total_bytes is None or device.free_bytes is None:
        return None
    return max(0, device.free_bytes - int(device.total_bytes * reserved_fraction))


__all__ = [
    "AdmissionError",
    "Grant",
    "Headroom",
    "ResourceAdmission",
    "ResourceRequest",
]
