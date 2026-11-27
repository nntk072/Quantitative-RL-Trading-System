"""Trade, distribution, and decision-diversity charts with lazy exports."""

from importlib import import_module
from typing import Any

_EXPORT_MODULES = {
    "plot_hold_time_pnl": "trade",
    "plot_hold_time_pnl_html": "trade",
    "plot_holding_time_hist": "distributions",
    "plot_mae_mfe": "trade",
    "plot_mae_mfe_html": "trade",
    "plot_pnl_box_by_regime": "distributions",
    "plot_pnl_histogram": "distributions",
    "plot_rolling_winrate": "trade",
    "plot_rolling_winrate_html": "trade",
    "plot_tod_heatmap": "trade",
    "plot_tod_heatmap_html": "trade",
    "render_decision_diversity_figures": "diversity",
    "write_distribution_artifacts": "distributions",
    "write_trade_diagnostics": "trade",
}

__all__ = [
    "plot_hold_time_pnl",
    "plot_hold_time_pnl_html",
    "plot_holding_time_hist",
    "plot_mae_mfe",
    "plot_mae_mfe_html",
    "plot_pnl_box_by_regime",
    "plot_pnl_histogram",
    "plot_rolling_winrate",
    "plot_rolling_winrate_html",
    "plot_tod_heatmap",
    "plot_tod_heatmap_html",
    "render_decision_diversity_figures",
    "write_distribution_artifacts",
    "write_trade_diagnostics",
]


def __getattr__(name: str) -> Any:
    """Resolve a lazily exported diagnostic plotting symbol.

    Args:
        name: Public symbol requested by the caller.

    Returns:
        The symbol from its owning module.
    """
    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(f".{module_name}", __name__)
    return getattr(module, name)
