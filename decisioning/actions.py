"""Versioned, flag-derived coordinate contract for strategy-overlay actions.

An action width is not an action schema: several different flag combinations
produce the same number of coordinates. Use names when decoding, logging or
constructing policy priors. Existing coordinate ordering is intentionally kept.
"""

from __future__ import annotations

from dataclasses import dataclass

SCHEMA_VERSION = "overlay-action-v2"
DISCRETE_TRADING_SCHEMA_VERSION = "discrete-trading-v1"


@dataclass(frozen=True)
class DiscreteActionSchema:
    """Named categorical actions for the legacy 20-action trading interface."""

    names: tuple[str, ...]
    version: str = DISCRETE_TRADING_SCHEMA_VERSION

    @property
    def width(self) -> int:
        """Number of categorical choices in the discrete action space.

        Returns:
            Numeric result returned by ``width``.
        """
        return len(self.names)

    @property
    def key(self) -> str:
        """Return the stable key for this categorical action menu.

        Returns:
            Text returned by ``key``.
        """
        return f"discrete-{self.width}"

    def to_dict(self) -> dict[str, object]:
        """Return the complete ordered category contract.

        Returns:
            Mapping from ``str`` keys to ``object`` values.
        """
        return {
            "kind": "discrete",
            "version": self.version,
            "key": self.key,
            "width": self.width,
            "n_actions": self.width,
            "coordinates": list(self.names),
            "has_direction": False,
            "has_sl_mode": False,
            "has_tp_mode": False,
            "has_multi_tp": False,
            "has_simplex": False,
        }


def build_discrete_trading_action_schema(n_actions: int = 20) -> DiscreteActionSchema:
    """Describe the exact categorical menu used by ``TradingEnv`` Discrete(20).

    Args:
        n_actions: Numeric value used for the n actions.

    Returns:
        Result of describe the exact categorical menu used by ``TradingEnv`` Discrete(20).
    """
    if n_actions != 20:
        raise ValueError(
            f"the discrete trading action contract requires 20 choices, got {n_actions}"
        )
    risk_levels = ("low", "mid", "high")
    rr_levels = ("low", "mid", "high")
    names = ["hold"]
    names.extend(
        f"enter_{direction}_risk_{risk}_rr_{rr}"
        for direction in ("long", "short")
        for risk in risk_levels
        for rr in rr_levels
    )
    names.append("exit")
    return DiscreteActionSchema(tuple(names))


@dataclass(frozen=True)
class ActionSchema:
    """Ordered continuous and categorical action-coordinate contract.

    Attributes:
        names: Coordinates in policy-vector order.
        has_direction: Whether direction is an explicit coordinate.
        has_sl_mode: Whether stop-loss mode is represented.
        has_tp_mode: Whether take-profit mode is represented.
        has_multi_tp: Whether multiple target choices are represented.
        has_simplex: Whether target weights use simplex coordinates.
        version: Version identifier for this schema.
    """

    names: tuple[str, ...]
    has_direction: bool
    has_sl_mode: bool
    has_tp_mode: bool
    has_multi_tp: bool
    has_simplex: bool
    version: str = SCHEMA_VERSION

    @property
    def width(self) -> int:
        """Return the number of action coordinates.

        Returns:
            Numeric result returned by ``width``.
        """
        return len(self.names)

    @property
    def indices(self) -> dict[str, int]:
        """Map every coordinate name to its position in the action vector.

        Returns:
            Mapping from ``str`` keys to ``int`` values.
        """
        result = {name: idx for idx, name in enumerate(self.names)}
        if self.has_multi_tp:
            result["target"] = result["tp1_sel"]
        return result

    @property
    def key(self) -> str:
        """Return the canonical key describing the enabled coordinate flags.

        Returns:
            Text returned by ``key``.
        """
        canonical: dict[tuple[bool, bool, bool, bool, bool], str] = {
            (False, False, False, False, False): "5",
            (True, False, False, False, False): "6_dir",
            (False, True, False, False, False): "6_sl",
            (False, False, True, False, False): "6_tp",
            (True, True, False, False, False): "7",
            (True, False, True, False, False): "7_tp",
            (True, True, True, False, False): "8",
            (True, True, True, True, False): "10",
            (False, True, True, True, True): "11",
            (True, True, True, True, True): "12",
        }
        flags = (
            self.has_direction,
            self.has_sl_mode,
            self.has_tp_mode,
            self.has_multi_tp,
            self.has_simplex,
        )
        if flags in canonical:
            return canonical[flags]
        return "v2:" + "".join(str(int(flag)) for flag in flags)

    def to_dict(self) -> dict[str, object]:
        """Return the complete JSON-safe coordinate contract.

        Returns:
            Mapping from ``str`` keys to ``object`` values.
        """
        return {
            "version": self.version,
            "key": self.key,
            "width": self.width,
            "coordinates": list(self.names),
            "has_direction": self.has_direction,
            "has_sl_mode": self.has_sl_mode,
            "has_tp_mode": self.has_tp_mode,
            "has_multi_tp": self.has_multi_tp,
            "has_simplex": self.has_simplex,
        }


def build_action_schema(
    *,
    has_direction: bool = False,
    has_sl_mode: bool = False,
    has_tp_mode: bool = False,
    has_multi_tp: bool = False,
    has_simplex: bool = False,
) -> ActionSchema:
    """Build the ordered action schema for a selected set of strategy controls.

    Args:
        has_direction: Include an explicit long/short coordinate.
        has_sl_mode: Include stop-loss mode selection.
        has_tp_mode: Include take-profit mode selection.
        has_multi_tp: Include multiple target selection.
        has_simplex: Include simplex target-allocation coordinates.

    Returns:
        Schema with canonical coordinate order and version.
    """
    if has_simplex and not has_multi_tp:
        raise ValueError("simplex fractions require multi-TP targets")
    coordinates: list[str] = []
    if has_direction:
        coordinates.append("direction")
    coordinates.extend(("intensity", "stop", "risk"))
    coordinates.extend(("tp1_sel", "tp2_sel", "tp3_sel") if has_multi_tp else ("target",))
    if has_sl_mode:
        coordinates.append("sl_mode")
    if has_tp_mode:
        coordinates.append("tp_mode")
    if has_simplex:
        coordinates.extend(("z1", "z2"))
    coordinates.append("exit")
    return ActionSchema(
        names=tuple(coordinates),
        has_direction=has_direction,
        has_sl_mode=has_sl_mode,
        has_tp_mode=has_tp_mode,
        has_multi_tp=has_multi_tp,
        has_simplex=has_simplex,
    )
