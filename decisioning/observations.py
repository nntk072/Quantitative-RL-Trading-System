"""Versioned account-state observation contracts.

Observation meaning is part of a policy's input schema. In particular, equal
vector widths do not establish that two checkpoints use the same coordinates.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

import numpy as np

from decisioning.observation_state import ENTRY_STATES, entry_state_one_hot


def pad_observation_window(
    seq: np.ndarray[Any, Any],
    window: int,
) -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any]]:
    """Left-pad a sequence window and mark which rows contain real events.

    Args:
        seq: Seq used by the operation described above.
        window: Numeric value used for the window.

    Returns:
        Array returned by ``pad_observation_window``.
    """
    values = np.asarray(seq, dtype=np.float32)
    if not isinstance(window, (int, np.integer)) or isinstance(window, bool) or window <= 0:
        raise ValueError("observation window must be a positive integer")
    if values.ndim == 1:
        width = 1
        values = values.reshape(-1, 1)
    elif values.ndim == 2:
        width = int(values.shape[1])
    else:
        raise ValueError(f"observation sequence must be 1D or 2D, got {values.ndim}D")
    n_real = int(values.shape[0])
    mask = np.zeros(window, dtype=np.float32)
    if n_real >= window:
        return values[-window:], np.ones(window, dtype=np.float32)
    if n_real == 0:
        return np.zeros((window, width), dtype=np.float32), mask
    padded = np.pad(values, ((window - n_real, 0), (0, 0)), mode="constant", constant_values=0.0)
    mask[window - n_real :] = 1.0
    return cast(np.ndarray[Any, Any], padded.astype(np.float32)), mask


def normalized_account_vector(
    *,
    equity: float,
    initial_balance: float,
    pos_dir: float,
    open_pnl: float,
    dist_to_sl: float,
    trailing_dd: float,
    close: float,
    entry_state: str | None = None,
) -> np.ndarray[Any, Any]:
    """Build the legacy normalized account input coordinates.

    Args:
        equity: Current account equity in account currency.
        initial_balance: Numeric value used for the initial balance.
        pos_dir: Numeric value used for the pos dir.
        open_pnl: Numeric value used for the open pnl.
        dist_to_sl: Numeric value used for the dist to sl.
        trailing_dd: Numeric value used for the trailing dd.
        close: Numeric value used for the close.
        entry_state: Entry state used by the operation described above.

    Returns:
        Array returned by ``normalized_account_vector``.
    """
    scalar_inputs = {
        "equity": equity,
        "initial_balance": initial_balance,
        "pos_dir": pos_dir,
        "open_pnl": open_pnl,
        "dist_to_sl": dist_to_sl,
        "trailing_dd": trailing_dd,
        "close": close,
    }
    for name, value in scalar_inputs.items():
        if not np.isfinite(float(value)):
            raise ValueError(f"account-state-v1 input {name} must be finite")
    if initial_balance > 0.0 and equity <= 0.0:
        raise ValueError(
            "account-state-v1 equity must be positive when initial_balance is positive"
        )

    norm_equity = float(np.log(equity / initial_balance)) if initial_balance > 0 else 0.0
    norm_pnl = open_pnl / initial_balance if initial_balance > 0 else 0.0
    unrealised_r = (open_pnl / equity * 100.0) if equity > 0 else 0.0
    norm_dist = dist_to_sl / close if close > 0 else 0.0
    values = [norm_equity, pos_dir, norm_pnl, unrealised_r, norm_dist, float(trailing_dd)]
    if entry_state is not None:
        values.extend(entry_state_one_hot(entry_state))
    with np.errstate(over="ignore", invalid="ignore"):
        result = np.asarray(values, dtype=np.float32)
    if not np.isfinite(result).all():
        raise ValueError("account-state-v1 output coordinates must be finite")
    return result


OBSERVATION_SCHEMA_V1 = "account-state-v1"
OBSERVATION_SCHEMA_V2 = "account-state-v2"
OBSERVATION_SCHEMA_REPEATED_PAYOUT = "account-state-repeated-payout"
_LEGACY_REPEATED_PAYOUT_SCHEMA_ID = "account-state-v3-repeated-payout"

V1_COORDINATES = (
    "log_equity_over_initial",
    "position_direction",
    "open_pnl_over_initial",
    "unrealized_r_legacy",
    "initial_stop_width_over_price",
    "trailing_drawdown_pct",
)

V2_COORDINATES = (
    "log_equity_over_initial",
    "position_direction",
    "open_pnl_over_initial",
    "unrealized_r",
    "trailing_drawdown_over_limit",
    "daily_loss_over_limit",
    "remaining_daily_loss_budget_over_limit",
    "loss_from_initial_over_limit",
    "remaining_max_loss_budget_over_limit",
    "planned_risk_over_limit",
    "initial_stop_distance_over_price",
    "active_sl_headroom_over_initial_risk",
    "remaining_size_fraction",
    "position_age_over_scale",
    "tp1_hit",
    "tp2_hit",
    "tp3_hit",
    "distance_to_tp1_over_initial_risk",
    "distance_to_tp2_over_initial_risk",
    "distance_to_tp3_over_initial_risk",
    "sl_mode_fixed",
    "sl_mode_breakeven",
    "sl_mode_trailing",
    "tp_mode_fixed",
    "tp_mode_breakeven",
    "tp_mode_trailing",
    "exit_mode_structural",
    "exit_mode_ema",
)


@dataclass(frozen=True)
class ObservationSchema:
    """Explicit coordinate names and version for the account branch."""

    version: str
    coordinates: tuple[str, ...]
    entry_state_visibility: bool = False

    @property
    def width(self) -> int:
        """Return the total number of flattened observation coordinates.

        Returns:
            Numeric result returned by ``width``.
        """
        return len(self.coordinates)

    def to_dict(self) -> dict[str, Any]:
        """Return the ordered observation contract as JSON-compatible data.

        Returns:
            Mapping from ``str`` keys to ``Any`` values.
        """
        return {
            "version": self.version,
            "observation_width": self.width,
            "observation_coordinates": list(self.coordinates),
            "entry_state_visibility": self.entry_state_visibility,
        }


def build_observation_schema(
    version: str = OBSERVATION_SCHEMA_V1,
    *,
    entry_state_visibility: bool = False,
) -> ObservationSchema:
    """Return a named schema; never infer semantics from a vector width.

    Args:
        version: Text or path value identifying the version.
        entry_state_visibility: Whether to enable or require the entry state visibility.

    Returns:
        Result of return a named schema; never infer semantics from a vector width.
    """
    coordinates: tuple[str, ...]
    if version == OBSERVATION_SCHEMA_V1:
        coordinates = V1_COORDINATES
    elif version in (OBSERVATION_SCHEMA_V2, OBSERVATION_SCHEMA_REPEATED_PAYOUT):
        coordinates = V2_COORDINATES
    else:
        raise ValueError(f"unknown observation schema version: {version!r}")
    if entry_state_visibility:
        coordinates = (*coordinates, *(f"entry_state_{name.lower()}" for name in ENTRY_STATES))
    return ObservationSchema(version, coordinates, entry_state_visibility)


def _canonicalize_saved_observation_schema_id(schema_id: str) -> str:
    """Map the historical checkpoint identifier to its current domain name.

    This mapping is limited to persisted metadata. New configs and runtime
    schemas must use the current identifier directly.
    """
    if schema_id == _LEGACY_REPEATED_PAYOUT_SCHEMA_ID:
        return OBSERVATION_SCHEMA_REPEATED_PAYOUT
    return schema_id


def requires_normalized_account_observation(version: str) -> bool:
    """Whether an account observation schema requires normalized account values."""
    return version in (OBSERVATION_SCHEMA_V2, OBSERVATION_SCHEMA_REPEATED_PAYOUT)


def validate_observation_schema(
    actual: dict[str, Any] | None,
    expected: ObservationSchema,
    *,
    allow_legacy_v1: bool = False,
) -> None:
    """Validate saved observation semantics before checkpoint evaluation/resume.

    Args:
        actual: Key-value data used for the actual.
        expected: Expected used by the operation described above.
        allow_legacy_v1: Whether to enable or require the allow legacy v1.
    """
    if actual is None:
        if expected.version == OBSERVATION_SCHEMA_V1 and allow_legacy_v1:
            return
        raise ValueError(
            "checkpoint has no observation schema metadata; explicit schema metadata is "
            f"required for {expected.version}"
        )
    saved = {
        "version": _canonicalize_saved_observation_schema_id(str(actual.get("version"))),
        "observation_width": actual.get("observation_width"),
        "observation_coordinates": actual.get("observation_coordinates"),
        "entry_state_visibility": actual.get("entry_state_visibility"),
    }
    if saved != expected.to_dict():
        raise ValueError(
            "checkpoint observation schema differs from requested environment schema: "
            f"saved={saved!r}, requested={expected.to_dict()!r}"
        )


def _ratio(numerator: float, denominator: float) -> float:
    """Process the requested value.

    Args:
        numerator: Numeric value used for the numerator.
        denominator: Numeric value used for the denominator.

    Returns:
        Numeric result returned by ``_ratio``.
    """
    return float(numerator / denominator) if denominator > 0.0 else 0.0


def account_state_v2(
    *,
    equity: float,
    initial_balance: float,
    position_direction: float,
    open_pnl: float,
    planned_risk_usd: float = 0.0,
    trailing_drawdown_pct: float = 0.0,
    trailing_drawdown_limit: float = 0.0,
    daily_loss: float = 0.0,
    daily_loss_limit: float = 0.0,
    loss_from_initial: float = 0.0,
    max_loss_limit: float = 0.0,
    risk_per_trade_limit: float = 0.0,
    current_price: float = 0.0,
    entry_price: float = 0.0,
    initial_sl_price: float | None = None,
    active_sl_price: float | None = None,
    remaining_size: float = 0.0,
    initial_size: float = 0.0,
    position_age_bars: float = 0.0,
    position_age_scale_bars: float = 60.0,
    tp_hit_mask: int = 0,
    tp_prices: tuple[float | None, float | None, float | None] = (None, None, None),
    sl_mode: str = "fixed",
    tp_mode: str = "fixed",
    exit_mode: str = "structural",
    entry_state: str | None = None,
) -> np.ndarray[Any, Any]:
    """Build normalized v2 state without changing account or risk semantics.

    The caller supplies the policy-canonical ``daily_loss`` value. The current
    account policy uses session-equity loss, including open PnL; the
    repeated-payout schema retains this coordinate layout while identifying its
    account-policy semantics explicitly.
    ``active_sl_headroom_over_initial_risk`` is positive when the current price
    is on the safe side of the active stop.

    Args:
        equity: Current account equity in account currency.
        initial_balance: Numeric value used for the initial balance.
        position_direction: Numeric value used for the position direction.
        open_pnl: Numeric value used for the open pnl.
        planned_risk_usd: Numeric value used for the planned risk usd.
        trailing_drawdown_pct: Numeric value used for the trailing drawdown pct.
        trailing_drawdown_limit: Numeric value used for the trailing drawdown limit.
        daily_loss: Numeric value used for the daily loss.
        daily_loss_limit: Numeric value used for the daily loss limit.
        loss_from_initial: Numeric value used for the loss from initial.
        max_loss_limit: Numeric value used for the max loss limit.
        risk_per_trade_limit: Numeric value used for the risk per trade limit.
        current_price: Numeric value used for the current price.
        entry_price: Price at which the position was opened.
        initial_sl_price: Initial sl price used by the operation described above.
        active_sl_price: Active sl price used by the operation described above.
        remaining_size: Number specifying the remaining size for this operation.
        initial_size: Number specifying the initial size for this operation.
        position_age_bars: Market bar or price data used for build normalized v2 state without changing account or risk semantics.
        position_age_scale_bars: Market bar or price data used for build normalized v2 state without changing account or risk semantics.
        tp_hit_mask: Boolean or status values aligned with the input tp hit.
        tp_prices: Market bar or price data used for build normalized v2 state without changing account or risk semantics.
        sl_mode: Text or path value identifying the sl mode.
        tp_mode: Text or path value identifying the tp mode.
        exit_mode: Text or path value identifying the exit mode.
        entry_state: Entry state used by the operation described above.

    Returns:
        Array returned by ``account_state_v2``.
    """
    scalar_inputs = {
        "equity": equity,
        "initial_balance": initial_balance,
        "position_direction": position_direction,
        "open_pnl": open_pnl,
        "planned_risk_usd": planned_risk_usd,
        "trailing_drawdown_pct": trailing_drawdown_pct,
        "trailing_drawdown_limit": trailing_drawdown_limit,
        "daily_loss": daily_loss,
        "daily_loss_limit": daily_loss_limit,
        "loss_from_initial": loss_from_initial,
        "max_loss_limit": max_loss_limit,
        "risk_per_trade_limit": risk_per_trade_limit,
        "current_price": current_price,
        "entry_price": entry_price,
        "remaining_size": remaining_size,
        "initial_size": initial_size,
        "position_age_bars": position_age_bars,
        "position_age_scale_bars": position_age_scale_bars,
    }
    for name, value in scalar_inputs.items():
        if not np.isfinite(float(value)):
            raise ValueError(f"account-state-v2 input {name} must be finite")
    if initial_sl_price is not None and not np.isfinite(float(initial_sl_price)):
        raise ValueError("account-state-v2 input initial_sl_price must be finite")
    if active_sl_price is not None and not np.isfinite(float(active_sl_price)):
        raise ValueError("account-state-v2 input active_sl_price must be finite")
    if any(target is not None and not np.isfinite(float(target)) for target in tp_prices):
        raise ValueError("account-state-v2 input tp_prices must be finite when provided")
    if len(tp_prices) != 3:
        raise ValueError("account-state-v2 requires exactly three take-profit prices")
    if float(position_direction) not in (-1.0, 0.0, 1.0):
        raise ValueError("account-state-v2 position_direction must be -1, 0, or 1")
    if float(position_age_scale_bars) <= 0.0:
        raise ValueError("account-state-v2 position_age_scale_bars must be positive")
    if float(position_age_bars) < 0.0:
        raise ValueError("account-state-v2 position_age_bars must be non-negative")
    if float(remaining_size) < 0.0 or float(initial_size) < 0.0:
        raise ValueError("account-state-v2 position sizes must be non-negative")
    if not isinstance(tp_hit_mask, (int, np.integer)) or isinstance(tp_hit_mask, bool):
        raise ValueError("account-state-v2 tp_hit_mask must be an integer bitmask")
    if tp_hit_mask < 0 or tp_hit_mask > 0b111:
        raise ValueError("account-state-v2 tp_hit_mask must contain only three target bits")
    if sl_mode not in {"fixed", "breakeven", "trailing"}:
        raise ValueError(f"unsupported account-state-v2 sl_mode: {sl_mode!r}")
    if tp_mode not in {"fixed", "breakeven", "trailing"}:
        raise ValueError(f"unsupported account-state-v2 tp_mode: {tp_mode!r}")
    if exit_mode not in {"structural", "ema_21"}:
        raise ValueError(f"unsupported account-state-v2 exit_mode: {exit_mode!r}")

    has_position = float(position_direction) != 0.0
    initial_risk = (
        abs(float(entry_price) - float(initial_sl_price))
        if has_position and initial_sl_price is not None
        else 0.0
    )
    stop_width = (
        abs(float(entry_price) - float(initial_sl_price))
        if has_position and initial_sl_price is not None
        else 0.0
    )
    active_headroom = (
        float(position_direction) * (float(current_price) - float(active_sl_price))
        if has_position and active_sl_price is not None
        else 0.0
    )
    target_distances = [
        float(position_direction) * (float(target) - float(current_price))
        if has_position and target is not None
        else 0.0
        for target in tp_prices
    ]
    daily_ratio = _ratio(float(daily_loss), float(daily_loss_limit))
    max_loss_ratio = _ratio(float(loss_from_initial), float(max_loss_limit))
    sl_modes = (
        tuple(float(sl_mode == mode) for mode in ("fixed", "breakeven", "trailing"))
        if has_position
        else (0.0, 0.0, 0.0)
    )
    tp_modes = (
        tuple(float(tp_mode == mode) for mode in ("fixed", "breakeven", "trailing"))
        if has_position
        else (0.0, 0.0, 0.0)
    )
    exit_modes = (
        (float(exit_mode == "structural"), float(exit_mode == "ema_21"))
        if has_position
        else (0.0, 0.0)
    )
    values = [
        float(np.log(equity / initial_balance)) if initial_balance > 0.0 and equity > 0.0 else 0.0,
        float(position_direction),
        _ratio(float(open_pnl), float(initial_balance)),
        _ratio(float(open_pnl), float(planned_risk_usd)) if has_position else 0.0,
        _ratio(float(trailing_drawdown_pct), float(trailing_drawdown_limit)),
        daily_ratio,
        1.0 - daily_ratio if daily_loss_limit > 0.0 else 0.0,
        max_loss_ratio,
        1.0 - max_loss_ratio if max_loss_limit > 0.0 else 0.0,
        _ratio(float(planned_risk_usd), float(risk_per_trade_limit)) if has_position else 0.0,
        _ratio(stop_width, float(current_price)),
        _ratio(active_headroom, initial_risk),
        _ratio(float(remaining_size), float(initial_size)) if has_position else 0.0,
        _ratio(float(position_age_bars), float(position_age_scale_bars)) if has_position else 0.0,
        *(
            float(bool(int(tp_hit_mask) & (1 << index))) if has_position else 0.0
            for index in range(3)
        ),
        *(_ratio(distance, initial_risk) for distance in target_distances),
        *sl_modes,
        *tp_modes,
        *exit_modes,
    ]
    if entry_state is not None:
        values.extend(entry_state_one_hot(entry_state))
    result = np.asarray(values, dtype=np.float32)
    if result.ndim != 1 or not np.isfinite(result).all():
        raise ValueError("account-state-v2 produced a non-finite observation")
    return result
