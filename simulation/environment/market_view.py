"""Lightweight numpy-backed row views for TradingEnv hot path.

Avoids per-step ``pd.Series`` / ``bars.iloc`` construction while remaining
duck-compatible with strategy APIs that expect Series-like ``.get`` /
``__getitem__`` / ``.index`` membership.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True, slots=True)
class BarView:
    """OHLC (+ optional spread) for a single bar without pandas."""

    open: float
    high: float
    low: float
    close: float
    spread: float = float("nan")

    def __getitem__(self, key: str) -> float:
        """Process BarView.

        Args:
            key: Text or path value identifying the key.

        Returns:
            Numeric result returned by ``__getitem__``.
        """
        if key == "open":
            return self.open
        if key == "high":
            return self.high
        if key == "low":
            return self.low
        if key == "close":
            return self.close
        if key == "spread":
            return self.spread
        raise KeyError(key)

    def get(self, key: str, default: Any = None) -> Any:
        """Return an OHLC/spread value, using ``default`` for unknown fields.

        Args:
            key: Text or path value identifying the key.
            default: Default used by the operation described above.

        Returns:
            Result of return an OHLC/spread value, using ``default`` for unknown fields.
        """
        try:
            return self[key]
        except KeyError:
            return default

    @property
    def index(self) -> frozenset[str]:
        """Return names of fields available on this bar, including valid spread.

        Returns:
            Result of return names of fields available on this bar, including valid spread.
        """
        keys = {"open", "high", "low", "close"}
        if np.isfinite(self.spread):
            keys = keys | {"spread"}
        return frozenset(keys)


class FeatureRow:
    """Zero-copy view of one feature-matrix row (numpy + column map)."""

    __slots__ = ("_values", "_col_to_idx", "_index", "decision_at_ms")

    def __init__(
        self,
        values: np.ndarray[Any, Any],
        col_to_idx: dict[str, int],
        decision_at_ms: int | None = None,
    ) -> None:
        """Initialize FeatureRow and its owned state.

        Args:
            values: Values to process, in input order.
            col_to_idx: Key-value data used for the col to idx.
            decision_at_ms: Decision at ms used by the operation described above.
        """
        self._values = values
        self._col_to_idx = col_to_idx
        self.decision_at_ms = decision_at_ms
        # Strategies use ``col not in row.index`` / ``col in row.index``.
        self._index = col_to_idx

    @property
    def index(self) -> dict[str, int]:
        """Return the feature-name to column-index mapping for this row.

        Returns:
            Mapping from ``str`` keys to ``int`` values.
        """
        return self._index

    def get(self, key: str, default: Any = np.nan) -> Any:
        """Return a feature value as float or ``default`` when the column is absent.

        Args:
            key: Text or path value identifying the key.
            default: Default used by the operation described above.

        Returns:
            Result of return a feature value as float or ``default`` when the column is absent.
        """
        idx = self._col_to_idx.get(key)
        if idx is None:
            return default
        return float(self._values[idx])

    def __getitem__(self, key: str) -> float:
        """Process FeatureRow.

        Args:
            key: Text or path value identifying the key.

        Returns:
            Numeric result returned by ``__getitem__``.
        """
        idx = self._col_to_idx[key]
        return float(self._values[idx])

    def __contains__(self, key: object) -> bool:
        """Process FeatureRow.

        Args:
            key: Key used by the operation described above.

        Returns:
            Whether contains meets the requested condition.
        """
        return key in self._col_to_idx

    def __iter__(self) -> Iterator[str]:
        """Iterate over FeatureRow.

        Returns:
            Each iter value, yielded in processing order.
        """
        return iter(self._col_to_idx)
