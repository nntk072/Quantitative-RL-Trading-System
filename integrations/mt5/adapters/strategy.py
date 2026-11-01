from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from integrations.mt5.domain.signal import Signal


class TradingStrategy(ABC):
    """Interface for strategies that convert market data into signals."""

    @abstractmethod
    def signal(self) -> tuple[str, Signal]:
        """Return the current signal for the strategy's configured market.

        Returns:
            Values returned by ``signal``, in the declared order.
        """
        raise NotImplementedError
