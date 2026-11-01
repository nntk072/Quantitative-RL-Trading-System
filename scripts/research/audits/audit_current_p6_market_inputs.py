#!/usr/bin/env python3
"""Verify and quality-scan the market inputs named by the recovered P6 manifest.

The audit streams MT5 exports in bounded chunks. It reports observed timestamp
gaps without labeling market closures as missing bars; timezone and schedule
interpretation require separate source-specific evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from artifacts.atomic import write_json_atomic
from configuration.paths import repository_root

ROOT = repository_root(__file__)
CAMPAIGN = (
    ROOT
    / "outputs/gpu_campaigns/rq1_entry_fsm_pair_seed50_train2025_20261024_policy2m_v1/campaign.json"
)
DEFAULT_OUTPUT = (
    ROOT / "evidence/research/releases/negative-evidence-readiness-2026-11-01/"
    "current_source_market_input_audit.json"
)
CHUNK_ROWS = 500_000


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _timestamp_columns(header: list[str]) -> tuple[str, str | None]:
    upper = {name.upper(): name for name in header}
    date_name = upper.get("<DATE>") or upper.get("DATE")
    time_name = upper.get("<TIME>") or upper.get("TIME")
    if date_name is None:
        raise ValueError(f"missing DATE column: {header}")
    return date_name, time_name


def _parse_timestamp(frame: pd.DataFrame, date_col: str, time_col: str | None) -> pd.Series:
    if time_col is None:
        return pd.to_datetime(frame[date_col], format="%Y.%m.%d", errors="coerce")
    joined = frame[date_col].astype(str) + " " + frame[time_col].astype(str)
    has_fraction = frame[time_col].astype(str).str.contains("\\.", regex=True).any()
    fmt = "%Y.%m.%d %H:%M:%S.%f" if has_fraction else "%Y.%m.%d %H:%M:%S"
    return pd.to_datetime(joined, format=fmt, errors="coerce")


def scan_csv(path: Path, *, chunksize: int = CHUNK_ROWS) -> dict[str, Any]:
    with path.open(encoding="utf-8-sig") as stream:
        header = [value.strip() for value in stream.readline().rstrip("\r\n").split("\t")]
    upper = {name.upper(): name for name in header}
    is_tick = all(name in upper for name in ("<BID>", "<ASK>"))
    date_col, time_col = _timestamp_columns(header)
    kind = "tick" if is_tick else "bar"
    required_numeric = (
        [upper[x] for x in ("<BID>", "<ASK>") if x in upper]
        if is_tick
        else [
            upper[x]
            for x in ("<OPEN>", "<HIGH>", "<LOW>", "<CLOSE>", "<TICKVOL>", "<VOL>", "<SPREAD>")
            if x in upper
        ]
    )
    if is_tick and not {"<BID>", "<ASK>", "<LAST>", "<VOLUME>"}.issubset(upper):
        raise ValueError(f"unsupported tick columns in {path}: {header}")
    if not is_tick and not {"<OPEN>", "<HIGH>", "<LOW>", "<CLOSE>"}.issubset(upper):
        raise ValueError(f"unsupported market input columns in {path}: {header}")

    counts: Counter[str] = Counter()
    monthly_rows: Counter[str] = Counter()
    tick_minutes: set[int] = set()
    last_timestamp: pd.Timestamp | None = None
    last_bid_ask: tuple[float, float] | None = None
    first_timestamp: pd.Timestamp | None = None
    final_timestamp: pd.Timestamp | None = None
    gap_counts: Counter[str] = Counter()
    spread_sample: list[float] = []
    bar_minutes: set[int] = set()
    sample_stride = 10_000
    chunks = pd.read_csv(path, sep="\t", chunksize=chunksize, engine="c")

    for chunk in chunks:
        prior_chunk_timestamp = last_timestamp
        prior_chunk_bid_ask = last_bid_ask
        counts["rows"] += len(chunk)
        timestamps = _parse_timestamp(chunk, date_col, time_col)
        counts["timestamp_parse_failures"] += int(timestamps.isna().sum())
        if timestamps.notna().any():
            valid_ts = timestamps[timestamps.notna()]
            if first_timestamp is None:
                first_timestamp = pd.Timestamp(valid_ts.iloc[0])
            final_timestamp = pd.Timestamp(valid_ts.iloc[-1])
            if len(valid_ts) > 1:
                gaps = valid_ts.diff().dt.total_seconds()
                counts["out_of_order_adjacent_timestamps"] += int((gaps < 0).sum())
                counts["duplicate_adjacent_timestamps"] += int((gaps == 0).sum())
                if is_tick:
                    gap_counts["greater_than_1s"] += int((gaps > 1).sum())
                    gap_counts["greater_than_60s"] += int((gaps > 60).sum())
                    gap_counts["greater_than_3600s"] += int((gaps > 3600).sum())
                else:
                    gap_counts["greater_than_60s"] += int((gaps > 60).sum())
                    gap_counts["greater_than_300s"] += int((gaps > 300).sum())
                    gap_counts["greater_than_3600s"] += int((gaps > 3600).sum())
            if last_timestamp is not None and len(valid_ts):
                boundary = pd.Timestamp(valid_ts.iloc[0]) - last_timestamp
                boundary_seconds = boundary.total_seconds()
                if boundary_seconds < 0:
                    counts["out_of_order_adjacent_timestamps"] += 1
                elif boundary_seconds == 0:
                    counts["duplicate_adjacent_timestamps"] += 1
                elif is_tick:
                    if boundary_seconds > 1:
                        gap_counts["greater_than_1s"] += 1
                    if boundary_seconds > 60:
                        gap_counts["greater_than_60s"] += 1
                    if boundary_seconds > 3600:
                        gap_counts["greater_than_3600s"] += 1
                else:
                    if boundary_seconds > 60:
                        gap_counts["greater_than_60s"] += 1
                    if boundary_seconds > 300:
                        gap_counts["greater_than_300s"] += 1
                    if boundary_seconds > 3600:
                        gap_counts["greater_than_3600s"] += 1
            last_timestamp = pd.Timestamp(valid_ts.iloc[-1])
            month_values = timestamps.dt.strftime("%Y-%m")
            monthly_rows.update(month_values[timestamps.notna()].value_counts().to_dict())
            if is_tick:
                tick_minutes.update(
                    (valid_ts.astype("int64") // 60_000_000_000).astype(int).tolist()
                )
            elif "_M1_" in path.name:
                bar_minutes.update(
                    (valid_ts.astype("int64") // 60_000_000_000).astype(int).tolist()
                )

        numeric = chunk.loc[:, required_numeric].apply(pd.to_numeric, errors="coerce")
        values = numeric.to_numpy(dtype=np.float64, copy=False)
        finite = np.isfinite(values).all(axis=1)
        counts["rows_with_nonfinite_or_missing_numeric"] += int((~finite).sum())
        if is_tick:
            bid = numeric[upper["<BID>"]].to_numpy(dtype=np.float64)
            ask = numeric[upper["<ASK>"]].to_numpy(dtype=np.float64)
            finite_bid = np.isfinite(bid)
            finite_ask = np.isfinite(ask)
            finite_quote = finite_bid & finite_ask
            counts["missing_or_nonfinite_bid_rows"] += int((~finite_bid).sum())
            counts["missing_or_nonfinite_ask_rows"] += int((~finite_ask).sum())
            counts["missing_or_nonfinite_bid_and_ask_rows"] += int(
                ((~finite_bid) & (~finite_ask)).sum()
            )
            for optional_column in ("<LAST>", "<VOLUME>"):
                if optional_column in upper:
                    optional_values = pd.to_numeric(chunk[upper[optional_column]], errors="coerce")
                    counts[f"missing_optional_{optional_column.strip('<>').lower()}_rows"] += int(
                        (~np.isfinite(optional_values.to_numpy(dtype=np.float64))).sum()
                    )
            counts["nonpositive_bid_or_ask_rows"] += int(((bid <= 0) | (ask <= 0)).sum())
            counts["inverted_quote_rows"] += int((ask < bid).sum())
            adjacent_ties = timestamps.diff().eq(pd.Timedelta(0)).to_numpy()
            if (
                len(chunk)
                and prior_chunk_timestamp is not None
                and pd.notna(timestamps.iloc[0])
                and timestamps.iloc[0] == prior_chunk_timestamp
            ):
                adjacent_ties[0] = True
            if adjacent_ties.any():
                previous_bid = np.roll(bid, 1)
                previous_ask = np.roll(ask, 1)
                previous_finite = np.isfinite(previous_bid) & np.isfinite(previous_ask)
                if adjacent_ties[0] and prior_chunk_bid_ask is not None:
                    previous_bid[0], previous_ask[0] = prior_chunk_bid_ask
                    previous_finite[0] = all(np.isfinite(prior_chunk_bid_ask))
                comparable = adjacent_ties & previous_finite & finite_quote
                same_quote = comparable & (previous_bid == bid) & (previous_ask == ask)
                counts["same_timestamp_identical_bid_ask_pairs"] += int(same_quote.sum())
                counts["same_timestamp_changed_bid_ask_pairs"] += int(
                    (comparable & ~same_quote).sum()
                )
                counts["same_timestamp_pairs_with_missing_quote"] += int(
                    (adjacent_ties & ~comparable).sum()
                )
            if len(chunk):
                last_bid_ask = (float(bid[-1]), float(ask[-1]))
            spreads = ask - bid
            counts["zero_spread_rows"] += int((spreads == 0).sum())
            sampled = spreads[::sample_stride]
            spread_sample.extend(float(value) for value in sampled if math.isfinite(float(value)))
        else:
            opening, high, low, close = (
                numeric[upper[column]].to_numpy(dtype=np.float64)
                for column in ("<OPEN>", "<HIGH>", "<LOW>", "<CLOSE>")
            )
            valid_ohlc = (
                (high >= low)
                & (high >= opening)
                & (high >= close)
                & (low <= opening)
                & (low <= close)
            )
            counts["invalid_ohlc_rows"] += int((finite & ~valid_ohlc).sum())
            for col, key in (
                ("<TICKVOL>", "negative_tick_volume_rows"),
                ("<VOL>", "negative_real_volume_rows"),
                ("<SPREAD>", "negative_spread_rows"),
            ):
                if col in upper:
                    values_for_col = numeric[upper[col]]
                    counts[key] += int((values_for_col < 0).sum())

    try:
        display_path = path.relative_to(ROOT).as_posix()
    except ValueError:
        display_path = path.as_posix()
    report: dict[str, Any] = {
        "path": display_path,
        "kind": kind,
        "bytes": path.stat().st_size,
        "row_count": counts["rows"],
        "timestamp_parse_failures": counts["timestamp_parse_failures"],
        "out_of_order_adjacent_timestamps": counts["out_of_order_adjacent_timestamps"],
        "duplicate_adjacent_timestamps": counts["duplicate_adjacent_timestamps"],
        "first_timestamp_wall_clock": first_timestamp.isoformat()
        if first_timestamp is not None
        else None,
        "last_timestamp_wall_clock": final_timestamp.isoformat()
        if final_timestamp is not None
        else None,
        "rows_with_nonfinite_or_missing_numeric": counts["rows_with_nonfinite_or_missing_numeric"],
        "observed_gap_counts": dict(gap_counts),
        "rows_by_month": dict(sorted(monthly_rows.items())),
    }
    if is_tick:
        spread_array = np.asarray(spread_sample, dtype=np.float64)
        report.update(
            {
                "nonpositive_bid_or_ask_rows": counts["nonpositive_bid_or_ask_rows"],
                "inverted_quote_rows": counts["inverted_quote_rows"],
                "zero_spread_rows": counts["zero_spread_rows"],
                "missing_or_nonfinite_bid_rows": counts["missing_or_nonfinite_bid_rows"],
                "missing_or_nonfinite_ask_rows": counts["missing_or_nonfinite_ask_rows"],
                "missing_or_nonfinite_bid_and_ask_rows": counts[
                    "missing_or_nonfinite_bid_and_ask_rows"
                ],
                "same_timestamp_identical_bid_ask_pairs": counts[
                    "same_timestamp_identical_bid_ask_pairs"
                ],
                "same_timestamp_changed_bid_ask_pairs": counts[
                    "same_timestamp_changed_bid_ask_pairs"
                ],
                "same_timestamp_pairs_with_missing_quote": counts[
                    "same_timestamp_pairs_with_missing_quote"
                ],
                "missing_optional_last_rows": counts["missing_optional_last_rows"],
                "missing_optional_volume_rows": counts["missing_optional_volume_rows"],
                "sampled_spread_quantiles": {
                    "sample_every_rows": sample_stride,
                    "sample_count": int(spread_array.size),
                    "p50": float(np.quantile(spread_array, 0.50)) if spread_array.size else None,
                    "p95": float(np.quantile(spread_array, 0.95)) if spread_array.size else None,
                    "p99": float(np.quantile(spread_array, 0.99)) if spread_array.size else None,
                },
                "observed_unique_quote_minutes": len(tick_minutes),
                "_tick_minutes": tick_minutes,
            }
        )
    else:
        report.update(
            {
                "invalid_ohlc_rows": counts["invalid_ohlc_rows"],
                "negative_tick_volume_rows": counts["negative_tick_volume_rows"],
                "negative_real_volume_rows": counts["negative_real_volume_rows"],
                "negative_spread_rows": counts["negative_spread_rows"],
            }
        )
        if "_M1_" in path.name:
            report["_bar_minutes"] = bar_minutes
    return report


def build_report(campaign_path: Path, *, chunksize: int = CHUNK_ROWS) -> dict[str, Any]:
    campaign = json.loads(campaign_path.read_text(encoding="utf-8"))
    inputs: dict[str, str] = campaign["data_inputs"]
    records: list[dict[str, Any]] = []
    by_path: dict[str, dict[str, Any]] = {}
    minute_indexes: dict[str, set[int]] = {}
    for identity, expected_hash in sorted(inputs.items()):
        role, relative = identity.split(":", 1)
        path = (ROOT / relative).resolve()
        path.relative_to(ROOT)
        if not path.is_file():
            records.append({"identity": identity, "path": relative, "status": "missing"})
            continue
        actual_hash = sha256_file(path)
        quality: dict[str, Any]
        if role == "calendar":
            schedule = pd.read_csv(path)
            date_col = next(
                (str(name) for name in schedule if str(name).lower() in {"date", "session_date"}),
                None,
            )
            quality = {
                "kind": "configured_session_calendar",
                "bytes": path.stat().st_size,
                "row_count": len(schedule),
                "columns": list(schedule.columns),
                "date_column": date_col,
                "duplicate_dates": int(schedule[date_col].duplicated().sum()) if date_col else None,
                "first_date": str(schedule[date_col].iloc[0])
                if date_col and len(schedule)
                else None,
                "last_date": str(schedule[date_col].iloc[-1])
                if date_col and len(schedule)
                else None,
            }
        else:
            quality = (
                scan_csv(path, chunksize=chunksize)
                if path.suffix.lower() == ".csv"
                else {"path": relative}
            )
        tick_minutes = quality.pop("_tick_minutes", None)
        bar_minutes = quality.pop("_bar_minutes", None)
        if isinstance(tick_minutes, set):
            minute_indexes[f"tick:{relative}"] = tick_minutes
        if isinstance(bar_minutes, set):
            minute_indexes[f"bar:{relative}"] = bar_minutes
        record = {
            "identity": identity,
            "role": role,
            "path": relative,
            "expected_sha256": expected_hash,
            "observed_sha256": actual_hash,
            "hash_matches_manifest": actual_hash == expected_hash,
            **quality,
            "status": "present_hash_match"
            if actual_hash == expected_hash
            else "present_hash_mismatch",
        }
        records.append(record)
        by_path[relative] = record

    # Coverage is computed from the campaign's stored M1 bars and corresponding
    # bid/ask tick inputs. Missing quote minutes remain visible in the counts.
    coverage: dict[str, Any] = {}
    for role in ("training", "testing"):
        for tick_path, tick_record in (
            (path, record)
            for path, record in by_path.items()
            if path.startswith(f"data/{role}/") and record.get("kind") == "tick"
        ):
            symbol = Path(tick_path).name.split("_")[0]
            tick_minute_set = minute_indexes.get(f"tick:{tick_path}", set())
            m1_path = next(
                (
                    path
                    for path in by_path
                    if path.startswith(f"data/{role}/")
                    and Path(path).name.startswith(f"{symbol}_M1_")
                ),
                None,
            )
            if m1_path is None:
                continue
            bar_minute_set = minute_indexes.get(f"bar:{m1_path}", set())
            covered = tick_minute_set.intersection(bar_minute_set)
            coverage[f"{role}:{symbol}"] = {
                "m1_bar_minutes": len(bar_minute_set),
                "tick_quote_minutes": len(tick_minute_set),
                "m1_minutes_with_at_least_one_tick": len(covered),
                "m1_minutes_without_ticks": len(bar_minute_set - tick_minute_set),
                "coverage_fraction": len(covered) / len(bar_minute_set) if bar_minute_set else None,
                "interpretation": "minute overlap only; no session calendar or within-minute execution chronology implied",
            }

    current_source_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    return {
        "schema": "aalto.current_p6_market_input_audit.v1",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "repository_head": current_source_commit,
        "audit_script_path": Path(__file__).resolve().relative_to(ROOT).as_posix(),
        "audit_script_sha256": sha256_file(Path(__file__).resolve()),
        "campaign_path": campaign_path.relative_to(ROOT).as_posix(),
        "campaign_sha256": sha256_file(campaign_path),
        "campaign_fingerprint": campaign["fingerprint"],
        "runtime": {
            "python": platform.python_version(),
            "pandas": pd.__version__,
            "architecture": platform.machine(),
        },
        "input_count": len(records),
        "input_bytes_scanned": sum(record.get("bytes", 0) for record in records),
        "all_inputs_present": all(record.get("status") != "missing" for record in records),
        "all_input_hashes_match": all(
            record.get("hash_matches_manifest", False) for record in records
        ),
        "inputs": records,
        "m1_tick_minute_coverage": coverage,
        "identity_limits": [
            "Timestamps are reported as source wall-clock values; this scan does not establish the correct timezone or DST interpretation.",
            "Observed gaps are not classified as missing bars without an authoritative instrument schedule.",
            "Minute overlap is not proof of quote availability at an order arrival timestamp.",
            "This scan does not establish data ownership, provider identity, or publication rights.",
            "Files are the exact campaign training/testing bundle inputs; this is not an inventory of every raw file, cache, or outside-repository artifact.",
        ],
        "evidence_role": "current-byte hash and streaming structural-quality audit for the selected P6 campaign inputs; not strategy or licensing evidence",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", type=Path, default=CAMPAIGN)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--chunksize", type=int, default=CHUNK_ROWS)
    args = parser.parse_args()
    output = args.out if args.out.is_absolute() else ROOT / args.out
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing evidence: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    report = build_report(args.campaign, chunksize=args.chunksize)
    report["elapsed_seconds"] = round(time.monotonic() - started, 3)
    write_json_atomic(output, report, default=None)
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "input_count",
                    "input_bytes_scanned",
                    "all_inputs_present",
                    "all_input_hashes_match",
                    "elapsed_seconds",
                )
            },
            indent=2,
        )
    )
    print(output)


if __name__ == "__main__":
    main()
