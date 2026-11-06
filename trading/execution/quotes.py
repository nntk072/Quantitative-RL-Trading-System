"""Canonical deterministic quote and protective-fill calculations."""

from __future__ import annotations

import math

from trading.execution.costs import CostModel


def adverse_tick_fill_quote(
    quote: tuple[float, float],
    direction: int,
    slippage_points: float,
    *,
    opening: bool,
) -> tuple[float, float]:
    """Worsen only the transacted quote side by configured tick slippage.

    Args:
        quote: Executable bid/ask pair.
        direction: Position side, +1 for long or -1 for short.
        slippage_points: Adverse price adjustment applied to the transacted side.
        opening: Whether the quote is used to open or close the position.

    Returns:
        Adjusted bid/ask pair with the untouched side preserved.
    """
    if direction not in (-1, 1):
        raise ValueError("direction must be -1 or +1")
    slippage = float(slippage_points)
    if not math.isfinite(slippage) or slippage < 0.0:
        raise ValueError("tick slippage must be finite and non-negative")
    bid, ask = map(float, quote)
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


def undo_adverse_tick_slippage_quote(
    quote: tuple[float, float], direction: int, slippage_points: float, *, opening: bool
) -> tuple[float, float]:
    """Recover the executable quote before an already-applied adverse adjustment.

    Args:
        quote: Bid and ask after tick-side slippage was applied.
        direction: Position direction, ``1`` for long or ``-1`` for short.
        slippage_points: Adverse adjustment in instrument points.
        opening: Whether the fill opened the position.

    Returns:
        Bid and ask before the modeled slippage adjustment.
    """
    if direction not in (-1, 1):
        raise ValueError("direction must be -1 or +1")
    slippage = float(slippage_points)
    if not math.isfinite(slippage) or slippage < 0.0:
        raise ValueError("slippage_points must be finite and non-negative")
    bid, ask = map(float, quote)
    if opening:
        if direction == 1:
            ask -= slippage
        else:
            bid += slippage
    elif direction == 1:
        bid += slippage
    else:
        ask -= slippage
    return bid, ask


def undo_adverse_quote_level_slippage(
    quote: tuple[float, float], direction: int, slippage_points: float, *, opening: bool
) -> tuple[float, float]:
    """Undo a modeled protective-level adjustment applied to the whole quote.

    Args:
        quote: Bid and ask after a whole-quote adjustment.
        direction: Position direction, ``1`` for long or ``-1`` for short.
        slippage_points: Quote shift in instrument points.
        opening: Whether the fill opened the position.

    Returns:
        Bid and ask before the modeled quote-level shift.
    """
    if direction not in (-1, 1):
        raise ValueError("direction must be -1 or +1")
    slippage = float(slippage_points)
    if not math.isfinite(slippage) or slippage < 0.0:
        raise ValueError("slippage_points must be finite and non-negative")
    bid, ask = map(float, quote)
    shift = slippage if (direction == -1 if opening else direction == 1) else -slippage
    return bid + shift, ask + shift


def raw_spread_to_price(raw_spread_points: float | None, point_size: float) -> float | None:
    """Convert a broker-reported spread to price units, preserving missing values.

    Args:
        raw_spread_points: Raw spread points used by the operation described above.
        point_size: Number specifying the point size for this operation.

    Returns:
        Result of convert a broker-reported spread to price units, preserving missing values.
    """
    if raw_spread_points is None:
        return None
    spread = float(raw_spread_points)
    return spread * float(point_size) if math.isfinite(spread) else None


def quote_from_bar_price(
    cost_model: CostModel, price: float, spread_points: float | None
) -> tuple[float, float]:
    """Build a quote from a bar price and raw broker spread points.

    Args:
        cost_model: Cost model used by the operation described above.
        price: Numeric value used for the price.
        spread_points: Spread points used by the operation described above.

    Returns:
        Values returned by ``quote_from_bar_price``, in the declared order.
    """
    spread = raw_spread_to_price(spread_points, cost_model.point_size)
    return cost_model.bar_quote(float(price), bar_spread=spread)


def exit_side_bar_range(
    direction: int,
    bid_low: float,
    bid_high: float,
    spread_price_units: float | None,
    cost_model: CostModel,
) -> tuple[float, float]:
    """Return low/high OHLC bounds on the position's executable exit side.

    MT5 bar OHLC is bid based. Long exits transact on bid; short exits
    transact on ask, derived from the bar's recorded spread. This is a
    bar-spread estimate, not a reconstruction of intrabar spread changes.

    Args:
        direction: Position direction, ``1`` for long or ``-1`` for short.
        bid_low: Low bid price from the bar.
        bid_high: High bid price from the bar.
        spread_price_units: Recorded spread converted to price units, or
            ``None`` to use the configured default spread.
        cost_model: Cost model providing the default spread when needed.

    Returns:
        The low and high prices for the position's executable exit side.
    """
    if direction not in (-1, 1):
        raise ValueError("direction must be -1 or +1")
    spread = cost_model.spread_points if spread_price_units is None else spread_price_units
    if direction == 1:
        return float(bid_low), float(bid_high)
    return float(bid_low) + float(spread), float(bid_high) + float(spread)


def protective_level_fill_quote(
    direction: int, hit_price: float, cost_model: CostModel
) -> tuple[float, float]:
    """Build a bid/ask quote that executes a protective level with adverse slippage.

    Args:
        direction: Signed trade direction: 1 for long and -1 for short.
        hit_price: Numeric value used for the hit price.
        cost_model: Cost model used by the operation described above.

    Returns:
        Values returned by ``protective_level_fill_quote``, in the declared order.
    """
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
    """Account for a bar opening through its protective stop.

    Args:
        direction: Signed trade direction: 1 for long and -1 for short.
        stop_price: Numeric value used for the stop price.
        bar_open: Numeric value used for the bar open.
        opening_spread: Numeric value used for the opening spread.

    Returns:
        Numeric result returned by ``bar_stop_trigger_price``.
    """
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
    """Price a bar stop at its level or at a worse opening quote.

    Args:
        direction: Signed trade direction: 1 for long and -1 for short.
        stop_price: Numeric value used for the stop price.
        bar_open: Numeric value used for the bar open.
        raw_spread_points: Raw spread points used by the operation described above.
        cost_model: Cost model used by the operation described above.

    Returns:
        Values returned by ``bar_stop_fill_quote``, in the declared order.
    """
    spread = raw_spread_to_price(raw_spread_points, cost_model.point_size)
    if spread is None:
        spread = float(cost_model.spread_points)
    trigger = bar_stop_trigger_price(direction, stop_price, bar_open, spread)
    return protective_level_fill_quote(direction, trigger, cost_model)
