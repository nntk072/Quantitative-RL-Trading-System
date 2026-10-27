"""Compact thesis-choice, performance, and PPO-learning plots."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from decisioning.thesis import THESIS_IDEAS, THESIS_TIMEFRAMES


def write_thesis_heatmaps(metrics: dict[str, Any], split_dir: Path, dpi: int) -> None:
    """Write 6-by-9 choice and outcome heatmaps with cell support counts."""
    selection_rows = metrics.get("selection_matrix", [])
    performance_rows = metrics.get("performance_by_idea_timeframe", [])
    if not isinstance(selection_rows, list) or not isinstance(performance_rows, list):
        return
    import matplotlib.pyplot as plt

    selection = _matrix_from_rows(selection_rows, "selected_count")
    _plot_matrix(
        selection,
        title="Primary thesis selections",
        colorbar_label="Selected decision bars",
        output_path=split_dir / "thesis_selection_heatmap.png",
        dpi=dpi,
        format_value=lambda value: f"{int(value)}",
    )

    performance = _complete_performance_rows(performance_rows)
    use_realized_r = any(row.get("mean_realized_r") is not None for row in performance)
    metric_name = "mean_realized_r" if use_realized_r else "mean_pnl"
    values = _matrix_from_rows(performance, metric_name)
    support_name = "realized_r_trade_count" if use_realized_r else "completed_trade_count"
    counts = _matrix_from_rows(performance, support_name)
    _plot_matrix(
        values,
        title=(
            "Mean realized R by primary thesis"
            if use_realized_r
            else "Mean net PnL by primary thesis"
        ),
        colorbar_label=("Mean realized R" if use_realized_r else "Mean net PnL (account currency)"),
        output_path=split_dir / "thesis_performance_heatmap.png",
        dpi=dpi,
        format_value=lambda value: f"{value:.2f}",
        support=counts,
    )
    plt.close("all")


def write_thesis_learning_plots(csv_path: Path, output_dir: Path, dpi: int) -> list[Path]:
    """Plot rollout-level policy activity and thesis entropy from PPO training."""
    if not csv_path.is_file():
        return []
    frame = pd.read_csv(csv_path)
    required = {"timestep", "thesis/no_trade_rate", "thesis/entropy_mean_nats"}
    if not required.issubset(frame.columns) or frame.empty:
        return []

    import matplotlib.pyplot as plt

    output_dir.mkdir(parents=True, exist_ok=True)
    x = pd.to_numeric(frame["timestep"], errors="coerce")
    outputs: list[Path] = []
    fig, axis = plt.subplots(figsize=(11, 5))
    axis.plot(x, frame["thesis/no_trade_rate"], label="NO_TRADE, all decision bars")
    eligible_key = "thesis/no_trade_rate_when_eligible"
    if eligible_key in frame:
        axis.plot(x, frame[eligible_key], label="NO_TRADE when a trade thesis is eligible")
    eligible_coverage_key = "thesis/trade_eligible_step_rate"
    if eligible_coverage_key in frame:
        axis.plot(x, frame[eligible_coverage_key], label="Bars with an eligible trade thesis")
    axis.set(xlabel="Environment timesteps", ylabel="Decision-bar rate", ylim=(-0.02, 1.02))
    axis.set_title("Thesis activity during PPO training")
    axis.grid(True, alpha=0.25)
    axis.legend(loc="best")
    fig.tight_layout()
    activity_path = output_dir / "thesis_activity.png"
    fig.savefig(activity_path, dpi=dpi)
    plt.close(fig)
    outputs.append(activity_path)

    fig, axis = plt.subplots(figsize=(11, 5))
    entropy = pd.to_numeric(frame["thesis/entropy_mean_nats"], errors="coerce")
    axis.plot(x, entropy, color="#245c9f", label="Masked thesis entropy")
    axis.set(xlabel="Environment timesteps", ylabel="Entropy (nats)")
    axis.set_title("Primary-thesis entropy during PPO training")
    axis.grid(True, alpha=0.25)
    axis.legend(loc="best")
    fig.tight_layout()
    entropy_path = output_dir / "thesis_entropy.png"
    fig.savefig(entropy_path, dpi=dpi)
    plt.close(fig)
    outputs.append(entropy_path)
    return outputs


def _complete_performance_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    indexed = {(str(row.get("idea")), str(row.get("setup_timeframe"))): row for row in rows}
    return [
        indexed.get(
            (idea, timeframe), {"idea": idea, "setup_timeframe": timeframe, "trade_count": 0}
        )
        for idea in THESIS_IDEAS
        for timeframe in THESIS_TIMEFRAMES
    ]


def _matrix_from_rows(rows: list[dict[str, Any]], value_key: str) -> NDArray[np.float64]:
    indexed = {
        (str(row.get("idea")), str(row.get("timeframe", row.get("setup_timeframe")))): row
        for row in rows
    }
    matrix = np.full((len(THESIS_IDEAS), len(THESIS_TIMEFRAMES)), np.nan, dtype=np.float64)
    for idea_index, idea in enumerate(THESIS_IDEAS):
        for timeframe_index, timeframe in enumerate(THESIS_TIMEFRAMES):
            value = indexed.get((idea, timeframe), {}).get(value_key)
            try:
                parsed = float(cast(str | int | float, value))
            except (TypeError, ValueError):
                continue
            if np.isfinite(parsed):
                matrix[idea_index, timeframe_index] = parsed
    return matrix


def _plot_matrix(
    values: NDArray[np.float64],
    *,
    title: str,
    colorbar_label: str,
    output_path: Path,
    dpi: int,
    format_value: Any,
    support: NDArray[np.float64] | None = None,
) -> None:
    import matplotlib.pyplot as plt

    indexed = np.ma.masked_invalid(values)  # type: ignore[no-untyped-call]
    fig, axis = plt.subplots(figsize=(13, 7))
    image = axis.imshow(indexed, aspect="auto", cmap="viridis")
    axis.set_xticks(range(len(THESIS_TIMEFRAMES)), THESIS_TIMEFRAMES, rotation=45, ha="right")
    axis.set_yticks(range(len(THESIS_IDEAS)), THESIS_IDEAS)
    axis.set_xlabel("Primary setup timeframe")
    axis.set_ylabel("Primary idea")
    axis.set_title(title)
    colorbar = fig.colorbar(image, ax=axis)
    colorbar.set_label(colorbar_label)
    for row in range(values.shape[0]):
        for column in range(values.shape[1]):
            value = values[row, column]
            if support is None:
                count = 0 if not np.isfinite(value) else int(value)
            else:
                count = 0 if not np.isfinite(support[row, column]) else int(support[row, column])
            text = "—" if not np.isfinite(value) else format_value(float(value))
            if support is not None:
                annotation = f"{text}\nn={count}"
            else:
                annotation = f"{text}"
            axis.text(column, row, annotation, ha="center", va="center", fontsize=7)
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=dpi)
    plt.close(fig)
