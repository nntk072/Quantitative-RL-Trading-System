"""Full env trace freeze for one fixed episode (SEMANTIC-ORACLE, env_trace.v1).

The frozen file is a characterization of the implementation (not a hand calculation). It
records, for every step, the ordering key (valuation bar, action ordinal), reward, flags,
equity and position state, and for every trade record its ordering key, type, reason and bar.
Integers, strings, booleans and keys compare exactly. Reward and equity compare with the
tolerances of the oracle policy (reward 1e-12, money 1e-6). A change requires a new trace
version and an explicit note in semantic_contracts.md.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from simulation.environment.env import TradingEnv
from tests.unit.simulation.test_environment.test_trading_env_golden_traces import (
    _make_deterministic_bars,
    _make_features,
)

TRACE_PATH = (
    Path(__file__).resolve().parents[4]
    / "planning/native_modernization/semantic_oracle/fixtures/env_trace.v1.json"
)
ACTIONS = [1, 2, 0, 1, 1, 2, 0, 0] * 10
REWARD_ABS = 1e-12
MONEY_ABS = 1e-6


def _episode() -> dict[str, Any]:
    bars = _make_deterministic_bars(120)
    features = _make_features(bars)
    env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=10,
        initial_balance=100_000.0,
        episodic=True,
        use_sweep_reward=False,
    )
    env.reset(seed=42)
    steps: list[dict[str, Any]] = []
    trades: list[dict[str, Any]] = []
    for ordinal, action in enumerate(ACTIONS):
        before = len(env.trade_log)
        _, reward, done, truncated, _ = env.step(int(action))
        index = int(env.step_idx)
        for seq, record in enumerate(env.trade_log[before:]):
            bar = record.get("bar")
            trades.append(
                {
                    "key": [index, ordinal, seq],
                    "type": str(record.get("type")),
                    "reason": str(record.get("reason", "")),
                    "bar": int(bar) if isinstance(bar, int) else None,
                }
            )
        steps.append(
            {
                "key": [index, ordinal],
                "action": int(action),
                "reward": round(float(reward), 12),
                "terminated": bool(done),
                "truncated": bool(truncated),
                "equity": round(float(env.account.equity), 6),
                "position_open": env.position is not None,
            }
        )
        if done or truncated:
            break
    return {"steps": steps, "trades": trades}


@pytest.fixture(scope="module")
def frozen() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(TRACE_PATH.read_text(encoding="utf-8"))
    return data


def test_frozen_trace_digest_matches_its_content(frozen: dict[str, Any]) -> None:
    blob = json.dumps(frozen["trace"], sort_keys=True, separators=(",", ":")).encode()
    assert hashlib.sha256(blob).hexdigest() == frozen["sha256"]
    assert frozen["n_steps"] == len(frozen["trace"]["steps"])
    assert frozen["n_trades"] == len(frozen["trace"]["trades"])


def test_ordering_keys_are_strictly_increasing_and_unique(frozen: dict[str, Any]) -> None:
    step_keys = [tuple(row["key"]) for row in frozen["trace"]["steps"]]
    trade_keys = [tuple(row["key"]) for row in frozen["trace"]["trades"]]
    assert step_keys == sorted(step_keys) and len(set(step_keys)) == len(step_keys)
    assert trade_keys == sorted(trade_keys) and len(set(trade_keys)) == len(trade_keys)


def test_live_episode_replays_the_frozen_trace(frozen: dict[str, Any]) -> None:
    live = _episode()
    expected = frozen["trace"]
    assert len(live["steps"]) == len(expected["steps"])
    assert len(live["trades"]) == len(expected["trades"])
    for got, want in zip(live["steps"], expected["steps"], strict=True):
        assert got["key"] == want["key"]
        assert got["action"] == want["action"]
        assert got["terminated"] is want["terminated"]
        assert got["truncated"] is want["truncated"]
        assert got["position_open"] is want["position_open"]
        assert got["reward"] == pytest.approx(want["reward"], abs=REWARD_ABS)
        assert got["equity"] == pytest.approx(want["equity"], abs=MONEY_ABS)
    for got, want in zip(live["trades"], expected["trades"], strict=True):
        assert got == want


def test_frozen_episode_ends_by_truncation_at_the_last_bar(frozen: dict[str, Any]) -> None:
    last = frozen["trace"]["steps"][-1]
    assert last["truncated"] is True
    assert last["terminated"] is False
    assert last["key"][0] == 120
