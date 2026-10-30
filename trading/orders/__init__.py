"""Order geometry, structural references, and action-selection contracts."""

from .entries import (
    OrderGeometry,
    TargetReference,
    dynamic_tp,
    place_strategy_order,
    resolve_strategy_entry,
)
from .levels import DEVIATION_KS, deviation_levels, level_near_candles
from .selection import decode_tp_fractions, decode_tp_mode, decode_tp_selections, validate_tp_levels
from .stops import filter_sl_candidates, manipulation_state, stop_menu
from .targets import collapse_levels, deviation_candidates, target_menu
from .timeframes import (
    TIMEFRAME_ORDER,
    normalize_timeframe,
    reference_timeframe,
    reference_timeframe_index,
    source_timeframe,
    timeframe_index,
)

__all__ = [
    "OrderGeometry",
    "DEVIATION_KS",
    "TIMEFRAME_ORDER",
    "TargetReference",
    "collapse_levels",
    "decode_tp_fractions",
    "decode_tp_mode",
    "decode_tp_selections",
    "deviation_candidates",
    "deviation_levels",
    "dynamic_tp",
    "filter_sl_candidates",
    "manipulation_state",
    "normalize_timeframe",
    "level_near_candles",
    "place_strategy_order",
    "reference_timeframe",
    "reference_timeframe_index",
    "resolve_strategy_entry",
    "stop_menu",
    "source_timeframe",
    "target_menu",
    "timeframe_index",
    "validate_tp_levels",
]
