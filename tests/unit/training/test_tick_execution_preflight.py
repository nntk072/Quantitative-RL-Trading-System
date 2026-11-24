from __future__ import annotations

import pandas as pd
import pytest

from market_data.loading.ticks import TickBook, tick_execution_coverage
from training.setup.tick_execution_preflight import (
    registered_no_fill_quote_anchors,
    tick_execution_split_schedule,
    validate_registered_no_fill_anchors,
)


def test_tick_quote_anchors_keep_scheduled_minute_across_missing_bar() -> None:
    index = pd.DatetimeIndex(
        [
            pd.Timestamp("2025-12-31T14:30:00Z"),
            pd.Timestamp("2025-12-31T14:31:00Z"),
            pd.Timestamp("2025-12-31T14:32:00Z"),
            pd.Timestamp("2025-12-31T14:34:00Z"),
        ]
    )
    train_mask = pd.Series([True] * len(index), index=index)
    session_labels = pd.Series(["ny"] * len(index), index=index)

    schedule = tick_execution_split_schedule(
        index,
        train_mask,
        "2026-01-02",
        session_labels=session_labels,
        include_report_only_split=False,
    )

    assert schedule["train"]["decision_times"].equals(index)
    assert schedule["train"]["quote_anchor_times"].equals(index + pd.Timedelta(minutes=1))
    assert schedule["train"]["quote_anchor_positions"].tolist() == [1, 2, 3, 4]


def test_helsinki_quote_anchor_uses_dst_aware_instant() -> None:
    index = pd.DatetimeIndex(
        [
            pd.Timestamp("2024-12-30 16:30:00", tz="Etc/GMT-3"),
            pd.Timestamp("2024-12-30 16:31:00", tz="Etc/GMT-3"),
        ]
    )
    train_mask = pd.Series([True, True], index=index)
    session_labels = pd.Series(["ny", "ny"], index=index)

    schedule = tick_execution_split_schedule(
        index,
        train_mask,
        "2025-01-01",
        session_labels=session_labels,
        source_clock_model="europe_helsinki",
        include_report_only_split=False,
    )

    expected = pd.DatetimeIndex(
        [
            pd.Timestamp("2024-12-30 14:31:00Z"),
            pd.Timestamp("2024-12-30 14:32:00Z"),
        ]
    )
    assert schedule["train"]["quote_anchor_times"].tz_convert("UTC").equals(expected)


def test_early_close_excludes_order_anchor_at_the_scheduled_close() -> None:
    index = pd.DatetimeIndex(
        [
            pd.Timestamp("2025-01-20 19:58:00", tz="Etc/GMT-3"),
            pd.Timestamp("2025-01-20 19:59:00", tz="Etc/GMT-3"),
            pd.Timestamp("2025-01-20 20:00:00", tz="Etc/GMT-3"),
        ]
    )
    train_mask = pd.Series(True, index=index)
    session_labels = pd.Series("ny", index=index)

    schedule = tick_execution_split_schedule(
        index,
        train_mask,
        "2026-01-01",
        session_labels=session_labels,
        session_timezone="America/Chicago",
        source_clock_model="europe_helsinki",
        session_start="08:30",
        session_end="15:00",
        scheduled_session_closes={"2025-01-20": "20:00"},
        include_report_only_split=False,
    )

    assert schedule["train"]["decision_positions"].tolist() == [0]
    assert schedule["train"]["quote_anchor_times"].tz_convert("UTC").tolist() == [
        pd.Timestamp("2025-01-20T17:59:00Z")
    ]


def test_quote_coverage_reports_each_unavailable_order_time() -> None:
    orders = pd.DatetimeIndex(
        [pd.Timestamp("2025-01-20T17:59:00Z"), pd.Timestamp("2025-01-20T18:01:00Z")]
    )
    tickbook = TickBook(
        pd.DatetimeIndex([pd.Timestamp("2025-01-20T18:00:00Z")])
        .to_numpy(dtype="datetime64[ns]")
        .astype("int64"),
        pd.Series([100.0]).to_numpy(),
        pd.Series([100.2]).to_numpy(),
    )

    coverage = tick_execution_coverage(
        tickbook,
        orders,
        max_latency_ns_exclusive=0,
        max_quote_wait_ms=60_000,
    )

    assert coverage["unavailable_order_times_utc"] == ["2025-01-20T18:01:00+00:00"]


def test_registered_quote_gaps_are_accepted_only_as_explicit_no_fills() -> None:
    anchor = "2025-01-20T18:01:00+00:00"

    validate_registered_no_fill_anchors([anchor], [anchor])

    with pytest.raises(ValueError, match="unexpected=.*2025-01-20T18:02:00"):
        validate_registered_no_fill_anchors(["2025-01-20T18:02:00+00:00"], [anchor])


def test_registered_quote_gap_lookup_preserves_dotted_symbol_names() -> None:
    anchor = "2025-01-20T18:01:00+00:00"

    assert registered_no_fill_quote_anchors({"US100.cash": [anchor]}, "US100.cash") == [anchor]
