"""Canonical trade-setup categories and wire schemas for policy and environment."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

TRADE_SETUP_SCHEMA_VERSION = "trade-setup-candidate-v1"
TRADE_SETUP_OBSERVATION_VERSION = "trade-setup-observation-v1"
TRADE_SETUP_ACTION_VERSION = "trade-setup-overlay-action-v1"
TRADE_SETUP_EXECUTION_ACTION_VERSION = "trade-setup-entry-execution-action-v2"
CANDIDATE_GEOMETRY_OBSERVATION_VERSION = "candidate-geometry-observation-v2"
CANDIDATE_GEOMETRY_FEATURE_VERSION = "candidate-geometry-features-v2"
CANDIDATE_GEOMETRY_ENTRY_TYPES = ("market", "limit")
CANDIDATE_GEOMETRY_FEATURE_NAMES = (
    "direction",
    "entry_type_limit",
    "entry_price_offset_atr",
    "source_zone_low_offset_atr",
    "source_zone_high_offset_atr",
    "atr_over_reference_price",
    "spread_atr",
    "round_trip_cost_atr",
    "minimum_stop_distance_atr",
    "maximum_stop_distance_atr",
    "minimum_target_distance_atr",
    "maximum_target_distance_atr",
    "limit_ttl_fraction",
    "candidate_age_fraction",
    "session_close_time_fraction",
    "source_zone_width_atr",
)

TRADE_SETUP_IDEAS = (
    "po3",
    "order_block",
    "standard_deviation",
    "fvg_retest",
    "ifvg_retest",
    "ifvg_unretested",
)
TRADE_SETUP_TIMEFRAMES = ("M1", "M3", "M5", "M10", "M15", "M30", "H1", "H4", "D1")
TRADE_SETUP_DIRECTIONS = (1, -1)  # long, short
NO_TRADE_ID = 0


def candidate_geometry_slot(candidate_id: int | float, entry_type: str) -> int:
    """Return the stable candidate slot for a setup and entry type.

    Slot zero is always no-trade. Every executable setup has distinct market
    and limit slots, allowing the policy to compare the two entry hypotheses
    jointly while retaining the existing ``trade_setup`` and
    ``entry_execution`` action coordinates.

    Args:
        candidate_id: Nonzero executable setup identifier.
        entry_type: Entry hypothesis, either ``market`` or ``limit``.

    Returns:
        Stable action slot for the setup and entry-type pair.
    """
    if (
        isinstance(candidate_id, bool)
        or int(candidate_id) != candidate_id
        or not 1 <= int(candidate_id) < TRADE_SETUP_CATEGORY_COUNT
    ):
        raise ValueError("candidate_id is outside the executable trade-setup catalog")
    if entry_type not in CANDIDATE_GEOMETRY_ENTRY_TYPES:
        raise ValueError(f"unsupported entry type: {entry_type!r}")
    entry_index = CANDIDATE_GEOMETRY_ENTRY_TYPES.index(entry_type)
    return 1 + (int(candidate_id) - 1) * len(CANDIDATE_GEOMETRY_ENTRY_TYPES) + entry_index


def candidate_geometry_slot_count() -> int:
    """Return the fixed slot count including no-trade and entry hypotheses.

    Returns:
        Total action slots across no-trade and all setup-entry combinations.
    """
    executable_count = TRADE_SETUP_CATEGORY_COUNT - 1
    return 1 + executable_count * len(CANDIDATE_GEOMETRY_ENTRY_TYPES)


def candidate_geometry_slot_semantics(slot: int | float) -> tuple[int, str]:
    """Decode a nonzero candidate slot to its setup ID and entry type.

    Args:
        slot: Candidate-geometry action slot to decode.

    Returns:
        Setup identifier and entry type; slot zero maps to no-trade.
    """
    slot_count = candidate_geometry_slot_count()
    if isinstance(slot, bool) or int(slot) != slot or not 0 <= int(slot) < slot_count:
        raise ValueError("candidate slot is outside the candidate-geometry observation")
    if int(slot) == 0:
        return NO_TRADE_ID, "market"
    setup_offset, entry_index = divmod(int(slot) - 1, len(CANDIDATE_GEOMETRY_ENTRY_TYPES))
    return setup_offset + 1, CANDIDATE_GEOMETRY_ENTRY_TYPES[entry_index]


def candidate_geometry_observation_schema() -> dict[str, object]:
    """Describe the versioned fixed-width candidate geometry observations.

    Returns:
        Schema fields for candidate IDs, features, eligibility mask, and entry types.
    """
    return {
        "version": CANDIDATE_GEOMETRY_OBSERVATION_VERSION,
        "feature_version": CANDIDATE_GEOMETRY_FEATURE_VERSION,
        "candidate_schema_version": TRADE_SETUP_SCHEMA_VERSION,
        "candidate_ids_key": "candidate_ids",
        "candidate_features_key": "candidate_features",
        "candidate_mask_key": "candidate_mask",
        "candidate_count": candidate_geometry_slot_count(),
        "feature_names": list(CANDIDATE_GEOMETRY_FEATURE_NAMES),
        "entry_types": list(CANDIDATE_GEOMETRY_ENTRY_TYPES),
        "no_trade_slot": 0,
        "mask_semantics": "true means eligible; no-trade slot 0 is always eligible",
    }


def _decode_mode_coordinate(value: float, default: str, defer_threshold: float) -> tuple[str, bool]:
    """Map a unit-interval management coordinate without importing trading code.

    Args:
        value: Signed policy action coordinate in the expected unit interval.
        default: Management mode used when the coordinate defers.
        defer_threshold: Distance around the center coordinate treated as defer.

    Returns:
        Resolved management mode and whether the policy selected it explicitly.
    """
    unit = min(1.0, max(0.0, float(value)))
    if abs(unit - 0.5) < float(defer_threshold):
        return default, False
    return ("fixed", "breakeven", "trailing")[min(2, int(unit * 3))], True


@dataclass(frozen=True)
class TradeSetupCandidate:
    """One stable policy choice: idea, setup timeframe, direction, or no-trade."""

    candidate_id: int
    idea: str | None
    setup_timeframe: str | None
    direction: int

    @property
    def is_no_trade(self) -> bool:
        """Return whether this candidate represents the no-trade choice.

        Returns:
            Whether is no trade meets the requested condition.
        """
        return self.candidate_id == NO_TRADE_ID


@dataclass(frozen=True)
class TradeSetupExecutionChoice:
    """Decoded market/limit choice and its conditional limit controls."""

    order_type: str
    limit_offset_atr: float
    ttl_bars: int


@dataclass(frozen=True)
class TradeSetupGeometryChoice:
    """Decoded stop/target geometry and position-management coordinates."""

    stop_anchor_fraction: float
    target_fraction: float
    target_selections: tuple[float, float, float] | None
    simplex_logits: tuple[float, float] | None
    exit_mode: str
    sl_mode: str = "fixed"
    sl_mode_explicit: bool = False
    has_sl_mode: bool = False
    tp_mode: str = "fixed"
    tp_mode_explicit: bool = False
    has_tp_mode: bool = False


@dataclass(frozen=True)
class TradeSetupActionSchema:
    """Versioned Box action layout whose first coordinate selects a setup."""

    names: tuple[str, ...]
    has_sl_mode: bool
    has_tp_mode: bool
    has_multi_tp: bool
    has_simplex: bool
    has_entry_execution: bool = False
    version: str = TRADE_SETUP_ACTION_VERSION

    @property
    def width(self) -> int:
        """Return the number of action coordinates.

        Returns:
            Numeric result returned by ``width``.
        """
        return len(self.names)

    @property
    def indices(self) -> dict[str, int]:
        """Map each action-coordinate name to its ordered index.

        Returns:
            Mapping from ``str`` keys to ``int`` values.
        """
        result = {name: index for index, name in enumerate(self.names)}
        if self.has_multi_tp:
            result["target"] = result["tp1_sel"]
        return result

    @property
    def key(self) -> str:
        """Return the canonical key for the configured coordinate flags.

        Returns:
            Text returned by ``key``.
        """
        return "trade_setup:" + "_".join(self.names)

    def to_dict(self) -> dict[str, object]:
        """Return the versioned action contract as JSON-compatible data.

        Returns:
            Mapping from ``str`` keys to ``object`` values.
        """
        return {
            "kind": "trade_setup_overlay",
            "version": self.version,
            "key": self.key,
            "width": self.width,
            "coordinates": list(self.names),
            "categorical_coordinates": [
                name
                for name in ("trade_setup", "sl_mode", "tp_mode", "entry_execution", "exit")
                if name in self.names
            ],
            "conditional_coordinates": [
                name for name in ("limit_offset_atr", "limit_ttl_bars") if name in self.names
            ],
            "has_trade_setup": True,
            "trade_setup_candidate_schema_version": TRADE_SETUP_SCHEMA_VERSION,
            "trade_setup_category_count": TRADE_SETUP_CATEGORY_COUNT,
            "has_direction": False,
            "has_sl_mode": self.has_sl_mode,
            "has_tp_mode": self.has_tp_mode,
            "has_multi_tp": self.has_multi_tp,
            "has_simplex": self.has_simplex,
            "has_entry_execution": self.has_entry_execution,
            "entry_execution_semantics": (
                "raw value below zero selects market; zero or above selects limit"
                if self.has_entry_execution
                else None
            ),
            "limit_offset_atr_semantics": (
                "unit coordinate maps to [0, configured maximum ATR distance]"
                if self.has_entry_execution
                else None
            ),
            "limit_ttl_bars_semantics": (
                "unit coordinate maps to integer bars in [1, configured maximum]"
                if self.has_entry_execution
                else None
            ),
        }


def build_trade_setup_action_schema(
    *,
    has_sl_mode: bool = False,
    has_tp_mode: bool = False,
    has_multi_tp: bool = False,
    has_simplex: bool = False,
    has_entry_execution: bool = False,
) -> TradeSetupActionSchema:
    """Create the versioned action layout for primary trade-setup selection.

    Args:
        has_sl_mode: Whether to enable or require the has sl mode.
        has_tp_mode: Whether to enable or require the has tp mode.
        has_multi_tp: Whether to enable or require the has multi tp.
        has_simplex: Whether to enable or require the has simplex.
        has_entry_execution: Whether the policy chooses market or limit entry.

    Returns:
        Result of create the versioned action layout for primary trade-setup selection.
    """
    if has_simplex and not has_multi_tp:
        raise ValueError("simplex fractions require multi-TP targets")
    coordinates = ["trade_setup", "stop", "risk"]
    coordinates.extend(("tp1_sel", "tp2_sel", "tp3_sel") if has_multi_tp else ("target",))
    if has_sl_mode:
        coordinates.append("sl_mode")
    if has_tp_mode:
        coordinates.append("tp_mode")
    if has_simplex:
        coordinates.extend(("z1", "z2"))
    if has_entry_execution:
        coordinates.extend(("entry_execution", "limit_offset_atr", "limit_ttl_bars"))
    coordinates.append("exit")
    return TradeSetupActionSchema(
        names=tuple(coordinates),
        has_sl_mode=has_sl_mode,
        has_tp_mode=has_tp_mode,
        has_multi_tp=has_multi_tp,
        has_simplex=has_simplex,
        has_entry_execution=has_entry_execution,
        version=(
            TRADE_SETUP_EXECUTION_ACTION_VERSION
            if has_entry_execution
            else TRADE_SETUP_ACTION_VERSION
        ),
    )


def decode_trade_setup_execution_choice(
    action: Sequence[float],
    schema: TradeSetupActionSchema,
    *,
    max_limit_offset_atr: float,
    max_limit_ttl_bars: int,
) -> TradeSetupExecutionChoice:
    """Decode policy coordinates into an order type, ATR offset, and TTL.

    The offset coordinate is represented as a unit value in the policy action
    vector. Long limits are later placed below the decision reference price;
    short limits are placed above it. The order TTL is an integer number of
    M1 bars and uses the inclusive range from one to the configured maximum.

    Args:
        action: Policy action coordinates in schema order.
        schema: Action schema that defines coordinate positions and width.
        max_limit_offset_atr: Largest available limit offset in ATR units.
        max_limit_ttl_bars: Largest allowed order lifetime in M1 bars.

    Returns:
        Chosen order type, ATR offset, and integer TTL.
    """
    if not schema.has_entry_execution:
        raise ValueError("entry execution coordinates are not enabled in this schema")
    if not math.isfinite(max_limit_offset_atr) or max_limit_offset_atr <= 0.0:
        raise ValueError("max_limit_offset_atr must be finite and positive")
    if isinstance(max_limit_ttl_bars, bool) or max_limit_ttl_bars < 1:
        raise ValueError("max_limit_ttl_bars must be a positive integer")
    if int(max_limit_ttl_bars) != max_limit_ttl_bars:
        raise ValueError("max_limit_ttl_bars must be a positive integer")
    values = [float(value) for value in action]
    if len(values) != schema.width:
        raise ValueError(f"action width {len(values)} disagrees with schema width {schema.width}")
    if not all(math.isfinite(value) and -1.0 <= value <= 1.0 for value in values):
        raise ValueError("action values must be finite and in [-1, 1]")
    indices = schema.indices
    order_type = "market" if values[indices["entry_execution"]] < 0.0 else "limit"
    unit_offset = 0.5 * (values[indices["limit_offset_atr"]] + 1.0)
    unit_ttl = 0.5 * (values[indices["limit_ttl_bars"]] + 1.0)
    max_ttl = int(max_limit_ttl_bars)
    ttl_bars = 1 + min(int(unit_ttl * max_ttl), max_ttl - 1)
    return TradeSetupExecutionChoice(
        order_type=order_type,
        limit_offset_atr=unit_offset * float(max_limit_offset_atr),
        ttl_bars=ttl_bars,
    )


def decode_trade_setup_geometry_choice(
    action: Sequence[float],
    schema: TradeSetupActionSchema,
    *,
    allow_ema_exit: bool = True,
    default_sl_mode: str = "fixed",
    default_tp_mode: str = "fixed",
    sl_mode_defer_threshold: float = 0.1,
    tp_mode_defer_threshold: float = 0.1,
) -> TradeSetupGeometryChoice:
    """Decode the setup action's stop, target, and exit coordinates.

    The stop coordinate maps from ``[-1, 1]`` to the environment's ``[0, 2]``
    anchor scale. Target coordinates map to ``[0, 1]``. Multi-target and
    simplex coordinates retain their named slot order. When EMA exits are
    disabled, the exit coordinate resolves to structural exit.

    Args:
        action: Policy action coordinates in schema order.
        schema: Action schema that defines coordinate positions and features.
        allow_ema_exit: Whether the policy can select EMA-based exits.
        default_sl_mode: Stop mode used when the policy defers its choice.
        default_tp_mode: Target mode used when the policy defers its choice.
        sl_mode_defer_threshold: Center-band width that defers the stop-mode choice.
        tp_mode_defer_threshold: Center-band width that defers the target-mode choice.

    Returns:
        Decoded stop, target, exit, and management-mode settings.
    """
    values = [float(value) for value in action]
    if len(values) != schema.width:
        raise ValueError(f"action width {len(values)} disagrees with schema width {schema.width}")
    if not all(math.isfinite(value) and -1.0 <= value <= 1.0 for value in values):
        raise ValueError("action values must be finite and in [-1, 1]")
    indices = schema.indices
    stop_fraction = values[indices["stop"]] + 1.0

    def to_unit(index: int) -> float:
        """Map one signed action coordinate to the unit interval.

        Args:
            index: Coordinate index in the validated action vector.

        Returns:
            Coordinate scaled from ``[-1, 1]`` to ``[0, 1]``.
        """
        return 0.5 * (values[index] + 1.0)

    target_selections = (
        (
            to_unit(indices["tp1_sel"]),
            to_unit(indices["tp2_sel"]),
            to_unit(indices["tp3_sel"]),
        )
        if schema.has_multi_tp
        else None
    )
    target_fraction = (
        target_selections[2] if target_selections is not None else to_unit(indices["target"])
    )
    simplex_logits = (
        (to_unit(indices["z1"]), to_unit(indices["z2"])) if schema.has_simplex else None
    )
    exit_mode = "ema_21" if allow_ema_exit and to_unit(indices["exit"]) >= 0.5 else "structural"
    sl_mode = default_sl_mode
    sl_mode_explicit = False
    if schema.has_sl_mode:
        sl_unit = to_unit(indices["sl_mode"])
        if abs(sl_unit - 0.5) >= float(sl_mode_defer_threshold):
            sl_mode = ("fixed", "breakeven", "trailing")[min(2, int(sl_unit * 3))]
            sl_mode_explicit = True
    tp_mode, tp_mode_explicit = (
        _decode_mode_coordinate(
            to_unit(indices["tp_mode"]), default_tp_mode, tp_mode_defer_threshold
        )
        if schema.has_tp_mode
        else (default_tp_mode, False)
    )
    return TradeSetupGeometryChoice(
        stop_anchor_fraction=float(stop_fraction),
        target_fraction=float(target_fraction),
        target_selections=target_selections,
        simplex_logits=simplex_logits,
        exit_mode=exit_mode,
        sl_mode=sl_mode,
        sl_mode_explicit=sl_mode_explicit,
        has_sl_mode=schema.has_sl_mode,
        tp_mode=tp_mode,
        tp_mode_explicit=tp_mode_explicit,
        has_tp_mode=schema.has_tp_mode,
    )


def _catalog() -> tuple[TradeSetupCandidate, ...]:
    """Process the requested value.

    Returns:
        Values returned by ``_catalog``, in the declared order.
    """
    candidates = [TradeSetupCandidate(NO_TRADE_ID, None, None, 0)]
    for direction in TRADE_SETUP_DIRECTIONS:
        for idea in TRADE_SETUP_IDEAS:
            for timeframe in TRADE_SETUP_TIMEFRAMES:
                candidates.append(TradeSetupCandidate(len(candidates), idea, timeframe, direction))
    return tuple(candidates)


TRADE_SETUP_CANDIDATES = _catalog()
TRADE_SETUP_CATEGORY_COUNT = len(TRADE_SETUP_CANDIDATES)
_CANDIDATE_BY_SEMANTICS = {
    (item.idea, item.setup_timeframe, item.direction): item for item in TRADE_SETUP_CANDIDATES
}


def trade_setup_candidate(candidate_id: int) -> TradeSetupCandidate:
    """Return a setup entry by ID, rejecting unknown IDs.

    Args:
        candidate_id: Numeric value used for the candidate id.

    Returns:
        Result of return a setup entry by ID, rejecting unknown IDs.
    """
    if isinstance(candidate_id, bool) or not isinstance(candidate_id, int):
        raise TypeError("trade setup candidate ID must be an integer")
    if not 0 <= candidate_id < TRADE_SETUP_CATEGORY_COUNT:
        raise ValueError(f"trade setup candidate ID is out of range: {candidate_id}")
    return TRADE_SETUP_CANDIDATES[candidate_id]


def trade_setup_candidate_id(idea: str, setup_timeframe: str, direction: int) -> int:
    """Resolve an exact idea/timeframe/direction tuple to its stable ID.

    Args:
        idea: Text or path value identifying the idea.
        setup_timeframe: Text or path value identifying the setup timeframe.
        direction: Signed trade direction: 1 for long and -1 for short.

    Returns:
        Numeric result returned by ``trade_setup_candidate_id``.
    """
    key = (str(idea), str(setup_timeframe).upper(), int(direction))
    try:
        candidate = _CANDIDATE_BY_SEMANTICS[key]
    except KeyError as exc:
        raise ValueError(f"unknown trade setup semantics: {key!r}") from exc
    return candidate.candidate_id


def trade_setup_center(candidate_id: int) -> float:
    """Encode an ID at the center of its equal-width Box interval.

    Args:
        candidate_id: Numeric value used for the candidate id.

    Returns:
        Numeric result returned by ``trade_setup_center``.
    """
    trade_setup_candidate(candidate_id)
    return 2.0 * (candidate_id + 0.5) / TRADE_SETUP_CATEGORY_COUNT - 1.0


def trade_setup_id_from_box(value: float) -> int:
    """Decode a finite normalized Box value to its stable category.

    Args:
        value: Value to process.

    Returns:
        Numeric result returned by ``trade_setup_id_from_box``.
    """
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError("trade setup action value must be finite")
    if not -1.0 <= numeric <= 1.0:
        raise ValueError("trade setup action value must be in [-1, 1]")
    index = int((numeric + 1.0) * 0.5 * TRADE_SETUP_CATEGORY_COUNT)
    return min(index, TRADE_SETUP_CATEGORY_COUNT - 1)


def trade_setup_observation_schema() -> dict[str, object]:
    """Describe the canonical eligibility mask recorded by new checkpoints.

    Returns:
        Mapping from ``str`` keys to ``object`` values.
    """
    return {
        "version": TRADE_SETUP_OBSERVATION_VERSION,
        "candidate_schema_version": TRADE_SETUP_SCHEMA_VERSION,
        "mask_key": "trade_setup_mask",
        "candidate_count": TRADE_SETUP_CATEGORY_COUNT,
        "no_trade_id": NO_TRADE_ID,
        "mask_semantics": "1 means eligible; NO_TRADE is always eligible",
    }


def validate_trade_setup_observation_schema(
    actual_schema: object, expected_schema: dict[str, object] | None
) -> None:
    """Reject checkpoints whose setup eligibility semantics differ from config.

    Args:
        actual_schema: Actual schema used by the operation described above.
        expected_schema: Key-value data used for the expected schema.
    """
    if actual_schema != expected_schema:
        raise ValueError(
            "checkpoint trade setup observation schema differs from the configured trade setup mask"
        )


def validate_candidate_geometry_observation_schema(
    actual_schema: object, expected_schema: dict[str, object] | None
) -> None:
    """Reject checkpoints whose price-aware candidate tensor semantics differ.

    The candidate tensor is part of the policy input contract even though it is
    consumed by the hierarchical action head rather than by the market encoder.
    A checkpoint trained without this exact slot/feature layout must therefore
    never be loaded as a price-aware candidate policy.

    Args:
        actual_schema: Candidate-geometry schema recorded on the checkpoint.
        expected_schema: Candidate-geometry schema required by the configured environment.
    """
    if actual_schema != expected_schema:
        raise ValueError(
            "checkpoint candidate geometry observation schema differs from the configured "
            "candidate geometry contract"
        )


__all__ = [
    "CANDIDATE_GEOMETRY_ENTRY_TYPES",
    "CANDIDATE_GEOMETRY_FEATURE_NAMES",
    "CANDIDATE_GEOMETRY_FEATURE_VERSION",
    "CANDIDATE_GEOMETRY_OBSERVATION_VERSION",
    "NO_TRADE_ID",
    "TRADE_SETUP_ACTION_VERSION",
    "TRADE_SETUP_EXECUTION_ACTION_VERSION",
    "TRADE_SETUP_CANDIDATES",
    "TRADE_SETUP_CATEGORY_COUNT",
    "TRADE_SETUP_DIRECTIONS",
    "TRADE_SETUP_IDEAS",
    "TRADE_SETUP_OBSERVATION_VERSION",
    "TRADE_SETUP_SCHEMA_VERSION",
    "TRADE_SETUP_TIMEFRAMES",
    "TradeSetupCandidate",
    "TradeSetupActionSchema",
    "TradeSetupExecutionChoice",
    "candidate_geometry_observation_schema",
    "candidate_geometry_slot",
    "candidate_geometry_slot_count",
    "candidate_geometry_slot_semantics",
    "build_trade_setup_action_schema",
    "decode_trade_setup_execution_choice",
    "trade_setup_candidate",
    "trade_setup_candidate_id",
    "trade_setup_center",
    "trade_setup_id_from_box",
    "trade_setup_observation_schema",
    "validate_candidate_geometry_observation_schema",
    "validate_trade_setup_observation_schema",
]
