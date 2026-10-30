"""Matplotlib and Plotly adapters for prepared per-trade chart geometry."""

from __future__ import annotations

from typing import Any

import pandas as pd

from evaluation.plotting.order_chart_data import OrderLevels

_ENTRY_LINE = "#546e7a"
_RED = "#e53935"
_GREEN = "#2e7d32"


def draw_order_levels_mpl(
    ax: Any, levels: OrderLevels, stop_updates: pd.DataFrame | None = None
) -> None:
    """Light SL/TP fills, the entry dash, candle marks, and offset arrows."""
    updates = pd.DataFrame() if stop_updates is None else stop_updates.copy()
    if not updates.empty:
        updates = updates.loc[updates["type"].eq("sl_update")].copy()
        time_column = "effective_time" if "effective_time" in updates.columns else "time"
        updates[time_column] = pd.to_datetime(updates[time_column], errors="coerce")
        updates = updates.dropna(subset=[time_column, "price"]).sort_values(time_column)
    labeled_span = False
    for t0, t1 in levels.manip_spans:
        ax.axvspan(
            t0,
            t1,
            color="#7e57c2",
            alpha=0.12,
            linewidth=0,
            zorder=0,
            label="PO3 manipulation phase" if not labeled_span else None,
        )
        labeled_span = True
    labeled_distribution = False
    for t0, t1 in levels.distribution_spans:
        ax.axvspan(
            t0,
            t1,
            color="#26a69a",
            alpha=0.10,
            linewidth=0,
            zorder=0,
            label="PO3 distribution phase" if not labeled_distribution else None,
        )
        labeled_distribution = True
    labeled_end = False
    for ts in levels.manip_ends:
        ax.axvline(
            ts,
            color="#4527a0",
            linewidth=1.0,
            linestyle="-.",
            zorder=2,
            label="manipulation end" if not labeled_end else None,
        )
        labeled_end = True
    if levels.red is not None:
        initial_stop_end = (
            pd.Timestamp(updates.iloc[0][time_column]) if not updates.empty else levels.t_close
        )
        ax.fill_between(
            [levels.t_open, initial_stop_end],
            levels.red[0],
            levels.red[1],
            color=_RED,
            alpha=0.12,
            linewidth=0,
            zorder=0,
        )
    if levels.green is not None:
        ax.fill_between(
            [levels.t_open, levels.t_close],
            levels.green[0],
            levels.green[1],
            color=_GREEN,
            alpha=0.12,
            linewidth=0,
            zorder=0,
        )
    ax.plot(
        [levels.t_open, levels.t_close],
        [levels.entry, levels.entry],
        color=_ENTRY_LINE,
        linewidth=1.0,
        linestyle="--",
        zorder=3,
    )
    seen: set[str] = set()
    labeled_retracement = False
    for seg in levels.segs:
        segment_end = seg.t1
        if not updates.empty and seg.label.startswith("Stop loss"):
            segment_end = pd.Timestamp(updates.iloc[0][time_column])
        ax.plot(
            [seg.t0, segment_end],
            [seg.price, seg.price],
            color=seg.color,
            linewidth=1.0,
            linestyle=seg.linestyle,
            label=(
                "Swing Fibonacci / SD levels"
                if seg.label.startswith("Fib/SD:") and not labeled_retracement
                else seg.label
                if not seg.label.startswith("Fib/SD:") and seg.label not in seen
                else None
            ),
            zorder=3,
        )
        if seg.label.startswith("Fib/SD:"):
            ax.annotate(
                seg.label.removeprefix("Fib/SD: "),
                xy=(segment_end, seg.price),
                xytext=(2, 0),
                textcoords="offset points",
                fontsize=6,
                color=seg.color,
                va="center",
            )
            labeled_retracement = True
        seen.add(seg.label)
        if seg.mark is not None:
            ax.scatter([seg.mark], [seg.price], s=18, color=seg.color, zorder=4, marker="o")
    seen_zones: set[str] = set()
    labeled_zone_midpoint = False
    for zone in levels.zones:
        ax.fill_between(
            [zone.t0, zone.t1],
            zone.low,
            zone.high,
            color=zone.color,
            alpha=0.12,
            linewidth=0,
            label=zone.label if zone.label not in seen_zones else None,
            zorder=1,
        )
        ax.plot(
            [zone.t0, zone.t1],
            [zone.midpoint, zone.midpoint],
            color=zone.color,
            linewidth=0.8,
            linestyle="--",
            alpha=0.8,
            label="Zone midpoint" if not labeled_zone_midpoint else None,
            zorder=2,
        )
        labeled_zone_midpoint = True
        seen_zones.add(zone.label)
    for update_i, (_, update) in enumerate(updates.iterrows()):
        start = pd.Timestamp(update[time_column])
        end = (
            pd.Timestamp(updates.iloc[update_i + 1][time_column])
            if update_i + 1 < len(updates)
            else levels.t_close
        )
        price = float(update["price"])
        ax.plot(
            [start, end],
            [price, price],
            color="#6a1b9a",
            linewidth=1.4,
            linestyle="-.",
            zorder=5,
            label="Active stop after partial" if update_i == 0 else None,
        )
        ax.scatter(
            [start],
            [price],
            marker="D",
            s=24,
            color="#6a1b9a",
            zorder=8,
            label="Stop update" if update_i == 0 else None,
        )
    labeled_sd = False
    for k, price in levels.deviations:
        ax.plot(
            [levels.t_open, levels.t_close],
            [price, price],
            color="#90a4ae",
            linewidth=0.6,
            linestyle=":",
            label=("Selected range projection (not statistical SD)" if not labeled_sd else None),
            zorder=1,
        )
        labeled_sd = True
        ax.annotate(
            f"{k:g}x",
            xy=(levels.t_close, price),
            xytext=(2, 0),
            textcoords="offset points",
            ha="left",
            va="center",
            fontsize=7,
            color="#607d8b",
        )
    _arrow(
        ax, levels.t_open, levels.entry, levels.direction == 1, "#00cc00", levels.offset, "Entry"
    )
    exit_up = levels.direction != 1
    _arrow(ax, levels.t_close, levels.exit_price, exit_up, "#ff0000", levels.offset, "Exit")
    ax.set_ylim(*levels.ylim)
    y0, y1 = levels.ylim
    for label, price, color in levels.off_chart_levels:
        edge = y0 if price < y0 else y1
        marker = "v" if price < y0 else "^"
        ax.scatter(
            [levels.t_close], [edge], marker=marker, s=35, color=color, zorder=7, clip_on=False
        )
        ax.annotate(
            f"{label}: {price:.2f} (outside view)",
            xy=(levels.t_close, edge),
            xytext=(-8, 8 if edge == y1 else -14),
            textcoords="offset points",
            ha="right",
            va="center",
            fontsize=7,
            color=color,
            clip_on=False,
        )


def _arrow(
    ax: Any,
    when: pd.Timestamp,
    price: float,
    point_up: bool,
    color: str,
    offset: float,
    label: str,
) -> None:
    """Triangle whose tip sits on ``price``, a little off the candle."""
    text_y = price - offset if point_up else price + offset
    ax.annotate(
        "",
        xy=(when, price),
        xytext=(when, text_y),
        arrowprops={"arrowstyle": "-|>", "color": color, "mutation_scale": 12, "lw": 1.2},
        zorder=5,
    )
    ax.scatter([], [], marker="^" if point_up else "v", c=color, s=40, label=label)


def draw_order_levels_plotly(fig: Any, levels: OrderLevels) -> None:
    """Plotly twin of :func:`draw_order_levels_mpl`."""
    import plotly.graph_objects as go

    for t0, t1 in levels.manip_spans:
        fig.add_vrect(
            x0=t0,
            x1=t1,
            fillcolor="#7e57c2",
            opacity=0.12,
            line_width=0,
            row=1,
            col=1,
        )
    for t0, t1 in levels.distribution_spans:
        fig.add_vrect(
            x0=t0,
            x1=t1,
            fillcolor="#26a69a",
            opacity=0.10,
            line_width=0,
            row=1,
            col=1,
        )
    for ts in levels.manip_ends:
        fig.add_vline(
            x=ts,
            line_color="#4527a0",
            line_width=1,
            line_dash="dash",
            row=1,
            col=1,
        )

    def _band(band: tuple[float, float] | None, color: str) -> None:
        if band is None:
            return
        fig.add_shape(
            type="rect",
            x0=levels.t_open,
            x1=levels.t_close,
            y0=band[0],
            y1=band[1],
            fillcolor=color,
            opacity=1,
            line_width=0,
            row=1,
            col=1,
        )

    _band(levels.red, "rgba(229,57,53,0.12)")
    _band(levels.green, "rgba(46,125,50,0.12)")
    fig.add_trace(
        go.Scatter(
            x=[levels.t_open, levels.t_close],
            y=[levels.entry, levels.entry],
            mode="lines",
            name="Entry price",
            line=dict(color=_ENTRY_LINE, width=1, dash="dash"),
        ),
        row=1,
        col=1,
    )
    labeled_retracement = False
    for seg in levels.segs:
        fig.add_trace(
            go.Scatter(
                x=[seg.t0, seg.t1],
                y=[seg.price, seg.price],
                mode="lines",
                name=(
                    "Swing Fibonacci / SD levels" if seg.label.startswith("Fib/SD:") else seg.label
                ),
                legendgroup=(
                    "Swing Fibonacci / SD levels" if seg.label.startswith("Fib/SD:") else seg.label
                ),
                showlegend=not seg.label.startswith("Fib/SD:") or not labeled_retracement,
                line=dict(
                    color=seg.color, width=1, dash="dash" if seg.linestyle == "--" else "dot"
                ),
                hovertemplate=f"{seg.label}<br>Price: %{{y:.2f}}<extra></extra>",
            ),
            row=1,
            col=1,
        )
        if seg.label.startswith("Fib/SD:"):
            labeled_retracement = True
        if seg.mark is not None:
            fig.add_trace(
                go.Scatter(
                    x=[seg.mark],
                    y=[seg.price],
                    mode="markers",
                    name=seg.label,
                    showlegend=False,
                    marker=dict(size=7, color=seg.color, symbol="circle"),
                ),
                row=1,
                col=1,
            )
    seen_zones: set[str] = set()
    labeled_zone_midpoint = False
    for zone in levels.zones:
        fig.add_trace(
            go.Scatter(
                x=[zone.t0, zone.t1, zone.t1, zone.t0],
                y=[zone.low, zone.low, zone.high, zone.high],
                fill="toself",
                fillcolor=zone.color,
                opacity=0.12,
                mode="lines",
                line=dict(width=0, color=zone.color),
                name=zone.label,
                legendgroup=zone.label,
                showlegend=zone.label not in seen_zones,
                hovertemplate=f"{zone.label}: %{{y:.2f}}<extra></extra>",
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=[zone.t0, zone.t1],
                y=[zone.midpoint, zone.midpoint],
                mode="lines",
                name="Zone midpoint",
                legendgroup="Zone midpoint",
                showlegend=not labeled_zone_midpoint,
                line=dict(color=zone.color, width=1, dash="dash"),
                hovertemplate=f"{zone.label} midpoint: %{{y:.2f}}<extra></extra>",
            ),
            row=1,
            col=1,
        )
        labeled_zone_midpoint = True
        seen_zones.add(zone.label)
    for k, price in levels.deviations:
        fig.add_trace(
            go.Scatter(
                x=[levels.t_open, levels.t_close],
                y=[price, price],
                mode="lines",
                name=f"Range projection {k:g}x (not statistical SD)",
                line=dict(color="#90a4ae", width=1, dash="dot"),
            ),
            row=1,
            col=1,
        )
    entry_up = levels.direction == 1
    fig.add_trace(
        go.Scatter(
            x=[levels.t_open],
            y=[levels.entry - levels.offset if entry_up else levels.entry + levels.offset],
            mode="markers",
            name="Entry",
            marker=dict(
                symbol="triangle-up" if entry_up else "triangle-down",
                size=12,
                color="#00cc00",
            ),
        ),
        row=1,
        col=1,
    )
    exit_up = levels.direction != 1
    fig.add_trace(
        go.Scatter(
            x=[levels.t_close],
            y=[levels.exit_price - levels.offset if exit_up else levels.exit_price + levels.offset],
            mode="markers",
            name="Exit",
            marker=dict(
                symbol="triangle-up" if exit_up else "triangle-down",
                size=12,
                color="#ff0000",
            ),
        ),
        row=1,
        col=1,
    )
    fig.update_yaxes(range=list(levels.ylim), row=1, col=1)
