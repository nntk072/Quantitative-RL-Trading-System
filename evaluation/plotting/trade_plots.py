"""Compatibility facade for trade diagnostic charts."""

from .diagnostics.trade import (
    plot_hold_time_pnl,
    plot_hold_time_pnl_html,
    plot_mae_mfe,
    plot_mae_mfe_html,
    plot_rolling_winrate,
    plot_rolling_winrate_html,
    plot_tod_heatmap,
    plot_tod_heatmap_html,
    write_trade_diagnostics,
)

__all__ = [
    "plot_hold_time_pnl",
    "plot_hold_time_pnl_html",
    "plot_mae_mfe",
    "plot_mae_mfe_html",
    "plot_rolling_winrate",
    "plot_rolling_winrate_html",
    "plot_tod_heatmap",
    "plot_tod_heatmap_html",
    "write_trade_diagnostics",
]
