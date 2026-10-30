from __future__ import annotations

import pandas as pd
from omegaconf import OmegaConf

from evaluation.reporting.order_chart_regeneration import (
    _chart_feature_config,
    _entry_idea_timeframes,
)


def test_chart_overlay_selection_enables_only_requested_context_families() -> None:
    config = OmegaConf.create(
        {
            "features": {
                "order_blocks": {"enabled": False, "timeframes": ["M5"]},
                "include_fvg_ifvg": False,
                "include_strategy_state": False,
                "ifvg_mtf": {"enabled": False, "timeframes": ["M5"]},
                "structure": {"enabled": True, "timeframes": ["M5"]},
            }
        }
    )

    chart_config = _chart_feature_config(
        config,
        order_block_timeframes=("M1", "H1"),
        fvg_timeframes=(),
        ifvg_timeframes=("M5", "D1"),
        swing_timeframes=("M1", "M5"),
    )

    assert chart_config.features.order_blocks.enabled is True
    assert list(chart_config.features.order_blocks.timeframes) == ["M1", "H1"]
    assert chart_config.features.include_fvg_ifvg is False
    assert chart_config.features.include_strategy_state is True
    assert chart_config.features.ifvg_mtf.enabled is True
    assert list(chart_config.features.ifvg_mtf.timeframes) == ["M5", "D1"]
    assert chart_config.features.structure.enabled is True
    assert list(chart_config.features.structure.timeframes) == ["M5"]
    assert config.features.order_blocks.enabled is False


def test_m1_only_swing_plot_keeps_primary_structure_without_mtf_build() -> None:
    config = OmegaConf.create({"features": {"structure": {"enabled": True}}})

    chart_config = _chart_feature_config(
        config,
        order_block_timeframes=(),
        fvg_timeframes=(),
        ifvg_timeframes=(),
        swing_timeframes=("M1",),
    )

    assert chart_config.features.structure.enabled is False


def test_replot_rebuilds_all_timeframes_used_by_overlapping_trade_ideas() -> None:
    trades = pd.DataFrame(
        [
            {
                "type": "open",
                "entry_ideas": (
                    "['po3', 'fvg_retest', 'ifvg_retest', 'ifvg_unretested', "
                    "'order_block', 'standard_deviation']"
                ),
                "entry_idea_timeframes": (
                    "{'po3': ['M15'], 'fvg_retest': ['M5'], 'ifvg_retest': ['M10'], "
                    "'ifvg_unretested': ['M30'], "
                    "'order_block': ['M3'], 'standard_deviation': ['H1']}"
                ),
            }
        ]
    )
    idea_timeframes = _entry_idea_timeframes(trades)
    config = OmegaConf.create(
        {
            "features": {
                "order_blocks": {"enabled": False, "timeframes": []},
                "entry_ideas": {"enabled": False, "timeframes": []},
                "include_fvg_ifvg": False,
                "include_strategy_state": False,
                "fvg_timeframes": [],
                "ifvg_mtf": {"enabled": False, "timeframes": []},
                "po3_state_mtf": {"enabled": False, "timeframes": []},
                "structure": {"enabled": False, "timeframes": []},
            }
        }
    )

    chart_config = _chart_feature_config(
        config,
        order_block_timeframes=(),
        fvg_timeframes=(),
        ifvg_timeframes=(),
        swing_timeframes=(),
        entry_idea_timeframes=idea_timeframes,
    )

    assert list(chart_config.features.order_blocks.timeframes) == ["M3"]
    assert list(chart_config.features.fvg_timeframes) == ["M5", "M15"]
    assert list(chart_config.features.ifvg_mtf.timeframes) == ["M10", "M15", "M30"]
    assert list(chart_config.features.po3_state_mtf.timeframes) == ["M15"]
    assert list(chart_config.features.entry_ideas.timeframes) == ["H1"]
