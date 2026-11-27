"""Deterministic VecEnv contracts using recording remotes instead of child processes."""

from __future__ import annotations

from collections import deque
from types import SimpleNamespace
from typing import Any, cast

import gymnasium as gym
import numpy as np
import pytest
from gymnasium import spaces
from stable_baselines3.common.vec_env.base_vec_env import CloudpickleWrapper

from learning.rl import environment_adapter as adapter


class RecordingRemote:
    def __init__(self, responses: list[Any] | None = None) -> None:
        self.sent: list[Any] = []
        self.responses = deque(responses or [])
        self.closed = False

    def send(self, value: Any) -> None:
        self.sent.append(value)

    def recv(self) -> Any:
        if not self.responses:
            raise RuntimeError("no response was queued for this remote")
        return self.responses.popleft()

    def close(self) -> None:
        self.closed = True


class RecordingProcess:
    def __init__(self) -> None:
        self.join_calls: list[float | None] = []
        self.terminated = False

    def join(self, timeout: float | None = None) -> None:
        self.join_calls.append(timeout)

    def is_alive(self) -> bool:
        return False

    def terminate(self) -> None:
        self.terminated = True


def _vec_env(
    remotes: list[RecordingRemote], *, render_mode: str | None = None
) -> adapter.ShardedBundleVecEnv:
    vec = object.__new__(adapter.ShardedBundleVecEnv)
    vec.waiting = False
    vec.closed = False
    vec._shard_ranges = [(0, 2), (2, 3)]
    vec.remotes = remotes
    vec.processes = [RecordingProcess(), RecordingProcess()]
    vec.num_envs = 3
    vec.observation_space = spaces.Dict({"state": spaces.Box(-10.0, 10.0, (1,))})
    vec.action_space = spaces.Discrete(3)
    vec.reset_infos = [{}, {}, {}]
    vec._seeds = [None, None, None]
    vec._options = [{}, {}, {}]
    vec.render_mode = render_mode
    return vec


def test_sharded_vecenv_reset_and_step_preserve_logical_environment_order() -> None:
    remotes = [
        RecordingRemote(
            [
                [({"state": np.asarray([1.0])}, {"seed": 10}), ({"state": np.asarray([2.0])}, {})],
                [
                    ({"state": np.asarray([3.0])}, 1.0, False, {"slot": 0}, {}),
                    ({"state": np.asarray([4.0])}, 2.0, True, {"slot": 1}, {"reset": 1}),
                ],
            ]
        ),
        RecordingRemote(
            [
                [({"state": np.asarray([5.0])}, {"seed": 12})],
                [({"state": np.asarray([6.0])}, 3.0, False, {"slot": 2}, {})],
            ]
        ),
    ]
    vec = _vec_env(remotes)
    vec.seed(10)
    vec.set_options({"mode": "deterministic"})

    reset_observations = cast(dict[str, np.ndarray[Any, Any]], vec.reset())

    np.testing.assert_array_equal(reset_observations["state"].ravel(), [1.0, 2.0, 5.0])
    assert vec.reset_infos == [{"seed": 10}, {}, {"seed": 12}]
    assert remotes[0].sent[0] == (
        "reset",
        [(10, {"mode": "deterministic"}), (11, {"mode": "deterministic"})],
    )
    assert remotes[1].sent[0] == ("reset", [(12, {"mode": "deterministic"})])

    actions = np.asarray([0, 1, 2])
    vec.step_async(actions)
    assert vec.waiting
    assert remotes[0].sent[1][0] == "step"
    assert remotes[1].sent[1][0] == "step"
    np.testing.assert_array_equal(remotes[0].sent[1][1], actions[:2])
    np.testing.assert_array_equal(remotes[1].sent[1][1], actions[2:])
    with pytest.raises(RuntimeError, match="previous step is pending"):
        vec.step_async(actions)

    observations, rewards, dones, infos = vec.step_wait()
    observations = cast(dict[str, np.ndarray[Any, Any]], observations)

    np.testing.assert_array_equal(observations["state"].ravel(), [3.0, 4.0, 6.0])
    np.testing.assert_array_equal(rewards, [1.0, 2.0, 3.0])
    np.testing.assert_array_equal(dones, [False, True, False])
    assert infos == [{"slot": 0}, {"slot": 1}, {"slot": 2}]
    assert vec.reset_infos == [{}, {"reset": 1}, {}]
    assert not vec.waiting
    with pytest.raises(RuntimeError, match="without a pending step"):
        vec.step_wait()


def test_sharded_vecenv_validates_shards_and_requested_indices() -> None:
    with pytest.raises(ValueError, match="at least one environment"):
        cast(Any, adapter.ShardedBundleVecEnv)([], n_shards=1)
    with pytest.raises(ValueError, match="n_shards"):
        cast(Any, adapter.ShardedBundleVecEnv)([lambda: None], n_shards=2)
    with pytest.raises(ValueError, match="unsupported multiprocessing start method"):
        cast(Any, adapter.ShardedBundleVecEnv)([lambda: None], n_shards=1, start_method="invalid")

    remotes = [RecordingRemote(), RecordingRemote()]
    vec = _vec_env(remotes)
    assert vec.num_shards == 2
    assert vec.logical_envs_per_shard == [2, 1]
    assert vec._group_indices([2, 0]) == [[(0, 0)], [(2, 0)]]
    assert vec._requested_indices([2, 0]) == [2, 0]
    with pytest.raises(IndexError, match="outside"):
        vec.get_attr("state", indices=[3])
    with pytest.raises(ValueError, match="expected 3 actions"):
        vec.step_async(np.asarray([0, 1]))


def test_sharded_vecenv_attributes_methods_wrappers_render_and_close() -> None:
    remotes = [
        RecordingRemote([[True, True], ["zero"], None, [0], [False]]),
        RecordingRemote([[True], ["two"], None, [2], [True]]),
    ]
    vec = _vec_env(remotes, render_mode="rgb_array")

    assert vec.has_attr("value")
    assert vec.get_attr("name", indices=[2, 0]) == ["two", "zero"]
    vec.set_attr("value", 4, indices=[0, 2])
    assert remotes[0].sent[2] == ("set_attr", ((0,), "value", 4))
    assert remotes[1].sent[2] == ("set_attr", ((0,), "value", 4))
    assert vec.env_method("increment", 2, indices=[2, 0], amount=3) == [2, 0]
    assert vec.env_is_wrapped(gym.Wrapper, indices=[2, 0]) == [True, False]
    assert all(command[0] == "has_attr" for command in [remotes[0].sent[0], remotes[1].sent[0]])

    remotes[0].responses.append([np.asarray([0]), np.asarray([1])])
    remotes[1].responses.append([np.asarray([2])])
    remotes[0].responses.append(None)
    remotes[1].responses.append(None)
    images = vec.get_images()
    assert [int(image[0]) for image in images if image is not None] == [0, 1, 2]

    vec.close()
    vec.close()
    assert vec.closed
    assert all(remote.closed for remote in remotes)
    assert all(process.join_calls == [5] for process in vec.processes)


def test_sharded_vecenv_warns_when_images_are_requested_without_rgb_mode() -> None:
    vec = _vec_env([RecordingRemote(), RecordingRemote()], render_mode=None)

    with pytest.warns(UserWarning, match="expected 'rgb_array'"):
        assert vec.get_images() == [None, None, None]


def test_observation_stacking_supports_dict_tuple_and_box_spaces() -> None:
    dict_space = spaces.Dict({"x": spaces.Box(-1.0, 1.0, (1,))})
    stacked_dict = cast(Any, adapter._stack_observations)(
        [{"x": np.asarray([1.0])}, {"x": np.asarray([2.0])}], dict_space
    )
    np.testing.assert_array_equal(stacked_dict["x"].ravel(), [1.0, 2.0])
    with pytest.raises(TypeError, match="Dict observation space"):
        cast(Any, adapter._stack_observations)([], dict_space)

    tuple_space = spaces.Tuple((spaces.Box(-1.0, 1.0, (1,)), spaces.Discrete(2)))
    stacked_tuple = cast(Any, adapter._stack_observations)(
        [(np.asarray([1.0]), np.asarray(0)), (np.asarray([2.0]), np.asarray(1))], tuple_space
    )
    np.testing.assert_array_equal(stacked_tuple[0].ravel(), [1.0, 2.0])
    np.testing.assert_array_equal(stacked_tuple[1], [0, 1])
    with pytest.raises(TypeError, match="Tuple observation space"):
        cast(Any, adapter._stack_observations)([], tuple_space)

    box_space = spaces.Box(-1.0, 1.0, (1,))
    stacked_box = cast(Any, adapter._stack_observations)(
        [np.asarray([3.0]), np.asarray([4.0])], box_space
    )
    np.testing.assert_array_equal(stacked_box.ravel(), [3.0, 4.0])


def test_remote_worker_errors_are_raised_with_the_worker_traceback() -> None:
    remote = RecordingRemote([{"worker_error": "ValueError: invalid action"}])
    with pytest.raises(RuntimeError, match="invalid action"):
        adapter.ShardedBundleVecEnv._receive(remote)

    remotes = [
        RecordingRemote([[(np.asarray([0.0]), 1.0, False, {}, {})]]),
        RecordingRemote([{"worker_error": "worker stopped"}]),
    ]
    vec = _vec_env(remotes)
    vec.waiting = True
    with pytest.raises(RuntimeError, match="worker stopped"):
        vec.step_wait()
    assert not vec.waiting


class TinyEnv(gym.Env[Any, int]):
    observation_space = spaces.Box(-10.0, 10.0, (1,), dtype=np.float32)
    action_space: spaces.Space[Any] = spaces.Discrete(2)

    def __init__(self, *, terminated: bool = False, truncated: bool = False) -> None:
        self.terminated = terminated
        self.truncated = truncated
        self.value = 0
        self.reset_calls: list[tuple[int | None, dict[str, Any]]] = []
        self.received_actions: list[int] = []
        self.name = "tiny"

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None):
        super().reset(seed=seed)
        self.reset_calls.append((seed, options or {}))
        return np.asarray([self.value], dtype=np.float32), {"seed": seed, "options": options or {}}

    def step(self, action: int):
        self.received_actions.append(action)
        observation = np.asarray([self.value + 10], dtype=np.float32)
        return observation, 1.0, self.terminated, self.truncated, {"action": action}

    def render(self) -> np.ndarray[Any, Any]:
        return np.asarray([self.value], dtype=np.uint8)

    def get_wrapper_attr(self, name: str) -> Any:
        return getattr(self, name)

    def increment(self, amount: int = 1) -> int:
        self.value += amount
        return self.value


class WorkerRemote:
    def __init__(self, commands: list[tuple[str, Any]]) -> None:
        self.commands = deque(commands)
        self.sent: list[Any] = []
        self.closed = False

    def recv(self) -> tuple[str, Any]:
        if not self.commands:
            raise EOFError
        return self.commands.popleft()

    def send(self, value: Any) -> None:
        self.sent.append(value)

    def close(self) -> None:
        self.closed = True


def test_shard_worker_handles_reset_step_access_and_control_commands(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import stable_baselines3.common.env_util as env_util

    terminated_env = TinyEnv(terminated=True)
    truncated_env = TinyEnv(truncated=True)
    commands: list[tuple[str, Any]] = [
        ("get_spaces", None),
        ("reset", [(7, {"tag": "first"}), (8, {})]),
        ("step", [1, 0]),
        ("render", None),
        ("get_attr", ((0, 1), "name")),
        ("has_attr", ((0, 1), "name")),
        ("has_attr", ((0, 1), "missing")),
        ("set_attr", ((0, 1), "value", 5)),
        ("env_method", ((0, 1), "increment", (2,), {})),
        ("is_wrapped", ((0, 1), gym.Wrapper)),
        ("unsupported", None),
        ("close", None),
    ]
    remote = WorkerRemote(commands)
    parent_remote = SimpleNamespace(close=lambda: None)
    monkeypatch.setattr(adapter, "_patch_env", lambda env: env)
    monkeypatch.setattr(env_util, "is_wrapped", lambda _env, _cls: False)

    adapter._shard_worker(
        remote,
        parent_remote,
        CloudpickleWrapper([lambda: terminated_env, lambda: truncated_env]),
    )

    responses = remote.sent
    assert responses[0] == (terminated_env.observation_space, terminated_env.action_space)
    assert responses[1][0][1] == {"seed": 7, "options": {"tag": "first"}}
    assert responses[1][1][1] == {"seed": 8, "options": {}}
    assert responses[2][0][2] is True
    assert responses[2][0][3]["TimeLimit.truncated"] is False
    assert responses[2][0][3]["terminal_observation"].tolist() == [10.0]
    assert responses[2][1][3]["TimeLimit.truncated"] is True
    assert responses[2][1][3]["terminal_observation"].tolist() == [10.0]
    assert len(responses[3]) == 2
    for image in responses[3]:
        np.testing.assert_array_equal(image, [0])
    assert responses[4] == ["tiny", "tiny"]
    assert responses[5] == [True, True]
    assert responses[6] == [False, False]
    assert responses[7] is None
    assert responses[8] == [7, 7]
    assert responses[9] == [False, False]
    assert "unsupported VecEnv worker command" in responses[10]["worker_error"]
    assert remote.closed
