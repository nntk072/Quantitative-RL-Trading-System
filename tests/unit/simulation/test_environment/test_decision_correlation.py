from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import pytest

from decisioning.trade_setup import (
    TRADE_SETUP_CATEGORY_COUNT,
    TradeSetupActionSchema,
    trade_setup_candidate_id,
    trade_setup_center,
)
from features.context.trade_setup_candidates import trade_setup_candidate_feature_columns
from simulation.environment.env import TradingEnv


def _market_inputs(*, periods: int = 16) -> tuple[pd.DataFrame, pd.DataFrame]:
    index = pd.date_range("2025-01-06 14:30", periods=periods, freq="1min", tz="UTC")
    close = np.full(periods, 20_000.0)
    bars = pd.DataFrame(
        {
            "open": close,
            "high": close + 2.0,
            "low": close - 2.0,
            "close": close,
            "spread": 0.6,
            "session_id": 0,
        },
        index=index,
    )
    features = pd.DataFrame(
        0.0,
        index=index,
        columns=[name for _, name in trade_setup_candidate_feature_columns()],
    )
    features["entry_idea_fvg_retest_M5_long"] = 1.0
    features["M5_fvg_bull_retest_confirmed_at_time_ns"] = float(index[0].value)
    features["M5_fvg_bull_retest_origin_time_ns"] = float(index[0].value - 300_000_000_000)
    features["last_swing_low"] = close - 20.0
    features["last_swing_high"] = close + 40.0
    return bars, features


def _setup_action(env: TradingEnv, candidate_id: int) -> np.ndarray[Any, Any]:
    schema = env.action_schema
    assert isinstance(schema, TradeSetupActionSchema)
    assert schema.width > 0
    assert TRADE_SETUP_CATEGORY_COUNT > candidate_id >= 0
    action = np.zeros(schema.width, dtype=np.float32)
    action[schema.indices["trade_setup"]] = trade_setup_center(candidate_id)
    return action


def _trade_setup_env(
    bars: pd.DataFrame, features: pd.DataFrame, *, fill_latency_bars: int = 0, max_steps: int = 4
) -> TradingEnv:
    return TradingEnv(
        bars=bars,
        features=features,
        obs_window=1,
        strategy_actions=True,
        trade_setup_actions=True,
        fill_latency_bars=fill_latency_bars,
        open_manipulation_bars=0,
        max_episode_steps=max_steps,
        episodic=False,
    )


def test_immediate_setup_rejection_uses_the_environment_decision_id() -> None:
    bars, features = _market_inputs()
    env = _trade_setup_env(bars, features)
    env.reset(seed=7)
    inactive_id = trade_setup_candidate_id("fvg_retest", "M1", 1)

    _, _, _, _, info = env.step(_setup_action(env, inactive_id))

    rejection = next(event for event in env.trade_log if event["type"] == "reject")
    assert str(info["decision_id"]).endswith(":d1")
    assert info["trade_setup_candidate_id"] == inactive_id
    assert info["trade_setup_eligible"] is False
    assert info["trade_setup_selected_idea"] == ""
    assert info["trade_setup_action_schema_version"] == env.action_schema.version
    assert info["action"] == 0
    assert info["position_direction_at_decision"] == 0
    assert info["position_id_at_decision"] is None
    assert info["pending_order_id_at_decision"] is None
    assert rejection["decision_id"] == info["decision_id"]
    assert rejection["entry_rejection_reason"] == "trade_setup_inactive"


def test_no_trade_decision_is_recorded_as_an_eligible_setup_choice() -> None:
    bars, features = _market_inputs()
    env = _trade_setup_env(bars, features)
    env.reset(seed=7)

    _, _, _, _, info = env.step(_setup_action(env, 0))

    assert info["trade_setup_candidate_id"] == 0
    assert info["trade_setup_eligible"] is True
    assert info["trade_setup_selected_idea"] == "no_trade"
    assert info["trade_setup_selected_timeframe"] == ""
    assert info["trade_setup_selected_direction"] == 0


def test_delayed_setup_order_and_open_keep_the_originating_decision_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bars, features = _market_inputs()
    # Leave one nonterminal policy step after the delayed fill so this test can
    # inspect the live position and its originating decision ID.
    env = _trade_setup_env(bars, features, fill_latency_bars=1, max_steps=3)
    env.reset(seed=7)
    active_id = trade_setup_candidate_id("fvg_retest", "M5", 1)
    monkeypatch.setattr(
        TradingEnv,
        "_build_entry_levels",
        lambda self, *_args, **_kwargs: (20_000.0, 19_990.0, 20_020.0, 0.1, True, None),
    )

    _, _, _, _, first_info = env.step(_setup_action(env, active_id))
    assert first_info["trade_setup_source_event_identity_status"] == "identified"
    assert first_info["trade_setup_candidate_id"] == active_id
    assert first_info["trade_setup_eligible"] is True
    assert first_info["trade_setup_selected_idea"] == "fvg_retest"
    assert first_info["trade_setup_selected_timeframe"] == "M5"
    assert first_info["trade_setup_selected_direction"] == 1
    expected_event_time = int(features["M5_fvg_bull_retest_confirmed_at_time_ns"].iloc[0])
    expected_origin_time = int(features["M5_fvg_bull_retest_origin_time_ns"].iloc[0])
    assert first_info["trade_setup_source_event_id"] == (
        "candidate-scoped-source-time-identity.v1:fvg_retest:M5:1:"
        f"M5_fvg_bull_retest_confirmed_at_time_ns={expected_event_time}:"
        f"M5_fvg_bull_retest_origin_time_ns={expected_origin_time}"
    )
    _, _, _, _, second_info = env.step(_setup_action(env, 0))

    submitted = next(event for event in env.trade_log if event["type"] == "order_submit")
    opened = next(event for event in env.trade_log if event["type"] == "open")
    assert str(first_info["decision_id"]).endswith(":d1")
    assert str(second_info["decision_id"]).endswith(":d2")
    assert submitted["decision_id"] == first_info["decision_id"]
    assert submitted["order_type"] == "market"
    assert str(submitted["order_id"]).endswith(":market")
    assert second_info["pending_order_id_at_decision"] == submitted["order_id"]
    assert opened["decision_id"] == first_info["decision_id"]
    assert opened["order_id"] == submitted["order_id"]
    filled = next(event for event in env.trade_log if event["type"] == "order_fill")
    assert filled["order_id"] == submitted["order_id"]
    assert filled["decision_id"] == first_info["decision_id"]
    assert filled["price"] == opened["price"]
    assert submitted["trade_setup_source_event_id"] == first_info["trade_setup_source_event_id"]
    assert opened["trade_setup_source_event_id"] == first_info["trade_setup_source_event_id"]
    assert (
        submitted["trade_setup_source_event_times_ns"]
        == first_info["trade_setup_source_event_times_ns"]
    )
    assert (
        opened["trade_setup_source_event_times_ns"]
        == first_info["trade_setup_source_event_times_ns"]
    )
    assert opened["trade_setup_source_event_identity_status"] == "identified"
    assert (
        opened["trade_setup_event_identity_version"]
        == (first_info["trade_setup_event_identity_version"])
    )
    assert opened["trade_setup_candidate_id"] == active_id
    assert env.position is not None
    assert env.position.origin_decision_id == first_info["decision_id"]

    exit_record: dict[str, object] = {"type": "tp_partial_close"}
    env._stamp_exit(exit_record, float(env.position.entry_price))
    assert exit_record["origin_decision_id"] == first_info["decision_id"]


def test_delayed_order_cancel_keeps_the_originating_decision_id() -> None:
    bars, features = _market_inputs()
    env = _trade_setup_env(bars, features, fill_latency_bars=1, max_steps=1)
    env.reset(seed=7)
    active_id = trade_setup_candidate_id("fvg_retest", "M5", 1)

    _, _, _, truncated, info = env.step(_setup_action(env, active_id))

    submitted = next(event for event in env.trade_log if event["type"] == "order_submit")
    canceled = next(event for event in env.trade_log if event["type"] == "order_cancel")
    assert truncated is True
    assert canceled["reason"] == "episode_ended_before_scheduled_fill"
    assert canceled["decision_id"] == submitted["decision_id"] == info["decision_id"]


def test_delayed_entry_rejection_keeps_the_submitting_decision_id() -> None:
    bars, features = _market_inputs()
    env = _trade_setup_env(bars, features, fill_latency_bars=1, max_steps=2)
    env.reset(seed=7)
    active_id = trade_setup_candidate_id("fvg_retest", "M5", 1)

    _, _, _, _, submitted_info = env.step(_setup_action(env, active_id))
    _, _, _, _, due_info = env.step(_setup_action(env, 0))

    rejection = next(event for event in env.trade_log if event["type"] == "reject")
    assert rejection["entry_rejection_reason"] == "no_valid_sl"
    assert rejection["decision_id"] == submitted_info["decision_id"]
    assert due_info["decision_id"] != rejection["decision_id"]


def test_delayed_order_cannot_fill_after_session_reset() -> None:
    bars, features = _market_inputs()
    bars["session_id"] = [0, 0, 0, 0, *([1] * (len(bars) - 4))]
    env = _trade_setup_env(bars, features, fill_latency_bars=2, max_steps=2)
    env.reset(seed=7)
    active_id = trade_setup_candidate_id("fvg_retest", "M5", 1)

    _, _, _, _, info = env.step(_setup_action(env, active_id))

    assert env._pending_entry_order is None
    rejection = next(event for event in env.trade_log if event["type"] == "reject")
    assert rejection["entry_rejection_reason"] == "overnight_boundary"
    assert rejection["decision_id"] == info["decision_id"]
