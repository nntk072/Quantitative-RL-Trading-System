"""Causal fixed-width candidate-geometry observations for trade-setup policies."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from decisioning.trade_setup import (
    CANDIDATE_GEOMETRY_FEATURE_NAMES,
    NO_TRADE_ID,
    TRADE_SETUP_CANDIDATES,
    candidate_geometry_slot,
    candidate_geometry_slot_count,
    candidate_geometry_slot_semantics,
)
from features.context.entry_ideas import entry_idea_context
from features.context.trade_setup_candidates import trade_setup_candidate_event_identities
from trading.orders import limit_price_from_atr_offset, place_strategy_order

_FEATURE_INDEX = {name: index for index, name in enumerate(CANDIDATE_GEOMETRY_FEATURE_NAMES)}


def _finite(value: Any) -> float | None:
    """Convert a scalar to a finite float when possible.

    Args:
        value: Scalar-like value to convert.

    Returns:
        A finite float, or ``None`` for invalid and non-finite values.
    """
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if np.isfinite(numeric) else None


def _source_zone(
    row: Any, candidate: Any, context: dict[str, Any] | None = None
) -> tuple[float, float] | None:
    """Resolve causal source-zone geometry used by candidate proposal audits.

    Args:
        row: Causal feature row containing source-zone values.
        candidate: Setup definition identifying the source idea and timeframe.
        context: Optional precomputed entry-idea context for the candidate direction.

    Returns:
        Source-zone low and high bounds, or ``None`` when unavailable.
    """
    if candidate.idea == "standard_deviation":
        timeframe = str(candidate.setup_timeframe).upper()
        prefix = "" if timeframe == "M1" else f"{timeframe}_"
        low = _finite(row.get(f"{prefix}standard_deviation_band_low", np.nan))
        high = _finite(row.get(f"{prefix}standard_deviation_band_high", np.nan))
        if low is not None and high is not None and low <= high:
            return low, high
        return None

    context = (
        entry_idea_context(row, int(candidate.direction), include_zones=True)
        if context is None
        else context
    )
    matching = [
        zone
        for zone in context.get("zones", ())
        if str(zone.get("idea", "")) == str(candidate.idea)
        and str(zone.get("timeframe", "")).upper() == str(candidate.setup_timeframe).upper()
    ]
    if candidate.idea == "po3":
        ifvg = [zone for zone in matching if str(zone.get("family", "")).lower() == "ifvg"]
        if ifvg:
            matching = ifvg
    if not matching:
        return None
    matching.sort(
        key=lambda zone: (
            int(zone.get("start_time_ns") or 0),
            float(zone.get("low", np.inf)),
            float(zone.get("high", np.inf)),
        ),
        reverse=True,
    )
    low = _finite(matching[0].get("low"))
    high = _finite(matching[0].get("high"))
    if low is None or high is None or low > high:
        return None
    return low, high


def _reference_quote(env: Any, index: int) -> tuple[float, float] | None:
    """Use the last causal tick in the decision bar, with bar-price fallback.

    Args:
        env: Environment providing the tick book and bar quote.
        index: Completed decision-bar index.

    Returns:
        Valid bid and ask values, or ``None`` when a required quote is absent.
    """
    bar = env._bar_at(index)
    if getattr(env, "_tickbook", None) is not None:
        bar_time = pd.Timestamp(env._bar_time(index))
        last_quote = None
        for quote in env._tickbook.bar_quotes(
            bar_time, bar_minutes=max(1, int(round(float(env._minutes_per_step))))
        ):
            last_quote = quote
        if last_quote is not None:
            _quote_time, bid, ask = last_quote
            return float(bid), float(ask)
        if bool(getattr(env, "tick_execution_required", False)):
            return None
    bid, ask = env._bar_quote(bar)
    if not (np.isfinite(bid) and np.isfinite(ask) and 0.0 < bid <= ask):
        return None
    return float(bid), float(ask)


def _session_remaining(env: Any, index: int) -> tuple[int, float] | None:
    """Measure time to configured session close without reading future rows.

    Args:
        env: Environment providing session times and bar duration.
        index: Completed decision-bar index.

    Returns:
        Remaining bar count and normalized session time, or ``None`` if closed.
    """
    now = pd.Timestamp(env._bar_time(index))
    closes = getattr(env, "_scheduled_session_closes", {})
    close_text = closes.get(now.date().isoformat()) if isinstance(closes, dict) else None
    if not isinstance(close_text, str) or not close_text.strip():
        return None
    try:
        close = pd.Timestamp(f"{now.date().isoformat()} {close_text}").tz_localize(now.tz)
        start_text = str(getattr(env, "_session_start", ""))
        session_start = pd.Timestamp(f"{now.date().isoformat()} {start_text}").tz_localize(now.tz)
    except (TypeError, ValueError):
        return None
    decision_time = now + pd.Timedelta(minutes=float(env._minutes_per_step))
    session_duration = (close - session_start).total_seconds()
    seconds_remaining = (close - decision_time).total_seconds()
    if session_duration <= 0.0 or seconds_remaining <= 0.0:
        return None
    minutes_per_step = max(float(env._minutes_per_step), 1e-9)
    bars_remaining = max(1, int(np.ceil(seconds_remaining / (60.0 * minutes_per_step))))
    return bars_remaining, float(np.clip(seconds_remaining / session_duration, 0.0, 1.0))


def _candidate_age_fraction(env: Any, row: Any, candidate_id: int, index: int) -> float | None:
    """Measure candidate age from its latest identified source event.

    Args:
        env: Environment supplying the decision timestamp and age limit.
        row: Causal feature row containing candidate event identities.
        candidate_id: Stable trade-setup identifier.
        index: Completed bar index used for the decision.

    Returns:
        Age as a fraction of the configured limit, or ``None`` when invalid.
    """
    identities = trade_setup_candidate_event_identities(row, [candidate_id])
    if len(identities) != 1 or identities[0].status != "identified":
        return None
    source_times = [int(value) for _, value in identities[0].source_event_times_ns]
    if not source_times:
        return None
    decision_ns = pd.Timestamp(env._bar_time(index)).value + int(
        round(float(env._minutes_per_step) * 60.0 * 1_000_000_000)
    )
    age_bars = (decision_ns - max(source_times)) / max(
        float(env._minutes_per_step) * 60.0 * 1_000_000_000, 1.0
    )
    max_age = max(1, int(getattr(env, "candidate_max_age_bars", 1)))
    if age_bars < 0.0 or age_bars > max_age:
        return None
    return float(np.clip(age_bars / max_age, 0.0, 1.0))


def _geometry_distances(
    env: Any,
    row: Any,
    candidate: Any,
    entry_price: float,
    atr: float,
) -> tuple[float, float, float, float] | None:
    """Calculate executable stop and target distance ranges in ATR units.

    Args:
        env: Environment providing strategy, risk, and instrument settings.
        row: Causal feature row used to construct protective levels.
        candidate: Stable setup proposal whose geometry is being measured.
        entry_price: Proposed executable entry price.
        atr: Positive average true range used for normalization.

    Returns:
        Minimum and maximum stop and target distances, or ``None`` if unavailable.
    """
    placed = place_strategy_order(
        env.strategy,
        direction=int(candidate.direction),
        entry_price=float(entry_price),
        feat_row=row,
        min_dist=float(env._min_sl_distance(row)),
        sl_fraction=0.5,
        tp_fraction=0.5,
        exit_mode="structural",
        buffer_pts=float(env.sl_buffer_pts),
        max_tp_distance=float(env._max_tp_here()),
        rr_bounds=(float(env.rr_ratio_range[0]), float(env.rr_ratio_range[1])),
        htf=tuple(str(value) for value in env._target_timeframes),
        entry_timeframe_floor=str(candidate.setup_timeframe),
        standard_deviation_timeframes=(
            (str(candidate.setup_timeframe),)
            if str(candidate.idea) == "standard_deviation"
            else None
        ),
        allow_multi_tp=False,
        allow_simplex=True,
        price_increment=float(env.cost_model.point_size),
        trade_setup=candidate,
    )
    stop_distances = [abs(float(entry_price) - float(price)) / atr for _, price in placed.sl_menu]
    target_distances = [abs(float(price) - float(entry_price)) / atr for _, price in placed.tp_menu]
    if not stop_distances or not target_distances:
        return None
    values = (
        min(stop_distances),
        max(stop_distances),
        min(target_distances),
        max(target_distances),
    )
    return values if all(np.isfinite(value) and value > 0.0 for value in values) else None


def _feature_vector(
    *,
    candidate: Any,
    entry_type: str,
    entry_price: float,
    reference_price: float,
    zone: tuple[float, float],
    atr: float,
    spread: float,
    round_trip_cost: float,
    distances: tuple[float, float, float, float],
    ttl_fraction: float,
    age_fraction: float,
    session_fraction: float,
    source_zone_width_atr: float,
) -> np.ndarray[Any, np.dtype[np.float32]]:
    """Encode one proposal's causal geometry using the versioned feature order.

    Args:
        candidate: Stable setup semantics for the proposal.
        entry_type: Either ``market`` or ``limit``.
        entry_price: Proposed entry price.
        reference_price: Causal market price used for relative offsets.
        zone: Low and high bounds of the source zone.
        atr: Positive average true range.
        spread: Current bid-ask spread in price units.
        round_trip_cost: Estimated round-trip execution cost in price units.
        distances: Stop and target distance bounds in ATR units.
        ttl_fraction: Limit lifetime as a fraction of its configured maximum.
        age_fraction: Candidate age as a fraction of its configured maximum.
        session_fraction: Time until session close as a fraction of session length.
        source_zone_width_atr: Source-zone width divided by ATR.

    Returns:
        Float32 candidate feature vector in schema order.
    """
    values = np.zeros(len(CANDIDATE_GEOMETRY_FEATURE_NAMES), dtype=np.float32)
    low, high = zone
    values[_FEATURE_INDEX["direction"]] = float(candidate.direction)
    values[_FEATURE_INDEX["entry_type_limit"]] = 1.0 if entry_type == "limit" else 0.0
    values[_FEATURE_INDEX["entry_price_offset_atr"]] = float((entry_price - reference_price) / atr)
    values[_FEATURE_INDEX["source_zone_low_offset_atr"]] = float((low - reference_price) / atr)
    values[_FEATURE_INDEX["source_zone_high_offset_atr"]] = float((high - reference_price) / atr)
    values[_FEATURE_INDEX["atr_over_reference_price"]] = float(atr / reference_price)
    values[_FEATURE_INDEX["spread_atr"]] = float(spread / atr)
    values[_FEATURE_INDEX["round_trip_cost_atr"]] = float(round_trip_cost / atr)
    values[_FEATURE_INDEX["minimum_stop_distance_atr"]] = float(distances[0])
    values[_FEATURE_INDEX["maximum_stop_distance_atr"]] = float(distances[1])
    values[_FEATURE_INDEX["minimum_target_distance_atr"]] = float(distances[2])
    values[_FEATURE_INDEX["maximum_target_distance_atr"]] = float(distances[3])
    values[_FEATURE_INDEX["limit_ttl_fraction"]] = float(ttl_fraction)
    values[_FEATURE_INDEX["candidate_age_fraction"]] = float(age_fraction)
    values[_FEATURE_INDEX["session_close_time_fraction"]] = float(session_fraction)
    values[_FEATURE_INDEX["source_zone_width_atr"]] = float(source_zone_width_atr)
    return values


def build_candidate_geometry_observation(
    env: Any, step_idx: int | None = None
) -> dict[str, np.ndarray[Any, Any]]:
    """Build the causal candidate-geometry observation for policy selection.

    Only information available by the decision boundary is used. Candidate
    outcome replay, future fills, future protective triggers, and realized
    returns are intentionally absent.

    Args:
        env: Trading environment supplying causal market and execution state.
        step_idx: Optional completed bar index; defaults to the current index.

    Returns:
        Fixed-width candidate IDs, geometry features, and boolean eligibility mask.
    """
    index = int(env.step_idx if step_idx is None else step_idx)
    count = candidate_geometry_slot_count()
    candidate_ids = np.asarray(
        [candidate_geometry_slot_semantics(slot)[0] for slot in range(count)],
        dtype=np.int64,
    )
    setup_ids = getattr(env, "_trade_setup_candidate_ids", None)
    if setup_ids is not None:
        candidate_ids[~np.isin(candidate_ids, [NO_TRADE_ID, *setup_ids])] = NO_TRADE_ID
    features = np.zeros((count, len(CANDIDATE_GEOMETRY_FEATURE_NAMES)), dtype=np.float32)
    mask = np.zeros(count, dtype=np.bool_)
    mask[NO_TRADE_ID] = True
    if not bool(getattr(env, "candidate_geometry_actions", False)):
        return {
            "candidate_ids": candidate_ids,
            "candidate_features": features,
            "candidate_mask": mask,
        }
    if not 0 <= index < int(env._n_bars):
        return {
            "candidate_ids": candidate_ids,
            "candidate_features": features,
            "candidate_mask": mask,
        }

    setup_mask = env._trade_setup_mask_for_step(index)
    row = env._feature_row_at(index)
    quote = _reference_quote(env, index)
    if quote is None:
        return {
            "candidate_ids": candidate_ids,
            "candidate_features": features,
            "candidate_mask": mask,
        }
    bid, ask = quote
    reference_price = float(env._bar_at(index).close)
    atr = _finite(row.get("atr_5", row.get("atr", np.nan)))
    if atr is None or atr <= 0.0 or reference_price <= 0.0:
        return {
            "candidate_ids": candidate_ids,
            "candidate_features": features,
            "candidate_mask": mask,
        }

    spread = ask - bid
    slippage = _finite(getattr(env, "tick_fill_slippage_points", 0.0))
    commission = _finite(getattr(env.cost_model, "commission_per_lot", 0.0))
    contract_size = _finite(getattr(env, "contract_size", None))
    point_value = _finite(getattr(env.cost_model, "point_value", 1.0))
    if (
        spread < 0.0
        or slippage is None
        or slippage < 0.0
        or commission is None
        or commission < 0.0
        or contract_size is None
        or contract_size <= 0.0
        or point_value is None
        or point_value <= 0.0
    ):
        return {
            "candidate_ids": candidate_ids,
            "candidate_features": features,
            "candidate_mask": mask,
        }
    round_trip_cost = spread + 2.0 * slippage + 2.0 * commission / (contract_size * point_value)
    session_clock = _session_remaining(env, index)
    if session_clock is None:
        return {
            "candidate_ids": candidate_ids,
            "candidate_features": features,
            "candidate_mask": mask,
        }
    remaining_bars, session_fraction = session_clock
    max_ttl = max(1, int(env.limit_order_max_ttl_bars))
    ttl_bars = max(1, min(max_ttl, remaining_bars if remaining_bars > 0 else 1))
    ttl_fraction = float(ttl_bars / max_ttl)
    active_candidate_ids = np.flatnonzero(setup_mask[1:] > 0.0) + 1
    active_directions = {
        int(TRADE_SETUP_CANDIDATES[int(candidate_id)].direction)
        for candidate_id in active_candidate_ids
    }
    contexts = {
        direction: entry_idea_context(row, direction, include_zones=True)
        for direction in active_directions
    }

    for candidate_id in active_candidate_ids:
        candidate = TRADE_SETUP_CANDIDATES[int(candidate_id)]
        zone = _source_zone(row, candidate, contexts.get(int(candidate.direction)))
        age_fraction = _candidate_age_fraction(env, row, int(candidate_id), index)
        if zone is None or age_fraction is None:
            continue
        side = "long" if int(candidate.direction) == 1 else "short"
        signal_name = f"entry_idea_{candidate.idea}_{candidate.setup_timeframe}_{side}"
        raw_quality = _finite(row.get(signal_name, np.nan))
        if raw_quality is None or raw_quality <= 0.0:
            continue
        # Candidate eligibility is binary; it is not a signal-quality score.
        # Geometry v2 uses the measured source-zone width instead.

        market_entry = ask if int(candidate.direction) == 1 else bid
        market_distances = _geometry_distances(env, row, candidate, market_entry, atr)
        if market_distances is not None:
            slot = candidate_geometry_slot(int(candidate_id), "market")
            values = _feature_vector(
                candidate=candidate,
                entry_type="market",
                entry_price=market_entry,
                reference_price=reference_price,
                zone=zone,
                atr=atr,
                spread=spread,
                round_trip_cost=round_trip_cost,
                distances=market_distances,
                ttl_fraction=0.0,
                age_fraction=age_fraction,
                session_fraction=session_fraction,
                source_zone_width_atr=(zone[1] - zone[0]) / atr,
            )
            if np.isfinite(values).all():
                features[slot] = values
                mask[slot] = True

        midpoint = 0.5 * (float(zone[0]) + float(zone[1]))
        passive_offset = int(candidate.direction) * (reference_price - midpoint) / atr
        if not (
            np.isfinite(passive_offset) and 0.0 < passive_offset <= env.limit_order_max_offset_atr
        ):
            continue
        try:
            limit_entry = limit_price_from_atr_offset(
                direction=int(candidate.direction),
                reference_price=reference_price,
                atr=atr,
                offset_atr=float(passive_offset),
                point_size=float(env.cost_model.point_size),
            )
        except ValueError:
            continue
        if int(candidate.direction) == 1 and not limit_entry < ask:
            continue
        if int(candidate.direction) == -1 and not limit_entry > bid:
            continue
        if not float(zone[0]) <= limit_entry <= float(zone[1]):
            continue
        limit_distances = _geometry_distances(env, row, candidate, limit_entry, atr)
        if limit_distances is None:
            continue
        slot = candidate_geometry_slot(int(candidate_id), "limit")
        values = _feature_vector(
            candidate=candidate,
            entry_type="limit",
            entry_price=limit_entry,
            reference_price=reference_price,
            zone=zone,
            atr=atr,
            spread=spread,
            round_trip_cost=round_trip_cost,
            distances=limit_distances,
            ttl_fraction=ttl_fraction,
            age_fraction=age_fraction,
            session_fraction=session_fraction,
            source_zone_width_atr=(zone[1] - zone[0]) / atr,
        )
        if np.isfinite(values).all():
            features[slot] = values
            mask[slot] = True

    return {
        "candidate_ids": candidate_ids,
        "candidate_features": features,
        "candidate_mask": mask,
    }


__all__ = ["build_candidate_geometry_observation"]
