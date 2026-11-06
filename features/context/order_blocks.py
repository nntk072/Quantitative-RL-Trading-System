"""Causal, context-qualified order-block zones.

This operational definition records the last opposing candle before an ATR-sized
displacement closes through a previously confirmed swing. It is a reproducible
feature definition, not evidence that the pattern has predictive value. It is
independent of PO3: no PO3 phase, sweep, or IFVG confirmation is required.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from features.technical.indicators import atr
from features.technical.structure import structure_levels


@dataclass
class _DiagnosticZone:
    zone_id: int
    low: float
    high: float
    created_at: int
    origin_at: int
    pending: tuple[int, float] | None = None


def _build_order_block_features(
    bars: pd.DataFrame,
    *,
    swing_period: int = 5,
    impulse_atr: float = 0.5,
    search_bars: int = 10,
    max_age_bars: int = 240,
    atr_period: int = 14,
    capture_events: bool,
) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    """Build scalar features and optionally retain the per-zone event ledger.

    A bullish block is the last bearish candle in the configured lookback
    before a bullish displacement closes above the prior confirmed swing high.
    A bearish block mirrors that rule. The zone becomes observable at the
    displacement bar close. Later bars may signal a zone retest. Close-through
    of the distal edge or expiry deactivates the zone.

    Args:
        bars: Market bars to process.
        swing_period: Numeric value used for the swing period.
        impulse_atr: Numeric value used for the impulse atr.
        search_bars: Market bar or price data used for return active bullish/bearish OB zones, retests, ages, and ATR distances.
        max_age_bars: Market bar or price data used for return active bullish/bearish OB zones, retests, ages, and ATR distances.
        atr_period: Numeric value used for the atr period.
        capture_events: Whether to retain every active zone's diagnostic retest events.

    Returns:
        Scalar features and, when requested, a zone-scoped retest event ledger.
    """
    if swing_period < 1 or search_bars < 1 or max_age_bars < 1:
        raise ValueError("order-block periods and age must be positive")
    if not np.isfinite(impulse_atr) or impulse_atr < 0.0:
        raise ValueError("impulse_atr must be finite and nonnegative")
    required = {"open", "high", "low", "close"}
    missing = required.difference(bars.columns)
    if missing:
        raise ValueError(f"order-block bars missing columns: {sorted(missing)}")

    n = len(bars)
    opens = bars["open"].to_numpy(dtype=float)
    highs = bars["high"].to_numpy(dtype=float)
    lows = bars["low"].to_numpy(dtype=float)
    closes = bars["close"].to_numpy(dtype=float)
    atr_values = atr(bars, period=atr_period).to_numpy(dtype=float)
    levels = structure_levels(bars, swing_period=swing_period)
    prior_high = levels["last_swing_high"].shift(1).to_numpy(dtype=float)
    prior_low = levels["last_swing_low"].shift(1).to_numpy(dtype=float)

    columns = {
        "ob_bull_active": np.zeros(n),
        "ob_bull_retest": np.zeros(n),
        "ob_bull_low": np.full(n, np.nan),
        "ob_bull_high": np.full(n, np.nan),
        "ob_bull_mid": np.full(n, np.nan),
        "ob_bull_origin_time_ms": np.full(n, np.nan),
        "ob_bull_retest_confirmed_at_time_ns": np.full(n, np.nan),
        "ob_bull_age": np.full(n, np.nan),
        "ob_bull_distance_atr": np.full(n, np.nan),
        "ob_bull_new": np.zeros(n),
        "ob_bear_active": np.zeros(n),
        "ob_bear_retest": np.zeros(n),
        "ob_bear_low": np.full(n, np.nan),
        "ob_bear_high": np.full(n, np.nan),
        "ob_bear_mid": np.full(n, np.nan),
        "ob_bear_origin_time_ms": np.full(n, np.nan),
        "ob_bear_retest_confirmed_at_time_ns": np.full(n, np.nan),
        "ob_bear_age": np.full(n, np.nan),
        "ob_bear_distance_atr": np.full(n, np.nan),
        "ob_bear_new": np.zeros(n),
    }
    zones: dict[str, tuple[float, float, int, int] | None] = {"bull": None, "bear": None}
    scalar_zone_ids: dict[str, int | None] = {"bull": None, "bear": None}
    pending_retests: dict[str, tuple[int, float] | None] = {"bull": None, "bear": None}
    diagnostic_zones: dict[str, list[_DiagnosticZone]] = {"bull": [], "bear": []}
    zone_sequence = 0
    retest_events: list[dict[str, int | float | str | bool]] = []
    times_ms = (
        pd.DatetimeIndex(bars.index).to_numpy(dtype="datetime64[ns]").view(np.int64) // 1_000_000
    )

    for i in range(n):
        atr_now = atr_values[i]
        bullish_break = (
            np.isfinite(prior_high[i])
            and closes[i] > prior_high[i]
            and np.isfinite(atr_now)
            and closes[i] - opens[i] >= impulse_atr * atr_now
        )
        bearish_break = (
            np.isfinite(prior_low[i])
            and closes[i] < prior_low[i]
            and np.isfinite(atr_now)
            and opens[i] - closes[i] >= impulse_atr * atr_now
        )
        if bullish_break:
            for j in range(i - 1, max(-1, i - search_bars - 1), -1):
                if closes[j] < opens[j]:
                    zone_sequence += 1
                    zones["bull"] = (float(lows[j]), float(highs[j]), i, j)
                    scalar_zone_ids["bull"] = zone_sequence
                    pending_retests["bull"] = None
                    if capture_events:
                        diagnostic_zones["bull"].append(
                            _DiagnosticZone(
                                zone_id=zone_sequence,
                                low=float(lows[j]),
                                high=float(highs[j]),
                                created_at=i,
                                origin_at=j,
                            )
                        )
                    columns["ob_bull_new"][i] = 1.0
                    break
        if bearish_break:
            for j in range(i - 1, max(-1, i - search_bars - 1), -1):
                if closes[j] > opens[j]:
                    zone_sequence += 1
                    zones["bear"] = (float(lows[j]), float(highs[j]), i, j)
                    scalar_zone_ids["bear"] = zone_sequence
                    pending_retests["bear"] = None
                    if capture_events:
                        diagnostic_zones["bear"].append(
                            _DiagnosticZone(
                                zone_id=zone_sequence,
                                low=float(lows[j]),
                                high=float(highs[j]),
                                created_at=i,
                                origin_at=j,
                            )
                        )
                    columns["ob_bear_new"][i] = 1.0
                    break

        for side in ("bull", "bear"):
            zone = zones[side]
            if zone is None:
                continue
            zone_low, zone_high, created_at, origin_at = zone
            age = i - created_at
            invalidated = closes[i] < zone_low if side == "bull" else closes[i] > zone_high
            if age > max_age_bars or invalidated:
                zones[side] = None
                scalar_zone_ids[side] = None
                pending_retests[side] = None
                continue
            active = f"ob_{side}_active"
            columns[active][i] = 1.0
            columns[f"ob_{side}_low"][i] = zone_low
            columns[f"ob_{side}_high"][i] = zone_high
            columns[f"ob_{side}_mid"][i] = 0.5 * (zone_low + zone_high)
            columns[f"ob_{side}_origin_time_ms"][i] = float(times_ms[origin_at])
            columns[f"ob_{side}_age"][i] = float(age)
            if np.isfinite(atr_now) and atr_now > 0.0:
                if closes[i] > zone_high:
                    distance = closes[i] - zone_high
                elif closes[i] < zone_low:
                    distance = closes[i] - zone_low
                else:
                    distance = 0.0
                columns[f"ob_{side}_distance_atr"][i] = distance / atr_now
            pending = pending_retests[side]
            if pending is not None and i > pending[0]:
                confirms = closes[i] > pending[1] if side == "bull" else closes[i] < pending[1]
                if confirms:
                    columns[f"ob_{side}_retest"][i] = 1.0
                    columns[f"ob_{side}_retest_confirmed_at_time_ns"][i] = pd.Timestamp(
                        bars.index[i]
                    ).value
                    pending_retests[side] = None
            if age > 0 and lows[i] <= zone_high and highs[i] >= zone_low:
                pending_retests[side] = (i, highs[i] if side == "bull" else lows[i])

        if capture_events:
            for side in ("bull", "bear"):
                active_zones: list[_DiagnosticZone] = []
                for diagnostic_zone in diagnostic_zones[side]:
                    created_at = diagnostic_zone.created_at
                    zone_low = diagnostic_zone.low
                    zone_high = diagnostic_zone.high
                    age = i - created_at
                    invalidated = closes[i] < zone_low if side == "bull" else closes[i] > zone_high
                    if age <= 0 or age > max_age_bars or invalidated:
                        if age <= 0:
                            active_zones.append(diagnostic_zone)
                        continue
                    active_zones.append(diagnostic_zone)
                    pending = diagnostic_zone.pending
                    if pending is not None:
                        pending_bar, pending_extreme = pending
                        if i > pending_bar:
                            confirms = (
                                closes[i] > pending_extreme
                                if side == "bull"
                                else closes[i] < pending_extreme
                            )
                            if confirms:
                                origin_at = diagnostic_zone.origin_at
                                retest_events.append(
                                    {
                                        "zone_id": diagnostic_zone.zone_id,
                                        "side": side,
                                        "confirmation_bar": i,
                                        "confirmation_time_ns": pd.Timestamp(bars.index[i]).value,
                                        "source_origin_bar": origin_at,
                                        "source_origin_time_ns": pd.Timestamp(
                                            bars.index[origin_at]
                                        ).value,
                                        "zone_low": zone_low,
                                        "zone_high": zone_high,
                                        "selected_by_scalar": (
                                            scalar_zone_ids[side] == diagnostic_zone.zone_id
                                            and columns[f"ob_{side}_retest"][i] > 0.0
                                        ),
                                    }
                                )
                                diagnostic_zone.pending = None
                    if lows[i] <= zone_high and highs[i] >= zone_low:
                        diagnostic_zone.pending = (
                            i,
                            highs[i] if side == "bull" else lows[i],
                        )
                diagnostic_zones[side] = active_zones

    scalar = pd.DataFrame(columns, index=bars.index)
    if not capture_events:
        return scalar, None
    ledger = pd.DataFrame(
        retest_events,
        columns=[
            "zone_id",
            "side",
            "confirmation_bar",
            "confirmation_time_ns",
            "source_origin_bar",
            "source_origin_time_ns",
            "zone_low",
            "zone_high",
            "selected_by_scalar",
        ],
    )
    return scalar, ledger


def build_order_block_features_with_event_ledger(
    bars: pd.DataFrame,
    *,
    swing_period: int = 5,
    impulse_atr: float = 0.5,
    search_bars: int = 10,
    max_age_bars: int = 240,
    atr_period: int = 14,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return scalar features and per-zone retest events for causal diagnostics.

    The scalar projection preserves latest-zone behavior. Ledger rows also
    include confirmations from older still-active zones without changing the
    model-facing feature output.

    Args:
        bars: Chronological OHLC bars used to identify order blocks.
        swing_period: Lookback for confirming local swing structure.
        impulse_atr: Minimum displacement after the block, measured in ATR.
        search_bars: Maximum backward search for the source candle.
        max_age_bars: Maximum lifetime of an active order-block zone.
        atr_period: Lookback used to calculate the volatility scale.

    Returns:
        Scalar feature frame and event ledger of confirmed zone retests.
    """
    scalar, ledger = _build_order_block_features(
        bars,
        swing_period=swing_period,
        impulse_atr=impulse_atr,
        search_bars=search_bars,
        max_age_bars=max_age_bars,
        atr_period=atr_period,
        capture_events=True,
    )
    assert ledger is not None
    return scalar, ledger


def build_order_block_features(
    bars: pd.DataFrame,
    *,
    swing_period: int = 5,
    impulse_atr: float = 0.5,
    search_bars: int = 10,
    max_age_bars: int = 240,
    atr_period: int = 14,
) -> pd.DataFrame:
    """Return the existing scalar latest-zone order-block feature view.

    Args:
        bars: Chronological OHLC bars used to identify order blocks.
        swing_period: Lookback for confirming local swing structure.
        impulse_atr: Minimum displacement after the block, measured in ATR.
        search_bars: Maximum backward search for the source candle.
        max_age_bars: Maximum lifetime of an active order-block zone.
        atr_period: Lookback used to calculate the volatility scale.

    Returns:
        Feature frame containing the latest active order-block projection.
    """
    features, ledger = _build_order_block_features(
        bars,
        swing_period=swing_period,
        impulse_atr=impulse_atr,
        search_bars=search_bars,
        max_age_bars=max_age_bars,
        atr_period=atr_period,
        capture_events=False,
    )
    assert ledger is None
    return features


__all__ = ["build_order_block_features", "build_order_block_features_with_event_ledger"]
