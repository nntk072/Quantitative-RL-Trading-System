from __future__ import annotations

from typing import cast

import numpy as np
import numpy.typing as npt
from gymnasium import spaces
from scripts.research.benchmarks.compact_observation_transport import (
    CompactObservationSubprocVecEnv,
    _encode_observation,
    observation_market_digest,
)


class _IndexedMarketSource:
    def __init__(self) -> None:
        self.step_idx = 3
        self.observation_space = spaces.Dict(
            {
                "account": spaces.Box(-10.0, 10.0, shape=(2,), dtype=np.float32),
                "seq": spaces.Box(-10.0, 10.0, shape=(2, 3), dtype=np.float32),
                "seq_mask": spaces.Box(0.0, 1.0, shape=(2,), dtype=np.float32),
            }
        )

    @property
    def unwrapped(self) -> _IndexedMarketSource:
        return self

    def _get_observation(self) -> dict[str, npt.NDArray[np.float32]]:
        value = np.float32(self.step_idx)
        return {
            "account": np.asarray([value, -value], dtype=np.float32),
            "seq": np.full((2, 3), value, dtype=np.float32),
            "seq_mask": np.asarray([1.0, float(self.step_idx % 2)], dtype=np.float32),
        }


def _uninitialized_vec_env(source: _IndexedMarketSource) -> CompactObservationSubprocVecEnv:
    vec_env = object.__new__(CompactObservationSubprocVecEnv)
    vec_env._market_source = source
    vec_env._validate_market = True
    vec_env.observation_space = source.observation_space
    return vec_env


def test_market_digest_ignores_dynamic_account_values() -> None:
    source = _IndexedMarketSource()
    observation = source._get_observation()
    changed = {**observation, "account": np.asarray([9.0, -8.0], dtype=np.float32)}

    assert observation_market_digest(observation) == observation_market_digest(changed)


def test_compact_stack_reconstructs_duplicate_market_rows_losslessly() -> None:
    source = _IndexedMarketSource()
    source.step_idx = 3
    first_observation = source._get_observation()
    first = _encode_observation(source, first_observation, validate_market=True)
    source.step_idx = 3
    second_observation = source._get_observation()
    second_observation["account"] = np.asarray([7.0, -6.0], dtype=np.float32)
    second = _encode_observation(source, second_observation, validate_market=True)

    stacked = _uninitialized_vec_env(source)._stack_compact((first, second))

    stacked_dict = cast(dict[str, npt.NDArray[np.float32]], stacked)
    assert np.array_equal(stacked_dict["seq"], np.stack([first_observation["seq"]] * 2))
    assert np.array_equal(stacked_dict["seq_mask"], np.stack([first_observation["seq_mask"]] * 2))
    assert np.array_equal(
        stacked_dict["account"],
        np.asarray([[3.0, -3.0], [7.0, -6.0]], dtype=np.float32),
    )


def test_compact_stack_handles_diverged_market_indices() -> None:
    source = _IndexedMarketSource()
    source.step_idx = 3
    first = _encode_observation(source, source._get_observation(), validate_market=True)
    source.step_idx = 4
    second = _encode_observation(source, source._get_observation(), validate_market=True)

    stacked = _uninitialized_vec_env(source)._stack_compact((first, second))

    stacked_dict = cast(dict[str, npt.NDArray[np.float32]], stacked)
    assert np.array_equal(stacked_dict["seq"][:, 0, 0], np.asarray([3.0, 4.0], dtype=np.float32))
    assert np.array_equal(stacked_dict["seq_mask"][:, 1], np.asarray([1.0, 0.0], dtype=np.float32))
