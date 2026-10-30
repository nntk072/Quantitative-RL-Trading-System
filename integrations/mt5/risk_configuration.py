"""Validated MT5 live-risk configuration shared by live entry points."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

from loguru import logger

DEFAULT_RISK_PER_SYMBOL = 0.01
DEFAULT_MAX_TOTAL_RISK = 0.02
DEFAULT_STOP_LOSS_PIPS = 50.0
DEFAULT_INTERVAL_MINUTES = 1.0


@dataclass(frozen=True, slots=True)
class LiveRiskConfiguration:
    """Risk sizing and polling settings for the MT5 RL live runtime."""

    risk_per_symbol: float = DEFAULT_RISK_PER_SYMBOL
    max_total_risk: float = DEFAULT_MAX_TOTAL_RISK
    stop_loss_pips: float = DEFAULT_STOP_LOSS_PIPS
    interval_minutes: float = DEFAULT_INTERVAL_MINUTES

    def as_dict(self) -> dict[str, float]:
        return asdict(self)


def _read_value(block: Any, key: str) -> Any:
    if isinstance(block, Mapping):
        return block.get(key)
    getter = getattr(block, "get", None)
    if callable(getter):
        return getter(key, None)
    return getattr(block, key, None)


def load_live_risk_configuration(cfg: Any) -> LiveRiskConfiguration:
    """Resolve risk values from ``live_risk_overrides`` and validate them.

    Missing configuration fields retain the documented repository defaults
    with a warning. Invalid, non-finite, or non-positive values fail closed so
    an incomplete live configuration cannot silently enable invalid sizing.
    """
    block = _read_value(cfg, "live_risk_overrides")
    defaults = LiveRiskConfiguration()
    if block is None:
        logger.warning(
            "no live_risk_overrides block in run config; using repository defaults {}",
            defaults.as_dict(),
        )
        return defaults

    values: dict[str, float] = {}
    for key, default in defaults.as_dict().items():
        raw_value = _read_value(block, key)
        if raw_value is None:
            logger.warning("live_risk_overrides.{} missing; using default {}", key, default)
            values[key] = default
            continue
        if isinstance(raw_value, bool):
            raise ValueError(f"live_risk_overrides.{key} must be a finite positive number")
        try:
            value = float(raw_value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"live_risk_overrides.{key} must be a finite positive number") from exc
        if not math.isfinite(value) or value <= 0.0:
            raise ValueError(f"live_risk_overrides.{key} must be a finite positive number")
        values[key] = value

    return LiveRiskConfiguration(**values)


__all__ = ["LiveRiskConfiguration", "load_live_risk_configuration"]
