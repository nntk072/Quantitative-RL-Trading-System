"""Tests for MAE/MFE, hold-time, win-rate, and time-of-day diagnostic charts."""

from __future__ import annotations

from typing import cast

import matplotlib
from matplotlib.collections import PathCollection

matplotlib.use("Agg")

import pandas as pd
import pytest

from evaluation.metrics.trade_diagnostics import (
    closed_trades_table,
    mae_mfe_table,
    rolling_win_rate,
    weekday_hour_pnl,
)
from evaluation.plotting import (
    diagnostics as diagnostics_package,
)
from evaluation.plotting import (
    distribution_plots as legacy_distributions,
)
from evaluation.plotting import (
    diversity as legacy_diversity,
)
from evaluation.plotting import (
    trade_plots as legacy_trade,
)
from evaluation.plotting.trade_plots import (
    plot_hold_time_pnl,
    plot_mae_mfe,
    plot_mae_mfe_html,
    plot_rolling_winrate,
    plot_tod_heatmap,
    write_trade_diagnostics,
)


def _trades() -> pd.DataFrame:
    idx = pd.date_range("2026-03-02 16:30", periods=40, freq="15min")
    rows: list[dict[str, object]] = []
    for i, t in enumerate(idx[::4]):
        close_i = min(i * 4 + 2, len(idx) - 1)
        rows.append(
            {
                "type": "open",
                "direction": 1 if i % 2 == 0 else -1,
                "price": 20000.0 + i,
                "time": t,
                "bar": i * 4,
                "lots": 1.0,
            }
        )
        rows.append(
            {
                "type": "tp_close" if i % 3 == 0 else "close",
                "direction": 1 if i % 2 == 0 else -1,
                "price": 20000.0 + i + (5 if i % 2 == 0 else -4),
                "time": idx[close_i],
                "bar": close_i,
                "pnl": 20.0 if i % 2 == 0 else -8.0,
            }
        )
    return pd.DataFrame(rows)


def test_diagnostics_package_exports_and_legacy_modules_are_stable() -> None:
    expected = [
        "plot_hold_time_pnl",
        "plot_hold_time_pnl_html",
        "plot_holding_time_hist",
        "plot_mae_mfe",
        "plot_mae_mfe_html",
        "plot_pnl_box_by_regime",
        "plot_pnl_histogram",
        "plot_rolling_winrate",
        "plot_rolling_winrate_html",
        "plot_tod_heatmap",
        "plot_tod_heatmap_html",
        "render_decision_diversity_figures",
        "write_distribution_artifacts",
        "write_trade_diagnostics",
    ]
    assert diagnostics_package.__all__ == expected
    for legacy_module in (legacy_trade, legacy_distributions, legacy_diversity):
        for name in legacy_module.__all__:
            assert getattr(diagnostics_package, name) is getattr(legacy_module, name)
    unknown_diagnostic = "unknown_diagnostic"
    with pytest.raises(AttributeError, match="unknown_diagnostic"):
        getattr(diagnostics_package, unknown_diagnostic)


def _bars() -> pd.DataFrame:
    import numpy as np

    idx = pd.date_range("2026-03-02 16:30", periods=40, freq="15min")
    close = 20000.0 + np.linspace(0, 10, 40)
    return pd.DataFrame(
        {
            "open": close - 0.5,
            "high": close + 2.0,
            "low": close - 2.0,
            "close": close,
        },
        index=idx,
    )


def test_closed_trades_table_hold_time() -> None:
    closed = closed_trades_table(_trades())
    assert not closed.empty
    assert (closed["hold_min"] > 0).all()
    assert set(closed["win"].unique()).issubset({True, False})


def test_rolling_win_rate_window() -> None:
    closed = closed_trades_table(_trades())
    roll = rolling_win_rate(closed, window=5)
    assert len(roll) == len(closed)
    assert roll.dropna().between(0, 100).all()


def test_weekday_hour_heatmap_shape() -> None:
    import numpy as np

    closed = closed_trades_table(_trades())
    matrix, weekdays, hours = weekday_hour_pnl(closed)
    assert matrix.shape[0] == 7
    assert len(weekdays) == 7
    assert len(hours) == matrix.shape[1]
    assert np.isfinite(matrix).any()


def test_empty_trade_ledgers_return_empty_diagnostic_shapes() -> None:
    empty = pd.DataFrame()

    assert closed_trades_table(empty).empty
    assert mae_mfe_table(_bars(), empty).empty
    assert rolling_win_rate(empty).empty
    matrix, weekdays, hours = weekday_hour_pnl(empty)
    assert matrix.shape == (7, 0)
    assert weekdays == ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    assert hours == []


def test_mae_mfe_positive_adverse() -> None:
    table = mae_mfe_table(_bars(), _trades(), lots=1.0, contract_size=1.0)
    assert not table.empty
    assert (table["mae_usd"] >= -1e-9).all()
    assert (table["mfe_usd"] >= -1e-9).all()


def test_diagnostic_pngs(tmp_path) -> None:
    write_trade_diagnostics(
        tmp_path,
        _trades(),
        _bars(),
        dpi=72,
        save_plots=True,
        save_html=False,
    )
    for name in ("hold_time_pnl.png", "rolling_winrate.png", "tod_heatmap.png", "mae_mfe.png"):
        path = tmp_path / name
        assert path.exists() and path.stat().st_size > 0


def test_empty_hold_time_still_writes(tmp_path) -> None:
    fig = plot_hold_time_pnl(pd.DataFrame(), out_path=tmp_path / "empty.png", dpi=72)
    assert (tmp_path / "empty.png").stat().st_size > 0
    del fig


def test_empty_trade_diagnostic_plots_return_labeled_fallbacks(tmp_path) -> None:
    empty = pd.DataFrame()
    mae = plot_mae_mfe(empty, out_path=tmp_path / "empty-mae.png", dpi=72)
    rolling = plot_rolling_winrate(empty)
    tod = plot_tod_heatmap(empty)

    assert mae.axes[0].get_title() == "MAE vs MFE"
    assert "No MAE/MFE data" in [text.get_text() for text in mae.axes[0].texts]
    assert mae.axes[0].axison is False
    assert rolling.axes[0].get_title() == "Rolling win rate"
    assert "No closed trades" in [text.get_text() for text in rolling.axes[0].texts]
    assert tod.axes[0].get_title() == "Time-of-day PnL"
    assert "No closed trades" in [text.get_text() for text in tod.axes[0].texts]
    assert (tmp_path / "empty-mae.png").is_file()


def test_mae_mfe_plot_uses_stop_take_profit_markers_and_usd_axes() -> None:
    table = pd.DataFrame(
        [
            {"mae_usd": 2.0, "mfe_usd": 12.0, "win": True, "sl_reached": True, "tp_reached": False},
            {"mae_usd": 3.0, "mfe_usd": 15.0, "win": True, "sl_reached": False, "tp_reached": True},
            {
                "mae_usd": 4.0,
                "mfe_usd": 7.0,
                "win": False,
                "sl_reached": False,
                "tp_reached": False,
            },
        ]
    )

    figure = plot_mae_mfe(table)

    axis = figure.axes[0]
    assert axis.get_xlabel() == "MAE (USD, adverse)"
    assert axis.get_ylabel() == "MFE (USD, favorable)"
    assert [
        cast(PathCollection, collection).get_sizes().tolist() for collection in axis.collections[:3]
    ] == [
        [55],
        [55],
        [36],
    ]
    legend = axis.get_legend()
    assert legend is not None
    assert {text.get_text() for text in legend.get_texts()} == {
        "Win",
        "Loss",
        "SL reached",
        "TP reached",
        "MAE = MFE",
    }


def test_optional_bars_omit_mae_mfe_artifact(tmp_path) -> None:
    write_trade_diagnostics(
        tmp_path,
        _trades(),
        None,
        dpi=72,
        save_plots=True,
        save_html=False,
    )

    assert (tmp_path / "hold_time_pnl.png").is_file()
    assert (tmp_path / "rolling_winrate.png").is_file()
    assert (tmp_path / "tod_heatmap.png").is_file()
    assert not (tmp_path / "mae_mfe.png").exists()


def test_interactive_mae_mfe_empty_and_close_type_annotations(tmp_path) -> None:
    pytest.importorskip("plotly")
    empty_figure = plot_mae_mfe_html(pd.DataFrame())
    table = pd.DataFrame(
        [
            {
                "mae_usd": 2.0,
                "mfe_usd": 12.0,
                "win": True,
                "sl_reached": False,
                "tp_reached": True,
                "close_type": "tp_close",
            }
        ]
    )

    figure = plot_mae_mfe_html(table, out_path=tmp_path / "mae-mfe.html")

    assert empty_figure.layout.annotations[0].text == "No MAE/MFE data"
    assert [trace.name for trace in figure.data] == ["Win", "MAE = MFE"]
    assert list(figure.data[0].text) == ["tp_close"]
    assert list(figure.data[0].marker.symbol) == ["triangle-up"]
    assert (tmp_path / "mae-mfe.html").is_file()


def test_plot_mae_mfe_and_winrate_smoke(tmp_path) -> None:
    closed = closed_trades_table(_trades())
    mae = mae_mfe_table(_bars(), _trades())
    plot_mae_mfe(mae, out_path=tmp_path / "mae.png", dpi=72)
    plot_rolling_winrate(closed, out_path=tmp_path / "wr.png", dpi=72)
    plot_tod_heatmap(closed, out_path=tmp_path / "tod.png", dpi=72)
    assert (tmp_path / "mae.png").stat().st_size > 0


def test_interactive_hold_time(tmp_path) -> None:
    pytest.importorskip("plotly")
    from evaluation.plotting.trade_plots import plot_hold_time_pnl_html

    plot_hold_time_pnl_html(closed_trades_table(_trades()), out_path=tmp_path / "h.html")
    assert (tmp_path / "h.html").stat().st_size > 0
