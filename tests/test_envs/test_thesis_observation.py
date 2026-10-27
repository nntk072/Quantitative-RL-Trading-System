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
    thesis_candidate_id,
    thesis_center,
)
from features.context.thesis_candidates import thesis_candidate_feature_columns
from simulation.environment.env import TradingEnv
from tests.test_envs.test_account_normalization import _make_bars, _make_features


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
