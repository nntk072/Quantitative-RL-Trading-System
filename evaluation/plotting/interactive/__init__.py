"""Interactive Plotly charts grouped by chart family."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "plot_baseline_comparison": (".comparison", "plot_baseline_comparison"),
    "plot_daily_pnl": (".performance", "plot_daily_pnl"),
    "plot_drawdown": (".performance", "plot_drawdown"),
    "plot_equity_curve": (".performance", "plot_equity_curve"),
    "plot_fvg_signals_interactive": (".po3", "plot_fvg_signals_interactive"),
    "plot_monthly_returns_heatmap": (".performance", "plot_monthly_returns_heatmap"),
    "plot_per_trade_orders": (".orders", "plot_per_trade_orders"),
    "plot_price_with_orders": (".orders", "plot_price_with_orders"),
    "plot_returns_dist": (".performance", "plot_returns_dist"),
    "plot_trade_pnl_hist": (".performance", "plot_trade_pnl_hist"),
}

__all__ = [
    "plot_baseline_comparison",
    "plot_daily_pnl",
    "plot_drawdown",
    "plot_equity_curve",
    "plot_fvg_signals_interactive",
    "plot_monthly_returns_heatmap",
    "plot_per_trade_orders",
    "plot_price_with_orders",
    "plot_returns_dist",
    "plot_trade_pnl_hist",
]


def __getattr__(name: str) -> Any:
    """Resolve a lazily exported interactive plotting symbol.

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
