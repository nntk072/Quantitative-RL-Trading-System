"""Device resolution and RAM/VRAM-based sizing of the training configuration."""

from __future__ import annotations

import pytest
import torch

from compute.environment import device

GiB = 1024**3


def test_get_device_auto_without_cuda_is_cpu(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)

    assert device.get_device(None) == torch.device("cpu")
    assert device.get_device("auto") == torch.device("cpu")
    assert device.get_device("") == torch.device("cpu")


def test_get_device_auto_with_cuda_is_cuda(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)

    assert device.get_device("AUTO") == torch.device("cuda")


def test_get_device_explicit_value_is_used_as_given() -> None:
    assert device.get_device("cpu") == torch.device("cpu")
    assert device.get_device("cuda:1") == torch.device("cuda", 1)


def test_get_device_rejects_an_invalid_value() -> None:
    with pytest.raises(ValueError, match="Invalid device value"):
        device.get_device("not-a-device")


def test_suggest_n_steps_grows_only_for_large_cards() -> None:
    assert device.suggest_n_steps(current=2048, vram_bytes=None) == 2048
    assert device.suggest_n_steps(current=2048, vram_bytes=40 * GiB) == 8192
    assert device.suggest_n_steps(current=2048, vram_bytes=20 * GiB) == 4096
    assert device.suggest_n_steps(current=2048, vram_bytes=8 * GiB) == 2048
    assert device.suggest_n_steps(current=10000, vram_bytes=40 * GiB) == 10000


def test_suggest_n_envs_single_env_is_left_alone() -> None:
    assert (
        device.suggest_n_envs(
            requested=1,
            total_ram_bytes=512 * GiB,
            available_ram_bytes=400 * GiB,
            cpu_count=32,
            vram_bytes=141 * GiB,
        )
        == 1
    )


def test_suggest_n_envs_on_cpu_is_capped_by_ram() -> None:
    # 64 GiB free leaves room for 8 workers at the default 4 GiB each.
    assert (
        device.suggest_n_envs(
            requested=8,
            total_ram_bytes=128 * GiB,
            available_ram_bytes=64 * GiB,
            cpu_count=8,
            vram_bytes=None,
        )
        == 8
    )


def test_suggest_n_envs_on_cpu_with_little_ram_falls_to_one() -> None:
    assert (
        device.suggest_n_envs(
            requested=8,
            total_ram_bytes=16 * GiB,
            available_ram_bytes=6 * GiB,
            cpu_count=8,
            vram_bytes=None,
        )
        == 1
    )


def test_suggest_n_envs_on_large_gpu_follows_the_ram_tier() -> None:
    assert (
        device.suggest_n_envs(
            requested=8,
            total_ram_bytes=1024 * GiB,
            available_ram_bytes=600 * GiB,
            cpu_count=64,
            vram_bytes=141 * GiB,
        )
        == 128
    )
    assert (
        device.suggest_n_envs(
            requested=8,
            total_ram_bytes=1024 * GiB,
            available_ram_bytes=300 * GiB,
            cpu_count=64,
            vram_bytes=141 * GiB,
        )
        == 64
    )


def test_suggest_n_envs_with_custom_worker_size_is_capped_by_ram() -> None:
    result = device.suggest_n_envs(
        requested=64,
        total_ram_bytes=512 * GiB,
        available_ram_bytes=100 * GiB,
        cpu_count=64,
        vram_bytes=None,
        worker_ram_bytes=8 * GiB,
    )

    assert result <= 16
    assert result & (result - 1) == 0


def test_suggest_batch_size_without_vram_keeps_current() -> None:
    assert (
        device.suggest_batch_size(
            current=256,
            n_steps=2048,
            n_envs=8,
            vram_bytes=None,
            arch="mlp",
        )
        == 256
    )
