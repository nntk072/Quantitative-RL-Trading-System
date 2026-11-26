"""Env-level oracle scenarios for pending orders, ambiguous bars, breach latch and candidate mask.

Each scenario is an entry of ``env_scenarios`` in the frozen fixture file
(SEMANTIC-ORACLE, fixture version 2.0.0). Expectations are hand-derived in the fixture
and only replayed here. Scenarios whose polarity is ``open`` are skipped with their reason,
so they stay visible. Scenarios whose polarity is ``not_applicable`` check the evidence
claim that the source has no such operation.
"""

from __future__ import annotations

import contextlib
import functools
import json
import re
import warnings
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest import mock

import numpy as np
import pandas as pd
import pytest

from decisioning.trade_setup import (
    TRADE_SETUP_CANDIDATES,
    candidate_geometry_slot,
    candidate_geometry_slot_count,
)
from market_data.loading.ticks import TickLimitExecutionQuote
from simulation.environment import candidate_geometry_observation as geometry
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


SECOND_SESSION_BAR = 1440  # first bar of the second NY window on the two-day tape
SECOND_DAY_CANDIDATE = 19  # standard_deviation, M1, long


def _enabled_env(*, signal: bool) -> TradingEnv:
    """Real TradingEnv with candidate geometry enabled (O2).

    Synthetic bands and entry-idea signal columns are added so that the real candidate
    pipeline builds. Zone, age and distance are supplied by the caller through seams.
    """
    warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)
    bars, features = _tape()
    frame = features.copy()
    extra: dict[str, np.ndarray[Any, Any]] = {}
    for candidate in TRADE_SETUP_CANDIDATES:
        side = "long" if int(candidate.direction) == 1 else "short"
        extra[f"entry_idea_{candidate.idea}_{candidate.setup_timeframe}_{side}"] = np.zeros(
            len(frame)
        )
        if candidate.idea == "standard_deviation":
            prefix = "" if candidate.setup_timeframe == "M1" else f"{candidate.setup_timeframe}_"
            extra[f"{prefix}standard_deviation_band_low"] = bars["close"].to_numpy() - 2.0
            extra[f"{prefix}standard_deviation_band_high"] = bars["close"].to_numpy() + 2.0
            if signal:
                extra[f"entry_idea_{candidate.idea}_{candidate.setup_timeframe}_{side}"] = np.ones(
                    len(frame)
                )
    extra["atr_5"] = np.ones(len(frame))
    frame = pd.concat([frame, pd.DataFrame(extra, index=frame.index)], axis=1)
    for _ in range(40):
        try:
            env = TradingEnv(
                bars=bars,
                features=frame,
                obs_window=10,
                initial_balance=100_000.0,
                episodic=True,
                use_sweep_reward=False,
                trade_setup_actions=True,
                candidate_geometry_actions=True,
                agent_entry_execution=True,
                strategy_actions=True,
            )
            env.reset(seed=42)
            return env
        except ValueError as exc:
            missing = re.findall(r"'([^']+)'", str(exc))
            if not missing:
                raise
            for column in missing:
                frame[column] = 0.0
    raise RuntimeError("enabled candidate env could not be built")


def _replay_enabled_geometry(sid: str, expect: dict[str, Any]) -> None:
    signal = sid != "G2-enabled-signal-off"
    zone_present = sid != "G2-enabled-zone-missing"
    env = _enabled_env(signal=signal)
    zone = (19998.0, 20001.0) if zone_present else None
    with contextlib.ExitStack() as stack:
        stack.enter_context(
            mock.patch.object(geometry, "_reference_quote", lambda _e, _i: (20000.0, 20000.1))
        )
        stack.enter_context(mock.patch.object(geometry, "_source_zone", lambda *_a: zone))
        stack.enter_context(
            mock.patch.object(geometry, "_candidate_age_fraction", lambda *_a: 0.25)
        )
        stack.enter_context(
            mock.patch.object(geometry, "_geometry_distances", lambda *_a: (1.0, 2.0, 1.5, 3.0))
        )
        mask = build_candidate_geometry_observation(env)["candidate_mask"]
    true_indices = [int(i) for i in np.flatnonzero(mask)]
    if "mask_true_indices" in expect:
        assert true_indices == expect["mask_true_indices"], f"{sid}: {true_indices}"
    if "candidate_market_slot_eligible" in expect:
        slot = candidate_geometry_slot(SECOND_DAY_CANDIDATE, "market")
        assert bool(mask[slot]), f"{sid}: market slot {slot} not eligible"
        assert bool(mask[0]), f"{sid}: no-trade slot must always be eligible"


def _run_two_day(*, breached: bool, steps: int = 1300) -> dict[str, Any]:
    """Non-episodic real env on a two-day tape with the session window set to the tape clock (O3)."""
    bars = _make_deterministic_bars(1500)
    features = _make_features(bars)
    env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=10,
        initial_balance=100_000.0,
        episodic=False,
        use_sweep_reward=False,
        session_start="16:30",
        session_end="23:00",
        session_timezone="Etc/GMT-3",
    )
    env.reset(seed=42)
    assert env._session_ids_arr is not None
    second_session = int(env._session_ids_arr[SECOND_SESSION_BAR])
    if breached:
        env.account.close_trade(-11_000.0)
    second_steps = 0
    for _ in range(steps):
        if int(env._session_ids_arr[env.step_idx]) == second_session:
            second_steps += 1
        _, _, done, truncated, _ = env.step(1)
        if done or truncated:
            break
    submits = Counter(t.get("session_id") for t in env.trade_log if t.get("type") == "order_submit")
    opens = sum(1 for t in env.trade_log if t.get("type") == "open")
    return {
        "submits_total": sum(submits.values()),
        "submits_in_second_session": submits.get(second_session, 0),
        "second_session_steps": second_steps,
        "opens": opens,
        "breach_log": list(env.breach_log),
        "year_failed": bool(getattr(env, "_year_failed", False)),
    }


def _replay_cross_session(sid: str, expect: dict[str, Any]) -> None:
    observed = _run_two_day(breached=sid == "G4-cross-session-breach-blocks-submits")
    if "submits_in_second_session_at_least" in expect:
        assert observed["submits_in_second_session"] >= expect["submits_in_second_session_at_least"]
    if "second_session_steps_at_least" in expect:
        assert observed["second_session_steps"] >= expect["second_session_steps_at_least"]
    if "submits_total" in expect:
        assert observed["submits_total"] == expect["submits_total"]
    if "opens" in expect:
        assert observed["opens"] == expect["opens"]
    if "breach_log" in expect:
        assert observed["breach_log"] == expect["breach_log"]
    if "year_failed" in expect:
        assert observed["year_failed"] is expect["year_failed"]


def _replay(scenario: dict[str, Any]) -> None:
    sid = scenario["id"]
    expect = scenario["expect"]
    if sid.startswith("G2-enabled"):
        _replay_enabled_geometry(sid, expect)
        return
    if sid.startswith("G4-cross-session"):
        _replay_cross_session(sid, expect)
        return
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


@pytest.mark.parametrize("scenario", [pytest.param(s, id=s["id"]) for s in _REPLAYABLE])
def test_env_scenario_matches_hand_expectation(scenario: dict[str, Any]) -> None:
    _replay(scenario)


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
