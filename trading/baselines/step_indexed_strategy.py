"""Baseline strategy interface.

Strategies can be advanced with ``act()`` when every bar is visited, or queried
by absolute bar index with ``act_at()`` when an environment skips rows. This
keeps precomputed signals aligned to market data without depending on the
observation layout.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from operator import index as integer_index
from typing import Any


class BaseStrategy(ABC):
    """Common interface for all non-learned and learned baselines.

    Subclasses implement :meth:`_signal` (one action per bar index) or
    override :meth:`act` directly. Actions follow the continuous contract
    of ``TradingEnv``: positive = long fraction, negative = short fraction,
    0 = hold/exit.
    """

    def __init__(self, n_bars: int) -> None:
        """Store the expected number of bars and reset the step counter.

        Args:
            n_bars: Length of the pre-computed signal array.
        """
        self._n_bars = n_bars
        self._idx = 0

    def reset(self) -> None:
        """Reset the internal step counter for a new episode."""
        self._idx = 0

    def fast_forward(self, n_bars: int) -> None:
        """Advance the step counter by ``n_bars`` without emitting actions.

        ``TradingEnv.reset()`` starts stepping at bar ``obs_window``, so a
        strategy evaluated through :func:`run_episode` must skip the first
        ``obs_window`` pre-computed signals to stay aligned with the bars
        the environment actually trades.

        Args:
            n_bars: Market bar or price data used for advance the step counter by ``n_bars`` without emitting actions.
        """
        self._idx = min(self._idx + max(n_bars, 0), self._n_bars)

    def act(self, obs: dict[str, Any]) -> float:
        """Return the action for the current bar.

        Args:
            obs: Environment observation (ignored by signal-based
                strategies; kept for interface compatibility).

        Returns:
            Continuous action in ``[-1.0, 1.0]``.
        """
        signal = float(self._signal(min(self._idx, self._n_bars - 1)))
        self._idx += 1
        return signal

    def act_at(self, bar_index: int) -> float:
        """Return the action for an absolute bar without advancing strategy state.

        Args:
            bar_index: Absolute row index in the bars used to build the strategy.

        Returns:
            The signal at ``bar_index``.
        """
        if isinstance(bar_index, bool):
            raise TypeError("bar_index must be an integer row index")
        try:
            idx = integer_index(bar_index)
        except TypeError as exc:
            raise TypeError("bar_index must be an integer row index") from exc
        if not 0 <= idx < self._n_bars:
            raise IndexError(f"bar_index {idx} is outside [0, {self._n_bars})")
        return float(self._signal(idx))

    @abstractmethod
    def _signal(self, idx: int) -> float:
        """Return the action for bar ``idx``.

        Args:
            idx: Numeric value used for the idx.

        Returns:
            Numeric result returned by ``_signal``.
        """
