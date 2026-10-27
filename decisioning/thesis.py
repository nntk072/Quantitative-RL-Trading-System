"""Stable primary-trade-thesis categories shared by policy and environment."""

from __future__ import annotations

import math
from dataclasses import dataclass

THESIS_SCHEMA_VERSION = "thesis-candidate-v1"
THESIS_OBSERVATION_VERSION = "thesis-observation-v1"
THESIS_ACTION_VERSION = "thesis-overlay-action-v1"

THESIS_IDEAS = (
    "po3",
    "order_block",
    "standard_deviation",
    "fvg_retest",
    "ifvg_retest",
    "ifvg_unretested",
)
THESIS_TIMEFRAMES = ("M1", "M3", "M5", "M10", "M15", "M30", "H1", "H4", "D1")
THESIS_DIRECTIONS = (1, -1)  # long, short
NO_TRADE_ID = 0


@dataclass(frozen=True)
class ThesisCandidate:
    """One stable policy category; ID zero is the explicit no-trade choice."""

    candidate_id: int
    idea: str | None
    setup_timeframe: str | None
    direction: int

    @property
    def is_no_trade(self) -> bool:
        return self.candidate_id == NO_TRADE_ID


@dataclass(frozen=True)
class ThesisActionSchema:
    """Versioned Box action layout whose first coordinate selects one thesis."""

    names: tuple[str, ...]
    has_sl_mode: bool
    has_tp_mode: bool
    has_multi_tp: bool
    has_simplex: bool
    version: str = THESIS_ACTION_VERSION

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
            "thesis_candidate_schema_version": THESIS_SCHEMA_VERSION,
            "thesis_category_count": THESIS_CATEGORY_COUNT,
            "has_direction": False,
            "has_sl_mode": self.has_sl_mode,
            "has_tp_mode": self.has_tp_mode,
            "has_multi_tp": self.has_multi_tp,
            "has_simplex": self.has_simplex,
        }


def build_thesis_action_schema(
    *,
    has_sl_mode: bool = False,
    has_tp_mode: bool = False,
    has_multi_tp: bool = False,
    has_simplex: bool = False,
) -> ThesisActionSchema:
    """Create the independent thesis action layout without changing legacy schemas."""
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
    return ThesisActionSchema(
        names=tuple(coordinates),
        has_sl_mode=has_sl_mode,
        has_tp_mode=has_tp_mode,
        has_multi_tp=has_multi_tp,
        has_simplex=has_simplex,
    )


def _catalog() -> tuple[ThesisCandidate, ...]:
    candidates = [ThesisCandidate(NO_TRADE_ID, None, None, 0)]
    for direction in THESIS_DIRECTIONS:
        for idea in THESIS_IDEAS:
            for timeframe in THESIS_TIMEFRAMES:
                candidates.append(ThesisCandidate(len(candidates), idea, timeframe, direction))
    return tuple(candidates)


THESIS_CANDIDATES = _catalog()
THESIS_CATEGORY_COUNT = len(THESIS_CANDIDATES)
_CANDIDATE_BY_SEMANTICS = {
    (item.idea, item.setup_timeframe, item.direction): item for item in THESIS_CANDIDATES
}


def thesis_candidate(candidate_id: int) -> ThesisCandidate:
    """Return the catalog entry for a category ID, rejecting unknown IDs."""
    if isinstance(candidate_id, bool) or not isinstance(candidate_id, int):
        raise TypeError("thesis candidate ID must be an integer")
    if not 0 <= candidate_id < THESIS_CATEGORY_COUNT:
        raise ValueError(f"thesis candidate ID is out of range: {candidate_id}")
    return THESIS_CANDIDATES[candidate_id]


def thesis_candidate_id(idea: str, setup_timeframe: str, direction: int) -> int:
    """Resolve an exact idea/timeframe/direction tuple to its stable ID."""
    key = (str(idea), str(setup_timeframe).upper(), int(direction))
    try:
        candidate = _CANDIDATE_BY_SEMANTICS[key]
    except KeyError as exc:
        raise ValueError(f"unknown thesis semantics: {key!r}") from exc
    return candidate.candidate_id


def thesis_center(candidate_id: int) -> float:
    """Encode an ID at the exact center of its equal-width Box interval."""
    thesis_candidate(candidate_id)
    return 2.0 * (candidate_id + 0.5) / THESIS_CATEGORY_COUNT - 1.0


def thesis_id_from_box(value: float) -> int:
    """Decode a finite normalized Box value to the nearest stable category."""
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError("thesis action value must be finite")
    if not -1.0 <= numeric <= 1.0:
        raise ValueError("thesis action value must be in [-1, 1]")
    index = int((numeric + 1.0) * 0.5 * THESIS_CATEGORY_COUNT)
    return min(index, THESIS_CATEGORY_COUNT - 1)


def thesis_observation_schema() -> dict[str, object]:
    """Describe the optional eligibility-mask branch independently of account state."""
    return {
        "version": THESIS_OBSERVATION_VERSION,
        "candidate_schema_version": THESIS_SCHEMA_VERSION,
        "mask_key": "thesis_mask",
        "candidate_count": THESIS_CATEGORY_COUNT,
        "no_trade_id": NO_TRADE_ID,
        "mask_semantics": "1 means eligible; NO_TRADE is always eligible",
    }


__all__ = [
    "NO_TRADE_ID",
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
    "build_thesis_action_schema",
    "thesis_candidate",
    "thesis_candidate_id",
    "thesis_center",
    "thesis_id_from_box",
    "thesis_observation_schema",
]
