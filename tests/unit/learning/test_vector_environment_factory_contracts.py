"""Vector backend choice preserves serial safety and validates bundle sharding."""

from __future__ import annotations

import multiprocessing
import os
import sys
from typing import Any

import pytest
from omegaconf import OmegaConf

from learning.rl import agent


def test_vector_factory_rejects_unknown_backend_before_constructing_environment() -> None:
    cfg = OmegaConf.create({"env": {"n_envs": 2, "vector_backend": "threadpool"}})

    with pytest.raises(ValueError, match="env.vector_backend must be"):
        agent.build_vector_env(object(), cfg, lambda: object())


def test_serial_vector_factory_caps_native_threads_for_each_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = OmegaConf.create({"env": {"n_envs": 3, "vector_backend": "serial"}})
    calls: list[str] = []
    torch_calls: list[int] = []
    for name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
        monkeypatch.setenv(name, "4")

    class _Vec:
        def __init__(self, factories: list[Any]) -> None:
            self.environments = [factory() for factory in factories]

    monkeypatch.setattr(agent, "_SB3_AVAILABLE", True)
    monkeypatch.setattr(agent, "DummyVecEnv", _Vec)
    monkeypatch.setattr(sys.modules["torch"], "set_num_threads", torch_calls.append)

    def make_environment() -> object:
        calls.append("created")
        return object()

    result = agent.build_vector_env(object(), cfg, make_environment)

    assert len(result.environments) == 3
    assert calls == ["created"] * 3
    assert torch_calls == [1] * 3
    assert all(os.environ[name] == "1" for name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS"))


def test_vector_factory_uses_serial_dummy_wrapper_for_single_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = object()
    cfg = OmegaConf.create({"env": {"n_envs": 1, "vector_backend": "subproc"}})
    observed: list[Any] = []

    class _Vec:
        def __init__(self, factories: list[Any]) -> None:
            observed.extend(factory() for factory in factories)

    monkeypatch.setattr(agent, "_SB3_AVAILABLE", True)
    monkeypatch.setattr(agent, "DummyVecEnv", _Vec)
    monkeypatch.setattr(agent, "SubprocVecEnv", lambda *_args, **_kwargs: pytest.fail("spawned"))

    agent.build_vector_env(env, cfg, lambda: pytest.fail("single env must use env directly"))

    assert observed == [env]


@pytest.mark.parametrize("shards", [0, 4])
def test_sharded_bundle_factory_uses_bounded_default_or_configured_shards(
    monkeypatch: pytest.MonkeyPatch, shards: int
) -> None:
    cfg = OmegaConf.create(
        {
            "env": {
                "n_envs": 4,
                "vector_backend": "sharded_bundle",
                "data_source": "bundle",
                "vector_shards": shards,
            }
        }
    )
    recorded: dict[str, Any] = {}

    class _Sharded:
        def __init__(
            self, factories: list[Any], *, n_shards: int, start_method: str | None
        ) -> None:
            recorded.update(factories=factories, n_shards=n_shards, start_method=start_method)

    monkeypatch.setattr(agent, "_SB3_AVAILABLE", True)
    monkeypatch.setattr(multiprocessing, "get_all_start_methods", lambda: ["spawn"])
    monkeypatch.setattr("learning.rl.environment_adapter.ShardedBundleVecEnv", _Sharded)

    agent.build_vector_env(object(), cfg, lambda: object())

    assert len(recorded["factories"]) == 4
    assert recorded["n_shards"] == (4 if shards == 0 else shards)
    assert recorded["start_method"] is None


def test_sharded_backend_rejects_non_bundle_data_before_loading_adapter() -> None:
    cfg = OmegaConf.create({"env": {"n_envs": 2, "vector_backend": "sharded_bundle"}})

    with pytest.raises(ValueError, match="requires env.data_source='bundle'"):
        agent.build_vector_env(object(), cfg, lambda: object())


@pytest.mark.parametrize("shards", [-1, 5])
def test_sharded_backend_rejects_out_of_range_explicit_shard_counts(
    monkeypatch: pytest.MonkeyPatch, shards: int
) -> None:
    cfg = OmegaConf.create(
        {
            "env": {
                "n_envs": 4,
                "vector_backend": "sharded_bundle",
                "data_source": "bundle",
                "vector_shards": shards,
            }
        }
    )
    monkeypatch.setattr(agent, "_SB3_AVAILABLE", True)

    with pytest.raises(ValueError, match="env.vector_shards must be between 1 and env.n_envs"):
        agent.build_vector_env(object(), cfg, lambda: object())


def test_vector_factory_uses_raw_environment_when_factory_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = object()
    cfg = OmegaConf.create({"env": {"n_envs": 4, "vector_backend": "serial"}})
    observed: list[Any] = []

    class _Vec:
        def __init__(self, factories: list[Any]) -> None:
            observed.extend(factory() for factory in factories)

    monkeypatch.setattr(agent, "_SB3_AVAILABLE", True)
    monkeypatch.setattr(agent, "DummyVecEnv", _Vec)

    agent.build_vector_env(env, cfg, None)

    assert observed == [env]


def test_vector_factory_reports_missing_stable_baselines_dependency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(agent, "_SB3_AVAILABLE", False)

    with pytest.raises(ImportError, match="stable-baselines3 is required"):
        agent.build_vector_env(object(), OmegaConf.create({"env": {}}), None)
