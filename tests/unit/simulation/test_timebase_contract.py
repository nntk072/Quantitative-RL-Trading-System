"""Bar-spacing fallback for simulation clock calculations."""

from __future__ import annotations

import pandas as pd
import pytest

from simulation.environment.timebase import _minutes_per_step


@pytest.mark.parametrize(
    "index",
    [
        pd.DatetimeIndex([]),
        pd.DatetimeIndex(["2026-01-02T10:00:00Z"]),
        pd.DatetimeIndex(["2026-01-02T10:00:00Z", "2026-01-02T10:00:00Z", "2026-01-02T09:59:00Z"]),
    ],
)
def test_bar_spacing_uses_one_minute_when_no_positive_interval_exists(
    index: pd.DatetimeIndex,
) -> None:
    assert _minutes_per_step(index) == pytest.approx(1.0)


def test_bar_spacing_uses_median_positive_interval() -> None:
    index = pd.DatetimeIndex(
        [
            "2026-01-02T10:00:00Z",
            "2026-01-02T10:01:00Z",
            "2026-01-02T10:01:00Z",
            "2026-01-02T10:04:00Z",
        ]
    )

    assert _minutes_per_step(index) == pytest.approx(2.0)
