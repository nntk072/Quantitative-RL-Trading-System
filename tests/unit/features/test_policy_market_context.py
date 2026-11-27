from __future__ import annotations

from pathlib import Path
from typing import cast

import numpy as np
import pandas as pd
import pytest

from features.context.policy_market import (
    attach_policy_market_context,
    build_policy_market_context,
)
from market_data.loading.ticks import TickBook


def _book(index: pd.DatetimeIndex, seconds: list[int]) -> TickBook:
    stamps = np.asarray(
        [index[0].value + second * 1_000_000_000 for second in seconds], dtype=np.int64
    )
    return TickBook(
        stamps,
        np.asarray([100.0 + i for i in range(len(stamps))]),
        np.asarray([100.2 + i for i in range(len(stamps))]),
    )


def test_short_schedule_is_known_at_first_bar_and_quotes_stop_at_bar_close(tmp_path) -> None:
    index = pd.date_range("2025-11-28 16:30", periods=2, freq="min", tz="Etc/GMT-3")
    bars = pd.DataFrame({"close": [100.0, 101.0]}, index=index)
    features = pd.DataFrame({"atr_5": [2.0, 2.0]}, index=index)
    schedule = tmp_path / "schedule.csv"
    schedule.write_text(
        "session_date,scheduled_ny_close_broker_time,scheduled_short\n2025-11-28,20:15,true\n",
        encoding="utf-8",
    )
    book = _book(index, [5, 30, 60, 90])

    context = build_policy_market_context(
        bars,
        features,
        book,
        schedule_path=schedule,
    )

    first = context.iloc[0]
    assert first["ny_scheduled_short"] == 1.0
    assert np.isclose(first["ny_scheduled_close_fraction"], 1215 / 1440)
    assert np.isclose(first["ny_minutes_to_scheduled_close"], 1.0)
    assert first["tick_quote_available"] == 1.0
    assert first["tick_quote_activity"] == np.log1p(2)
    # The quote stamped exactly at 16:31 belongs to the next bar.
    assert np.isclose(first["tick_bid_offset_atr"], 0.5)
    assert np.isclose(first["tick_ask_offset_atr"], 0.6)


def test_configured_calendar_includes_ftmo_early_close_on_2025_01_09() -> None:
    index = pd.date_range("2025-01-09 16:29", periods=2, freq="min", tz="Etc/GMT-3")
    bars = pd.DataFrame({"close": [100.0, 101.0]}, index=index)
    features = pd.DataFrame({"atr_5": [2.0, 2.0]}, index=index)
    schedule_path = Path(__file__).resolve().parents[3] / "config/ny_session_schedule.csv"

    context = build_policy_market_context(
        bars,
        features,
        _book(index, [30, 90]),
        schedule_path=schedule_path,
    )

    first = context.iloc[0]
    assert first["ny_scheduled_short"] == 1.0
    assert np.isclose(first["ny_scheduled_close_fraction"], 990 / 1440)


def test_schedule_clock_is_converted_from_helsinki_to_chicago_with_dst(tmp_path: Path) -> None:
    index = pd.date_range("2025-03-10 16:30", periods=1, freq="min", tz="Etc/GMT-3")
    bars = pd.DataFrame({"close": [100.0]}, index=index)
    features = pd.DataFrame({"atr_5": [2.0]}, index=index)
    schedule = tmp_path / "schedule.csv"
    schedule.write_text(
        "session_date,scheduled_ny_close_broker_time,scheduled_short\n2025-03-10,22:00,true\n",
        encoding="utf-8",
    )

    context = build_policy_market_context(
        bars,
        features,
        _book(index, [5]),
        schedule_path=schedule,
        session_start="08:30",
        session_end="15:00",
        session_tz="America/Chicago",
        source_clock_model="europe_helsinki",
    )

    assert context.iloc[0]["ny_scheduled_short"] == 1.0
    assert np.isclose(context.iloc[0]["ny_scheduled_close_fraction"], 15 * 60 / 1440)
    assert np.isclose(context.iloc[0]["ny_minutes_to_scheduled_close"], 330 / 390)


def test_future_ticks_do_not_change_completed_bar_context(tmp_path) -> None:
    index = pd.date_range("2025-11-28 16:30", periods=2, freq="min", tz="Etc/GMT-3")
    bars = pd.DataFrame({"close": [100.0, 101.0]}, index=index)
    features = pd.DataFrame({"atr_5": [2.0, 2.0]}, index=index)
    schedule = tmp_path / "schedule.csv"
    schedule.write_text(
        "session_date,scheduled_ny_close_broker_time,scheduled_short\n",
        encoding="utf-8",
    )
    full = build_policy_market_context(
        bars,
        features,
        _book(index, [5, 30, 60, 90]),
        schedule_path=schedule,
    )
    prefix = build_policy_market_context(
        bars.iloc[:1],
        features.iloc[:1],
        _book(index[:1], [5, 30, 60, 90]),
        schedule_path=schedule,
    )

    pd.testing.assert_series_equal(full.iloc[0], prefix.iloc[0])


def test_attach_policy_market_context_preserves_features_and_appends_context(tmp_path) -> None:
    index = pd.date_range("2025-11-28 16:30", periods=2, freq="min", tz="Etc/GMT-3")
    bars = pd.DataFrame({"close": [100.0, 101.0]}, index=index)
    features = pd.DataFrame({"atr_5": [2.0, 2.0], "ret_1": [0.01, -0.01]}, index=index)
    schedule = tmp_path / "schedule.csv"
    schedule.write_text(
        "session_date,scheduled_ny_close_broker_time,scheduled_short\n",
        encoding="utf-8",
    )

    result = attach_policy_market_context(
        bars,
        features,
        _book(index, [5, 30, 60, 90]),
        schedule_path=schedule,
    )

    assert result.index.equals(features.index)
    pd.testing.assert_frame_equal(result.loc[:, features.columns], features)
    assert result["tick_quote_available"].eq(1.0).all()


def test_attach_policy_market_context_rejects_duplicate_context_columns(tmp_path) -> None:
    index = pd.date_range("2025-11-28 16:30", periods=1, freq="min", tz="Etc/GMT-3")
    bars = pd.DataFrame({"close": [100.0]}, index=index)
    features = pd.DataFrame({"atr_5": [2.0], "tick_quote_available": [1.0]}, index=index)
    schedule = tmp_path / "schedule.csv"
    schedule.write_text(
        "session_date,scheduled_ny_close_broker_time,scheduled_short\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="columns already exist"):
        attach_policy_market_context(
            bars,
            features,
            _book(index, [5]),
            schedule_path=schedule,
        )


@pytest.mark.parametrize(
    ("bars", "features", "book", "message"),
    [
        (pd.DataFrame(), pd.DataFrame(), None, "same nonempty index"),
        (
            pd.DataFrame({"close": [100.0]}, index=pd.date_range("2025-01-01", periods=1)),
            pd.DataFrame({"atr_5": [1.0]}, index=pd.date_range("2025-01-02", periods=1)),
            None,
            "same nonempty index",
        ),
        (
            pd.DataFrame({"close": [100.0]}, index=pd.date_range("2025-01-01", periods=1)),
            pd.DataFrame({"atr_5": [1.0]}, index=pd.date_range("2025-01-01", periods=1)),
            None,
            "configured bid/ask tick book",
        ),
    ],
)
def test_policy_market_context_rejects_unusable_bar_inputs(
    bars: pd.DataFrame,
    features: pd.DataFrame,
    book: TickBook | None,
    message: str,
    tmp_path: Path,
) -> None:
    schedule = tmp_path / "schedule.csv"
    schedule.write_text(
        "session_date,scheduled_ny_close_broker_time,scheduled_short\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=message):
        build_policy_market_context(bars, features, book, schedule_path=schedule)


def test_policy_market_context_rejects_incomplete_or_duplicate_schedules(tmp_path) -> None:
    index = pd.date_range("2025-11-28 16:30", periods=1, freq="min", tz="Etc/GMT-3")
    bars = pd.DataFrame({"close": [100.0]}, index=index)
    features = pd.DataFrame({"atr_5": [2.0]}, index=index)
    book = _book(index, [5])
    schedule = tmp_path / "schedule.csv"
    schedule.write_text("session_date,scheduled_short\n2025-11-28,true\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing columns"):
        build_policy_market_context(bars, features, book, schedule_path=schedule)
    schedule.write_text(
        "session_date,scheduled_ny_close_broker_time,scheduled_short\n"
        "2025-11-28,20:15,true\n2025-11-28,20:15,false\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate dates"):
        build_policy_market_context(bars, features, book, schedule_path=schedule)


@pytest.mark.parametrize("clock", ["25:00", "24:00", "10:60", "10:00:00"])
def test_policy_market_context_rejects_noncanonical_session_clock(tmp_path, clock: str) -> None:
    index = pd.date_range("2025-11-28 16:30", periods=1, freq="min", tz="Etc/GMT-3")
    bars = pd.DataFrame({"close": [100.0]}, index=index)
    features = pd.DataFrame({"atr_5": [2.0]}, index=index)
    schedule = tmp_path / "schedule.csv"
    schedule.write_text(
        "session_date,scheduled_ny_close_broker_time,scheduled_short\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid HH:MM time"):
        build_policy_market_context(
            bars,
            features,
            _book(index, [5]),
            schedule_path=schedule,
            session_start=clock,
        )


def test_policy_context_marks_missing_or_invalid_quotes_unavailable(tmp_path: Path) -> None:
    index = pd.date_range("2025-11-28 16:30", periods=2, freq="min", tz="Etc/GMT-3")
    bars = pd.DataFrame({"close": [100.0, 101.0]}, index=index)
    features = pd.DataFrame({"atr_5": [2.0, 2.0]}, index=index)
    schedule = tmp_path / "schedule.csv"
    schedule.write_text(
        "session_date,scheduled_ny_close_broker_time,scheduled_short\n",
        encoding="utf-8",
    )
    book = TickBook(
        np.asarray([index[0].value + 5_000_000_000, index[1].value + 5_000_000_000]),
        np.asarray([101.0, 102.0]),
        np.asarray([100.0, 102.5]),
    )

    context = build_policy_market_context(bars, features, book, schedule_path=schedule)

    assert context["tick_quote_available"].tolist() == [0.0, 1.0]
    assert np.isnan(cast(float, context.loc[index[0], "tick_spread_atr"]))
    assert context.loc[index[1], "tick_quote_activity"] == np.log1p(1)


def test_policy_context_fails_closed_on_misaligned_inputs_or_missing_schema(tmp_path: Path) -> None:
    index = pd.date_range("2025-11-28 16:30", periods=1, freq="min", tz="Etc/GMT-3")
    bars = pd.DataFrame({"close": [100.0]}, index=index)
    features = pd.DataFrame({"atr_5": [2.0]}, index=index)
    schedule = tmp_path / "schedule.csv"
    schedule.write_text(
        "session_date,scheduled_ny_close_broker_time,scheduled_short\n",
        encoding="utf-8",
    )
    book = _book(index, [5])

    with pytest.raises(ValueError, match="same nonempty index"):
        build_policy_market_context(bars, features.iloc[:0], book, schedule_path=schedule)
    with pytest.raises(ValueError, match="configured bid/ask tick book"):
        build_policy_market_context(bars, features, None, schedule_path=schedule)
    with pytest.raises(ValueError, match="duplicate dates"):
        duplicate_schedule = tmp_path / "duplicate.csv"
        duplicate_schedule.write_text(
            "session_date,scheduled_ny_close_broker_time,scheduled_short\n"
            "2025-11-28,20:00,true\n2025-11-28,21:00,false\n",
            encoding="utf-8",
        )
        build_policy_market_context(bars, features, book, schedule_path=duplicate_schedule)
