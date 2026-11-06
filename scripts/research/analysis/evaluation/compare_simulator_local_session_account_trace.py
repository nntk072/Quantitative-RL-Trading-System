#!/usr/bin/env python3
"""Compare controlled account transitions on two supplied local M1 sessions.

This is a deterministic engine-parity trace, not a learned-policy replay or an
economic performance estimate. It preserves the local date-derived session
IDs and uses only supplied training bars and local session labels.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd

from artifacts.atomic import write_json_atomic
from artifacts.identity import file_sha256
from configuration.paths import repository_root
from market_data.loading.bars import load_bars
from market_data.loading.ticks import TickBook, build_tick_book
from market_data.transforms.cleaning import clean
from market_data.transforms.sessions import add_session_id, add_session_labels
from simulation.backtest import run_backtest
from simulation.environment.env import TradingEnv
from trading.execution import COST_US100

ROOT = repository_root(__file__)
DEFAULT_BARS = Path("data/training/US100.cash_M1_202412300105_202610162349.csv")
DEFAULT_PACKET = Path(
    "evidence/research/simulator_execution_parity/local_session_account_transition"
)
DEFAULT_TICKS = Path("data/training/US100.cash_202412300105_202610162349.csv")
INITIAL_BALANCE = 50_000.0


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _event_record(event: Any) -> dict[str, Any]:
    source = event.to_dict() if hasattr(event, "to_dict") else dict(event)
    output: dict[str, Any] = {}
    for key in (
        "type",
        "direction",
        "price",
        "pnl",
        "net_pnl",
        "lots",
        "size",
        "session_id",
        "decision_bar_time",
        "decision_time",
        "order_submission_time",
        "fill_time",
        "close_time",
        "time",
        "reason",
        "exit_reason",
        "equity",
        "daily_loss",
    ):
        if key not in source:
            continue
        value = source[key]
        if value is pd.NA or value is pd.NaT:
            value = None
        elif isinstance(value, (pd.Timestamp, np.datetime64)):
            value = pd.Timestamp(value).isoformat()
        elif isinstance(value, np.generic):
            value = value.item()
        if isinstance(value, float) and not np.isfinite(value):
            value = None
        output[key] = value
    return output


def build_report(
    bars_path: Path,
    *,
    timezone: str = "Etc/GMT-3",
    ticks_path: Path | None = None,
    scenario: str = "account_transition",
    prebuilt_tickbook: TickBook | None = None,
    input_bars_sha256: str | None = None,
    input_ticks_sha256: str | None = None,
) -> dict[str, Any]:
    if scenario not in {
        "account_transition",
        "daily_loss_full_evaluation_failure",
        "max_loss_terminal",
    }:
        raise ValueError(f"unsupported account trace scenario: {scenario!r}")
    bars = clean(load_bars(bars_path), tz=timezone)
    bars = add_session_labels(bars, tz=timezone)
    bars = add_session_id(bars)
    bars = bars.loc[(bars.index >= "2024-12-30") & (bars.index < "2026-01-01")]
    eligible: list[tuple[int, pd.DataFrame]] = []
    for session_id, group in bars.loc[bars["session"] == "ny"].groupby("session_id", sort=True):
        if len(group) >= 8:
            eligible.append((int(cast(int, session_id)), group.iloc[:8].copy()))
        if len(eligible) == 2:
            break
    if len(eligible) != 2 or eligible[0][0] == eligible[1][0]:
        raise ValueError(
            "could not find two distinct local training session IDs with eight NY bars"
        )

    trace_bars = pd.concat([group for _, group in eligible]).copy()
    trace_index = pd.DatetimeIndex(trace_bars.index)
    if trace_bars.index.has_duplicates:
        raise ValueError("selected local session bars have duplicate timestamps")
    tickbook = prebuilt_tickbook
    if ticks_path is not None and tickbook is None:
        tickbook = build_tick_book(
            ticks_path,
            tz=timezone,
            session_start="16:00",
            session_end="23:59",
            price_grid_increment=0.25,
        )
    # These wide, current-row-relative references keep protective levels out
    # of the deliberately short controlled entry/exit path. They are not
    # supplied to a trained policy and do not use future prices.
    features = pd.DataFrame(
        {
            "last_swing_low": trace_bars["close"].to_numpy(dtype=float) - 1_000.0,
            "last_swing_high": trace_bars["close"].to_numpy(dtype=float) + 1_000.0,
            # Controlled runner lookup only; never interpreted as a market feature.
            "trace_bar_ordinal": np.arange(len(trace_bars), dtype=float),
        },
        index=trace_bars.index,
    )
    # There are 14 transitions for 16 bars. The daily-loss scenario attempts a
    # same-session re-entry after a breach, then checks next-session recovery.
    actions = (
        [1, 0, 19, 1, 0, 0, 0, 0, 1, 0, 19, 0, 0, 0]
        if scenario in {"daily_loss_full_evaluation_failure", "max_loss_terminal"}
        else [1, 0, 19, 0, 0, 0, 0, 0, 1, 0, 19, 0, 0, 0]
    )
    if len(actions) != len(trace_bars) - 2:
        raise ValueError("controlled action sequence does not match selected bars")

    guardrails = {
        "daily_loss_limit": 1.0 if scenario == "daily_loss_full_evaluation_failure" else 10_000.0,
        "max_loss_limit": 1.0 if scenario == "max_loss_terminal" else 20_000.0,
        "risk_per_trade_limit": 10_000.0,
        "soft_daily_loss_limit": 0.0,
        "soft_max_loss_limit": 0.0,
        # Hard loss limits are percentage-based. Preserve the $1 controlled
        # breach by configuring its equivalent share of initial balance.
        "daily_loss_limit_pct": 1.0 / INITIAL_BALANCE
        if scenario == "daily_loss_full_evaluation_failure"
        else 0.05,
        "max_loss_limit_initial_pct": 1.0 / INITIAL_BALANCE
        if scenario == "max_loss_terminal"
        else 0.10,
        "soft_daily_loss_limit_pct": 0.0,
        "soft_max_loss_limit_initial_pct": 0.0,
    }
    tick_mode = tickbook is not None
    randomized_fill_latency_ms = 30.0 if tick_mode else 0.0
    env = TradingEnv(
        bars=trace_bars,
        features=features,
        obs_window=1,
        initial_balance=INITIAL_BALANCE,
        cost_model=COST_US100,
        guardrail_kwargs=guardrails,
        risk_frac_range=(0.001, 0.001),
        rr_ratio_range=(1.0, 1.0),
        min_lot=0.01,
        max_lot=1.0,
        contract_size=1.0,
        max_loss_per_trade_usd=1_000.0,
        episodic=scenario == "max_loss_terminal",
        reward_mode="pnl",
        block_overnight=False,
        tickbook=tickbook,
        tick_execution_required=tick_mode,
        randomized_fill_latency_ms=randomized_fill_latency_ms,
    )
    env.reset(seed=7)
    env_terminated = False
    env_truncated = False
    env_termination_action_index: int | None = None
    env_actions_executed = 0
    for action_index, action in enumerate(actions):
        _, _, terminated, truncated, _ = env.step(action)
        env_actions_executed += 1
        if terminated or truncated:
            env_terminated = bool(terminated)
            env_truncated = bool(truncated)
            env_termination_action_index = action_index
            if scenario != "max_loss_terminal":
                raise ValueError(
                    "account trace terminated before its controlled action sequence ended"
                )
            break
    if scenario == "max_loss_terminal" and not env_terminated:
        raise ValueError("max-loss scenario did not terminate the episodic environment")

    def policy(observation: np.ndarray[Any, Any]) -> int:
        action_bar_index = int(round(float(observation[-1, -1])))
        if action_bar_index >= len(actions):
            return 0
        return actions[action_bar_index]

    result = run_backtest(
        trace_bars,
        features,
        policy,
        obs_window=1,
        cost_model=COST_US100,
        initial_balance=INITIAL_BALANCE,
        guardrail_kwargs=guardrails,
        risk_frac=0.001,
        rr_ratio=1.0,
        use_structure_sl_tp=True,
        swing_buffer_pts=0.0,
        min_lot=0.01,
        max_lot=1.0,
        contract_size=1.0,
        max_loss_per_trade_usd=1_000.0,
        hold_on_zero=True,
        block_overnight=False,
        exit_action=19,
        tickbook=tickbook,
        tick_execution_required=tick_mode,
        randomized_fill_latency_ms=randomized_fill_latency_ms,
        execution_seed=7,
    )

    env_events = [_event_record(event) for event in env.trade_log]
    backtest_events = [_event_record(event) for event in result["trades"].to_dict("records")]
    env_breach_events = [_event_record(event) for event in env.breach_events]
    backtest_breach_events = [_event_record(event) for event in result["breach_events"]]

    def lifecycle(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        records = []
        for event in events:
            if event.get("type") in {"open", "close", "forced_close"}:
                record = dict(event)
                if record["type"] == "forced_close":
                    record["event_type"] = "forced_close"
                    record["type"] = "close"
                records.append(record)
        return records

    env_lifecycle = lifecycle(env_events)
    backtest_lifecycle = lifecycle(backtest_events)
    env_opens = [event for event in env_lifecycle if event["type"] == "open"]
    backtest_opens = [event for event in backtest_lifecycle if event["type"] == "open"]
    env_closes = [event for event in env_lifecycle if event["type"] == "close"]
    backtest_closes = [event for event in backtest_lifecycle if event["type"] == "close"]
    expected_lifecycle_count = (
        1 if scenario in {"max_loss_terminal", "daily_loss_full_evaluation_failure"} else 2
    )
    if (len(env_opens), len(backtest_opens), len(env_closes), len(backtest_closes)) != (
        expected_lifecycle_count,
        expected_lifecycle_count,
        expected_lifecycle_count,
        expected_lifecycle_count,
    ):
        raise ValueError(
            f"{scenario} produced unexpected lifecycle counts: "
            f"env_opens={len(env_opens)}, backtest_opens={len(backtest_opens)}, "
            f"env_closes={len(env_closes)}, backtest_closes={len(backtest_closes)}, "
            f"expected_each={expected_lifecycle_count}"
        )
    if [event["type"] for event in env_lifecycle] != [
        event["type"] for event in backtest_lifecycle
    ]:
        raise ValueError("environment and backtest open/close lifecycle order differs")

    def event_session(event: dict[str, Any]) -> int:
        session_id = event.get("session_id")
        if session_id is not None:
            return int(session_id)
        event_time = next(
            (
                event[key]
                for key in ("fill_time", "close_time", "time")
                if event.get(key) is not None
            ),
            None,
        )
        if event_time is None:
            raise ValueError("lifecycle event has neither a session ID nor a fill time")
        timestamp = pd.Timestamp(event_time)
        if timestamp.tzinfo is None:
            timestamp = timestamp.tz_localize(trace_index.tz)
        else:
            timestamp = timestamp.tz_convert(trace_index.tz)
        bar_time = timestamp.floor("min")
        if bar_time in trace_index:
            return int(cast(int, trace_bars.loc[bar_time, "session_id"]))
        matching_sessions = [
            session_id
            for session_id, group in eligible
            if group.index[0].date() <= timestamp.date() <= group.index[-1].date()
        ]
        if len(matching_sessions) != 1:
            raise ValueError(
                f"lifecycle fill timestamp has no unique selected local session: {timestamp}"
            )
        return matching_sessions[0]

    def event_time(event: dict[str, Any]) -> str | None:
        value = next(
            (
                event[key]
                for key in ("fill_time", "close_time", "time")
                if event.get(key) is not None
            ),
            None,
        )
        return str(value) if value is not None else None

    def event_timestamp(event: dict[str, Any]) -> pd.Timestamp:
        value = event_time(event)
        if value is None:
            raise ValueError("open event has no timestamp")
        return pd.Timestamp(value)

    lifecycle_comparisons = []
    for env_event, backtest_event in zip(env_lifecycle, backtest_lifecycle, strict=True):
        lifecycle_comparisons.append(
            {
                "type": env_event["type"],
                "same_session_id": event_session(env_event) == event_session(backtest_event),
                "same_fill_time": event_time(env_event) is not None
                and event_time(env_event) == event_time(backtest_event),
                "same_direction": env_event.get("direction") == backtest_event.get("direction"),
                "price_delta": float(env_event["price"]) - float(backtest_event["price"]),
                "same_price": bool(
                    np.isclose(
                        float(env_event["price"]),
                        float(backtest_event["price"]),
                        rtol=0.0,
                        atol=1e-8,
                    )
                ),
            }
        )
    if not all(
        item["same_session_id"]
        and item["same_fill_time"]
        and item["same_direction"]
        and item["same_price"]
        for item in lifecycle_comparisons
    ):
        execution_lifecycle_matches = False
    else:
        execution_lifecycle_matches = True

    close_comparisons = []
    for env_close, backtest_close in zip(env_closes, backtest_closes, strict=True):
        close_time_equal = event_time(env_close) is not None and event_time(
            env_close
        ) == event_time(backtest_close)
        close_comparisons.append(
            {
                "same_session_id": event_session(env_close) == event_session(backtest_close),
                "same_close_time": close_time_equal,
                "pnl_delta": float(env_close["pnl"]) - float(backtest_close["pnl"]),
                "same_pnl": bool(
                    np.isclose(
                        float(env_close["pnl"]), float(backtest_close["pnl"]), rtol=0.0, atol=1e-9
                    )
                ),
            }
        )
    close_lifecycle_matches = all(
        item["same_session_id"] and item["same_close_time"] and item["same_pnl"]
        for item in close_comparisons
    )

    first_session_id, second_session_id = (session_id for session_id, _ in eligible)
    expected_close_sessions = (
        {first_session_id}
        if scenario in {"max_loss_terminal", "daily_loss_full_evaluation_failure"}
        else {first_session_id, second_session_id}
    )
    if {event_session(event) for event in env_closes} != expected_close_sessions:
        actual_sessions = {event_session(event) for event in env_closes}
        raise ValueError(
            "environment close events do not cover expected sessions: "
            f"expected={expected_close_sessions}, actual={actual_sessions}, "
            f"events={env_closes}"
        )
    if {event_session(event) for event in backtest_closes} != expected_close_sessions:
        actual_sessions = {event_session(event) for event in backtest_closes}
        raise ValueError(
            "backtest close events do not cover expected sessions: "
            f"expected={expected_close_sessions}, actual={actual_sessions}, "
            f"events={backtest_closes}"
        )
    env_first_session_pnl = sum(
        float(event["pnl"]) for event in env_closes if event_session(event) == first_session_id
    )
    backtest_first_session_pnl = sum(
        float(event["pnl"]) for event in backtest_closes if event_session(event) == first_session_id
    )
    session_reset_check_applicable = scenario != "max_loss_terminal"
    env_reset_matches = (
        bool(
            np.isclose(
                env.account.session_start_balance,
                INITIAL_BALANCE + env_first_session_pnl,
                rtol=0.0,
                atol=1e-8,
            )
        )
        if session_reset_check_applicable
        else None
    )
    backtest_reset_matches = (
        bool(
            np.isclose(
                result["account"].session_start_balance,
                INITIAL_BALANCE + backtest_first_session_pnl,
                rtol=0.0,
                atol=1e-8,
            )
        )
        if session_reset_check_applicable
        else None
    )

    equity_delta = float(env.account.equity) - float(result["account"].equity)
    balance_delta = float(env.account.balance) - float(result["account"].balance)
    daily_loss_delta = float(env.account.daily_loss) - float(result["account"].daily_loss)
    daily_loss_comparison_applicable = scenario != "max_loss_terminal"
    account_matches = all(
        np.isclose(value, 0.0, rtol=0.0, atol=1e-8)
        for value in (
            (equity_delta, balance_delta, daily_loss_delta)
            if daily_loss_comparison_applicable
            else (equity_delta, balance_delta)
        )
    )
    env_first_session_open_count = sum(
        event_session(event) == first_session_id for event in env_opens
    )
    backtest_first_session_open_count = sum(
        event_session(event) == first_session_id for event in backtest_opens
    )
    env_second_session_open_count = sum(
        event_session(event) == second_session_id for event in env_opens
    )
    backtest_second_session_open_count = sum(
        event_session(event) == second_session_id for event in backtest_opens
    )
    env_post_breach_same_session_opens = 0
    backtest_post_breach_same_session_opens = 0
    if scenario in {"daily_loss_full_evaluation_failure", "max_loss_terminal"}:
        if env_breach_events and backtest_breach_events:
            env_breach_time = pd.Timestamp(env_breach_events[0]["time"])
            backtest_breach_time = pd.Timestamp(backtest_breach_events[0]["time"])
            env_post_breach_same_session_opens = sum(
                event_session(event) == first_session_id
                and event_timestamp(event) > env_breach_time
                for event in env_opens
            )
            backtest_post_breach_same_session_opens = sum(
                event_session(event) == first_session_id
                and event_timestamp(event) > backtest_breach_time
                for event in backtest_opens
            )
        if scenario == "daily_loss_full_evaluation_failure":
            breach_reason = "daily_loss"
        else:
            breach_reason = "max_drawdown"
        breach_lists_match = (
            len(env_breach_events) == 1
            and len(backtest_breach_events) == 1
            and str(env_breach_events[0].get("reason")) == breach_reason
            and str(backtest_breach_events[0].get("reason")) == breach_reason
            and int(env_breach_events[0].get("session_id", -1)) == first_session_id
            and int(backtest_breach_events[0].get("session_id", -1)) == first_session_id
            and pd.Timestamp(env_breach_events[0]["time"])
            == pd.Timestamp(backtest_breach_events[0]["time"])
            and np.isclose(
                float(env_breach_events[0]["equity"]),
                float(backtest_breach_events[0]["equity"]),
                rtol=0.0,
                atol=1e-8,
            )
            and np.isclose(
                float(env_breach_events[0]["daily_loss"]),
                float(backtest_breach_events[0]["daily_loss"]),
                rtol=0.0,
                atol=1e-8,
            )
        )
        expected_limit = guardrails[
            "daily_loss_limit"
            if scenario == "daily_loss_full_evaluation_failure"
            else "max_loss_limit"
        ]
        expected_session_opens = 0
        risk_transition_matches = (
            breach_lists_match
            and actions[3] == 1
            and env_first_session_open_count == 1
            and backtest_first_session_open_count == 1
            and env_second_session_open_count == expected_session_opens
            and backtest_second_session_open_count == expected_session_opens
            and env_post_breach_same_session_opens == 0
            and backtest_post_breach_same_session_opens == 0
            and env_first_session_pnl <= -expected_limit
            and (
                not session_reset_check_applicable or (env_reset_matches and backtest_reset_matches)
            )
            and (scenario != "max_loss_terminal" or env_terminated)
            and (
                scenario != "max_loss_terminal"
                or (env_termination_action_index is not None and env_termination_action_index <= 2)
            )
        )
    else:
        risk_transition_matches = not env_breach_events and not backtest_breach_events
    risk_transition = {
        "scenario": scenario,
        "daily_loss_limit": guardrails["daily_loss_limit"],
        "max_loss_limit": guardrails["max_loss_limit"],
        "environment_breach_events": env_breach_events,
        "backtest_breach_events": backtest_breach_events,
        "environment_first_session_open_count": env_first_session_open_count,
        "backtest_first_session_open_count": backtest_first_session_open_count,
        "environment_next_session_open_count": env_second_session_open_count,
        "backtest_next_session_open_count": backtest_second_session_open_count,
        "environment_post_breach_same_session_open_count": env_post_breach_same_session_opens,
        "backtest_post_breach_same_session_open_count": backtest_post_breach_same_session_opens,
        "attempted_same_session_reentry_after_first_close": scenario
        in {"daily_loss_full_evaluation_failure"}
        and actions[3] == 1,
        "scheduled_same_session_entry_after_max_loss": scenario == "max_loss_terminal"
        and actions[3] == 1,
        "same_session_reentry_blocked": scenario != "max_loss_terminal"
        or (env_first_session_open_count == 1 and backtest_first_session_open_count == 1),
        "next_session_entry_allowed_after_reset": False,
        "max_loss_rollout_latched": scenario == "max_loss_terminal"
        and env_second_session_open_count == 0
        and backtest_second_session_open_count == 0,
        "daily_loss_evaluation_latched": scenario == "daily_loss_full_evaluation_failure"
        and env_second_session_open_count == 0
        and backtest_second_session_open_count == 0,
        "environment_terminated": env_terminated,
        "environment_truncated": env_truncated,
        "environment_termination_action_index": env_termination_action_index,
        "environment_actions_executed": env_actions_executed,
        "risk_transition_matches": bool(risk_transition_matches),
    }
    trace_passed = (
        execution_lifecycle_matches
        and close_lifecycle_matches
        and (not session_reset_check_applicable or (env_reset_matches and backtest_reset_matches))
        and account_matches
        and risk_transition_matches
    )

    return {
        "schema_version": 1,
        "trace_passed": bool(trace_passed),
        "trace_status": "matched"
        if trace_passed
        else ("tick_path_account_difference" if tick_mode else "bar_fallback_execution_difference"),
        "scenario": scenario,
        "execution_mode": "tick_required" if tick_mode else "bar_fallback",
        "randomized_fill_latency_ms": randomized_fill_latency_ms,
        "session_reset_check_applicable": session_reset_check_applicable,
        "interpretation": "Controlled account-transition comparison on local training bars; not a learned-policy replay or economic performance estimate.",
        "execution_timing_contracts": {
            "environment": "TickBook quote at configured execution time"
            if tick_mode
            else "next-market-bar open quote and timestamp",
            "event_backtest": "TickBook quote at configured execution time"
            if tick_mode
            else "next-market-bar open quote and timestamp",
            "source_basis": "current engine implementations and the bar-open parity regression",
        },
        "session_source": "local M1 bar dates and the repository's date-derived session_id; local NY labels select the rows, with no external calendar claim",
        "timezone_label": timezone,
        "input_bars": str(bars_path.resolve().relative_to(ROOT)),
        "input_bars_sha256": input_bars_sha256 or file_sha256(bars_path),
        "input_ticks": None if ticks_path is None else str(ticks_path.resolve().relative_to(ROOT)),
        "input_ticks_sha256": (
            None if ticks_path is None else input_ticks_sha256 or file_sha256(ticks_path)
        ),
        "selected_sessions": [
            {
                "session_id": session_id,
                "date": str(group.index[0].date()),
                "first_bar": group.index[0].isoformat(),
                "last_bar": group.index[-1].isoformat(),
                "selected_rows": len(group),
            }
            for session_id, group in eligible
        ],
        "controlled_actions": actions,
        "guardrail_settings": guardrails,
        "risk_transition": risk_transition,
        "initial_balance": INITIAL_BALANCE,
        "environment_events": env_events,
        "backtest_events": backtest_events,
        "lifecycle_comparisons": lifecycle_comparisons,
        "close_comparisons": close_comparisons,
        "first_session_realized_close_pnl": {
            "environment": env_first_session_pnl,
            "event_backtest": backtest_first_session_pnl,
        },
        "expected_second_session_start_balance": {
            "environment": (
                INITIAL_BALANCE + env_first_session_pnl if session_reset_check_applicable else None
            ),
            "event_backtest": (
                INITIAL_BALANCE + backtest_first_session_pnl
                if session_reset_check_applicable
                else None
            ),
        },
        "environment_second_session_start_balance": float(env.account.session_start_balance),
        "backtest_second_session_start_balance": float(result["account"].session_start_balance),
        "session_reset_matches_within_engine": {
            "environment": env_reset_matches,
            "event_backtest": backtest_reset_matches,
        },
        "final_account": {
            "environment_balance": float(env.account.balance),
            "backtest_balance": float(result["account"].balance),
            "environment_equity": float(env.account.equity),
            "backtest_equity": float(result["account"].equity),
            "environment_daily_loss": float(env.account.daily_loss),
            "backtest_daily_loss": float(result["account"].daily_loss),
            "balance_delta": balance_delta,
            "equity_delta": equity_delta,
            "daily_loss_delta": daily_loss_delta,
            "daily_loss_comparison_applicable": daily_loss_comparison_applicable,
            "daily_loss_comparison_scope": (
                "final_state"
                if daily_loss_comparison_applicable
                else "breach_instant_only_environment_terminates_before_backtest_session_reset"
            ),
            "cross_engine_account_state_matches": bool(account_matches),
        },
        "code_sha256": {
            "simulation/environment/env.py": _sha256(ROOT / "simulation/environment/env.py"),
            "simulation/environment/risk_runtime.py": _sha256(
                ROOT / "simulation/environment/risk_runtime.py"
            ),
            "simulation/backtest/event_driven_backtest.py": _sha256(
                ROOT / "simulation/backtest/event_driven_backtest.py"
            ),
            "simulation/backtest/protective_events.py": _sha256(
                ROOT / "simulation/backtest/protective_events.py"
            ),
            "market_data/transforms/sessions.py": _sha256(
                ROOT / "market_data/transforms/sessions.py"
            ),
            "generator": _sha256(Path(__file__).resolve()),
        },
        "limitations": [
            "Two selected local date-derived sessions and two controlled positions are not comprehensive execution coverage.",
            "The action schedule is prescribed and does not estimate policy quality or economic value.",
            "Local broker-time session IDs are used as supplied; no external clock or schedule authority is asserted.",
            "This does not establish broker-connected or restart-safe live account parity.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bars-csv", type=Path, default=ROOT / DEFAULT_BARS)
    parser.add_argument("--ticks-csv", type=Path)
    parser.add_argument("--timezone", default="Etc/GMT-3")
    parser.add_argument("--out", type=Path)
    parser.add_argument(
        "--scenario",
        choices=(
            "account_transition",
            "daily_loss_full_evaluation_failure",
            "max_loss_terminal",
            "both",
            "all",
        ),
        default="account_transition",
    )
    args = parser.parse_args()
    scenarios = (
        ("account_transition", "daily_loss_full_evaluation_failure")
        if args.scenario == "both"
        else ("account_transition", "daily_loss_full_evaluation_failure", "max_loss_terminal")
        if args.scenario == "all"
        else (args.scenario,)
    )
    packet_dir = args.out.parent.resolve() if args.out is not None else ROOT / DEFAULT_PACKET
    packet_dir.mkdir(parents=True, exist_ok=True)
    input_bars_hash = file_sha256(args.bars_csv)
    input_ticks_hash = file_sha256(args.ticks_csv) if args.ticks_csv is not None else None
    shared_tickbook = None
    if args.ticks_csv is not None and len(scenarios) > 1:
        shared_tickbook = build_tick_book(
            args.ticks_csv,
            tz=args.timezone,
            session_start="16:00",
            session_end="23:59",
            price_grid_increment=0.25,
        )
    reports: list[tuple[Path, dict[str, Any]]] = []
    for scenario in scenarios:
        if args.out is not None and len(scenarios) == 1:
            output_path = args.out.resolve()
        elif scenario == "account_transition":
            filename = (
                "session_tick_account_transition.json"
                if args.ticks_csv
                else "session_account_transition.json"
            )
            output_path = packet_dir / filename
        elif scenario == "daily_loss_full_evaluation_failure":
            filename = "daily_breach_full_evaluation_failure.json"
            output_path = packet_dir / filename
        else:
            filename = (
                "session_tick_max_loss_terminal.json"
                if args.ticks_csv
                else "session_max_loss_terminal.json"
            )
            output_path = packet_dir / filename
        report = build_report(
            args.bars_csv,
            timezone=args.timezone,
            ticks_path=args.ticks_csv,
            scenario=scenario,
            prebuilt_tickbook=shared_tickbook,
            input_bars_sha256=input_bars_hash,
            input_ticks_sha256=input_ticks_hash,
        )
        write_json_atomic(output_path, report)
        reports.append((output_path, report))
    readme = """# Local session account transition trace

This packet uses short, controlled action sequences over supplied US100
training M1 bars from two distinct date-derived session IDs. It compares
environment and event-backtest fills, realized PnL, session-start balance
resets, daily-loss blocking, and final account state. It is not a learned-policy
replay or an economic performance estimate.

Both engines reset their session-start balance from their own prior-session
close PnL. The bar fallback and tick-required traces use the same next-market-
bar open time and quote contract across engines. The tick-required report uses
the same TickBook and 30 ms randomized latency in both engines. Each report
preserves exact event comparisons and the reset checks; neither is a learned-
policy replay.

The daily-loss trace sets a controlled $1 hard daily limit, attempts another
entry after a first-session loss crosses that limit, and checks that both
engines latch account failure across the remainder of the evaluation.

The max-loss trace sets a controlled $1 account-loss limit and runs the
environment episodically. Both engines record the max-loss breach and make no
same-session or later-session opens; the environment terminates at the breach.

Local session labels and date-derived IDs are used as supplied. No external
clock, provider, or calendar claim is made.

## Files

- `session_account_transition.json`: controlled bar-fallback trace.
- `session_tick_account_transition.json`: controlled TickBook trace when
  generated with `--ticks-csv`.
- `daily_breach_full_evaluation_failure.json`: controlled daily-breach latch
  trace generated with `--scenario both --ticks-csv`.
- `session_tick_max_loss_terminal.json`: controlled episodic max-loss
  termination and rollout-wide open latch when generated with `--scenario all --ticks-csv`.
- `session_*_verification.json`: independently recomputed trace and input/source
  byte verification.
- `OUTPUT_SHA256SUMS`: packet and generator hashes.

## Reproduction

```bash
.venv/bin/python scripts/research/analysis/evaluation/compare_simulator_local_session_account_trace.py
.venv/bin/python scripts/research/analysis/evaluation/compare_simulator_local_session_account_trace.py --scenario both --ticks-csv data/training/US100.cash_202412300105_202610162349.csv
.venv/bin/python scripts/research/analysis/evaluation/compare_simulator_local_session_account_trace.py --scenario all --ticks-csv data/training/US100.cash_202412300105_202610162349.csv
.venv/bin/python scripts/research/analysis/evaluation/verify_simulator_local_session_account_trace.py evidence/research/simulator_execution_parity/local_session_account_transition/session_tick_account_transition.json evidence/research/simulator_execution_parity/local_session_account_transition/daily_breach_full_evaluation_failure.json evidence/research/simulator_execution_parity/local_session_account_transition/session_tick_max_loss_terminal.json
```
"""
    readme_path = packet_dir / "README.md"
    readme_path.write_text(readme, encoding="utf-8")
    packet_prefix = packet_dir.relative_to(ROOT).as_posix()
    generator_path = Path(__file__).resolve()
    checksum_lines = [
        f"{_sha256(readme_path)}  {packet_prefix}/README.md",
        *[
            f"{_sha256(path)}  {path.relative_to(ROOT).as_posix()}"
            for path in sorted(
                candidate
                for candidate in packet_dir.glob("*.json")
                if not candidate.name.endswith("_verification.json")
            )
        ],
        f"{_sha256(generator_path)}  {generator_path.relative_to(ROOT).as_posix()}",
    ]
    (packet_dir / "OUTPUT_SHA256SUMS").write_text(
        "\n".join(checksum_lines) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            [
                {
                    "out": str(path),
                    "scenario": report["scenario"],
                    "trace_passed": report["trace_passed"],
                    "trace_status": report["trace_status"],
                    "sessions": len(report["selected_sessions"]),
                }
                for path, report in reports
            ],
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
