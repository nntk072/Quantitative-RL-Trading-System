from __future__ import annotations

import pandas as pd
from omegaconf import OmegaConf

from features.pipeline.feature_build_inputs import (
    DEFAULT_MTF_CONTEXT_TIMEFRAMES,
    configured_feature_timeframes,
    feature_block_enabled,
    resample_market_pair,
    source_timeframe_training_mask,
    split_raw_fvg_features,
)
from market_data.transforms.resample import resample


def test_split_raw_fvg_features_keeps_model_features_separate() -> None:
    features = pd.DataFrame(
        {
            "ret_1": [0.1],
            "M5_fvg_bull_low": [100.0],
            "M5_fvg_bull_active": [1],
            "M5_fvg_retest_bear": [0],
            "M5_fvg_bear_retest_origin_time_ns": [123.0],
        }
    )

    model_features, raw_features = split_raw_fvg_features(features)

    assert list(model_features.columns) == ["ret_1"]
    assert list(raw_features.columns) == [
        "M5_fvg_bull_low",
        "M5_fvg_bull_active",
        "M5_fvg_retest_bear",
        "M5_fvg_bear_retest_origin_time_ns",
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


def test_feature_block_enabled_prefers_nested_then_flat_configuration() -> None:
    nested_cfg = OmegaConf.create({"smt": {"enabled": False}, "smt_enabled": True})
    flat_cfg = OmegaConf.create({"smt_enabled": False})

    assert not feature_block_enabled(nested_cfg, "smt", True)
    assert not feature_block_enabled(flat_cfg, "smt", True)
    assert feature_block_enabled(None, "smt", True)


def test_resample_market_pair_uses_native_per_symbol_and_derives_missing_frame() -> None:
    index = pd.date_range("2025-01-06 09:00", periods=6, freq="1min", tz="Etc/GMT-3")
    primary_m1 = pd.DataFrame({"open": range(6), "high": range(1, 7)}, index=index)
    secondary_m1 = primary_m1 + 10
    primary_native = pd.DataFrame({"open": [99]}, index=index[:1])

    primary, secondary = resample_market_pair(
        primary_m1,
        secondary_m1,
        "M3",
        primary_timeframes={"M3": primary_native},
    )

    assert primary is primary_native
    assert secondary is not None
    pd.testing.assert_frame_equal(secondary, resample(secondary_m1, "M3"))


def test_source_timeframe_training_mask_excludes_unclosed_source_bars() -> None:
    primary_index = pd.date_range("2025-01-06 09:00", periods=3, freq="1h", tz="Etc/GMT-3")
    source_index = primary_index[:2]
    primary = pd.DataFrame(index=primary_index)
    source = pd.DataFrame(index=source_index)
    train_mask = pd.Series([True, True, False], index=primary_index)

    source_mask = source_timeframe_training_mask(
        source,
        primary,
        train_mask,
        "H1",
        scheduled_closes={},
        session_start="16:30",
    )

    assert source_mask is not None
    assert source_mask.tolist() == [True, False]


def test_source_timeframe_training_mask_handles_missing_train_rows() -> None:
    primary_index = pd.date_range("2025-01-06 09:00", periods=2, freq="1h", tz="Etc/GMT-3")
    primary = pd.DataFrame(index=primary_index)
    source = pd.DataFrame(index=primary_index)

    empty_mask = source_timeframe_training_mask(
        source,
        primary,
        pd.Series(False, index=primary_index),
        "H1",
        scheduled_closes={},
        session_start="16:30",
    )

    assert empty_mask is not None
    assert empty_mask.tolist() == [False, False]
