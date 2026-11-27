"""NY session classification for Helsinki-local chart timestamps."""

from __future__ import annotations

import pandas as pd
import pytest

from market_data.transforms.sessions import (
    add_session_labels,
    get_session,
    ny_session_mask,
    session_reference_index,
)


@pytest.mark.parametrize(
    ("date", "labels", "expected"),
    [
        (
            "2025-03-10",
            ["15:29", "15:30", "22:00", "22:01"],
            [False, True, True, False],
        ),
        (
            "2025-10-27",
            ["15:29", "15:30", "22:00", "22:01"],
            [False, True, True, False],
        ),
        (
            "2025-04-07",
            ["16:29", "16:30", "23:00", "23:01"],
            [False, True, True, False],
        ),
    ],
)
def test_ny_mask_converts_helsinki_wall_time_before_classifying(
    date: str, labels: list[str], expected: list[bool]
) -> None:
    index = pd.DatetimeIndex([f"{date} {label}" for label in labels]).tz_localize("Etc/GMT-3")

    actual = ny_session_mask(
        index,
        start="09:30",
        end="16:00",
        session_tz="America/New_York",
        source_clock_model="europe_helsinki",
    )

    assert actual.tolist() == expected


@pytest.mark.parametrize(
    ("date", "labels"),
    [
        ("2025-03-10", ["15:29", "15:30", "22:00", "22:01"]),
        ("2025-10-27", ["15:29", "15:30", "22:00", "22:01"]),
        ("2025-04-07", ["16:29", "16:30", "23:00", "23:01"]),
    ],
)
def test_session_labels_share_the_same_helsinki_to_ny_conversion(
    date: str, labels: list[str]
) -> None:
    index = pd.DatetimeIndex([f"{date} {label}" for label in labels]).tz_localize("Etc/GMT-3")
    bars = pd.DataFrame({"close": range(len(index))}, index=index)

    result = add_session_labels(
        bars,
        tz="America/New_York",
        ny_end="16:00",
        source_clock_model="europe_helsinki",
    )

    assert result["session"].tolist() == ["london", "ny", "ny", "closed"]


def test_session_reference_rejects_unregistered_clock_and_ambiguous_wall_time() -> None:
    with pytest.raises(ValueError, match="unsupported source clock model"):
        session_reference_index(pd.DatetimeIndex(["2025-01-01"]), "unregistered")

    ambiguous = pd.DatetimeIndex(["2025-10-26 03:30"]).tz_localize("Etc/GMT-3")
    with pytest.raises(Exception, match="Cannot infer|ambiguous"):
        session_reference_index(ambiguous, "europe_helsinki")


def test_session_helpers_cover_overnight_windows_and_exchange_defaults() -> None:
    index = pd.DatetimeIndex(
        ["2025-01-06 23:00", "2025-01-07 01:00", "2025-01-07 02:01"]
    ).tz_localize("Etc/GMT-3")

    assert ny_session_mask(index, start="22:00", end="02:00").tolist() == [True, True, False]
    assert get_session("2025-01-06 18:00", tz="America/Chicago") == "asia"
    assert get_session("2025-01-06 09:00", tz="America/New_York") == "london"


def test_non_native_session_mask_requires_aware_index() -> None:
    with pytest.raises(ValueError, match="requires a timezone-aware index"):
        ny_session_mask(
            pd.DatetimeIndex(["2025-01-06 10:00"]),
            session_tz="America/New_York",
            source_clock_model="ftmo_mt5_us_dst",
        )


def test_native_naive_session_labels_localize_in_configured_timezone() -> None:
    index = pd.DatetimeIndex(["2025-01-06 09:00", "2025-01-06 16:30"])
    bars = pd.DataFrame({"close": [1.0, 2.0]}, index=index)

    labeled = add_session_labels(bars, tz="Etc/GMT-3", source_clock_model="native")

    assert labeled.index.equals(index)
    assert labeled["session"].tolist() == ["london", "ny"]
