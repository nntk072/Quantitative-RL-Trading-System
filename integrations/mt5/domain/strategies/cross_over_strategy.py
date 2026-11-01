import pandas as pd
import talib
from loguru import logger

from integrations.mt5.adapters import TradingData, TradingStrategy
from integrations.mt5.domain.signal import Signal


class CrossOverStrategy(TradingStrategy):
    """Moving-average crossover strategy for broker-neutral execution."""

    def __init__(self, trading_data: TradingData) -> None:
        """Initialize CrossOverStrategy and its owned state.

        Args:
            trading_data: Trading data used by the operation described above.
        """
        self.data = trading_data

    def signal(self) -> tuple[str, Signal]:
        """Evaluate the latest bars and return the crossover signal.

        Returns:
            Pair of broker symbol and long, short, or neutral signal.
        """
        df: pd.DataFrame = self.data.get_data()
        symbol = self.data.get_symbol()
        if df.empty:
            logger.warning(f"No data available for symbol {symbol}")
            return self.data.get_symbol(), Signal.NONE
        df["MA20"] = df["close"].rolling(window=20).mean()
        df["MA50"] = df["close"].rolling(window=50).mean()

        df["macd"], df["signal"], _ = talib.MACD(df["close"].to_numpy(dtype=float))

        buy_condition = df["MA20"] > df["MA50"]
        sell_condition = df["MA20"] < df["MA50"]

        last_buy = bool(buy_condition.iloc[-1])
        last_sell = bool(sell_condition.iloc[-1])

        if last_buy and not last_sell:
            return symbol, Signal.BUY
        if last_sell and not last_buy:
            return symbol, Signal.SELL
        return symbol, Signal.NONE
