"""Validated MT5 live-risk configuration shared by live entry points."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any, TypedDict, cast

from loguru import logger

DEFAULT_RISK_PER_SYMBOL = 0.01
DEFAULT_MAX_TOTAL_RISK = 0.02
DEFAULT_STOP_LOSS_PIPS = 50.0
DEFAULT_INTERVAL_MINUTES = 1.0
DEFAULT_EXECUTION_SLIPPAGE_POINTS = 5.0
DEFAULT_COMMISSION_PER_LOT = 0.0


class LiveRiskOverrides(TypedDict):
    """Validated values passed to the RL paper/live entrypoint."""

    risk_per_symbol: float
    max_total_risk: float
    risk_per_symbol_usd_cap: float | None
    stop_loss_pips: float
    interval_minutes: float
    execution_slippage_points: float
    commission_per_lot: float


@dataclass(frozen=True, slots=True)
class LiveRiskConfiguration:
    """Risk sizing and polling settings for the MT5 RL live runtime."""

    risk_per_symbol: float = DEFAULT_RISK_PER_SYMBOL
    max_total_risk: float = DEFAULT_MAX_TOTAL_RISK
    risk_per_symbol_usd_cap: float | None = None
    stop_loss_pips: float = DEFAULT_STOP_LOSS_PIPS
    interval_minutes: float = DEFAULT_INTERVAL_MINUTES
    execution_slippage_points: float = DEFAULT_EXECUTION_SLIPPAGE_POINTS
    commission_per_lot: float = DEFAULT_COMMISSION_PER_LOT

    def as_dict(self) -> LiveRiskOverrides:
        """Return the validated risk settings as a plain mapping.

        Returns:
            Validated risk values, including the optional USD sizing cap.
        """
        values = asdict(self)
        return {
            "risk_per_symbol": float(values["risk_per_symbol"]),
            "max_total_risk": float(values["max_total_risk"]),
            "risk_per_symbol_usd_cap": values["risk_per_symbol_usd_cap"],
            "stop_loss_pips": float(values["stop_loss_pips"]),
            "interval_minutes": float(values["interval_minutes"]),
            "execution_slippage_points": float(values["execution_slippage_points"]),
            "commission_per_lot": float(values["commission_per_lot"]),
        }


def _read_value(block: Any, key: str) -> Any:
    """Read value.

    Args:
        block: Block used by the operation described above.
        key: Text or path value identifying the key.

    Returns:
        Result of read value.
    """
    if isinstance(block, Mapping):
        return block.get(key)
    getter = getattr(block, "get", None)
    if callable(getter):
        return getter(key, None)
    return getattr(block, key, None)


def load_live_risk_configuration(cfg: Any) -> LiveRiskConfiguration:
    """Resolve risk values from ``live_risk_overrides`` and validate them.

    Missing configuration fields retain the documented repository defaults
    with a warning. Non-finite or out-of-range risk and execution-cost values
    fail closed so an incomplete config cannot silently enable invalid sizing.

    Args:
        cfg: Run configuration used by this operation.

    Returns:
        Result of resolve risk values from ``live_risk_overrides`` and validate them.
    """
    block = _read_value(cfg, "live_risk_overrides")
    defaults = LiveRiskConfiguration()
    if block is None:
        logger.warning(
            "no live_risk_overrides block in run config; using repository defaults {}",
            defaults.as_dict(),
        )

    values: dict[str, float] = {}
    risk_per_symbol_usd_cap: float | None = None
    for key, default in defaults.as_dict().items():
        if key == "risk_per_symbol_usd_cap":
            ftmo = _read_value(cfg, "ftmo")
            raw_cap = _read_value(ftmo, "risk_sizing_limit_usd")
            if raw_cap is None:
                raw_cap = _read_value(ftmo, "risk_per_trade_limit")
            if raw_cap is None:
                risk_per_symbol_usd_cap = None
                continue
            if isinstance(raw_cap, bool):
                raise ValueError("ftmo.risk_sizing_limit_usd must be a finite positive number")
            try:
                cap = float(raw_cap)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "ftmo.risk_sizing_limit_usd must be a finite positive number"
                ) from exc
            if not math.isfinite(cap) or cap <= 0.0:
                raise ValueError("ftmo.risk_sizing_limit_usd must be a finite positive number")
            risk_per_symbol_usd_cap = cap
            continue
        if key == "execution_slippage_points":
            raw_value = _read_value(_read_value(cfg, "costs"), "slippage_points")
            config_path = "costs.slippage_points"
            allow_zero = True
        elif key == "commission_per_lot":
            raw_value = _read_value(_read_value(cfg, "costs"), "commission_per_lot")
            config_path = "costs.commission_per_lot"
            allow_zero = True
        else:
            raw_value = _read_value(block, key)
            config_path = f"live_risk_overrides.{key}"
            allow_zero = False
        if raw_value is None:
            logger.warning("{} missing; using default {}", config_path, default)
            values[key] = cast(float, default)
            continue
        if isinstance(raw_value, bool):
            qualifier = "non-negative" if allow_zero else "positive"
            raise ValueError(f"{config_path} must be a finite {qualifier} number")
        try:
            value = float(raw_value)
        except (TypeError, ValueError) as exc:
            qualifier = "non-negative" if allow_zero else "positive"
            raise ValueError(f"{config_path} must be a finite {qualifier} number") from exc
        if not math.isfinite(value) or value < 0.0 or (not allow_zero and value == 0.0):
            qualifier = "non-negative" if allow_zero else "positive"
            raise ValueError(f"{config_path} must be a finite {qualifier} number")
        values[key] = value

    return LiveRiskConfiguration(
        **values,
        risk_per_symbol_usd_cap=risk_per_symbol_usd_cap,
    )


__all__ = ["LiveRiskConfiguration", "LiveRiskOverrides", "load_live_risk_configuration"]
