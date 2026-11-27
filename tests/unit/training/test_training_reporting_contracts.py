"""Dashboard plots require usable samples and preserve optional HTML output."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from gymnasium import spaces

from training.artifacts.manifests import (
    action_space_width,
    observation_account_dim,
    observation_space_shapes,
)
from training.reporting.training_curves import save_dashboard_plots


def test_dashboard_plot_export_skips_logs_without_timestep_or_numeric_series(
    tmp_path: Path,
) -> None:
    no_timestep = tmp_path / "no-timestep.csv"
    pd.DataFrame({"pnl": [1.0, 2.0], "long": [0.5, 0.5]}).to_csv(no_timestep, index=False)
    first_output = tmp_path / "no-timestep-plots"

    save_dashboard_plots(no_timestep, first_output)

    assert first_output.is_dir()
    assert list(first_output.iterdir()) == []

    invalid_series = tmp_path / "invalid-series.csv"
    pd.DataFrame(
        {
            "timestep": [1, 2],
            "return_pct": ["invalid", ""],
            "pnl": ["n/a", "invalid"],
            "action_mean": ["invalid", "n/a"],
        }
    ).to_csv(invalid_series, index=False)
    second_output = tmp_path / "invalid-series-plots"

    save_dashboard_plots(invalid_series, second_output, save_html=False)

    assert list(second_output.iterdir()) == []


def test_dashboard_plot_export_writes_numeric_png_and_optional_html(
    tmp_path: Path,
) -> None:
    pytest.importorskip("plotly")
    log_path = tmp_path / "training-prefix.csv"
    pd.DataFrame(
        {
            "timestep": [1_000, 2_000],
            "pnl": [1.5, -0.5],
            "long": [0.4, 0.3],
            "flat": [0.6, 0.7],
        }
    ).to_csv(log_path, index=False)
    output = tmp_path / "plots"

    save_dashboard_plots(log_path, output, dpi=40, save_html=True)

    for name in (
        "dashboard_reward.png",
        "dashboard_reward.html",
        "dashboard_behavior.png",
        "dashboard_behavior.html",
    ):
        assert (output / name).is_file()


def test_manifest_serializes_gym_observation_and_action_dimensions_with_fallbacks() -> None:
    env = type(
        "Env",
        (),
        {
            "observation_space": spaces.Dict(
                {
                    "seq": spaces.Box(-1.0, 1.0, (12, 7)),
                    "seq_mask": spaces.Box(0.0, 1.0, (12,)),
                    "account": spaces.Box(-1.0, 1.0, (5,)),
                    "trade_setup_mask": spaces.Box(0.0, 1.0, (109,)),
                    "candidate_mask": spaces.MultiBinary(217),
                }
            ),
            "action_space": spaces.Box(-1.0, 1.0, (6,)),
        },
    )()

    assert observation_account_dim(env) == 5
    assert observation_space_shapes(env) == {
        "seq": [12, 7],
        "seq_mask": [12],
        "account": [5],
        "trade_setup_mask": [109],
        "candidate_mask": [217],
    }
    assert action_space_width(env) == 6
    assert (
        action_space_width(type("DiscreteEnv", (), {"action_space": spaces.Discrete(20)})()) == 20
    )

    no_account = type(
        "NoAccountEnv",
        (),
        {"observation_space": spaces.Dict({"seq": spaces.Box(-1.0, 1.0, (4, 3))})},
    )()
    assert observation_account_dim(no_account) == 0
    assert observation_space_shapes(no_account) == {"seq": [4, 3]}
    assert observation_account_dim(object()) == 0
    assert observation_space_shapes(object()) == {}
