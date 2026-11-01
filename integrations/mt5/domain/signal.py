from enum import Enum


class Signal(Enum):
    """Directional and no-action outcomes emitted by an MT5 strategy."""

    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    NONE = "none"
