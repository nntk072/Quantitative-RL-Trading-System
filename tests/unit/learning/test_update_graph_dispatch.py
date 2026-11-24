"""Dispatch rules of the captured PPO update, checked on CPU with fake models.

Capturing the update needs CUDA. These tests cover which models take the captured path and
which fall back to the original SB3 update, which runs on any device.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import torch

from learning.rl.update_graph import _graph_supported, _graphed_train, install_graphed_update


def _policy(device: str = "cpu", *, masks: bool = True) -> SimpleNamespace:
    policy = SimpleNamespace(device=torch.device(device))
    if masks:
        policy.validate_rollout_masks = lambda _masks: None
    return policy


def _model(
    policy: Any,
    *,
    target_kl: float | None = None,
    clip_range_vf: float | None = None,
    buffer_size: int = 2,
    n_envs: int = 4,
    batch_size: int = 4,
    original: Mock | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        policy=policy,
        target_kl=target_kl,
        clip_range_vf=clip_range_vf,
        rollout_buffer=SimpleNamespace(buffer_size=buffer_size, n_envs=n_envs),
        batch_size=batch_size,
        train=original or Mock(),
    )


def test_graph_supported_only_for_cuda_policies_without_early_stopping() -> None:
    assert _graph_supported(_model(_policy("cuda")))
    assert not _graph_supported(_model(_policy("cpu")))
    assert not _graph_supported(_model(_policy("cuda"), target_kl=0.02))
    assert not _graph_supported(_model(_policy("cuda"), clip_range_vf=0.2))
    assert not _graph_supported(_model(_policy("cuda", masks=False)))


def test_unsupported_model_uses_the_original_update() -> None:
    original = Mock()
    model = _model(_policy("cpu"), original=original)

    _graphed_train(model, original, {})

    original.assert_called_once_with()


def test_update_with_uneven_minibatches_uses_the_original_update() -> None:
    original = Mock()
    # 2 steps x 3 envs = 6 samples, which the batch size of 4 does not divide evenly.
    model = _model(_policy("cuda"), buffer_size=2, n_envs=3, batch_size=4, original=original)

    _graphed_train(model, original, {})

    original.assert_called_once_with()


def test_install_routes_train_to_the_captured_path_only_when_supported() -> None:
    original = Mock()
    model = _model(_policy("cpu"), original=original)

    install_graphed_update(model)
    model.train()

    original.assert_called_once_with()
