from __future__ import annotations

import csv
import datetime as dt
import json
import pathlib
import subprocess
from typing import Any, cast

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


def test_cpu_mask_for_slot_selects_exact_allocated_ids() -> None:
    assert resources.cpu_mask_for_slot([2, 4, 7], slot=0, cpus=2) == ("0x14", [2, 4])


@pytest.mark.parametrize("slot,cpus", [(-1, 1), (0, 0)])
def test_cpu_mask_rejects_invalid_slot_or_worker_width(slot: int, cpus: int) -> None:
    with pytest.raises(ValueError, match="non-negative/positive"):
        resources.cpu_mask_for_slot([0, 1], slot=slot, cpus=cpus)


def test_cpu_mask_for_range_rejects_negative_start_and_empty_range() -> None:
    with pytest.raises(ValueError, match="range start"):
        resources.cpu_mask_for_range([0, 1], start=-1, cpus=1)
    with pytest.raises(ValueError, match="range start"):
        resources.cpu_mask_for_range([0, 1], start=0, cpus=0)


def test_worker_command_returns_direct_command_without_a_node() -> None:
    command = ["python", "-m", "training.cli"]

    assert resources.worker_command(command, node=None, gpu_type="gh200", cpus=2) is command


@pytest.mark.parametrize(
    "kwargs,match",
    [
        ({"gpu_count": -1}, "GPU count"),
        ({"gpu_count": 1, "available_gpu_count": 0}, "GPU count"),
        ({"gpu_count": 1, "available_gpu_count": 2, "gpu_id": 2}, "GPU count"),
        ({"cpu_mask": "0x3"}, "provided together"),
        ({"step_cpus": 1}, "cannot be smaller"),
    ],
)
def test_worker_command_rejects_invalid_gpu_and_cpu_bindings(
    kwargs: dict[str, Any], match: str
) -> None:
    with pytest.raises(ValueError, match=match):
        resources.worker_command(["python"], node="gpu1", gpu_type="h100", cpus=2, **kwargs)


def test_worker_command_builds_cpu_only_guarded_request(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(resources, "ROOT", pathlib.Path("/project"))

    command = resources.worker_command(
        ["python", "worker.py"],
        node="cpu1",
        gpu_type="none",
        cpus=2,
        gpu_count=0,
        cpu_mask="0x30",
        expected_cpu_ids=[4, 5],
        step_cpus=3,
    )

    assert "--cpus-per-task=3" in command
    assert "--cpu-bind=mask_cpu:0x30" in command
    assert "--gpus=none:0" not in command
    assert command[command.index("--") + 1 :] == ["python", "worker.py"]
    assert str(resources.WORKER_CPU_AFFINITY_GUARD) in command


def test_expand_slurm_hosts_preserves_order_and_rejects_invalid_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        cast(Any, resources).subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            args=[], returncode=0, stdout="gpu2\ngpu1\n", stderr=""
        ),
    )
    assert resources.expand_slurm_hosts("gpu[1-2]") == ["gpu2", "gpu1"]

    monkeypatch.setattr(
        cast(Any, resources).subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="invalid hostlist"
        ),
    )
    with pytest.raises(ValueError, match="could not expand Slurm node list"):
        resources.expand_slurm_hosts("bad[")

    monkeypatch.setattr(
        cast(Any, resources).subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            args=[], returncode=0, stdout="gpu1\ngpu1\n", stderr=""
        ),
    )
    with pytest.raises(ValueError, match="no hosts or duplicate"):
        resources.expand_slurm_hosts("gpu1")


@pytest.mark.parametrize("raw", ["gpu1,gpu2", "gpu1,gpu1"])
def test_resolve_worker_nodes_supports_dry_run_and_rejects_duplicates(raw: str) -> None:
    if raw == "gpu1,gpu2":
        assert resources.resolve_worker_nodes(raw, dry_run=True) == ["gpu1", "gpu2"]
    else:
        with pytest.raises(ValueError, match="empty or contains duplicates"):
            resources.resolve_worker_nodes(raw, dry_run=True)
    assert resources.resolve_worker_nodes(None, dry_run=False) == []


def test_resolve_worker_nodes_validates_parent_allocation_and_outside_hosts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SLURM_NODELIST", raising=False)
    monkeypatch.delenv("SLURM_JOB_NODELIST", raising=False)
    with pytest.raises(ValueError, match="existing multi-node Slurm allocation"):
        resources.resolve_worker_nodes("gpu1", dry_run=False)

    monkeypatch.setenv("SLURM_JOB_NODELIST", "gpu[1-2]")
    monkeypatch.setattr(
        resources,
        "expand_slurm_hosts",
        lambda hosts: {
            "gpu[1-2]": ["gpu1", "gpu2"],
            "gpu2": ["gpu2"],
            "gpu3": ["gpu3"],
        }[hosts],
    )
    assert resources.resolve_worker_nodes("gpu2", dry_run=False) == ["gpu2"]

    with pytest.raises(ValueError, match="outside the Slurm allocation"):
        resources.resolve_worker_nodes("gpu3", dry_run=False)


def test_worker_node_cpu_metadata_is_identity_checked_and_sorted(tmp_path: pathlib.Path) -> None:
    ready = tmp_path / "123" / "gpu1" / "ready"
    ready.parent.mkdir(parents=True)
    ready.write_text(json.dumps({"node": "gpu1", "job_id": "123", "cpu_ids": [7, 2, 4]}))

    assert resources.worker_node_cpu_ids(tmp_path, "123", "gpu1.cluster") == [2, 4, 7]

    ready.write_text(json.dumps({"node": "gpu2", "job_id": "123", "cpu_ids": [1]}))
    with pytest.raises(RuntimeError, match="identity mismatch"):
        resources.worker_node_cpu_ids(tmp_path, "123", "gpu1")

    ready.write_text(json.dumps({"node": "gpu1", "job_id": "123", "cpu_ids": [1, 1]}))
    with pytest.raises(RuntimeError, match="invalid CPU set"):
        resources.worker_node_cpu_ids(tmp_path, "123", "gpu1")


def test_worker_node_resources_validates_cpu_memory_and_gpu_inventory(
    tmp_path: pathlib.Path,
) -> None:
    ready = tmp_path / "123" / "gpu1" / "ready"
    ready.parent.mkdir(parents=True)
    metadata = {
        "node": "gpu1",
        "job_id": 123,
        "cpu_ids": [4, 2],
        "memory_limit_bytes": 1024,
        "gpu_memory": [{"total_bytes": 4096, "free_bytes": 2048}],
    }
    ready.write_text(json.dumps(metadata))

    result = resources.worker_node_resources(tmp_path, "123", "gpu1")

    assert result["cpu_ids"] == [2, 4]
    assert result["memory_limit_bytes"] == 1024
    assert result["gpu_memory"] == metadata["gpu_memory"]

    metadata["gpu_memory"] = [{"total_bytes": 0, "free_bytes": 1}]
    ready.write_text(json.dumps(metadata))
    with pytest.raises(RuntimeError, match="invalid resource metadata"):
        resources.worker_node_resources(tmp_path, "123", "gpu1")


@pytest.mark.parametrize(
    "resources_by_node,expected",
    [
        (
            {
                "gpu1": {
                    "cpu_ids": list(range(9)),
                    "memory_limit_bytes": 256 * 1024**3,
                    "gpu_memory": [{"total_bytes": 40 * 1024**3, "free_bytes": 32 * 1024**3}],
                }
            },
            (4, 4),
        ),
        (
            {"gpu1": {"cpu_ids": list(range(5)), "gpu_type": "gh200"}},
            (1, 1),
        ),
        (
            {"cpu1": {"cpu_ids": list(range(5)), "memory_limit_bytes": None}},
            (1, 1),
        ),
    ],
)
def test_plan_worker_capacity_uses_cpu_memory_and_gpu_limits(
    resources_by_node: dict[str, dict[str, object]], expected: tuple[int, int]
) -> None:
    plan = resources.plan_worker_capacity(
        resources_by_node,
        n_envs=4,
        data_source="bars",
        gpus_per_node=1,
        memory_reserve_gib=0,
    )

    node = next(iter(plan["nodes"].values()))
    assert (plan["workers"], node["workers"]) == expected


@pytest.mark.parametrize(
    "kwargs,match",
    [
        ({"n_envs": 12}, "not benchmarked"),
        ({"gpus_per_node": 0}, "limits are invalid"),
        ({"gpu_memory_reserve_fraction": 1.0}, "limits are invalid"),
        ({"cpu_reserve_per_node": -1}, "limits are invalid"),
    ],
)
def test_plan_worker_capacity_rejects_unbenchmarked_or_invalid_limits(
    kwargs: dict[str, object], match: str
) -> None:
    options: dict[str, Any] = {
        "n_envs": 4,
        "data_source": "bars",
        "gpus_per_node": 1,
        "memory_reserve_gib": 0,
    }
    options.update(kwargs)
    with pytest.raises(ValueError, match=match):
        resources.plan_worker_capacity({"gpu1": {"cpu_ids": [0, 1]}}, **options)


def test_gpu_memory_inventory_filters_slurm_visible_devices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = "0, GPU-a, 40960, 20480\n1, GPU-b, 81920, 40960\ninvalid\n2, GPU-c, bad, 1\n"
    monkeypatch.setattr(
        cast(Any, resources).subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            args=[], returncode=0, stdout=output, stderr=""
        ),
    )
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "GPU-b,0")

    inventory = resources.gpu_memory_inventory()

    assert [item["uuid"] for item in inventory] == ["GPU-b", "GPU-a"]
    assert inventory[1]["total_bytes"] == 40960 * 1024**2
    assert inventory[0]["free_bytes"] == 40960 * 1024**2


@pytest.mark.parametrize("failure", ["returncode", "missing", "timeout"])
def test_gpu_memory_inventory_fails_closed_when_smi_is_unavailable(
    monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    if failure == "returncode":
        monkeypatch.setattr(
            cast(Any, resources).subprocess,
            "run",
            lambda *_args, **_kwargs: subprocess.CompletedProcess(
                args=[], returncode=1, stdout="", stderr="unavailable"
            ),
        )
    else:
        error = (
            FileNotFoundError
            if failure == "missing"
            else subprocess.TimeoutExpired("nvidia-smi", 5)
        )

        def fail(*_args: object, **_kwargs: object) -> None:
            raise error

        monkeypatch.setattr(cast(Any, resources).subprocess, "run", fail)

    assert resources.gpu_memory_inventory() == []


def test_gpu_memory_inventory_returns_all_devices_without_visibility_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)
    monkeypatch.setattr(
        cast(Any, resources).subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            args=[], returncode=0, stdout="0, GPU-a, 40960, 20480\n", stderr=""
        ),
    )

    assert [item["uuid"] for item in resources.gpu_memory_inventory()] == ["GPU-a"]


def test_gpu_memory_inventory_returns_no_devices_when_visibility_is_explicitly_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "")
    monkeypatch.setattr(
        cast(Any, resources).subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            args=[], returncode=0, stdout="0, GPU-a, 40960, 20480\n", stderr=""
        ),
    )

    assert resources.gpu_memory_inventory() == []


def test_cgroup_memory_file_reads_v2_path_and_rejects_escape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_read = pathlib.Path.read_text

    def read_text(path: pathlib.Path, *args: Any, **kwargs: Any) -> str:
        if str(path) == "/proc/self/cgroup":
            return "0::/slurm/job_12/step_0"
        return original_read(path, *args, **kwargs)

    monkeypatch.setattr(pathlib.Path, "read_text", read_text)
    monkeypatch.setattr(pathlib.Path, "resolve", lambda path, **_kwargs: path)
    monkeypatch.setattr(
        pathlib.Path,
        "is_file",
        lambda path: str(path) == "/sys/fs/cgroup/slurm/job_12/step_0/memory.max",
    )

    result = resources.cgroup_memory_file("memory.max")

    assert result == pathlib.Path("/sys/fs/cgroup/slurm/job_12/step_0/memory.max")

    monkeypatch.setattr(pathlib.Path, "read_text", lambda path, *_args, **_kwargs: "0::/../../tmp")
    assert resources.cgroup_memory_file("memory.max") is None


def test_cgroup_memory_file_finds_v1_memory_controller(monkeypatch: pytest.MonkeyPatch) -> None:
    original_read = pathlib.Path.read_text

    def read_text(path: pathlib.Path, *args: Any, **kwargs: Any) -> str:
        if str(path) == "/proc/self/cgroup":
            return "2:cpu:/jobs/12\n3:cpu,memory:/jobs/12"
        return original_read(path, *args, **kwargs)

    monkeypatch.setattr(pathlib.Path, "read_text", read_text)
    monkeypatch.setattr(pathlib.Path, "resolve", lambda path, **_kwargs: path)
    monkeypatch.setattr(
        pathlib.Path,
        "is_file",
        lambda path: str(path) == "/sys/fs/cgroup/memory/jobs/12/memory.limit_in_bytes",
    )

    assert resources.cgroup_memory_file("memory.limit_in_bytes") == pathlib.Path(
        "/sys/fs/cgroup/memory/jobs/12/memory.limit_in_bytes"
    )


def test_cgroup_memory_file_skips_malformed_entries_and_uses_safe_mount_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_resolve = pathlib.Path.resolve
    monkeypatch.setattr(
        pathlib.Path,
        "read_text",
        lambda path, *_args, **_kwargs: (
            "malformed-entry" if str(path) == "/proc/self/cgroup" else ""
        ),
    )
    monkeypatch.setattr(pathlib.Path, "resolve", lambda path, **_kwargs: original_resolve(path))
    monkeypatch.setattr(
        pathlib.Path,
        "is_file",
        lambda path: str(path) == "/sys/fs/cgroup/memory/memory.max",
    )

    assert resources.cgroup_memory_file("memory.max") == pathlib.Path(
        "/sys/fs/cgroup/memory/memory.max"
    )


def test_cgroup_memory_file_rejects_mount_fallback_that_resolves_outside_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def resolve(path: pathlib.Path, **_kwargs: Any) -> pathlib.Path:
        if str(path) == "/sys/fs/cgroup/memory/memory.max":
            return pathlib.Path("/tmp/outside")
        return path

    monkeypatch.setattr(
        pathlib.Path,
        "read_text",
        lambda path, *_args, **_kwargs: (
            "malformed-entry" if str(path) == "/proc/self/cgroup" else ""
        ),
    )
    monkeypatch.setattr(pathlib.Path, "resolve", resolve)
    monkeypatch.setattr(pathlib.Path, "is_file", lambda _path: False)

    assert resources.cgroup_memory_file("memory.max") is None


def test_available_resources_uses_tightest_parent_limit_and_cpu_affinity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    memory = pathlib.Path("/sys/fs/cgroup/job_12/step_0/memory.max")
    limits = {
        "/sys/fs/cgroup/job_12/step_0/memory.max": "max",
        "/sys/fs/cgroup/job_12/memory.max": "8589934592",
        "/sys/fs/cgroup/memory.max": "max",
    }
    original_read = pathlib.Path.read_text

    def read_text(path: pathlib.Path, *args: Any, **kwargs: Any) -> str:
        if str(path) in limits:
            return limits[str(path)]
        return original_read(path, *args, **kwargs)

    monkeypatch.setattr(resources, "cgroup_memory_file", lambda _name: memory)
    monkeypatch.setattr(pathlib.Path, "read_text", read_text)
    monkeypatch.setattr(cast(Any, resources).os, "sched_getaffinity", lambda _pid: {1, 3, 5})

    assert resources.available_resources() == {
        "memory_limit_bytes": 8589934592,
        "cpu_affinity": 3,
        "cpu_ids": [1, 3, 5],
    }


def test_available_resources_reads_legacy_memory_limit_when_v2_is_missing(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    limit = tmp_path / "memory.limit_in_bytes"
    limit.write_text("2048")
    monkeypatch.setattr(
        resources, "cgroup_memory_file", lambda name: limit if name.endswith("bytes") else None
    )
    monkeypatch.setattr(cast(Any, resources).os, "sched_getaffinity", lambda _pid: {2})

    assert resources.available_resources() == {
        "memory_limit_bytes": 2048,
        "cpu_affinity": 1,
        "cpu_ids": [2],
    }


def test_utc_returns_timezone_aware_iso_timestamp() -> None:
    timestamp = dt.datetime.fromisoformat(resources.utc())

    assert timestamp.tzinfo == dt.UTC


def test_plan_worker_capacity_applies_bundle_memory_estimate_and_no_gpu_fallback() -> None:
    bundle = resources.plan_worker_capacity(
        {
            "gh200": {
                "cpu_ids": list(range(65)),
                "memory_limit_bytes": 512 * 1024**3,
                "gpu_type": "GH200",
            }
        },
        n_envs=64,
        data_source="bundle",
        gpus_per_node=1,
        memory_reserve_gib=0,
    )
    bars = resources.plan_worker_capacity(
        {
            "other": {
                "cpu_ids": list(range(65)),
                "memory_limit_bytes": 512 * 1024**3,
                "gpu_type": "other",
            }
        },
        n_envs=64,
        data_source="bars",
        gpus_per_node=1,
        memory_reserve_gib=0,
    )

    assert bundle["nodes"]["gh200"]["estimated_worker_memory_gib"] == 30
    assert bundle["nodes"]["gh200"]["gpu_capacity"] == 9
    assert bars["nodes"]["other"]["gpu_capacity"] == 1


def test_sample_resources_continues_when_cgroup_and_gpu_sampling_fail(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(resources, "utc", lambda: "timestamp")
    monkeypatch.setattr(resources, "cgroup_memory_file", lambda _name: None)
    monkeypatch.setattr(cast(Any, resources).os, "getloadavg", lambda: (0.25, 0.2, 0.1))

    def unavailable(*_args: Any, **_kwargs: Any) -> None:
        raise FileNotFoundError("nvidia-smi")

    monkeypatch.setattr(cast(Any, resources).subprocess, "run", unavailable)
    target = tmp_path / "samples.csv"
    resources.sample_resources(target)

    with target.open(encoding="utf-8") as stream:
        row = next(csv.reader(stream))
    assert row == ["timestamp", "0.25", "", "", "", "", "", ""]


def test_sample_resources_appends_host_cgroup_and_gpu_values(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    counters = {
        name: tmp_path / name
        for name in ("memory.current", "memory.max", "memory.peak", "memory.events")
    }
    for name, path in counters.items():
        path.write_text(f"{name}: 123\n")
    monkeypatch.setattr(resources, "utc", lambda: "2026-01-02T00:00:00+00:00")
    monkeypatch.setattr(resources, "cgroup_memory_file", lambda name: counters[name])
    monkeypatch.setattr(cast(Any, resources).os, "getloadavg", lambda: (1.5, 1.0, 0.5))
    monkeypatch.setattr(
        cast(Any, resources).subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            args=[], returncode=0, stdout="45, 512\n", stderr=""
        ),
    )
    target = tmp_path / "samples.csv"

    resources.sample_resources(target)

    row = next(csv.reader(target.open(encoding="utf-8")))
    assert row == [
        "2026-01-02T00:00:00+00:00",
        "1.5",
        "memory.current: 123",
        "memory.max: 123",
        "memory.peak: 123",
        "memory.events: 123",
        "45",
        "512",
    ]
