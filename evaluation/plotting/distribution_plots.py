"""Compatibility facade for PnL and trade-distribution charts."""

from .diagnostics.distributions import (
    plot_holding_time_hist,
    plot_pnl_box_by_regime,
    plot_pnl_histogram,
    write_distribution_artifacts,
)

__all__ = [
    "plot_holding_time_hist",
    "plot_pnl_box_by_regime",
    "plot_pnl_histogram",
    "write_distribution_artifacts",
]
