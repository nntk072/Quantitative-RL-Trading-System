"""Multi-target position invariants."""

from __future__ import annotations

import math

from trading.execution import Position


def target_close_size(pos: Position, slot_num: int, *, is_final: bool) -> float:
    """Return a target leg's close size while preserving a configured runner."""
    init_size = float(pos.tp_initial_size or pos.initial_size or pos.size)
    fractions = tuple(float(value) for value in pos.tp_lot_fractions)
    active_slots = [
        slot
        for slot in (1, 2, 3)
        if (pos.tp_hit_mask & (1 << (slot - 1))) or getattr(pos, f"tp{slot}_price") is not None
    ]
    runner_fraction = float(pos.ema_runner_fraction)
    if is_final and runner_fraction <= 0.0:
        return float(pos.size)
    try:
        fraction_index = active_slots.index(slot_num)
    except ValueError:
        return float(pos.size)
    fraction = (
        fractions[fraction_index]
        if fraction_index < len(fractions)
        else 1.0 / max(1, len(active_slots))
    )
    close_size = min(round(fraction * init_size, 2), float(pos.size))
    if is_final and runner_fraction > 0.0:
        minimum_runner = round(init_size * runner_fraction, 2)
        close_size = min(close_size, max(0.0, float(pos.size) - minimum_runner))
    return close_size if close_size > 0.0 else float(pos.size)


def reorder_remaining_targets(
    pos: Position, *, point_size: float, price_tolerance: float = 1e-8
) -> None:
    """Disable invalid remaining TP slots without fabricating target prices.

    Args:
        pos: Pos used by the operation described above.
        point_size: Number specifying the point size for this operation.
        price_tolerance: Numeric value used for the price tolerance.
    """
    tol = max(float(price_tolerance), float(point_size) / 2.0)
    last_price: float | None = None
    for slot in (1, 2, 3):
        bit = 1 << (slot - 1)
        attr = f"tp{slot}_price"
        level = getattr(pos, attr)
        if level is None or (pos.tp_hit_mask & bit):
            continue
        price = float(level)
        valid = math.isfinite(price) and (
            (pos.direction == 1 and price > pos.entry_price + tol)
            or (pos.direction == -1 and price < pos.entry_price - tol)
        )
        if valid and last_price is not None:
            valid = price > last_price + tol if pos.direction == 1 else price < last_price - tol
        if not valid:
            setattr(pos, attr, None)
        else:
            last_price = price
    if hasattr(pos, "tp_price"):
        pos.tp_price = next(
            (
                getattr(pos, f"tp{slot}_price")
                for slot in (1, 2, 3)
                if getattr(pos, f"tp{slot}_price") is not None
            ),
            None,
        )
