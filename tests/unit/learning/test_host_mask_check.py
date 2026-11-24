"""Host-side eligibility check must fail closed and pass good masks through unchanged."""

from __future__ import annotations

from typing import Any, cast

import gymnasium as gym
import numpy as np
import pytest
from stable_baselines3.common.vec_env import DummyVecEnv
from stable_baselines3.common.vec_env.base_vec_env import VecEnv

from learning.rl.host_mask_check import EligibilityCheckedVecEnv

_WIDTH = 4


class _MaskEnv(gym.Env[Any, Any]):
    """Returns a trade-setup mask that is good, empty, or non-finite on demand."""

    def __init__(self, mask: np.ndarray[Any, Any]) -> None:
        super().__init__()
        self.observation_space = gym.spaces.Dict(
            {
                "trade_setup_mask": gym.spaces.Box(-np.inf, np.inf, (_WIDTH,), np.float32),
                "x": gym.spaces.Box(-1.0, 1.0, (1,), np.float32),
            }
        )
        self.action_space = gym.spaces.Box(-1.0, 1.0, (1,), np.float32)
        self._mask = mask

    def reset(self, *, seed: int | None = None, options: Any = None) -> tuple[Any, dict[str, Any]]:
        return {"trade_setup_mask": self._mask.copy(), "x": np.zeros(1, np.float32)}, {}

    def step(self, action: Any) -> tuple[Any, float, bool, bool, dict[str, Any]]:
        obs, _ = self.reset()
        return obs, 0.0, False, False, {}


def _wrapped(mask: np.ndarray[Any, Any]) -> EligibilityCheckedVecEnv:
    venv: VecEnv = DummyVecEnv([lambda: _MaskEnv(mask)])
    return EligibilityCheckedVecEnv(venv, "trade_setup_mask", _WIDTH)


def test_good_mask_passes_through_reset_and_step() -> None:
    mask = np.ones((1, _WIDTH), dtype=np.float32)
    env = _wrapped(mask)
    obs = cast(dict[str, Any], env.reset())
    assert np.array_equal(obs["trade_setup_mask"], mask)
    stepped = env.step(np.zeros((1, 1), dtype=np.float32))
    obs = cast(dict[str, Any], stepped[0])
    assert np.array_equal(obs["trade_setup_mask"], mask)
    env.close()


def test_row_without_an_eligible_category_fails_closed() -> None:
    env = _wrapped(np.zeros((1, _WIDTH), dtype=np.float32))
    with pytest.raises(ValueError, match="allow a category"):
        env.reset()


def test_non_finite_mask_fails_closed_on_step() -> None:
    mask = np.ones((1, _WIDTH), dtype=np.float32)
    env = _wrapped(mask)
    env.reset()
    inner = cast(DummyVecEnv, env.venv)
    cast(_MaskEnv, inner.envs[0].unwrapped)._mask = np.full((1, _WIDTH), np.nan, dtype=np.float32)
    with pytest.raises(ValueError, match="finite"):
        env.step(np.zeros((1, 1), dtype=np.float32))
    env.close()
