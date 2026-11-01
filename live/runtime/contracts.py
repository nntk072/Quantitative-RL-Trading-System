"""Broker-neutral contracts for live inference and execution adapters."""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol

import pandas as pd


class LiveSignal(StrEnum):
    """Enumerate broker-neutral directional decisions from a live strategy."""

    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    NONE = "none"


class MarketDataSource(Protocol):
    """Provide the current instrument identity and market bars to a strategy."""

    def get_symbol(self) -> str:
        """Return the broker symbol represented by this data source.

        Returns:
            Text returned by ``get_symbol``.
        """

    def get_data(self) -> pd.DataFrame:
        """Return the latest market bars available for the configured symbol.

        Returns:
            DataFrame returned by ``get_data``.
        """


class LiveStrategy(Protocol):
    """Define the live decision contract consumed by execution adapters."""

    def signal(self) -> tuple[str, LiveSignal]:
        """Return the instrument and its current directional signal.

        Returns:
            Values returned by ``signal``, in the declared order.
        """


__all__ = ["LiveSignal", "LiveStrategy", "MarketDataSource"]
