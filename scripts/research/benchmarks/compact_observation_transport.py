"""Benchmark-only, lossless index transport for market observations.

Workers send a market row index and the environment-specific account vector.
The parent reconstructs the market-only fields from the same immutable bundle.
This is an experiment adapter; production training continues to use the stock
vector environment unless the explicit benchmark flag is selected.
"""

from __future__ import annotations

import hashlib
import multiprocessing as mp
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, cast

import gymnasium as gym
import numpy as np
from gymnasium import spaces
from stable_baselines3.common.vec_env import SubprocVecEnv
from stable_baselines3.common.vec_env.base_vec_env import (
    CloudpickleWrapper,
    VecEnvObs,
    VecEnvStepReturn,
)
from stable_baselines3.common.vec_env.patch_gym import _patch_env
from stable_baselines3.common.vec_env.subproc_vec_env import _stack_obs


class _MarketObservationSource(Protocol):
    observation_space: spaces.Dict
    step_idx: int

    def _get_observation(self) -> dict[str, Any]: ...


def _market_source(env: gym.Env[Any, Any]) -> _MarketObservationSource:
    source = cast(_MarketObservationSource, env.unwrapped)
    if not isinstance(source.observation_space, spaces.Dict):
        raise TypeError("compact transport requires a Dict observation space")
    return source


@dataclass(frozen=True, slots=True)
class CompactObservationRef:
    """Compact per-environment response for the benchmark worker protocol."""

    market_index: int
    account: np.ndarray[Any, Any]
    static_keys: tuple[str, ...]
    market_digest: bytes | None = None


def observation_market_digest(observation: dict[str, Any]) -> bytes:
    """Hash market-only fields in a stable key and dtype order."""
    digest = hashlib.blake2b(digest_size=16)
    for key in sorted(set(observation) - {"account"}):
        value = np.ascontiguousarray(observation[key])
        digest.update(key.encode("utf-8"))
        digest.update(value.dtype.str.encode("ascii"))
        digest.update(np.asarray(value.shape, dtype=np.int64).tobytes())
        digest.update(value.view(np.uint8))
    return digest.digest()


def _encode_observation(
    source: _MarketObservationSource,
    observation: dict[str, Any],
    *,
    validate_market: bool,
    market_index: int | None = None,
) -> CompactObservationRef:
    if "account" not in observation:
        raise ValueError("compact transport requires the environment account observation")
    expected = set(source.observation_space.spaces)
    if set(observation) != expected:
        raise ValueError("observation fields differ from the compact transport schema")
    market_digest = observation_market_digest(observation) if validate_market else None
    return CompactObservationRef(
        market_index=int(source.step_idx if market_index is None else market_index),
        account=np.array(observation["account"], copy=True),
        static_keys=tuple(sorted(expected - {"account"})),
        market_digest=market_digest,
    )


def _compact_worker(
    remote: Any,
    parent_remote: Any,
    env_fn_wrapper: CloudpickleWrapper,
    validate_market: bool,
) -> None:
    """SB3-compatible worker that sends market indices instead of repeated arrays."""
    from stable_baselines3.common.env_util import is_wrapped

    parent_remote.close()
    env = _patch_env(env_fn_wrapper.var())
    source = _market_source(env)
    reset_info: dict[str, Any] = {}
    try:
        while True:
            try:
                command, data = remote.recv()
            except EOFError:
                break

            try:
                if command == "step":
                    observation_market_index = int(source.step_idx)
                    observation, reward, terminated, truncated, info = env.step(data)
                    done = bool(terminated or truncated)
                    info = dict(info)
                    info["TimeLimit.truncated"] = bool(truncated and not terminated)
                    if done:
                        info["terminal_observation"] = _encode_observation(
                            source,
                            observation,
                            validate_market=validate_market,
                            market_index=observation_market_index,
                        )
                        observation, reset_info = env.reset()
                    remote.send(
                        (
                            _encode_observation(
                                source,
                                observation,
                                validate_market=validate_market,
                                market_index=observation_market_index,
                            ),
                            reward,
                            done,
                            info,
                            reset_info,
                        )
                    )
                elif command == "reset":
                    maybe_options = {"options": data[1]} if data[1] else {}
                    observation, reset_info = env.reset(seed=data[0], **maybe_options)
                    remote.send(
                        (
                            _encode_observation(
                                source, observation, validate_market=validate_market
                            ),
                            reset_info,
                        )
                    )
                elif command == "render":
                    remote.send(env.render())
                elif command == "close":
                    env.close()
                    remote.close()
                    break
                elif command == "get_spaces":
                    remote.send((env.observation_space, env.action_space))
                elif command == "env_method":
                    method = env.get_wrapper_attr(data[0])
                    remote.send(method(*data[1], **data[2]))
                elif command == "get_attr":
                    remote.send(env.get_wrapper_attr(data))
                elif command == "has_attr":
                    try:
                        env.get_wrapper_attr(data)
                        remote.send(True)
                    except AttributeError:
                        remote.send(False)
                elif command == "set_attr":
                    setattr(env, data[0], data[1])
                    remote.send(None)
                elif command == "is_wrapped":
                    remote.send(is_wrapped(env, data))
                else:
                    raise NotImplementedError(f"`{command}` is not implemented in the worker")
            except BaseException:
                remote.send({"worker_error": "compact observation worker failed"})
                raise
    except (EOFError, KeyboardInterrupt):
        pass
    finally:
        remote.close()


class CompactObservationSubprocVecEnv(SubprocVecEnv):
    """SubprocVecEnv reference semantics with lossless market-index responses."""

    def __init__(
        self,
        env_fns: list[Callable[[], gym.Env[Any, Any]]],
        start_method: str | None = None,
        *,
        market_source: gym.Env[Any, Any],
        validate_market: bool = False,
    ) -> None:
        if not env_fns:
            raise ValueError("CompactObservationSubprocVecEnv requires at least one environment")
        if start_method is None:
            forkserver_available = "forkserver" in mp.get_all_start_methods()
            start_method = "forkserver" if forkserver_available else "spawn"
        if start_method not in mp.get_all_start_methods():
            raise ValueError(f"unsupported multiprocessing start method: {start_method}")

        self.waiting = False
        self.closed = False
        self._market_source = _market_source(market_source)
        self._validate_market = validate_market
        context = mp.get_context(start_method)
        pipes = [context.Pipe() for _ in env_fns]
        self.remotes = tuple(parent for parent, _ in pipes)
        self.work_remotes = tuple(child for _, child in pipes)
        self.processes = []
        for child, parent, env_fn in zip(self.work_remotes, self.remotes, env_fns, strict=True):
            process = cast(Any, context).Process(
                target=_compact_worker,
                args=(child, parent, CloudpickleWrapper(env_fn), validate_market),
                daemon=True,
            )
            process.start()
            self.processes.append(process)
            child.close()

        self.remotes[0].send(("get_spaces", None))
        observation_space, action_space = self.remotes[0].recv()
        if (
            not isinstance(observation_space, spaces.Dict)
            or "account" not in observation_space.spaces
        ):
            self.close()
            raise TypeError("compact transport requires Dict observations with an account field")
        super(SubprocVecEnv, self).__init__(len(env_fns), observation_space, action_space)

    def _market_observation(
        self, reference: CompactObservationRef, cache: dict[int, dict[str, np.ndarray[Any, Any]]]
    ) -> dict[str, np.ndarray[Any, Any]]:
        market_index = int(reference.market_index)
        market = cache.get(market_index)
        if market is None:
            source = self._market_source
            previous_index = int(source.step_idx)
            try:
                source.step_idx = market_index
                full = source._get_observation()
            finally:
                source.step_idx = previous_index
            if set(full) != set(reference.static_keys) | {"account"}:
                raise RuntimeError("market reconstruction observation keys changed")
            market = {
                key: np.asarray(value).copy() for key, value in full.items() if key != "account"
            }
            if self._validate_market and observation_market_digest(full) != reference.market_digest:
                raise RuntimeError(
                    f"market observation reconstruction mismatch at index {market_index}"
                )
            cache[market_index] = market
        elif self._validate_market:
            full = dict(market)
            full["account"] = reference.account
            if observation_market_digest(full) != reference.market_digest:
                raise RuntimeError(f"market observation reuse mismatch at index {market_index}")
        return market

    def _stack_compact(self, references: Sequence[CompactObservationRef]) -> VecEnvObs:
        if not references:
            raise ValueError("cannot stack an empty compact observation list")
        market_cache: dict[int, dict[str, np.ndarray[Any, Any]]] = {}
        market_rows = [self._market_observation(ref, market_cache) for ref in references]
        observation_space = self._observation_dict_space()
        if self._validate_market and any(
            set(ref.static_keys) != set(observation_space.spaces) - {"account"}
            for ref in references
        ):
            raise RuntimeError("compact observation static fields differ from observation space")
        observations: list[dict[str, np.ndarray[Any, Any]]] = []
        for ref, market in zip(references, market_rows, strict=True):
            observations.append({**market, "account": ref.account})
        stackable = cast(
            list[
                np.ndarray[Any, Any]
                | dict[str, np.ndarray[Any, Any]]
                | tuple[np.ndarray[Any, Any], ...]
            ],
            observations,
        )
        return _stack_obs(stackable, observation_space)

    def _observation_dict_space(self) -> spaces.Dict:
        if not isinstance(self.observation_space, spaces.Dict):
            raise TypeError("compact transport requires a Dict observation space")
        return self.observation_space

    def reset(self) -> VecEnvObs:
        for env_idx, remote in enumerate(self.remotes):
            remote.send(("reset", (self._seeds[env_idx], self._options[env_idx])))
        results = [remote.recv() for remote in self.remotes]
        references, reset_infos = zip(*results, strict=True)
        self.reset_infos = list(reset_infos)
        self._reset_seeds()
        self._reset_options()
        return self._stack_compact(cast(Sequence[CompactObservationRef], references))

    def step_wait(self) -> VecEnvStepReturn:
        if not self.waiting:
            raise RuntimeError("step_wait called without a pending step")
        try:
            results = [remote.recv() for remote in self.remotes]
        finally:
            self.waiting = False
        references, rewards, dones, infos, reset_infos = zip(*results, strict=True)
        self.reset_infos = list(reset_infos)
        decoded_infos: list[dict[str, Any]] = []
        market_cache: dict[int, dict[str, np.ndarray[Any, Any]]] = {}
        for info in infos:
            decoded = dict(info)
            terminal = decoded.get("terminal_observation")
            if isinstance(terminal, CompactObservationRef):
                market = self._market_observation(terminal, market_cache)
                decoded["terminal_observation"] = {
                    **market,
                    "account": terminal.account,
                }
            decoded_infos.append(decoded)
        observations = self._stack_compact(cast(Sequence[CompactObservationRef], references))
        return observations, np.stack(rewards), np.stack(dones), decoded_infos

    def step_async(self, actions: np.ndarray[Any, Any]) -> None:
        if self.waiting:
            raise RuntimeError("step_async called while a previous step is pending")
        for remote, action in zip(self.remotes, actions, strict=True):
            remote.send(("step", action))
        self.waiting = True


__all__ = [
    "CompactObservationRef",
    "CompactObservationSubprocVecEnv",
    "observation_market_digest",
]
