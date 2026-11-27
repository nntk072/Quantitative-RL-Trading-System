"""Exercise PPO CUDA-graph construction and minibatch math on CPU with fake CUDA APIs."""

from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest
import torch
from torch import nn

from learning.rl.update_graph import _StepGraph


class _FakeStream:
    def __init__(self) -> None:
        self.waited_for: list[Any] = []

    def wait_stream(self, stream: Any) -> None:
        self.waited_for.append(stream)


class _FakeGraph:
    def __init__(self) -> None:
        self.replays = 0

    def replay(self) -> None:
        self.replays += 1


class _Policy(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.weight = nn.Parameter(torch.tensor(0.5))
        self.optimizer = torch.optim.SGD(self.parameters(), lr=0.0)
        self.device = torch.device("cpu")
        self.reset_mode_prior_stats = Mock()
        self.evaluate_calls = 0

    def evaluate_actions(
        self, observations: dict[str, torch.Tensor], actions: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        self.evaluate_calls += 1
        values = self.weight * observations["x"]
        log_prob = -torch.square(actions - self.weight)
        entropy = torch.full_like(log_prob, 0.25)
        return values, log_prob, entropy


def _sample() -> SimpleNamespace:
    return SimpleNamespace(
        observations={"x": torch.tensor([1.0, 2.0])},
        actions=torch.tensor([0.0, 0.0]),
        old_log_prob=torch.tensor([-0.2, -0.1]),
        advantages=torch.tensor([1.0, -1.0]),
        returns=torch.tensor([0.5, 1.5]),
    )


def test_step_graph_captures_cpu_math_and_restores_capture_contexts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    side_stream = _FakeStream()
    current_stream = _FakeStream()
    graph = _FakeGraph()
    synchronizations: list[None] = []
    stale_capture_modes: list[bool] = []
    monkeypatch.setattr(torch.cuda, "Stream", lambda: side_stream)
    monkeypatch.setattr(torch.cuda, "current_stream", lambda: current_stream)
    monkeypatch.setattr(torch.cuda, "stream", lambda _stream: nullcontext())
    monkeypatch.setattr(torch.cuda, "graph", lambda _graph, **_kwargs: nullcontext())
    monkeypatch.setattr(torch.cuda, "CUDAGraph", lambda: graph)
    monkeypatch.setattr(torch.cuda, "synchronize", lambda: synchronizations.append(None))
    monkeypatch.setattr(
        torch.autograd.graph,
        "set_override_stale_capture_stream",
        stale_capture_modes.append,
        raising=False,
    )
    policy = _Policy()
    model = SimpleNamespace(
        policy=policy,
        normalize_advantage=True,
        ent_coef=0.01,
        vf_coef=0.5,
        max_grad_norm=1.0,
    )
    sample = _sample()

    step = _StepGraph(model, sample)
    step.clip.fill_(0.2)
    step._step()

    values = sample.observations["x"] * policy.weight
    log_prob = -torch.square(sample.actions - policy.weight)
    entropy = torch.full_like(log_prob, 0.25)
    advantages = (sample.advantages - sample.advantages.mean()) / (sample.advantages.std() + 1e-8)
    ratio = torch.exp(log_prob - sample.old_log_prob)
    policy_loss = -torch.minimum(
        advantages * ratio,
        advantages * torch.clamp(ratio, 1 - step.clip, 1 + step.clip),
    ).mean()
    clip_fraction = torch.mean((torch.abs(ratio - 1) > step.clip).float())
    value_loss = torch.nn.functional.mse_loss(sample.returns, values)
    entropy_loss = -entropy.mean()
    expected_stats = torch.stack((policy_loss, value_loss, entropy_loss, clip_fraction))
    log_ratio = log_prob - sample.old_log_prob
    expected_kl = torch.mean((torch.exp(log_ratio) - 1) - log_ratio)

    assert torch.allclose(step.stats, expected_stats)
    assert torch.allclose(step.kl, expected_kl)
    assert torch.allclose(step.loss, policy_loss + 0.01 * entropy_loss + 0.5 * value_loss)
    assert not step.bad.item()
    assert policy.evaluate_calls == 5  # three warmups, capture, and the direct math check
    policy.reset_mode_prior_stats.assert_called_once_with()
    assert stale_capture_modes == [True, False]
    assert side_stream.waited_for == [current_stream]
    assert current_stream.waited_for == [side_stream]
    assert synchronizations == [None]
