#!/usr/bin/env python3
"""Measure selected fill timestamps against source tick-side updates.

The report identifies source-resolution timestamp groups containing sparse
bid/ask updates or changed quotes at a tied timestamp. It also replays the
parser's per-side forward-fill rule to report whether its first valid quote at
an event timestamp uses a carried side. Export timestamp ties have no inferred
within-tie chronology, and this report does not establish a provider clock.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
from collections import Counter
from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd

from artifacts.atomic import write_json_atomic
from configuration.paths import repository_root
from market_data.transforms.price_grid import quantize_prices

ROOT = repository_root(__file__)
DEFAULT_CHUNK_ROWS = 500_000


def _column_map(columns: Iterable[str]) -> dict[str, str]:
    return {str(column).strip().strip("<>").upper(): str(column) for column in columns}


def _timestamp_utc(value: Any) -> pd.Timestamp | None:
    """Parse a possibly empty event timestamp into UTC."""
    if value is None or pd.isna(value) or not str(value).strip():
        return None
    parsed = pd.to_datetime(value, format="mixed", utc=True, errors="coerce")
    return None if pd.isna(parsed) else pd.Timestamp(parsed)


def _execution_timing_fields(row: Mapping[Any, Any], event_time: Any) -> dict[str, Any]:
    """Expose logged order-arrival and quote-wait timing without inferring it."""
    submission = _timestamp_utc(row.get("order_submission_time"))
    order_time = _timestamp_utc(row.get("execution_order_time"))
    arrival_time = _timestamp_utc(row.get("execution_arrival_time"))
    fill_time = _timestamp_utc(event_time)
    latency_value = row.get("execution_latency_ns")
    latency_ns = pd.to_numeric("" if latency_value is None else str(latency_value), errors="coerce")
    return {
        "order_submission_time_utc": None if submission is None else submission.isoformat(),
        "execution_order_time_utc": None if order_time is None else order_time.isoformat(),
        "execution_arrival_time_utc": None if arrival_time is None else arrival_time.isoformat(),
        "reported_execution_latency_ns": (None if pd.isna(latency_ns) else int(float(latency_ns))),
        "execution_latency_ms_from_timestamps": (
            None
            if order_time is None or arrival_time is None
            else (arrival_time - order_time).total_seconds() * 1000.0
        ),
        "quote_wait_ms_after_arrival": (
            None
            if arrival_time is None or fill_time is None
            else (fill_time - arrival_time).total_seconds() * 1000.0
        ),
    }


def _summarize_execution_timing(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize only the order/arrival/fill timestamps present in ledgers."""
    submitted = [event for event in events if event["order_submission_time_utc"] is not None]
    order_arrivals = [
        event
        for event in events
        if event["execution_order_time_utc"] is not None
        and event["execution_arrival_time_utc"] is not None
    ]
    arrival_fills = [event for event in events if event["quote_wait_ms_after_arrival"] is not None]

    def distribution(values: list[float]) -> dict[str, int | float | None]:
        return {
            "count": len(values),
            "minimum": min(values) if values else None,
            "median": float(np.median(values)) if values else None,
            "p95": float(np.quantile(values, 0.95)) if values else None,
            "maximum": max(values) if values else None,
        }

    return {
        "events_with_order_submission_time": len(submitted),
        "events_with_order_and_arrival_times": len(order_arrivals),
        "events_with_arrival_and_fill_times": len(arrival_fills),
        "events_filled_at_or_after_arrival": sum(
            float(event["quote_wait_ms_after_arrival"]) >= 0.0 for event in arrival_fills
        ),
        "events_filled_before_arrival": sum(
            float(event["quote_wait_ms_after_arrival"]) < 0.0 for event in arrival_fills
        ),
        "reported_execution_latency_ms": distribution(
            [
                float(event["execution_latency_ms_from_timestamps"])
                for event in order_arrivals
                if event["execution_latency_ms_from_timestamps"] is not None
            ]
        ),
        "quote_wait_after_arrival_ms": distribution(
            [float(event["quote_wait_ms_after_arrival"]) for event in arrival_fills]
        ),
    }


def _prepare_events(events: pd.DataFrame, source_timezone: str) -> pd.DataFrame:
    """Select tick-backed fills and assign the quote side each fill needs."""
    columns = _column_map(events.columns)
    required = {"TYPE", "POSITION_ID", "ACTUAL_TICK_TIME", "DIRECTION"}
    missing = required.difference(columns)
    if missing:
        raise ValueError(f"event ledger is missing required columns: {sorted(missing)}")

    work = events.copy()
    for normalized in required:
        work[normalized.lower()] = work[columns[normalized]]
    source_column = columns.get("_EVENT_LEDGER_SOURCE")
    source_identity = (
        pd.Series("", index=work.index, dtype="string")
        if source_column is None
        else work[source_column].fillna("").astype(str)
    )
    work["_position_identity"] = list(
        zip(source_identity, work["position_id"].astype(str), strict=True)
    )
    if "FILL_QUOTE_SOURCE" in columns:
        source = work[columns["FILL_QUOTE_SOURCE"]].fillna("").astype(str).str.lower()
        work = work.loc[source.eq("tick")].copy()

    work["event_type"] = work["type"].fillna("").astype(str).str.lower()
    work = work.loc[
        work["actual_tick_time"].notna()
        & work["actual_tick_time"].astype(str).str.strip().ne("")
        & work["position_id"].notna()
        & work["position_id"].astype(str).str.strip().ne("")
        & ~work["event_type"].isin({"reject", "rejected"})
    ].copy()

    work["direction"] = pd.to_numeric(work["direction"], errors="coerce")
    opens = work.loc[work["event_type"].eq("open")]
    directions_by_position = {
        position_identity: int(math.copysign(1, direction))
        for position_identity, direction in zip(
            opens["_position_identity"], opens["direction"], strict=True
        )
        if pd.notna(direction) and float(direction) != 0.0
    }
    work["is_entry"] = work["event_type"].eq("open")
    if "PRICE" in columns:
        work["reported_fill_price"] = pd.to_numeric(work[columns["PRICE"]], errors="coerce")
    else:
        work["reported_fill_price"] = np.nan
    direct_sign = np.sign(work["direction"])
    position_sign = work["_position_identity"].map(directions_by_position)
    direction_sign = direct_sign.where(direct_sign.ne(0) & direct_sign.notna(), position_sign)
    valid_direction = direction_sign.notna()
    work = work.loc[valid_direction].copy()
    direction_sign = direction_sign.loc[valid_direction]
    work["is_entry"] = work["event_type"].eq("open")
    work["direction_sign"] = direction_sign
    work["required_quote_side"] = np.select(
        [
            work["is_entry"] & direction_sign.gt(0),
            work["is_entry"] & direction_sign.lt(0),
            direction_sign.gt(0),
            direction_sign.lt(0),
        ],
        ["ask", "bid", "bid", "ask"],
        default="",
    )
    work["event_id"] = [str(index) for index in work.index]
    work["event_time_utc"] = pd.to_datetime(
        work["actual_tick_time"], format="mixed", utc=True, errors="coerce"
    )
    work = work.loc[work["event_time_utc"].notna() & work["required_quote_side"].notna()].copy()
    work["event_time_ns"] = work["event_time_utc"].astype("int64")
    # Event output is metadata about the provided export's wall clock. The
    # conversion uses an explicit CLI timezone and is not a source-clock claim.
    work["source_wall_time"] = work["event_time_utc"].dt.tz_convert(source_timezone).astype(str)
    return cast(pd.DataFrame, work.reset_index(drop=True))


def apply_configured_price_grid(
    report: dict[str, Any],
    increment: float,
    *,
    configuration_path: str | Path | None = None,
) -> dict[str, Any]:
    """Add deterministic price-grid reconstruction to a raw alignment report.

    The transformation mirrors the quote-book pipeline: validate raw carried
    pairs first, then round both sides with the configured half-away rule.
    Raw values remain in the report so readers can distinguish source data
    from the configured parser view.

    Args:
        report: Raw fill-to-source alignment report with parsed quote values.
        increment: Configured price-grid increment for the selected run.
        configuration_path: Optional run configuration used to identify the
            price-grid setting.

    Returns:
        A copied report with grid-quantized prices and fill comparisons.
    """
    grid = float(increment)
    if not math.isfinite(grid) or grid <= 0:
        raise ValueError("price-grid increment must be finite and positive")
    if report.get("price_grid_application") is not None:
        raise ValueError("price grid has already been applied to this alignment report")
    result = copy.deepcopy(report)

    def quantized(value: float | None) -> float | None:
        if value is None:
            return None
        return float(quantize_prices([value], grid)[0])

    for event in result.get("events", []):
        group = event.get("timestamp_group")
        if group is None:
            event["configured_grid_required_side_price"] = None
            event["reported_fill_price_matches_configured_grid_parser_side"] = None
            event["configured_grid_required_side_min_at_timestamp"] = None
            event["configured_grid_required_side_max_at_timestamp"] = None
            event["reported_fill_price_within_configured_grid_side_range"] = None
            continue

        for side in ("bid", "ask"):
            group[f"configured_grid_first_valid_{side}"] = quantized(
                group.get(f"stable_parser_first_valid_{side}")
            )
            group[f"configured_grid_raw_{side}_min"] = quantized(group.get(f"raw_{side}_min"))
            group[f"configured_grid_raw_{side}_max"] = quantized(group.get(f"raw_{side}_max"))

        required_side = str(event["required_quote_side"])
        parser_price = group[f"configured_grid_first_valid_{required_side}"]
        raw_min = group[f"configured_grid_raw_{required_side}_min"]
        raw_max = group[f"configured_grid_raw_{required_side}_max"]
        fill_price = event.get("reported_fill_price")
        matches = (
            None
            if fill_price is None or parser_price is None
            else math.isclose(float(fill_price), parser_price, rel_tol=0.0, abs_tol=1e-6)
        )
        within_range = (
            None
            if fill_price is None or raw_min is None or raw_max is None
            else raw_min - 1e-6 <= float(fill_price) <= raw_max + 1e-6
        )
        event["configured_grid_required_side_price"] = parser_price
        event["reported_fill_price_matches_configured_grid_parser_side"] = matches
        event["configured_grid_required_side_min_at_timestamp"] = raw_min
        event["configured_grid_required_side_max_at_timestamp"] = raw_max
        event["reported_fill_price_within_configured_grid_side_range"] = within_range

    summary = result.setdefault("summary", {})
    for key in (
        "reported_fill_price_matches_configured_grid_parser_side",
        "reported_fill_price_differs_from_configured_grid_parser_side",
    ):
        summary.pop(key, None)
    for event in result.get("events", []):
        matches = event.get("reported_fill_price_matches_configured_grid_parser_side")
        if matches is not None:
            key = (
                "reported_fill_price_matches_configured_grid_parser_side"
                if matches
                else "reported_fill_price_differs_from_configured_grid_parser_side"
            )
            summary[key] = int(summary.get(key, 0)) + 1

    config = None if configuration_path is None else Path(configuration_path)
    result["schema_version"] = 3
    result["price_grid_application"] = {
        "increment": grid,
        "rounding": "nearest_half_away_from_zero",
        "configuration_path": None if config is None else str(config),
        "configuration_sha256": None if config is None else _sha256(config),
        "order": "carry sides and validate quote pair, then quantize",
    }
    return result


def correct_event_directions_from_ledgers(
    report: dict[str, Any],
    event_ledger: pd.DataFrame,
    *,
    source_timezone: str,
) -> dict[str, Any]:
    """Rebind event directions using both ledger source and position ID.

    Independent run ledgers can reuse position IDs. This refresh prevents an
    open in one ledger from overwriting the direction of the same ID in its
    matched control or treatment ledger.

    Args:
        report: Existing raw alignment report with source event IDs.
        event_ledger: Combined fill rows tagged with ``_event_ledger_source``.
        source_timezone: Timezone recorded by the existing alignment scan.

    Returns:
        A copied report with corrected direction and required-side metrics.
    """
    result = copy.deepcopy(report)
    if result.get("source_timezone_used_for_timestamp_join") != source_timezone:
        raise ValueError("direction refresh timezone must match the report timezone")
    prepared = _prepare_events(event_ledger, source_timezone)
    rows_by_id = {str(row["event_id"]): row for row in prepared.to_dict(orient="records")}

    for event in result.get("events", []):
        row = rows_by_id.get(str(event["event_id"]))
        if row is None:
            raise ValueError(f"event ledger rows do not cover report event {event['event_id']!r}")
        if str(row["position_id"]) != str(event["position_id"]) or str(
            row.get("_event_ledger_source")
        ) != str(event.get("event_ledger_source")):
            raise ValueError(f"event identity mismatch for report event {event['event_id']!r}")

        side = str(row["required_quote_side"])
        event["direction"] = int(row["direction_sign"])
        event["required_quote_side"] = side
        event.update(_execution_timing_fields(row, event.get("event_time_utc")))
        group = event.get("timestamp_group")
        if group is None:
            event.update(
                {
                    "stable_parser_required_side_price": None,
                    "stable_parser_required_side_price_matches_fill": None,
                    "stable_parser_required_side_carried": None,
                    "stable_parser_required_side_source_time_utc": None,
                    "stable_parser_required_side_age_ms_at_fill_time": None,
                    "raw_required_side_min_at_timestamp": None,
                    "raw_required_side_max_at_timestamp": None,
                    "reported_fill_price_within_raw_side_range": None,
                }
            )
        else:
            parser_price = group[f"stable_parser_first_valid_{side}"]
            raw_min = group[f"raw_{side}_min"]
            raw_max = group[f"raw_{side}_max"]
            source_time = group[f"stable_parser_{side}_source_time_utc"]
            source_time_ns = None if source_time is None else int(pd.Timestamp(source_time).value)
            event_time_ns = int(pd.Timestamp(event["event_time_utc"]).value)
            fill_price = event.get("reported_fill_price")
            event.update(
                {
                    "stable_parser_required_side_price": parser_price,
                    "stable_parser_required_side_price_matches_fill": (
                        None
                        if fill_price is None or parser_price is None
                        else math.isclose(
                            float(fill_price), float(parser_price), rel_tol=0.0, abs_tol=1e-6
                        )
                    ),
                    "stable_parser_required_side_carried": group[f"first_valid_{side}_carried"],
                    "stable_parser_required_side_source_time_utc": source_time,
                    "stable_parser_required_side_age_ms_at_fill_time": (
                        None
                        if source_time_ns is None
                        else (event_time_ns - source_time_ns) / 1_000_000.0
                    ),
                    "raw_required_side_min_at_timestamp": raw_min,
                    "raw_required_side_max_at_timestamp": raw_max,
                    "reported_fill_price_within_raw_side_range": (
                        None
                        if fill_price is None or raw_min is None or raw_max is None
                        else float(raw_min) - 1e-6 <= float(fill_price) <= float(raw_max) + 1e-6
                    ),
                }
            )
            for key in tuple(group):
                if key.startswith("configured_grid_"):
                    group.pop(key)

        for key in (
            "configured_grid_required_side_price",
            "reported_fill_price_matches_configured_grid_parser_side",
            "configured_grid_required_side_min_at_timestamp",
            "configured_grid_required_side_max_at_timestamp",
            "reported_fill_price_within_configured_grid_side_range",
        ):
            event.pop(key, None)

    result.pop("price_grid_application", None)
    result.pop("price_grid_postprocessor_path", None)
    result.pop("price_grid_postprocessor_sha256", None)
    result["schema_version"] = 2
    result["summary"] = _summarize_alignment_events(result.get("events", []))
    result["execution_timing"] = _summarize_execution_timing(result.get("events", []))
    result["direction_resolution"] = {
        "identity_key": ["event_ledger_source", "position_id"],
        "method": "opening direction resolved independently within each source ledger",
    }
    return result


def _summarize_alignment_events(events: list[dict[str, Any]]) -> dict[str, int]:
    """Recompute base alignment counters from event records."""
    counts: Counter[str] = Counter()
    for event in events:
        counts["events"] += 1
        counts["entries" if event["event_type"] == "open" else "exits"] += 1
        group = event.get("timestamp_group")
        if group is None:
            counts["unmatched_timestamps"] += 1
            continue
        counts["matched_timestamps"] += 1
        if group["changed_quote_within_timestamp"]:
            counts["events_in_changed_quote_groups"] += 1
        side = str(event["required_quote_side"])
        if group[f"missing_{side}_rows"] > 0:
            counts["events_in_groups_with_missing_required_side"] += 1
        if group["first_valid_quote_exists"] and group[f"first_valid_{side}_carried"]:
            counts["first_parser_quote_carried_required_side"] += 1
            counts["events_with_stable_parser_carried_required_side"] += 1
        if not group["first_valid_quote_exists"]:
            counts["groups_without_valid_parser_quote"] += 1
        matches = event.get("stable_parser_required_side_price_matches_fill")
        if matches is not None:
            counts[
                "reported_fill_price_matches_stable_parser_required_side"
                if matches
                else "reported_fill_price_differs_from_stable_parser_required_side"
            ] += 1
    return dict(counts)


class _TimestampGroup:
    """Streaming summary for one raw timestamp, preserving source row order."""

    def __init__(self, timestamp_ns: int) -> None:
        self.timestamp_ns = timestamp_ns
        self.rows = 0
        self.missing_bid_rows = 0
        self.missing_ask_rows = 0
        self.bid_min = math.inf
        self.bid_max = -math.inf
        self.ask_min = math.inf
        self.ask_max = -math.inf
        self.first_valid_bid_carried: bool | None = None
        self.first_valid_ask_carried: bool | None = None
        self.first_valid_bid: float | None = None
        self.first_valid_ask: float | None = None
        self.first_valid_bid_source_ns: int | None = None
        self.first_valid_ask_source_ns: int | None = None

    def add(
        self,
        raw_bid: float,
        raw_ask: float,
        carried_bid: float,
        carried_ask: float,
        *,
        missing_bid: bool,
        missing_ask: bool,
    ) -> None:
        self.rows += 1
        self.missing_bid_rows += int(missing_bid)
        self.missing_ask_rows += int(missing_ask)
        if not missing_bid:
            self.bid_min = min(self.bid_min, raw_bid)
            self.bid_max = max(self.bid_max, raw_bid)
        if not missing_ask:
            self.ask_min = min(self.ask_min, raw_ask)
            self.ask_max = max(self.ask_max, raw_ask)
        if (
            self.first_valid_bid_carried is None
            and math.isfinite(carried_bid)
            and math.isfinite(carried_ask)
            and carried_bid > 0.0
            and carried_ask >= carried_bid
        ):
            self.first_valid_bid_carried = missing_bid
            self.first_valid_ask_carried = missing_ask

    def add_chunk_group(
        self,
        *,
        row_count: int,
        missing_bid_rows: int,
        missing_ask_rows: int,
        bid_min: float,
        bid_max: float,
        ask_min: float,
        ask_max: float,
        first_valid_bid_carried: bool | None,
        first_valid_ask_carried: bool | None,
        first_valid_bid: float | None,
        first_valid_ask: float | None,
        first_valid_bid_source_ns: int | None,
        first_valid_ask_source_ns: int | None,
    ) -> None:
        """Merge one vectorized chunk's partial summary for this timestamp."""
        self.rows += row_count
        self.missing_bid_rows += missing_bid_rows
        self.missing_ask_rows += missing_ask_rows
        self.bid_min = min(self.bid_min, bid_min)
        self.bid_max = max(self.bid_max, bid_max)
        self.ask_min = min(self.ask_min, ask_min)
        self.ask_max = max(self.ask_max, ask_max)
        if self.first_valid_bid_carried is None and first_valid_bid_carried is not None:
            self.first_valid_bid_carried = first_valid_bid_carried
            self.first_valid_ask_carried = first_valid_ask_carried
            self.first_valid_bid = first_valid_bid
            self.first_valid_ask = first_valid_ask
            self.first_valid_bid_source_ns = first_valid_bid_source_ns
            self.first_valid_ask_source_ns = first_valid_ask_source_ns

    @staticmethod
    def _finite_or_none(value: float) -> float | None:
        return float(value) if math.isfinite(value) else None

    @staticmethod
    def _timestamp_or_none(value: int | None) -> str | None:
        return None if value is None else pd.Timestamp(value, unit="ns", tz="UTC").isoformat()

    def as_record(self) -> dict[str, Any]:
        return {
            "source_timestamp_utc": pd.Timestamp(
                self.timestamp_ns, unit="ns", tz="UTC"
            ).isoformat(),
            "raw_rows_at_timestamp": self.rows,
            "missing_bid_rows": self.missing_bid_rows,
            "missing_ask_rows": self.missing_ask_rows,
            "raw_bid_min": self._finite_or_none(self.bid_min),
            "raw_bid_max": self._finite_or_none(self.bid_max),
            "raw_ask_min": self._finite_or_none(self.ask_min),
            "raw_ask_max": self._finite_or_none(self.ask_max),
            "changed_bid_within_timestamp": bool(self.bid_min < self.bid_max),
            "changed_ask_within_timestamp": bool(self.ask_min < self.ask_max),
            "changed_quote_within_timestamp": bool(
                self.bid_min < self.bid_max or self.ask_min < self.ask_max
            ),
            "first_valid_quote_exists": self.first_valid_bid_carried is not None,
            "first_valid_bid_carried": self.first_valid_bid_carried,
            "first_valid_ask_carried": self.first_valid_ask_carried,
            "stable_parser_first_valid_bid": self.first_valid_bid,
            "stable_parser_first_valid_ask": self.first_valid_ask,
            "stable_parser_bid_source_time_utc": self._timestamp_or_none(
                self.first_valid_bid_source_ns
            ),
            "stable_parser_ask_source_time_utc": self._timestamp_or_none(
                self.first_valid_ask_source_ns
            ),
        }


def analyze_fill_alignment(
    event_ledger: pd.DataFrame,
    tick_chunks: Iterable[pd.DataFrame],
    *,
    source_timezone: str,
) -> dict[str, Any]:
    """Join filled entry/exit timestamps to streamed source quote groups.

    ``tick_chunks`` must contain MT5 DATE/TIME/BID/ASK columns in source order.
    The timestamp timezone is required explicitly because local export values
    alone do not establish which clock the provider used.
    """
    events = _prepare_events(event_ledger, source_timezone)
    wanted: dict[int, list[int]] = {}
    for index, timestamp_ns in enumerate(events["event_time_ns"].to_numpy(dtype=np.int64)):
        wanted.setdefault(int(timestamp_ns), []).append(index)

    matched: dict[int, _TimestampGroup] = {}
    scanned_rows = 0
    parse_failures = 0
    out_of_order_rows = 0
    last_timestamp_ns: int | None = None
    last_bid = math.nan
    last_ask = math.nan
    last_bid_source_ns: int | None = None
    last_ask_source_ns: int | None = None
    wanted_timestamps = np.fromiter(wanted, dtype=np.int64)

    for chunk in tick_chunks:
        columns = _column_map(chunk.columns)
        needed = {"DATE", "TIME", "BID", "ASK"}
        missing_columns = needed.difference(columns)
        if missing_columns:
            raise ValueError(f"tick input is missing columns: {sorted(missing_columns)}")
        date_values = chunk[columns["DATE"]].astype(str)
        time_values = chunk[columns["TIME"]].astype(str)
        joined = date_values + " " + time_values
        has_fraction = time_values.str.contains("\\.", regex=True).any()
        fmt = "%Y.%m.%d %H:%M:%S.%f" if has_fraction else "%Y.%m.%d %H:%M:%S"
        parsed = pd.to_datetime(joined, format=fmt, errors="coerce")
        parse_failures += int(parsed.isna().sum())
        if parsed.isna().any():
            raise ValueError(
                "tick input has unparsable DATE/TIME values; refusing partial alignment"
            )
        timestamp_ns_values = (
            parsed.dt.tz_localize(source_timezone).dt.tz_convert("UTC").astype("int64").to_numpy()
        )
        if len(timestamp_ns_values) > 1:
            out_of_order_rows += int((np.diff(timestamp_ns_values) < 0).sum())
            if np.any(np.diff(timestamp_ns_values) < 0):
                raise ValueError(
                    "tick source is not monotonic; refusing chronology-dependent alignment"
                )
        if last_timestamp_ns is not None and timestamp_ns_values[0] < last_timestamp_ns:
            out_of_order_rows += 1
            raise ValueError("tick source is not monotonic across chunks; refusing alignment")
        bids = pd.to_numeric(chunk[columns["BID"]], errors="coerce").to_numpy(dtype=np.float64)
        asks = pd.to_numeric(chunk[columns["ASK"]], errors="coerce").to_numpy(dtype=np.float64)
        scanned_rows += len(chunk)
        if not len(chunk):
            continue

        missing_bid = ~np.isfinite(bids) | (bids <= 0.0)
        missing_ask = ~np.isfinite(asks) | (asks <= 0.0)
        clean_bid = np.where(missing_bid, np.nan, bids)
        clean_ask = np.where(missing_ask, np.nan, asks)
        carried_bid = pd.Series(np.concatenate(([last_bid], clean_bid))).ffill().to_numpy()[1:]
        carried_ask = pd.Series(np.concatenate(([last_ask], clean_ask))).ffill().to_numpy()[1:]
        valid_pair = (
            np.isfinite(carried_bid)
            & np.isfinite(carried_ask)
            & (carried_bid > 0.0)
            & (carried_ask >= carried_bid)
        )
        bid_update_ns = np.where(missing_bid, -1, timestamp_ns_values)
        ask_update_ns = np.where(missing_ask, -1, timestamp_ns_values)
        bid_source_ns = np.maximum.accumulate(
            np.concatenate(
                (
                    np.array([-1 if last_bid_source_ns is None else last_bid_source_ns]),
                    bid_update_ns,
                )
            )
        )[1:]
        ask_source_ns = np.maximum.accumulate(
            np.concatenate(
                (
                    np.array([-1 if last_ask_source_ns is None else last_ask_source_ns]),
                    ask_update_ns,
                )
            )
        )[1:]

        # Only materialize group summaries for event timestamps; side carry is
        # still updated over every row so the selected group's state is exact.
        target_mask = np.isin(timestamp_ns_values, wanted_timestamps)
        target_times = np.unique(timestamp_ns_values[target_mask])
        for timestamp_ns in target_times:
            timestamp_ns = int(timestamp_ns)
            lo = int(np.searchsorted(timestamp_ns_values, timestamp_ns, side="left"))
            hi = int(np.searchsorted(timestamp_ns_values, timestamp_ns, side="right"))
            bid_present = ~missing_bid[lo:hi]
            ask_present = ~missing_ask[lo:hi]
            candidate_rows = np.flatnonzero(valid_pair[lo:hi])
            if len(candidate_rows):
                first_valid = lo + int(candidate_rows[0])
                first_bid_carried: bool | None = bool(missing_bid[first_valid])
                first_ask_carried: bool | None = bool(missing_ask[first_valid])
                first_valid_bid: float | None = float(carried_bid[first_valid])
                first_valid_ask: float | None = float(carried_ask[first_valid])
                first_valid_bid_source_ns: int | None = int(bid_source_ns[first_valid])
                first_valid_ask_source_ns: int | None = int(ask_source_ns[first_valid])
            else:
                first_bid_carried = None
                first_ask_carried = None
                first_valid_bid = first_valid_ask = None
                first_valid_bid_source_ns = first_valid_ask_source_ns = None
            timestamp_summary = matched.setdefault(timestamp_ns, _TimestampGroup(timestamp_ns))
            timestamp_summary.add_chunk_group(
                row_count=hi - lo,
                missing_bid_rows=int(missing_bid[lo:hi].sum()),
                missing_ask_rows=int(missing_ask[lo:hi].sum()),
                bid_min=float(bids[lo:hi][bid_present].min()) if bid_present.any() else math.inf,
                bid_max=float(bids[lo:hi][bid_present].max()) if bid_present.any() else -math.inf,
                ask_min=float(asks[lo:hi][ask_present].min()) if ask_present.any() else math.inf,
                ask_max=float(asks[lo:hi][ask_present].max()) if ask_present.any() else -math.inf,
                first_valid_bid_carried=first_bid_carried,
                first_valid_ask_carried=first_ask_carried,
                first_valid_bid=first_valid_bid,
                first_valid_ask=first_valid_ask,
                first_valid_bid_source_ns=first_valid_bid_source_ns,
                first_valid_ask_source_ns=first_valid_ask_source_ns,
            )
        last_bid = float(carried_bid[-1]) if math.isfinite(carried_bid[-1]) else math.nan
        last_ask = float(carried_ask[-1]) if math.isfinite(carried_ask[-1]) else math.nan
        last_bid_source_ns = int(bid_source_ns[-1]) if bid_source_ns[-1] >= 0 else None
        last_ask_source_ns = int(ask_source_ns[-1]) if ask_source_ns[-1] >= 0 else None
        last_timestamp_ns = int(timestamp_ns_values[-1])

    output_events: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for row in events.to_dict(orient="records"):
        event_type = str(row["event_type"])
        required_side = str(row["required_quote_side"])
        event_time = pd.Timestamp(row["event_time_utc"])
        group_summary = matched.get(int(row["event_time_ns"]))
        event_group: dict[str, Any] | None = (
            group_summary.as_record() if group_summary is not None else None
        )
        reported_fill_price = row.get("reported_fill_price")
        reported_fill_price = (
            float(reported_fill_price)
            if reported_fill_price is not None
            and pd.notna(reported_fill_price)
            and math.isfinite(float(reported_fill_price))
            else None
        )
        parser_side_price = (
            None
            if event_group is None
            else event_group[f"stable_parser_first_valid_{required_side}"]
        )
        raw_side_min = None if event_group is None else event_group[f"raw_{required_side}_min"]
        raw_side_max = None if event_group is None else event_group[f"raw_{required_side}_max"]
        source_time = (
            None
            if event_group is None
            else event_group[f"stable_parser_{required_side}_source_time_utc"]
        )
        carried_side = (
            None if event_group is None else event_group[f"first_valid_{required_side}_carried"]
        )
        source_time_ns = None if source_time is None else int(pd.Timestamp(source_time).value)
        carry_age_ms = (
            None
            if source_time_ns is None
            else (int(row["event_time_ns"]) - source_time_ns) / 1_000_000.0
        )
        parser_price_match = (
            None
            if reported_fill_price is None or parser_side_price is None
            else math.isclose(reported_fill_price, parser_side_price, rel_tol=0.0, abs_tol=1e-6)
        )
        raw_range_match = (
            None
            if reported_fill_price is None or raw_side_min is None or raw_side_max is None
            else raw_side_min - 1e-6 <= reported_fill_price <= raw_side_max + 1e-6
        )
        record = {
            "event_id": row["event_id"],
            "event_ledger_source": row.get("_event_ledger_source"),
            "event_type": event_type,
            "position_id": str(row["position_id"]),
            "event_time_utc": event_time.isoformat(),
            "source_wall_time_using_configured_timezone": row["source_wall_time"],
            **_execution_timing_fields(row, event_time),
            "direction": int(float(row["direction_sign"])),
            "required_quote_side": required_side,
            "reported_fill_price": reported_fill_price,
            "stable_parser_required_side_price": parser_side_price,
            "stable_parser_required_side_price_matches_fill": parser_price_match,
            "stable_parser_required_side_carried": carried_side,
            "stable_parser_required_side_source_time_utc": source_time,
            "stable_parser_required_side_age_ms_at_fill_time": carry_age_ms,
            "raw_required_side_min_at_timestamp": raw_side_min,
            "raw_required_side_max_at_timestamp": raw_side_max,
            "reported_fill_price_within_raw_side_range": raw_range_match,
            "timestamp_group_matched": event_group is not None,
            "timestamp_group": event_group,
        }
        output_events.append(record)
        counts["events"] += 1
        counts["entries" if row["is_entry"] else "exits"] += 1
        if event_group is None:
            counts["unmatched_timestamps"] += 1
            continue
        counts["matched_timestamps"] += 1
        if event_group["changed_quote_within_timestamp"]:
            counts["events_in_changed_quote_groups"] += 1
        if event_group[f"missing_{required_side}_rows"] > 0:
            counts["events_in_groups_with_missing_required_side"] += 1
        if (
            event_group["first_valid_quote_exists"]
            and event_group[f"first_valid_{required_side}_carried"]
        ):
            counts["first_parser_quote_carried_required_side"] += 1
        if not event_group["first_valid_quote_exists"]:
            counts["groups_without_valid_parser_quote"] += 1
        if parser_price_match is not None:
            counts[
                "reported_fill_price_matches_stable_parser_required_side"
                if parser_price_match
                else "reported_fill_price_differs_from_stable_parser_required_side"
            ] += 1
        if carried_side:
            counts["events_with_stable_parser_carried_required_side"] += 1

    return {
        "schema_version": 2,
        "source_timezone_used_for_timestamp_join": source_timezone,
        "event_count": len(output_events),
        "tick_rows_scanned": scanned_rows,
        "tick_timestamp_parse_failures": parse_failures,
        "out_of_order_rows": out_of_order_rows,
        "summary": dict(counts),
        "execution_timing": _summarize_execution_timing(output_events),
        "interpretation_limits": [
            "Timestamp joins are at the precision exported by the local files.",
            "Same-timestamp source row order is preserved to emulate the parser; it is not treated as authoritative within-timestamp chronology.",
            "A carried side is a property of the configured local parser's forward-fill rule, not proof of simultaneous executable quote availability.",
            "The configured timezone is used only for local-to-UTC alignment; this report does not establish the source clock, DST history, or feed schedule.",
            "Stable-parser prices reproduce the first valid carried quote under the source file row order. Tied timestamp groups do not establish that this row order is real quote chronology.",
            "Raw side minima and maxima are descriptive values observed at the fill timestamp; they are not a valid bid/ask pair or an executable-price interval.",
            "The report compares the ledger's recorded fill price to the local parser reconstruction. It does not independently prove the broker used that quote or reconstruct order-arrival causality.",
        ],
        "events": output_events,
    }


def _read_tick_chunks(path: Path, chunksize: int) -> Iterator[pd.DataFrame]:
    return pd.read_csv(path, sep="\t", chunksize=chunksize, engine="c", encoding="utf-8-sig")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--events-csv",
        type=Path,
        action="append",
        default=[],
        help="Selected run training/fills.csv or trades.csv; repeat to align multiple ledgers in one tick scan",
    )
    parser.add_argument("--ticks-csv", type=Path, help="Matching local MT5 tick export")
    parser.add_argument(
        "--source-timezone",
        help="Explicit configured timezone used by tick ingestion",
    )
    parser.add_argument(
        "--regrid-existing-report",
        type=Path,
        help="Apply the configured price grid to a previously generated raw alignment report",
    )
    parser.add_argument(
        "--price-grid-increment",
        type=float,
        help="Optional configured price-grid increment; applied after quote-pair validation",
    )
    parser.add_argument(
        "--price-grid-config",
        type=Path,
        help="Optional config path recorded as provenance for the price-grid increment",
    )
    parser.add_argument("--chunksize", type=int, default=DEFAULT_CHUNK_ROWS)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.chunksize < 1:
        parser.error("--chunksize must be positive")
    tool_path = Path(__file__).resolve()
    if args.regrid_existing_report is not None:
        if args.ticks_csv is not None:
            parser.error("--regrid-existing-report cannot be combined with --ticks-csv")
        if args.price_grid_increment is None:
            parser.error("--regrid-existing-report requires --price-grid-increment")
        if not args.events_csv or args.source_timezone is None:
            parser.error(
                "refreshing an existing report requires --events-csv and --source-timezone"
            )
        if not args.regrid_existing_report.is_file():
            parser.error("the existing alignment report must exist")
        if any(not path.is_file() for path in args.events_csv):
            parser.error("all event ledgers must exist")
        if args.price_grid_config is not None and not args.price_grid_config.is_file():
            parser.error("the price-grid configuration path must exist")
        report = json.loads(args.regrid_existing_report.read_text(encoding="utf-8"))
        event_frames = []
        for path in args.events_csv:
            frame = pd.read_csv(path)
            frame["_event_ledger_source"] = str(path)
            event_frames.append(frame)
        event_ledger = pd.concat(event_frames, ignore_index=True)
        report = correct_event_directions_from_ledgers(
            report,
            event_ledger,
            source_timezone=args.source_timezone,
        )
        report = apply_configured_price_grid(
            report,
            args.price_grid_increment,
            configuration_path=args.price_grid_config,
        )
        report["price_grid_postprocessor_path"] = str(tool_path.relative_to(ROOT))
        report["price_grid_postprocessor_sha256"] = _sha256(tool_path)
        write_json_atomic(args.out, report)
        print(
            json.dumps(
                {
                    "out": str(args.out),
                    "price_grid_increment": args.price_grid_increment,
                    "summary": report["summary"],
                },
                sort_keys=True,
            )
        )
        return
    if args.ticks_csv is None or args.source_timezone is None or not args.events_csv:
        parser.error(
            "a tick scan requires --ticks-csv, --source-timezone, and at least one --events-csv"
        )
    if args.price_grid_config is not None and not args.price_grid_config.is_file():
        parser.error("the price-grid configuration path must exist")
    if any(not path.is_file() for path in args.events_csv) or not args.ticks_csv.is_file():
        parser.error("all event ledgers and the tick input must exist")
    event_frames = []
    for path in args.events_csv:
        frame = pd.read_csv(path)
        frame["_event_ledger_source"] = str(path)
        event_frames.append(frame)
    events = pd.concat(event_frames, ignore_index=True)
    report = analyze_fill_alignment(
        events,
        _read_tick_chunks(args.ticks_csv, args.chunksize),
        source_timezone=args.source_timezone,
    )
    report["event_ledger_paths"] = [str(path) for path in args.events_csv]
    report["tick_source_path"] = str(args.ticks_csv)
    report["analysis_tool_path"] = str(tool_path.relative_to(ROOT))
    report["analysis_tool_sha256"] = _sha256(tool_path)
    report["event_ledger_sha256"] = {str(path): _sha256(path) for path in args.events_csv}
    report["tick_source_sha256"] = _sha256(args.ticks_csv)
    if args.price_grid_increment is not None:
        report = apply_configured_price_grid(
            report,
            args.price_grid_increment,
            configuration_path=args.price_grid_config,
        )
    write_json_atomic(args.out, report)
    print(
        json.dumps(
            {
                "out": str(args.out),
                "summary": report["summary"],
                "tick_rows_scanned": report["tick_rows_scanned"],
            },
            sort_keys=True,
        )
    )


def _sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


if __name__ == "__main__":
    main()
