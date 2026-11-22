"""Helsinki source wall labels must resolve to their real UTC instants."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pandas as pd
import pytest

from simulation.environment.market_access import MarketAccessMixin


@pytest.mark.parametrize(
    ("label", "expected_utc"),
    [
        ("2024-12-30 16:45", "2024-12-30 14:45:00+00:00"),
        ("2025-07-30 16:45", "2025-07-30 13:45:00+00:00"),
    ],
    ids=("helsinki-winter-plus-two", "helsinki-summer-plus-three"),
)
def test_frames_bar_time_localizes_helsinki_wall_label(
    label: str,
    expected_utc: str,
) -> None:
    source_index = pd.DatetimeIndex([pd.Timestamp(label, tz="Etc/GMT-3")])
    env = SimpleNamespace(
        _bar_times=source_index.to_numpy(),
        _bundle_arrays=None,
        _source_clock_model="europe_helsinki",
    )

    actual = MarketAccessMixin._bar_time(cast(MarketAccessMixin, env), 0)

    assert actual.tz_convert("UTC") == pd.Timestamp(expected_utc)


@pytest.mark.parametrize(
    ("label", "expected_utc"),
    [
        ("2024-12-30 16:45", "2024-12-30 14:45:00+00:00"),
        ("2025-07-30 16:45", "2025-07-30 13:45:00+00:00"),
    ],
    ids=("helsinki-winter-plus-two", "helsinki-summer-plus-three"),
)
def test_bundle_bar_time_remains_utc_epoch_for_helsinki_source(
    label: str,
    expected_utc: str,
) -> None:
    source_index = pd.DatetimeIndex([pd.Timestamp(expected_utc)])
    env = SimpleNamespace(
        _bar_times=source_index.to_numpy(dtype="datetime64[ns]"),
        _bundle_arrays={},
        _source_clock_model="europe_helsinki",
    )

    actual = MarketAccessMixin._bar_time(cast(MarketAccessMixin, env), 0)

    assert actual.tz_convert("UTC") == pd.Timestamp(expected_utc)


def test_frames_utc_instant_is_not_reinterpreted_by_helsinki_model() -> None:
    instant = pd.Timestamp("2025-12-02 14:45", tz="UTC")
    env = SimpleNamespace(
        _bar_times=pd.DatetimeIndex([instant]).to_numpy(),
        _bundle_arrays=None,
        _source_clock_model="europe_helsinki",
    )

    actual = MarketAccessMixin._bar_time(cast(MarketAccessMixin, env), 0)

    assert actual.tz_convert("UTC") == instant
