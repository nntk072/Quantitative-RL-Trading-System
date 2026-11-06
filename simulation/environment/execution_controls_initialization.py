"""Focused simulation initialization service."""

from __future__ import annotations

from math import isfinite

from market_data.loading.ticks import TickBook

from .mixin_base import RuntimeMixinBase


class ExecutionControlsInitializationMixin(RuntimeMixinBase):
    """Initialize execution source, fill latency, slippage, and quote-wait controls."""

    def _initialize_execution_controls(
        self,
        tickbook: TickBook | None,
        tick_execution_required: bool,
        fill_delay_ms: int,
        randomized_fill_latency_ms: float,
        max_tick_quote_wait_ms: int,
        tick_fill_slippage_points: float,
    ) -> None:
        """Initialize execution controls.

        Args:
            tickbook: Tickbook used by the operation described above.
            tick_execution_required: Whether to enable or require the tick execution required.
            fill_delay_ms: Numeric value used for the fill delay ms.
            randomized_fill_latency_ms: Numeric value used for the randomized fill latency ms.
            max_tick_quote_wait_ms: Numeric value used for the max tick quote wait ms.
            tick_fill_slippage_points: Market-fill slippage in price points. The
                historical parameter name is retained for API compatibility.
        """
        self._tickbook = tickbook
        self.tick_execution_required = bool(tick_execution_required)
        self.fill_delay_ms = int(fill_delay_ms)
        self.randomized_fill_latency_ms = float(randomized_fill_latency_ms)
        self.max_tick_quote_wait_ms = int(max_tick_quote_wait_ms)
        self.tick_fill_slippage_points = float(tick_fill_slippage_points)
        if self.randomized_fill_latency_ms < 0:
            raise ValueError("randomized_fill_latency_ms cannot be negative")
        if self.randomized_fill_latency_ms > 30.0:
            raise ValueError("randomized_fill_latency_ms must be at most 30ms exclusive")
        if self.max_tick_quote_wait_ms <= 0:
            raise ValueError("max_tick_quote_wait_ms must be positive")
        if not isfinite(self.tick_fill_slippage_points) or self.tick_fill_slippage_points < 0:
            raise ValueError("tick_fill_slippage_points must be finite and non-negative")
        if (
            self.tick_execution_required or self.randomized_fill_latency_ms > 0
        ) and tickbook is None:
            raise ValueError("tick-only execution requires a TickBook")


__all__ = ["ExecutionControlsInitializationMixin"]
