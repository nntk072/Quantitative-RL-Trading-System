"""Paired training/testing figures for artifact-driven thesis reports."""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any


def _finite(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _paired_bars(
    ax: Any,
    values: dict[str, dict[str, float]],
    categories: list[str],
    *,
    title: str,
    xlabel: str,
    colors: dict[str, str],
    np: Any,
    top_n: int = 10,
) -> None:
    totals = {
        category: sum(values.get(split, {}).get(category, 0.0) for split in colors)
        for category in categories
    }
    labels = sorted(categories, key=lambda item: (-totals[item], item))[:top_n]
    ax.set_title(title)
    if not labels:
        ax.text(
            0.5, 0.5, "No recorded observations", ha="center", va="center", transform=ax.transAxes
        )
        ax.set_axis_off()
        return
    y = np.arange(len(labels), dtype=float)
    height = 0.36
    for offset, split in ((-height / 2, "training"), (height / 2, "testing")):
        counts = [values.get(split, {}).get(label, 0.0) for label in labels]
        ax.barh(y + offset, counts, height=height, color=colors[split], label=split.capitalize())
    ax.set_yticks(y, labels=labels)
    ax.invert_yaxis()
    ax.set_xlabel(xlabel)
    ax.grid(axis="x", alpha=0.25)
    ax.legend(loc="best")


def generate_train_test_figures(
    report: dict[str, Any], campaign_dir: Path, figure_dir: Path, report_dir: Path
) -> None:
    """Create comparison figures and add their report-relative paths to variants."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd

    colors = {"training": "#1f5a94", "testing": "#e07b24"}

    def read_equity(run_dir: Path, split: str) -> Any:
        path = run_dir / split / "equity.csv"
        if not path.is_file():
            raise FileNotFoundError(f"required split equity data is missing: {path}")
        frame = pd.read_csv(path, index_col=0, parse_dates=True)
        if frame.empty or "equity" not in frame.columns:
            raise ValueError(f"required split equity data is empty or malformed: {path}")
        equity = pd.to_numeric(frame["equity"], errors="coerce")
        values = equity.to_numpy(dtype=float)
        if not np.isfinite(values).all() or np.any(values <= 0.0):
            raise ValueError(f"required split equity data has invalid values: {path}")
        equity.index = pd.DatetimeIndex(frame.index)
        return equity

    for variant in report.get("variants", []):
        run_artifact_dir = variant.get("run_artifact_dir")
        splits = variant.get("splits", {})
        if not isinstance(run_artifact_dir, str) or not all(
            isinstance(splits.get(split), dict) for split in ("training", "testing")
        ):
            continue

        curves = {
            split: read_equity(campaign_dir / run_artifact_dir, split)
            for split in ("training", "testing")
        }
        action_seed = variant.get("seed", "not recorded")
        split_titles = {}
        for split, curve in curves.items():
            start, end = curve.index[0], curve.index[-1]
            date_range = str(start.year) if start.year == end.year else f"{start.year}–{end.year}"
            role = "in-sample" if split == "training" else "report-only"
            split_titles[split] = f"{split.capitalize()} · {date_range} · {role}"
        out_dir = figure_dir / variant["run_key"] / "training_testing_comparison"
        out_dir.mkdir(parents=True, exist_ok=True)
        generated: dict[str, Path] = {}

        # Separate panels preserve actual dates while a shared axis makes equity comparable.
        all_equity = np.concatenate([curve.to_numpy(dtype=float) for curve in curves.values()])
        lower, upper = float(all_equity.min()), float(all_equity.max())
        margin = max((upper - lower) * 0.06, 1.0)
        fig, axes = plt.subplots(1, 2, figsize=(16, 5.8), sharey=True)
        for ax, split in zip(axes, ("training", "testing")):
            equity = curves[split]
            ax.plot(
                equity.index,
                equity.to_numpy(dtype=float),
                color=colors[split],
                linewidth=1.15,
                label=f"One saved stochastic replay (seed {action_seed})",
            )
            ax.axhline(
                float(equity.iloc[0]),
                color="#6b7280",
                linestyle="--",
                linewidth=0.9,
                label="Split starting equity",
            )
            ax.set_title(split_titles[split])
            ax.set_xlabel("Date")
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))  # type: ignore[no-untyped-call]
            ax.grid(True, alpha=0.25)
            ax.legend(loc="best")
        axes[0].set_ylabel("Account equity")
        axes[0].set_ylim(lower - margin, upper + margin)
        fig.suptitle(
            f"{variant['variant']}: one saved stochastic replay (seed {action_seed}; shared scale)"
        )
        fig.autofmt_xdate()
        fig.tight_layout()
        path = out_dir / "train_test_equity.png"
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        generated["train_test_equity"] = path

        drawdowns = {
            split: (curve.cummax() - curve) / curve.cummax() * 100.0
            for split, curve in curves.items()
        }
        dd_max = max(float(series.max()) for series in drawdowns.values())
        fig, axes = plt.subplots(1, 2, figsize=(16, 5.3), sharey=True)
        for ax, split in zip(axes, ("training", "testing")):
            series = drawdowns[split]
            ax.plot(series.index, series.to_numpy(dtype=float), color=colors[split], linewidth=1.0)
            ax.set_title(f"{split_titles[split]} · max {float(series.max()):.2f}%")
            ax.set_xlabel("Date")
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))  # type: ignore[no-untyped-call]
            ax.grid(True, alpha=0.25)
        axes[0].set_ylabel("Drawdown from split running peak (%)")
        axes[0].set_ylim(0.0, max(dd_max * 1.08, 1.0))
        fig.suptitle(
            f"{variant['variant']}: training and testing drawdown (shared scale; diagnostic)"
        )
        fig.autofmt_xdate()
        fig.tight_layout()
        path = out_dir / "train_test_drawdown.png"
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        generated["train_test_drawdown"] = path

        monthly_changes: dict[str, Any] = {}
        for split, equity in curves.items():
            monthly = equity.resample("ME").last().dropna()
            changes = monthly.diff()
            if not changes.empty:
                changes.iloc[0] = float(monthly.iloc[0] - equity.iloc[0])
            monthly_changes[split] = changes
        month_values = [
            float(value)
            for series in monthly_changes.values()
            for value in series.to_numpy(dtype=float)
            if np.isfinite(value)
        ]
        pnl_limit = max(
            max(abs(min(month_values)), abs(max(month_values))) * 1.08 if month_values else 1.0,
            1.0,
        )
        fig, axes = plt.subplots(1, 2, figsize=(16, 5.2), sharey=True)
        for ax, split in zip(axes, ("training", "testing")):
            series = monthly_changes[split]
            labels = [timestamp.strftime("%Y-%m") for timestamp in series.index]
            values = series.to_numpy(dtype=float)
            ax.bar(np.arange(len(values)), values, color=colors[split], alpha=0.88)
            ax.axhline(0.0, color="#333333", linewidth=0.8)
            ax.set_xticks(np.arange(len(values)), labels=labels, rotation=45, ha="right")
            ax.set_title(split_titles[split])
            ax.set_xlabel("Month")
            ax.grid(axis="y", alpha=0.25)
        axes[0].set_ylabel("Change in end-of-month account equity")
        axes[0].set_ylim(-pnl_limit, pnl_limit)
        fig.suptitle(f"{variant['variant']}: monthly P&L from saved equity paths")
        fig.tight_layout()
        path = out_dir / "train_test_monthly_pnl.png"
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        generated["train_test_monthly_pnl"] = path

        metric_specs = (
            ("total_return_pct", "Total return", "%", 100.0),
            ("max_drawdown", "Maximum drawdown", "%", 100.0),
            ("sharpe", "Sharpe ratio", "Ratio", 1.0),
            ("profit_factor", "Profit factor", "Ratio", 1.0),
            ("win_rate", "Win rate", "%", 100.0),
            ("n_trades", "Completed trades", "Trade count", 1.0),
        )
        fig, axes = plt.subplots(2, 3, figsize=(15, 8.2))
        for ax, (metric, title, unit, scale) in zip(axes.flat, metric_specs):
            values = []
            labels = []
            bar_colors = []
            for split in ("training", "testing"):
                value = _finite(splits[split].get("metrics", {}).get(metric))
                if value is not None:
                    values.append(value * scale)
                    labels.append(split.capitalize())
                    bar_colors.append(colors[split])
            if values:
                bars = ax.bar(labels, values, color=bar_colors)
                fmt = "%.0f" if unit == "Trade count" else "%.2f"
                ax.bar_label(bars, fmt=fmt, padding=3)
                ax.axhline(0.0, color="#333333", linewidth=0.7)
            else:
                ax.text(0.5, 0.5, "Not recorded", ha="center", va="center", transform=ax.transAxes)
            ax.set_title(title)
            ax.set_ylabel(unit)
            ax.grid(axis="y", alpha=0.25)
        fig.suptitle(f"{variant['variant']}: training and testing metrics")
        fig.tight_layout()
        path = out_dir / "train_test_metrics.png"
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        generated["train_test_metrics"] = path

        fig, ax = plt.subplots(figsize=(8.8, 5.4))
        outcome_names = ("wins", "losses", "breakeven_within_tolerance")
        x = np.arange(2, dtype=float)
        bottom = np.zeros(2, dtype=float)
        outcome_colors = {
            "wins": "#4c9f70",
            "losses": "#c44e52",
            "breakeven_within_tolerance": "#e6b84c",
        }
        for outcome in outcome_names:
            values = [
                _finite(splits[split].get("counts", {}).get(outcome)) or 0.0
                for split in ("training", "testing")
            ]
            ax.bar(
                x,
                values,
                bottom=bottom,
                label=outcome.replace("_", " "),
                color=outcome_colors[outcome],
            )
            bottom += np.asarray(values, dtype=float)
        ax.set_xticks(x, labels=[split_titles["training"], split_titles["testing"]])
        ax.set_ylabel("Trade count")
        ax.set_title(f"{variant['variant']}: trade outcomes by split")
        ax.legend(title="Net trade result", loc="best")
        ax.grid(axis="y", alpha=0.25)
        fig.tight_layout()
        path = out_dir / "train_test_outcomes.png"
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        generated["train_test_outcomes"] = path

        exit_values: dict[str, dict[str, dict[str, float]]] = {}
        for split in ("training", "testing"):
            breakdown = (
                splits[split].get("exit_breakdown", {}).get("exit_reason_by_net_outcome", {})
            )
            for outcome in ("winning", "losing", "breakeven"):
                for reason, value in breakdown.get(outcome, {}).items():
                    number = _finite(value)
                    if number is not None:
                        exit_values.setdefault(outcome, {}).setdefault(split, {})[str(reason)] = (
                            number
                        )
        fig, axes = plt.subplots(1, 3, figsize=(18, 6.2))
        for ax, outcome in zip(axes, ("winning", "losing", "breakeven")):
            split_data = exit_values.get(outcome, {})
            categories = sorted(
                {reason for reason_map in split_data.values() for reason in reason_map},
                key=lambda reason: (
                    -sum(reason_map.get(reason, 0.0) for reason_map in split_data.values())
                ),
            )
            _paired_bars(
                ax,
                split_data,
                categories,
                title=f"{outcome.capitalize()} trades",
                xlabel="Trade count",
                colors=colors,
                np=np,
                top_n=8,
            )
        fig.suptitle(f"{variant['variant']}: exit reasons by trade outcome and split")
        fig.tight_layout()
        path = out_dir / "train_test_exit_reasons_by_outcome.png"
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        generated["train_test_exit_reasons_by_outcome"] = path

        risk_data: dict[str, list[float]] = {}
        for split in ("training", "testing"):
            raw_values = splits[split].get("plot_data", {}).get("risk_approved", [])
            risk_data[split] = [
                value for item in raw_values if (value := _finite(item)) is not None
            ]
        combined_risk = [value for values in risk_data.values() for value in values]
        fig, axes = plt.subplots(1, 2, figsize=(13, 5.3), sharey=True)
        if combined_risk:
            bin_count = min(25, max(5, int(math.sqrt(len(combined_risk)))))
            bins = np.histogram_bin_edges(combined_risk, bins=bin_count)
            for ax, split in zip(axes, ("training", "testing")):
                if risk_data[split]:
                    ax.hist(
                        risk_data[split], bins=bins, density=True, color=colors[split], alpha=0.7
                    )
                else:
                    ax.text(
                        0.5,
                        0.5,
                        "No saved risk observations",
                        ha="center",
                        va="center",
                        transform=ax.transAxes,
                    )
                ax.set_title(split_titles[split])
                ax.set_xlabel("Approved risk per trade idea (account currency)")
                ax.grid(axis="y", alpha=0.25)
            axes[0].set_ylabel("Density")
        else:
            for ax in axes:
                ax.text(
                    0.5,
                    0.5,
                    "No saved risk observations",
                    ha="center",
                    va="center",
                    transform=ax.transAxes,
                )
                ax.set_axis_off()
        fig.suptitle(f"{variant['variant']}: approved risk distribution (same bins; density scale)")
        fig.tight_layout()
        path = out_dir / "train_test_approved_risk_distribution.png"
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        generated["train_test_approved_risk_distribution"] = path

        setup_values = {
            split: {
                str(name): number
                for name, value in splits[split]
                .get("important_setup", {})
                .get("setup_types", {})
                .items()
                if (number := _finite(value)) is not None
            }
            for split in ("training", "testing")
        }
        fig, ax = plt.subplots(figsize=(11, 6.0))
        _paired_bars(
            ax,
            setup_values,
            sorted({name for values in setup_values.values() for name in values}),
            title=f"{variant['variant']}: setup type frequency by split",
            xlabel="Trade count",
            colors=colors,
            np=np,
            top_n=12,
        )
        fig.tight_layout()
        path = out_dir / "train_test_setup_mix.png"
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        generated["train_test_setup_mix"] = path

        fig, axes = plt.subplots(1, 2, figsize=(19, 8.0))
        for ax, title, field in (
            (axes[0], "Selected stop reference", "sl_breakdown"),
            (axes[1], "Selected target reference", "tp_breakdown"),
        ):
            reference_values = {
                split: {
                    str(name): number
                    for name, value in splits[split]
                    .get(field, {})
                    .get("selected_reference", {})
                    .items()
                    if (number := _finite(value)) is not None
                }
                for split in ("training", "testing")
            }
            _paired_bars(
                ax,
                reference_values,
                sorted({name for values in reference_values.values() for name in values}),
                title=title,
                xlabel="Trade count",
                colors=colors,
                np=np,
                top_n=12,
            )
        fig.suptitle(f"{variant['variant']}: stop and target reference use by split")
        fig.tight_layout()
        path = out_dir / "train_test_sl_tp_references.png"
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        generated["train_test_sl_tp_references"] = path

        for name, path in generated.items():
            if not path.is_file() or path.stat().st_size == 0:
                raise RuntimeError(f"training/testing comparison figure generation failed: {path}")
        variant["comparison_figures"] = {
            name: os.path.relpath(path, report_dir) for name, path in generated.items()
        }
