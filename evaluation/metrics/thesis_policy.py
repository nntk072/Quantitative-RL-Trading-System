"""Deprecated compatibility imports for old thesis-policy metric paths."""

from evaluation.metrics.trade_setup_policy import (
    summarize_thesis_decisions,
    summarize_trade_setup_decisions,
)

__all__ = ["summarize_thesis_decisions", "summarize_trade_setup_decisions"]
