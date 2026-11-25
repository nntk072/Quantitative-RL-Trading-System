"""Live resource inventory read from fake cgroup v2, Slurm, and CUDA fixtures."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from compute.slurm.inventory import GpuDevice, NodeInventory, read_inventory

GiB = 1024**3
AFFINITY = {0, 1, 2, 3, 4, 5, 6, 7}
JOB_FILES = {
    "cpu.max": "250000 100000",
    "memory.max": str(8 * GiB),
    "memory.current": str(3 * GiB),
    "memory.peak": str(5 * GiB),
}
STEP_FILES = {
    "cpu.max": "max 100000",
    "memory.max": "max",
    "memory.current": str(GiB),
    "memory.peak": str(2 * GiB),
}


def _cgroup_tree(
    tmp_path: Path,
    *,
    job: dict[str, str] | None = None,
    step: dict[str, str] | None = None,
) -> tuple[Path, Path]:
    """Create slurm/uid_1/job_2/step_0 with the job-level and step-level files."""
    root = tmp_path / "sys" / "fs" / "cgroup"
    job_dir = root / "slurm" / "uid_1" / "job_2"
    step_dir = job_dir / "step_0"
    step_dir.mkdir(parents=True)
    for name, value in (JOB_FILES if job is None else job).items():
        (job_dir / name).write_text(value + "\n", encoding="utf-8")
    for name, value in (STEP_FILES if step is None else step).items():
        (step_dir / name).write_text(value + "\n", encoding="utf-8")
    proc = tmp_path / "proc" / "self" / "cgroup"
    proc.parent.mkdir(parents=True)
    proc.write_text("0::/slurm/uid_1/job_2/step_0\n", encoding="utf-8")
    return root, proc


@pytest.fixture
def affinity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("compute.slurm.inventory.os.sched_getaffinity", lambda _pid: AFFINITY)


def _read(
    tmp_path: Path,
    *,
    proc_cgroup: Path | None = None,
    cgroup_root: Path | None = None,
    environ: dict[str, str] | None = None,
    scratch_path: Path | None = None,
    free_bytes_of: Callable[[Path], int] | None = None,
    gpu_records: list[dict[str, object]] | None = None,
) -> NodeInventory:
    """Read one inventory from fake roots; the default environment is empty."""
    return read_inventory(
        proc_cgroup=proc_cgroup,
        cgroup_root=cgroup_root,
        environ={} if environ is None else environ,
        scratch_path=scratch_path,
        free_bytes_of=free_bytes_of or (lambda _path: 0),
        gpu_records=gpu_records or [],
    )


def test_limits_come_from_the_job_level_and_the_tightest_ancestor_wins(
    tmp_path: Path, affinity: None
) -> None:
    root, proc = _cgroup_tree(tmp_path)

    inventory = _read(tmp_path, proc_cgroup=proc, cgroup_root=root, environ={})

    # cpu.max 250000/100000 is 2.5 cores, so floor gives 2 granted cores out of 8 in the mask.
    assert inventory.cpu_ids == (0, 1, 2, 3, 4, 5, 6, 7)
    assert inventory.cpu_quota_cores == 2.5
    assert inventory.granted_cpus == 2
    # The step's memory.max is "max" and is ignored; the job's 8 GiB limit binds.
    assert inventory.memory_limit_bytes == 8 * GiB
    # Usage is read at the allocation (job) level, not the step's 1 GiB current or 2 GiB peak.
    assert inventory.memory_current_bytes == 3 * GiB
    assert inventory.memory_peak_bytes == 5 * GiB


def test_a_finite_step_limit_tighter_than_the_job_limit_is_used(
    tmp_path: Path, affinity: None
) -> None:
    root, proc = _cgroup_tree(tmp_path, step={**STEP_FILES, "memory.max": str(4 * GiB)})

    inventory = _read(tmp_path, proc_cgroup=proc, cgroup_root=root, environ={})

    assert inventory.memory_limit_bytes == 4 * GiB


def test_slurm_cpus_per_task_caps_granted_cores_when_no_quota_is_set(
    tmp_path: Path, affinity: None
) -> None:
    job = {**JOB_FILES, "cpu.max": "max 100000"}
    root, proc = _cgroup_tree(tmp_path, job=job, step={**STEP_FILES, "cpu.max": "max 100000"})

    inventory = _read(
        tmp_path,
        proc_cgroup=proc,
        cgroup_root=root,
        environ={"SLURM_CPUS_PER_TASK": "3", "SLURM_CPU_BIND": "mask_cpu:0x7"},
    )

    assert inventory.cpu_quota_cores is None
    assert inventory.granted_cpus == 3
    assert inventory.slurm_cpus_per_task == 3
    assert inventory.slurm_cpu_bind == "mask_cpu:0x7"


def test_missing_cgroup_reports_unknown_memory_and_never_substitutes_host_totals(
    tmp_path: Path, affinity: None
) -> None:
    proc = tmp_path / "proc" / "self" / "cgroup"
    proc.parent.mkdir(parents=True)
    proc.write_text("0::/\n", encoding="utf-8")

    inventory = _read(tmp_path, proc_cgroup=proc, cgroup_root=tmp_path / "absent", environ={})

    assert inventory.memory_limit_bytes is None
    assert inventory.memory_current_bytes is None
    assert inventory.memory_peak_bytes is None
    assert inventory.cpu_quota_cores is None
    # Cores still come from the affinity mask, which is the allocation's own view.
    assert inventory.granted_cpus == 8


@pytest.mark.parametrize("bad", ["abc 100000", "250000 zero"])
def test_malformed_cpu_quota_fails_closed(tmp_path: Path, affinity: None, bad: str) -> None:
    job = {**JOB_FILES, "cpu.max": bad}
    root, proc = _cgroup_tree(tmp_path, job=job)

    with pytest.raises(ValueError):
        _read(tmp_path, proc_cgroup=proc, cgroup_root=root, environ={})


def test_malformed_slurm_cpu_count_fails_closed(tmp_path: Path, affinity: None) -> None:
    root, proc = _cgroup_tree(tmp_path)

    with pytest.raises(ValueError, match="SLURM_CPUS_PER_TASK"):
        _read(
            tmp_path,
            proc_cgroup=proc,
            cgroup_root=root,
            environ={"SLURM_CPUS_PER_TASK": "four"},
        )


def test_gpus_are_exactly_the_cuda_visible_devices_with_their_reported_memory(
    tmp_path: Path, affinity: None
) -> None:
    records = [
        {"index": 0, "uuid": "GPU-abc", "total_bytes": 96 * GiB, "free_bytes": 90 * GiB},
        {"index": 1, "uuid": "GPU-xyz", "total_bytes": 96 * GiB, "free_bytes": 2 * GiB},
    ]

    inventory = _read(
        tmp_path,
        environ={"CUDA_VISIBLE_DEVICES": "GPU-abc,1"},
        gpu_records=records,
    )

    assert inventory.gpus == (
        GpuDevice(token="GPU-abc", total_bytes=96 * GiB, free_bytes=90 * GiB),
        GpuDevice(token="1", total_bytes=96 * GiB, free_bytes=2 * GiB),
    )


@pytest.mark.parametrize("value", ["", " , ", "-1", "NoDevFiles"])
def test_sentinel_or_empty_cuda_visible_devices_expose_no_gpu(
    tmp_path: Path, affinity: None, value: str
) -> None:
    inventory = _read(tmp_path, environ={"CUDA_VISIBLE_DEVICES": value}, gpu_records=[])

    assert inventory.gpus == ()


def test_visible_gpu_without_a_measured_record_has_unknown_memory(
    tmp_path: Path, affinity: None
) -> None:
    inventory = _read(tmp_path, environ={"CUDA_VISIBLE_DEVICES": "GPU-missing"}, gpu_records=[])

    assert inventory.gpus == (GpuDevice(token="GPU-missing", total_bytes=None, free_bytes=None),)


def test_scratch_space_is_measured_on_the_given_path_only(tmp_path: Path, affinity: None) -> None:
    seen: list[Path] = []

    def fake_free(path: Path) -> int:
        seen.append(path)
        return 7 * GiB

    scratch = tmp_path / "scratch"
    measured = _read(tmp_path, environ={}, scratch_path=scratch, free_bytes_of=fake_free)
    unmeasured = _read(tmp_path, environ={}, scratch_path=None)

    assert seen == [scratch]
    assert measured.scratch_free_bytes == 7 * GiB
    assert unmeasured.scratch_free_bytes is None


def test_slurm_gpu_and_cpu_binding_variables_are_recorded(tmp_path: Path, affinity: None) -> None:
    inventory = _read(
        tmp_path,
        environ={"SLURM_GPUS_ON_NODE": "1", "SLURM_CPU_BIND": "mask_cpu:0xff"},
    )

    assert inventory.slurm_gpus_on_node == 1
    assert inventory.slurm_cpu_bind == "mask_cpu:0xff"
