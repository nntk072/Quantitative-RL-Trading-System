from __future__ import annotations

import pandas as pd
from omegaconf import OmegaConf

from features.pipeline.feature_build_inputs import (
    DEFAULT_MTF_CONTEXT_TIMEFRAMES,
    configured_feature_timeframes,
    split_raw_fvg_features,
)


def test_split_raw_fvg_features_keeps_model_features_separate() -> None:
    features = pd.DataFrame(
        {
            "ret_1": [0.1],
            "M5_fvg_bull_low": [100.0],
            "M5_fvg_bull_active": [1],
            "M5_fvg_retest_bear": [0],
        }
    )

    model_features, raw_features = split_raw_fvg_features(features)

    assert list(model_features.columns) == ["ret_1"]
    assert list(raw_features.columns) == [
        "M5_fvg_bull_low",
        "M5_fvg_bull_active",
        "M5_fvg_retest_bear",
    ]


def test_configured_feature_timeframes_supports_nested_and_flat_config() -> None:
    nested_cfg = OmegaConf.create({"smt": {"enabled": True, "timeframes": ["M5", "H1"]}})
    flat_cfg = OmegaConf.create({"smt_timeframes": ["M3", "M15"]})

    assert configured_feature_timeframes(nested_cfg, "smt", DEFAULT_MTF_CONTEXT_TIMEFRAMES) == [
        "M5",
        "H1",
    ]
    assert configured_feature_timeframes(flat_cfg, "smt", DEFAULT_MTF_CONTEXT_TIMEFRAMES) == [
        "M3",
        "M15",
    ]
    assert configured_feature_timeframes(None, "smt", DEFAULT_MTF_CONTEXT_TIMEFRAMES) == list(
        DEFAULT_MTF_CONTEXT_TIMEFRAMES
    )
