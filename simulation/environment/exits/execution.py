from __future__ import annotations

from ..accounting.trades import TradeAccountingRuntimeMixin
from ..mixin_base import RuntimeMixinBase
from ..quotes.fills import FillQuoteRuntimeMixin
from ..quotes.ticks import TickQuoteRuntimeMixin
from .ema import EmaExitRuntimeMixin
from .protective_levels import ProtectiveLevelRuntimeMixin


class ExecutionRuntimeMixin(
    ProtectiveLevelRuntimeMixin,
    TickQuoteRuntimeMixin,
    FillQuoteRuntimeMixin,
    TradeAccountingRuntimeMixin,
    EmaExitRuntimeMixin,
    RuntimeMixinBase,
):
    """Compose quote selection, protective levels, and trade accounting."""

    pass


__all__ = ["ExecutionRuntimeMixin"]
