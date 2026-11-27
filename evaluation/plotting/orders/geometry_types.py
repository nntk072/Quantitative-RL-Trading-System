"""Data models shared by static order-chart geometry and rendering."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class LevelSeg:
    """Horizontal segment tied to a candle when one exists."""

    label: str
    price: float
    t0: pd.Timestamp
    t1: pd.Timestamp
    color: str
    linestyle: str
    mark: pd.Timestamp | None = None


@dataclass
class ZoneBand:
    """A causal feature zone displayed over its active chart interval."""

    label: str
    low: float
    high: float
    t0: pd.Timestamp
    t1: pd.Timestamp
    color: str

    @property
    def midpoint(self) -> float:
        """Return the center price of this chart zone.

        Returns:
            Numeric result returned by ``midpoint``.
        """
        return (self.low + self.high) / 2.0


@dataclass
class OrderLevels:
    """Geometry for the position box. Far targets stay out of ``ylim``."""

    ylim: tuple[float, float]
    t_open: pd.Timestamp
    t_close: pd.Timestamp
    entry: float
    direction: int
    exit_price: float
    red: tuple[float, float] | None = None
    green: tuple[float, float] | None = None
    segs: list[LevelSeg] = field(default_factory=list)
    deviations: list[tuple[float, float]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    offset: float = 1.0
    manip_spans: list[tuple[pd.Timestamp, pd.Timestamp]] = field(default_factory=list)
    manip_ends: list[pd.Timestamp] = field(default_factory=list)
    distribution_spans: list[tuple[pd.Timestamp, pd.Timestamp]] = field(default_factory=list)
    off_chart_levels: list[tuple[str, float, str]] = field(default_factory=list)
    zones: list[ZoneBand] = field(default_factory=list)
