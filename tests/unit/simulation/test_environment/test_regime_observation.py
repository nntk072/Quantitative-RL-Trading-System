from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from omegaconf import OmegaConf

from decisioning.regime_observations import REGIME_FEATURES, regime_observation_schema
from simulation.environment import regime_observation_enabled
from simulation.environment.env import TradingEnv
from tests.unit.simulation.test_environment.test_account_normalization import (
    _make_bars,
    _make_features,
)


def _features_with_regime(bars: pd.DataFrame) -> pd.DataFrame:
    features = _make_features(bars)
    for offset, name in enumerate(REGIME_FEATURES):
        features[name] = np.linspace(-1.0, 1.0, len(bars), dtype=np.float32) + offset
    return features


def test_disabled_regime_branch_preserves_baseline_observation_keys() -> None:
    bars = _make_bars(120)
    env = TradingEnv(bars=bars, features=_make_features(bars), obs_window=10)

    observation, _ = env.reset(seed=11)

    assert set(observation) == {"seq", "seq_mask", "account"}
    assert env.regime_observation_schema is None


def test_regime_vector_has_per_feature_warmup_mask_and_schema() -> None:
    bars = _make_bars(120)
    features = _features_with_regime(bars)
    features[REGIME_FEATURES[0]] = np.nan
    env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=10,
        regime_observation=True,
    )

    observation, _ = env.reset(seed=11)

    assert observation["regime"].shape == (len(REGIME_FEATURES),)
    assert observation["regime_mask"].shape == (len(REGIME_FEATURES),)
    assert observation["regime"].dtype == np.float32
    assert observation["regime_mask"].dtype == np.float32
    assert observation["regime_mask"][0] == 0.0
    assert np.all(np.isfinite(observation["regime"]))
    assert env.observation_space.contains(observation)
    assert env.regime_observation_schema == regime_observation_schema()


def test_regime_observation_at_t_is_unchanged_by_future_rows() -> None:
    bars = _make_bars(120)
    features = _features_with_regime(bars)
    env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=10,
        regime_observation=True,
    )
    env.step_idx = 40
    original = env._get_observation()
    env._obs_features_arr[41:, env._regime_idx] = 1_000_000.0
    changed_future = env._get_observation()

    np.testing.assert_array_equal(original["regime"], changed_future["regime"])
    np.testing.assert_array_equal(original["regime_mask"], changed_future["regime_mask"])


def test_regime_observation_fails_if_required_feature_is_missing() -> None:
    bars = _make_bars(120)
    features = _features_with_regime(bars).drop(columns=[REGIME_FEATURES[-1]])

    with pytest.raises(ValueError, match="missing required D1 features"):
        TradingEnv(
            bars=bars,
            features=features,
            obs_window=10,
            regime_observation=True,
        )


def test_regime_observation_requires_source_index_normalization() -> None:
    cfg = OmegaConf.create(
        {
            "env": {"regime_observation": True},
            "features": {"normalize_d1_technical_on_source": False},
        }
    )

    with pytest.raises(ValueError, match="normalize_d1_technical_on_source=true"):
        regime_observation_enabled(cfg)

    cfg.features.normalize_d1_technical_on_source = True
    assert regime_observation_enabled(cfg)
