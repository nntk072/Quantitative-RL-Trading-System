"""Previous-day high/low levels: populated on tz-aware indexes and causal on the calendar day.

Regression for the detect_session_levels defect: date-keyed daily extremes were reindexed against
a DatetimeIndex, which never matches for tz-aware indexes, so prev_day_high/low were always null.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import pytest

from features.technical.structure import detect_session_levels

TIMEZONES = ("UTC", "Etc/GMT-3", None)


def _bars(tz: str | None, days: int = 3, seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    index = pd.date_range("2025-01-06 00:00", periods=days * 1440, freq="min", tz=tz)
    close = 100 + np.cumsum(rng.normal(0.0, 0.1, len(index)))
    return pd.DataFrame(
        {
            "open": close,
            "high": close + np.abs(rng.normal(0.0, 1.0, len(index))),
            "low": close - np.abs(rng.normal(0.0, 1.0, len(index))),
            "close": close,
            "volume": 1.0,
        },
        index=index,
    )


def _expected(bars: pd.DataFrame) -> tuple[Any, Any]:
    dates = np.asarray(pd.DatetimeIndex(bars.index).date)
    days: list[Any] = sorted(set(dates))
    high: Any = pd.Series(bars["high"].to_numpy()).groupby(dates).max()
    low: Any = pd.Series(bars["low"].to_numpy()).groupby(dates).min()
    previous = {day: days[i - 1] for i, day in enumerate(days) if i > 0}
    exp_high = np.array([high[previous[d]] if d in previous else np.nan for d in dates])
    exp_low = np.array([low[previous[d]] if d in previous else np.nan for d in dates])
    return exp_high, exp_low


@pytest.mark.parametrize("tz", TIMEZONES)
def test_prev_day_levels_equal_the_prior_calendar_day_extremes(tz: str | None) -> None:
    bars = _bars(tz)
    levels = detect_session_levels(bars)
    exp_high, exp_low = _expected(bars)
    np.testing.assert_array_equal(levels["prev_day_high"].to_numpy(), exp_high)
    np.testing.assert_array_equal(levels["prev_day_low"].to_numpy(), exp_low)
    assert levels["prev_day_high"].notna().sum() == len(bars) - 1440


@pytest.mark.parametrize("tz", TIMEZONES)
def test_prev_day_levels_do_not_change_when_the_current_day_changes(tz: str | None) -> None:
    bars = _bars(tz)
    original = detect_session_levels(bars)
    day_two = bars.index[1440:2880]
    perturbed = bars.copy()
    perturbed.loc[day_two, ["high", "low"]] = perturbed.loc[day_two, ["high", "low"]] * 1.5
    changed = detect_session_levels(perturbed)
    # Day two's levels come from day one only, so changing day two leaves them identical.
    pd.testing.assert_frame_equal(
        changed.loc[day_two, ["prev_day_high", "prev_day_low"]],
        original.loc[day_two, ["prev_day_high", "prev_day_low"]],
        check_exact=True,
    )
    # Day three takes its prior-day levels from the perturbed day two.
    assert not changed.loc[bars.index[2880:], "prev_day_high"].equals(
        original.loc[bars.index[2880:], "prev_day_high"]
    )


@pytest.mark.parametrize("tz", ("UTC", None))
def test_prev_day_levels_are_prefix_and_future_append_invariant(tz: str | None) -> None:
    bars = _bars(tz)
    full = detect_session_levels(bars)
    cut = 1500
    prefix = detect_session_levels(bars.iloc[:cut])
    pd.testing.assert_frame_equal(
        prefix[["prev_day_high", "prev_day_low"]],
        full.iloc[:cut][["prev_day_high", "prev_day_low"]],
        check_exact=True,
    )
    future = bars.iloc[cut:].copy()
    future[["high", "low", "close"]] = future[["high", "low", "close"]] * 2.0
    extended = detect_session_levels(pd.concat([bars.iloc[:cut], future]))
    pd.testing.assert_frame_equal(
        extended.iloc[:cut][["prev_day_high", "prev_day_low"]],
        full.iloc[:cut][["prev_day_high", "prev_day_low"]],
        check_exact=True,
    )
