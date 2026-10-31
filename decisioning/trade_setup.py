"""Canonical trade-setup categories and wire schemas for policy and environment.

New runs use ``trade_setup_*`` identifiers. Explicit legacy builders and
translators retain the historical ``thesis_*`` wire contract for existing
checkpoints and records; ``decisioning.thesis`` remains a compatibility import.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# The first three identifiers are new canonical wire versions. The legacy
# constants below remain exact for checkpoints and run records already written.
TRADE_SETUP_SCHEMA_VERSION = "trade-setup-candidate-v1"
TRADE_SETUP_OBSERVATION_VERSION = "trade-setup-observation-v1"
TRADE_SETUP_ACTION_VERSION = "trade-setup-overlay-action-v1"
LEGACY_THESIS_SCHEMA_VERSION = "thesis-candidate-v1"
LEGACY_THESIS_OBSERVATION_VERSION = "thesis-observation-v1"
LEGACY_THESIS_ACTION_VERSION = "thesis-overlay-action-v1"

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


@dataclass(frozen=True)
class TradeSetupCandidate:
    """One stable policy choice: idea, setup timeframe, direction, or no-trade."""

    candidate_id: int
    idea: str | None
    setup_timeframe: str | None
    direction: int

    @property
    def is_no_trade(self) -> bool:
        return self.candidate_id == NO_TRADE_ID


@dataclass(frozen=True)
class TradeSetupActionSchema:
    """Versioned Box action layout whose first coordinate selects a setup."""

    names: tuple[str, ...]
    has_sl_mode: bool
    has_tp_mode: bool
    has_multi_tp: bool
    has_simplex: bool
    version: str = TRADE_SETUP_ACTION_VERSION

    @property
    def width(self) -> int:
        return len(self.names)

    @property
    def indices(self) -> dict[str, int]:
        result = {name: index for index, name in enumerate(self.names)}
        if self.has_multi_tp:
            result["target"] = result["tp1_sel"]
        return result

    @property
    def key(self) -> str:
        return "trade_setup:" + "_".join(self.names)

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": "trade_setup_overlay",
            "version": self.version,
            "key": self.key,
            "width": self.width,
            "coordinates": list(self.names),
            "categorical_coordinates": [
                name for name in ("trade_setup", "sl_mode", "tp_mode", "exit") if name in self.names
            ],
            "has_trade_setup": True,
            "trade_setup_candidate_schema_version": TRADE_SETUP_SCHEMA_VERSION,
            "trade_setup_category_count": TRADE_SETUP_CATEGORY_COUNT,
            "has_direction": False,
            "has_sl_mode": self.has_sl_mode,
            "has_tp_mode": self.has_tp_mode,
            "has_multi_tp": self.has_multi_tp,
            "has_simplex": self.has_simplex,
        }


def build_trade_setup_action_schema(
    *,
    has_sl_mode: bool = False,
    has_tp_mode: bool = False,
    has_multi_tp: bool = False,
    has_simplex: bool = False,
) -> TradeSetupActionSchema:
    """Create the independent setup action layout without changing old schemas."""
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
    coordinates.append("exit")
    return TradeSetupActionSchema(
        names=tuple(coordinates),
        has_sl_mode=has_sl_mode,
        has_tp_mode=has_tp_mode,
        has_multi_tp=has_multi_tp,
        has_simplex=has_simplex,
    )


@dataclass(frozen=True)
class LegacyThesisActionSchema:
    """Historical action layout used to load checkpoints with thesis wire names."""

    names: tuple[str, ...]
    has_sl_mode: bool
    has_tp_mode: bool
    has_multi_tp: bool
    has_simplex: bool
    version: str = LEGACY_THESIS_ACTION_VERSION

    @property
    def width(self) -> int:
        return len(self.names)

    @property
    def indices(self) -> dict[str, int]:
        result = {name: index for index, name in enumerate(self.names)}
        if self.has_multi_tp:
            result["target"] = result["tp1_sel"]
        return result

    @property
    def key(self) -> str:
        return "thesis:" + "_".join(self.names)

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": "thesis_overlay",
            "version": self.version,
            "key": self.key,
            "width": self.width,
            "coordinates": list(self.names),
            "categorical_coordinates": [
                name for name in ("thesis", "sl_mode", "tp_mode", "exit") if name in self.names
            ],
            "has_thesis": True,
            "thesis_candidate_schema_version": LEGACY_THESIS_SCHEMA_VERSION,
            "thesis_category_count": TRADE_SETUP_CATEGORY_COUNT,
            "has_direction": False,
            "has_sl_mode": self.has_sl_mode,
            "has_tp_mode": self.has_tp_mode,
            "has_multi_tp": self.has_multi_tp,
            "has_simplex": self.has_simplex,
        }


def build_legacy_thesis_action_schema(
    *,
    has_sl_mode: bool = False,
    has_tp_mode: bool = False,
    has_multi_tp: bool = False,
    has_simplex: bool = False,
) -> LegacyThesisActionSchema:
    """Build the exact pre-migration action layout for old configs/checkpoints."""
    if has_simplex and not has_multi_tp:
        raise ValueError("simplex fractions require multi-TP targets")
    coordinates = ["thesis", "stop", "risk"]
    coordinates.extend(("tp1_sel", "tp2_sel", "tp3_sel") if has_multi_tp else ("target",))
    if has_sl_mode:
        coordinates.append("sl_mode")
    if has_tp_mode:
        coordinates.append("tp_mode")
    if has_simplex:
        coordinates.extend(("z1", "z2"))
    coordinates.append("exit")
    return LegacyThesisActionSchema(
        names=tuple(coordinates),
        has_sl_mode=has_sl_mode,
        has_tp_mode=has_tp_mode,
        has_multi_tp=has_multi_tp,
        has_simplex=has_simplex,
    )


def _catalog() -> tuple[TradeSetupCandidate, ...]:
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
    """Return a setup entry by ID, rejecting unknown IDs."""
    if isinstance(candidate_id, bool) or not isinstance(candidate_id, int):
        raise TypeError("trade setup candidate ID must be an integer")
    if not 0 <= candidate_id < TRADE_SETUP_CATEGORY_COUNT:
        raise ValueError(f"trade setup candidate ID is out of range: {candidate_id}")
    return TRADE_SETUP_CANDIDATES[candidate_id]


def trade_setup_candidate_id(idea: str, setup_timeframe: str, direction: int) -> int:
    """Resolve an exact idea/timeframe/direction tuple to its stable ID."""
    key = (str(idea), str(setup_timeframe).upper(), int(direction))
    try:
        candidate = _CANDIDATE_BY_SEMANTICS[key]
    except KeyError as exc:
        raise ValueError(f"unknown trade setup semantics: {key!r}") from exc
    return candidate.candidate_id


def trade_setup_center(candidate_id: int) -> float:
    """Encode an ID at the center of its equal-width Box interval."""
    trade_setup_candidate(candidate_id)
    return 2.0 * (candidate_id + 0.5) / TRADE_SETUP_CATEGORY_COUNT - 1.0


def trade_setup_id_from_box(value: float) -> int:
    """Decode a finite normalized Box value to its stable category."""
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError("trade setup action value must be finite")
    if not -1.0 <= numeric <= 1.0:
        raise ValueError("trade setup action value must be in [-1, 1]")
    index = int((numeric + 1.0) * 0.5 * TRADE_SETUP_CATEGORY_COUNT)
    return min(index, TRADE_SETUP_CATEGORY_COUNT - 1)


def trade_setup_observation_schema() -> dict[str, object]:
    """Describe the canonical eligibility mask recorded by new checkpoints."""
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
    """Reject checkpoints whose setup eligibility semantics differ from config."""
    if actual_schema != expected_schema:
        raise ValueError(
            "checkpoint trade setup observation schema differs from the configured trade setup mask"
        )


def legacy_thesis_observation_schema() -> dict[str, object]:
    """Return the exact observation metadata written by thesis-era checkpoints."""
    return {
        "version": LEGACY_THESIS_OBSERVATION_VERSION,
        "candidate_schema_version": LEGACY_THESIS_SCHEMA_VERSION,
        "mask_key": "thesis_mask",
        "candidate_count": TRADE_SETUP_CATEGORY_COUNT,
        "no_trade_id": NO_TRADE_ID,
        "mask_semantics": "1 means eligible; NO_TRADE is always eligible",
    }


def translate_legacy_thesis_action_schema(
    legacy_schema: dict[str, object],
) -> dict[str, object]:
    """Translate a known legacy action schema to the canonical wire schema.

    This changes only the names and version identity. Coordinate order, Box
    centers, category IDs, and all optional-layout settings remain identical.
    """
    if legacy_schema.get("kind") != "thesis_overlay":
        raise ValueError("not a legacy thesis action schema")
    if legacy_schema.get("version") != LEGACY_THESIS_ACTION_VERSION:
        raise ValueError("unsupported legacy thesis action schema version")
    coordinates = legacy_schema.get("coordinates")
    if not isinstance(coordinates, list) or not coordinates or coordinates[0] != "thesis":
        raise ValueError("legacy thesis action schema has an unknown coordinate layout")
    translated = ["trade_setup", *coordinates[1:]]
    canonical = build_trade_setup_action_schema(
        has_sl_mode=bool(legacy_schema.get("has_sl_mode", False)),
        has_tp_mode=bool(legacy_schema.get("has_tp_mode", False)),
        has_multi_tp=bool(legacy_schema.get("has_multi_tp", False)),
        has_simplex=bool(legacy_schema.get("has_simplex", False)),
    ).to_dict()
    if translated != canonical["coordinates"]:
        raise ValueError("legacy thesis action coordinates do not match the canonical layout")
    return canonical


def translate_legacy_thesis_observation_schema(
    legacy_schema: dict[str, object],
) -> dict[str, object]:
    """Translate the old mask metadata after validating its exact semantics."""
    if legacy_schema != legacy_thesis_observation_schema():
        raise ValueError("unsupported legacy thesis observation schema")
    return trade_setup_observation_schema()


# Public compatibility aliases. These names are persisted in old code and records.
THESIS_SCHEMA_VERSION = LEGACY_THESIS_SCHEMA_VERSION
THESIS_OBSERVATION_VERSION = LEGACY_THESIS_OBSERVATION_VERSION
THESIS_ACTION_VERSION = LEGACY_THESIS_ACTION_VERSION
THESIS_IDEAS = TRADE_SETUP_IDEAS
THESIS_TIMEFRAMES = TRADE_SETUP_TIMEFRAMES
THESIS_DIRECTIONS = TRADE_SETUP_DIRECTIONS
THESIS_CANDIDATES = TRADE_SETUP_CANDIDATES
THESIS_CATEGORY_COUNT = TRADE_SETUP_CATEGORY_COUNT
ThesisCandidate = TradeSetupCandidate
ThesisActionSchema = LegacyThesisActionSchema
build_thesis_action_schema = build_legacy_thesis_action_schema
thesis_candidate = trade_setup_candidate
thesis_candidate_id = trade_setup_candidate_id
thesis_center = trade_setup_center
thesis_id_from_box = trade_setup_id_from_box
thesis_observation_schema = legacy_thesis_observation_schema


def validate_thesis_observation_schema(
    actual_schema: object, expected_schema: dict[str, object] | None
) -> None:
    """Validate the old checkpoint observation metadata without translation."""
    if actual_schema != expected_schema:
        raise ValueError("checkpoint thesis observation schema differs from the configured mask")


__all__ = [
    "NO_TRADE_ID",
    "TRADE_SETUP_ACTION_VERSION",
    "TRADE_SETUP_CANDIDATES",
    "TRADE_SETUP_CATEGORY_COUNT",
    "TRADE_SETUP_DIRECTIONS",
    "TRADE_SETUP_IDEAS",
    "TRADE_SETUP_OBSERVATION_VERSION",
    "TRADE_SETUP_SCHEMA_VERSION",
    "TRADE_SETUP_TIMEFRAMES",
    "TradeSetupCandidate",
    "TradeSetupActionSchema",
    "LegacyThesisActionSchema",
    "build_trade_setup_action_schema",
    "trade_setup_candidate",
    "trade_setup_candidate_id",
    "trade_setup_center",
    "trade_setup_id_from_box",
    "trade_setup_observation_schema",
    "validate_trade_setup_observation_schema",
    "legacy_thesis_observation_schema",
    "translate_legacy_thesis_action_schema",
    "translate_legacy_thesis_observation_schema",
    "THESIS_ACTION_VERSION",
    "THESIS_CANDIDATES",
    "THESIS_CATEGORY_COUNT",
    "THESIS_DIRECTIONS",
    "THESIS_IDEAS",
    "THESIS_OBSERVATION_VERSION",
    "THESIS_SCHEMA_VERSION",
    "THESIS_TIMEFRAMES",
    "ThesisCandidate",
    "ThesisActionSchema",
    "build_legacy_thesis_action_schema",
    "build_thesis_action_schema",
    "thesis_candidate",
    "thesis_candidate_id",
    "thesis_center",
    "thesis_id_from_box",
    "thesis_observation_schema",
    "validate_thesis_observation_schema",
]
