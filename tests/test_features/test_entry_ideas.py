"""Separate, overlapping trading idea features and causal swing retracements."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from features.context.entry_ideas import build_entry_idea_features, entry_idea_context
from features.context.swing_retracement import (
    SWING_LEVELS,
    build_swing_retracement_features,
    level_token,
)
from features.pipeline.schema import select_obs_columns
from features.technical.structure import structure_levels


def _bars(closes: list[float]) -> pd.DataFrame:
    close = np.asarray(closes, dtype=float)
    index = pd.date_range("2025-01-06 16:30", periods=len(close), freq="1min")
    return pd.DataFrame(
        {
            "open": close,
            "high": close + 0.1,
            "low": close - 0.1,
            "close": close,
        },
        index=index,
    )


def test_entry_ideas_are_multi_hot_and_keep_source_timeframes() -> None:
    source = pd.DataFrame(
        {
            "M5_po3_distribution": [1.0],
            "M5_po3_distribution_direction": [1.0],
            "M5_po3_distribution_after_ifvg": [1.0],
            "M5_ifvg_bull_active": [1.0],
            "M5_ob_bull_retest": [1.0],
            "M15_fvg_retest_bull": [1.0],
            "H1_standard_deviation_entry_long": [1.0],
        }
    )

    ideas = build_entry_idea_features(source)
    context = entry_idea_context(pd.concat([source, ideas], axis=1).iloc[0], 1)
    model_features = select_obs_columns(ideas)

    assert ideas.loc[0, "entry_idea_long_count"] == 4.0
    assert ideas.loc[0, "entry_idea_overlap_long"] == 1.0
    assert set(ideas.columns).issubset(model_features.columns)
    assert context["ideas"] == ["po3", "order_block", "standard_deviation", "fvg_retest"]
    assert context["timeframes"] == {
        "po3": ["M5"],
        "order_block": ["M5"],
        "standard_deviation": ["H1"],
        "fvg_retest": ["M15"],
    }
    assert context["gap_reactions"] == {"FVG": ["M15"]}


def test_gap_reaction_context_keeps_fvg_and_ifvg_distinct() -> None:
    row = pd.Series(
        {
            "entry_idea_fvg_retest_long": 1.0,
            "M3_fvg_retest_bull": 1.0,
            "H1_ifvg_retest_bull": 1.0,
        }
    )

    context = entry_idea_context(row, 1)

    assert context["ideas"] == ["fvg_retest"]
    assert context["gap_reactions"] == {"FVG": ["M3"], "IFVG": ["H1"]}


def test_entry_ideas_handle_duplicate_input_columns_and_keep_overlapping_contexts() -> None:
    # Feature blocks can contain repeated labels after concatenation. Selecting
    # such a label by name returns a DataFrame, so consume source columns by
    # position and preserve every active idea.
    source = pd.DataFrame(
        [[1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]],
        columns=[
            "M5_po3_distribution",
            "M5_po3_distribution_direction",
            "M5_po3_distribution_direction",
            "M5_po3_distribution_after_ifvg",
            "M5_ifvg_bull_active",
            "M5_ob_bull_retest",
            "M5_ob_bull_retest",
            "M15_fvg_retest_bull",
        ],
    )

    ideas = build_entry_idea_features(source)
    context = entry_idea_context(pd.concat([source, ideas], axis=1).iloc[0], 1)

    assert ideas.loc[0, "entry_idea_long_count"] == 3.0
    assert ideas.loc[0, "entry_idea_overlap_long"] == 1.0
    assert context["ideas"] == ["po3", "order_block", "fvg_retest"]
    assert context["timeframes"] == {
        "po3": ["M5"],
        "order_block": ["M5"],
        "fvg_retest": ["M15"],
    }


def test_po3_context_records_only_the_ifvg_used_for_distribution() -> None:
    row = pd.Series(
        {
            "entry_idea_po3_long": 1.0,
            "M5_po3_distribution": 1.0,
            "M5_po3_distribution_direction": 1.0,
            "M5_po3_distribution_after_ifvg": 1.0,
            "M5_ifvg_bull_active": 1.0,
            "po3_ifvg_confirmation_tf_code": 15.0,
            "po3_ifvg_low": 100.0,
            "po3_ifvg_high": 101.0,
            "po3_ifvg_time_ns": 1_735_000_000_000_000_000,
            "po3_ifvg_fvg_origin_time_ns": 1_734_999_000_000_000_000,
            "M5_fvg_bull_active": 1.0,
            "M5_fvg_bull_low": 98.0,
            "M5_fvg_bull_high": 99.0,
        }
    )

    context = entry_idea_context(row, 1, include_zones=True)

    assert context["ideas"] == ["po3"]
    assert context["zones"] == [
        {
            "idea": "po3",
            "family": "fvg",
            "timeframe": "M15",
            "side": "bull",
            "low": 100.0,
            "high": 101.0,
            "start_time_ns": 1_734_999_000_000_000_000,
        },
        {
            "idea": "po3",
            "family": "ifvg",
            "timeframe": "M15",
            "side": "bull",
            "low": 100.0,
            "high": 101.0,
            "start_time_ns": 1_735_000_000_000_000_000,
        },
    ]


def test_fvg_retest_context_records_only_its_active_fvg_for_plot_controls() -> None:
    row = pd.Series(
        {
            "entry_idea_fvg_retest_long": 1.0,
            "M5_fvg_retest_bull": 1.0,
            "M5_fvg_bull_active": 1.0,
            "M5_fvg_bull_low": 100.0,
            "M5_fvg_bull_high": 101.0,
            "M5_ifvg_bull_active": 1.0,
            "M5_ifvg_bull_low": 102.0,
            "M5_ifvg_bull_high": 103.0,
        }
    )

    context = entry_idea_context(row, 1, include_zones=True)

    assert context["ideas"] == ["fvg_retest"]
    assert [zone["family"] for zone in context["zones"]] == ["fvg"]
    assert [(zone["low"], zone["high"]) for zone in context["zones"]] == [(100.0, 101.0)]


@pytest.mark.parametrize(
    ("closes", "side"),
    [
        ([1, 2, 3, 2, 1, 2, 3, 4, 2.2], "long"),
        ([4, 3, 2, 3, 4, 3, 2, 1, 2.9], "short"),
    ],
)
def test_swing_retracement_uses_confirmed_leg_and_050_to_0786_band(
    closes: list[float], side: str
) -> None:
    result = build_swing_retracement_features(_bars(closes), swing_period=1, atr_mult=0.0)

    assert result.iloc[-1][f"standard_deviation_entry_{side}"] == 1.0
    assert result.iloc[-1]["standard_deviation_leg_direction"] == (1.0 if side == "long" else -1.0)
    fraction = result.iloc[-1]["standard_deviation_retracement_fraction"]
    assert 0.5 <= fraction <= 0.786
    assert (
        result.iloc[-1]["standard_deviation_band_low"]
        < result.iloc[-1]["standard_deviation_band_high"]
    )
    for level in SWING_LEVELS:
        token = level_token(level)
        assert f"standard_deviation_level_{token}_price" in result
        assert f"standard_deviation_level_{token}_distance" in result
    assert result.iloc[-1]["standard_deviation_level_0_5_distance"] == pytest.approx(0.0, abs=1.0)


@pytest.mark.parametrize(
    ("closes", "one_anchor", "zero_anchor"),
    [
        ([1, 2, 3, 2, 1, 2, 3, 4, 2.2], "last_swing_low", "last_swing_high"),
        ([4, 3, 2, 3, 4, 3, 2, 1, 2.9], "last_swing_high", "last_swing_low"),
    ],
)
def test_swing_level_endpoints_follow_the_entry_idea_direction(
    closes: list[float], one_anchor: str, zero_anchor: str
) -> None:
    bars = _bars(closes)
    structure = structure_levels(bars, swing_period=1)
    result = build_swing_retracement_features(bars, swing_period=1, atr_mult=0.0)
    row = result.iloc[-1]
    pivots = structure.iloc[-1]

    assert row["standard_deviation_level_1_price"] == pytest.approx(pivots[one_anchor])
    assert row["standard_deviation_level_0_price"] == pytest.approx(pivots[zero_anchor])
    assert row["standard_deviation_leg_direction"] == (
        1.0 if one_anchor == "last_swing_low" else -1.0
    )


def test_swing_retracement_does_not_use_unconfirmed_future_pivot() -> None:
    bars = _bars([1, 2, 3, 2, 1, 2, 3, 4, 2.2])
    prefix = build_swing_retracement_features(bars.iloc[:8], swing_period=1, atr_mult=0.0)
    complete = build_swing_retracement_features(bars, swing_period=1, atr_mult=0.0)

    assert_frame_equal(prefix, complete.iloc[:8])
    assert complete.iloc[7]["standard_deviation_entry_long"] == 0.0
    assert complete.iloc[8]["standard_deviation_entry_long"] == 1.0


def test_swing_extension_levels_expire_when_body_closes_beyond_level_zero() -> None:
    bars = _bars([1, 2, 3, 2, 1, 2, 3, 4, 2.2, 5.0])
    result = build_swing_retracement_features(bars, swing_period=1, atr_mult=0.0)

    assert result.iloc[8]["standard_deviation_leg_valid"] == 1.0
    assert result.iloc[8]["standard_deviation_leg_direction"] == 1.0
    assert np.isfinite(result.iloc[8]["standard_deviation_level_neg_4_price"])
    assert result.iloc[9]["standard_deviation_leg_valid"] == 0.0
    assert result.iloc[9]["standard_deviation_leg_direction"] == 0.0
    assert np.isnan(result.iloc[9]["standard_deviation_level_neg_4_price"])


@pytest.mark.parametrize(
    ("low", "high"),
    [(0.5, 0.5), (-0.1, 0.5), (0.2, 1.1)],
)
def test_swing_retracement_rejects_invalid_band(low: float, high: float) -> None:
    with pytest.raises(ValueError, match="retracement bounds"):
        build_swing_retracement_features(
            _bars([1, 2, 1]), retracement_low=low, retracement_high=high
        )
