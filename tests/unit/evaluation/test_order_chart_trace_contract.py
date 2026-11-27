"""Order-chart context follows only feature states known at entry time."""

from __future__ import annotations

import numpy as np
import pandas as pd

from evaluation.metrics.trades import TradeChartMetrics
from evaluation.plotting.chart_overlays import OverlayEvents
from evaluation.plotting.order_chart_data import (
    _manipulation_marks,
    _retracement_segments,
    order_levels,
)


def test_po3_context_does_not_extend_into_feature_rows_after_entry() -> None:
    index = pd.date_range("2025-02-03 15:00", periods=5, freq="min", tz="UTC")
    close = np.full(len(index), 100.0)
    bars = pd.DataFrame(
        {
            "open": close,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
        },
        index=index,
    )
    features = pd.DataFrame(
        {
            "po3_manipulation_active": [1.0] * len(index),
            "po3_distribution": [1.0] * len(index),
            "po3_manipulation_end": [0.0, 0.0, 1.0, 0.0, 1.0],
        },
        index=index,
    )
    metrics = TradeChartMetrics(
        entry_price=100.0,
        exit_price=100.0,
        direction=1,
        mae_price=99.0,
        mfe_price=101.0,
        mae_time=index[0],
        mfe_time=index[1],
        sl_price=None,
        tp_price=None,
        mae_drawn=False,
        mfe_drawn=False,
    )
    open_row = pd.Series(
        {
            "time": index[2],
            "direction": 1,
            "entry_ideas": ["po3"],
            "entry_idea_timeframes": {"po3": ["M1"]},
        }
    )

    levels = order_levels(
        bars,
        metrics,
        OverlayEvents(),
        bars,
        index[2],
        index[4],
        open_row,
        show_mae_mfe=False,
        show_sl_tp=False,
        features=features,
    )

    assert levels.manip_spans == [(index[0], index[2])]
    assert levels.distribution_spans == [(index[0], index[2])]
    assert levels.manip_ends == [index[2]]


def test_retracement_omits_swing_leg_that_had_not_ended_at_entry() -> None:
    index = pd.date_range("2025-02-03 15:00", periods=4, freq="min", tz="UTC")
    window = pd.DataFrame({"low": [99.0] * 4, "high": [101.0] * 4}, index=index)
    features = pd.DataFrame(
        {
            "M5_standard_deviation_leg_start_time_ns": [index[0].value] * 4,
            "M5_standard_deviation_leg_end_time_ns": [index[3].value] * 4,
            "M5_standard_deviation_level_0_5_price": [100.0] * 4,
        },
        index=index,
    )
    open_row = pd.Series(
        {
            "entry_ideas": ["standard_deviation"],
            "entry_idea_timeframes": {"standard_deviation": ["M5"]},
        }
    )

    segments = _retracement_segments(
        features,
        window,
        open_row,
        index[2],
        index[3],
        99.0,
        101.0,
        entry_idea_plot_config={"standard_deviation": {"levels": [0.5]}},
    )

    assert segments == []


def test_po3_plot_setting_can_disable_all_context_marks() -> None:
    index = pd.date_range("2025-02-03 15:00", periods=3, freq="min", tz="UTC")
    window = pd.DataFrame(index=index)
    features = pd.DataFrame(
        {
            "M1_po3_manipulation_active": [1.0, 1.0, 0.0],
            "M1_po3_distribution": [0.0, 1.0, 1.0],
            "M1_po3_manipulation_end": [0.0, 1.0, 0.0],
            "M1_po3_manipulation_high": [101.0] * 3,
            "M1_po3_manipulation_low": [99.0] * 3,
        },
        index=index,
    )
    open_row = pd.Series(
        {"time": index[1], "entry_ideas": ["po3"], "entry_idea_timeframes": {"po3": ["M1"]}}
    )

    context = _manipulation_marks(
        features,
        window,
        index[1],
        index[2],
        1,
        open_row,
        entry_idea_plot_config={"po3": {"enabled": False}},
    )

    assert context == ([], [], [], [])
