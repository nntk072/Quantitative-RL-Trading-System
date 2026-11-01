import MetaTrader5 as mt5
import pandas as pd

from integrations.mt5.adapters import TradingData


class MT5Data(TradingData):
    """Market-data source that reads recent rates from the MetaTrader terminal.

    Attributes:
        symbol: Broker symbol to query.
        time_frame: MetaTrader timeframe identifier.
    """

    def __init__(self, symbol: str, time_frame: int) -> None:
        """Initialize MT5Data and its owned state.

        Args:
            symbol: Text or path value identifying the symbol.
            time_frame: Numeric value used for the time frame.
        """
        self.symbol = symbol
        self.time_frame = time_frame

    def get_data(self) -> pd.DataFrame:
        """Fetch recent rates for the configured symbol and timeframe.

        Returns:
            Bar frame with timestamps converted from terminal epoch seconds.
        """
        rates = mt5.copy_rates_from_pos(self.symbol, self.time_frame, 0, 1000)
        rates_frame = pd.DataFrame(rates)
        if not rates_frame.empty:
            rates_frame["time"] = pd.to_datetime(rates_frame["time"], unit="s")
        return rates_frame

    def get_symbol(self) -> str:
        """Return the configured broker symbol.

        Returns:
            Text returned by ``get_symbol``.
        """
        return self.symbol
