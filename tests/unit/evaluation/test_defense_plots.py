"""Smoke tests for defense EDA charts."""

from __future__ import annotations

from typing import cast

import matplotlib
import numpy as np
import pandas as pd
import pytest
from matplotlib.patches import Rectangle

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from evaluation.plotting import __all__ as plotting_exports
from evaluation.plotting import data as data_package
from evaluation.plotting import data_plots, plots, plots_interactive, po3_plots
from evaluation.plotting import defense_plots as legacy_defense
from evaluation.plotting.data import (
    defense as data_defense,
)
from evaluation.plotting.data import (
    exploration as data_exploration,
)
from evaluation.plotting.data import (
    po3 as data_po3,
)
from evaluation.plotting.defense_plots import (
    plot_activity_24h,
    plot_coverage_with_gaps,
    plot_curated_feature_hists,
    plot_event_rates,
    plot_ifvg_event_study,
    plot_ifvg_occupancy_monthly,
    plot_ny_return_tails,
    plot_pca_ifvg,
    plot_spread_regime,
)
from evaluation.plotting.po3_plots import plot_annotated_ny_session


def _bars(n: int = 400) -> pd.DataFrame:
    idx = pd.date_range("2025-01-02 16:30", periods=n, freq="1min", tz="Etc/GMT-3")
    rng = np.random.default_rng(0)
    close = 20000.0 + np.cumsum(rng.normal(0, 1, n))
    return pd.DataFrame(
        {
            "open": close - 0.5,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "tickvol": rng.integers(10, 80, n).astype(float),
            "volume": np.zeros(n),
            "spread": np.where(np.arange(n) < 50, 150.0, 80.0),
        },
        index=idx,
    )


def test_defense_core_pngs(tmp_path) -> None:
    bars = _bars()
    plot_coverage_with_gaps(bars, out_path=tmp_path / "cov.png", dpi=72)
    plot_spread_regime(bars, out_path=tmp_path / "spr.png", dpi=72)
    plot_activity_24h(bars, out_path=tmp_path / "act.png", dpi=72)
    plot_ny_return_tails(bars, out_path=tmp_path / "ret.png", dpi=72)
    for name in ("cov.png", "spr.png", "act.png", "ret.png"):
        assert (tmp_path / name).stat().st_size > 0


def test_data_family_activity_chart_uses_grouped_tick_volume(tmp_path) -> None:
    bars = _bars(120)
    output = tmp_path / "grouped" / "activity.png"

    figure = data_package.plot_activity_24h(bars, out_path=output, dpi=72)

    assert output.is_file() and output.stat().st_size > 0
    assert len(figure.axes) == 1
    axis = figure.axes[0]
    bar_index = pd.DatetimeIndex(bars.index)
    expected_activity = bars["tickvol"].groupby(bar_index.hour * 60 + bar_index.minute).mean()
    assert axis.get_title() == "24h activity (tickvol; CFD vol ignored)"
    assert len(axis.lines) == 1
    np.testing.assert_array_equal(axis.lines[0].get_xdata(), expected_activity.index)
    np.testing.assert_allclose(axis.lines[0].get_ydata(), expected_activity.to_numpy())
    plt.close(figure)


def test_data_package_exports_and_legacy_facade_are_stable() -> None:
    expected_exports = [
        "plot_activity_24h",
        "plot_annotated_ny_session",
        "plot_coverage_calendar",
        "plot_coverage_with_gaps",
        "plot_curated_feature_hists",
        "plot_event_rates",
        "plot_feature_histograms",
        "plot_fvg_signals",
        "plot_ifvg_event_study",
        "plot_ifvg_occupancy_monthly",
        "plot_log_return_dist",
        "plot_ny_return_tails",
        "plot_pca_ifvg",
        "plot_session_profile",
        "plot_signal_counts",
        "plot_signals_for_day",
        "plot_spread_regime",
        "plot_split_overlay",
        "write_data_eda",
    ]
    assert data_package.__all__ == expected_exports
    assert all(
        getattr(data_package, name) is getattr(module, name)
        for module, names in (
            (data_defense, data_defense.__all__),
            (data_exploration, data_exploration.__all__),
            (data_po3, data_po3.__all__),
        )
        for name in names
    )
    assert all(
        getattr(legacy_defense, name) is getattr(data_defense, name)
        for name in data_defense.__all__
    )
    assert all(
        getattr(data_plots, name) is getattr(data_exploration, name)
        for name in data_exploration.__all__
    )
    assert all(getattr(po3_plots, name) is getattr(data_po3, name) for name in data_po3.__all__)
    with pytest.raises(AttributeError, match="has no attribute 'unknown_plot'"):
        unknown_name = "unknown_plot"
        getattr(data_package, unknown_name)


def test_plotting_facade_exports_remain_stable() -> None:
    assert plotting_exports == [
        "plot_drawdown",
        "plot_equity_curve",
        "plot_per_trade_orders",
        "plot_per_trade_orders_html",
        "plot_price_with_orders",
    ]
    assert plots.__all__ == [
        "BREACH_COLOR",
        "CLOSE_COLOR",
        "EQUITY_COLOR",
        "LONG_COLOR",
        "PEAK_COLOR",
        "SHORT_COLOR",
        "STYLE",
        "_apply_style",
        "_axis_date_format",
        "_candle_body_days",
        "_close_time_label",
        "_draw_dd_panel",
        "_extend_trade_window",
        "_extract_window",
        "_pair_trades",
        "_per_trade_equity",
        "_plot_price_line_fallback",
        "_save",
        "_structure_anchors",
        "_trade_filename",
        "plot_baseline_comparison",
        "plot_daily_pnl",
        "plot_direction_summary",
        "plot_drawdown",
        "plot_equity_curve",
        "plot_monthly_returns_heatmap",
        "plot_per_trade_orders",
        "plot_price_with_orders",
        "plot_returns_dist",
        "plot_trade_pnl_hist",
    ]
    assert plots_interactive.__all__ == [
        "plot_equity_curve",
        "plot_drawdown",
        "plot_daily_pnl",
        "plot_trade_pnl_hist",
        "plot_returns_dist",
        "plot_monthly_returns_heatmap",
        "plot_baseline_comparison",
        "plot_price_with_orders",
        "plot_per_trade_orders",
        "plot_fvg_signals_interactive",
        "_check",
        "_save",
        "_PLOTLY_AVAILABLE",
    ]


def test_pre_rl_pngs(tmp_path) -> None:
    bars = _bars()
    rng = np.random.default_rng(1)
    feat = pd.DataFrame(
        {
            "rsi": rng.uniform(20, 80, len(bars)),
            "atr": rng.uniform(1, 5, len(bars)),
            "price_in_ifvg_bull": rng.integers(0, 2, len(bars)),
            "po3_distribution": rng.integers(0, 2, len(bars)),
            "entry_long": rng.integers(0, 2, len(bars)),
        },
        index=bars.index,
    )
    plot_event_rates(feat, "2025-01-02", "2025-01-03", out_path=tmp_path / "er.png", dpi=72)
    plot_ifvg_occupancy_monthly(feat, out_path=tmp_path / "occ.png", dpi=72)
    plot_ifvg_event_study(bars, feat, "2025-12-31", horizon=5, out_path=tmp_path / "es.png", dpi=72)
    plot_pca_ifvg(feat, "2025-12-31", max_points=200, out_path=tmp_path / "pca.png", dpi=72)
    for name in ("er.png", "occ.png", "es.png", "pca.png"):
        assert (tmp_path / name).stat().st_size > 0


def test_annotated_ny_session(tmp_path) -> None:
    bars = _bars()
    feat = pd.DataFrame(
        {
            "entry_long": 0.0,
            "asian_high": 20010.0,
            "asian_low": 19990.0,
            "po3_manipulation_low": 19980.0,
            "price_in_ifvg_bull": 0.0,
        },
        index=bars.index,
    )
    feat.loc[feat.index[10], "entry_long"] = 1.0
    fig = plot_annotated_ny_session(
        bars,
        feat,
        pd.Timestamp("2025-01-02", tz="Etc/GMT-3"),
        out_path=tmp_path / "po3.png",
        dpi=72,
        candle_tf="1min",
    )
    assert (tmp_path / "po3.png").stat().st_size > 0
    assert len(fig.axes) == 1


def test_curated_feature_histogram_renders_binary_rate_and_skips_empty_feature(
    tmp_path,
) -> None:
    index = pd.date_range("2025-01-02 00:00", periods=4, freq="min", tz="UTC")
    features = pd.DataFrame(
        {
            "rsi": [25.0, 40.0, 60.0, 75.0],
            "atr_norm_price": [np.nan, np.inf, -np.inf, np.nan],
            "price_in_ifvg_bull": [0.0, 1.0, 1.0, 1.0],
        },
        index=index,
    )
    output = tmp_path / "curated.png"

    figure = plot_curated_feature_hists(features, out_path=output, dpi=72)

    assert output.is_file()
    assert len(figure.axes) == 3
    assert len(figure.axes[1].patches) == 0
    assert [cast(Rectangle, patch).get_height() for patch in figure.axes[2].patches] == [0.25, 0.75]
    plt.close(figure)
