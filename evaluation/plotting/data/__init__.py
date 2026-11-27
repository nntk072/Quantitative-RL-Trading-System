"""Market-data and diagnostic evaluation charts, loaded lazily by family."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "plot_activity_24h": (".defense", "plot_activity_24h"),
    "plot_annotated_ny_session": (".po3", "plot_annotated_ny_session"),
    "plot_coverage_calendar": (".exploration", "plot_coverage_calendar"),
    "plot_coverage_with_gaps": (".defense", "plot_coverage_with_gaps"),
    "plot_curated_feature_hists": (".defense", "plot_curated_feature_hists"),
    "plot_event_rates": (".defense", "plot_event_rates"),
    "plot_feature_histograms": (".exploration", "plot_feature_histograms"),
    "plot_fvg_signals": (".po3", "plot_fvg_signals"),
    "plot_ifvg_event_study": (".defense", "plot_ifvg_event_study"),
    "plot_ifvg_occupancy_monthly": (".defense", "plot_ifvg_occupancy_monthly"),
    "plot_log_return_dist": (".exploration", "plot_log_return_dist"),
    "plot_ny_return_tails": (".defense", "plot_ny_return_tails"),
    "plot_pca_ifvg": (".defense", "plot_pca_ifvg"),
    "plot_session_profile": (".exploration", "plot_session_profile"),
    "plot_signal_counts": (".exploration", "plot_signal_counts"),
    "plot_signals_for_day": (".exploration", "plot_signals_for_day"),
    "plot_spread_regime": (".defense", "plot_spread_regime"),
    "plot_split_overlay": (".exploration", "plot_split_overlay"),
    "write_data_eda": (".exploration", "write_data_eda"),
}

__all__ = [
    "plot_activity_24h",
    "plot_annotated_ny_session",
    "plot_coverage_calendar",
    "plot_coverage_with_gaps",
    "plot_curated_feature_hists",
    "plot_event_rates",
    "plot_feature_histograms",
    "plot_fvg_signals",
    "plot_ifvg_event_study",
    "plot_ifvg_occupancy_monthly",
    "plot_log_return_dist",
    "plot_ny_return_tails",
    "plot_pca_ifvg",
    "plot_session_profile",
    "plot_signal_counts",
    "plot_signals_for_day",
    "plot_spread_regime",
    "plot_split_overlay",
    "write_data_eda",
]


def __getattr__(name: str) -> Any:
    """Resolve a lazily exported plotting symbol.

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
