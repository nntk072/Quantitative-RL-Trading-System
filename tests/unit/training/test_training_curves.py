"""Smoke tests for training-progress plots."""

from __future__ import annotations

import matplotlib
import numpy as np
import pandas as pd
import pytest

matplotlib.use("Agg")

from training.reporting.training_curves import (
    _save_training_html,
    plot_entropy_explvar,
    plot_kl_clip,
    plot_learning_curve,
    plot_learning_rate,
    plot_losses,
    plot_mode_means,
    save_dashboard_plots,
    save_training_plots,
)


@pytest.fixture()
def training_log(tmp_path) -> pd.DataFrame:
    """Synthetic training log with all expected SB3 columns."""
    n = 20
    rng = np.random.default_rng(0)
    df = pd.DataFrame(
        {
            "timestep": np.arange(1, n + 1) * 2048,
            "rollout/ep_rew_mean": rng.normal(0, 1, n).cumsum(),
            "rollout/ep_len_mean": rng.uniform(200, 1000, n),
            "train/policy_gradient_loss": rng.uniform(-0.05, 0.05, n),
            "train/value_loss": rng.uniform(0, 10, n),
            "train/entropy_loss": rng.uniform(-2, -0.5, n),
            "train/approx_kl": rng.uniform(0, 0.02, n),
            "train/clip_fraction": rng.uniform(0, 0.5, n),
            "train/explained_variance": rng.uniform(-0.1, 1.0, n),
            "train/learning_rate": np.full(n, 3e-4),
        }
    )
    path = tmp_path / "training_log.csv"
    df.to_csv(path, index=False)
    return df


def test_plot_learning_curve(training_log, tmp_path):
    plot_learning_curve(training_log, out_path=tmp_path / "lc.png")
    assert (tmp_path / "lc.png").stat().st_size > 0


def test_plot_losses(training_log, tmp_path):
    plot_losses(training_log, out_path=tmp_path / "losses.png")
    assert (tmp_path / "losses.png").stat().st_size > 0


def test_plot_entropy_explvar(training_log, tmp_path):
    plot_entropy_explvar(training_log, out_path=tmp_path / "entropy.png")
    assert (tmp_path / "entropy.png").stat().st_size > 0


def test_plot_kl_clip(training_log, tmp_path):
    plot_kl_clip(training_log, out_path=tmp_path / "kl.png")
    assert (tmp_path / "kl.png").stat().st_size > 0


def test_plot_learning_rate(training_log, tmp_path):
    plot_learning_rate(training_log, out_path=tmp_path / "lr.png")
    assert (tmp_path / "lr.png").stat().st_size > 0


def test_save_training_plots(tmp_path):
    """save_training_plots should generate all 5 PNGs."""
    n = 15
    rng = np.random.default_rng(1)
    df = pd.DataFrame(
        {
            "timestep": np.arange(1, n + 1) * 2048,
            "rollout/ep_rew_mean": rng.normal(0, 1, n),
            "train/policy_gradient_loss": rng.normal(0, 0.01, n),
            "train/value_loss": rng.uniform(0, 5, n),
            "train/entropy_loss": rng.uniform(-2, -0.5, n),
            "train/approx_kl": rng.uniform(0, 0.01, n),
            "train/clip_fraction": rng.uniform(0, 0.3, n),
            "train/explained_variance": rng.uniform(0, 1, n),
            "train/learning_rate": np.full(n, 3e-4),
        }
    )
    log_path = tmp_path / "training_log.csv"
    df.to_csv(log_path, index=False)

    save_training_plots(log_path, out_dir=tmp_path, save_html=False)

    for name in ["learning_curve", "losses", "entropy_explvar", "kl_clip", "lr"]:
        assert (tmp_path / f"{name}.png").stat().st_size > 0, f"Missing {name}.png"


def test_plot_mode_means_skips_a_log_without_those_columns(training_log, tmp_path):
    assert plot_mode_means(training_log, out_path=tmp_path / "mode_means.png") is None
    assert not (tmp_path / "mode_means.png").exists()


def test_plot_mode_means_writes_when_the_columns_exist(tmp_path):
    df = pd.DataFrame(
        {
            "timestep": [2048, 4096, 6144],
            "train/mean_exit": [0.2, 0.4, 0.1],
            "train/mean_direction": [-0.1, -0.3, 0.0],
            "train/mode_prior": [1e-4, 2e-4, 1e-4],
        }
    )
    fig = plot_mode_means(df, out_path=tmp_path / "mode_means.png")
    assert fig is not None
    assert (tmp_path / "mode_means.png").stat().st_size > 0


def test_save_training_plots_empty_log(tmp_path):
    """save_training_plots should not crash on missing/empty log."""
    missing = tmp_path / "nonexistent.csv"
    save_training_plots(missing, out_dir=tmp_path, save_html=False)
    # Should not raise, should create no files
    assert not any(tmp_path.glob("*.png"))


def test_save_training_html_writes_each_available_metric_family(tmp_path):
    pytest.importorskip("plotly")
    frame = pd.DataFrame(
        {
            "timestep": [1, 2],
            "rollout/ep_rew_mean": [0.1, 0.2],
            "train/policy_gradient_loss": [-0.1, -0.2],
            "train/value_loss": [1.0, 0.8],
            "train/entropy_loss": [-1.0, -0.8],
            "train/explained_variance": [0.2, 0.3],
            "train/approx_kl": [0.01, 0.02],
            "train/clip_fraction": [0.1, 0.2],
            "train/learning_rate": [0.001, 0.0005],
            "train/mean_exit": [0.1, 0.2],
            "train/mean_direction": [-0.1, 0.0],
            "train/mode_prior": [0.5, 0.6],
        }
    )

    _save_training_html(frame, tmp_path)

    assert {
        "learning_curve.html",
        "losses.html",
        "entropy_explvar.html",
        "kl_clip.html",
        "lr.html",
        "mode_means.html",
    } <= {path.name for path in tmp_path.glob("*.html")}


def test_save_training_plots_handles_single_sample_metrics_without_html(tmp_path):
    log_path = tmp_path / "single_sample.csv"
    pd.DataFrame(
        {
            "timestep": [2048],
            "rollout/ep_rew_mean": [0.4],
            "train/learning_rate": [3e-4],
        }
    ).to_csv(log_path, index=False)
    out_dir = tmp_path / "single_sample_plots"

    save_training_plots(log_path, out_dir=out_dir, save_html=True)

    assert (out_dir / "learning_curve.png").is_file()
    assert (out_dir / "lr.png").is_file()
    assert not list(out_dir.glob("*.html"))
    assert not (out_dir / "mode_means.png").exists()


def test_save_dashboard_plots(tmp_path):
    log_path = tmp_path / "dashboard_log.csv"
    pd.DataFrame(
        {
            "timestep": [8192, 16384],
            "pnl": [0.1, -0.2],
            "action_mean": [0.1, -0.1],
            "action_std": [1.0, 0.9],
            "long": [0.2, 0.3],
            "short": [0.3, 0.2],
            "flat": [0.5, 0.5],
            "structure_sl": [0.4, 0.5],
            "structure_tp": [0.6, 0.5],
            "grad_norm": [1.2, 0.8],
            "return_pct": [1.0, ""],
            "eval_max_drawdown_pct": [0.2, 0.3],
            "eval_total_pnl": [100.0, -200.0],
            "avg_trade": [10.0, -20.0],
            "sharpe": [0.5, ""],
            "sortino": [0.7, 0.6],
            "profit_factor": [1.2, 0.8],
            "win_rate": [0.6, 0.4],
            "n_trades": [10, 20],
            "turnover": [0.3, 0.4],
        }
    ).to_csv(log_path, index=False)
    out = tmp_path / "plots"
    save_dashboard_plots(log_path, out_dir=out, save_html=False)
    for name in (
        "dashboard_return",
        "dashboard_pnl",
        "dashboard_sharpe",
        "dashboard_profit_factor",
        "dashboard_win_rate",
        "dashboard_trade_count",
        "dashboard_turnover",
        "dashboard_reward",
        "dashboard_behavior",
        "dashboard_risk",
        "dashboard_grad_norm",
    ):
        assert (out / f"{name}.png").stat().st_size > 0


@pytest.mark.parametrize(
    "frame",
    [pd.DataFrame(), pd.DataFrame({"pnl": [1.0]})],
    ids=("empty", "missing-timestep"),
)
def test_save_dashboard_plots_skips_logs_without_dashboard_timesteps(frame, tmp_path):
    log_path = tmp_path / "incomplete_dashboard.csv"
    frame.to_csv(log_path, index=False)
    out_dir = tmp_path / "incomplete_plots"

    save_dashboard_plots(log_path, out_dir=out_dir)

    assert not list(out_dir.glob("*.png"))
    assert not list(out_dir.glob("*.html"))


def test_save_dashboard_plots_coerces_bad_values_and_writes_html(tmp_path):
    pytest.importorskip("plotly")
    log_path = tmp_path / "dashboard_mixed_values.csv"
    pd.DataFrame(
        {
            "timestep": [2048, 4096, 6144],
            "return_pct": ["1.5", "not-a-number", "2.0"],
        }
    ).to_csv(log_path, index=False)
    out_dir = tmp_path / "dashboard_mixed_values"

    save_dashboard_plots(log_path, out_dir=out_dir, save_html=True)

    assert (out_dir / "dashboard_return.png").stat().st_size > 0
    assert (out_dir / "dashboard_return.html").stat().st_size > 0
    assert not (out_dir / "dashboard_pnl.png").exists()
