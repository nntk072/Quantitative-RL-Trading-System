"""Compact trade-setup choice, performance, and PPO-learning plots."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from decisioning.trade_setup import TRADE_SETUP_IDEAS, TRADE_SETUP_TIMEFRAMES


def write_trade_setup_heatmaps(metrics: dict[str, Any], split_dir: Path, dpi: int) -> None:
    """Write 6-by-9 choice and outcome heatmaps with cell support counts.

    Args:
        metrics: Key-value data used for the metrics.
        split_dir: Text or path value identifying the split dir.
        dpi: Resolution of generated plots, in dots per inch.
    """
    selection_rows = metrics.get("selection_matrix", [])
    performance_rows = metrics.get("performance_by_idea_timeframe", [])
    if not isinstance(selection_rows, list) or not isinstance(performance_rows, list):
        return
    import matplotlib.pyplot as plt

    file_prefix = "trade_setup"
    display_name = "trade setup"

    selection = _matrix_from_rows(selection_rows, "selected_count")
    _plot_matrix(
        selection,
        title=f"Primary {display_name} selections",
        colorbar_label="Selected decision bars",
        output_path=split_dir / f"{file_prefix}_selection_heatmap.png",
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
            f"Mean realized R by primary {display_name}"
            if use_realized_r
            else f"Mean net PnL by primary {display_name}"
        ),
        colorbar_label=("Mean realized R" if use_realized_r else "Mean net PnL (account currency)"),
        output_path=split_dir / f"{file_prefix}_performance_heatmap.png",
        dpi=dpi,
        format_value=lambda value: f"{value:.2f}",
        support=counts,
    )
    plt.close("all")


def write_trade_setup_learning_plots(csv_path: Path, output_dir: Path, dpi: int) -> list[Path]:
    """Plot rollout-level setup-selection activity and entropy from PPO training.

    Args:
        csv_path: Path or filename identifying the csv.
        output_dir: Text or path value identifying the output dir.
        dpi: Resolution of generated plots, in dots per inch.

    Returns:
        Path returned by ``write_trade_setup_learning_plots``.
    """
    if not csv_path.is_file():
        return []
    frame = pd.read_csv(csv_path)
    prefix = "trade_setup"
    required = {"timestep", f"{prefix}/no_trade_rate", f"{prefix}/entropy_mean_nats"}
    if not required.issubset(frame.columns) or frame.empty:
        return []

    import matplotlib.pyplot as plt

    output_dir.mkdir(parents=True, exist_ok=True)
    x = pd.to_numeric(frame["timestep"], errors="coerce")
    outputs: list[Path] = []
    fig, axis = plt.subplots(figsize=(11, 5))
    axis.plot(x, frame[f"{prefix}/no_trade_rate"], label="NO_TRADE, all decision bars")
    eligible_key = f"{prefix}/no_trade_rate_when_eligible"
    if eligible_key in frame:
        axis.plot(x, frame[eligible_key], label="NO_TRADE when a setup is eligible")
    eligible_coverage_key = f"{prefix}/trade_eligible_step_rate"
    if eligible_coverage_key in frame:
        axis.plot(x, frame[eligible_coverage_key], label="Bars with an eligible trade setup")
    axis.set(xlabel="Environment timesteps", ylabel="Decision-bar rate", ylim=(-0.02, 1.02))
    axis.set_title("Trade-setup activity during PPO training")
    axis.grid(True, alpha=0.25)
    axis.legend(loc="best")
    fig.tight_layout()
    file_prefix = "trade_setup"
    activity_path = output_dir / f"{file_prefix}_activity.png"
    fig.savefig(activity_path, dpi=dpi)
    plt.close(fig)

    outputs.append(activity_path)

    fig, axis = plt.subplots(figsize=(11, 5))
    entropy = pd.to_numeric(frame[f"{prefix}/entropy_mean_nats"], errors="coerce")
    axis.plot(x, entropy, color="#245c9f", label="Masked trade-setup entropy")
    axis.set(xlabel="Environment timesteps", ylabel="Entropy (nats)")
    axis.set_title("Primary trade-setup entropy during PPO training")
    axis.grid(True, alpha=0.25)
    axis.legend(loc="best")
    fig.tight_layout()
    entropy_path = output_dir / f"{file_prefix}_entropy.png"
    fig.savefig(entropy_path, dpi=dpi)
    plt.close(fig)
    outputs.append(entropy_path)
    return outputs


def _complete_performance_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Process performance rows.

    Args:
        rows: Items supplied for the rows, in input order.

    Returns:
        Mapping from ``str`` keys to ``Any]`` values.
    """
    indexed = {(str(row.get("idea")), str(row.get("setup_timeframe"))): row for row in rows}
    return [
        indexed.get(
            (idea, timeframe), {"idea": idea, "setup_timeframe": timeframe, "trade_count": 0}
        )
        for idea in TRADE_SETUP_IDEAS
        for timeframe in TRADE_SETUP_TIMEFRAMES
    ]


def _matrix_from_rows(rows: list[dict[str, Any]], value_key: str) -> NDArray[np.float64]:
    """Process from rows.

    Args:
        rows: Items supplied for the rows, in input order.
        value_key: Text or path value identifying the value key.

    Returns:
        Array returned by ``_matrix_from_rows``.
    """
    indexed = {
        (str(row.get("idea")), str(row.get("timeframe", row.get("setup_timeframe")))): row
        for row in rows
    }
    matrix = np.full(
        (len(TRADE_SETUP_IDEAS), len(TRADE_SETUP_TIMEFRAMES)), np.nan, dtype=np.float64
    )
    for idea_index, idea in enumerate(TRADE_SETUP_IDEAS):
        for timeframe_index, timeframe in enumerate(TRADE_SETUP_TIMEFRAMES):
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
    """Process matrix.

    Args:
        values: Values to process, in input order.
        title: Text or path value identifying the title.
        colorbar_label: Text or path value identifying the colorbar label.
        output_path: Path at which to write the output.
        dpi: Resolution of generated plots, in dots per inch.
        format_value: Format value used by the operation described above.
        support: Support used by the operation described above.
    """
    import matplotlib.pyplot as plt

    indexed = np.ma.masked_invalid(values)  # type: ignore[no-untyped-call]
    fig, axis = plt.subplots(figsize=(13, 7))
    image = axis.imshow(indexed, aspect="auto", cmap="viridis")
    axis.set_xticks(
        range(len(TRADE_SETUP_TIMEFRAMES)), TRADE_SETUP_TIMEFRAMES, rotation=45, ha="right"
    )
    axis.set_yticks(range(len(TRADE_SETUP_IDEAS)), TRADE_SETUP_IDEAS)
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


__all__ = [
    "write_trade_setup_heatmaps",
    "write_trade_setup_learning_plots",
]
