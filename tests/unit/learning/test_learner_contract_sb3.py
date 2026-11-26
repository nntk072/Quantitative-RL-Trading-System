"""SB3 PPO and SAC contract checks on a synthetic CPU environment.

These cover seeded determinism, weights-only load, the replay-buffer
truncation rule, and the exact-resume gap. The environment is a tiny
deterministic gymnasium task with no market data.
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any

import gymnasium as gym
import numpy as np
import pytest
import torch
from gymnasium import spaces
from stable_baselines3 import PPO, SAC
from stable_baselines3.common.buffers import ReplayBuffer


class _ContractEnv(gym.Env[Any, Any]):
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


def _state_dict_equal(left: dict[str, torch.Tensor], right: dict[str, torch.Tensor]) -> bool:
    if left.keys() != right.keys():
        return False
    return all(torch.equal(left[key], right[key]) for key in left)


def _ppo(seed: int) -> PPO:
    return PPO(
        "MlpPolicy",
        _ContractEnv(),
        n_steps=16,
        batch_size=16,
        n_epochs=2,
        seed=seed,
        device="cpu",
        verbose=0,
    )


def _sac(seed: int, env: gym.Env[Any, Any] | None = None) -> SAC:
    return SAC(
        "MlpPolicy",
        _ContractEnv() if env is None else env,
        buffer_size=200,
        learning_starts=10,
        batch_size=16,
        train_freq=1,
        gradient_steps=1,
        seed=seed,
        device="cpu",
        verbose=0,
    )


def test_seeded_ppo_training_is_bitwise_reproducible_on_cpu() -> None:
    first = _ppo(seed=3)
    first.learn(total_timesteps=32)
    second = _ppo(seed=3)
    second.learn(total_timesteps=32)
    assert _state_dict_equal(first.policy.state_dict(), second.policy.state_dict())


def test_seeded_sac_training_is_bitwise_reproducible_on_cpu() -> None:
    first = _sac(seed=3)
    first.learn(total_timesteps=40)
    second = _sac(seed=3)
    second.learn(total_timesteps=40)
    assert _state_dict_equal(first.policy.state_dict(), second.policy.state_dict())


def test_ppo_weights_only_load_reproduces_deterministic_inference(tmp_path: Path) -> None:
    model = _ppo(seed=5)
    model.learn(total_timesteps=32)
    path = tmp_path / "ppo_weights"
    model.save(path)
    restored = PPO.load(path, device="cpu")
    obs = np.linspace(-0.5, 0.5, 3, dtype=np.float32)
    expected, _ = model.predict(obs, deterministic=True)
    actual, _ = restored.predict(obs, deterministic=True)
    np.testing.assert_array_equal(actual, expected)
    assert restored.num_timesteps == model.num_timesteps
    assert _state_dict_equal(model.policy.state_dict(), restored.policy.state_dict())


def test_sac_checkpoint_restores_optimizer_state_and_counters(tmp_path: Path) -> None:
    model = _sac(seed=7)
    model.learn(total_timesteps=40)
    path = tmp_path / "sac_weights"
    model.save(path)
    restored = SAC.load(path, device="cpu")
    assert restored.num_timesteps == model.num_timesteps
    assert restored._n_updates == model._n_updates
    original_state = model.actor.optimizer.state_dict()["state"]
    restored_state = restored.actor.optimizer.state_dict()["state"]
    assert original_state.keys() == restored_state.keys()
    for key in original_state:
        for name in original_state[key]:
            value = original_state[key][name]
            if isinstance(value, torch.Tensor):
                assert torch.equal(value, restored_state[key][name])


def test_sac_default_checkpoint_omits_the_replay_buffer(tmp_path: Path) -> None:
    # Replay contents are not part of a default SAC save; resuming starts from an
    # empty buffer. This pins the gap that the exact-resume test below records.
    model = _sac(seed=9)
    model.learn(total_timesteps=40)
    assert model.replay_buffer is not None and model.replay_buffer.size() > 0
    path = tmp_path / "sac_default"
    model.save(path)
    with zipfile.ZipFile(f"{path}.zip") as archive:
        names = archive.namelist()
    assert not any("replay_buffer" in name for name in names)
    restored = SAC.load(path, device="cpu")
    assert restored.replay_buffer is not None and restored.replay_buffer.size() == 0


@pytest.mark.xfail(
    strict=True,
    reason=(
        "exact resume is not provided: the default SAC checkpoint omits the replay "
        "buffer, the RNG state and the environment state, so a resumed run cannot "
        "reproduce a continued run"
    ),
)
def test_sac_exact_resume_reproduces_a_continued_run(tmp_path: Path) -> None:
    continued = _sac(seed=11)
    continued.learn(total_timesteps=40)
    path = tmp_path / "sac_exact"
    continued.save(path)
    resumed = SAC.load(path, env=_ContractEnv(), device="cpu")
    continued.learn(total_timesteps=20, reset_num_timesteps=False)
    resumed.learn(total_timesteps=20, reset_num_timesteps=False)
    assert _state_dict_equal(continued.policy.state_dict(), resumed.policy.state_dict())


def test_replay_sampling_never_treats_a_time_limit_as_termination() -> None:
    buffer = ReplayBuffer(
        8,
        spaces.Box(0.0, 100.0, (1,), dtype=np.float32),
        spaces.Box(-1.0, 1.0, (1,), dtype=np.float32),
        device="cpu",
        n_envs=1,
        handle_timeout_termination=True,
    )
    terminated_at, truncated_at = 2, 4
    for index in range(6):
        done = index in (terminated_at, truncated_at)
        infos = [{"TimeLimit.truncated": index == truncated_at and done}]
        buffer.add(
            np.array([[float(index)]], dtype=np.float32),
            np.array([[float(index + 1)]], dtype=np.float32),
            np.array([[0.0]], dtype=np.float32),
            np.array([1.0], dtype=np.float32),
            np.array([done], dtype=np.float32),
            infos,
        )
    torch.manual_seed(0)
    np.random.seed(0)
    samples = buffer.sample(512)
    observed = samples.observations.numpy().reshape(-1).astype(int)
    next_observed = samples.next_observations.numpy().reshape(-1).astype(int)
    dones = samples.dones.numpy().reshape(-1)
    assert observed.min() >= 0 and observed.max() <= 5, "sampled an unwritten slot"
    np.testing.assert_array_equal(next_observed, observed + 1)
    assert np.all(dones[observed == terminated_at] == 1.0)
    assert np.all(dones[observed == truncated_at] == 0.0)
    assert np.all(dones[~np.isin(observed, [terminated_at])] == 0.0)
