"""Equity, returns, P&L, and comparison charts."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "_draw_dd_panel": (".equity", "_draw_dd_panel"),
    "plot_baseline_comparison": (".comparison", "plot_baseline_comparison"),
    "plot_daily_pnl": (".charts", "plot_daily_pnl"),
    "plot_direction_summary": (".charts", "plot_direction_summary"),
    "plot_drawdown": (".equity", "plot_drawdown"),
    "plot_equity_curve": (".equity", "plot_equity_curve"),
    "plot_monthly_returns_heatmap": (".charts", "plot_monthly_returns_heatmap"),
    "plot_returns_dist": (".charts", "plot_returns_dist"),
    "plot_trade_pnl_hist": (".charts", "plot_trade_pnl_hist"),
}

__all__ = [
    "plot_baseline_comparison",
    "plot_daily_pnl",
    "plot_direction_summary",
    "plot_drawdown",
    "plot_equity_curve",
    "plot_monthly_returns_heatmap",
    "plot_returns_dist",
    "plot_trade_pnl_hist",
]


def __getattr__(name: str) -> Any:
    """Resolve a lazily exported performance plotting symbol.

    Args:
        name: Public symbol requested by the caller.

    Returns:
        The symbol from its owning module.
    """
    try:
        module_name, attribute = _EXPORTS[name]
    except KeyError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
    value = getattr(import_module(module_name, __name__), attribute)
    globals()[name] = value
    return value
