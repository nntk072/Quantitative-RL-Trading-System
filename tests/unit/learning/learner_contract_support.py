"""Shared synthetic environment and SB3 factories for the learner-contract tests.

The environment is a tiny deterministic gymnasium task with no market data.
It exposes an explicit snapshot so exact-resume tests can restore it.
"""

from __future__ import annotations

from typing import Any

import gymnasium as gym
import numpy as np
import torch
from gymnasium import spaces
from stable_baselines3 import PPO, SAC


class ContractEnv(gym.Env[Any, Any]):
    """Deterministic 2-D continuous task: reward favours actions near the state."""

    observation_space = spaces.Box(-1.0, 1.0, (3,), dtype=np.float32)
    action_space = spaces.Box(-1.0, 1.0, (2,), dtype=np.float32)

    def __init__(self, horizon: int = 8) -> None:
        self._horizon = horizon
        self._t = 0
        self._state: np.ndarray[Any, Any] = np.zeros(3, dtype=np.float32)

    def reset(
        self, *, seed: int | None = None, options: Any = None
    ) -> tuple[np.ndarray[Any, Any], dict[str, Any]]:
        super().reset(seed=seed)
        self._t = 0
        self._state = self.np_random.uniform(-1, 1, size=3).astype(np.float32)
        return self._state.copy(), {}

    def step(
        self, action: np.ndarray[Any, Any]
    ) -> tuple[np.ndarray[Any, Any], float, bool, bool, dict[str, Any]]:
        self._t += 1
        reward = -float(np.sum((action - self._state[:2]) ** 2))
        self._state = np.clip(0.9 * self._state + 0.1 * np.r_[action, 0.0], -1, 1).astype(
            np.float32
        )
        truncated = self._t >= self._horizon
        return self._state.copy(), reward, False, truncated, {}

    def get_state(self) -> dict[str, Any]:
        """Return an explicit copy of the internal state for exact-resume tests."""
        return {
            "t": self._t,
            "state": self._state.copy(),
            "bit_generator": self.np_random.bit_generator.state,
        }

    def set_state(self, snapshot: dict[str, Any]) -> None:
        """Restore a snapshot produced by :meth:`get_state`."""
        self._t = int(snapshot["t"])
        self._state = np.asarray(snapshot["state"]).copy()
        self.np_random.bit_generator.state = snapshot["bit_generator"]


def state_dict_equal(left: dict[str, torch.Tensor], right: dict[str, torch.Tensor]) -> bool:
    """Return whether two state dicts have the same keys and bitwise-equal tensors."""
    if left.keys() != right.keys():
        return False
    return all(torch.equal(left[key], right[key]) for key in left)


def ppo_model(seed: int, env: gym.Env[Any, Any] | None = None) -> PPO:
    """Build a small CPU PPO model on the contract environment."""
    return PPO(
        "MlpPolicy",
        ContractEnv() if env is None else env,
        n_steps=16,
        batch_size=16,
        n_epochs=2,
        seed=seed,
        device="cpu",
        verbose=0,
    )


def sac_model(seed: int, env: gym.Env[Any, Any] | None = None) -> SAC:
    """Build a small CPU SAC model on the contract environment."""
    return SAC(
        "MlpPolicy",
        ContractEnv() if env is None else env,
        buffer_size=200,
        learning_starts=10,
        batch_size=16,
        train_freq=1,
        gradient_steps=1,
        seed=seed,
        device="cpu",
        verbose=0,
    )
