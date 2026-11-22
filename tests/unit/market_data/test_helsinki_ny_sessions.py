"""NY session classification for Helsinki-local chart timestamps."""

from __future__ import annotations

import pandas as pd
import pytest

from market_data.transforms.sessions import add_session_labels, ny_session_mask


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
