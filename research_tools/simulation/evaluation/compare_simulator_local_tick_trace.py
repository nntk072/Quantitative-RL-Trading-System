#!/usr/bin/env python3
"""Replay one source-verified local tick trace through both simulators.

The trace is selected from an existing fill-to-tick source alignment report,
then checked against the current production TickBook and local M1 bars. It is
a controlled action replay, not a replay of the historical campaign policy.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from artifacts.atomic import write_json_atomic
from artifacts.identity import file_sha256
from configuration import load_config
from configuration.paths import repository_root
from market_data.loading.bars import load_bars
from market_data.loading.ticks import TickBook, build_tick_book
from market_data.splits.definitions import inclusive_date_exclusive_end
from market_data.transforms.sessions import (
    add_session_id,
    add_session_labels,
    ny_session_mask,
    session_reference_index,
)
from simulation.backtest import run_backtest
from simulation.environment.env import TradingEnv
from trading.execution import COST_US100

ROOT = repository_root(__file__)
DEFAULT_TICKS = Path("data/US100.cash_202412300105_202610162349.csv")
DEFAULT_BARS = Path("data/US100.cash_M1_202412300105_202610162349.csv")
DEFAULT_ALIGNMENT = Path(
    "evidence/research/fill_quote_source_alignment/selected_campaign_fill_quote_alignment.json"
)
DEFAULT_OUTPUT = Path("evidence/research/simulator_execution_parity/local_tick_action_trace.json")


def _time(value: Any) -> pd.Timestamp:
    parsed = pd.to_datetime(value, format="mixed", utc=True, errors="raise")
    return pd.Timestamp(parsed)


def _reported_quote(event: Mapping[str, Any], increment: float) -> tuple[float, float] | None:
    """Return a source-verified bid/ask pair from a unique full quote group."""
    group = event.get("timestamp_group")
    if not isinstance(group, Mapping):
        return None
    if (
        group.get("raw_rows_at_timestamp") != 1
        or not group.get("first_valid_quote_exists")
        or group.get("first_valid_bid_carried")
        or group.get("first_valid_ask_carried")
        or group.get("changed_quote_within_timestamp")
    ):
        return None
    event_time = _time(event.get("event_time_utc"))
    if _time(group.get("source_timestamp_utc")) != event_time:
        return None
    bid = group.get("configured_grid_first_valid_bid")
    ask = group.get("configured_grid_first_valid_ask")
    if bid is None or ask is None:
        return None
    quote = float(bid), float(ask)
    if not (np.isfinite(quote).all() and quote[0] > 0.0 and quote[1] >= quote[0]):
        return None
    raw_bid, raw_ask = (
        group.get("stable_parser_first_valid_bid"),
        group.get("stable_parser_first_valid_ask"),
    )
    if raw_bid is None or raw_ask is None:
        return None
    expected = np.asarray([float(raw_bid), float(raw_ask)], dtype=float)
    grid_quote = np.asarray(quote, dtype=float)
    if not np.all(np.isfinite(expected)) or increment <= 0.0 or not np.isfinite(increment):
        return None
    # Source report applies the configured half-away price grid. The returned
    # values are checked against the report's own configured-grid fields.
    if not np.allclose(grid_quote / increment, np.round(grid_quote / increment), atol=1e-8):
        return None
    return quote


def _select_event_pair(
    alignment: Mapping[str, Any],
    bars: pd.DataFrame,
    book: TickBook,
    *,
    timezone: str,
    max_hold_minutes: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Select an entry/exit quote pair that the current TickBook resolves exactly."""
    grid_info = alignment.get("price_grid_application") or {}
    increment = float(grid_info.get("increment", 0.0))
    if increment <= 0.0:
        raise ValueError("alignment report has no valid configured price-grid increment")

    bar_index = pd.DatetimeIndex(bars.index)
    if bar_index.tz is None:
        bar_index = bar_index.tz_localize(timezone)
    decision_index = (
        bar_index[bars["session"].eq("ny").to_numpy()] if "session" in bars else bar_index
    )
    candidates: list[dict[str, Any]] = []
    for raw_event in alignment.get("events", []):
        if not isinstance(raw_event, Mapping):
            continue
        quote = _reported_quote(raw_event, increment)
        if quote is None:
            continue
        order_time_value = raw_event.get("order_submission_time_utc")
        event_time_value = raw_event.get("event_time_utc")
        if not order_time_value or not event_time_value:
            continue
        order_time = _time(order_time_value).tz_convert(timezone)
        event_time = _time(event_time_value)
        decision_time = order_time - pd.Timedelta(minutes=1)
        if (
            order_time != order_time.floor("min")
            or order_time not in bar_index
            or decision_time not in decision_index
        ):
            continue
        resolved = book.execution_quote_event_at(order_time)
        if resolved is None:
            continue
        resolved_time, resolved_bid, resolved_ask = resolved
        if (
            resolved_time != event_time
            or not np.isclose(resolved_bid, quote[0], rtol=0.0, atol=1e-6)
            or not np.isclose(resolved_ask, quote[1], rtol=0.0, atol=1e-6)
        ):
            continue
        direction = int(raw_event.get("direction", 0) or 0)
        if direction not in (-1, 1):
            continue
        required_side = str(raw_event.get("required_quote_side", ""))
        expected_entry_side = "ask" if direction == 1 else "bid"
        if (
            str(raw_event.get("event_type", "")).lower() == "open"
            and required_side != expected_entry_side
        ):
            continue
        candidates.append(
            {
                **dict(raw_event),
                "_order_time": order_time,
                "_event_time": event_time,
                "_quote": quote,
                "_direction": direction,
            }
        )

    entries = [event for event in candidates if str(event.get("event_type", "")).lower() == "open"]
    entries.sort(key=lambda event: event["_order_time"])
    for entry in entries:
        direction = int(entry["_direction"])
        exit_side = "bid" if direction == 1 else "ask"
        for exit_event in candidates:
            hold = (exit_event["_order_time"] - entry["_order_time"]).total_seconds() / 60.0
            if not 2 <= hold <= max_hold_minutes:
                continue
            if exit_event["_order_time"].date() != entry["_order_time"].date():
                continue
            if str(exit_event.get("required_quote_side", "")) != exit_side:
                continue
            if exit_event["_order_time"] <= entry["_order_time"]:
                continue
            return entry, exit_event
    raise ValueError(
        "no same-session event pair matched unique full source quotes and current TickBook"
    )


def _select_event_pairs(
    alignment: Mapping[str, Any],
    bars: pd.DataFrame,
    book: TickBook,
    *,
    timezone: str,
    max_hold_minutes: int,
    max_pairs: int,
    max_pairs_per_stratum: int = 1,
    start_month: str | None = None,
    end_month: str | None = None,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Select quality-screened source pairs across months and both directions.

    Pair selection uses timestamp-group quality and TickBook resolution only;
    it does not rank or filter pairs by reported PnL. A bounded number of pairs
    per month/direction stratum is selected, and no source event is reused.
    """
    if max_pairs < 1 or max_pairs_per_stratum < 1:
        raise ValueError("max_pairs and max_pairs_per_stratum must be positive")
    for name, value in (("start_month", start_month), ("end_month", end_month)):
        if value is not None and (len(value) != 7 or value[4] != "-"):
            raise ValueError(f"{name} must use YYYY-MM format")
    if start_month is not None and end_month is not None and start_month > end_month:
        raise ValueError("start_month must not be later than end_month")
    raw_events = alignment.get("events", [])
    event_keys: dict[int, str] = {}
    for index, event in enumerate(raw_events):
        if not isinstance(event, Mapping):
            continue
        source = str(event.get("event_ledger_source", ""))
        event_id = event.get("event_id")
        event_keys[id(event)] = (
            f"{source}::event:{event_id}" if event_id is not None else f"row:{index}"
        )
    months = sorted(
        {
            _time(event["event_time_utc"]).strftime("%Y-%m")
            for event in raw_events
            if isinstance(event, Mapping)
            and event.get("event_time_utc")
            and str(event.get("event_type", "")).lower() == "open"
            and (
                start_month is None
                or _time(event["event_time_utc"]).strftime("%Y-%m") >= start_month
            )
            and (end_month is None or _time(event["event_time_utc"]).strftime("%Y-%m") <= end_month)
        }
    )
    used_events: set[str] = set()
    selected: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for month in months:
        for direction in (1, -1):
            for _ in range(max_pairs_per_stratum):
                if len(selected) >= max_pairs:
                    return selected
                stratum_events = []
                for event in raw_events:
                    if not isinstance(event, Mapping) or event_keys[id(event)] in used_events:
                        continue
                    event_time = event.get("event_time_utc")
                    if not event_time or _time(event_time).strftime("%Y-%m") != month:
                        continue
                    if (
                        str(event.get("event_type", "")).lower() == "open"
                        and int(event.get("direction", 0) or 0) != direction
                    ):
                        continue
                    stratum_event = dict(event)
                    stratum_event["_source_event_key"] = event_keys[id(event)]
                    stratum_events.append(stratum_event)
                try:
                    pair = _select_event_pair(
                        {**alignment, "events": stratum_events},
                        bars,
                        book,
                        timezone=timezone,
                        max_hold_minutes=max_hold_minutes,
                    )
                except ValueError:
                    break
                selected.append(pair)
                used_events.update(str(event["_source_event_key"]) for event in pair)
    return selected


def _timestamp_text(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    return pd.Timestamp(value).isoformat()


def _json_safe(value: Any) -> Any:
    """Normalize NumPy scalars and missing/non-finite values for strict JSON."""
    if value is None or value is pd.NA:
        return None
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def _trade_event(event: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: (
            _timestamp_text(event.get(key)) if key.endswith("time") else _json_safe(event.get(key))
        )
        for key in (
            "type",
            "direction",
            "price",
            "pnl",
            "reason",
            "time",
            "fill_quote_source",
            "decision_bar_time",
            "decision_time",
            "order_submission_time",
            "fill_time",
            "actual_tick_time",
            "execution_arrival_time",
            "lots",
            "size",
            "net_pnl",
        )
        if key in event
    }


def replay_local_tick_trace(
    *,
    tickbook: TickBook,
    bars: pd.DataFrame,
    entry_order_time: pd.Timestamp,
    exit_order_time: pd.Timestamp,
    direction: int,
    initial_balance: float = 50_000.0,
) -> dict[str, Any]:
    """Run a single controlled order pair in both simulator implementations."""
    if direction not in (-1, 1):
        raise ValueError("direction must be -1 or 1")
    if not entry_order_time < exit_order_time:
        raise ValueError("exit_order_time must follow entry_order_time")
    if entry_order_time not in bars.index or exit_order_time not in bars.index:
        raise ValueError("both order times must lie on the supplied M1 bar index")

    entry_signal_time = entry_order_time - pd.Timedelta(minutes=1)
    exit_signal_time = exit_order_time - pd.Timedelta(minutes=1)
    env_entry_action = 1 if direction == 1 else 10
    backtest_entry_action = direction
    start_time = entry_signal_time - pd.Timedelta(minutes=1)
    stop = exit_order_time + pd.Timedelta(minutes=1)
    window = bars.loc[start_time:stop].copy()
    if len(window) < 4:
        raise ValueError("local M1 trace is too short for entry and exit transitions")
    if "session_id" not in window:
        window = add_session_id(window)
    if "session" in window:
        eligible_decisions = window.index[window["session"].eq("ny")]
        if (
            entry_signal_time not in eligible_decisions
            or exit_signal_time not in eligible_decisions
        ):
            raise ValueError("both decision bars must be in the supplied NY session")
    else:
        # Direct synthetic replays may provide a preselected session without labels.
        window["session"] = "ny"
    # Use only the current completed bar for the controlled protective offsets.
    features = pd.DataFrame(
        {
            "last_swing_low": window["low"] - 50.0,
            "last_swing_high": window["high"] + 50.0,
        },
        index=window.index,
    )
    cost_model = COST_US100
    env = TradingEnv(
        window,
        features,
        obs_window=1,
        initial_balance=initial_balance,
        cost_model=cost_model,
        risk_frac_range=(0.001, 0.001),
        rr_ratio_range=(1.0, 1.0),
        min_lot=0.01,
        max_lot=1.0,
        contract_size=1.0,
        swing_buffer_pts=0.0,
        max_loss_per_trade_usd=1_000.0,
        block_overnight=False,
        episodic=False,
        reward_mode="pnl",
        tickbook=tickbook,
        tick_execution_required=True,
        session_timezone="America/Chicago",
        source_clock_model="native",
    )
    env.reset(seed=7)
    while env._bar_time(env.step_idx) <= exit_signal_time:
        decision_time = env._bar_time(env.step_idx)
        action = (
            env_entry_action
            if decision_time == entry_signal_time
            else 19
            if decision_time == exit_signal_time
            else 0
        )
        env.step(action)

    policy_rows = window.iloc[1:-1]
    policy_times = pd.DatetimeIndex(policy_rows.index[policy_rows["session"].eq("ny")])
    policy_index = 0

    def policy(_observation: np.ndarray[Any, Any]) -> int:
        nonlocal policy_index
        decision_time = policy_times[policy_index]
        policy_index += 1
        return (
            backtest_entry_action
            if decision_time == entry_signal_time
            else 19
            if decision_time == exit_signal_time
            else 0
        )

    result = run_backtest(
        window,
        features,
        policy,
        obs_window=1,
        cost_model=cost_model,
        initial_balance=initial_balance,
        max_loss_per_trade_usd=1_000.0,
        tickbook=tickbook,
        tick_execution_required=True,
        block_overnight=False,
        hold_on_zero=True,
        exit_action=19,
        use_structure_sl_tp=True,
        swing_buffer_pts=0.0,
        risk_frac=0.001,
        rr_ratio=1.0,
        min_lot=0.01,
        max_lot=1.0,
        contract_size=1.0,
        session_timezone="America/Chicago",
        source_clock_model="native",
    )
    # The environment's order_fill row is an annotation for the same fill
    # that its open row records. Both engines stamp actual position fills.
    env_events = [
        event
        for event in env.trade_log
        if event.get("type") != "order_fill" and pd.notna(event.get("fill_time"))
    ]
    backtest_events = [
        event
        for event in result["trades"].to_dict(orient="records")
        if event.get("type") != "order_fill" and pd.notna(event.get("fill_time"))
    ]
    actual_events = {"environment": env_events, "backtest": backtest_events}
    expected_schedule = [("open", entry_order_time), ("close", exit_order_time)]
    if any(
        [(event["type"], pd.Timestamp(event.get("order_submission_time"))) for event in events]
        != expected_schedule
        for events in actual_events.values()
    ):
        return {
            "trace_passed": False,
            "direction": direction,
            "entry_order_time": entry_order_time.isoformat(),
            "exit_order_time": exit_order_time.isoformat(),
            "schedule_miss": {
                "expected_event_types": ["open", "close"],
                "actual_events": {
                    engine: [_trade_event(event) for event in events]
                    for engine, events in actual_events.items()
                },
            },
        }
    env_open, env_close = env_events
    backtest_open, backtest_close = backtest_events
    comparisons = []
    for env_event, backtest_event in zip(env_events, backtest_events, strict=True):
        comparisons.append(
            {
                "same_tick_source": env_event["fill_quote_source"]
                == backtest_event["fill_quote_source"]
                == "tick",
                "same_fill_timestamp": pd.Timestamp(env_event["fill_time"]).tz_convert("UTC")
                == pd.Timestamp(backtest_event["fill_time"]).tz_convert("UTC"),
                "same_price": bool(
                    np.isclose(env_event["price"], backtest_event["price"], rtol=0.0, atol=1e-8)
                ),
                "same_source_decision_bar": pd.Timestamp(env_event["decision_bar_time"]).tz_convert(
                    "UTC"
                )
                == pd.Timestamp(backtest_event["decision_bar_time"]).tz_convert("UTC"),
                "same_order_submission_time": pd.Timestamp(
                    env_event["order_submission_time"]
                ).tz_convert("UTC")
                == pd.Timestamp(backtest_event["order_submission_time"]).tz_convert("UTC"),
            }
        )
    close_pnl_match = bool(np.isclose(env_close["pnl"], backtest_close["pnl"], rtol=0.0, atol=1e-8))
    balance_match = bool(
        np.isclose(env.account.balance, result["account"].balance, rtol=0.0, atol=1e-8)
    )
    return {
        "trace_passed": all(all(check.values()) for check in comparisons)
        and close_pnl_match
        and balance_match,
        "initial_balance": initial_balance,
        "direction": direction,
        "environment_entry_action": env_entry_action,
        "backtest_entry_action": backtest_entry_action,
        "entry_order_time": entry_order_time.isoformat(),
        "exit_order_time": exit_order_time.isoformat(),
        "hold_minutes": (exit_order_time - entry_order_time).total_seconds() / 60.0,
        "entry": {"environment": _trade_event(env_open), "backtest": _trade_event(backtest_open)},
        "exit": {"environment": _trade_event(env_close), "backtest": _trade_event(backtest_close)},
        "entry_and_exit_comparisons": comparisons,
        "close_pnl_match": close_pnl_match,
        "environment_close_pnl": float(env_close["pnl"]),
        "backtest_close_pnl": float(backtest_close["pnl"]),
        "ending_balance_match": balance_match,
        "environment_ending_balance": float(env.account.balance),
        "backtest_ending_balance": float(result["account"].balance),
        "starting_balance": float(initial_balance),
        "execution_settings": {
            "tick_execution_required": True,
            "randomized_fill_latency_ms": 0.0,
            "max_tick_quote_wait_ms": 60_000,
            "execution_seed": 7,
            "hold_on_zero": True,
            "exit_action": 19,
        },
        "cost_model": {
            "spread_points": cost_model.spread_points,
            "point_size": cost_model.point_size,
            "commission_per_lot": cost_model.commission_per_lot,
            "price_value_per_point": cost_model.point_value,
        },
    }


def build_report(
    tick_path: Path,
    bars_path: Path,
    alignment_path: Path,
    *,
    timezone: str | None = None,
    max_hold_minutes: int = 60,
    max_trace_pairs: int = 24,
    max_pairs_per_stratum: int = 1,
    start_month: str | None = None,
    end_month: str | None = None,
) -> dict[str, Any]:
    """Build source-verified quote pairs and replay each through both engines."""
    cfg = load_config()
    source_timezone = timezone or str(cfg.data.tz)
    source_clock_model = str(cfg.data.get("timestamp_clock", "native"))
    session_timezone = str(cfg.session.tz)
    train_start = pd.Timestamp(str(cfg.data.split.train_start))
    train_end_exclusive = min(
        inclusive_date_exclusive_end(str(cfg.data.split.train_end), None),
        pd.Timestamp(str(cfg.data.split.test_start)),
    )
    alignment = json.loads(alignment_path.read_text(encoding="utf-8"))
    join_timezone = alignment.get("source_timezone_used_for_timestamp_join")
    if source_clock_model == "europe_helsinki":
        expected_join_timezone = "Europe/Helsinki"
    elif source_clock_model == "native":
        expected_join_timezone = source_timezone
    else:
        raise ValueError(f"quote alignment does not support source clock {source_clock_model!r}")
    if join_timezone != expected_join_timezone:
        raise ValueError(
            f"quote-alignment timestamp join timezone must be {expected_join_timezone!r} "
            f"for {source_clock_model!r}, got {join_timezone!r}"
        )
    recorded_hash = alignment.get("tick_source_sha256")
    current_hash = file_sha256(tick_path)
    if recorded_hash != current_hash:
        raise ValueError("tick source hash does not match the quote-alignment evidence")
    bars_frame = load_bars(
        bars_path, start_inclusive=train_start, end_exclusive=train_end_exclusive
    )
    bar_index = pd.DatetimeIndex(bars_frame.index)
    if bar_index.tz is None:
        bar_index = bar_index.tz_localize(source_timezone)
    bar_index = session_reference_index(bar_index, source_clock_model).tz_convert(session_timezone)
    bars_frame.index = bar_index
    eligible = ny_session_mask(
        bar_index,
        start=str(cfg.session.start),
        end=str(cfg.session.end),
        session_tz=session_timezone,
    )
    bars_frame = add_session_labels(bars_frame, tz=session_timezone, ny_end=str(cfg.session.end))
    bars_frame.loc[~eligible & bars_frame["session"].eq("ny"), "session"] = "closed"
    bars_frame.loc[eligible, "session"] = "ny"
    bars_frame = add_session_id(bars_frame)
    grid = float((alignment.get("price_grid_application") or {}).get("increment", 0.0))
    if not np.isfinite(grid) or grid <= 0.0:
        raise ValueError("quote-alignment evidence lacks a valid price grid")
    book = build_tick_book(
        tick_path,
        tz=source_timezone,
        price_grid_increment=grid,
        start_inclusive=train_start.date().isoformat(),
        end_exclusive=train_end_exclusive,
        source_clock_model=source_clock_model,
    )
    pairs = _select_event_pairs(
        alignment,
        bars_frame,
        book,
        timezone=session_timezone,
        max_hold_minutes=max_hold_minutes,
        max_pairs=max_trace_pairs,
        max_pairs_per_stratum=max_pairs_per_stratum,
        start_month=start_month,
        end_month=end_month,
    )
    if not pairs:
        raise ValueError("no monthly direction strata matched unique full source quotes")

    def evidence_event(event: Mapping[str, Any]) -> dict[str, Any]:
        group = event["timestamp_group"]
        return {
            "event_ledger_source": event.get("event_ledger_source"),
            "event_id": event.get("event_id"),
            "event_type": event.get("event_type"),
            "reported_order_submission_time_utc": event.get("order_submission_time_utc"),
            "reported_tick_time_utc": event.get("event_time_utc"),
            "direction": int(event["_direction"]),
            "required_quote_side": event.get("required_quote_side"),
            "bid": float(event["_quote"][0]),
            "ask": float(event["_quote"][1]),
            "raw_rows_at_timestamp": group.get("raw_rows_at_timestamp"),
            "bid_carried": bool(group.get("first_valid_bid_carried")),
            "ask_carried": bool(group.get("first_valid_ask_carried")),
            "changed_quote_within_timestamp": bool(group.get("changed_quote_within_timestamp")),
        }

    pair_reports = []
    for pair_index, (entry, exit_event) in enumerate(pairs, start=1):
        replay = replay_local_tick_trace(
            tickbook=book,
            bars=bars_frame,
            entry_order_time=entry["_order_time"],
            exit_order_time=exit_event["_order_time"],
            direction=int(entry["_direction"]),
        )
        pair_reports.append(
            {
                "pair_id": f"local_tick_pair_{pair_index:03d}",
                "stratum_month": entry["_event_time"].strftime("%Y-%m"),
                "direction": int(entry["_direction"]),
                "historical_quote_evidence": {
                    "alignment_tool_sha256": alignment.get("analysis_tool_sha256"),
                    "price_grid_increment": grid,
                    "entry": evidence_event(entry),
                    "exit": evidence_event(exit_event),
                },
                "replay": replay,
            }
        )

    directions = {pair["direction"] for pair in pair_reports}
    return {
        "schema_version": "simulator-local-tick-action-trace-set-v1",
        "trace_passed": all(pair["replay"]["trace_passed"] for pair in pair_reports),
        "trace_pair_count": len(pair_reports),
        "months_covered": sorted({pair["stratum_month"] for pair in pair_reports}),
        "directions_covered": sorted(directions),
        "source_event_reuse": False,
        "selection_rule": (
            f"At most {max_pairs_per_stratum} pairs per source month and direction, selected in "
            "chronological order from the training period using NY decision bars and unique "
            "complete quote groups reproduced by the current "
            f"TickBook within {start_month or 'all'} through {end_month or 'all'}; no PnL-based "
            "selection and no source event reused."
        ),
        "claim_scope": (
            "Controlled one-entry/one-exit action replays across source month/direction strata "
            "using current local US100 M1 bars and TickBook quotes matched to unique, complete "
            "source timestamp groups in the recorded local quote-alignment scan. These are not "
            "historical policy replays or provider-clock validation."
        ),
        "timezone_label": session_timezone,
        "source_timezone_carrier": source_timezone,
        "source_clock_model": source_clock_model,
        "alignment_join_timezone": join_timezone,
        "training_source_dates": {
            "start_inclusive": train_start.date().isoformat(),
            "end_exclusive": train_end_exclusive.date().isoformat(),
        },
        "timezone_limitation": "Configured local timestamp interpretation; no external clock authority assessed.",
        "inputs": {
            "tick_path": str(tick_path),
            "tick_sha256": current_hash,
            "m1_bars_path": str(bars_path),
            "m1_bars_sha256": file_sha256(bars_path),
            "quote_alignment_report_path": str(alignment_path),
            "quote_alignment_report_sha256": file_sha256(alignment_path),
        },
        "generator": {
            "path": str(Path(__file__).resolve()),
            "sha256": file_sha256(Path(__file__)),
        },
        "trace_pairs": pair_reports,
        "limitations": [
            "The action sequence is controlled and does not reproduce a campaign policy.",
            "The quote scan preserves the configured parser's per-side carry and price-grid rules.",
            "The data's timestamp ties do not establish within-tie source chronology.",
            "Market impact and broker-specific effects are not modeled.",
        ],
    }


def main() -> None:
    """Parse command-line arguments and write the trace report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticks-csv", type=Path, default=ROOT / DEFAULT_TICKS)
    parser.add_argument("--bars-csv", type=Path, default=ROOT / DEFAULT_BARS)
    parser.add_argument("--alignment-report", type=Path, default=ROOT / DEFAULT_ALIGNMENT)
    parser.add_argument("--timezone", help="source wall-clock carrier override (default: data.tz)")
    parser.add_argument("--max-hold-minutes", type=int, default=60)
    parser.add_argument("--max-trace-pairs", type=int, default=24)
    parser.add_argument("--max-pairs-per-stratum", type=int, default=1)
    parser.add_argument("--start-month", help="inclusive source month in YYYY-MM form")
    parser.add_argument("--end-month", help="inclusive source month in YYYY-MM form")
    parser.add_argument("--out", type=Path, default=ROOT / DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = build_report(
        args.ticks_csv,
        args.bars_csv,
        args.alignment_report,
        timezone=args.timezone,
        max_hold_minutes=args.max_hold_minutes,
        max_trace_pairs=args.max_trace_pairs,
        max_pairs_per_stratum=args.max_pairs_per_stratum,
        start_month=args.start_month,
        end_month=args.end_month,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(args.out, report)
    print(json.dumps({"out": str(args.out), "trace_passed": report["trace_passed"]}))
    if not report["trace_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
