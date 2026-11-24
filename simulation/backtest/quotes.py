"""Quote and fill helpers used by the event-driven backtester."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from market_data.loading.ticks import (
    TickExecutionUnavailable,
    nearest_tick_execution,
    resolve_tick_execution,
)
from trading.execution import CostModel, protective_level_fill_quote, raw_spread_to_price

if TYPE_CHECKING:
    from market_data.loading.ticks import TickBook


def _bar_spread_price_units(row: pd.Series, cost_model: CostModel) -> float | None:
    """Convert the bar's raw MT5 ``spread`` column (broker points) to price units.

    MT5 CSVs report ``spread`` in integer broker points (e.g. ``80``), not
    price units. ``CostModel.bar_quote``/``fill_price`` expect the spread
    already in price units (e.g. ``0.6`` for US100), so it must be scaled by
    ``point_size`` here. Without this conversion a raw value like 80 was
    being added directly to the close price, producing bid/ask quotes tens
    to hundreds of points away from the visible candle.

    Args:
        row: Row index or record being processed.
        cost_model: Cost model used by the operation described above.

    Returns:
        Result of convert the bar's raw MT5 ``spread`` column (broker points) to price units.
    """
    if "spread" not in row.index or pd.isna(row["spread"]):
        return None
    return raw_spread_to_price(float(row["spread"]), cost_model.point_size)


def _sl_tp_fill_quote(
    direction: int,
    hit_price: float,
    cost_model: CostModel,
) -> tuple[float, float]:
    """Build a fill quote for an intrabar SL/TP hit on the triggering bar.

    The fill price is pinned to the SL/TP level; the opposite side is
    extended by the model spread so that ``Broker.close_position`` can
    deduct the round-turn spread cost.

    Args:
        direction: Signed trade direction: 1 for long and -1 for short.
        hit_price: Numeric value used for the hit price.
        cost_model: Cost model used by the operation described above.

    Returns:
        Values returned by ``_sl_tp_fill_quote``, in the declared order.
    """
    return protective_level_fill_quote(direction, hit_price, cost_model)


def _bar_quote(row: pd.Series, cost_model: CostModel) -> tuple[float, float]:
    """Derive ``(bid, ask)`` from a bar row (MT5 close = bid).

    Args:
        row: Row index or record being processed.
        cost_model: Cost model used by the operation described above.

    Returns:
        Values returned by ``_bar_quote``, in the declared order.
    """
    bar_spread = _bar_spread_price_units(row, cost_model)
    return cost_model.bar_quote(float(row["close"]), bar_spread=bar_spread)


def _fill_quote(
    fill_instant: pd.Timestamp,
    row: pd.Series,
    cost_model: CostModel,
    tickbook: TickBook | None,
) -> tuple[float, float]:
    """Return the fill quote for an order executed at *fill_instant*.

    *row* must be the bar whose time range contains *fill_instant* (i.e. the
    bar actually being executed into) — it is used both as the bar-quote
    fallback and as a sanity range for tick fills.

    Guards against tick-data gaps/outliers: a ``TickBook`` forward-fills
    quotes across data gaps, which can return a stale tick far from the
    current candle. If the tick quote's mid price falls outside this bar's
    ``[low, high]`` range (widened by a small buffer for spread), the tick
    fill is rejected in favour of a bar-based quote, so fills always land
    on/near a visible candle.

    Args:
        fill_instant: Fill instant used by the operation described above.
        row: Row index or record being processed.
        cost_model: Cost model used by the operation described above.
        tickbook: Tickbook used by the operation described above.

    Returns:
        Values returned by ``_fill_quote``, in the declared order.
    """
    return _fill_quote_event(fill_instant, row, cost_model, tickbook)[0]


def _fill_quote_event(
    fill_instant: pd.Timestamp,
    row: pd.Series,
    cost_model: CostModel,
    tickbook: TickBook | None,
    *,
    rng: np.random.Generator | None = None,
    randomized_fill_latency_ms: float = 0.0,
    max_tick_quote_wait_ms: int = 60_000,
    tick_execution_required: bool = False,
) -> tuple[tuple[float, float], pd.Timestamp, str, dict[str, Any]]:
    """Return a delayed execution quote and timing/source metadata.

    Args:
        fill_instant: Fill instant used by the operation described above.
        row: Row index or record being processed.
        cost_model: Cost model used by the operation described above.
        tickbook: Tickbook used by the operation described above.
        rng: Rng used by the operation described above.
        randomized_fill_latency_ms: Numeric value used for the randomized fill latency ms.
        max_tick_quote_wait_ms: Numeric value used for the max tick quote wait ms.
        tick_execution_required: Whether to enable or require the tick execution required.

    Returns:
        Mapping from ``str`` keys to ``Any]`` values.
    """
    if randomized_fill_latency_ms > 30.0 or randomized_fill_latency_ms < 0.0:
        raise ValueError("randomized_fill_latency_ms must be in [0, 30]")
    if max_tick_quote_wait_ms <= 0:
        raise ValueError("max_tick_quote_wait_ms must be positive")
    if tick_execution_required or randomized_fill_latency_ms > 0:
        if tickbook is None or rng is None:
            raise TickExecutionUnavailable("tick-only fills require a TickBook and RNG")
        execution = resolve_tick_execution(
            tickbook,
            fill_instant,
            rng,
            max_latency_ns_exclusive=int(randomized_fill_latency_ms * 1_000_000),
            max_quote_wait_ns=max_tick_quote_wait_ms * 1_000_000,
        )
        if execution is None:
            # No tick follows the arrival within the cap: the nearest tick in time, within the same cap.
            nearest = nearest_tick_execution(
                tickbook,
                pd.Timestamp(fill_instant),
                max_gap_ns=int(max_tick_quote_wait_ms * 1_000_000),
            )
            if nearest is None:
                raise TickExecutionUnavailable(
                    f"no executable tick within {max_tick_quote_wait_ms}ms of {fill_instant}"
                )
            execution = nearest
        return (
            (execution.bid, execution.ask),
            execution.tick_time,
            "tick",
            {
                "order_submission_time": execution.order_time,
                "execution_order_time": execution.order_time,
                "execution_arrival_time": execution.arrival_time,
                "execution_latency_ns": execution.latency_ns,
                "actual_tick_time": execution.tick_time,
                "fill_quote_source": "tick",
            },
        )

    bar_spread = _bar_spread_price_units(row, cost_model)
    if tickbook is not None:
        q = tickbook.quote_at(fill_instant)
        if q is not None:
            bid, ask = q
            mid = (bid + ask) / 2.0
            lo = float(row["low"])
            hi = float(row["high"])
            buffer = max(hi - lo, bar_spread or 0.0, cost_model.spread_points)
            if tick_execution_required or lo - buffer <= mid <= hi + buffer:
                return (
                    q,
                    fill_instant,
                    "tick",
                    {
                        "order_submission_time": fill_instant,
                        "execution_order_time": fill_instant,
                        "execution_arrival_time": fill_instant,
                        "execution_latency_ns": 0,
                        "actual_tick_time": fill_instant,
                        "fill_quote_source": "tick",
                    },
                )
                # In legacy mode, reject outlier ticks and use the candle quote.
    if tick_execution_required:
        raise TickExecutionUnavailable(
            f"no executable tick within {max_tick_quote_wait_ms}ms of {fill_instant}"
        )
    return (
        cost_model.bar_quote(float(row["open"]), bar_spread=bar_spread),
        fill_instant,
        "bar_open",
        {},
    )
