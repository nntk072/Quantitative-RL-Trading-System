from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from gymnasium import spaces

from decisioning.thesis import (
    NO_TRADE_ID,
    THESIS_CATEGORY_COUNT,
    THESIS_OBSERVATION_VERSION,
    ThesisActionSchema,
    thesis_candidate,
    thesis_candidate_id,
    thesis_center,
)
from features.context.thesis_candidates import thesis_candidate_feature_columns
from simulation.environment.env import TradingEnv
from tests.unit.simulation.test_environment.test_account_normalization import (
    _make_bars,
    _make_features,
)


def _features_with_thesis_columns() -> tuple[pd.DataFrame, pd.DataFrame]:
    bars = _make_bars(120)
    features = _make_features(bars)
    thesis_features = pd.DataFrame(
        0.0,
        index=features.index,
        columns=[column for _, column in thesis_candidate_feature_columns()],
    )
    features = pd.concat([features, thesis_features], axis=1)
    active_column = "entry_idea_fvg_retest_M5_long"
    features.loc[bars.index[50], active_column] = 1.0
    return bars, features


def test_thesis_observation_mask_is_exact_and_legacy_keys_stay_unchanged() -> None:
    bars, features = _features_with_thesis_columns()
    thesis_env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=10,
        strategy_actions=True,
        thesis_actions=True,
    )
    assert thesis_env.thesis_observation_schema is not None
    assert thesis_env.thesis_observation_schema["version"] == THESIS_OBSERVATION_VERSION
    assert isinstance(thesis_env.observation_space, spaces.Dict)
    assert thesis_env.observation_space["thesis_mask"].shape == (THESIS_CATEGORY_COUNT,)

    thesis_env.step_idx = 49
    previous = thesis_env._get_observation()["thesis_mask"]
    thesis_env.step_idx = 50
    current = thesis_env._get_observation()["thesis_mask"]
    candidate_id = thesis_candidate_id("fvg_retest", "M5", 1)

    assert previous[NO_TRADE_ID] == current[NO_TRADE_ID] == 1.0
    assert previous[candidate_id] == 0.0
    assert current[candidate_id] == 1.0
    assert current[thesis_candidate_id("fvg_retest", "M1", 1)] == 0.0
    assert current[thesis_candidate_id("fvg_retest", "M5", -1)] == 0.0
    assert int(current.sum()) == 2

    legacy_env = TradingEnv(bars=bars, features=features, obs_window=10, strategy_actions=True)
    legacy_obs, _ = legacy_env.reset(seed=3)
    assert "thesis_mask" not in legacy_obs
    assert isinstance(legacy_env.observation_space, spaces.Dict)
    assert "thesis_mask" not in legacy_env.observation_space
    assert legacy_env.thesis_observation_schema is None


def test_thesis_observation_requires_strategy_overlay_and_idea_features() -> None:
    bars, features = _features_with_thesis_columns()
    with pytest.raises(ValueError, match="requires strategy_actions=true"):
        TradingEnv(bars=bars, features=features, obs_window=10, thesis_actions=True)

    with pytest.raises(ValueError, match="per-timeframe entry-idea"):
        TradingEnv(
            bars=bars,
            features=_make_features(bars),
            obs_window=10,
            strategy_actions=True,
            thesis_actions=True,
        )


def test_thesis_decoder_uses_selected_direction_and_rejects_inactive_candidate() -> None:
    bars, features = _features_with_thesis_columns()
    env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=10,
        strategy_actions=True,
        thesis_actions=True,
        allow_multi_tp=True,
        allow_agent_sl_mode=True,
        allow_agent_tp_mode=True,
        allow_simplex=True,
    )
    env.step_idx = 50
    schema = env.action_schema
    assert isinstance(schema, ThesisActionSchema)
    active_id = thesis_candidate_id("fvg_retest", "M5", 1)
    action = np.zeros(schema.width, dtype=np.float32)
    action[schema.indices["thesis"]] = thesis_center(active_id)
    direction, risk, _, _ = env._decode_action(action, features.iloc[50])
    assert direction == 1
    assert risk > 0.0
    assert env._selected_thesis is not None
    assert env._selected_thesis.candidate_id == active_id

    action[schema.indices["thesis"]] = thesis_center(NO_TRADE_ID)
    direction, risk, _, _ = env._decode_action(action, features.iloc[50])
    assert direction == 0
    assert risk == 0.0

    inactive_id = thesis_candidate_id("fvg_retest", "M1", 1)
    action[schema.indices["thesis"]] = thesis_center(inactive_id)
    direction, risk, _, _ = env._decode_action(action, features.iloc[50])
    assert direction == 0
    assert risk == 0.0
    assert env._selected_thesis is None


def test_delayed_entry_keeps_the_selected_primary_thesis(monkeypatch: pytest.MonkeyPatch) -> None:
    bars, features = _features_with_thesis_columns()
    env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=10,
        strategy_actions=True,
        thesis_actions=True,
        fill_latency_bars=1,
    )
    primary = thesis_candidate(thesis_candidate_id("fvg_retest", "M5", 1))
    later_context = thesis_candidate(thesis_candidate_id("order_block", "H1", -1))
    env._selected_thesis = primary
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
        entry_machine=None,
        done=False,
        pending_due=False,
        session_blocked=False,
        peak_dd_block=False,
    )
    pending = env._pending_entry_order
    assert pending is not None
    assert pending["selected"]["_selected_thesis"].candidate_id == primary.candidate_id
    assert env.trade_log[-1]["type"] == "order_submit"
    assert env.trade_log[-1]["thesis_candidate_id"] == primary.candidate_id
    assert env.trade_log[-1]["primary_setup_timeframe"] == "M5"

    entered_thesis: list[int | None] = []

    def capture_entry(self: TradingEnv, *args: object, **kwargs: object) -> None:
        selected = self._selected_thesis
        entered_thesis.append(selected.candidate_id if selected is not None else None)

    monkeypatch.setattr(TradingEnv, "_try_enter_position", capture_entry)
    env._selected_thesis = later_context
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
        entry_machine=None,
    )

    assert entered_thesis == [primary.candidate_id]
    assert env._selected_thesis == later_context
    assert env._pending_entry_order is None
