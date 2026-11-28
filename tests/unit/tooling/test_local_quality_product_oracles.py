"""Small product-oracle and finite-horizon GAE validation without training experiments."""

from __future__ import annotations

import numpy as np
import pytest
import torch
from gymnasium import spaces
from stable_baselines3.common.buffers import DictRolloutBuffer
from tools.quality.local_checks.product_oracles import PRODUCT_ORACLES, exercise_product_oracles
from tools.quality.local_checks.trace_comparison import compare_quality_traces


@pytest.mark.parametrize("target", list(PRODUCT_ORACLES))
@pytest.mark.parametrize("payload", [b"", bytes(range(24)), b"\xff" * 128])
def test_independent_product_oracles(target: str, payload: bytes) -> None:
    """Check representative empty, mixed and boundary inputs."""
    exercise_product_oracles(payload, target)


def test_gae_finite_horizon_oracle() -> None:
    """Compare SB3 GAE recurrence with the direct finite sum for each rollout step."""
    from learning.rl.rollout_buffer import DeviceDictRolloutBuffer

    obs = spaces.Dict({"x": spaces.Box(-1.0, 1.0, (1,), dtype=np.float32)})
    action = spaces.Box(-1.0, 1.0, (1,), dtype=np.float32)
    reward = np.array([0.2, -0.1, 1.0, 0.4], dtype=np.float32)
    value = np.array([0.1, 0.3, 0.2, 0.5], dtype=np.float32)
    starts = np.array([1, 0, 1, 0], dtype=np.float32)
    gamma, lam = 0.97, 0.91
    for cls in (DictRolloutBuffer, DeviceDictRolloutBuffer):
        buffer = cls(4, obs, action, device="cpu", gamma=gamma, gae_lambda=lam, n_envs=1)
        buffer.rewards[:, 0] = reward
        buffer.values[:, 0] = value
        buffer.episode_starts[:, 0] = starts
        buffer.compute_returns_and_advantage(torch.tensor([0.25]), np.array([0], dtype=np.float32))
        deltas = [
            reward[i] + gamma * (1 - starts[i + 1]) * value[i + 1] - value[i]
            if i < 3
            else reward[i] + gamma * 0.25 - value[i]
            for i in range(4)
        ]
        expected = []
        for i in range(4):
            total = 0.0
            for j in range(i, 4):
                if j > i and starts[j]:
                    break
                total += (gamma * lam) ** (j - i) * deltas[j]
            expected.append(total)
        np.testing.assert_allclose(buffer.advantages[:, 0], expected, atol=1e-6, rtol=1e-6)
        np.testing.assert_allclose(
            buffer.returns[:, 0], np.array(expected) + value, atol=1e-6, rtol=1e-6
        )


def test_trace_tolerances_never_hide_structural_mismatches() -> None:
    """Numeric tolerances are field-specific and do not coerce booleans."""
    assert compare_quality_traces({"x": 1.0}, {"x": 1.01}, {"$.x": {"atol": 0.02}}) == []
    assert compare_quality_traces({"x": 1}, {"x": True}, {"$": {"atol": 100}})
    assert compare_quality_traces([1, 2], [1], {})
    assert compare_quality_traces(float("nan"), float("nan"), {})
