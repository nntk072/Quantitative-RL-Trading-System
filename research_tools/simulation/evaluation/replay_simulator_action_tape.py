"""Replay one frozen action tape through TradingEnv and the event backtest."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from research_tools.simulation.evaluation.action_tape import ActionTape

from simulation.backtest import run_backtest
from simulation.environment.env import TradingEnv


def _utc_index(index: pd.Index) -> pd.DatetimeIndex:
    if not isinstance(index, pd.DatetimeIndex) or index.tz is None:
        raise ValueError("bars must use a timezone-aware DatetimeIndex")
    utc = index.tz_convert("UTC")
    if not utc.is_monotonic_increasing or utc.has_duplicates:
        raise ValueError("bar timestamps must be strictly increasing and unique")
    return utc


def _action_for_engine(action: int | list[float]) -> int | np.ndarray[Any, Any]:
    return np.asarray(action, dtype=np.float32) if isinstance(action, list) else action


def _action_for_backtest(
    action: int | list[float],
    environment_kwargs: Mapping[str, Any],
    backtest_kwargs: Mapping[str, Any],
) -> int | np.ndarray[Any, Any]:
    if isinstance(action, list):
        return np.asarray(action, dtype=np.float32)
    if action in (0, 19):
        return action
    if not 1 <= action <= 18:
        raise ValueError(f"unsupported discrete environment action: {action}")
    offset = action - 1 if action <= 9 else action - 10
    direction = 1 if action <= 9 else -1
    risk_index, rr_index = divmod(offset, 3)
    risk_low, risk_high = environment_kwargs.get("risk_frac_range", (0.005, 0.02))
    rr_low, rr_high = environment_kwargs.get("rr_ratio_range", (1.0, 3.0))
    risk_levels = (risk_low, (risk_low + risk_high) / 2, risk_high)
    rr_levels = (rr_low, (rr_low + rr_high) / 2, rr_high)
    backtest_risk = backtest_kwargs.get("risk_frac")
    backtest_rr = backtest_kwargs.get("rr_ratio")
    if backtest_risk is None or not np.isclose(
        risk_levels[risk_index], float(backtest_risk), rtol=0.0, atol=1e-12
    ):
        raise ValueError(
            "frozen discrete action risk variant disagrees with the backtest risk_frac"
        )
    if backtest_rr is None or not np.isclose(
        rr_levels[rr_index], float(backtest_rr), rtol=0.0, atol=1e-12
    ):
        raise ValueError("frozen discrete action RR variant disagrees with the backtest rr_ratio")
    return direction


def _required_sha256(provenance: Mapping[str, Any], name: str) -> str:
    value = provenance.get(name)
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value.lower())
    ):
        raise ValueError(f"run provenance requires a 64-character {name}")
    return value.lower()


def _validated_provenance(provenance: Mapping[str, Any]) -> dict[str, str]:
    if provenance.get("split") != "train":
        raise ValueError("action-tape simulator replay requires a train-only window")
    values = {
        "window_id": str(provenance.get("window_id", "")),
        "split": "train",
        "bars_sha256": _required_sha256(provenance, "bars_sha256"),
        "features_sha256": _required_sha256(provenance, "features_sha256"),
        "window_manifest_sha256": _required_sha256(provenance, "window_manifest_sha256"),
        "resolved_config_sha256": _required_sha256(provenance, "resolved_config_sha256"),
        "source_fingerprint": _required_sha256(provenance, "source_fingerprint"),
        "source_timezone": str(provenance.get("source_timezone", "")),
        "source_clock_model": str(provenance.get("source_clock_model", "")),
        "session_timezone": str(provenance.get("session_timezone", "")),
    }
    if not values["window_id"]:
        raise ValueError("run provenance requires a non-empty window_id")
    if not all(
        values[key] for key in ("source_timezone", "source_clock_model", "session_timezone")
    ):
        raise ValueError("run provenance requires source and session timezone details")
    return values


def _load_tapes(
    tape_path: Path,
    bars: pd.DataFrame,
    features: pd.DataFrame,
    environment_kwargs: Mapping[str, Any],
    backtest_kwargs: Mapping[str, Any],
    *,
    backtest_tape_path: Path | None = None,
) -> tuple[ActionTape, ActionTape, pd.DatetimeIndex]:
    utc_index = _utc_index(bars.index)
    if not bars.index.equals(features.index):
        raise ValueError("bars and features must have exactly aligned indices")
    environment_tape = ActionTape.load(tape_path)
    backtest_tape = ActionTape.load(backtest_tape_path or tape_path)
    times = pd.DatetimeIndex([timestamp for timestamp, _ in environment_tape.actions])
    positions = utc_index.get_indexer(times)
    if np.any(positions < 0):
        raise ValueError("every action timestamp must match an input bar")
    backtest_times = pd.DatetimeIndex([timestamp for timestamp, _ in backtest_tape.actions])
    backtest_positions = utc_index.get_indexer(backtest_times)
    if np.any(backtest_positions < 0):
        raise ValueError("every backtest action timestamp must match an input bar")
    obs_window = int(environment_kwargs.get("obs_window", 60))
    if int(backtest_kwargs.get("obs_window", 60)) != obs_window:
        raise ValueError("environment and backtest obs_window must match")
    if any(position < obs_window for position in positions) or any(
        position < obs_window or position >= len(bars) - 1 for position in backtest_positions
    ):
        raise ValueError("action timestamps must identify eligible decision bars")
    if "session" in bars and any(
        str(bars.iloc[int(position)]["session"]) != "ny"
        for position in np.concatenate((positions, backtest_positions))
    ):
        raise ValueError("action timestamps must identify NY-eligible decision bars")
    return environment_tape, backtest_tape, utc_index


def _validate_matched_settings(
    environment_kwargs: Mapping[str, Any],
    backtest_kwargs: Mapping[str, Any],
    seed: int,
    provenance: Mapping[str, Any],
) -> None:
    pairs = {
        "initial_balance": ("initial_balance", "initial_balance", 100_000.0),
        "cost_model": ("cost_model", "cost_model", None),
        "guardrail_kwargs": ("guardrail_kwargs", "guardrail_kwargs", None),
        "min_lot": ("min_lot", "min_lot", 0.01),
        "max_lot": ("max_lot", "max_lot", 100.0),
        "contract_size": ("contract_size", "contract_size", 1.0),
        "max_loss_per_trade_usd": (
            "max_loss_per_trade_usd",
            "max_loss_per_trade_usd",
            None,
        ),
        "block_overnight": ("block_overnight", "block_overnight", True),
        "tick_execution_required": ("tick_execution_required", "tick_execution_required", False),
        "randomized_fill_latency_ms": (
            "randomized_fill_latency_ms",
            "randomized_fill_latency_ms",
            0.0,
        ),
    }
    for name, (environment_key, backtest_key, default) in pairs.items():
        left = environment_kwargs.get(environment_key, default)
        right = backtest_kwargs.get(backtest_key, default)
        if left != right:
            raise ValueError(f"environment and backtest {name} settings must match")
    environment_risk = environment_kwargs.get("risk_frac_range", (0.005, 0.02))
    backtest_risk = backtest_kwargs.get("policy_risk_frac_range")
    if backtest_risk is None:
        risk = backtest_kwargs.get("risk_frac")
        if risk is None:
            raise ValueError("backtest risk_frac or policy_risk_frac_range must be explicit")
        backtest_risk = (risk, risk)
    if tuple(environment_risk) != tuple(backtest_risk):
        raise ValueError("environment and backtest risk fraction settings must match")
    environment_rr = environment_kwargs.get("rr_ratio_range", (1.0, 3.0))
    backtest_rr = backtest_kwargs.get("policy_rr_ratio_range")
    if backtest_rr is None:
        ratio = backtest_kwargs.get("rr_ratio", 2.0)
        backtest_rr = (ratio, ratio)
    if tuple(environment_rr) != tuple(backtest_rr):
        raise ValueError("environment and backtest RR settings must match")
    if backtest_kwargs.get("execution_seed", 0) != seed:
        raise ValueError("environment reset seed and backtest execution_seed must match")
    environment_tickbook = environment_kwargs.get("tickbook")
    backtest_tickbook = backtest_kwargs.get("tickbook")
    if environment_tickbook is not backtest_tickbook:
        raise ValueError("environment and backtest must share the same TickBook instance")
    if environment_tickbook is not None:
        _required_sha256(provenance, "ticks_sha256")


def _run_environment(
    bars: pd.DataFrame,
    features: pd.DataFrame,
    tape: ActionTape,
    utc_index: pd.DatetimeIndex,
    kwargs: Mapping[str, Any],
    seed: int,
) -> tuple[TradingEnv, list[str], list[dict[str, Any]], bool, bool]:
    environment = TradingEnv(bars=bars, features=features, **dict(kwargs))
    environment.reset(seed=seed)
    environment_times: list[str] = []
    environment_account_rows: list[dict[str, Any]] = []
    terminated, truncated = False, False
    for expected_time, _ in tape.actions:
        actual_time = utc_index[int(environment.step_idx)].to_pydatetime()
        if actual_time != expected_time:
            raise ValueError(
                "environment decision timestamp mismatch: "
                f"expected {expected_time.isoformat()}, got {actual_time.isoformat()}"
            )
        action = tape.next_action(actual_time)
        _, reward, terminated, truncated, info = environment.step(_action_for_engine(action))
        snapshot = info.get("account_state_snapshot")
        if not isinstance(snapshot, Mapping):
            raise ValueError("environment step is missing its account_state_snapshot")
        environment_account_rows.append(
            {
                "decision_bar_time_utc": actual_time.isoformat(),
                "account_state": dict(snapshot),
                "reward": float(reward),
                "reward_parts": dict(info.get("reward_parts", {})),
                "terminated": bool(terminated),
                "truncated": bool(truncated),
            }
        )
        environment_times.append(actual_time.isoformat())
        if (terminated or truncated) and len(environment_times) != len(tape.actions):
            raise ValueError("environment terminated before consuming the full action tape")
    tape.assert_fully_consumed()
    return (
        environment,
        environment_times,
        environment_account_rows,
        bool(terminated),
        bool(truncated),
    )


def _snapshot_time(value: Any) -> str | None:
    if value is None:
        return None
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        return None
    return timestamp.tz_convert("UTC").isoformat()


def _compare_account_state_rows(
    environment_rows: list[dict[str, Any]],
    backtest_trace: Any,
    *,
    backtest_policy_decision_times_utc: set[str] | None = None,
) -> tuple[bool, list[dict[str, Any]]]:
    if not isinstance(backtest_trace, pd.DataFrame) or backtest_trace.empty:
        return False, [{"mismatches": ["backtest_account_state_trace_missing"]}]

    trace_by_time: dict[str, dict[str, Any]] = {}
    for raw_row in backtest_trace.to_dict(orient="records"):
        row = {str(key): value for key, value in raw_row.items()}
        time = _snapshot_time(row.get("decision_time"))
        if time is not None:
            if time in trace_by_time:
                return False, [
                    {"decision_time_utc": time, "mismatches": ["duplicate_backtest_time"]}
                ]
            trace_by_time[time] = row

    ignored_fields = {"backtest_bar_index", "state_phase", "trade_event_count"}
    backtest_decision_times = (
        None
        if backtest_policy_decision_times_utc is None
        else {
            normalized
            for value in backtest_policy_decision_times_utc
            if (normalized := _snapshot_time(value)) is not None
        }
    )
    comparisons: list[dict[str, Any]] = []
    for environment_row in environment_rows:
        environment_snapshot = environment_row["account_state"]
        time = _snapshot_time(environment_snapshot.get("decision_time"))
        backtest_snapshot = None if time is None else trace_by_time.get(time)
        mismatches: list[str] = []
        if time is None:
            mismatches.append("environment_decision_time_invalid")
        elif backtest_snapshot is None:
            mismatches.append("backtest_decision_time_missing")
        else:
            phase_is_comparable = backtest_decision_times is None or time in backtest_decision_times
            if phase_is_comparable and environment_snapshot.get(
                "state_phase"
            ) != backtest_snapshot.get("state_phase"):
                mismatches.append("state_phase")
            fields = sorted((set(environment_snapshot) | set(backtest_snapshot)) - ignored_fields)
            for field in fields:
                left = environment_snapshot.get(field)
                right = backtest_snapshot.get(field)
                if field == "state_phase" and not phase_is_comparable:
                    equal = True
                elif field in {"decision_time", "valuation_time"} or field in {
                    "pending_order_submission_time",
                    "pending_order_expiry_time",
                    "pending_order_scheduled_fill_time",
                }:
                    equal = _snapshot_time(left) == _snapshot_time(right)
                elif field == "pending_order_id" or field == "pending_order_decision_id":
                    equal = (left is None) == (right is None)
                elif pd.isna(left) and pd.isna(right):
                    equal = True
                elif isinstance(left, (int, float, np.integer, np.floating)) and isinstance(
                    right, (int, float, np.integer, np.floating)
                ):
                    equal = bool(np.isclose(left, right, rtol=0.0, atol=1e-8))
                else:
                    equal = left == right
                if not equal:
                    mismatches.append(field)
        comparisons.append(
            {
                "decision_bar_time_utc": environment_row["decision_bar_time_utc"],
                "decision_time_utc": time,
                "environment_state_phase": environment_snapshot.get("state_phase"),
                "backtest_state_phase": (
                    None if backtest_snapshot is None else backtest_snapshot.get("state_phase")
                ),
                "trade_event_count_pair": (
                    environment_snapshot.get("trade_event_count"),
                    None
                    if backtest_snapshot is None
                    else backtest_snapshot.get("trade_event_count"),
                ),
                "environment_account_state": _json_safe(environment_snapshot),
                "backtest_account_state": (
                    None if backtest_snapshot is None else _json_safe(backtest_snapshot)
                ),
                "environment_reward": environment_row["reward"],
                "environment_reward_parts": environment_row["reward_parts"],
                "mismatches": mismatches,
            }
        )
    return all(not row["mismatches"] for row in comparisons), comparisons


def _run_backtest(
    bars: pd.DataFrame,
    features: pd.DataFrame,
    tape: ActionTape,
    kwargs: Mapping[str, Any],
    environment_kwargs: Mapping[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    calls = 0

    def tape_policy(_observation: Any) -> int | np.ndarray[Any, Any]:
        nonlocal calls
        if calls >= len(tape.actions):
            raise ValueError("backtest requested more actions than the frozen tape contains")
        action = _action_for_backtest(
            tape.next_action(tape.actions[calls][0]), environment_kwargs, kwargs
        )
        calls += 1
        return action

    result = run_backtest(bars, features, tape_policy, **dict(kwargs))
    tape.assert_fully_consumed()
    decision_frame = result["policy_decisions"]
    times = [
        pd.Timestamp(value).tz_convert("UTC").isoformat()
        for value in decision_frame.get("decision_bar_time", pd.Series(dtype=object)).tolist()
    ]
    expected = [timestamp.isoformat() for timestamp, _ in tape.actions]
    if times != expected:
        raise ValueError("backtest decision timestamps differ from the frozen action tape")
    return result, times


def _lifecycle(events: list[dict[str, Any]]) -> list[str]:
    return [
        str(event["type"])
        for event in events
        if event.get("type") in {"open", "close", "forced_close"}
    ]


def _canonical_order_event(event: Mapping[str, Any]) -> dict[str, Any]:
    event_type = str(event.get("type", ""))

    def optional_text(key: str) -> Any:
        value = event.get(key)
        missing = pd.isna(value)
        if value is None or (isinstance(missing, (bool, np.bool_)) and missing):
            return None
        return value

    def optional_number(key: str) -> Any:
        value = event.get(key)
        if isinstance(value, (int, float, np.integer, np.floating)) and not np.isfinite(value):
            return None
        return value

    common = {
        "type": event_type,
        "direction": event.get("direction"),
        "trade_setup_candidate_id": optional_number("trade_setup_candidate_id"),
        "trade_setup_source_event_id": event.get("trade_setup_source_event_id"),
        "reason": optional_text("reason") or optional_text("entry_rejection_reason"),
    }
    if event_type == "order_submit":
        common.update(
            {
                "decision_bar_time": _event_time_utc(event, "decision_bar_time"),
                "decision_time": _event_time_utc(event, "decision_time"),
                "order_submission_time": _event_time_utc(event, "order_submission_time"),
                "expiry_time": _event_time_utc(event, "expiry_time"),
                "order_type": event.get("order_type"),
                "limit_price": optional_number("limit_price"),
                "limit_offset_atr": optional_number("limit_offset_atr"),
                "ttl_bars": optional_number("ttl_bars"),
            }
        )
    elif event_type == "order_fill":
        common.update(
            {
                "order_submission_time": _event_time_utc(event, "order_submission_time"),
                "time": _event_time_utc(event, "fill_time", "actual_tick_time", "time"),
                "order_type": event.get("order_type"),
                "limit_price": optional_number("limit_price"),
                "bid": optional_number("bid"),
                "ask": optional_number("ask"),
                "price": optional_number("price"),
            }
        )
    elif event_type == "order_cancel":
        common.update(
            {
                "decision_time": _event_time_utc(event, "decision_time"),
                "order_submission_time": _event_time_utc(event, "order_submission_time"),
                "expiry_time": _event_time_utc(event, "expiry_time"),
                "order_type": event.get("order_type"),
                "limit_price": optional_number("limit_price"),
            }
        )
    elif event_type == "reject":
        common.update(
            {
                "decision_bar_time": _event_time_utc(event, "decision_bar_time", "time"),
                "decision_time": _event_time_utc(event, "decision_time"),
            }
        )
    return common


def _compare_order_events(
    environment_events: list[dict[str, Any]], backtest_events: list[dict[str, Any]]
) -> tuple[bool, list[str]]:
    order_event_types = {"order_submit", "order_fill", "order_cancel", "reject"}
    environment = [
        _canonical_order_event(event)
        for event in environment_events
        if event.get("type") in order_event_types
        and (event.get("type") != "order_fill" or event.get("order_type") == "limit")
    ]
    backtest = [
        _canonical_order_event(event)
        for event in backtest_events
        if event.get("type") in order_event_types
        and (event.get("type") != "order_fill" or event.get("order_type") == "limit")
    ]
    mismatches: list[str] = []
    if len(environment) != len(backtest):
        mismatches.append("order_event_count")
    for index, (left, right) in enumerate(zip(environment, backtest, strict=False)):
        if left.get("type") != right.get("type"):
            mismatches.append(f"event_type[{index}]")
        for field in sorted(set(left) | set(right)):
            if field not in left or field not in right:
                mismatches.append(f"{left.get('type')}[{index}].{field}")
                continue
            left_value = left[field]
            right_value = right[field]
            if isinstance(left_value, (int, float, np.integer, np.floating)) and isinstance(
                right_value, (int, float, np.integer, np.floating)
            ):
                equal = bool(np.isclose(left_value, right_value, rtol=0.0, atol=1e-8))
            else:
                equal = left_value == right_value
            if not equal:
                mismatches.append(f"{left['type']}[{index}].{field}")
    return not mismatches, mismatches


def _event_time_utc(event: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = event.get(key)
        missing = pd.isna(value)
        if value is None or (isinstance(missing, (bool, np.bool_)) and missing):
            continue
        timestamp = pd.Timestamp(value)
        if timestamp.tzinfo is None:
            return None
        return timestamp.tz_convert("UTC").isoformat()
    return None


def _canonical_lifecycle_event(event: Mapping[str, Any]) -> dict[str, Any]:
    event_type = str(event.get("type", ""))
    tp_price = event.get("tp_price")
    if isinstance(tp_price, (int, float, np.integer, np.floating)) and not np.isfinite(tp_price):
        tp_price = None
    canonical: dict[str, Any] = {
        "type": event_type,
        "direction": event.get("direction"),
        "decision_bar_time": _event_time_utc(event, "decision_bar_time"),
        "fill_time": _event_time_utc(event, "fill_time", "actual_tick_time", "time"),
        "price": event.get("price"),
    }
    if event_type == "open":
        canonical.update(
            {
                "size": event.get("lots", event.get("size")),
                "sl_price": event.get("sl_price"),
                "tp_price": tp_price,
                "modeled_stop_risk_usd": event.get("modeled_stop_risk_usd", event.get("risk_cash")),
                "risk_budget_usd": event.get("approved_risk_usd", event.get("risk_budget_usd")),
                "risk_frac": event.get("risk_frac"),
            }
        )
        if tp_price is not None:
            rr_ratio = event.get("rr_ratio")
            if rr_ratio is not None:
                missing_rr_ratio = pd.isna(rr_ratio)
                if isinstance(missing_rr_ratio, (bool, np.bool_)) and missing_rr_ratio:
                    rr_ratio = None
            canonical["rr_ratio"] = rr_ratio
    elif event_type in {"close", "forced_close"}:
        canonical.update(
            {
                "entry_price": event.get("entry_price"),
                "size": event.get("size", event.get("lots")),
                "net_pnl": event.get("net_pnl", event.get("pnl")),
            }
        )
    return canonical


def _compare_lifecycle_events(
    environment_events: list[dict[str, Any]], backtest_events: list[dict[str, Any]]
) -> tuple[bool, list[str]]:
    environment = [
        _canonical_lifecycle_event(event)
        for event in environment_events
        if event.get("type") in {"open", "close", "forced_close"}
    ]
    backtest = [
        _canonical_lifecycle_event(event)
        for event in backtest_events
        if event.get("type") in {"open", "close", "forced_close"}
    ]
    mismatches: list[str] = []
    if len(environment) != len(backtest):
        mismatches.append("lifecycle_event_count")
    for index, (left, right) in enumerate(zip(environment, backtest, strict=False)):
        if left["type"] != right["type"]:
            mismatches.append(f"lifecycle[{index}].type")
            continue
        for field in left:
            left_value, right_value = left[field], right[field]
            if isinstance(left_value, (int, float)) and isinstance(right_value, (int, float)):
                equal = bool(np.isclose(left_value, right_value, rtol=0.0, atol=1e-8))
            else:
                equal = left_value == right_value
            if not equal:
                mismatches.append(f"{left['type']}[{index}].{field}")
    return not mismatches, mismatches


def _json_safe(value: Any) -> Any:
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, np.ndarray):
        return _json_safe(value.tolist())
    if isinstance(value, np.generic):
        return _json_safe(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def replay_simulator_action_tape(
    bars: pd.DataFrame,
    features: pd.DataFrame,
    tape_path: Path,
    *,
    environment_kwargs: Mapping[str, Any],
    backtest_kwargs: Mapping[str, Any],
    run_provenance: Mapping[str, Any],
    seed: int,
    backtest_tape_path: Path | None = None,
) -> dict[str, Any]:
    """Replay exact UTC decision-bar timestamps through both simulator APIs.

    ``run_provenance`` must identify the frozen train-only input window and its
    bars, features, resolved configuration, and source revision hashes.
    """
    provenance = _validated_provenance(run_provenance)
    _validate_matched_settings(environment_kwargs, backtest_kwargs, seed, run_provenance)
    if environment_kwargs.get("tickbook") is not None:
        provenance["ticks_sha256"] = _required_sha256(run_provenance, "ticks_sha256")
    environment_tape, backtest_tape, utc_index = _load_tapes(
        tape_path,
        bars,
        features,
        environment_kwargs,
        backtest_kwargs,
        backtest_tape_path=backtest_tape_path,
    )
    decision_times = [timestamp for timestamp, _ in environment_tape.actions]
    environment, environment_times, environment_account_rows, terminated, truncated = (
        _run_environment(bars, features, environment_tape, utc_index, environment_kwargs, seed)
    )
    backtest_result, actual_backtest_times = _run_backtest(
        bars, features, backtest_tape, backtest_kwargs, environment_kwargs
    )
    environment_events = [dict(event) for event in environment.trade_log]
    backtest_events = [dict(event) for event in backtest_result["trades"].to_dict("records")]
    expected_environment_times = [timestamp.isoformat() for timestamp in decision_times]
    expected_backtest_times = [timestamp.isoformat() for timestamp, _ in backtest_tape.actions]
    environment_lifecycle = _lifecycle(environment_events)
    backtest_lifecycle = _lifecycle(backtest_events)
    event_fields_match, event_field_mismatches = _compare_lifecycle_events(
        environment_events, backtest_events
    )
    order_events_match, order_event_mismatches = _compare_order_events(
        environment_events, backtest_events
    )
    account_state_matches, account_state_rows = _compare_account_state_rows(
        environment_account_rows,
        backtest_result.get("account_state_trace"),
        backtest_policy_decision_times_utc=set(expected_backtest_times),
    )
    environment_balance = float(environment.account.balance)
    backtest_balance = float(backtest_result["account"].balance)
    checks = {
        "environment_consumed_tape_at_exact_times": environment_times == expected_environment_times,
        "backtest_decisions_match_tape_times": actual_backtest_times == expected_backtest_times,
        "lifecycle_events_match": environment_lifecycle == backtest_lifecycle,
        "lifecycle_event_fields_match": event_fields_match,
        "order_events_match": order_events_match,
        "account_state_trace_matches": account_state_matches,
        "final_balance_matches": bool(
            np.isclose(environment_balance, backtest_balance, rtol=0, atol=1e-8)
        ),
    }
    return {
        "schema_version": 1,
        "tape_sha256": environment_tape.sha256,
        "run_provenance": provenance,
        "seed": int(seed),
        "tape_decision_times_utc": expected_environment_times,
        "environment_tape_sha256": environment_tape.sha256,
        "backtest_tape_sha256": backtest_tape.sha256,
        "backtest_tape_decision_times_utc": expected_backtest_times,
        "environment_decision_times_utc": environment_times,
        "backtest_decision_bar_times_utc": actual_backtest_times,
        "environment_events": _json_safe(environment_events),
        "backtest_events": _json_safe(backtest_events),
        "environment_lifecycle": environment_lifecycle,
        "backtest_lifecycle": backtest_lifecycle,
        "lifecycle_event_field_mismatches": event_field_mismatches,
        "order_event_field_mismatches": order_event_mismatches,
        "account_state_parity": {
            "matched_decision_count": sum(not row["mismatches"] for row in account_state_rows),
            "rows": account_state_rows,
        },
        "environment_account_trace": _json_safe(environment_account_rows),
        "environment_event_count": len(environment_events),
        "backtest_event_count": len(backtest_events),
        "environment_final_balance": environment_balance,
        "backtest_final_balance": backtest_balance,
        "checks": checks,
        "trace_passed": all(checks.values()),
        "environment_terminated": terminated,
        "environment_truncated": truncated,
    }
