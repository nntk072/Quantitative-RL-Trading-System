from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from market_data.transforms.align import align_timeframes, join_symbols, timeframe_close_times


@given(
    minutes_per_bar=st.sampled_from((3, 5, 10)),
    source_count=st.integers(min_value=2, max_value=20),
)
@settings(max_examples=60, derandomize=True, database=None)
def test_higher_timeframe_value_appears_only_at_its_close(
    minutes_per_bar: int, source_count: int
) -> None:
    start = pd.Timestamp("2025-01-06 00:00", tz="UTC")
    minute_count = minutes_per_bar * source_count
    m1_index = pd.date_range(start, periods=minute_count + 1, freq="min")
    source_index = pd.date_range(
        start,
        periods=source_count + 1,
        freq=pd.Timedelta(minutes=minutes_per_bar),
    )
    m1 = pd.DataFrame({"minute": np.arange(len(m1_index))}, index=m1_index)
    higher = pd.DataFrame({"signal": np.arange(source_count + 1, dtype=float)}, index=source_index)
    aligned = align_timeframes(m1, {f"M{minutes_per_bar}": higher})

    for minute, timestamp in enumerate(m1_index):
        completed_count = min(minute // minutes_per_bar, source_count)
        observed = aligned.loc[timestamp, f"M{minutes_per_bar}_signal"]
        if completed_count == 0:
            assert pd.isna(observed)
        else:
            assert observed == completed_count - 1


def test_secondary_symbol_join_never_uses_a_future_bar() -> None:
    index = pd.DatetimeIndex(
        [
            pd.Timestamp("2025-01-06 09:00", tz="UTC"),
            pd.Timestamp("2025-01-06 09:01", tz="UTC"),
            pd.Timestamp("2025-01-06 09:02", tz="UTC"),
        ],
        name="datetime",
    )
    primary = pd.DataFrame({"close": [10.0, 11.0, 12.0]}, index=index)
    secondary_index = pd.DatetimeIndex(
        [
            pd.Timestamp("2025-01-06 09:01", tz="UTC"),
            pd.Timestamp("2025-01-06 09:03", tz="UTC"),
        ],
        name="datetime",
    )
    secondary = pd.DataFrame({"close": [100.0, 200.0]}, index=secondary_index)

    joined = join_symbols(primary, secondary)

    assert pd.isna(joined.iloc[0]["sec_close"])
    assert joined["sec_close"].iloc[1:].tolist() == [100.0, 100.0]


def test_empty_higher_timeframe_does_not_add_empty_columns() -> None:
    index = pd.date_range("2025-01-06 00:00", periods=2, freq="min", tz="UTC")
    m1 = pd.DataFrame({"close": [10.0, 11.0]}, index=index)
    empty = pd.DataFrame({"signal": pd.Series(dtype=float)})

    aligned = align_timeframes(m1, {"M5": empty})

    pd.testing.assert_frame_equal(aligned, m1)


def test_timeframe_close_times_clip_a_short_session_final_bar() -> None:
    index = pd.DatetimeIndex([pd.Timestamp("2025-01-06 16:58", tz="UTC")])
    bars = pd.DataFrame({"close": [100.0]}, index=index)

    closes = timeframe_close_times(
        bars,
        "M5",
        scheduled_closes={"2025-01-06": "17:00"},
    )

    assert closes.iloc[0] == pd.Timestamp("2025-01-06 17:00", tz="UTC")


def test_timeframe_close_times_reject_unsupported_timeframes() -> None:
    bars = pd.DataFrame(index=pd.DatetimeIndex([], tz="UTC"))

    with pytest.raises(ValueError, match="unsupported timeframe"):
        timeframe_close_times(bars, "M2")
