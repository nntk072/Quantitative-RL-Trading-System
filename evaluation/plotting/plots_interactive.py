"""Compatibility API for the interactive Plotly chart families."""

from .interactive.comparison import (
    plot_baseline_comparison,
)
from .interactive.orders import (
    plot_per_trade_orders,
    plot_price_with_orders,
)
from .interactive.performance import (
    plot_daily_pnl,
    plot_drawdown,
    plot_equity_curve,
    plot_monthly_returns_heatmap,
    plot_returns_dist,
    plot_trade_pnl_hist,
)
from .interactive.po3 import (
    plot_fvg_signals_interactive,
)
from .interactive.rendering import _PLOTLY_AVAILABLE, _check, _save

__all__ = [
    "plot_equity_curve",
    "plot_drawdown",
    "plot_daily_pnl",
    "plot_trade_pnl_hist",
    "plot_returns_dist",
    "plot_monthly_returns_heatmap",
    "plot_baseline_comparison",
    "plot_price_with_orders",
    "plot_per_trade_orders",
    "plot_fvg_signals_interactive",
    "_check",
    "_save",
    "_PLOTLY_AVAILABLE",
]
