"""Render a causal swing-level and order-block preview from M1 source bars.

Example:
    .venv/bin/python scripts/research/plot_swing_order_block_preview.py \
        --bars data/US100.cash_M1_202412300105_202610162349.csv \
        --end 2025-12-31 --timeframe M1

The preview is a market-context illustration, not a trade or a performance
result. It selects the latest bar before ``--end`` where a live order block and
a valid, previously confirmed swing leg coexist. No future bars are used to
form the selected row's context.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import cast

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.patches import Rectangle

from features.context.order_blocks import build_order_block_features
from features.context.swing_retracement import (
    SWING_LEVELS,
    build_swing_retracement_features,
    level_token,
)
from features.technical.structure import structure_levels
from market_data.loading.bars import load_bars
from market_data.transforms.resample import TF, resample

DEFAULT_BARS = "data/US100.cash_M1_202412300105_202610162349.csv"
DEFAULT_OUTPUT = "outputs/research/swing_order_block_preview"
TIMEFRAMES: tuple[TF, ...] = ("M1", "M3", "M5", "M10", "M15", "M30", "H1", "H4", "D1")


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bars", type=Path, default=Path(DEFAULT_BARS))
    parser.add_argument("--end", default="2025-12-31", help="last local-market date to inspect")
    parser.add_argument("--timeframe", choices=TIMEFRAMES, default="M1")
    parser.add_argument("--window-bars", type=int, default=180)
    parser.add_argument("--swing-period", type=int, default=5)
    parser.add_argument("--output-dir", type=Path, default=Path(DEFAULT_OUTPUT))
    parser.add_argument("--timezone", default="Etc/GMT-3")
    return parser.parse_args()


def _load_bars(path: Path, timezone: str, timeframe: TF) -> pd.DataFrame:
    bars = load_bars(path)
    index = pd.DatetimeIndex(bars.index)
    if index.tz is None:
        bars.index = index.tz_localize(timezone)
    else:
        bars.index = index.tz_convert(timezone)
    return resample(bars, timeframe)


def _end_boundary(value: str, timezone: str) -> pd.Timestamp:
    end = pd.Timestamp(value)
    if end.tzinfo is None:
        end = end.tz_localize(timezone)
    else:
        end = end.tz_convert(timezone)
    if end == end.normalize():
        return end + pd.Timedelta(days=1)
    return end


def _select_bar(
    bars: pd.DataFrame,
    order_blocks: pd.DataFrame,
    retracements: pd.DataFrame,
    end_exclusive: pd.Timestamp,
) -> int:
    ob_active = (order_blocks["ob_bull_active"] > 0.0) | (order_blocks["ob_bear_active"] > 0.0)
    eligible = (
        (bars.index < end_exclusive)
        & ob_active.to_numpy()
        & (retracements["standard_deviation_leg_valid"].to_numpy() > 0.0)
    )
    positions = np.flatnonzero(eligible)
    if positions.size == 0:
        raise ValueError(
            "No bar before --end has both an active order block and a valid confirmed swing leg."
        )
    return int(positions[-1])


def _candles(ax: Axes, bars: pd.DataFrame, start: int, stop: int) -> None:
    shown = bars.iloc[start:stop]
    width = 0.62
    for position, (_, row) in enumerate(shown.iterrows()):
        opened = float(row["open"])
        high = float(row["high"])
        low = float(row["low"])
        closed = float(row["close"])
        color = "#14866d" if closed >= opened else "#c34b4b"
        ax.vlines(position, low, high, color=color, linewidth=0.8, zorder=3)
        body_low = min(opened, closed)
        body_height = max(abs(closed - opened), 0.01)
        ax.add_patch(
            Rectangle(
                (position - width / 2.0, body_low),
                width,
                body_height,
                facecolor=color,
                edgecolor=color,
                linewidth=0.5,
                zorder=4,
            )
        )
    tick_positions = np.linspace(0, max(0, len(shown) - 1), num=min(7, len(shown)), dtype=int)
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(
        [shown.index[int(i)].strftime("%b %d %H:%M") for i in tick_positions],
        rotation=20,
        ha="right",
    )
    ax.grid(axis="y", alpha=0.2)
    ax.set_ylabel("US100 price")


def _plot_swing_levels(
    bars: pd.DataFrame,
    retracements: pd.DataFrame,
    structure: pd.DataFrame,
    selected: int,
    window_bars: int,
    timeframe: TF,
    output_path: Path,
) -> dict[str, float]:
    start = max(0, selected - window_bars + 1)
    stop = selected + 1
    bar_index = pd.DatetimeIndex(bars.index)
    row = retracements.iloc[selected]
    structure_row = structure.iloc[selected]
    level_prices: dict[str, float] = {}
    for level in SWING_LEVELS:
        column = f"standard_deviation_level_{level_token(level)}_price"
        value = float(row[column])
        if np.isfinite(value):
            level_prices[f"{level:g}"] = value

    fig, ax = plt.subplots(figsize=(15, 8), constrained_layout=True)
    _candles(ax, bars, start, stop)
    shown = bars.iloc[start:stop]
    values = shown[["high", "low"]].to_numpy(dtype=float)
    span = max(float(np.ptp(values)), 1e-6)
    y_min = float(values[:, 1].min() - 0.12 * span)
    y_max = float(values[:, 0].max() + 0.12 * span)

    high_time = pd.Timestamp(structure_row["last_swing_high_time"])
    low_time = pd.Timestamp(structure_row["last_swing_low_time"])
    swing_high = float(structure_row["last_swing_high"])
    swing_low = float(structure_row["last_swing_low"])
    is_up_leg = high_time > low_time
    level_orientation = (
        "Up/long idea: level 1 = swing low; level 0 = swing high."
        if is_up_leg
        else "Down/short idea: level 1 = swing high; level 0 = swing low."
    )
    endpoint_labels = (
        {"1": "Level 1 · swing low", "0": "Level 0 · swing high"}
        if is_up_leg
        else {"1": "Level 1 · swing high", "0": "Level 0 · swing low"}
    )
    anchors = (
        [
            (low_time, swing_low, "Level 1 · swing low"),
            (high_time, swing_high, "Level 0 · swing high"),
        ]
        if high_time > low_time
        else [
            (high_time, swing_high, "Level 1 · swing high"),
            (low_time, swing_low, "Level 0 · swing low"),
        ]
    )
    anchor_x = [
        bar_index.get_indexer(pd.DatetimeIndex([stamp]), method="nearest")[0] - start
        for stamp, _, _ in anchors
    ]
    if all(0 <= x < len(shown) for x in anchor_x):
        anchor_prices = [price for _, price, _ in anchors]
        ax.plot(anchor_x, anchor_prices, color="#202a44", linewidth=2.2, zorder=5)
        ax.scatter(anchor_x, anchor_prices, color="#202a44", s=26, zorder=6)
        for x, (_, anchor_price, anchor_label) in zip(anchor_x, anchors, strict=True):
            horizontal = "left" if x < len(shown) / 2 else "right"
            ax.annotate(
                anchor_label,
                (x, anchor_price),
                xytext=(6 if horizontal == "left" else -6, 7),
                textcoords="offset points",
                ha=horizontal,
                fontsize=8,
                color="#202a44",
                bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.8, "pad": 1.5},
                zorder=7,
            )

    visible: list[str] = []
    hidden: list[str] = []
    for level in SWING_LEVELS:
        label = f"{level:g}"
        price = level_prices.get(label)
        if price is None or not y_min <= price <= y_max:
            if price is not None and level <= -4.0:
                hidden.append(f"{label}={price:.2f}")
            continue
        is_extension = level < 0.0
        color = "#8765aa" if is_extension else "#4582a1"
        style = "--" if is_extension else ":"
        ax.axhline(price, color=color, linestyle=style, linewidth=1.1, alpha=0.9)
        visible.append(f"{label} {price:.2f}")
        ax.text(
            0.01,
            price,
            endpoint_labels.get(label, f"Fib/SD {label}"),
            transform=ax.get_yaxis_transform(),
            ha="left",
            va="bottom",
            fontsize=8,
            color=color,
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.72, "pad": 1.5},
        )

    ax.set_ylim(y_min, y_max)
    selected_time = bar_index[selected]
    ax.set_title(
        f"US100 {timeframe} — confirmed swing Fib/SD levels at {selected_time:%Y-%m-%d %H:%M %Z}\n"
        f"{level_orientation} Negative levels extend beyond level 0."
    )
    footer = "Visible levels: " + (", ".join(visible) if visible else "none in this price window")
    if hidden:
        footer += "\nOff-view TP references: " + ", ".join(hidden)
    footer += "\nOff-view levels -6 and -8 remain swing-based TP references for every entry idea."
    fig.text(0.01, -0.02, footer, fontsize=8, va="top")
    fig.savefig(output_path, dpi=170, bbox_inches="tight")
    plt.close(fig)
    return level_prices


def _plot_order_block(
    bars: pd.DataFrame,
    order_blocks: pd.DataFrame,
    selected: int,
    window_bars: int,
    timeframe: TF,
    output_path: Path,
) -> dict[str, float | str]:
    row = order_blocks.iloc[selected]
    sides = [side for side in ("bull", "bear") if float(row[f"ob_{side}_active"]) > 0.0]
    if not sides:
        raise ValueError("Selected bar has no active order block")
    side = min(sides, key=lambda value: float(row[f"ob_{value}_age"]))
    lower = float(row[f"ob_{side}_low"])
    upper = float(row[f"ob_{side}_high"])
    midpoint = float(row[f"ob_{side}_mid"])
    origin_ms = float(row[f"ob_{side}_origin_time_ms"])
    bar_index = pd.DatetimeIndex(bars.index)
    if bar_index.tz is None:
        raise ValueError("order-block plot requires timezone-aware source bars")
    origin_time = pd.to_datetime(origin_ms, unit="ms", utc=True).tz_convert(bar_index.tz)
    origin_position = int(bar_index.searchsorted(origin_time, side="left"))
    start = max(0, selected - window_bars + 1)
    stop = selected + 1
    origin_in_view = max(start, origin_position)

    fig, ax = plt.subplots(figsize=(15, 8), constrained_layout=True)
    _candles(ax, bars, start, stop)
    color = "#27966f" if side == "bull" else "#c64f55"
    x0 = max(0, origin_in_view - start) - 0.45
    x1 = stop - start - 0.5
    ax.add_patch(
        Rectangle(
            (x0, lower),
            max(x1 - x0, 0.5),
            upper - lower,
            facecolor=color,
            edgecolor=color,
            linewidth=1.4,
            alpha=0.22,
            zorder=2,
        )
    )
    ax.axhline(lower, color=color, linewidth=1.0, alpha=0.85)
    ax.axhline(upper, color=color, linewidth=1.0, alpha=0.85)
    ax.axhline(
        midpoint, color=color, linestyle="--", linewidth=1.6, label=f"OB midpoint {midpoint:.2f}"
    )
    ax.axvline(origin_in_view - start, color=color, linestyle=":", linewidth=1.1)
    ax.text(
        0.01,
        upper,
        f"{side.upper()} OB  {lower:.2f}–{upper:.2f}\nMidpoint {midpoint:.2f}",
        transform=ax.get_yaxis_transform(),
        ha="left",
        va="bottom",
        fontsize=9,
        color=color,
        bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.8, "pad": 2.0},
    )
    ax.legend(loc="upper right")
    ax.set_title(
        f"US100 {timeframe} — {side.capitalize()} Order Block\n"
        f"Last opposing candle before displacement; source {origin_time:%Y-%m-%d %H:%M %Z}; "
        f"active at {bars.index[selected]:%Y-%m-%d %H:%M %Z}"
    )
    fig.savefig(output_path, dpi=170, bbox_inches="tight")
    plt.close(fig)
    return {"side": side, "low": lower, "high": upper, "midpoint": midpoint}


def main() -> None:
    args = _arguments()
    if args.window_bars < 20:
        raise ValueError("--window-bars must be at least 20")
    timeframe = cast(TF, args.timeframe)
    bars = _load_bars(args.bars, args.timezone, timeframe)
    end_exclusive = _end_boundary(args.end, args.timezone)
    bars = bars.loc[bars.index < end_exclusive]
    if bars.empty:
        raise ValueError("No source bars remain on or before the requested training date")
    order_blocks = build_order_block_features(bars, swing_period=args.swing_period)
    retracements = build_swing_retracement_features(bars, swing_period=args.swing_period)
    structure = structure_levels(bars, swing_period=args.swing_period)
    selected = _select_bar(bars, order_blocks, retracements, end_exclusive)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    swing_path = args.output_dir / "swing_fib_sd_levels.png"
    order_block_path = args.output_dir / "order_block_with_midpoint.png"
    level_prices = _plot_swing_levels(
        bars,
        retracements,
        structure,
        selected,
        args.window_bars,
        timeframe,
        swing_path,
    )
    order_block = _plot_order_block(
        bars,
        order_blocks,
        selected,
        args.window_bars,
        timeframe,
        order_block_path,
    )
    metadata = {
        "bars_file": str(args.bars),
        "timeframe": timeframe,
        "selected_time": bars.index[selected].isoformat(),
        "swing_period": args.swing_period,
        "swing_trade_idea": "long"
        if structure.iloc[selected]["last_swing_high_time"]
        > structure.iloc[selected]["last_swing_low_time"]
        else "short",
        "level_1_anchor": "swing_low"
        if structure.iloc[selected]["last_swing_high_time"]
        > structure.iloc[selected]["last_swing_low_time"]
        else "swing_high",
        "level_0_anchor": "swing_high"
        if structure.iloc[selected]["last_swing_high_time"]
        > structure.iloc[selected]["last_swing_low_time"]
        else "swing_low",
        "swing_levels": level_prices,
        "order_block": order_block,
        "swing_plot": str(swing_path),
        "order_block_plot": str(order_block_path),
        "note": "Causal feature preview from source bars; not a trade or performance result.",
    }
    metadata_path = args.output_dir / "preview_metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
