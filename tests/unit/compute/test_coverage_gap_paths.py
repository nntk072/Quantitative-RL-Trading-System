"""Behavioral edge cases for host resource readers and sizing policies."""

from __future__ import annotations

import os
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import Mock

import pytest
import torch

from compute import contracts
from compute.environment import capabilities, device, precision
from compute.slurm import resources, worker_resources

GiB = 1024**3


def test_device_sizing_uses_floor_for_large_gpu_with_small_host_ram() -> None:
    assert device._gpu_n_envs_target(80 * GiB, 64 * GiB) == 32
    assert device._gpu_n_envs_target(4 * GiB, 512 * GiB) == 8
    assert device._gpu_n_envs_target(80 * GiB, 280 * GiB) == 64
    assert device._gpu_n_envs_target(80 * GiB, 520 * GiB) == 128
    assert device._gpu_n_envs_target(40 * GiB, 520 * GiB) == 16
    assert device._gpu_n_envs_target(10 * GiB, 520 * GiB) == 8
    assert device.suggest_n_epochs(current=5, has_cuda=False) == 5
    assert device.suggest_n_epochs(current=5, has_cuda=True) == 15


def test_meminfo_reader_parses_fields_and_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "builtins.open",
        lambda *_args, **_kwargs: StringIO("MemTotal: 2000 kB\nMemAvailable: 750 kB\n"),
    )
    assert device._read_meminfo() == (2_048_000, 768_000)

    def unreadable(*_args: Any, **_kwargs: Any) -> StringIO:
        raise OSError("procfs unavailable")

    monkeypatch.setattr("builtins.open", unreadable)
    assert device._read_meminfo() == (0, 0)


def test_cgroup_and_slurm_readers_return_none_when_no_limits_are_visible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(device, "_current_cgroup_dir", lambda: None)
    monkeypatch.setattr(
        Path, "read_text", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError())
    )
    monkeypatch.delenv("SLURM_MEM_PER_NODE", raising=False)
    monkeypatch.delenv("SLURM_MEM_PER_CPU", raising=False)
    assert device._read_cgroup_cpu_count() is None
    assert device._read_cgroup_memory_limit() is None
    assert device._read_slurm_memory_limit() is None
    assert device._current_cgroup_dir() is None


def test_cgroup_file_uses_safe_mount_fallback_and_rejects_escape(tmp_path: Path) -> None:
    root = tmp_path / "cgroup"
    root.mkdir()
    fallback = root / "memory.max"
    fallback.write_text("4096\n", encoding="utf-8")
    proc = tmp_path / "proc-cgroup"
    proc.write_text("4:cpu:/job/4\n", encoding="utf-8")
    assert resources.cgroup_file("memory.max", proc_cgroup=proc, cgroup_root=root) == fallback

    outside = tmp_path / "outside"
    outside.write_text("secret", encoding="utf-8")
    (root / "memory.current").symlink_to(outside)
    assert resources.cgroup_file("memory.current", proc_cgroup=proc, cgroup_root=root) is None


def test_cgroup_value_and_allocation_lookup_handle_missing_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    value = tmp_path / "memory.current"
    value.write_text("8192\n", encoding="utf-8")
    monkeypatch.setattr(
        resources,
        "allocation_cgroup_file",
        lambda _name, **_kwargs: value,
    )
    assert resources.cgroup_value("memory.current") == "8192"
    monkeypatch.setattr(
        resources,
        "allocation_cgroup_file",
        lambda _name, **_kwargs: None,
    )
    assert resources.cgroup_value("memory.current") == ""
    assert (
        resources.allocation_cgroup_file(
            "memory.max", proc_cgroup=tmp_path / "missing", cgroup_root=tmp_path
        )
        is None
    )


def test_cgroup_file_resolves_v2_and_v1_paths_and_skips_bad_entries(tmp_path: Path) -> None:
    root = tmp_path / "cgroup"
    v2 = root / "job" / "step"
    v2.mkdir(parents=True)
    v2_file = v2 / "memory.max"
    v2_file.write_text("max\n", encoding="utf-8")
    proc = tmp_path / "proc-cgroup"
    proc.write_text(f"bad-entry\n0::{v2.relative_to(root)}\n", encoding="utf-8")

    assert resources.cgroup_file("memory.max", proc_cgroup=proc, cgroup_root=root) == v2_file

    v1 = root / "memory" / "legacy" / "step"
    v1.mkdir(parents=True)
    v1_file = v1 / "memory.limit_in_bytes"
    v1_file.write_text("4096\n", encoding="utf-8")
    proc.write_text("5:cpu,memory:/legacy/step\n", encoding="utf-8")

    assert (
        resources.cgroup_file("memory.limit_in_bytes", proc_cgroup=proc, cgroup_root=root)
        == v1_file
    )


def test_allocation_cgroup_file_prefers_job_parent_and_cgroup_value_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "cgroup"
    step = root / "job_17" / "step_2"
    step.mkdir(parents=True)
    (step / "memory.current").write_text("64\n", encoding="utf-8")
    (root / "job_17" / "memory.current").write_text("128\n", encoding="utf-8")
    proc = tmp_path / "proc-cgroup"
    proc.write_text("0::/job_17/step_2\n", encoding="utf-8")

    assert (
        resources.allocation_cgroup_file("memory.current", proc_cgroup=proc, cgroup_root=root)
        == root / "job_17" / "memory.current"
    )

    monkeypatch.setattr(
        resources,
        "allocation_cgroup_file",
        lambda _name: root / "unreadable",
    )
    (root / "unreadable").touch()
    monkeypatch.setattr(
        Path,
        "read_text",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("unreadable")),
    )
    assert resources.cgroup_value("memory.current") == ""


def test_resource_sampler_entrypoint_exits_after_writing_final_sample(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import runpy
    import sys

    run_manifest = tmp_path / "run.json"
    run_manifest.write_text('{"jobs": []}\n', encoding="utf-8")
    output = tmp_path / "samples.csv"
    monkeypatch.setattr(
        sys,
        "argv",
        ["resources.py", "--experiment-run", str(run_manifest), "--out", str(output)],
    )

    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path(str(Path(resources.__file__)), run_name="__main__")

    assert exit_info.value.code == 0
    assert output.read_text(encoding="utf-8").splitlines()[0].startswith("timestamp_utc,")


def test_worker_resource_readers_validate_metadata_errors_and_gpu_parse_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(RuntimeError, match="resource metadata is unavailable"):
        worker_resources.worker_node_resources(tmp_path, "job", "node-a")
    ready = tmp_path / "job" / "node-a" / "ready"
    ready.parent.mkdir(parents=True)
    ready.write_text('{"job_id":"wrong","node":"node-a"}', encoding="utf-8")
    with pytest.raises(RuntimeError, match="identity mismatch"):
        worker_resources.worker_node_resources(tmp_path, "job", "node-a")

    monkeypatch.setattr(
        cast(Any, resources).subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="bad,1\nnot-a-number,2\n"),
    )
    assert resources.gpu_sample() == ([], [])


def test_precision_context_fakes_cuda_autocast_without_allocating_a_gpu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel = object()
    autocast = Mock(return_value=sentinel)
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(torch, "autocast", autocast)

    assert precision.get_autocast_context("cuda", dtype=torch.float16) is sentinel
    autocast.assert_called_once_with(device_type="cuda", dtype=torch.float16, enabled=True)


def test_precision_context_returns_noop_when_cuda_dtype_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(precision, "get_autocast_dtype", lambda _device: None)

    with precision.get_autocast_context("cuda"):
        assert True


@pytest.mark.parametrize(
    ("override", "capability", "supports_bfloat16", "expected"),
    [
        ("auto", (7, 5), True, torch.float16),
        ("auto", (9, 0), True, torch.bfloat16),
        ("auto", None, False, torch.float16),
        ("fp16", (9, 0), True, torch.float16),
        ("bf16", (7, 5), False, torch.bfloat16),
        ("fp32", (9, 0), True, None),
    ],
)
def test_autocast_dtype_respects_gpu_capabilities_and_explicit_overrides(
    monkeypatch: pytest.MonkeyPatch,
    override: str,
    capability: tuple[int, int] | None,
    supports_bfloat16: bool,
    expected: torch.dtype | None,
) -> None:
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(
        precision,
        "discover_device_capabilities",
        lambda _device: SimpleNamespace(
            compute_capability=capability, supports_bfloat16=supports_bfloat16
        ),
    )

    assert precision.get_autocast_dtype("cuda", override) == expected


def test_autocast_dtype_rejects_unknown_override_and_disables_cpu_autocast(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)

    with pytest.raises(ValueError, match="compute.autocast_dtype"):
        precision.get_autocast_dtype("cuda", "tf32")
    assert precision.get_autocast_dtype("cpu", "bf16") is None


def test_accelerator_setup_enables_modern_cuda_tuning_without_gpu_allocation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_precision = Mock()
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(torch, "set_float32_matmul_precision", set_precision)
    monkeypatch.setattr(
        precision,
        "discover_device_capabilities",
        lambda _device: SimpleNamespace(accelerator_backend="cuda", compute_capability=(9, 0)),
    )
    monkeypatch.setattr(torch.backends.cuda.matmul, "allow_tf32", False)
    monkeypatch.setattr(torch.backends.cudnn, "allow_tf32", False)
    monkeypatch.setattr(torch.backends.cudnn, "benchmark", True)
    monkeypatch.delenv("PYTORCH_CUDA_ALLOC_CONF", raising=False)

    precision.configure_accelerator_for_training("cuda", cudnn_benchmark=False)

    assert os.environ["PYTORCH_CUDA_ALLOC_CONF"] == "expandable_segments:True"
    set_precision.assert_called_once_with("high")
    assert torch.backends.cudnn.benchmark is False


def test_compute_contracts_reject_negative_accelerator_and_empty_job() -> None:
    with pytest.raises(ValueError, match="accelerator count must be nonnegative"):
        contracts.ResourceProfile(1, 1, 1, accelerator_count=-1)
    with pytest.raises(ValueError, match="job command and working directory are required"):
        contracts.JobSpec((), contracts.ResourceProfile(1, 1, 1), "/work", {})


def test_automatic_device_capabilities_resolve_to_cpu_without_cuda(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    result = capabilities.discover_device_capabilities("auto")
    assert result.accelerator_kind is None
    assert result.accelerator_count == 0


def test_worker_memory_file_handles_missing_proc_cgroup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        Path,
        "read_text",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("not mounted")),
    )
    assert worker_resources.cgroup_memory_file("memory.max") is None


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        ({"SLURM_MEM_PER_NODE": "2G"}, 2 * GiB),
        ({"SLURM_MEM_PER_CPU": "2048"}, 2 * GiB),
        ({"SLURM_MEM_PER_NODE": "bad"}, None),
        ({}, None),
    ],
)
def test_slurm_resource_environment_readers_parse_and_fail_closed(
    monkeypatch: pytest.MonkeyPatch, env: dict[str, str], expected: int | None
) -> None:
    monkeypatch.delenv("SLURM_MEM_PER_NODE", raising=False)
    monkeypatch.delenv("SLURM_MEM_PER_CPU", raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    assert device._read_slurm_memory_limit() == expected

    monkeypatch.delenv("SLURM_CPUS_PER_TASK", raising=False)
    assert device._read_slurm_cpu_limit() is None
    monkeypatch.setenv("SLURM_CPUS_PER_TASK", "8")
    assert device._read_slurm_cpu_limit() == 8
    monkeypatch.setenv("SLURM_CPUS_PER_TASK", "invalid")
    assert device._read_slurm_cpu_limit() is None


def test_cgroup_v2_cpu_memory_and_process_path_parsers(tmp_path: Path, monkeypatch) -> None:
    cgroup = tmp_path / "job" / "42"
    cgroup.mkdir(parents=True)
    (cgroup / "memory.max").write_text("max\n", encoding="utf-8")
    (cgroup / "memory.current").write_text("0\n", encoding="utf-8")
    (cgroup / "memory.limit_in_bytes").write_text("8192\n", encoding="utf-8")
    (cgroup / "memory.usage_in_bytes").write_text("1024\n", encoding="utf-8")
    (cgroup / "cpu.max").write_text("150000 100000\n", encoding="utf-8")
    current_cgroup_dir = device._current_cgroup_dir
    monkeypatch.setattr(device, "_current_cgroup_dir", lambda: cgroup)
    original_read_text = Path.read_text

    def read_text(path: Path, *, encoding: str | None = None) -> str:
        if path == Path("/sys/fs/cgroup/memory.max"):
            return "max\n"
        if path == Path("/sys/fs/cgroup/memory.current"):
            return "0\n"
        if path in {
            Path("/sys/fs/cgroup/memory/memory.limit_in_bytes"),
            Path("/sys/fs/cgroup/memory/memory.usage_in_bytes"),
        }:
            raise OSError("legacy cgroup path is unavailable")
        return original_read_text(path, encoding=encoding)

    monkeypatch.setattr(Path, "read_text", read_text)

    assert device._read_cgroup_memory_limit() == (8192, 1024)
    assert device._read_cgroup_cpu_count() == 1

    monkeypatch.setattr(
        Path,
        "read_text",
        lambda self, **_kwargs: "0::/job/42\n" if self == Path("/proc/self/cgroup") else "",
    )
    monkeypatch.setattr(device, "_current_cgroup_dir", current_cgroup_dir)
    assert device._current_cgroup_dir() == Path("/sys/fs/cgroup/job/42")
    monkeypatch.setattr(Path, "read_text", lambda *_args, **_kwargs: "4:cpu:/job/42\n")
    assert device._current_cgroup_dir() is None


@pytest.mark.parametrize(
    ("cpu_max", "expected"),
    [("250000 100000", 2), ("100000 0", None)],
)
def test_cgroup_cpu_quota_reads_limits_and_skips_invalid_periods(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cpu_max: str, expected: int | None
) -> None:
    cgroup = tmp_path / "cgroup"
    cgroup.mkdir()
    monkeypatch.setattr(device, "_current_cgroup_dir", lambda: cgroup)

    def read_text(path: Path, *, encoding: str | None = None) -> str:
        if path == cgroup / "cpu.max":
            return cpu_max
        raise OSError("unavailable")

    monkeypatch.setattr(Path, "read_text", read_text)

    assert device._read_cgroup_cpu_count() == expected


def test_current_cgroup_directory_fails_closed_on_proc_read_error(monkeypatch) -> None:
    monkeypatch.setattr(
        Path, "read_text", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("procfs"))
    )

    assert device._current_cgroup_dir() is None


def test_scale_training_cfg_applies_allocation_cap_and_preserves_exact_geometry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from omegaconf import OmegaConf

    monkeypatch.setattr(device, "_read_meminfo", lambda: (128 * GiB, 64 * GiB))
    monkeypatch.setattr(device, "_read_cgroup_memory_limit", lambda: None)
    monkeypatch.setattr(device, "_read_slurm_memory_limit", lambda: None)
    monkeypatch.setattr(device, "_read_cgroup_cpu_count", lambda: None)
    monkeypatch.setattr(device, "_read_slurm_cpu_limit", lambda: 16)
    monkeypatch.setenv("QUANT_RL_MAX_N_ENVS", "4")
    cfg = OmegaConf.create(
        {
            "env": {"n_envs": 8, "data_source": "bundle"},
            "ppo": {"n_steps": 2048, "n_epochs": 5, "batch_size": 128},
        }
    )

    device.scale_training_cfg(cfg, torch.device("cpu"), "mlp")

    assert cfg.env.n_envs == 4
    assert cfg.ppo.n_steps == 2048
    assert cfg.ppo.n_epochs == 5
    assert cfg.ppo.batch_size == 128
    strict_cfg = OmegaConf.create(
        {
            "env": {"n_envs": 8, "data_source": "bundle"},
            "ppo": {"n_steps": 2048, "n_epochs": 5, "batch_size": 128},
        }
    )
    with pytest.raises(ValueError, match="exceeds the estimated host-memory capacity"):
        device.scale_training_cfg(
            strict_cfg, torch.device("cpu"), "mlp", preserve_ppo_geometry=True
        )


def test_scale_training_cfg_uses_mocked_gpu_capacity_without_device_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from omegaconf import OmegaConf

    monkeypatch.setattr(device, "_read_meminfo", lambda: (512 * GiB, 500 * GiB))
    monkeypatch.setattr(device, "_read_cgroup_memory_limit", lambda: None)
    monkeypatch.setattr(device, "_read_slurm_memory_limit", lambda: None)
    monkeypatch.setattr(device, "_read_cgroup_cpu_count", lambda: 32)
    monkeypatch.setattr(device, "_read_slurm_cpu_limit", lambda: None)
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(
        torch.cuda,
        "get_device_properties",
        lambda index: SimpleNamespace(total_memory=80 * GiB) if index == 0 else None,
    )
    monkeypatch.delenv("QUANT_RL_MAX_N_ENVS", raising=False)
    cfg = OmegaConf.create(
        {
            "env": {"n_envs": 8, "data_source": "frames"},
            "ppo": {"n_steps": 2048, "n_epochs": 5, "batch_size": 128},
        }
    )

    device.scale_training_cfg(cfg, torch.device("cuda"), "mlp")

    assert cfg.env.n_envs == 64
    assert cfg.ppo.n_steps == 8192
    assert cfg.ppo.n_epochs == 15
    assert cfg.ppo.batch_size == 4096
