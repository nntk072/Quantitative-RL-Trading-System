from __future__ import annotations

from typing import Any

import pandas as pd

from evaluation.reporting.trade_setup_plots import (
    write_trade_setup_heatmaps,
    write_trade_setup_learning_plots,
)


def test_thesis_heatmaps_render_for_zero_trade_and_populated_reports(tmp_path) -> None:
    metrics = {
        "selection_matrix": [
            {
                "idea": "fvg_retest",
                "timeframe": "M5",
                "selected_count": 4,
            }
        ],
        "performance_by_idea_timeframe": [
            {
                "idea": "fvg_retest",
                "setup_timeframe": "M5",
                "trade_count": 2,
                "mean_realized_r": 0.5,
            }
        ],
    }

    write_trade_setup_heatmaps(metrics, tmp_path, dpi=50)

    assert (tmp_path / "thesis_selection_heatmap.png").is_file()
    assert (tmp_path / "thesis_performance_heatmap.png").is_file()

    empty_metrics: dict[str, Any] = {
        "selection_matrix": [],
        "performance_by_idea_timeframe": [],
    }
    write_trade_setup_heatmaps(empty_metrics, tmp_path, dpi=50)
    assert (tmp_path / "thesis_selection_heatmap.png").stat().st_size > 0
    assert (tmp_path / "thesis_performance_heatmap.png").stat().st_size > 0


def test_thesis_learning_plots_use_rollout_diagnostics(tmp_path) -> None:
    diagnostics = tmp_path / "learning_diagnostics.csv"
    pd.DataFrame(
        {
            "timestep": [16, 32],
            "thesis/no_trade_rate": [0.7, 0.5],
            "thesis/no_trade_rate_when_eligible": [0.6, 0.4],
            "thesis/trade_eligible_step_rate": [0.8, 0.9],
            "thesis/entropy_mean_nats": [1.2, 1.0],
        }
    ).to_csv(diagnostics, index=False)

    outputs = write_trade_setup_learning_plots(diagnostics, tmp_path, dpi=50)

    assert {path.name for path in outputs} == {"thesis_activity.png", "thesis_entropy.png"}
    assert all(path.is_file() and path.stat().st_size > 0 for path in outputs)


def test_canonical_trade_setup_learning_plots_use_canonical_columns(tmp_path) -> None:
    diagnostics = tmp_path / "learning_diagnostics.csv"
    pd.DataFrame(
        {
            "timestep": [16, 32],
            "trade_setup/no_trade_rate": [0.7, 0.5],
            "trade_setup/no_trade_rate_when_eligible": [0.6, 0.4],
            "trade_setup/trade_eligible_step_rate": [0.8, 0.9],
            "trade_setup/entropy_mean_nats": [1.2, 1.0],
        }
    ).to_csv(diagnostics, index=False)

    outputs = write_trade_setup_learning_plots(diagnostics, tmp_path, dpi=50)

    assert {path.name for path in outputs} == {
        "trade_setup_activity.png",
        "trade_setup_entropy.png",
    }
    assert all(path.is_file() and path.stat().st_size > 0 for path in outputs)


def test_canonical_trade_setup_heatmaps_use_canonical_filenames(tmp_path) -> None:
    write_trade_setup_heatmaps(
        {
            "wire_schema": "trade_setup",
            "selection_matrix": [],
            "performance_by_idea_timeframe": [],
        },
        tmp_path,
        dpi=50,
    )

    assert (tmp_path / "trade_setup_selection_heatmap.png").is_file()
    assert (tmp_path / "trade_setup_performance_heatmap.png").is_file()
