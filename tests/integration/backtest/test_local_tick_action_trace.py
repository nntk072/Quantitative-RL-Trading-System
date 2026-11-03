"""Local source-quote matching and shared simulator trace fixtures."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from scripts.research.analysis.evaluation.compare_simulator_local_tick_trace import (
    _select_event_pair,
    _select_event_pairs,
    _trade_event,
    replay_local_tick_trace,
)

from market_data.loading.ticks import TickBook


def _source_event(
    *,
    event_id: str,
    event_type: str,
    direction: int,
    order_time: pd.Timestamp,
    fill_time: pd.Timestamp,
    bid: float,
    ask: float,
) -> dict[str, object]:
    return {
        "event_id": event_id,
        "event_type": event_type,
        "direction": direction,
        "required_quote_side": "ask" if direction == 1 else "bid",
        "order_submission_time_utc": order_time.tz_convert("UTC").isoformat(),
        "event_time_utc": fill_time.tz_convert("UTC").isoformat(),
        "timestamp_group": {
            "raw_rows_at_timestamp": 1,
            "first_valid_quote_exists": True,
            "first_valid_bid_carried": False,
            "first_valid_ask_carried": False,
            "changed_quote_within_timestamp": False,
            "source_timestamp_utc": fill_time.tz_convert("UTC").isoformat(),
            "configured_grid_first_valid_bid": bid,
            "configured_grid_first_valid_ask": ask,
            "stable_parser_first_valid_bid": bid,
            "stable_parser_first_valid_ask": ask,
        },
    }


def test_select_event_pair_requires_unique_quotes_reproduced_by_tickbook() -> None:
    index = pd.date_range("2025-01-06 16:48", periods=8, freq="1min", tz="Etc/GMT-3")
    bars = pd.DataFrame(index=index)
    entry_fill = index[2] + pd.Timedelta(milliseconds=100)
    exit_fill = index[5] + pd.Timedelta(milliseconds=100)
    tickbook = TickBook(
        np.asarray([entry_fill.tz_convert("UTC").value, exit_fill.tz_convert("UTC").value]),
        np.asarray([100.0, 101.0]),
        np.asarray([100.25, 101.25]),
    )
    alignment = {
        "price_grid_application": {"increment": 0.25},
        "events": [
            _source_event(
                event_id="entry",
                event_type="open",
                direction=1,
                order_time=index[2],
                fill_time=entry_fill,
                bid=100.0,
                ask=100.25,
            ),
            _source_event(
                event_id="exit_quote",
                event_type="open",
                direction=-1,
                order_time=index[5],
                fill_time=exit_fill,
                bid=101.0,
                ask=101.25,
            ),
        ],
    }

    entry, exit_event = _select_event_pair(
        alignment,
        bars,
        tickbook,
        timezone="Etc/GMT-3",
        max_hold_minutes=10,
    )

    assert entry["event_id"] == "entry"
    assert exit_event["event_id"] == "exit_quote"


def test_select_event_pairs_cover_each_available_month_direction_once() -> None:
    index = pd.date_range("2025-01-06 16:48", periods=12, freq="1min", tz="Etc/GMT-3")
    bars = pd.DataFrame(index=index)
    fill_indices = (2, 4, 7, 9)
    fill_times = [
        (index[position] + pd.Timedelta(milliseconds=100)).tz_convert("UTC")
        for position in fill_indices
    ]
    book = TickBook(
        np.asarray([timestamp.value for timestamp in fill_times]),
        np.asarray([100.0, 100.5, 101.0, 100.75]),
        np.asarray([100.25, 100.75, 101.25, 101.0]),
    )
    events = [
        _source_event(
            event_id="long_entry",
            event_type="open",
            direction=1,
            order_time=index[2],
            fill_time=fill_times[0],
            bid=100.0,
            ask=100.25,
        ),
        _source_event(
            event_id="long_exit",
            event_type="close",
            direction=1,
            order_time=index[4],
            fill_time=fill_times[1],
            bid=100.5,
            ask=100.75,
        ),
        _source_event(
            event_id="short_entry",
            event_type="open",
            direction=-1,
            order_time=index[7],
            fill_time=fill_times[2],
            bid=101.0,
            ask=101.25,
        ),
        _source_event(
            event_id="short_exit",
            event_type="close",
            direction=-1,
            order_time=index[9],
            fill_time=fill_times[3],
            bid=100.75,
            ask=101.0,
        ),
    ]
    events[1]["required_quote_side"] = "bid"
    events[3]["required_quote_side"] = "ask"

    pairs = _select_event_pairs(
        {"price_grid_application": {"increment": 0.25}, "events": events},
        bars,
        book,
        timezone="Etc/GMT-3",
        max_hold_minutes=60,
        max_pairs=24,
    )

    assert len(pairs) == 2
    assert [int(entry["_direction"]) for entry, _ in pairs] == [1, -1]
    selected_ids = [event["event_id"] for pair in pairs for event in pair]
    assert selected_ids == ["long_entry", "long_exit", "short_entry", "short_exit"]
    assert len(set(selected_ids)) == len(selected_ids)


@pytest.mark.parametrize("direction", [1, -1])
def test_shared_local_tick_trace_reconciles_account_and_fill_events(direction: int) -> None:
    index = pd.date_range("2025-01-06 16:48", periods=8, freq="1min", tz="Etc/GMT-3")
    prices = np.full(len(index), 100.0)
    bars = pd.DataFrame(
        {
            "open": prices,
            "high": prices + 1.0,
            "low": prices - 1.0,
            "close": prices,
            "spread": 0.0,
        },
        index=index,
    )
    entry_fill = index[2] + pd.Timedelta(milliseconds=100)
    exit_fill = index[5] + pd.Timedelta(milliseconds=100)
    book = TickBook(
        np.asarray([entry_fill.tz_convert("UTC").value, exit_fill.tz_convert("UTC").value]),
        np.asarray([100.0, 101.0]),
        np.asarray([100.25, 101.25]),
    )

    report = replay_local_tick_trace(
        tickbook=book,
        bars=bars,
        entry_order_time=index[2],
        exit_order_time=index[5],
        direction=direction,
    )

    assert report["trace_passed"] is True
    assert report["environment_entry_action"] == (1 if direction == 1 else 10)
    assert report["backtest_entry_action"] == direction
    assert report["close_pnl_match"] is True
    assert report["ending_balance_match"] is True
    assert pd.Timestamp(
        report["entry"]["environment"]["actual_tick_time"]
    ) == entry_fill.tz_convert("UTC")
    assert pd.Timestamp(report["exit"]["environment"]["actual_tick_time"]) == exit_fill.tz_convert(
        "UTC"
    )


def test_trade_event_serialization_uses_json_null_for_missing_numbers() -> None:
    event = _trade_event({"type": "open", "price": 100.0, "pnl": float("nan")})

    assert event["price"] == 100.0
    assert event["pnl"] is None
