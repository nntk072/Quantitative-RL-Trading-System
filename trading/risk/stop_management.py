"""Shared stop-management calculations for simulator implementations."""

from __future__ import annotations

import math


def confirmed_swing_trailing_stop_price(
    *,
    direction: int,
    swing_price: float,
    current_close: float | None,
    current_stop_price: float | None,
    buffer_points: float,
) -> float | None:
    """Return a confirmed-swing stop only when it tightens and stays protective.

    Args:
        direction: Position direction, ``1`` for long or ``-1`` for short.
        swing_price: Confirmed structural swing used as the stop reference.
        current_close: Latest close used to keep the stop beyond current price.
        current_stop_price: Existing stop, when one is already set.
        buffer_points: Distance applied beyond the swing in instrument points.

    Returns:
        Tighter protective stop price, or ``None`` when it is not valid.
    """
    if isinstance(direction, bool) or direction not in (-1, 1):
        raise ValueError("direction must be -1 or 1")

    amounts = {"swing_price": swing_price, "buffer_points": buffer_points}
    if current_close is not None:
        amounts["current_close"] = current_close
    if current_stop_price is not None:
        amounts["current_stop_price"] = current_stop_price
    normalized: dict[str, float] = {}
    for name, value in amounts.items():
        if isinstance(value, bool):
            raise ValueError(f"{name} must be finite")
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"{name} must be finite") from exc
        if not math.isfinite(number):
            raise ValueError(f"{name} must be finite")
        normalized[name] = number

    buffer = normalized["buffer_points"]
    if buffer < 0.0:
        raise ValueError("buffer_points must be non-negative")

    candidate = normalized["swing_price"] - direction * buffer
    if not math.isfinite(candidate):
        raise ValueError("trailing stop price must remain finite")
    current_stop = normalized.get("current_stop_price")
    if current_stop is not None:
        if math.isclose(candidate, current_stop, rel_tol=1e-12, abs_tol=1e-12):
            return None
        if direction * (candidate - current_stop) <= 0.0:
            return None
    current = normalized.get("current_close")
    if current is not None and direction * (current - candidate) <= 0.0:
        return None
    return candidate


def tightened_breakeven_stop_price(
    *,
    direction: int,
    entry_price: float,
    current_stop_price: float | None,
    buffer_points: float,
) -> float | None:
    """Return a buffered breakeven stop only when it tightens the current stop.

    Args:
        direction: Position direction, ``1`` for long or ``-1`` for short.
        entry_price: Position entry price used as the breakeven reference.
        current_stop_price: Existing stop price, if present.
        buffer_points: Offset beyond entry in instrument points.

    Returns:
        Improved breakeven stop price, or ``None`` if it would not tighten.
    """
    if isinstance(direction, bool) or direction not in (-1, 1):
        raise ValueError("direction must be -1 or 1")

    amounts = {"entry_price": entry_price, "buffer_points": buffer_points}
    if current_stop_price is not None:
        amounts["current_stop_price"] = current_stop_price
    normalized: dict[str, float] = {}
    for name, value in amounts.items():
        if isinstance(value, bool):
            raise ValueError(f"{name} must be finite")
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"{name} must be finite") from exc
        if not math.isfinite(number):
            raise ValueError(f"{name} must be finite")
        normalized[name] = number

    buffer = normalized["buffer_points"]
    if buffer < 0.0:
        raise ValueError("buffer_points must be non-negative")
    proposed = normalized["entry_price"] + direction * buffer
    if not math.isfinite(proposed):
        raise ValueError("proposed breakeven stop must remain finite")
    current_stop = normalized.get("current_stop_price")
    if direction == 1 and (current_stop is None or proposed > current_stop):
        return proposed
    if direction == -1 and (current_stop is None or proposed < current_stop):
        return proposed
    return None


def breakeven_stop_price(
    *,
    direction: int,
    entry_price: float,
    initial_stop_price: float | None,
    current_stop_price: float | None,
    best_favorable_points: float,
    trigger_r: float,
    buffer_points: float,
) -> float | None:
    """Return a tighter breakeven stop when the favorable-R trigger is reached.

    ``None`` means that the trigger is disabled, the initial risk distance is
    unavailable, or the proposed stop would not tighten the current stop.

    Raises:
        ValueError: If direction, prices, or management settings are invalid.

    Args:
        direction: Position direction, ``1`` for long or ``-1`` for short.
        entry_price: Position entry price.
        initial_stop_price: Stop price that defines initial risk, if available.
        current_stop_price: Current stop that the new stop must tighten.
        best_favorable_points: Best favorable movement observed since entry.
        trigger_r: Favorable-movement threshold expressed in initial-risk units.
        buffer_points: Offset beyond entry in instrument points.

    Returns:
        Tighter breakeven stop after the threshold, or ``None`` if not triggered.
    """
    if isinstance(direction, bool) or direction not in (-1, 1):
        raise ValueError("direction must be -1 or 1")

    amounts = {
        "entry_price": entry_price,
        "best_favorable_points": best_favorable_points,
        "trigger_r": trigger_r,
        "buffer_points": buffer_points,
    }
    if initial_stop_price is not None:
        amounts["initial_stop_price"] = initial_stop_price
    if current_stop_price is not None:
        amounts["current_stop_price"] = current_stop_price
    normalized: dict[str, float] = {}
    for name, value in amounts.items():
        if isinstance(value, bool):
            raise ValueError(f"{name} must be finite")
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"{name} must be finite") from exc
        if not math.isfinite(number):
            raise ValueError(f"{name} must be finite")
        normalized[name] = number

    entry = normalized["entry_price"]
    favorable = normalized["best_favorable_points"]
    trigger = normalized["trigger_r"]
    buffer = normalized["buffer_points"]
    if favorable < 0.0:
        raise ValueError("best_favorable_points must be non-negative")
    if buffer < 0.0:
        raise ValueError("buffer_points must be non-negative")
    if trigger <= 0.0 or initial_stop_price is None:
        return None

    initial_stop = normalized["initial_stop_price"]
    if initial_stop == entry:
        return None
    if (direction == 1 and initial_stop >= entry) or (direction == -1 and initial_stop <= entry):
        raise ValueError("initial_stop_price must be beyond entry on the adverse side")

    risk_points = abs(entry - initial_stop)
    trigger_points = trigger * risk_points
    if not math.isfinite(risk_points) or not math.isfinite(trigger_points):
        raise ValueError("initial risk and breakeven trigger distance must remain finite")
    if risk_points <= 0.0 or favorable < trigger_points:
        return None

    return tightened_breakeven_stop_price(
        direction=direction,
        entry_price=entry,
        current_stop_price=normalized.get("current_stop_price"),
        buffer_points=buffer,
    )
