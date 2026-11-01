import MetaTrader5 as mt5
from loguru import logger

from integrations.mt5.adapters import Trader, TradingStrategy


class CrossOverRobot:
    """Execute crossover strategy signals through a MetaTrader trader adapter.

    Args:
        volume: Requested position size.
        trader: Adapter that reads and changes broker positions.
        strategy: Signal-producing strategy.
        paper_trading: When true, log intended orders without submitting them.
    """

    def __init__(
        self, volume: float, trader: Trader, strategy: TradingStrategy, paper_trading: bool = True
    ):
        """Initialize the robot with its sizing, adapter, strategy, and mode.

        Args:
            volume: Numeric value used for the volume.
            trader: Trader used by the operation described above.
            strategy: Strategy used to select or evaluate trades.
            paper_trading: Whether to enable or require the paper trading.
        """
        self.volume = volume
        self.trader = trader
        self.strategy = strategy
        self.paper_trading = paper_trading
        self.magic_number = 20240100
        self.name = "Cross Over"
        logger.info(f"Starting CrossOver Robot (paper_trading={paper_trading})")

    def trade(self) -> None:
        """Executes the trading logic based on the strategy's signals."""
        logger.info("Searching for trading signal")
        symbol, signal = self.strategy.signal()

        if signal == signal.BUY:
            total_buy, _ = self.trader.get_opened_positions(symbol, mt5.ORDER_TYPE_BUY)
            if total_buy == 0:
                logger.info(f"Buying signal detected for {symbol}")
                if self.paper_trading:
                    logger.info(
                        f"[PAPER] Would open buy position for {symbol}: Volume: {self.volume}"
                    )
                else:
                    result = self.trader.open_position(
                        symbol,
                        self.volume,
                        mt5.ORDER_TYPE_BUY,
                        "CrossOver buy position",
                        self.magic_number,
                    )
                if not self.paper_trading:
                    if result is None:
                        return  # Exit if AutoTrading is disabled
                    logger.info(
                        f"Buy position opened: Order #{result.order}, Volume: {result.volume}, Price: {result.price}"
                    )

            total, _ = self.trader.get_opened_positions(symbol, mt5.ORDER_TYPE_SELL)
            if total > 0:
                logger.info(f"Closing existing sell positions for {symbol}")
                if not self.paper_trading:
                    self.trader.close_positions(self.name, symbol, mt5.ORDER_TYPE_BUY)
                else:
                    logger.info(f"[PAPER] Would close existing sell positions for {symbol}")

        elif signal == signal.SELL:
            total_sell, _ = self.trader.get_opened_positions(symbol, mt5.ORDER_TYPE_SELL)
            if total_sell == 0:
                logger.info(f"Selling signal detected for {symbol}")
                if self.paper_trading:
                    logger.info(
                        f"[PAPER] Would open sell position for {symbol}: Volume: {self.volume}"
                    )
                else:
                    result = self.trader.open_position(
                        symbol,
                        self.volume,
                        mt5.ORDER_TYPE_SELL,
                        "CrossOver sell position",
                        self.magic_number,
                    )
                    if result is None:
                        return  # Exit if AutoTrading is disabled
                    logger.info(
                        f"Sell position opened: Order #{result.order}, Volume: {result.volume}, Price: {result.price}"
                    )

            total, _ = self.trader.get_opened_positions(symbol, mt5.ORDER_TYPE_BUY)
            if total > 0:
                logger.info(f"Closing existing buy positions for {symbol}")
                if not self.paper_trading:
                    self.trader.close_positions(self.name, symbol, mt5.ORDER_TYPE_BUY)
                else:
                    logger.info(f"[PAPER] Would close existing buy positions for {symbol}")

        elif signal == signal.NONE:
            logger.info("No trading signal found.")

        logger.info("Waiting for the next trading signal")
        logger.info("\n")
