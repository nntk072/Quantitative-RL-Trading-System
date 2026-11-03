"""Fixture coverage for selected-fill to raw quote-source alignment."""

from __future__ import annotations

import pandas as pd
import pytest
from scripts.research.analysis.market_data.analyze_fill_quote_source_alignment import (
    analyze_fill_alignment,
    apply_configured_price_grid,
    correct_event_directions_from_ledgers,
)


def test_fill_alignment_reports_carried_sides_and_changed_timestamp_groups() -> None:
    events = pd.DataFrame(
        [
            {
                "type": "open",
                "position_id": "p1",
                "direction": 1,
                "actual_tick_time": "2025-01-01T00:00:01.000000Z",
                "price": 101.0,
                "fill_quote_source": "tick",
                "_event_ledger_source": "treatment/fills.csv",
            },
            {
                "type": "stop_close",
                "position_id": "p1",
                "direction": None,
                "actual_tick_time": "2025-01-01T00:00:02Z",
                "price": 100.75,
                "fill_quote_source": "tick",
                "_event_ledger_source": "treatment/fills.csv",
            },
            {
                "type": "reject",
                "position_id": "",
                "direction": -1,
                "actual_tick_time": "",
                "fill_quote_source": "",
            },
        ]
    )
    ticks = pd.DataFrame(
        [
            {
                "<DATE>": "2025.01.01",
                "<TIME>": "03:00:00.000",
                "<BID>": 100.0,
                "<ASK>": 101.12,
            },
            {"<DATE>": "2025.01.01", "<TIME>": "03:00:01.000", "<BID>": 100.5, "<ASK>": None},
            {"<DATE>": "2025.01.01", "<TIME>": "03:00:01.000", "<BID>": 100.75, "<ASK>": 101.25},
            {"<DATE>": "2025.01.01", "<TIME>": "03:00:02.000", "<BID>": None, "<ASK>": 101.3},
        ]
    )

    report = analyze_fill_alignment(
        events,
        [ticks.iloc[:2], ticks.iloc[2:]],
        source_timezone="Etc/GMT-3",
    )

    assert report["event_count"] == 2
    assert report["summary"]["entries"] == 1
    assert report["summary"]["exits"] == 1
    assert report["summary"]["matched_timestamps"] == 2
    assert report["summary"]["events_in_changed_quote_groups"] == 1
    assert report["summary"]["events_in_groups_with_missing_required_side"] == 2
    assert report["summary"]["first_parser_quote_carried_required_side"] == 2
    assert report["events"][0]["required_quote_side"] == "ask"
    assert report["events"][0]["event_ledger_source"] == "treatment/fills.csv"
    assert report["events"][0]["timestamp_group"]["raw_rows_at_timestamp"] == 2
    assert report["events"][0]["timestamp_group"]["changed_quote_within_timestamp"] is True
    assert report["events"][0]["timestamp_group"]["first_valid_ask_carried"] is True
    assert report["events"][0]["reported_fill_price"] == 101.0
    assert report["events"][0]["stable_parser_required_side_price"] == 101.12
    assert report["events"][0]["stable_parser_required_side_price_matches_fill"] is False
    assert report["events"][0]["stable_parser_required_side_carried"] is True
    assert report["events"][0]["stable_parser_required_side_age_ms_at_fill_time"] == 1000.0
    assert report["events"][0]["raw_required_side_min_at_timestamp"] == 101.25
    assert report["events"][0]["reported_fill_price_within_raw_side_range"] is False
    assert report["events"][1]["required_quote_side"] == "bid"
    assert report["events"][1]["event_ledger_source"] == "treatment/fills.csv"
    assert report["events"][1]["timestamp_group"]["first_valid_bid_carried"] is True
    assert report["events"][1]["stable_parser_required_side_price"] == 100.75
    assert report["events"][1]["stable_parser_required_side_price_matches_fill"] is True
    assert report["events"][1]["stable_parser_required_side_carried"] is True
    assert report["events"][1]["stable_parser_required_side_age_ms_at_fill_time"] == 1000.0
    assert report["events"][1]["raw_required_side_min_at_timestamp"] is None
    assert report["events"][1]["reported_fill_price_within_raw_side_range"] is None
    assert report["summary"]["reported_fill_price_matches_stable_parser_required_side"] == 1
    assert report["summary"]["reported_fill_price_differs_from_stable_parser_required_side"] == 1
    assert report["summary"]["events_with_stable_parser_carried_required_side"] == 2

    grid_report = apply_configured_price_grid(report, 0.25)
    assert grid_report["schema_version"] == 3
    assert grid_report["events"][0]["stable_parser_required_side_price"] == 101.12
    assert grid_report["events"][0]["configured_grid_required_side_price"] == 101.0
    assert (
        grid_report["events"][0]["reported_fill_price_matches_configured_grid_parser_side"] is True
    )
    assert (
        grid_report["events"][1]["reported_fill_price_matches_configured_grid_parser_side"] is True
    )
    assert grid_report["summary"]["reported_fill_price_matches_configured_grid_parser_side"] == 2
    with pytest.raises(ValueError, match="already been applied"):
        apply_configured_price_grid(grid_report, 0.25)


def test_position_direction_is_scoped_to_source_ledger() -> None:
    events = pd.DataFrame(
        [
            {
                "type": "open",
                "position_id": "p1",
                "direction": 1,
                "actual_tick_time": "2025-01-01T00:00:01Z",
                "price": 101.25,
                "fill_quote_source": "tick",
                "_event_ledger_source": "treatment/fills.csv",
            },
            {
                "type": "stop_close",
                "position_id": "p1",
                "direction": None,
                "actual_tick_time": "2025-01-01T00:00:02Z",
                "price": 99.5,
                "fill_quote_source": "tick",
                "_event_ledger_source": "treatment/fills.csv",
            },
            {
                "type": "open",
                "position_id": "p1",
                "direction": -1,
                "actual_tick_time": "2025-01-01T00:00:01Z",
                "price": 100.5,
                "fill_quote_source": "tick",
                "_event_ledger_source": "control/fills.csv",
            },
            {
                "type": "stop_close",
                "position_id": "p1",
                "direction": None,
                "actual_tick_time": "2025-01-01T00:00:02Z",
                "price": 101.0,
                "fill_quote_source": "tick",
                "_event_ledger_source": "control/fills.csv",
            },
        ]
    )
    ticks = pd.DataFrame(
        [
            {"<DATE>": "2025.01.01", "<TIME>": "03:00:00.000", "<BID>": 100.0, "<ASK>": 101.0},
            {"<DATE>": "2025.01.01", "<TIME>": "03:00:01.000", "<BID>": 100.5, "<ASK>": 101.25},
            {"<DATE>": "2025.01.01", "<TIME>": "03:00:02.000", "<BID>": 99.5, "<ASK>": 101.0},
        ]
    )

    report = analyze_fill_alignment(events, [ticks], source_timezone="Etc/GMT-3")

    assert [event["required_quote_side"] for event in report["events"]] == [
        "ask",
        "bid",
        "bid",
        "ask",
    ]
    assert report["summary"]["reported_fill_price_matches_stable_parser_required_side"] == 4
    assert (
        "not treated as authoritative within-timestamp chronology"
        in report["interpretation_limits"][1]
    )


def test_existing_report_direction_refresh_uses_ledger_identity() -> None:
    events = pd.DataFrame(
        [
            {
                "type": "open",
                "position_id": "shared-id",
                "direction": 1,
                "actual_tick_time": "2025-01-01T00:00:01Z",
                "order_submission_time": "2025-01-01T00:00:00Z",
                "execution_order_time": "2025-01-01T00:00:00Z",
                "execution_arrival_time": "2025-01-01T00:00:00.010Z",
                "execution_latency_ns": 10_000_000,
                "price": 101.25,
                "fill_quote_source": "tick",
                "_event_ledger_source": "treatment/fills.csv",
            },
            {
                "type": "close",
                "position_id": "shared-id",
                "direction": None,
                "actual_tick_time": "2025-01-01T00:00:02Z",
                "price": 100.0,
                "fill_quote_source": "tick",
                "_event_ledger_source": "treatment/fills.csv",
            },
            {
                "type": "open",
                "position_id": "shared-id",
                "direction": -1,
                "actual_tick_time": "2025-01-01T00:00:01Z",
                "price": 100.5,
                "fill_quote_source": "tick",
                "_event_ledger_source": "control/fills.csv",
            },
            {
                "type": "close",
                "position_id": "shared-id",
                "direction": None,
                "actual_tick_time": "2025-01-01T00:00:02Z",
                "price": 101.0,
                "fill_quote_source": "tick",
                "_event_ledger_source": "control/fills.csv",
            },
        ]
    )
    ticks = pd.DataFrame(
        [
            {"<DATE>": "2025.01.01", "<TIME>": "03:00:00.000", "<BID>": 100.0, "<ASK>": 101.0},
            {"<DATE>": "2025.01.01", "<TIME>": "03:00:01.000", "<BID>": 100.5, "<ASK>": 101.25},
            {"<DATE>": "2025.01.01", "<TIME>": "03:00:02.000", "<BID>": 100.0, "<ASK>": 101.0},
        ]
    )
    scanned = analyze_fill_alignment(events, [ticks], source_timezone="Etc/GMT-3")
    scanned["events"][0]["direction"] = -1
    scanned["events"][0]["required_quote_side"] = "bid"

    refreshed = correct_event_directions_from_ledgers(scanned, events, source_timezone="Etc/GMT-3")

    assert [event["required_quote_side"] for event in refreshed["events"]] == [
        "ask",
        "bid",
        "bid",
        "ask",
    ]
    assert refreshed["direction_resolution"]["identity_key"] == [
        "event_ledger_source",
        "position_id",
    ]
    assert refreshed["summary"]["reported_fill_price_matches_stable_parser_required_side"] == 4
    assert refreshed["execution_timing"]["events_with_order_and_arrival_times"] == 1
    assert refreshed["execution_timing"]["events_filled_at_or_after_arrival"] == 1
    assert refreshed["execution_timing"]["events_filled_before_arrival"] == 0
    assert refreshed["events"][0]["execution_latency_ms_from_timestamps"] == 10.0
    assert refreshed["events"][0]["quote_wait_ms_after_arrival"] == 990.0
