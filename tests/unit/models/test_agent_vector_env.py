"""Regression coverage for vectorized environment attachment on PPO resume."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import gymnasium as gym
import numpy as np
from omegaconf import OmegaConf
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv

from learning.rl.agent import build_vector_env
from learning.rl.environment_adapter import ShardedBundleVecEnv


class _TinyDictEnv(gym.Env[dict[str, np.ndarray[Any, Any]], int]):
    """Small deterministic environment for sharded VecEnv contract tests."""

    metadata = {"render_modes": ["rgb_array"]}

    def __init__(
        self,
        env_id: int,
        *,
        terminates: bool = False,
        truncates: bool = False,
        close_path: Path | None = None,
    ) -> None:
        self.env_id = env_id
        self.terminates = terminates
        self.truncates = truncates
        self.close_path = close_path
        self.marker = "initial"
        self.steps = 0
        self.render_mode = "rgb_array"
        self.observation_space = gym.spaces.Dict(
            {"position": gym.spaces.Box(-100.0, 100.0, shape=(2,), dtype=np.float32)}
        )
        self.action_space = gym.spaces.Discrete(2)

    def _observation(self) -> dict[str, np.ndarray[Any, Any]]:
        return {"position": np.asarray([self.env_id, self.steps], dtype=np.float32)}

    def reset(
        self, *, seed: int | None = None, options: dict[str, Any] | None = None
    ) -> tuple[dict[str, np.ndarray[Any, Any]], dict[str, Any]]:
        super().reset(seed=seed)
        self.steps = 0
        return self._observation(), {"env_id": self.env_id, "seed": seed}

    def step(
        self, action: int
    ) -> tuple[dict[str, np.ndarray[Any, Any]], float, bool, bool, dict[str, Any]]:
        if int(action) == 99:
            raise RuntimeError("step sentinel")
        self.steps += 1
        info = {"env_id": self.env_id, "steps": self.steps}
        return (
            self._observation(),
            float(self.env_id + int(action)),
            self.terminates,
            self.truncates,
            info,
        )

    def render(self) -> np.ndarray[Any, Any]:
        return np.full((2, 2, 3), self.env_id, dtype=np.uint8)

    def describe(self, prefix: str, *, multiplier: int = 1) -> str:
        return f"{prefix}{self.env_id * multiplier}"

    def close(self) -> None:
        if self.close_path is not None:
            self.close_path.write_text(str(self.env_id), encoding="utf-8")


def _make_cartpole() -> gym.Env[Any, Any]:
    return gym.make("CartPole-v1")


def _make_tiny_dict_env_factory(env_id: int) -> Callable[[], gym.Env[Any, Any]]:
    return lambda: _TinyDictEnv(env_id)


def test_resumed_ppo_uses_configured_vector_environment(tmp_path: Path) -> None:
    checkpoint = tmp_path / "single_env_ppo"
    original = PPO("MlpPolicy", _make_cartpole(), n_steps=8, batch_size=8, device="cpu")
    original.save(checkpoint)
    original_env = original.get_env()
    assert original_env is not None
    original_env.close()

    cfg = OmegaConf.create({"env": {"n_envs": 2, "data_source": "frames"}})
    resume_env = build_vector_env(_make_cartpole(), cfg, _make_cartpole)
    try:
        resumed = PPO.load(checkpoint, env=resume_env, device="cpu")
        assert resumed.n_envs == 2
        assert resumed.n_steps == 8
    finally:
        resume_env.close()


def test_serial_backend_keeps_logical_environment_count() -> None:
    cfg = OmegaConf.create(
        {"env": {"n_envs": 3, "data_source": "bundle", "vector_backend": "serial"}}
    )
    parent_env = _make_cartpole()
    vec_env = build_vector_env(parent_env, cfg, _make_cartpole)
    try:
        assert isinstance(vec_env, DummyVecEnv)
        assert vec_env.num_envs == 3
        assert not isinstance(vec_env, SubprocVecEnv)
    finally:
        vec_env.close()
        parent_env.close()


def test_serial_and_subprocess_backends_match_seeded_traces() -> None:
    serial_cfg = OmegaConf.create(
        {"env": {"n_envs": 2, "data_source": "bundle", "vector_backend": "serial"}}
    )
    subproc_cfg = OmegaConf.create(
        {"env": {"n_envs": 2, "data_source": "bundle", "vector_backend": "subproc"}}
    )
    serial_parent = _make_cartpole()
    subproc_parent = _make_cartpole()
    serial = build_vector_env(serial_parent, serial_cfg, _make_cartpole)
    subproc = build_vector_env(subproc_parent, subproc_cfg, _make_cartpole)
    try:
        serial.seed(314)
        subproc.seed(314)
        serial_obs = serial.reset()
        subproc_obs = subproc.reset()
        assert (serial_obs == subproc_obs).all()

        actions = [0, 1]
        for _ in range(25):
            serial_obs, serial_rewards, serial_dones, serial_infos = serial.step(actions)
            subproc_obs, subproc_rewards, subproc_dones, subproc_infos = subproc.step(actions)
            np.testing.assert_array_equal(serial_obs, subproc_obs)
            np.testing.assert_array_equal(serial_rewards, subproc_rewards)
            np.testing.assert_array_equal(serial_dones, subproc_dones)
            for serial_info, subproc_info in zip(serial_infos, subproc_infos, strict=True):
                assert serial_info.keys() == subproc_info.keys()
                for key in serial_info:
                    serial_value = serial_info[key]
                    subproc_value = subproc_info[key]
                    if isinstance(serial_value, np.ndarray):
                        np.testing.assert_array_equal(serial_value, subproc_value)
                    else:
                        assert serial_value == subproc_value
    finally:
        serial.close()
        subproc.close()
        serial_parent.close()
        subproc_parent.close()


def test_sharded_bundle_backend_matches_subprocess_traces_and_index_order() -> None:
    serial_cfg = OmegaConf.create(
        {"env": {"n_envs": 3, "data_source": "bundle", "vector_backend": "serial"}}
    )
    sharded_cfg = OmegaConf.create(
        {
            "env": {
                "n_envs": 3,
                "data_source": "bundle",
                "vector_backend": "sharded_bundle",
                "vector_shards": 2,
            }
        }
    )
    serial_parent = _make_cartpole()
    sharded_parent = _make_cartpole()
    serial = build_vector_env(serial_parent, serial_cfg, _make_cartpole)
    sharded = build_vector_env(sharded_parent, sharded_cfg, _make_cartpole)
    try:
        assert isinstance(sharded, ShardedBundleVecEnv)
        assert sharded.num_envs == 3
        assert len(sharded.processes) == 2
        assert sharded.num_shards == 2
        assert sharded.logical_envs_per_shard == [2, 1]
        serial.seed(314)
        sharded.seed(314)
        np.testing.assert_array_equal(serial.reset(), sharded.reset())

        assert serial.get_attr("np_random_seed", indices=[2, 0]) == [316, 314]
        assert sharded.get_attr("np_random_seed", indices=[2, 0]) == [316, 314]

        actions = np.asarray([0, 1, 0])
        for _ in range(80):
            serial_obs, serial_rewards, serial_dones, serial_infos = serial.step(actions)
            sharded_obs, sharded_rewards, sharded_dones, sharded_infos = sharded.step(actions)
            np.testing.assert_array_equal(serial_obs, sharded_obs)
            np.testing.assert_array_equal(serial_rewards, sharded_rewards)
            np.testing.assert_array_equal(serial_dones, sharded_dones)
            for serial_info, sharded_info in zip(serial_infos, sharded_infos, strict=True):
                assert serial_info.keys() == sharded_info.keys()
                for key, serial_value in serial_info.items():
                    sharded_value = sharded_info[key]
                    if isinstance(serial_value, np.ndarray):
                        np.testing.assert_array_equal(serial_value, sharded_value)
                    else:
                        assert serial_value == sharded_value
            assert serial.reset_infos == sharded.reset_infos
    finally:
        serial.close()
        sharded.close()
        serial_parent.close()
        sharded_parent.close()


def test_sharded_backend_requires_bundle_data_source() -> None:
    cfg = OmegaConf.create(
        {
            "env": {
                "n_envs": 2,
                "data_source": "frames",
                "vector_backend": "sharded_bundle",
                "vector_shards": 1,
            }
        }
    )
    parent_env = _make_cartpole()
    try:
        try:
            build_vector_env(parent_env, cfg, _make_cartpole)
        except ValueError as exc:
            assert "requires env.data_source='bundle'" in str(exc)
        else:
            raise AssertionError("sharded_bundle must reject frame-backed environments")
    finally:
        parent_env.close()


def test_sharded_backend_auto_shards_never_exceed_logical_envs() -> None:
    cfg = OmegaConf.create(
        {"env": {"n_envs": 3, "data_source": "bundle", "vector_backend": "sharded_bundle"}}
    )
    parent_env = _make_cartpole()
    vec_env = build_vector_env(parent_env, cfg, _make_cartpole)
    try:
        assert isinstance(vec_env, ShardedBundleVecEnv)
        assert vec_env.num_shards == 3
        assert vec_env.logical_envs_per_shard == [1, 1, 1]
    finally:
        vec_env.close()
        parent_env.close()


def test_sharded_environment_routes_selected_attributes_and_methods_in_requested_order() -> None:
    env_fns: list[Callable[[], gym.Env[Any, Any]]] = [
        _make_tiny_dict_env_factory(env_id) for env_id in range(5)
    ]
    env = ShardedBundleVecEnv(
        env_fns,
        n_shards=3,
        start_method="fork",
    )
    try:
        assert env.logical_envs_per_shard == [2, 2, 1]
        assert env.num_shards == 3
        assert env.has_attr("marker")
        assert not env.has_attr("missing_attribute")
        assert env.get_attr("env_id", indices=[4, 0, 3]) == [4, 0, 3]
        assert env.env_method("describe", "env-", indices=[4, 0, 3], multiplier=2) == [
            "env-8",
            "env-0",
            "env-6",
        ]

        env.set_attr("marker", "selected", indices=[3, 0])

        assert env.get_attr("marker", indices=[0, 1, 3, 4]) == [
            "selected",
            "initial",
            "selected",
            "initial",
        ]
        assert env.env_is_wrapped(gym.wrappers.TimeLimit) == [False] * 5
    finally:
        env.close()


def test_sharded_dict_observations_reset_info_render_and_terminal_semantics() -> None:
    env = ShardedBundleVecEnv(
        [
            lambda: _TinyDictEnv(0, terminates=True),
            lambda: _TinyDictEnv(1, truncates=True),
            lambda: _TinyDictEnv(2),
        ],
        n_shards=2,
        start_method="fork",
    )
    try:
        env.seed(12)
        observations = env.reset()
        assert isinstance(observations, dict)
        np.testing.assert_array_equal(
            observations["position"], np.asarray([[0, 0], [1, 0], [2, 0]], dtype=np.float32)
        )
        assert [info["seed"] for info in env.reset_infos] == [12, 13, 14]

        images = env.get_images()
        assert [int(image[0, 0, 0]) for image in images if image is not None] == [0, 1, 2]

        env.step_async(np.asarray([0, 1, 0]))
        next_observations, rewards, dones, infos = env.step_wait()

        np.testing.assert_array_equal(rewards, np.asarray([0.0, 2.0, 2.0]))
        np.testing.assert_array_equal(dones, np.asarray([True, True, False]))
        dict_observations = cast(dict[str, np.ndarray[Any, Any]], next_observations)
        np.testing.assert_array_equal(
            dict_observations["position"],
            np.asarray([[0, 0], [1, 0], [2, 1]], dtype=np.float32),
        )
        assert infos[0]["TimeLimit.truncated"] is False
        assert infos[1]["TimeLimit.truncated"] is True
        assert infos[0]["terminal_observation"]["position"].tolist() == [0.0, 1.0]
        assert infos[1]["terminal_observation"]["position"].tolist() == [1.0, 1.0]
        assert [info["env_id"] for info in env.reset_infos] == [0, 1, 2]
    finally:
        env.close()


def test_sharded_worker_errors_surface_and_close_is_idempotent(tmp_path: Path) -> None:
    close_path = tmp_path / "env-closed.txt"
    env = ShardedBundleVecEnv(
        [lambda: _TinyDictEnv(7, close_path=close_path)], n_shards=1, start_method="fork"
    )
    env.reset()
    env.step_async(np.asarray([99]))

    try:
        try:
            env.step_wait()
        except RuntimeError as exc:
            assert "step sentinel" in str(exc)
        else:
            raise AssertionError("worker step errors must be forwarded to the VecEnv caller")
        assert env.waiting is False
    finally:
        env.close()
        env.close()

    assert env.closed is True
    assert close_path.read_text(encoding="utf-8") == "7"


def test_sharded_environment_rejects_invalid_shard_counts_without_starting_workers() -> None:
    def factory() -> gym.Env[Any, Any]:
        return _TinyDictEnv(0)

    for env_fns, n_shards in (([], 1), ([factory], 0), ([factory], 2)):
        try:
            ShardedBundleVecEnv(env_fns, n_shards=n_shards, start_method="fork")
        except ValueError as exc:
            assert "at least one" in str(exc) or "between 1" in str(exc)
        else:
            raise AssertionError("invalid shard partition must be rejected before worker startup")
