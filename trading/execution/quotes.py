"""Canonical deterministic quote and protective-fill calculations."""

from __future__ import annotations

import math

from trading.execution.costs import CostModel


def raw_spread_to_price(raw_spread_points: float | None, point_size: float) -> float | None:
    """Convert a broker-reported spread to price units, preserving missing values."""
    if raw_spread_points is None:
        return None
    spread = float(raw_spread_points)
    return spread * float(point_size) if math.isfinite(spread) else None


def quote_from_bar_price(
    cost_model: CostModel, price: float, spread_points: float | None
) -> tuple[float, float]:
    """Build a quote from a bar price and raw broker spread points."""
    spread = raw_spread_to_price(spread_points, cost_model.point_size)
    return cost_model.bar_quote(float(price), bar_spread=spread)


def protective_level_fill_quote(
    direction: int, hit_price: float, cost_model: CostModel
) -> tuple[float, float]:
    """Build a bid/ask quote that executes a protective level with adverse slippage."""
    spread = float(cost_model.spread_points)
    slippage = float(cost_model.slippage_points)
    if direction == 1:
        bid = float(hit_price) - slippage
        return bid, bid + spread
    ask = float(hit_price) + slippage
    return ask - spread, ask


def bar_stop_trigger_price(
    direction: int,
    stop_price: float,
    bar_open: float,
    opening_spread: float,
) -> float:
    """Account for a bar opening through its protective stop."""
    if direction == 1:
        return min(float(stop_price), float(bar_open))
    opening_ask = float(bar_open) + float(opening_spread)
    return max(float(stop_price), opening_ask)


def bar_stop_fill_quote(
    direction: int,
    stop_price: float,
    bar_open: float,
    raw_spread_points: float | None,
    cost_model: CostModel,
) -> tuple[float, float]:
    """Price a bar stop at its level or at a worse opening quote."""
    spread = raw_spread_to_price(raw_spread_points, cost_model.point_size)
    if spread is None:
        spread = float(cost_model.spread_points)
    trigger = bar_stop_trigger_price(direction, stop_price, bar_open, spread)
    return protective_level_fill_quote(direction, trigger, cost_model)
