from abc import ABC, abstractmethod

import pandas as pd


class TradingData(ABC):
    """Broker-neutral interface for market-data access."""

    @abstractmethod
    def get_data(self) -> pd.DataFrame:
        """Fetch market bars for the adapter's configured symbol.

        Returns:
            DataFrame returned by ``get_data``.
        """
        raise NotImplementedError

    @abstractmethod
    def get_symbol(self) -> str:
        """Return the symbol configured for this data source.

        Returns:
            Text returned by ``get_symbol``.
        """
        raise NotImplementedError
