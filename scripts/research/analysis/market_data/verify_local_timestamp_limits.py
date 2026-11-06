#!/usr/bin/env python3
"""Verify the local timestamp and quote-chronology evidence packet."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
PACKET = (
    ROOT / "evidence/research/market_data_quality/local_timestamp_and_quote_chronology_limits.json"
)
PROFILE = ROOT / "evidence/research/market_data_quality/local_market_data_quality.json"
CARRY = ROOT / "evidence/research/market_data_quality/tickbook_carry_forward_audit.json"
CONFIG = ROOT / "config/base/default.yaml"
TICKS = ROOT / "market_data/loading/ticks.py"
SESSION_LEVELS = ROOT / "features/context/session_levels.py"


def _read_json(path: Path) -> dict[str, Any]:
    """Read a JSON object and reject non-object roots."""
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _sha256(path: Path) -> str:
    """Hash one file without loading its contents into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify() -> dict[str, Any]:
    """Cross-check packet counts and source identities against canonical reports."""
    packet = _read_json(PACKET)
    profile = _read_json(PROFILE)
    carry = _read_json(CARRY)
    if packet.get("schema") != "qrl.local_timestamp_and_quote_chronology_limits.v1":
        raise ValueError("unexpected timestamp-limit packet schema")

    for identity in packet["source_identities"]:
        path = ROOT / identity["path"]
        if _sha256(path) != identity["sha256"]:
            raise ValueError(f"source identity mismatch: {identity['path']}")

    ticks = [item for item in profile["inputs"] if item.get("kind") == "tick"]
    if len(ticks) != 4 or any(not item.get("hash_matches_manifest") for item in ticks):
        raise ValueError("expected four current hash-verified tick inputs")
    observed = {
        "input_rows": sum(int(item["row_count"]) for item in ticks),
        "timestamp_parse_failures": sum(int(item["timestamp_parse_failures"]) for item in ticks),
        "adjacent_timestamp_reversals": sum(
            int(item["out_of_order_adjacent_timestamps"]) for item in ticks
        ),
        "adjacent_timestamp_tie_groups": sum(
            int(item["duplicate_adjacent_timestamps"]) for item in ticks
        ),
        "tie_groups_with_changed_quote": sum(
            int(item["same_timestamp_changed_bid_ask_pairs"]) for item in ticks
        ),
        "tie_groups_with_missing_quote": sum(
            int(item["same_timestamp_pairs_with_missing_quote"]) for item in ticks
        ),
        "tie_groups_with_identical_quote": sum(
            int(item["same_timestamp_identical_bid_ask_pairs"]) for item in ticks
        ),
        "raw_rows_with_missing_or_nonpositive_quote_side": sum(
            int(item["missing_or_nonfinite_bid_rows"]) + int(item["missing_or_nonfinite_ask_rows"])
            for item in ticks
        ),
    }
    declared = packet["observed_local_quote_facts"]
    for name, value in observed.items():
        if int(declared[name]) != value:
            raise ValueError(f"packet count mismatch for {name}: {declared[name]} != {value}")

    totals = carry["totals"]
    carry_expectations = {
        "source_rows_read": int(declared["input_rows"]),
        "rows_retained_after_carry": int(declared["input_rows"]),
        "rows_dropped_for_unavailable_side_after_carry": 0,
        "rows_dropped_for_crossed_pair_after_carry": 0,
        "rows_with_any_side_carried_into_valid_quote": int(
            declared["raw_rows_with_missing_or_nonpositive_quote_side"]
        ),
    }
    for name, expected in carry_expectations.items():
        actual = int(totals[name])
        if actual != expected:
            raise ValueError(f"carry-forward mismatch for {name}: {actual} != {expected}")

    config_text = CONFIG.read_text(encoding="utf-8")
    tick_text = TICKS.read_text(encoding="utf-8")
    session_text = SESSION_LEVELS.read_text(encoding="utf-8")
    for text, marker, path in (
        (config_text, 'tz: "Etc/GMT-3"', CONFIG),
        (config_text, 'timestamp_clock: "ftmo_mt5_us_dst"', CONFIG),
        (tick_text, "dt = dt.tz_localize(tz)", TICKS),
        (tick_text, "stable source-row order", TICKS),
        (
            session_text,
            'tz_localize("America/New_York", ambiguous="raise", nonexistent="raise")',
            SESSION_LEVELS,
        ),
    ):
        if marker not in text:
            raise ValueError(f"configured behavior marker missing from {path}: {marker}")

    return {
        "status": "verified",
        "tick_inputs": len(ticks),
        **observed,
        "source_identities_verified": len(packet["source_identities"]),
        "carry_forward_rows_retained": int(totals["rows_retained_after_carry"]),
        "carry_forward_rows_dropped": int(
            totals["rows_dropped_for_unavailable_side_after_carry"]
            + totals["rows_dropped_for_crossed_pair_after_carry"]
        ),
    }


def main() -> int:
    print(json.dumps(verify(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
