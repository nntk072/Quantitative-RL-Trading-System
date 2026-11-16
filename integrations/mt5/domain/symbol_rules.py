"""Checks for broker supplied MT5 symbol constraints."""

import math
from typing import cast

import MetaTrader5 as mt5


def volume_matches_symbol(symbol_info: object, volume: float) -> bool:
    """Check that a requested lot volume fits the symbol's live constraints.

    Args:
        symbol_info: Broker-provided symbol constraints.
        volume: Requested position volume in lots.

    Returns:
        Whether the volume satisfies the current minimum, maximum, and step.
    """
    raw = tuple(
        getattr(symbol_info, name, None) for name in ("volume_min", "volume_max", "volume_step")
    )
    if any(
        value is None or isinstance(value, bool) or type(value).__name__ == "bool_" for value in raw
    ):
        return False
    try:
        volume_min, volume_max, volume_step = (float(cast(float, value)) for value in raw)
    except (TypeError, ValueError):
        return False
    if (
        isinstance(volume, bool)
        or not all(math.isfinite(value) for value in (volume, volume_min, volume_max, volume_step))
        or volume <= 0.0
        or volume_min <= 0.0
        or volume_max < volume_min
        or volume_step <= 0.0
        or not volume_min <= volume <= volume_max
    ):
        return False
    steps = (volume - volume_min) / volume_step
    return math.isclose(steps, round(steps), rel_tol=0.0, abs_tol=1e-8)


def filling_type(symbol_info: object) -> int | None:
    """Choose a fill policy permitted by current symbol execution metadata.

    Args:
        symbol_info: Broker-provided execution and filling flags.

    Returns:
        A permitted MT5 fill constant, or ``None`` if metadata is unsupported.
    """
    filling = getattr(symbol_info, "filling_mode", None)
    execution = getattr(symbol_info, "trade_exemode", None)
    if isinstance(filling, bool) or isinstance(execution, bool):
        return None
    try:
        flags, mode = float(cast(float, filling)), float(cast(float, execution))
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(value) and value.is_integer() for value in (flags, mode)) or flags < 0:
        return None
    flags, mode = int(flags), int(mode)
    if mode in {mt5.SYMBOL_TRADE_EXECUTION_REQUEST, mt5.SYMBOL_TRADE_EXECUTION_INSTANT}:
        return int(mt5.ORDER_FILLING_FOK)
    if mode not in {mt5.SYMBOL_TRADE_EXECUTION_MARKET, mt5.SYMBOL_TRADE_EXECUTION_EXCHANGE}:
        return None
    if flags & mt5.SYMBOL_FILLING_FOK:
        return int(mt5.ORDER_FILLING_FOK)
    if flags & mt5.SYMBOL_FILLING_IOC:
        return int(mt5.ORDER_FILLING_IOC)
    if mode == mt5.SYMBOL_TRADE_EXECUTION_EXCHANGE:
        return int(mt5.ORDER_FILLING_RETURN)
    return None


def symbol_allows_open(
    symbol_info: object, position_type: int, *, sl: float | None, tp: float | None
) -> bool:
    """Check live symbol trade, market-order, stop, and target permissions.

    Args:
        symbol_info: Broker-provided trade and order flags.
        position_type: MT5 buy or sell order type.
        sl: Stop-loss price to attach, if any.
        tp: Take-profit price to attach, if any.

    Returns:
        Whether the symbol currently permits the requested entry.
    """
    trade_mode, order_mode = (
        getattr(symbol_info, "trade_mode", None),
        getattr(symbol_info, "order_mode", None),
    )
    if isinstance(trade_mode, bool) or isinstance(order_mode, bool):
        return False
    try:
        trade_mode, order_mode = float(cast(float, trade_mode)), float(cast(float, order_mode))
    except (TypeError, ValueError):
        return False
    if not all(math.isfinite(value) and value.is_integer() for value in (trade_mode, order_mode)):
        return False
    mode, orders = int(trade_mode), int(order_mode)
    if orders < 0 or not orders & mt5.SYMBOL_ORDER_MARKET:
        return False
    if sl is not None and not orders & mt5.SYMBOL_ORDER_SL:
        return False
    if tp is not None and not orders & mt5.SYMBOL_ORDER_TP:
        return False
    if mode in {mt5.SYMBOL_TRADE_MODE_DISABLED, mt5.SYMBOL_TRADE_MODE_CLOSEONLY}:
        return False
    if position_type == mt5.ORDER_TYPE_BUY:
        return mode in {mt5.SYMBOL_TRADE_MODE_LONGONLY, mt5.SYMBOL_TRADE_MODE_FULL}
    if position_type == mt5.ORDER_TYPE_SELL:
        return mode in {mt5.SYMBOL_TRADE_MODE_SHORTONLY, mt5.SYMBOL_TRADE_MODE_FULL}
    return False
