"""Shared config and date-window helpers for feature research analyses."""

from __future__ import annotations

from typing import Any

import pandas as pd
from omegaconf import DictConfig

from configuration.paths import repository_root
from market_data.splits.definitions import make_train_mask

ROOT = repository_root(__file__)
DEFAULT_CONFIG = ROOT / "config/research/trade_setup_mtf_reasoning_2m.yaml"
TIMEFRAMES = ("M1", "M3", "M5", "M10", "M15", "M30", "H1", "H4", "D1")


def training_slice(
    frames: dict[str, pd.DataFrame], start: str, end: str
) -> dict[str, pd.DataFrame]:
    """Restrict each source stream to the declared inclusive date interval."""
    result: dict[str, pd.DataFrame] = {}
    for timeframe, frame in frames.items():
        index = pd.DatetimeIndex(frame.index)
        result[timeframe] = frame.loc[make_train_mask(index, end, start)]
    return result


def _configured_timeframes(block: Any, default: tuple[str, ...]) -> set[str]:
    configured = block.get("timeframes") if block is not None else None
    return {str(value).upper() for value in configured} if configured else set(default)


def candidate_supported(cfg: DictConfig, idea: str, timeframe: str) -> bool:
    """Return whether the resolved config enables this candidate source."""
    features = cfg.features
    timeframe = timeframe.upper()
    strategy_state = bool(features.get("include_strategy_state", False))
    if idea == "standard_deviation":
        block = features.get("entry_ideas")
        return bool(block and block.get("enabled", False)) and timeframe in _configured_timeframes(
            block, TIMEFRAMES
        )
    if idea == "order_block":
        block = features.get("order_blocks")
        return bool(block and block.get("enabled", False)) and timeframe in _configured_timeframes(
            block, TIMEFRAMES
        )
    if idea == "fvg_retest":
        if not bool(features.get("include_fvg_ifvg", False)):
            return False
        configured = features.get("fvg_timeframes")
        timeframes = (
            {str(value).upper() for value in configured}
            if configured
            else {
                "M1",
                *[str(value).upper() for value in features.get("htf_timeframes", TIMEFRAMES[1:])],
            }
        )
        return timeframe in timeframes
    if idea == "po3":
        if not strategy_state:
            return False
        if timeframe == "M1":
            return True
        block = features.get("po3_state_mtf")
        return bool(block and block.get("enabled", False)) and timeframe in _configured_timeframes(
            block, TIMEFRAMES
        )
    if idea in {"ifvg_retest", "ifvg_unretested"}:
        if not strategy_state:
            return False
        if timeframe == "M1":
            return True
        block = features.get("ifvg_mtf")
        return bool(block and block.get("enabled", False)) and timeframe in _configured_timeframes(
            block, TIMEFRAMES
        )
    return False
