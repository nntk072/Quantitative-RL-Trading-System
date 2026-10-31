"""Deprecated compatibility imports for persisted trade-thesis terminology."""

from features.context.trade_setup_candidates import (  # noqa: F401
    active_thesis_candidates,
    active_trade_setup_candidates,
    thesis_candidate_feature_columns,
    thesis_candidate_mask,
    trade_setup_candidate_feature_columns,
    trade_setup_candidate_mask,
)

__all__ = [
    "active_thesis_candidates",
    "active_trade_setup_candidates",
    "thesis_candidate_feature_columns",
    "thesis_candidate_mask",
    "trade_setup_candidate_feature_columns",
    "trade_setup_candidate_mask",
]
