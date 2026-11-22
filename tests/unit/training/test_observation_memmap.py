from __future__ import annotations

import numpy as np
import pandas as pd
from omegaconf import OmegaConf

from features.context.trade_setup_candidates import trade_setup_candidate_feature_columns
from simulation.environment.bundles import observation_features
from training.setup.environments import strategy_from_cfg
from training.setup.observation_memmap import publish_observation_memmap


def test_trade_setup_memmap_omits_candidate_features(tmp_path) -> None:
    index = pd.date_range("2025-01-06 14:30", periods=4, freq="1min", tz="UTC")
    prices = np.asarray([100.0, 100.5, 101.0, 101.5])
    bars = pd.DataFrame(
        {
            "open": prices,
            "high": prices + 1.0,
            "low": prices - 1.0,
            "close": prices,
            "spread": 0.0,
        },
        index=index,
    )
    candidate_columns = [name for _, name in trade_setup_candidate_feature_columns()]
    features = pd.DataFrame(0.0, index=index, columns=["atr_5", *candidate_columns])
    features["atr_5"] = 1.0
    features[candidate_columns[0]] = np.arange(len(index), dtype=np.float64)
    config = OmegaConf.load("config/base/default.yaml")
    config.env.n_envs = 8
    config.env.trade_setup_actions = True

    output = tmp_path / "observations.npy"
    publish_observation_memmap(features, bars, config, output)

    observed = np.load(output, allow_pickle=False)
    strategy, _, _ = strategy_from_cfg(config)
    expected, expected_columns = observation_features(
        bars,
        features,
        strategy.raw_columns,
        exclude_trade_setup_candidates=True,
    )
    np.testing.assert_array_equal(observed, expected)
    assert observed.shape[1] == len(expected_columns)
    assert candidate_columns[0] not in expected_columns
