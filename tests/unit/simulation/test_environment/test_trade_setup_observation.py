from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from gymnasium import spaces

from decisioning.trade_setup import (
    CANDIDATE_GEOMETRY_FEATURE_NAMES,
    NO_TRADE_ID,
    TRADE_SETUP_CATEGORY_COUNT,
    TRADE_SETUP_OBSERVATION_VERSION,
    TradeSetupActionSchema,
    candidate_geometry_slot_count,
    trade_setup_candidate,
    trade_setup_candidate_id,
    trade_setup_center,
)
from features.context.trade_setup_candidates import trade_setup_candidate_feature_columns
from simulation.environment.env import TradingEnv
from tests.unit.simulation.test_environment._account_fixtures import (
    _make_bars,
    _make_features,
)


def _features_with_trade_setup_columns() -> tuple[pd.DataFrame, pd.DataFrame]:
    bars = _make_bars(120)
    features = _make_features(bars)
    trade_setup_features = pd.DataFrame(
        0.0,
        index=features.index,
        columns=[column for _, column in trade_setup_candidate_feature_columns()],
    )
    features = pd.concat([features, trade_setup_features], axis=1)
    active_column = "entry_idea_fvg_retest_M5_long"
    features.loc[bars.index[50], active_column] = 1.0
    return bars, features


def test_trade_setup_observation_mask_is_exact_and_optional() -> None:
    bars, features = _features_with_trade_setup_columns()
    trade_setup_env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=10,
        strategy_actions=True,
        trade_setup_actions=True,
    )
    assert trade_setup_env.trade_setup_observation_schema is not None
    assert (
        trade_setup_env.trade_setup_observation_schema["version"] == TRADE_SETUP_OBSERVATION_VERSION
    )
    assert isinstance(trade_setup_env.observation_space, spaces.Dict)
    assert trade_setup_env.observation_space["trade_setup_mask"].shape == (
        TRADE_SETUP_CATEGORY_COUNT,
    )

    trade_setup_env.step_idx = 49
    previous = trade_setup_env._get_observation()["trade_setup_mask"]
    trade_setup_env.step_idx = 50
    current = trade_setup_env._get_observation()["trade_setup_mask"]
    candidate_id = trade_setup_candidate_id("fvg_retest", "M5", 1)

    assert previous[NO_TRADE_ID] == current[NO_TRADE_ID] == 1.0
    assert previous[candidate_id] == 0.0
    assert current[candidate_id] == 1.0
    assert current[trade_setup_candidate_id("fvg_retest", "M1", 1)] == 0.0
    assert current[trade_setup_candidate_id("fvg_retest", "M5", -1)] == 0.0
    assert int(current.sum()) == 2

    env_without_trade_setup = TradingEnv(
        bars=bars, features=features, obs_window=10, strategy_actions=True
    )
    observation, _ = env_without_trade_setup.reset(seed=3)
    assert "trade_setup_mask" not in observation
    assert isinstance(env_without_trade_setup.observation_space, spaces.Dict)
    assert "trade_setup_mask" not in env_without_trade_setup.observation_space
    assert env_without_trade_setup.trade_setup_observation_schema is None


def test_candidate_geometry_is_wired_into_real_environment_observations() -> None:
    bars, features = _features_with_trade_setup_columns()
    close_date = bars.index[50].date().isoformat()
    env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=10,
        strategy_actions=True,
        trade_setup_actions=True,
        candidate_geometry_actions=True,
        agent_entry_execution=True,
        scheduled_session_closes={close_date: "23:59"},
        session_start="00:00",
    )
    env.step_idx = 50

    observation = env._get_observation()

    count = candidate_geometry_slot_count()
    assert observation["candidate_ids"].shape == (count,)
    assert observation["candidate_features"].shape == (
        count,
        len(CANDIDATE_GEOMETRY_FEATURE_NAMES),
    )
    assert observation["candidate_mask"].dtype == np.bool_
    assert observation["candidate_mask"][0]
    assert isinstance(env.observation_space, spaces.Dict)
    candidate_mask_space = env.observation_space.spaces["candidate_mask"]
    assert isinstance(candidate_mask_space, spaces.Box)
    assert candidate_mask_space.dtype == np.bool_


def test_step_returns_candidate_mask_for_next_decision_row() -> None:
    bars, features = _features_with_trade_setup_columns()
    env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=10,
        strategy_actions=True,
        trade_setup_actions=True,
    )
    env.reset(seed=3)
    env.step_idx = 49
    env._ny_pos = int(np.searchsorted(env._ny_indices, env.step_idx))
    candidate_id = trade_setup_candidate_id("fvg_retest", "M5", 1)
    assert isinstance(env.action_schema, TradeSetupActionSchema)
    action = np.zeros(env.action_schema.width, dtype=np.float32)
    action[env.action_schema.indices["trade_setup"]] = trade_setup_center(NO_TRADE_ID)

    next_observation, _, terminated, truncated, _ = env.step(action)

    assert not terminated
    assert not truncated
    assert env.step_idx == 50
    assert next_observation["trade_setup_mask"][candidate_id] == 1.0
    np.testing.assert_array_equal(
        next_observation["trade_setup_mask"], env._trade_setup_mask_for_step()
    )


def test_trade_setup_observation_requires_strategy_overlay_and_idea_features() -> None:
    bars, features = _features_with_trade_setup_columns()
    with pytest.raises(ValueError, match="trade setup actions require strategy_actions=true"):
        TradingEnv(bars=bars, features=features, obs_window=10, trade_setup_actions=True)

    with pytest.raises(ValueError, match="per-timeframe entry-idea"):
        TradingEnv(
            bars=bars,
            features=_make_features(bars),
            obs_window=10,
            strategy_actions=True,
            trade_setup_actions=True,
        )


def test_trade_setup_decoder_uses_selected_direction_and_rejects_inactive_candidate() -> None:
    bars, features = _features_with_trade_setup_columns()
    env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=10,
        strategy_actions=True,
        trade_setup_actions=True,
        allow_multi_tp=True,
        allow_agent_sl_mode=True,
        allow_agent_tp_mode=True,
        allow_simplex=True,
    )
    env.step_idx = 50
    schema = env.action_schema
    assert isinstance(schema, TradeSetupActionSchema)
    active_id = trade_setup_candidate_id("fvg_retest", "M5", 1)
    action = np.zeros(schema.width, dtype=np.float32)
    action[schema.indices["trade_setup"]] = trade_setup_center(active_id)
    direction, risk, _, _ = env._decode_action(action, features.iloc[50])
    assert direction == 1
    assert risk > 0.0
    assert env._selected_trade_setup is not None
    assert env._selected_trade_setup.candidate_id == active_id

    action[schema.indices["trade_setup"]] = trade_setup_center(NO_TRADE_ID)
    direction, risk, _, _ = env._decode_action(action, features.iloc[50])
    assert direction == 0
    assert risk == 0.0

    inactive_id = trade_setup_candidate_id("fvg_retest", "M1", 1)
    action[schema.indices["trade_setup"]] = trade_setup_center(inactive_id)
    direction, risk, _, _ = env._decode_action(action, features.iloc[50])
    assert direction == 0
    assert risk == 0.0
    assert env._selected_trade_setup is None


def test_delayed_entry_keeps_the_selected_primary_trade_setup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bars, features = _features_with_trade_setup_columns()
    env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=10,
        strategy_actions=True,
        trade_setup_actions=True,
        fill_latency_bars=1,
    )
    primary = trade_setup_candidate(trade_setup_candidate_id("fvg_retest", "M5", 1))
    later_context = trade_setup_candidate(trade_setup_candidate_id("order_block", "H1", -1))
    env._selected_trade_setup = primary
    env.step_idx = 50
    when = env._bar_time(50)
    bar = env._bar_at(50)
    feat_row = env._feature_row_at(50)
    action = np.zeros(env.action_schema.width, dtype=np.float32)

    env._execute_step_action(
        action=action,
        discrete_action=1,
        risk_frac=0.005,
        rr_ratio=2.0,
        bar=bar,
        feat_row=feat_row,
        bar_time=when,
        session_id=env._current_session_id(),
        fill_idx=51,
        action_fill_time=env._bar_time(51),
        fill_bid=bar.open,
        fill_ask=bar.open + 0.6,
        fill_time=when,
        entry_fill_bid=bar.open,
        entry_fill_ask=bar.open + 0.6,
        entry_fill_time=when,
        market_fill_idx=51,
        entry_candidate=None,
        done=False,
        pending_due=False,
        session_blocked=False,
        peak_dd_block=False,
    )
    pending = env._pending_entry_order
    assert pending is not None
    assert pending["selected"]["_selected_trade_setup"].candidate_id == primary.candidate_id
    assert env.trade_log[-1]["type"] == "order_submit"
    assert env.trade_log[-1]["trade_setup_candidate_id"] == primary.candidate_id
    assert env.trade_log[-1]["primary_setup_timeframe"] == "M5"
    assert env.trade_log[-1]["decision_bar_time"] == when
    completed_bar_time = when + pd.Timedelta(minutes=env._minutes_per_step)
    assert env.trade_log[-1]["decision_time"] == completed_bar_time
    assert env.trade_log[-1]["signal_time"] == completed_bar_time
    assert env.trade_log[-1]["order_submission_time"] == completed_bar_time

    entered_trade_setups: list[int | None] = []

    def capture_entry(self: TradingEnv, *args: object, **kwargs: object) -> None:
        selected = self._selected_trade_setup
        entered_trade_setups.append(selected.candidate_id if selected is not None else None)

    monkeypatch.setattr(TradingEnv, "_try_enter_position", capture_entry)
    env._selected_trade_setup = later_context
    env._enforce_step_constraints(
        env._bar_at(51),
        env._feature_row_at(51),
        env._bar_time(51),
        env._current_session_id(),
        float(bars.iloc[51]["open"]),
        float(bars.iloc[51]["open"] + 0.6),
        env._bar_time(51),
        pending_due=True,
        entry_fill_bid=float(bars.iloc[51]["open"]),
        entry_fill_ask=float(bars.iloc[51]["open"] + 0.6),
        entry_fill_time=env._bar_time(51),
        market_fill_idx=51,
    )

    assert entered_trade_setups == [primary.candidate_id]
    assert env._selected_trade_setup == later_context
    assert env._pending_entry_order is None
