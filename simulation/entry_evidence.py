"""Shared causal interpretation of feature rows for the entry lifecycle."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from features.context.entry_ideas import entry_idea_context
from simulation.entry_state import EntryCandidate, EntryEvidence, immutable_setup_levels
from trading.strategies import BaselineStrategy


def build_entry_evidence(
    *,
    strategy: Any,
    feature_row: Any,
    bar: int,
    candidate: EntryCandidate | None,
    bars_index: pd.Index | None,
    state_machine_enabled: bool,
) -> EntryEvidence:
    """Translate shared strategy predicates into one causal evidence record.

    Args:
        strategy: Strategy whose setup and direction predicates are evaluated.
        feature_row: Current causal feature values.
        bar: Current bar position.
        candidate: Entry candidate carried by the lifecycle, if any.
        bars_index: Full bar index used to resolve event timestamps.
        state_machine_enabled: Whether state-machine context affects eligibility.

    Returns:
        Evidence flags and source identities for the current entry decision.
    """
    context_direction = int(strategy.context_direction(feature_row))
    names = tuple(str(name) for name in feature_row.index)

    def flagged(stem: str) -> bool:
        """Find a positive finite feature with the requested suffix.

        Args:
            stem: Feature suffix representing a boolean-like signal.

        Returns:
            Whether a matching feature is finite and positive.
        """
        for column in (name for name in names if name == stem or name.endswith("_" + stem)):
            try:
                value = float(feature_row.get(column, 0.0))
            except (TypeError, ValueError):
                continue
            if np.isfinite(value) and value > 0.0:
                return True
        return False

    bull_retest = flagged("ifvg_retest_bull") or flagged("fvg_retest_bull")
    bear_retest = flagged("ifvg_retest_bear") or flagged("fvg_retest_bear")
    try:
        idea_long_count = float(feature_row.get("entry_idea_long_count", 0.0) or 0.0)
        idea_short_count = float(feature_row.get("entry_idea_short_count", 0.0) or 0.0)
    except (TypeError, ValueError):
        idea_long_count = idea_short_count = 0.0
    idea_long = np.isfinite(idea_long_count) and idea_long_count > 0.0
    idea_short = np.isfinite(idea_short_count) and idea_short_count > 0.0
    sweep_low = flagged("sweep_low")
    sweep_high = flagged("sweep_high")
    setup_predicate = getattr(strategy, "entry_setup", None)
    setup_matches = (
        bool(setup_predicate(feature_row, context_direction))
        if context_direction in (-1, 1) and callable(setup_predicate)
        else context_direction in (-1, 1) and not callable(setup_predicate)
    )
    direction = context_direction
    if direction not in (-1, 1):
        if idea_long != idea_short:
            direction = 1 if idea_long else -1
        else:
            direction = (
                1
                if bull_retest and not bear_retest
                else -1
                if bear_retest and not bull_retest
                else 0
            )
    baseline_sweep_setup = (
        isinstance(strategy, BaselineStrategy)
        and state_machine_enabled
        and sweep_low != sweep_high
        and direction not in (-1, 1)
    )
    if direction not in (-1, 1) and baseline_sweep_setup:
        direction = 1 if sweep_low else -1
    if direction not in (-1, 1) and isinstance(strategy, BaselineStrategy) and candidate:
        direction = candidate.direction
    setup_matches = setup_matches or (baseline_sweep_setup and direction in (-1, 1))
    suffix = "bull" if direction == 1 else "bear"
    retest_confirmed = (direction == 1 and bull_retest) or (direction == -1 and bear_retest)
    distribution_ready = getattr(strategy, "distribution_ready", None)
    distribution_arm = (
        bool(distribution_ready(feature_row, direction))
        if direction in (-1, 1) and callable(distribution_ready)
        else False
    )

    setup_types: set[str] = set()
    active_idea_names: list[str] = []
    if direction in (-1, 1):
        sweep_stem = "sweep_low" if direction == 1 else "sweep_high"
        swing_stem = "swing_low_event" if direction == 1 else "swing_high_event"
        if flagged(sweep_stem):
            setup_types.add("sweep")
        if flagged(swing_stem):
            setup_types.add("swing")
        active_idea_names = entry_idea_context(feature_row, direction)["ideas"]
        setup_types.update(active_idea_names)
        if flagged(f"fvg_retest_{suffix}"):
            setup_types.add("fvg_reaction")
        if flagged(f"ifvg_retest_{suffix}") or flagged(f"ifvg_{suffix}_confirmed"):
            setup_types.add("ifvg_reaction")
        if not isinstance(strategy, BaselineStrategy) and any(
            flagged(stem) for stem in (f"ifvg_{suffix}_active", f"ifvg_retest_{suffix}")
        ):
            setup_types.add("ifvg")
    if distribution_arm:
        setup_types.add("distribution")
    setup_matches = setup_matches or bool(active_idea_names)
    if setup_matches and not setup_types:
        setup_types.add(str(getattr(strategy, "name", "strategy")))

    snapshot: dict[str, float] = {}
    if direction in (-1, 1):
        if flagged(sweep_stem):
            for suffix_name in ("level", "wick", "ref_tf_code"):
                column = f"{sweep_stem}_{suffix_name}"
                try:
                    value = float(feature_row.get(column, np.nan))
                except (TypeError, ValueError):
                    continue
                if np.isfinite(value):
                    snapshot[column] = value
            pivot_value = feature_row.get(f"{sweep_stem}_pivot_time_ns", np.nan)
            try:
                pivot_ns = int(float(pivot_value))
            except (TypeError, ValueError, OverflowError):
                pivot_ns = 0
            pivot_time: pd.Timestamp | None = (
                pd.Timestamp(pivot_ns, unit="ns", tz="UTC") if pivot_ns > 0 else None
            )
            if pivot_time is None:
                pivot_value = feature_row.get(
                    f"last_swing_{'low' if direction == 1 else 'high'}_time"
                )
                if pivot_value is not None and not pd.isna(pivot_value):
                    try:
                        pivot_time = pd.Timestamp(pivot_value)
                    except (TypeError, ValueError):
                        pivot_time = None
            if pivot_time is not None and bars_index is not None:
                index = pd.DatetimeIndex(bars_index)
                if index.tz is None and pivot_time.tzinfo is not None:
                    pivot_time = pivot_time.tz_localize(None)
                elif index.tz is not None and pivot_time.tzinfo is None:
                    pivot_time = pivot_time.tz_localize(index.tz)
                elif index.tz is not None:
                    pivot_time = pivot_time.tz_convert(index.tz)
                pivot_bar = int(
                    index.get_indexer(pd.DatetimeIndex([pivot_time]), method="nearest")[0]
                )
                if pivot_bar >= 0:
                    snapshot[f"{sweep_stem}_pivot_bar"] = float(pivot_bar)
        for geometry_stem in (
            f"ifvg_{suffix}_low",
            f"ifvg_{suffix}_high",
            f"fvg_{suffix}_low",
            f"fvg_{suffix}_high",
        ):
            for column in names:
                if column != geometry_stem and not column.endswith("_" + geometry_stem):
                    continue
                try:
                    value = float(feature_row.get(column, np.nan))
                except (TypeError, ValueError):
                    continue
                if np.isfinite(value):
                    snapshot[column] = value

    return EntryEvidence(
        bar=bar,
        evidence_detected=setup_matches,
        invalidated=(
            (sweep_low and sweep_high)
            or (flagged("swing_low_event") and flagged("swing_high_event"))
            or (bull_retest and bear_retest)
            or (idea_long and idea_short)
        ),
        arm_condition=(
            setup_matches
            or retest_confirmed
            or distribution_arm
            or (candidate is not None and direction == candidate.direction)
        ),
        retest_confirmed=retest_confirmed,
        direction=direction,
        setup_types=tuple(sorted(setup_types)),
        setup_levels_snapshot=immutable_setup_levels(snapshot),
    )


__all__ = ["build_entry_evidence"]
