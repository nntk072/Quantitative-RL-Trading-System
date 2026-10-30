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
    def _adverse_tick_fill_quote(
        self, quote: tuple[float, float], direction: int, *, opening: bool
    ) -> tuple[float, float]:
        """Worsen only the transacted bid/ask side after selecting a tick."""
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
        """Close at a selected quote, applying evaluation stress once at execution."""
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
        """Open at a selected quote, applying evaluation stress once at execution."""
        if tick_fill:
            quote = self._adverse_tick_fill_quote(quote, direction, opening=True)
        return self.broker.open_position(self.account, quote, lots, direction)

    def _sl_tp_fill_quote(self, direction: int, hit_price: float) -> tuple[float, float]:
        """Bid/ask that closes at *hit_price*, worsened only by adverse slippage.

        Longs sell the bid and shorts buy the ask, so that side is the stop
        or target. The other side is one model spread away so
        ``Broker.close_position`` still sees a two-sided quote.
        """
        return protective_level_fill_quote(direction, hit_price, self.cost_model)

    def _stop_fill_quote(
        self, bar: BarView, direction: int, stop_price: float
    ) -> tuple[float, float]:
        """Price a bar stop at its level unless the bar opens through it."""
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
        """
        return quote_from_bar_price(self.cost_model, float(bar.close), float(bar.spread))

    def _bar_open_quote(self, bar: BarView) -> tuple[float, float]:
        """Get an executable bid/ask from a bar's opening price."""
        return quote_from_bar_price(self.cost_model, float(bar.open), float(bar.spread))
