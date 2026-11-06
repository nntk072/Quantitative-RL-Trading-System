"""Diagnostic lifecycle projection for the PO3 state producer."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import numpy as np
import pandas as pd

_REQUIRED_COLUMNS = (
    "po3_setup_id",
    "po3_manipulation_direction",
    "po3_manipulation_active",
    "po3_manipulation_end",
    "po3_waiting_ifvg",
    "po3_ifvg_confirmed",
    "po3_distribution",
    "po3_distribution_after_ifvg",
    "po3_sweep_reference",
    "po3_sweep_reference_tf_code",
    "po3_sweep_pivot_time_ns",
    "po3_sweep_confirmed_at_ns",
    "po3_sweep_time_ns",
    "po3_reclaim_time_ns",
    "po3_ifvg_time_ns",
    "po3_ifvg_fvg_origin_bar",
    "po3_ifvg_fvg_origin_time_ns",
    "po3_sweep_conflict",
)


def _first_positive(values: Iterable[float]) -> int | None:
    """Return the first position containing a positive value, if present.

    Args:
        values: Ordered state values to inspect.

    Returns:
        Index of the first positive item, or ``None`` when there is none.
    """
    for position, value in enumerate(values):
        if float(value) > 0.0:
            return position
    return None


def _finite_or_none(value: Any) -> float | None:
    """Convert a value to a finite float, returning ``None`` for non-finite input.

    Args:
        value: Source value to normalize.

    Returns:
        Finite float, or ``None`` when the result is non-finite.
    """
    numeric = float(value)
    return numeric if np.isfinite(numeric) else None


def _origin_time_ns(state: pd.DataFrame, start: int, confirm_offset: int | None) -> int | None:
    """Recover the exact FVG origin timestamp from its producer bar index.

    Args:
        state: PO3 state frame containing the source-origin bar column.
        start: Start row for the setup sequence.
        confirm_offset: Offset of the confirmation row within the sequence.

    Returns:
        Origin timestamp in nanoseconds, or ``None`` when no confirmation exists.
    """
    if confirm_offset is None:
        return None
    origin = _finite_or_none(state["po3_ifvg_fvg_origin_bar"].iloc[start + confirm_offset])
    if origin is None:
        return None
    if not origin.is_integer() or not 0 <= int(origin) < len(state):
        raise ValueError("PO3 IFVG origin bar must be an in-range integer index")
    return int(state.index[int(origin)].value)


def build_po3_setup_lifecycle_ledger(state: pd.DataFrame) -> pd.DataFrame:
    """Project PO3 state rows into setup-sequence lifecycle records.

    One row represents one setup sequence accepted by
    :func:`features.po3.ifvg_state.build_po3_ifvg_state`; same-row conflicting
    sweeps are recorded separately because the producer does not start a
    setup for them. A setup ends when a later accepted sweep replaces it or at
    the input boundary. These are producer-state episodes, not a complete
    market-event ontology, policy proposals, or trades.

    Args:
        state: Output frame from ``build_po3_ifvg_state``.

    Returns:
        A chronologically ordered frame with one row per accepted setup and
        one row per rejected same-bar sweep conflict.

    Raises:
        ValueError: If the index, required state columns, or setup sequence
            identifiers cannot support an unambiguous projection.
    """
    missing = sorted(set(_REQUIRED_COLUMNS) - set(map(str, state.columns)))
    if missing:
        raise ValueError(f"PO3 state is missing required columns: {missing}")
    if not isinstance(state.index, pd.DatetimeIndex):
        raise ValueError("PO3 lifecycle ledger requires a DatetimeIndex")
    if not state.index.is_monotonic_increasing or not state.index.is_unique:
        raise ValueError("PO3 lifecycle index must be unique and chronological")

    ids = state["po3_setup_id"].to_numpy(dtype=float)
    if not np.isfinite(ids).all() or (ids < 0.0).any() or not np.equal(ids, np.floor(ids)).all():
        raise ValueError("po3_setup_id must contain finite non-negative integers")
    if (np.diff(ids) < 0.0).any():
        raise ValueError("po3_setup_id must be non-decreasing")

    starts = np.flatnonzero((ids > 0.0) & np.r_[True, ids[1:] != ids[:-1]])
    setup_ids = [int(ids[position]) for position in starts]
    if setup_ids and setup_ids != list(range(1, len(setup_ids) + 1)):
        raise ValueError("po3_setup_id must increase by one for each accepted setup")

    records: list[dict[str, Any]] = []
    for ordinal, start in enumerate(starts):
        end_exclusive = int(starts[ordinal + 1]) if ordinal + 1 < len(starts) else len(state)
        setup_id = int(ids[start])
        episode = state.iloc[int(start) : end_exclusive]
        last = end_exclusive - 1
        direction_impulse = float(state["po3_manipulation_direction"].iloc[start])
        if not np.isfinite(direction_impulse) or direction_impulse not in (-1.0, 1.0):
            raise ValueError(f"setup {setup_id} has no unambiguous PO3 direction")

        reclaim_offset = _first_positive(episode["po3_manipulation_end"].to_numpy(dtype=float))
        confirm_offset = _first_positive(episode["po3_ifvg_confirmed"].to_numpy(dtype=float))
        phase = state.iloc[last]
        if float(phase["po3_distribution_after_ifvg"]) > 0.0:
            phase_at_end = "distribution_after_ifvg"
        elif float(phase["po3_distribution"]) > 0.0:
            phase_at_end = "distribution"
        elif float(phase["po3_waiting_ifvg"]) > 0.0:
            phase_at_end = "waiting_for_ifvg"
        elif float(phase["po3_manipulation_active"]) > 0.0:
            phase_at_end = "manipulation"
        else:
            raise ValueError(f"setup {setup_id} ends in an unclassified PO3 state")

        next_start = int(starts[ordinal + 1]) if ordinal + 1 < len(starts) else None
        record: dict[str, Any] = {
            "event_kind": "po3_setup_sequence",
            "producer_setup_id": setup_id,
            "direction": int(-direction_impulse),
            "start_index": int(start),
            "start_time": state.index[start],
            "sweep_reference": _finite_or_none(state["po3_sweep_reference"].iloc[start]),
            "sweep_reference_tf_code": _finite_or_none(
                state["po3_sweep_reference_tf_code"].iloc[start]
            ),
            # These two values come from nullable float feature columns. Keep
            # their storage semantics visible: float64 cannot preserve epoch
            # nanoseconds exactly. Bar-indexed lifecycle events below are
            # reconstructed from the DatetimeIndex and remain exact.
            "sweep_pivot_time_source_float_ns": _finite_or_none(
                state["po3_sweep_pivot_time_ns"].iloc[start]
            ),
            "sweep_confirmed_at_source_float_ns": _finite_or_none(
                state["po3_sweep_confirmed_at_ns"].iloc[start]
            ),
            "sweep_time_ns": int(state.index[start].value),
            "reclaim_index": (None if reclaim_offset is None else int(start + reclaim_offset)),
            "reclaim_time_ns": (
                None if reclaim_offset is None else int(state.index[start + reclaim_offset].value)
            ),
            "ifvg_confirmation_index": (
                None if confirm_offset is None else int(start + confirm_offset)
            ),
            "ifvg_confirmation_time_ns": (
                None if confirm_offset is None else int(state.index[start + confirm_offset].value)
            ),
            "ifvg_fvg_origin_bar": _finite_or_none(
                state["po3_ifvg_fvg_origin_bar"].iloc[
                    int(start + confirm_offset) if confirm_offset is not None else start
                ]
            ),
            "ifvg_fvg_origin_time_ns": _origin_time_ns(state, start, confirm_offset),
            "last_observed_index": int(last),
            "last_observed_time": state.index[last],
            "phase_at_end": phase_at_end,
            "termination_reason": (
                "replaced_by_next_sweep" if next_start is not None else "input_end"
            ),
            "replacement_setup_id": (None if next_start is None else int(ids[next_start])),
            "replacement_time": None if next_start is None else state.index[next_start],
        }
        records.append(record)

    conflicts = np.flatnonzero(state["po3_sweep_conflict"].to_numpy(dtype=float) > 0.0)
    for position in conflicts:
        records.append(
            {
                "event_kind": "conflicting_same_bar_sweeps",
                "producer_setup_id": None,
                "direction": None,
                "start_index": int(position),
                "start_time": state.index[position],
                "sweep_reference": None,
                "sweep_reference_tf_code": None,
                "sweep_pivot_time_source_float_ns": None,
                "sweep_confirmed_at_source_float_ns": None,
                "sweep_time_ns": None,
                "reclaim_index": None,
                "reclaim_time_ns": None,
                "ifvg_confirmation_index": None,
                "ifvg_confirmation_time_ns": None,
                "ifvg_fvg_origin_bar": None,
                "ifvg_fvg_origin_time_ns": None,
                "last_observed_index": int(position),
                "last_observed_time": state.index[position],
                "phase_at_end": "conflict_rejected",
                "termination_reason": "same_bar_direction_conflict",
                "replacement_setup_id": None,
                "replacement_time": None,
            }
        )

    columns = [
        "event_kind",
        "producer_setup_id",
        "direction",
        "start_index",
        "start_time",
        "sweep_reference",
        "sweep_reference_tf_code",
        "sweep_pivot_time_source_float_ns",
        "sweep_confirmed_at_source_float_ns",
        "sweep_time_ns",
        "reclaim_index",
        "reclaim_time_ns",
        "ifvg_confirmation_index",
        "ifvg_confirmation_time_ns",
        "ifvg_fvg_origin_bar",
        "ifvg_fvg_origin_time_ns",
        "last_observed_index",
        "last_observed_time",
        "phase_at_end",
        "termination_reason",
        "replacement_setup_id",
        "replacement_time",
    ]
    return pd.DataFrame(records, columns=columns).sort_values(
        ["start_index", "event_kind"], kind="stable", ignore_index=True
    )
