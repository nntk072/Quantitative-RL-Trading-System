from __future__ import annotations

import subprocess
from typing import Any, cast

import pytest

from compute.slurm import worker_resources


def test_gpu_inventory_returns_no_devices_for_empty_visible_device_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", " , , ")
    monkeypatch.setattr(
        cast(Any, worker_resources).subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="0, GPU-a, 40960, 20480\n",
            stderr="",
        ),
    )

    assert worker_resources.gpu_memory_inventory() == []
