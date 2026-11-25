"""Admission control: typed refusals, reserved headroom, and GPU device checks."""

from __future__ import annotations

import pytest

from compute.slurm.admission import (
    AdmissionError,
    Grant,
    Headroom,
    ResourceAdmission,
    ResourceRequest,
)
from compute.slurm.inventory import GpuDevice, NodeInventory

GiB = 1024**3


def _inventory(**overrides: object) -> NodeInventory:
    """Eight affinity cores, a 10 GiB cgroup limit with 3 GiB in use, and no GPUs."""
    base: dict[str, object] = {
        "cpu_ids": tuple(range(8)),
        "cpu_quota_cores": None,
        "memory_limit_bytes": 10 * GiB,
        "memory_current_bytes": 3 * GiB,
        "memory_peak_bytes": None,
        "gpus": (),
        "scratch_free_bytes": None,
        "slurm_cpus_per_task": None,
        "slurm_gpus_on_node": None,
        "slurm_cpu_bind": None,
    }
    base.update(overrides)
    return NodeInventory(**base)  # type: ignore[arg-type]


def test_grant_takes_the_lowest_cores_and_keeps_one_core_as_headroom() -> None:
    admission = ResourceAdmission(_inventory(), Headroom(cpus=1, memory_bytes=2 * GiB))

    grant = admission.admit(ResourceRequest(cpus=3, memory_bytes=GiB))

    assert grant == Grant(cpu_ids=(0, 1, 2), memory_bytes=GiB, gpu_tokens=(), scratch_bytes=0)


def test_request_for_every_core_is_refused_because_headroom_is_reserved() -> None:
    admission = ResourceAdmission(_inventory(), Headroom(cpus=1, memory_bytes=2 * GiB))

    with pytest.raises(AdmissionError) as refused:
        admission.admit(ResourceRequest(cpus=8, memory_bytes=GiB))

    assert refused.value.resource == "cpu"
    assert (refused.value.requested, refused.value.available) == (8, 7)


def test_sequential_grants_consume_one_shared_core_pool() -> None:
    admission = ResourceAdmission(_inventory(), Headroom(cpus=1, memory_bytes=0))

    first = admission.admit(ResourceRequest(cpus=4, memory_bytes=GiB))
    with pytest.raises(AdmissionError) as refused:
        admission.admit(ResourceRequest(cpus=4, memory_bytes=GiB))

    assert first.cpu_ids == (0, 1, 2, 3)
    # Seven usable cores minus the four already granted leaves three.
    assert (refused.value.resource, refused.value.available) == ("cpu", 3)


def test_memory_available_is_limit_minus_current_usage_minus_headroom() -> None:
    # 10 GiB limit - 3 GiB current - 2 GiB headroom = 5 GiB available.
    admission = ResourceAdmission(_inventory(), Headroom(cpus=0, memory_bytes=2 * GiB))

    admission.admit(ResourceRequest(cpus=1, memory_bytes=5 * GiB))
    with pytest.raises(AdmissionError) as refused:
        admission.admit(ResourceRequest(cpus=1, memory_bytes=1))

    assert (refused.value.resource, refused.value.requested, refused.value.available) == (
        "memory",
        1,
        0,
    )


def test_oversized_memory_request_reports_the_reserved_limit() -> None:
    admission = ResourceAdmission(_inventory(), Headroom(cpus=0, memory_bytes=2 * GiB))

    with pytest.raises(AdmissionError) as refused:
        admission.admit(ResourceRequest(cpus=1, memory_bytes=5 * GiB + 1))

    assert refused.value.available == 5 * GiB


@pytest.mark.parametrize(
    "overrides",
    [
        {"memory_limit_bytes": None},
        {"memory_current_bytes": None},
    ],
)
def test_unknown_memory_limit_or_usage_refuses_memory_rather_than_using_host_ram(
    overrides: dict[str, object],
) -> None:
    admission = ResourceAdmission(_inventory(**overrides), Headroom(cpus=0, memory_bytes=0))

    with pytest.raises(AdmissionError) as refused:
        admission.admit(ResourceRequest(cpus=1, memory_bytes=1))

    assert refused.value.resource == "memory"
    assert refused.value.available is None


def test_gpu_request_without_a_visible_device_is_refused() -> None:
    admission = ResourceAdmission(_inventory(), Headroom(cpus=0, memory_bytes=0))

    with pytest.raises(AdmissionError) as refused:
        admission.admit(ResourceRequest(cpus=1, memory_bytes=1, gpus=1))

    assert (refused.value.resource, refused.value.requested, refused.value.available) == (
        "gpu_device",
        1,
        0,
    )


def test_gpu_count_beyond_visible_devices_is_refused() -> None:
    devices = (
        GpuDevice(token="GPU-a", total_bytes=None, free_bytes=None),
        GpuDevice(token="GPU-b", total_bytes=None, free_bytes=None),
    )
    admission = ResourceAdmission(_inventory(gpus=devices), Headroom(cpus=0, memory_bytes=0))

    with pytest.raises(AdmissionError) as refused:
        admission.admit(ResourceRequest(cpus=1, memory_bytes=1, gpus=3))

    assert (refused.value.resource, refused.value.available) == ("gpu", 2)


def test_gpu_memory_is_free_memory_minus_the_reserved_fraction() -> None:
    # 90 GiB free - 20% of 100 GiB total = 70 GiB usable.
    device = GpuDevice(token="GPU-a", total_bytes=100 * GiB, free_bytes=90 * GiB)
    admission = ResourceAdmission(
        _inventory(gpus=(device,)), Headroom(cpus=0, memory_bytes=0, gpu_memory_fraction=0.2)
    )

    grant = admission.admit(
        ResourceRequest(cpus=1, memory_bytes=1, gpus=1, gpu_memory_bytes=70 * GiB)
    )

    assert grant.gpu_tokens == ("GPU-a",)
    # The device is consumed, so the next GPU request fails with no usable device left.
    with pytest.raises(AdmissionError) as refused:
        admission.admit(ResourceRequest(cpus=1, memory_bytes=1, gpus=1))
    assert refused.value.resource == "gpu_device"


def test_gpu_memory_request_above_usable_bytes_reports_the_best_device() -> None:
    device = GpuDevice(token="GPU-a", total_bytes=100 * GiB, free_bytes=90 * GiB)
    admission = ResourceAdmission(
        _inventory(gpus=(device,)), Headroom(cpus=0, memory_bytes=0, gpu_memory_fraction=0.2)
    )

    with pytest.raises(AdmissionError) as refused:
        admission.admit(ResourceRequest(cpus=1, memory_bytes=1, gpus=1, gpu_memory_bytes=71 * GiB))

    assert (refused.value.resource, refused.value.available) == ("gpu_memory", 70 * GiB)


def test_device_with_unknown_memory_is_never_used_for_a_gpu_memory_request() -> None:
    device = GpuDevice(token="GPU-a", total_bytes=None, free_bytes=None)
    admission = ResourceAdmission(_inventory(gpus=(device,)), Headroom(cpus=0, memory_bytes=0))

    with pytest.raises(AdmissionError) as refused:
        admission.admit(ResourceRequest(cpus=1, memory_bytes=1, gpus=1, gpu_memory_bytes=1))

    assert (refused.value.resource, refused.value.available) == ("gpu_memory", None)


def test_refused_request_reserves_nothing() -> None:
    admission = ResourceAdmission(_inventory(), Headroom(cpus=1, memory_bytes=0))

    with pytest.raises(AdmissionError):
        admission.admit(ResourceRequest(cpus=2, memory_bytes=GiB, gpus=1))
    grant = admission.admit(ResourceRequest(cpus=7, memory_bytes=GiB))

    assert grant.cpu_ids == (0, 1, 2, 3, 4, 5, 6)


def test_scratch_request_respects_scratch_headroom() -> None:
    inventory = _inventory(scratch_free_bytes=10 * GiB)
    admission = ResourceAdmission(
        inventory, Headroom(cpus=0, memory_bytes=0, scratch_bytes=3 * GiB)
    )

    with pytest.raises(AdmissionError) as refused:
        admission.admit(ResourceRequest(cpus=1, memory_bytes=1, scratch_bytes=8 * GiB))
    grant = admission.admit(ResourceRequest(cpus=1, memory_bytes=1, scratch_bytes=7 * GiB))

    assert (refused.value.resource, refused.value.available) == ("scratch", 7 * GiB)
    assert grant.scratch_bytes == 7 * GiB


def test_scratch_request_without_a_measurement_is_refused() -> None:
    admission = ResourceAdmission(_inventory(), Headroom(cpus=0, memory_bytes=0))

    with pytest.raises(AdmissionError) as refused:
        admission.admit(ResourceRequest(cpus=1, memory_bytes=1, scratch_bytes=1))

    assert (refused.value.resource, refused.value.available) == ("scratch", None)


def test_granted_cores_follow_the_cpu_quota_not_the_affinity_count() -> None:
    # Affinity shows 8 cores, but cpu.max allows 2.5; floor gives 2 granted cores.
    admission = ResourceAdmission(_inventory(cpu_quota_cores=2.5), Headroom(cpus=0, memory_bytes=0))

    with pytest.raises(AdmissionError) as refused:
        admission.admit(ResourceRequest(cpus=3, memory_bytes=1))

    assert (refused.value.resource, refused.value.available) == ("cpu", 2)


@pytest.mark.parametrize(
    "build",
    [
        lambda: ResourceRequest(cpus=0, memory_bytes=1),
        lambda: ResourceRequest(cpus=1, memory_bytes=0),
        lambda: ResourceRequest(cpus=1, memory_bytes=1, gpus=-1),
        lambda: ResourceRequest(cpus=1, memory_bytes=1, gpu_memory_bytes=1),
        lambda: Headroom(gpu_memory_fraction=1.0),
        lambda: Headroom(cpus=-1),
    ],
)
def test_invalid_requests_and_headroom_are_rejected_before_admission(build: object) -> None:
    with pytest.raises(ValueError):
        build()  # type: ignore[operator]
