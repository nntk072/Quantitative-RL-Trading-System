"""Eligibility of each exact trade idea, timeframe, and direction candidate."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Literal, Protocol

import numpy as np
import pandas as pd

from decisioning.trade_setup import (
    NO_TRADE_ID,
    TRADE_SETUP_CANDIDATES,
    TRADE_SETUP_CATEGORY_COUNT,
    TradeSetupCandidate,
    trade_setup_candidate_id,
)

TRADE_SETUP_EVENT_IDENTITY_VERSION = "trade-setup-event-identity-v3"
TradeSetupEventIdentityStatus = Literal[
    "identified",
    "missing_source_event_time",
    "conflicting_source_event_times",
]


@dataclass(frozen=True, slots=True)
class TradeSetupEventIdentity:
    """Source-time identity for one active catalog candidate on one decision row.

    Attributes:
        candidate_id: Stable category ID from the unchanged 109-choice catalog.
        source_event_id: Deterministic identity when all required source times resolve.
        source_event_times_ns: Ordered source-event timestamp keys normalized to integer
            nanoseconds. Float-backed feature columns can round source values at subsecond
            precision, so these keys do not promise exact nanosecond instants.
        status: Whether identity is supported by the supplied feature row.
    """

    candidate_id: int
    source_event_id: str | None
    source_event_times_ns: tuple[tuple[str, int], ...]
    status: TradeSetupEventIdentityStatus


def trade_setup_event_identity_record(
    identity: TradeSetupEventIdentity | None,
) -> dict[str, object]:
    """Serialize one resolved setup identity for a decision or order ledger."""
    if identity is None:
        return {}
    return {
        "trade_setup_event_identity_version": TRADE_SETUP_EVENT_IDENTITY_VERSION,
        "trade_setup_source_event_id": identity.source_event_id,
        "trade_setup_source_event_identity_status": identity.status,
        "trade_setup_source_event_times_ns": [
            {"field": field, "time_ns": timestamp_ns}
            for field, timestamp_ns in identity.source_event_times_ns
        ],
    }


def _event_time_fields(candidate: TradeSetupCandidate) -> tuple[tuple[str, int], ...]:
    """Return source timestamp columns and their unit conversion.

    Args:
        candidate: Catalog category whose active source event is being identified.

    Returns:
        Column suffix and conversion-to-nanoseconds pairs in identity order.
    """
    assert candidate.idea is not None
    assert candidate.setup_timeframe is not None
    prefix = "" if candidate.setup_timeframe == "M1" else f"{candidate.setup_timeframe}_"
    side = "bull" if candidate.direction == 1 else "bear"
    names: tuple[tuple[str, int], ...]
    if candidate.idea == "po3":
        # M1 state is sourced from the shared aligned IFVG zone features; the
        # legacy PO3 phase mode does not populate its own ``po3_ifvg_*`` zone
        # provenance fields. MTF PO3 state is built per source timeframe and
        # carries that source-specific origin in its own state output.
        origin_field = (
            f"ifvg_{side}_fvg_origin_time_ns"
            if candidate.setup_timeframe == "M1"
            else "po3_ifvg_fvg_origin_time_ns"
        )
        names = (
            ("po3_sweep_time_ns", 1),
            ("po3_reclaim_time_ns", 1),
            (f"ifvg_{side}_confirmed_at_time_ns", 1),
            (origin_field, 1),
        )
    elif candidate.idea == "order_block":
        names = (
            (f"ob_{side}_origin_time_ms", 1_000_000),
            (f"ob_{side}_retest_confirmed_at_time_ns", 1),
        )
    elif candidate.idea == "standard_deviation":
        names = (
            ("standard_deviation_leg_start_time_ns", 1),
            ("standard_deviation_leg_end_time_ns", 1),
        )
    elif candidate.idea == "fvg_retest":
        names = (
            (f"fvg_{side}_retest_confirmed_at_time_ns", 1),
            (f"fvg_{side}_retest_origin_time_ns", 1),
        )
    elif candidate.idea == "ifvg_retest":
        names = (
            (f"ifvg_{side}_confirmed_at_time_ns", 1),
            (f"ifvg_{side}_retest_confirmed_at_time_ns", 1),
            (f"ifvg_{side}_fvg_origin_time_ns", 1),
        )
    elif candidate.idea == "ifvg_unretested":
        names = (
            (f"ifvg_{side}_confirmed_at_time_ns", 1),
            (f"ifvg_{side}_fvg_origin_time_ns", 1),
        )
        prefix = ""
    else:
        raise ValueError(f"unsupported trade setup idea: {candidate.idea!r}")
    return tuple((f"{prefix}{name}", scale) for name, scale in names)


def _time_values(value: Any, scale: int) -> tuple[int, ...]:
    """Normalize finite scalar/vector timestamp values to integer nanoseconds.

    Args:
        value: Timestamp value or duplicate-column values from the feature row.
        scale: Multiplier converting the source unit to nanoseconds.

    Returns:
        Distinct finite integer nanosecond keys in source order. Float-backed epoch
        timestamps retain their existing binary precision limits.
    """
    if isinstance(value, pd.Series):
        values = value.tolist()
    elif isinstance(value, (list, tuple, np.ndarray)):
        values = list(value)
    else:
        values = [value]
    result: list[int] = []
    for item in values:
        try:
            numeric = float(item)
        except (TypeError, ValueError):
            continue
        if np.isfinite(numeric):
            timestamp_ns = int(round(numeric * scale))
            if timestamp_ns not in result:
                result.append(timestamp_ns)
    return tuple(result)


def trade_setup_candidate_event_identities(
    row: Mapping[str, Any] | pd.Series | _FeatureRowLike,
    candidate_ids: Iterable[int] | None = None,
) -> tuple[TradeSetupEventIdentity, ...]:
    """Resolve source-event identities for active candidates without inference.

    An active category receives an ID only when its family-specific source
    timestamps are present and unambiguous. Boolean edges and row timestamps
    are never used as substitutes for a missing source event key. If one
    scalar feature selects a zone from same-row collisions, the identity also
    includes that selected zone's origin; other colliding zones are not separate
    category-level identities.

    Args:
        row: Feature row containing setup eligibility and raw source metadata.
        candidate_ids: Optional candidate IDs to resolve. This avoids scanning
            all 108 catalog columns when a decision selected one known eligible
            candidate.

    Returns:
        One identity record for each active catalog category, in catalog order.
    """
    if candidate_ids is None:
        candidates = active_trade_setup_candidates(row)
    else:
        selected: list[TradeSetupCandidate] = []
        for candidate_id in dict.fromkeys(candidate_ids):
            if not 0 <= candidate_id < TRADE_SETUP_CATEGORY_COUNT:
                raise ValueError(f"trade setup candidate ID is out of range: {candidate_id}")
            if candidate_id == NO_TRADE_ID:
                continue
            candidate = TRADE_SETUP_CANDIDATES[candidate_id]
            assert candidate.idea is not None
            assert candidate.setup_timeframe is not None
            side = "long" if candidate.direction == 1 else "short"
            feature_name = f"entry_idea_{candidate.idea}_{candidate.setup_timeframe}_{side}"
            if _value_is_active(_signal_value(row, feature_name)):
                selected.append(candidate)
        candidates = tuple(selected)

    identities: list[TradeSetupEventIdentity] = []
    for candidate in candidates:
        resolved: list[tuple[str, int]] = []
        conflict = False
        missing = False
        for column, scale in _event_time_fields(candidate):
            if column not in row:
                missing = True
                continue
            values = _time_values(_signal_value(row, column), scale)
            if len(values) > 1:
                conflict = True
            elif not values:
                missing = True
            else:
                resolved.append((column, values[0]))
        if conflict:
            status: TradeSetupEventIdentityStatus = "conflicting_source_event_times"
        elif missing:
            status = "missing_source_event_time"
        else:
            status = "identified"
        source_event_id = None
        if status == "identified":
            assert candidate.idea is not None
            assert candidate.setup_timeframe is not None
            timestamp_key = ":".join(f"{name}={value}" for name, value in resolved)
            source_event_id = (
                f"{TRADE_SETUP_EVENT_IDENTITY_VERSION}:{candidate.idea}:"
                f"{candidate.setup_timeframe}:{candidate.direction}:{timestamp_key}"
            )
        identities.append(
            TradeSetupEventIdentity(
                candidate_id=candidate.candidate_id,
                source_event_id=source_event_id,
                source_event_times_ns=tuple(resolved),
                status=status,
            )
        )
    return tuple(identities)


def trade_setup_candidate_event_time_fields(candidate_id: int) -> tuple[tuple[str, int], ...]:
    """Return the source timestamp columns and nanosecond scales for a category.

    Args:
        candidate_id: Nonzero category ID from the stable trade-setup catalog.

    Returns:
        Ordered source columns paired with their conversion multiplier to nanoseconds.

    Raises:
        ValueError: If the ID is outside the catalog or identifies NO_TRADE.
    """
    if not 0 <= candidate_id < TRADE_SETUP_CATEGORY_COUNT:
        raise ValueError(f"trade setup candidate ID is out of range: {candidate_id}")
    candidate = TRADE_SETUP_CANDIDATES[candidate_id]
    if candidate.candidate_id == NO_TRADE_ID:
        raise ValueError("NO_TRADE has no source-event timestamp fields")
    return _event_time_fields(candidate)


def _value_is_active(value: Any) -> bool:
    """Treat any finite positive feature value as an active binary context.

    Args:
        value: Value to process.

    Returns:
        Whether value is active meets the requested condition.
    """
    if isinstance(value, pd.Series):
        return any(_value_is_active(item) for item in value.tolist())
    if isinstance(value, (list, tuple, np.ndarray)):
        return any(_value_is_active(item) for item in value)
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return False
    return bool(np.isfinite(numeric) and numeric > 0.0)


def _signal_value(row: Mapping[str, Any] | pd.Series | _FeatureRowLike, name: str) -> Any:
    """Process value.

    Args:
        row: Row index or record being processed.
        name: Name used to identify the requested file, artifact, or item.

    Returns:
        Result of process value.
    """
    if name not in row:
        return 0.0
    if isinstance(row, pd.Series):
        return row.loc[name]
    return row.get(name, 0.0)


class _FeatureRowLike(Protocol):
    def get(self, key: str, default: Any = ...) -> Any:
        """Read a feature value with a fallback for missing columns.

        Args:
            key: Feature name to look up.
            default: Value returned when the feature is absent.

        Returns:
            Feature value or the supplied default.
        """
        ...

    def __getitem__(self, key: str) -> Any:
        """Process _FeatureRowLike.

        Args:
            key: Text or path value identifying the key.

        Returns:
            Result of process _FeatureRowLike.
        """
        ...

    def __iter__(self) -> Any:
        """Iterate over _FeatureRowLike.

        Returns:
            Result of iterate over _FeatureRowLike.
        """
        ...

    def __contains__(self, key: object) -> bool:
        """Process _FeatureRowLike.

        Args:
            key: Key used by the operation described above.

        Returns:
            Whether contains meets the requested condition.
        """
        ...


def active_trade_setup_candidates(
    row: Mapping[str, Any] | pd.Series | _FeatureRowLike,
) -> tuple[TradeSetupCandidate, ...]:
    """Return active candidates from their exact per-timeframe feature columns.

    Args:
        row: Row index or record being processed.

    Returns:
        Values returned by ``active_trade_setup_candidates``, in the declared order.
    """
    active: list[TradeSetupCandidate] = []
    for candidate in TRADE_SETUP_CANDIDATES[1:]:
        assert candidate.idea is not None
        assert candidate.setup_timeframe is not None
        side = "long" if candidate.direction == 1 else "short"
        column = f"entry_idea_{candidate.idea}_{candidate.setup_timeframe}_{side}"
        if _value_is_active(_signal_value(row, column)):
            active.append(candidate)
    return tuple(active)


def trade_setup_candidate_feature_columns() -> tuple[tuple[int, str], ...]:
    """Map each candidate ID to the exact per-timeframe eligibility feature.

    Returns:
        Values returned by ``trade_setup_candidate_feature_columns``, in the declared order.
    """
    columns: list[tuple[int, str]] = []
    for candidate in TRADE_SETUP_CANDIDATES[1:]:
        assert candidate.idea is not None
        assert candidate.setup_timeframe is not None
        side = "long" if candidate.direction == 1 else "short"
        name = f"entry_idea_{candidate.idea}_{candidate.setup_timeframe}_{side}"
        columns.append((candidate.candidate_id, name))
    return tuple(columns)


def trade_setup_candidate_mask(
    row: Mapping[str, Any] | pd.Series | _FeatureRowLike,
) -> np.ndarray[Any, np.dtype[np.float32]]:
    """Build the stable eligibility mask, with NO_TRADE always available.

    Args:
        row: Row index or record being processed.

    Returns:
        Array returned by ``trade_setup_candidate_mask``.
    """
    mask = np.zeros(TRADE_SETUP_CATEGORY_COUNT, dtype=np.float32)
    mask[NO_TRADE_ID] = 1.0
    for candidate in active_trade_setup_candidates(row):
        assert candidate.idea is not None
        assert candidate.setup_timeframe is not None
        mask[
            trade_setup_candidate_id(candidate.idea, candidate.setup_timeframe, candidate.direction)
        ] = 1.0
    return mask


__all__ = [
    "TRADE_SETUP_EVENT_IDENTITY_VERSION",
    "TradeSetupEventIdentity",
    "TradeSetupEventIdentityStatus",
    "active_trade_setup_candidates",
    "trade_setup_candidate_event_identities",
    "trade_setup_candidate_event_time_fields",
    "trade_setup_candidate_feature_columns",
    "trade_setup_candidate_mask",
]
