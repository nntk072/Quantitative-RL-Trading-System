"""Replay loop and statistics of the captured PPO update, run on CPU with a fake captured step.

The captured step itself needs CUDA. These tests replace it with a fake that performs the same
buffer copies and accumulations, so the loop, the logged statistics and the non-finite-loss
error are exercised without a GPU.
"""

from __future__ import annotations

from itertools import count
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import numpy as np
import pytest
import torch

from learning.rl import update_graph
from learning.rl.update_graph import _graphed_train, _StepGraph


def _sample(value: float) -> SimpleNamespace:
    return SimpleNamespace(
        observations={"x": torch.full((2,), value)},
        actions=torch.full((2,), value),
        old_log_prob=torch.full((2,), value),
        advantages=torch.full((2,), value),
        returns=torch.full((2,), value),
    )


class _FakeStepGraph:
    """Stands in for the captured step: counts builds and accumulates fixed statistics."""

    builds = 0
    bad_loss = False

    def __init__(self, model: Any, sample: Any) -> None:
        type(self).builds += 1
        self.clip = torch.zeros(())
        self.stats = torch.tensor([1.0, 2.0, 3.0, 4.0])
        self.kl = torch.tensor(0.5)
        self.loss = torch.tensor(7.0)
        self.bad = torch.tensor(type(self).bad_loss)

    def run(self, sample: Any, stats_total: torch.Tensor, kl_epoch: torch.Tensor) -> None:
        stats_total.add_(self.stats)
        kl_epoch.add_(self.kl)


def _buffer(samples_per_epoch: int) -> SimpleNamespace:
    values = np.linspace(0.0, 1.0, samples_per_epoch)
    returns = values + 0.5

    def get(batch_size: int) -> Any:
        return iter([_sample(float(index)) for index in range(0, samples_per_epoch, batch_size)])

    return SimpleNamespace(
        buffer_size=samples_per_epoch,
        n_envs=1,
        values=values,
        returns=returns,
        get=get,
        _device_rollout={"observation:mask": torch.zeros(1)},
    )


def _model(*, with_log_std: bool, n_epochs: int = 2) -> SimpleNamespace:
    policy = SimpleNamespace(
        device=torch.device("cpu"),
        trade_setup_mask_key="mask",
        optimizer=Mock(),
        set_training_mode=Mock(),
        validate_rollout_masks=Mock(),
        reset_mode_prior_stats=Mock(),
    )
    if with_log_std:
        policy.log_std = torch.zeros(3)
    return SimpleNamespace(
        policy=policy,
        batch_size=2,
        n_epochs=n_epochs,
        rollout_buffer=_buffer(samples_per_epoch=4),
        clip_range=lambda _remaining: 0.2,
        _current_progress_remaining=1.0,
        _update_learning_rate=Mock(),
        _n_updates=0,
        logger=Mock(),
        normalize_advantage=True,
    )


@pytest.fixture(autouse=True)
def _cpu_dispatch_with_fake_step(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeStepGraph.builds = 0
    _FakeStepGraph.bad_loss = False
    monkeypatch.setattr(update_graph, "_graph_supported", lambda model: True)
    monkeypatch.setattr(update_graph, "_StepGraph", _FakeStepGraph)


def test_replay_loop_accumulates_statistics_and_logs_them() -> None:
    model = _model(with_log_std=True)
    state: dict[str, Any] = {}

    _graphed_train(model, Mock(), state)

    assert _FakeStepGraph.builds == 1
    assert model._n_updates == 2  # one increment per epoch
    model._update_learning_rate.assert_called_once()
    model.policy.set_training_mode.assert_called_once_with(True)
    recorded = {
        call.args[0]: call.args[1] for call in model.logger.record.call_args_list if call.args
    }
    assert recorded["train/entropy_loss"] == pytest.approx(3.0)
    assert recorded["train/policy_gradient_loss"] == pytest.approx(1.0)
    assert recorded["train/value_loss"] == pytest.approx(2.0)
    assert recorded["train/clip_fraction"] == pytest.approx(4.0)
    assert recorded["train/approx_kl"] == pytest.approx(0.5)
    assert recorded["train/loss"] == pytest.approx(7.0)
    assert "train/std" in recorded


def test_replay_loop_without_log_std_skips_the_std_statistic() -> None:
    model = _model(with_log_std=False)

    _graphed_train(model, Mock(), {})

    recorded = [call.args[0] for call in model.logger.record.call_args_list if call.args]
    assert "train/std" not in recorded
    assert "train/explained_variance" in recorded


def test_replay_loop_reuses_the_captured_step_across_updates() -> None:
    model = _model(with_log_std=False)
    state: dict[str, Any] = {}

    _graphed_train(model, Mock(), state)
    _graphed_train(model, Mock(), state)

    assert _FakeStepGraph.builds == 1


def test_non_finite_loss_raises_after_the_update() -> None:
    _FakeStepGraph.bad_loss = True
    model = _model(with_log_std=False)

    with pytest.raises(ValueError, match="non-finite PPO loss"):
        _graphed_train(model, Mock(), {})


def test_step_graph_run_copies_the_minibatch_and_steps_the_optimizer() -> None:
    graph: Any = _StepGraph.__new__(_StepGraph)
    replays = count()
    graph.obs = {"x": torch.zeros(2)}
    graph.actions = torch.zeros(2)
    graph.old_log_prob = torch.zeros(2)
    graph.advantages = torch.zeros(2)
    graph.returns = torch.zeros(2)
    graph.stats = torch.tensor([1.0, 0.0, 0.0, 0.0])
    graph.kl = torch.tensor(0.25)
    graph.graph = SimpleNamespace(replay=lambda: next(replays))
    graph.model = SimpleNamespace(policy=SimpleNamespace(optimizer=Mock()))
    stats_total = torch.zeros(4)
    kl_epoch = torch.zeros(())

    graph.run(_sample(3.0), stats_total, kl_epoch)

    assert torch.equal(graph.obs["x"], torch.full((2,), 3.0))
    assert torch.equal(graph.actions, torch.full((2,), 3.0))
    assert next(replays) == 1
    graph.model.policy.optimizer.step.assert_called_once_with()
    assert stats_total[0].item() == pytest.approx(1.0)
    assert kl_epoch.item() == pytest.approx(0.25)
