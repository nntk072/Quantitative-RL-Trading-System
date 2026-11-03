"""Adapters for deterministic, precomputed position targets."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .step_indexed_strategy import BaseStrategy


class SignalSeriesStrategy(BaseStrategy):
    """Expose a validated continuous-action series through ``BaseStrategy``.

    Values use the continuous environment contract: positive requests long
    exposure, negative requests short exposure, and zero selects no trade.
    The input must already be causal and aligned to the evaluated bar rows.
    """

    def __init__(self, signals: pd.Series) -> None:
        """Validate and retain one position target per input bar.

        Args:
            signals: Continuous action values in ``[-1, 1]`` aligned to bars.

        Raises:
            TypeError: If ``signals`` is not a pandas Series.
            ValueError: If the series is empty, non-finite, or out of bounds.
        """
        if not isinstance(signals, pd.Series):
            raise TypeError("signals must be a pandas Series")
        if signals.empty:
            raise ValueError("signals must not be empty")
        try:
            values = signals.to_numpy(dtype=float, copy=True)
        except (TypeError, ValueError) as exc:
            raise ValueError("signals must be numeric") from exc
        if not np.isfinite(values).all():
            raise ValueError("signals must be finite")
        if ((values < -1.0) | (values > 1.0)).any():
            raise ValueError("signals must be in [-1, 1]")
        self._signals = values
        super().__init__(len(values))

    def _signal(self, idx: int) -> float:
        """Return the precomputed target at ``idx``."""
        return float(self._signals[idx])
