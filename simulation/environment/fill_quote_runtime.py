"""Focused simulation execution service."""

from __future__ import annotations

from typing import Any, cast

from trading.execution import (
    bar_stop_fill_quote,
    protective_level_fill_quote,
    quote_from_bar_price,
)

from .market_view import BarView
from .mixin_base import RuntimeMixinBase


class FillQuoteRuntimeMixin(RuntimeMixinBase):
    """Select fill quotes and apply configured bid/ask-side slippage."""

    def _adverse_tick_fill_quote(
        self, quote: tuple[float, float], direction: int, *, opening: bool
    ) -> tuple[float, float]:
        """Worsen only the transacted bid/ask side after selecting a tick.

        Args:
            quote: Items supplied for the quote, in input order.
            direction: Signed trade direction: 1 for long and -1 for short.
            opening: Whether to enable or require the opening.

        Returns:
            Values returned by ``_adverse_tick_fill_quote``, in the declared order.
        """
        bid, ask = map(float, quote)
        slippage = float(getattr(self, "tick_fill_slippage_points", 0.0))
        if opening:
            if direction == 1:
                ask += slippage
            else:
                bid -= slippage
        elif direction == 1:
            bid -= slippage
        else:
            ask += slippage
        return bid, ask

    def _close_at_quote(
        self,
        position: Any,
        quote: tuple[float, float],
        *,
        size: float | None = None,
        tick_fill: bool = False,
    ) -> tuple[float, float]:
        """Close at a selected quote, applying evaluation stress once at execution.

        Args:
            position: Position used by the operation described above.
            quote: Items supplied for the quote, in input order.
            size: Size used by the operation described above.
            tick_fill: Whether to enable or require the tick fill.

        Returns:
            Values returned by ``_close_at_quote``, in the declared order.
        """
        if tick_fill:
            quote = self._adverse_tick_fill_quote(quote, int(position.direction), opening=False)
        return cast(
            tuple[float, float],
            self.broker.close_position(self.account, position, quote, size=size),
        )

    def _open_at_quote(
        self,
        quote: tuple[float, float],
        lots: float,
        direction: int,
        *,
        tick_fill: bool = False,
    ) -> Any:
        """Open at a selected quote, applying evaluation stress once at execution.

        Args:
            quote: Items supplied for the quote, in input order.
            lots: Numeric value used for the lots.
            direction: Signed trade direction: 1 for long and -1 for short.
            tick_fill: Whether to enable or require the tick fill.

        Returns:
            Result of open at a selected quote, applying evaluation stress once at execution.
        """
        if tick_fill:
            quote = self._adverse_tick_fill_quote(quote, direction, opening=True)
        return self.broker.open_position(self.account, quote, lots, direction)

    def _sl_tp_fill_quote(self, direction: int, hit_price: float) -> tuple[float, float]:
        """Bid/ask that closes at *hit_price*, worsened only by adverse slippage.

        Longs sell the bid and shorts buy the ask, so that side is the stop
        or target. The other side is one model spread away so
        ``Broker.close_position`` still sees a two-sided quote.

        Args:
            direction: Signed trade direction: 1 for long and -1 for short.
            hit_price: Numeric value used for the hit price.

        Returns:
            Values returned by ``_sl_tp_fill_quote``, in the declared order.
        """
        return protective_level_fill_quote(direction, hit_price, self.cost_model)

    def _stop_fill_quote(
        self, bar: BarView, direction: int, stop_price: float
    ) -> tuple[float, float]:
        """Price a bar stop at its level unless the bar opens through it.

        Args:
            bar: Bar used by the operation described above.
            direction: Signed trade direction: 1 for long and -1 for short.
            stop_price: Numeric value used for the stop price.

        Returns:
            Values returned by ``_stop_fill_quote``, in the declared order.
        """
        return bar_stop_fill_quote(
            direction,
            stop_price,
            float(bar.open),
            float(bar.spread),
            self.cost_model,
        )

    def _bar_quote(self, bar: BarView) -> tuple[float, float]:
        """Get (bid, ask) from a bar using cost model.

        The bar's raw ``spread`` column is in MT5 broker points, not price
        units, so it must be scaled by ``point_size`` before being used as a
        price-unit spread (see ``trading.execution.raw_spread_to_price``).

        Args:
            bar: Bar used by the operation described above.

        Returns:
            Values returned by ``_bar_quote``, in the declared order.
        """
        return quote_from_bar_price(self.cost_model, float(bar.close), float(bar.spread))

    def _bar_open_quote(self, bar: BarView) -> tuple[float, float]:
        """Get an executable bid/ask from a bar's opening price.

        Args:
            bar: Bar used by the operation described above.

        Returns:
            Values returned by ``_bar_open_quote``, in the declared order.
        """
        return quote_from_bar_price(self.cost_model, float(bar.open), float(bar.spread))
