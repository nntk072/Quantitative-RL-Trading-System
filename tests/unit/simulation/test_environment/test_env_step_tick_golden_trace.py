"""Golden trace for TradingEnv.step() with a TickBook and tick execution required.

The existing golden trace has no TickBook and hashes only part of ``info``.
This one hashes every observation, reward, flag, the full ``info`` dict and the
trade log, so a speed-up of the step must leave all of them unchanged.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import numpy as np
import pandas as pd

from market_data.loading.ticks import TickBook
from simulation.environment.env import TradingEnv
from tests.unit.simulation.test_environment.test_trading_env_golden_traces import (
    _make_deterministic_bars,
    _make_features,
)

_ACTIONS = [0, 0, 0, 1, 0, 0, 10, 0, 0, 0, 2, 0, 0, 0, 10, 0, 0, 1, 0, 0] * 5


def _canonical(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _canonical(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, (list, tuple)):
        return [_canonical(v) for v in value]
    if isinstance(value, np.ndarray):
        return [_canonical(v) for v in value.tolist()]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.generic):
        return _canonical(value.item())
    if isinstance(value, float):
        return "nan" if value != value else repr(value)
    if isinstance(value, (bool, int, str)) or value is None:
        return value
    return str(value)


def _tickbook(bars: pd.DataFrame) -> TickBook:
    """Four deterministic ticks per bar: open, first extreme, second extreme, close."""
    ts: list[int] = []
    bid: list[float] = []
    for t, o, h, lo, c in zip(
        bars.index, bars["open"], bars["high"], bars["low"], bars["close"], strict=True
    ):
        first, second = (lo, h) if c >= o else (h, lo)
        for offset_s, price in ((1, o), (15, first), (30, second), (59, c)):
            ts.append(t.value + offset_s * 1_000_000_000)
            bid.append(float(price))
    bid_a = np.asarray(bid, dtype=np.float64)
    return TickBook(np.asarray(ts, dtype=np.int64), bid_a, bid_a + 0.6)


def run_tick_trace() -> tuple[str, dict[str, int]]:
    bars = _make_deterministic_bars(n=130)
    features = _make_features(bars)
    env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=10,
        initial_balance=100_000.0,
        episodic=True,
        use_sweep_reward=False,
        tickbook=_tickbook(bars),
        tick_execution_required=True,
    )
    obs, _ = env.reset(seed=42)
    steps: list[dict[str, Any]] = [{"obs0": _canonical(obs)}]
    for action in _ACTIONS:
        obs, reward, done, truncated, info = env.step(action)
        steps.append(
            {
                "obs": _canonical(obs),
                "reward": _canonical(float(reward)),
                "done": bool(done),
                "truncated": bool(truncated),
                "info": _canonical(dict(info)),
                "equity": _canonical(float(env.account.equity)),
            }
        )
        if done or truncated:
            break
    payload = {"steps": steps, "trade_log": _canonical(list(env.trade_log))}
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    stats = {"steps": len(steps) - 1, "trades": len(env.trade_log)}
    return hashlib.sha256(raw.encode("utf-8")).hexdigest(), stats


# Captured from the committed step code before any speed-up (2026-11-22).
# Floating-point results differ between x86_64 and aarch64 numerical libraries, so each
# host class keeps its own recorded value. The aarch64 value was produced by the current
# code on the GH200 node and has not been checked against an original aarch64 run.
_GOLDEN_HASHES = {
    "x86_64": "5fb5644e332782e98ec4e459e030eae4fed6075d97764014f25978fe659d89aa",
    "aarch64": "a7ffc31f08ba0f40a24ea4461c1bda59c923f8cd70bab09a4093844379e27e36",
}


def test_tick_env_step_trace_is_unchanged() -> None:
    digest, stats = run_tick_trace()
    assert stats["steps"] > 50
    import platform

    expected = _GOLDEN_HASHES.get(platform.machine())
    assert expected is not None, f"no golden hash for {platform.machine()}"
    assert digest == expected, f"expected {expected}, got {digest}, stats {stats}"
