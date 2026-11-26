"""Environment-level metamorphic oracle for causality, unused fields and determinism.

These tests drive the real ``TradingEnv`` on a synthetic tape (SEMANTIC-ORACLE).
Timing contract, established from the source and checked here: a decision made at
bar ``t`` fills at the open of bar ``t + 1``, and the output of ``step`` is valued at the
bar index the environment reports afterwards as ``step_idx``. So output ``j`` may depend
on bars up to its own valuation index and on nothing later.

Features are passed in separately and are held fixed in the perturbation tests. Feature
causality belongs to the feature graph work package, not to this environment oracle.
"""

from __future__ import annotations

import functools
from typing import Any

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from simulation.environment.env import TradingEnv
from tests.unit.simulation.test_environment.test_trading_env_golden_traces import (
    _make_deterministic_bars,
    _make_features,
)

ACTIONS = [1, 2, 0, 1, 1, 2, 0, 0] * 10
OHLC = ["open", "high", "low", "close"]
ENV_SETTINGS = settings(max_examples=12, deadline=None, database=None, derandomize=True)


def _flatten(obs: Any) -> Any:
    if isinstance(obs, dict):
        return {key: _flatten(obs[key]) for key in sorted(obs)}
    if isinstance(obs, (list, tuple)):
        return [_flatten(value) for value in obs]
    try:
        return np.asarray(obs, dtype=float).round(12).tolist()
    except (TypeError, ValueError):
        return str(obs)


def _make_env(bars: pd.DataFrame, features: pd.DataFrame) -> TradingEnv:
    return TradingEnv(
        bars=bars,
        features=features,
        obs_window=10,
        initial_balance=100_000.0,
        episodic=True,
        use_sweep_reward=False,
    )


def _run(
    bars: pd.DataFrame,
    features: pd.DataFrame,
    actions: list[int] | None = None,
    *,
    seed: int = 42,
    max_steps: int = 200,
) -> list[dict[str, Any]]:
    """Run the env and record, per step, the valuation index, output and flags."""
    env = _make_env(bars, features)
    env.reset(seed=seed)
    trace: list[dict[str, Any]] = []
    for action in (actions or ACTIONS)[:max_steps]:
        obs, reward, done, truncated, _ = env.step(int(action))
        trace.append(
            {
                "valuation_index": int(env.step_idx),
                "obs": _flatten(obs),
                "reward": float(reward),
                "terminated": bool(done),
                "truncated": bool(truncated),
                "equity": float(env.account.equity),
            }
        )
        if done or truncated:
            break
    return trace


def _steps_equal(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return left == right


@functools.cache
def _tape() -> tuple[pd.DataFrame, pd.DataFrame]:
    bars = _make_deterministic_bars(120)
    return bars, _make_features(bars)


@functools.cache
def _baseline() -> tuple[dict[str, Any], ...]:
    bars, features = _tape()
    return tuple(_run(bars, features))


@pytest.fixture
def tape() -> tuple[pd.DataFrame, pd.DataFrame]:
    return _tape()


@pytest.fixture
def baseline() -> list[dict[str, Any]]:
    return list(_baseline())


def test_valuation_index_advances_one_bar_per_step(baseline: list[dict[str, Any]]) -> None:
    """The ordering key of each output is the bar it is valued at: consecutive and unique."""
    indices = [row["valuation_index"] for row in baseline]
    assert indices == list(range(indices[0], indices[0] + len(indices)))
    assert len(set(indices)) == len(indices)


def test_reset_with_same_seed_gives_identical_first_output(
    tape: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    bars, features = tape
    first = _make_env(bars, features)
    second = _make_env(bars, features)
    obs_a, _ = first.reset(seed=7)
    obs_b, _ = second.reset(seed=7)
    assert _flatten(obs_a) == _flatten(obs_b)


def test_interleaved_instances_match_sequential_runs(
    tape: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    """Batch-vs-single: two env instances stepped alternately do not share state."""
    bars, features = tape
    solo = _run(bars, features, max_steps=25)
    env_a = _make_env(bars, features)
    env_b = _make_env(bars, features)
    env_a.reset(seed=42)
    env_b.reset(seed=42)
    interleaved_a: list[dict[str, Any]] = []
    interleaved_b: list[dict[str, Any]] = []
    for action in ACTIONS[:25]:
        for env, sink in ((env_a, interleaved_a), (env_b, interleaved_b)):
            obs, reward, done, truncated, _ = env.step(int(action))
            sink.append(
                {
                    "valuation_index": int(env.step_idx),
                    "obs": _flatten(obs),
                    "reward": float(reward),
                    "terminated": bool(done),
                    "truncated": bool(truncated),
                    "equity": float(env.account.equity),
                }
            )
    assert interleaved_a == solo
    assert interleaved_b == solo


@ENV_SETTINGS
@given(
    cut=st.integers(min_value=62, max_value=100),
    delta=st.sampled_from([-50.0, -5.0, 5.0, 50.0]),
    columns=st.sampled_from([OHLC, ["close"], ["high", "low"], ["open"]]),
)
def test_output_depends_only_on_bars_up_to_its_valuation_index(
    cut: int, delta: float, columns: list[str]
) -> None:
    """Perturb out-of-sample bars: outputs valued strictly before the cut are unchanged.

    The first output is valued at bar 61, so any cut of 62 or more has at least one
    output that must stay fixed.
    """
    bars, features = _tape()
    baseline = list(_baseline())
    perturbed = bars.copy()
    for column in columns:
        values = perturbed[column].to_numpy(dtype=float, copy=True)
        values[cut:] += delta
        perturbed[column] = values
    changed = _run(perturbed, features)
    checked = 0
    for old, new in zip(baseline, changed, strict=False):
        if old["valuation_index"] >= cut:
            break
        assert _steps_equal(old, new), f"output valued at bar {old['valuation_index']} changed"
        checked += 1
    assert checked > 0


@ENV_SETTINGS
@given(
    volume_scale=st.floats(min_value=0.1, max_value=10.0, allow_nan=False),
    tick_shift=st.integers(min_value=-500, max_value=500),
    vol_value=st.integers(min_value=-100, max_value=100),
)
def test_unused_volume_columns_do_not_change_the_trace(
    volume_scale: float, tick_shift: int, vol_value: int
) -> None:
    """Change unused fields: volume, tick volume and vol do not reach the env outputs."""
    bars, features = _tape()
    baseline = list(_baseline())
    changed_bars = bars.copy()
    changed_bars["volume"] = changed_bars["volume"] * volume_scale
    changed_bars["tickvol"] = changed_bars["tickvol"] + tick_shift
    changed_bars["vol"] = vol_value
    assert _run(changed_bars, features) == baseline


@ENV_SETTINGS
@given(length=st.integers(min_value=70, max_value=110))
def test_appending_future_bars_leaves_earlier_outputs_unchanged(length: int) -> None:
    """Append-future: a shorter tape reproduces every output that is not its data-end output."""
    bars, features = _tape()
    baseline = list(_baseline())
    short = _run(bars.iloc[:length], features.iloc[:length])
    assert short[-1]["truncated"] is True
    for old, new in zip(short[:-1], baseline, strict=False):
        assert _steps_equal(old, new)


def test_data_end_truncates_without_terminating(tape: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    """Terminal/truncation: running out of bars truncates and does not terminate."""
    bars, features = tape
    trace = _run(bars.iloc[:80], features.iloc[:80], max_steps=200)
    final = trace[-1]
    assert final["truncated"] is True
    assert final["terminated"] is False
    assert final["valuation_index"] == 80


def test_data_end_observation_differs_from_in_episode_observation(
    tape: tuple[pd.DataFrame, pd.DataFrame], baseline: list[dict[str, Any]]
) -> None:
    """Characterization (fixture AC-level note): the observation returned at data end is not the
    in-episode observation for the same valuation index. A learner must not treat it as a
    normal next state. Owner decision: LEARNER-CONTRACT bootstrap masking for truncation.
    """
    bars, features = tape
    short = _run(bars.iloc[:80], features.iloc[:80], max_steps=200)
    matching = next(
        row for row in baseline if row["valuation_index"] == short[-1]["valuation_index"]
    )
    assert short[-1]["obs"] != matching["obs"]


def test_no_trade_action_keeps_flat_account_and_zero_reward(
    tape: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    """No-trade (action 0): no order, no position, equity and reward unchanged for the run."""
    bars, features = tape
    env = _make_env(bars, features)
    env.reset(seed=42)
    equities: list[float] = []
    rewards: list[float] = []
    for _ in range(30):
        _, reward, done, truncated, info = env.step(0)
        assert not info["entry_opened"]
        assert env.position is None
        equities.append(float(env.account.equity))
        rewards.append(float(reward))
        assert not (done or truncated)
    assert env.trade_log == []
    assert set(equities) == {100_000.0}
    assert rewards == [0.0] * 30
