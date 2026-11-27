"""Compatibility facade for interactive performance charts."""

from .interactive.performance import (
    plot_daily_pnl,
    plot_drawdown,
    plot_equity_curve,
    plot_monthly_returns_heatmap,
    plot_returns_dist,
    plot_trade_pnl_hist,
)

__all__ = [
    "plot_daily_pnl",
    "plot_drawdown",
    "plot_equity_curve",
    "plot_monthly_returns_heatmap",
    "plot_returns_dist",
    "plot_trade_pnl_hist",
]
