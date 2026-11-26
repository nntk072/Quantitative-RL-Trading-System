"""Env-level oracle scenarios for pending orders, ambiguous bars, breach latch and candidate mask.

Each scenario is an entry of ``env_scenarios`` in the frozen fixture file
(SEMANTIC-ORACLE, fixture version 2.0.0). Expectations are hand-derived in the fixture
and only replayed here. Scenarios whose polarity is ``open`` are skipped with their reason,
so they stay visible. Scenarios whose polarity is ``not_applicable`` check the evidence
claim that the source has no such operation.
"""

from __future__ import annotations

import functools
import json
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pandas as pd
import pytest

from decisioning.trade_setup import candidate_geometry_slot_count
from market_data.loading.ticks import TickLimitExecutionQuote
from simulation.environment.candidate_geometry_observation import (
    build_candidate_geometry_observation,
)
from simulation.environment.env import TradingEnv
from tests.unit.simulation.test_environment.test_trading_env_golden_traces import (
    _make_deterministic_bars,
    _make_features,
)
from trading.execution.broker import Position

FIXTURE_PATH = (
    Path(__file__).resolve().parents[4]
    / "planning"
    / "native_modernization"
    / "semantic_oracle"
    / "fixtures"
    / "semantic_oracle_fixtures.v2.json"
)
SCENARIOS = {
    s["id"]: s for s in json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))["env_scenarios"]
}


@dataclass
class _Bar:
    open: float
    high: float
    low: float
    close: float
    spread: float


@functools.cache
def _tape() -> tuple[pd.DataFrame, pd.DataFrame]:
    bars = _make_deterministic_bars(120)
    return bars, _make_features(bars)


def _env(*, episodic: bool = True, block_overnight: bool = False) -> TradingEnv:
    bars, features = _tape()
    env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=10,
        initial_balance=100_000.0,
        episodic=episodic,
        use_sweep_reward=False,
        block_overnight=block_overnight,
    )
    env.reset(seed=42)
    return env


def _pending_order(env: TradingEnv, session_id: int, fill_quote: Any) -> dict[str, Any]:
    bar_time = pd.Timestamp(env._bar_time(env.step_idx))
    return {
        "order_id": "oracle-order-1",
        "order_type": "limit",
        "decision_id": "oracle-decision-1",
        "direction": 1,
        "risk_frac": 0.01,
        "rr_ratio": 2.0,
        "feat_row": env._feature_row_at(env.step_idx),
        "decision_time": bar_time,
        "decision_bar_time": bar_time,
        "decision_bar_idx": env.step_idx,
        "signal_bar_idx": env.step_idx,
        "signal_time": bar_time,
        "order_submission_time": bar_time,
        "expiry_time": bar_time + pd.Timedelta(hours=5),
        "limit_price": 20000.0,
        "entry_candidate": None,
        "decision_action": {},
        "selected": {},
        "fill_quote": fill_quote,
        "session_id": session_id,
    }


def _limit_quote(env: TradingEnv, offset_minutes: float) -> TickLimitExecutionQuote:
    base = pd.Timestamp(env._bar_time(env.step_idx))
    tick = base + pd.Timedelta(minutes=offset_minutes)
    return TickLimitExecutionQuote(
        order_time=base,
        arrival_time=base,
        tick_time=tick,
        bid=20000.0,
        ask=20000.6,
        limit_price=20000.0,
        latency_ns=0,
    )


def _run_pending(session_offset: int, fill_offset: float | None) -> dict[str, Any]:
    env = _env(episodic=True, block_overnight=True)
    assert env._session_ids_arr is not None
    session_id = int(env._session_ids_arr[env.step_idx]) + session_offset
    fill_quote = None if fill_offset is None else _limit_quote(env, fill_offset)
    env._pending_entry_order = _pending_order(env, session_id, fill_quote)
    env.step(0)
    cancels = [t for t in env.trade_log if t.get("type") == "order_cancel"]
    return {
        "trade_types": [t.get("type") for t in env.trade_log],
        "cancel_reason": cancels[0]["reason"] if cancels else None,
        "pending_after": env._pending_entry_order is not None,
        "position_open": env.position is not None,
        "entry_price": None if env.position is None else float(env.position.entry_price),
        "direction": None if env.position is None else int(env.position.direction),
    }


def _check_bar(high: float, low: float) -> dict[str, Any]:
    env = _env(episodic=True)
    env.position = Position(
        direction=1,
        size=1.0,
        entry_price=100.0,
        margin_used=0.0,
        initial_size=1.0,
        sl_price=99.0,
        tp_price=101.0,
        tp1_price=101.0,
        entry_timestamp=None,
    )
    bar: Any = _Bar(100.0, high, low, 100.0, 0.6)
    env._check_sl_tp(bar, 100.0, 100.0, bar_idx=env.step_idx)
    last = env.trade_log[-1] if env.trade_log else None
    return {
        "close_type": None if last is None else last["type"],
        "reason": None if last is None else last.get("reason"),
        "price": None if last is None else float(last["price"]),
        "position_open": env.position is not None,
    }


def _run_breach(breached: bool, steps: int = 40) -> dict[str, Any]:
    env = _env(episodic=False)
    if breached:
        env.account.close_trade(-11_000.0)
    opens = 0
    for _ in range(steps):
        before = len(env.trade_log)
        env.step(1)
        opens += sum(1 for t in env.trade_log[before:] if t.get("type") == "open")
    return {
        "opens": opens,
        "opens_at_least": opens,
        "breach_log": list(env.breach_log),
        "year_failed": bool(getattr(env, "_year_failed", False)),
    }


def _mask_indices(env: SimpleNamespace) -> list[int]:
    mask = build_candidate_geometry_observation(env)["candidate_mask"]
    return [int(i) for i in range(len(mask)) if bool(mask[i])]


def _replay(scenario: dict[str, Any]) -> None:
    sid = scenario["id"]
    expect = scenario["expect"]
    if sid.startswith("G1-") and sid != "G1-replace":
        fill_offset = {
            "G1-cancel-session-change": None,
            "G1-session-change-beats-available-fill": 0.0,
            "G1-fill-within-interval": 0.0,
            "G1-no-fill-after-interval": 5.0,
        }[sid]
        session_offset = (
            0 if sid in {"G1-fill-within-interval", "G1-no-fill-after-interval"} else -1
        )
        observed = _run_pending(session_offset, fill_offset)
        for key, want in expect.items():
            got = observed[key]
            if key == "entry_price":
                assert got == pytest.approx(want, abs=1e-9), f"{sid}.{key}: {got!r}"
            else:
                assert got == want, f"{sid}.{key}: {got!r} != {want!r}"
        return
    if sid == "G1-replace":
        names = [name for name in dir(TradingEnv) if not name.startswith("_")]
        assert not [n for n in names if "replace" in n or "amend" in n]
        return
    if sid.startswith("G3-"):
        bounds = {
            "G3-both-levels-stop-wins": (101.5, 98.5),
            "G3-tp-only": (101.5, 99.5),
            "G3-sl-only-gap-free": (100.2, 98.5),
            "G3-no-touch": (100.5, 99.5),
        }[sid]
        observed = _check_bar(*bounds)
        if expect.get("close_type") is None:
            assert observed["close_type"] is None and observed["position_open"] is True
            return
        for key, want in expect.items():
            got = observed[key]
            if key == "price":
                assert got == pytest.approx(want, abs=1e-9), f"{sid}.price {got!r} != {want!r}"
            else:
                assert got == want, f"{sid}.{key}: {got!r} != {want!r}"
        return
    if sid.startswith("G4-"):
        observed = _run_breach(breached=sid == "G4-breach-latch-blocks-entries")
        if "opens" in expect:
            assert observed["opens"] == expect["opens"]
        if "opens_at_least" in expect:
            assert observed["opens"] >= expect["opens_at_least"]
        assert observed["breach_log"] == expect["breach_log"]
        assert observed["year_failed"] is expect["year_failed"]
        return
    if sid.startswith("G2-"):
        disabled = SimpleNamespace(step_idx=0, candidate_geometry_actions=False)
        if sid == "G2-disabled-ignores-setup-ids":
            disabled._trade_setup_candidate_ids = [1, 2]
        assert _mask_indices(disabled) == expect["mask_true_indices"]
        if "width" in expect:
            width = build_candidate_geometry_observation(disabled)["candidate_mask"].shape[0]
            assert width == candidate_geometry_slot_count()
        return
    raise AssertionError(f"no replay for scenario {sid!r}")


_REPLAYABLE = [
    s for s in SCENARIOS.values() if s["polarity"] in {"positive", "adverse", "not_applicable"}
]
_OPEN = [s for s in SCENARIOS.values() if s["polarity"] == "open"]


@pytest.mark.parametrize("scenario", [pytest.param(s, id=s["id"]) for s in _REPLAYABLE])
def test_env_scenario_matches_hand_expectation(scenario: dict[str, Any]) -> None:
    _replay(scenario)


@pytest.mark.parametrize("scenario", [pytest.param(s, id=s["id"]) for s in _OPEN])
def test_open_env_scenario_is_visible_not_passed(scenario: dict[str, Any]) -> None:
    pytest.skip(f"open item, not passed: {scenario['classification']}")


def test_every_scenario_group_has_a_positive_and_an_adverse_case() -> None:
    for group in ("G1", "G2", "G3", "G4"):
        polarities = {s["polarity"] for s in SCENARIOS.values() if s["group"] == group}
        assert {"positive", "adverse"} <= polarities, group


def test_zero_target_leg_consumes_slot_and_keeps_position() -> None:
    """Fixture defect C3, fixed in version 2.0.0: a TP leg that rounds to zero must not exit.

    A 0.01-lot position with a 30 percent TP1 leg: the leg is 0.003 lots, which rounds to 0.
    The slot is consumed, the position stays open at 0.01 lots, and no trade is recorded.
    """
    env = _env(episodic=True)
    env.position = Position(
        direction=1,
        size=0.01,
        entry_price=100.0,
        margin_used=0.0,
        initial_size=0.01,
        tp_initial_size=0.01,
        tp1_price=101.0,
        tp2_price=102.0,
        tp_lot_fractions=(0.3, 0.7),
        sl_price=99.0,
        tp_price=101.0,
    )
    bar: Any = _Bar(100.0, 101.5, 99.5, 100.0, 0.6)
    env._check_sl_tp(bar, 100.0, 100.0, bar_idx=env.step_idx)
    assert env.position is not None
    assert env.position.size == pytest.approx(0.01, abs=1e-12)
    assert env.position.tp1_price is None
    assert env.position.tp_hit_mask & 1 == 1
    assert env.trade_log == []
