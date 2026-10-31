"""Eligibility of each exact trade idea, timeframe, and direction candidate."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

import numpy as np
import pandas as pd

from decisioning.trade_setup import (
    NO_TRADE_ID,
    TRADE_SETUP_CANDIDATES,
    TRADE_SETUP_CATEGORY_COUNT,
    TradeSetupCandidate,
    trade_setup_candidate_id,
)


def _value_is_active(value: Any) -> bool:
    """Treat any finite positive feature value as an active binary context."""
    if isinstance(value, pd.Series):
        return any(_value_is_active(item) for item in value.tolist())
    if isinstance(value, (list, tuple, np.ndarray)):
        return any(_value_is_active(item) for item in value)
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return False
    return bool(np.isfinite(numeric) and numeric > 0.0)


def _signal_value(row: Mapping[str, Any] | pd.Series | _FeatureRowLike, name: str) -> Any:
    if name not in row:
        return 0.0
    if isinstance(row, pd.Series):
        return row.loc[name]
    return row.get(name, 0.0)


class _FeatureRowLike(Protocol):
    def get(self, key: str, default: Any = ...) -> Any: ...

    def __getitem__(self, key: str) -> Any: ...

    def __iter__(self) -> Any: ...

    def __contains__(self, key: object) -> bool: ...


def active_trade_setup_candidates(
    row: Mapping[str, Any] | pd.Series | _FeatureRowLike,
) -> tuple[TradeSetupCandidate, ...]:
    """Return active candidates from their exact per-timeframe feature columns."""
    active: list[TradeSetupCandidate] = []
    for candidate in TRADE_SETUP_CANDIDATES[1:]:
        assert candidate.idea is not None
        assert candidate.setup_timeframe is not None
        side = "long" if candidate.direction == 1 else "short"
        column = f"entry_idea_{candidate.idea}_{candidate.setup_timeframe}_{side}"
        if _value_is_active(_signal_value(row, column)):
            active.append(candidate)
    return tuple(active)


def trade_setup_candidate_feature_columns() -> tuple[tuple[int, str], ...]:
    """Map each candidate ID to the exact per-timeframe eligibility feature."""
    columns: list[tuple[int, str]] = []
    for candidate in TRADE_SETUP_CANDIDATES[1:]:
        assert candidate.idea is not None
        assert candidate.setup_timeframe is not None
        side = "long" if candidate.direction == 1 else "short"
        name = f"entry_idea_{candidate.idea}_{candidate.setup_timeframe}_{side}"
        columns.append((candidate.candidate_id, name))
    return tuple(columns)


def trade_setup_candidate_mask(
    row: Mapping[str, Any] | pd.Series | _FeatureRowLike,
) -> np.ndarray[Any, np.dtype[np.float32]]:
    """Build the stable eligibility mask, with NO_TRADE always available."""
    mask = np.zeros(TRADE_SETUP_CATEGORY_COUNT, dtype=np.float32)
    mask[NO_TRADE_ID] = 1.0
    for candidate in active_trade_setup_candidates(row):
        assert candidate.idea is not None
        assert candidate.setup_timeframe is not None
        mask[
            trade_setup_candidate_id(candidate.idea, candidate.setup_timeframe, candidate.direction)
        ] = 1.0
    return mask


# Compatibility aliases. The feature names stored in observations remain unchanged.
active_thesis_candidates = active_trade_setup_candidates
thesis_candidate_feature_columns = trade_setup_candidate_feature_columns
thesis_candidate_mask = trade_setup_candidate_mask

__all__ = [
    "active_trade_setup_candidates",
    "trade_setup_candidate_feature_columns",
    "trade_setup_candidate_mask",
    "active_thesis_candidates",
    "thesis_candidate_feature_columns",
    "thesis_candidate_mask",
]
