#!/usr/bin/env python3
"""Audit paired quote-coverage sensitivity replays against raw MT5 source events.

The audit is deliberately descriptive. Reconstructed local quotes are not proof
of broker-tape completeness, broker-equivalent fills, or strategy profitability.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, deque
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd
from scripts.research.analysis.evaluation.compare_quote_coverage_sensitivity import (
    compare_frames,
    load_packet,
    validate_paired_manifests,
)

from configuration.configuration_loader import load_config
from configuration.paths import repository_root
from market_data.loading import build_tick_books

ROOT = repository_root(__file__)
DEFAULT_CONFIG = ROOT / "config/research/trade_setup_mtf_reasoning_2m.yaml"
DEFAULT_PROPOSALS = ROOT / "evidence/research/candidate_proposals"
DEFAULT_COVERAGE = ROOT / "evidence/research/tick_quote_coverage"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_packet_checksums(packet: Path) -> None:
    sums = packet / "OUTPUT_SHA256SUMS"
    if not sums.exists():
        raise ValueError(f"missing checksum manifest: {sums}")
    for line in sums.read_text(encoding="utf-8").splitlines():
        expected, filename = line.split(maxsplit=1)
        target = packet / filename.strip()
        if not target.is_file() or sha256(target) != expected:
            raise ValueError(f"checksum mismatch: {target}")


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return cast(
        list[dict[str, Any]], json.loads(frame.to_json(orient="records", date_format="iso"))
    )


def _stratified_outcome_sample(
    frame: pd.DataFrame,
    *,
    rows_per_stratum: int = 5,
) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    sampled = frame.copy()
    event_time = pd.to_datetime(sampled["valid_from"], utc=True, errors="raise")
    sampled = sampled.loc[event_time.dt.year == 2025].copy()
    event_time = pd.to_datetime(sampled["valid_from"], utc=True, errors="raise")
    sampled["cohort"] = np.where(event_time.dt.month <= 6, "early_2025", "late_2025")
    sampled["_event_time"] = event_time
    sampled = sampled.sort_values(
        ["cohort", "entry_type", "_event_time", "outcome_id"],
        kind="stable",
    )
    sampled = (
        sampled.groupby(["cohort", "entry_type"], sort=True, group_keys=False)
        .head(rows_per_stratum)
        .drop(columns=["_event_time"])
    )
    return sampled.reset_index(drop=True)


def _edge_sample(frame: pd.DataFrame, *, rows: int = 20) -> pd.DataFrame:
    if len(frame) <= rows:
        return frame.copy().reset_index(drop=True)
    half = rows // 2
    return pd.concat([frame.head(half), frame.tail(rows - half)], ignore_index=True)


def _group_status(frame: pd.DataFrame, field: str) -> list[dict[str, Any]]:
    grouped = (
        frame.groupby([field, "status"], dropna=False)
        .size()
        .rename("rows")
        .reset_index()
        .sort_values([field, "status"], kind="stable")
    )
    return _records(grouped)


def _normalize_raw_row(
    *,
    row_number: int,
    parts: list[str],
) -> dict[str, Any]:
    return {
        "source_row_number": row_number,
        "date": parts[0],
        "time": parts[1],
        "bid": parts[2] or None,
        "ask": parts[3] or None,
        "last": parts[4] or None,
        "volume": parts[5] or None,
        "flags": parts[6] if len(parts) > 6 else None,
    }


def _combine_edge_examples(
    first: list[dict[str, Any]], last: deque[dict[str, Any]]
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[int] = set()
    for row in [*first, *list(last)]:
        source_row = row.get("source_row_number")
        if source_row is None:
            current = row.get("current_source_row")
            if not isinstance(current, dict) or "source_row_number" not in current:
                raise ValueError("audit example has no stable source-row identity")
            source_row = current["source_row_number"]
        number = int(source_row)
        if number in seen:
            continue
        seen.add(number)
        merged.append(row)
    return merged


def scan_raw_tick_source(
    raw_tick_path: Path,
    *,
    train_end_date_exclusive: str,
    context_minutes: set[str],
) -> dict[str, Any]:
    """Stream raw MT5 export once and retain bounded audit examples."""
    flag_counts: Counter[str] = Counter()
    first_one_sided: list[dict[str, Any]] = []
    last_one_sided: deque[dict[str, Any]] = deque(maxlen=10)
    first_two_sided: list[dict[str, Any]] = []
    last_two_sided: deque[dict[str, Any]] = deque(maxlen=10)
    first_ties: list[dict[str, Any]] = []
    last_ties: deque[dict[str, Any]] = deque(maxlen=10)
    context: dict[str, dict[str, Any]] = {
        minute: {"first": [], "last": deque(maxlen=5), "rows": 0} for minute in context_minutes
    }
    rows = 0
    one_sided_rows = 0
    two_sided_rows = 0
    bid_blank_rows = 0
    ask_blank_rows = 0
    equal_timestamp_adjacent_rows = 0
    previous_timestamp: str | None = None
    previous_row: dict[str, Any] | None = None

    with raw_tick_path.open("r", encoding="utf-8", errors="strict", newline="") as handle:
        header = handle.readline()
        if "<DATE>" not in header or "<TIME>" not in header or "<FLAGS>" not in header:
            raise ValueError("unexpected MT5 raw tick header")
        for row_number, line in enumerate(handle, start=2):
            parts = line.rstrip("\r\n").split("\t")
            if len(parts) < 7:
                raise ValueError(f"malformed raw tick row {row_number}")
            date = parts[0]
            if date >= train_end_date_exclusive:
                break
            rows += 1
            raw = _normalize_raw_row(row_number=row_number, parts=parts)
            flags = parts[6]
            flag_counts[flags] += 1
            bid_text, ask_text = parts[2], parts[3]
            bid_blank_rows += int(not bid_text)
            ask_blank_rows += int(not ask_text)
            one_sided = bool(bid_text) ^ bool(ask_text)
            if one_sided:
                one_sided_rows += 1
                if len(first_one_sided) < 10:
                    first_one_sided.append(raw)
                last_one_sided.append(raw)
            valid_pair = False
            if bid_text and ask_text:
                try:
                    bid = float(bid_text)
                    ask = float(ask_text)
                except ValueError:
                    valid_pair = False
                else:
                    valid_pair = np.isfinite(bid) and np.isfinite(ask) and bid > 0.0 and ask >= bid
            if valid_pair:
                two_sided_rows += 1
                if len(first_two_sided) < 10:
                    first_two_sided.append(raw)
                last_two_sided.append(raw)

            timestamp = f"{parts[0]} {parts[1]}"
            if timestamp == previous_timestamp and previous_row is not None:
                equal_timestamp_adjacent_rows += 1
                pair = {
                    "timestamp": timestamp,
                    "previous_source_row": previous_row,
                    "current_source_row": raw,
                }
                if len(first_ties) < 10:
                    first_ties.append(pair)
                last_ties.append(pair)
            previous_timestamp = timestamp
            previous_row = raw

            minute = f"{parts[0]} {parts[1][:5]}:00"
            slot = context.get(minute)
            if slot is not None:
                slot["rows"] += 1
                if len(slot["first"]) < 5:
                    slot["first"].append(raw)
                slot["last"].append(raw)

    context_records: dict[str, Any] = {}
    for minute, slot in sorted(context.items()):
        context_records[minute] = {
            "rows": int(slot["rows"]),
            "first_rows": slot["first"],
            "last_rows": list(slot["last"]),
        }
    return {
        "training_source_rows_scanned": rows,
        "flag_counts": dict(sorted(flag_counts.items())),
        "one_sided_source_rows": one_sided_rows,
        "valid_two_sided_source_rows": two_sided_rows,
        "bid_blank_rows": bid_blank_rows,
        "ask_blank_rows": ask_blank_rows,
        "equal_timestamp_adjacent_rows": equal_timestamp_adjacent_rows,
        "one_sided_examples": _combine_edge_examples(first_one_sided, last_one_sided),
        "valid_two_sided_examples": _combine_edge_examples(first_two_sided, last_two_sided),
        "equal_timestamp_examples": _combine_edge_examples(first_ties, last_ties),
        "selected_minute_context": context_records,
    }


def _anchor_time(row: pd.Series) -> pd.Timestamp:
    for column in (
        "exit_time_tickbook",
        "fill_time_tickbook",
        "eligible_action_fill_time",
        "valid_from",
    ):
        value = row.get(column)
        if value is not None and not pd.isna(value):
            return pd.Timestamp(value).tz_convert("UTC")
    raise ValueError(f"sample lacks an auditable event time: {row['outcome_id']}")


def _source_minute(timestamp: pd.Timestamp, timezone: str) -> str:
    return (
        timestamp.tz_convert(timezone).tz_localize(None).floor("min").strftime("%Y.%m.%d %H:%M:00")
    )


def tickbook_context(
    *,
    config_path: Path,
    symbol: str,
    samples: pd.DataFrame,
    expected_tickbook_sha256: str,
) -> tuple[dict[str, Any], str]:
    cfg = load_config(config_path=config_path)
    book = build_tick_books(cfg, symbols=[symbol], datasets=["training"]).get(symbol)
    if book is None or len(book) == 0:
        raise ValueError("production training TickBook is unavailable")
    digest = book.content_sha256()
    if digest != expected_tickbook_sha256:
        raise ValueError("production TickBook identity differs from paired replay")
    contexts: dict[str, Any] = {}
    radius_ns = int(pd.Timedelta(seconds=1).value)
    for _, row in samples.iterrows():
        anchor = _anchor_time(row)
        i0 = int(np.searchsorted(book._ts, anchor.value - radius_ns, side="left"))
        i1 = int(np.searchsorted(book._ts, anchor.value + radius_ns, side="right"))
        indices = list(range(i0, min(i1, i0 + 12)))
        contexts[str(row["outcome_id"])] = {
            "anchor_utc": anchor.isoformat(),
            "rows": [
                {
                    "source_order_index": idx,
                    "time": pd.Timestamp(int(book._ts[idx]), unit="ns", tz="UTC").isoformat(),
                    "bid": float(book._bid[idx]),
                    "ask": float(book._ask[idx]),
                }
                for idx in indices
            ],
        }
    return contexts, digest


def build_audit(
    *,
    config_path: Path,
    strict_dir: Path,
    count_checked_dir: Path,
    tickbook_only_dir: Path,
    proposal_dir: Path,
    coverage_dir: Path,
    output_dir: Path,
) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(f"output dir already exists: {output_dir}")
    for packet in (strict_dir, count_checked_dir, tickbook_only_dir, proposal_dir, coverage_dir):
        verify_packet_checksums(packet)

    strict, strict_manifest = load_packet(strict_dir)
    count_checked, count_manifest = load_packet(count_checked_dir)
    tickbook_only, tickbook_manifest = load_packet(tickbook_only_dir)
    validate_paired_manifests(
        strict_manifest, count_manifest, packet_label="reconstructed_count_checked"
    )
    validate_paired_manifests(
        strict_manifest, tickbook_manifest, packet_label="reconstructed_tickbook_only"
    )
    count_comparison = compare_frames(strict, count_checked)
    tickbook_comparison = compare_frames(strict, tickbook_only)

    proposal_manifest_path = proposal_dir / "proposal_ledger_manifest.json"
    proposal_manifest = json.loads(proposal_manifest_path.read_text(encoding="utf-8"))
    proposal_path = proposal_dir / "candidate_proposals.parquet"
    if sha256(proposal_path) != proposal_manifest["outputs"]["candidate_proposals.parquet"]:
        raise ValueError("proposal parquet hash differs from proposal manifest")
    proposals = pd.read_parquet(
        proposal_path,
        columns=[
            "proposal_id",
            "idea_family",
            "source_timeframe",
            "direction",
            "valid_from",
            "entry_type",
            "eligible_action_fill_time",
        ],
    )
    if not proposals["proposal_id"].is_unique:
        raise ValueError("proposal ledger IDs must be unique")

    def joined(frame: pd.DataFrame) -> pd.DataFrame:
        out = frame.merge(proposals, on="proposal_id", how="left", validate="many_to_one")
        if out["entry_type"].isna().any():
            raise ValueError("outcome cannot be joined to proposal metadata")
        out["month"] = pd.to_datetime(out["valid_from"], utc=True).dt.strftime("%Y-%m")
        return out

    strict_joined = joined(strict)
    count_joined = joined(count_checked)
    tickbook_joined = joined(tickbook_only)
    sample_join = strict_joined.merge(
        tickbook_joined[
            [
                "outcome_id",
                "status",
                "fill_time",
                "fill_price",
                "exit_time",
                "exit_price",
                "exit_reason",
                "net_r",
            ]
        ],
        on="outcome_id",
        how="inner",
        validate="one_to_one",
        suffixes=("_strict", "_tickbook"),
    )
    changed = sample_join[
        (sample_join["status_strict"] == "unresolved_data")
        & (sample_join["status_tickbook"] != "unresolved_data")
    ]
    unchanged = sample_join[
        sample_join["status_strict"].isin(["filled_resolved", "unfilled_expired"])
        & (sample_join["status_strict"] == sample_join["status_tickbook"])
    ]
    changed_sample = _stratified_outcome_sample(changed)
    unchanged_sample = _stratified_outcome_sample(unchanged)
    audit_samples = pd.concat(
        [
            changed_sample.assign(sample_class="reclassified_from_strict_unresolved"),
            unchanged_sample.assign(sample_class="strict_completed_unchanged"),
        ],
        ignore_index=True,
    )
    if len(changed_sample) < 20 or len(unchanged_sample) < 20:
        raise ValueError("insufficient stratified changed/unchanged samples for mandatory audit")

    coverage_manifest_path = coverage_dir / "coverage_manifest.json"
    coverage_manifest = json.loads(coverage_manifest_path.read_text(encoding="utf-8"))
    coverage_path = coverage_dir / "minute_quote_coverage.csv"
    if sha256(coverage_path) != coverage_manifest["coverage_csv_sha256"]:
        raise ValueError("strict quote coverage CSV hash differs from manifest")
    coverage = pd.read_csv(coverage_path)
    minute_col = (
        "source_wall_clock" if "source_wall_clock" in coverage.columns else coverage.columns[0]
    )
    coverage[minute_col] = coverage[minute_col].astype(str)
    mismatch = coverage[coverage["source_tick_rows"] != coverage["m1_tickvol"]].sort_values(
        minute_col
    )
    missing = coverage[
        (coverage["source_tick_rows"] == 0) & (coverage["m1_tickvol"] > 0)
    ].sort_values(minute_col)
    if len(mismatch) < 20 or len(missing) < 20:
        raise ValueError("strict coverage does not contain enough mismatch/missing-window examples")

    cfg = load_config(config_path=config_path)
    symbol = str(cfg.data.primary)
    timezone = str(cfg.data.tz)
    dataset = cfg.data.datasets.training
    raw_tick_path = ROOT / str(dataset.raw_dir) / str(dataset.tick_files[symbol])
    raw_relative = str(raw_tick_path.relative_to(ROOT))
    expected_raw_hash = coverage_manifest["input_sha256"].get(raw_relative)
    if expected_raw_hash is None or sha256(raw_tick_path) != expected_raw_hash:
        raise ValueError("raw tick input differs from strict quote-coverage evidence")

    context_minutes = {
        _source_minute(_anchor_time(row), timezone) for _, row in audit_samples.iterrows()
    }
    mismatch_sample = _edge_sample(mismatch, rows=20)
    missing_sample = _edge_sample(missing, rows=20)
    context_minutes.update(
        pd.to_datetime(mismatch_sample[minute_col]).dt.strftime("%Y.%m.%d %H:%M:00").tolist()
    )
    context_minutes.update(
        pd.to_datetime(missing_sample[minute_col]).dt.strftime("%Y.%m.%d %H:%M:00").tolist()
    )
    raw_audit = scan_raw_tick_source(
        raw_tick_path,
        train_end_date_exclusive=(
            pd.Timestamp(str(cfg.data.split.train_end)) + pd.Timedelta(days=1)
        ).strftime("%Y.%m.%d"),
        context_minutes=context_minutes,
    )
    if raw_audit["training_source_rows_scanned"] != int(
        coverage_manifest["raw_tick_rows_in_training_window"]
    ):
        raise ValueError("streamed raw training-row count differs from strict coverage manifest")
    for example_key in (
        "one_sided_examples",
        "valid_two_sided_examples",
        "equal_timestamp_examples",
    ):
        if len(raw_audit[example_key]) < 20:
            raise ValueError(f"raw audit has fewer than 20 {example_key}")

    tick_context, tickbook_digest = tickbook_context(
        config_path=config_path,
        symbol=symbol,
        samples=audit_samples,
        expected_tickbook_sha256=str(strict_manifest["tickbook_sha256"]),
    )
    status_by_profile = {}
    for name, frame in (
        ("strict_raw", strict_joined),
        ("reconstructed_count_checked", count_joined),
        ("reconstructed_tickbook_only", tickbook_joined),
    ):
        status_by_profile[name] = {
            "status_counts": {str(k): int(v) for k, v in frame["status"].value_counts().items()},
            "by_month": _group_status(frame, "month"),
            "by_entry_type": _group_status(frame, "entry_type"),
            "by_idea_family": _group_status(frame, "idea_family"),
        }

    report = {
        "schema_version": "quote-coverage-sensitivity-audit-v1",
        "status": "paired_source_and_replay_audit_complete",
        "broker_equivalence_claim": False,
        "profitability_claim": False,
        "rl_policy_performance_claim": False,
        "estimand": "conditional_fixed_entry_only",
        "paired_comparisons": {
            "reconstructed_count_checked": count_comparison,
            "reconstructed_tickbook_only": tickbook_comparison,
        },
        "status_by_profile": status_by_profile,
        "strict_unresolved_reasons": {
            str(k): int(v)
            for k, v in strict_joined.loc[
                strict_joined["status"] == "unresolved_data", "unresolved_reason"
            ]
            .fillna("<null>")
            .value_counts()
            .items()
        },
        "outcome_samples": {
            "changed": _records(changed_sample),
            "unchanged": _records(unchanged_sample),
        },
        "coverage_mismatch_summary": {
            "raw_gt_m1_tickvol_minutes": int(
                (coverage["source_tick_rows"] > coverage["m1_tickvol"]).sum()
            ),
            "raw_lt_m1_tickvol_minutes": int(
                (coverage["source_tick_rows"] < coverage["m1_tickvol"]).sum()
            ),
            "raw_zero_with_positive_m1_tickvol_minutes": int(
                ((coverage["source_tick_rows"] == 0) & (coverage["m1_tickvol"] > 0)).sum()
            ),
        },
        "coverage_examples": {
            "count_mismatch": _records(mismatch_sample),
            "missing_raw_source_with_positive_m1_tickvol": _records(missing_sample),
        },
        "raw_source_audit": raw_audit,
        "production_tickbook_context": tick_context,
        "input_identity": {
            "config": str(config_path.relative_to(ROOT)),
            "raw_tick_path": raw_relative,
            "raw_tick_sha256": expected_raw_hash,
            "proposal_manifest_sha256": sha256(proposal_manifest_path),
            "proposal_parquet_sha256": sha256(proposal_path),
            "strict_coverage_manifest_sha256": sha256(coverage_manifest_path),
            "strict_coverage_csv_sha256": sha256(coverage_path),
            "tickbook_sha256": tickbook_digest,
            "strict_outcome_manifest_sha256": sha256(strict_dir / "outcome_manifest.json"),
            "strict_outcome_parquet_sha256": sha256(strict_dir / "conditional_outcomes.parquet"),
            "count_checked_manifest_sha256": sha256(count_checked_dir / "outcome_manifest.json"),
            "count_checked_parquet_sha256": sha256(
                count_checked_dir / "conditional_outcomes.parquet"
            ),
            "tickbook_only_manifest_sha256": sha256(tickbook_only_dir / "outcome_manifest.json"),
            "tickbook_only_parquet_sha256": sha256(
                tickbook_only_dir / "conditional_outcomes.parquet"
            ),
            "audit_source_sha256": sha256(Path(__file__)),
        },
        "interpretation_limits": [
            "Stateful reconstruction of one-sided MT5 export rows does not prove broker tape completeness.",
            "M1 tick-volume parity is a diagnostic, not established equivalence to exported quote-event rows.",
            "Conditional candidate brackets are repeated estimands and are not independent policy trades.",
            "The audit does not reproduce broker queue priority, partial fills, rejects, or account-server traces.",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    report_path = output_dir / "audit.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")
    (output_dir / "OUTPUT_SHA256SUMS").write_text(
        f"{sha256(report_path)}  {report_path.name}\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--strict-outcomes", type=Path, required=True)
    parser.add_argument("--count-checked-outcomes", type=Path, required=True)
    parser.add_argument("--tickbook-only-outcomes", type=Path, required=True)
    parser.add_argument("--proposal-dir", type=Path, default=DEFAULT_PROPOSALS)
    parser.add_argument("--coverage-dir", type=Path, default=DEFAULT_COVERAGE)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    def resolve(path: Path) -> Path:
        return path if path.is_absolute() else ROOT / path

    report = build_audit(
        config_path=resolve(args.config),
        strict_dir=resolve(args.strict_outcomes),
        count_checked_dir=resolve(args.count_checked_outcomes),
        tickbook_only_dir=resolve(args.tickbook_only_outcomes),
        proposal_dir=resolve(args.proposal_dir),
        coverage_dir=resolve(args.coverage_dir),
        output_dir=resolve(args.output_dir),
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "audit_sha256": sha256(resolve(args.output_dir) / "audit.json"),
                "strict_unresolved": report["paired_comparisons"]["reconstructed_tickbook_only"][
                    "strict_unresolved"
                ],
                "tickbook_only_unresolved": report["paired_comparisons"][
                    "reconstructed_tickbook_only"
                ]["alternative_unresolved"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
