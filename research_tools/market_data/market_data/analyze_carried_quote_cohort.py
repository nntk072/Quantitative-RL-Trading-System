#!/usr/bin/env python3
"""Link recorded fills using a carried quote side to their position ledgers.

This report measures dependence on the configured local parser's side carry.
It does not replay fills or assign counterfactual prices/PnL when a raw source
row lacks the required bid or ask.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path
from statistics import median
from typing import Any

from artifacts.atomic import write_json_atomic
from configuration.paths import repository_root

ROOT = repository_root(__file__)
DEFAULT_ALIGNMENT = Path(
    "evidence/research/fill_quote_source_alignment/selected_campaign_fill_quote_alignment.json"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _resolve(path: Path, root: Path) -> Path:
    return path if path.is_absolute() else root / path


def _load_positions(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source))
    if not rows or "position_id" not in rows[0]:
        raise ValueError(f"position ledger has no rows or position_id: {path}")
    positions: dict[str, dict[str, str]] = {}
    for row in rows:
        identity = str(row["position_id"])
        if not identity or identity in positions:
            raise ValueError(f"missing or duplicate position_id {identity!r} in {path}")
        positions[identity] = row
    return positions


def _assignment(value: str) -> tuple[str, Path]:
    name, separator, raw_path = value.partition("=")
    if not separator or not name.strip() or not raw_path.strip():
        raise argparse.ArgumentTypeError("expected ARM=positions.csv")
    return name.strip(), Path(raw_path.strip())


def build_report(
    alignment_path: Path,
    position_ledgers: list[tuple[str, Path]],
    *,
    root: Path = ROOT,
) -> dict[str, Any]:
    """Build a hash-linked carried-side event-to-position cohort report."""
    alignment_path = _resolve(alignment_path, root).resolve(strict=True)
    alignment = json.loads(alignment_path.read_text(encoding="utf-8"))
    events = alignment.get("events")
    if not isinstance(events, list) or int(alignment.get("event_count", -1)) != len(events):
        raise ValueError("alignment event count does not match its event ledger")

    arm_inputs: dict[str, dict[str, Any]] = {}
    fills_to_arm: dict[Path, str] = {}
    for arm, raw_position_path in position_ledgers:
        position_identity = _resolve(raw_position_path, root)
        position_path = position_identity.resolve(strict=True)
        fills_identity = position_identity.with_name("fills.csv")
        fills_path = fills_identity.resolve(strict=True)
        if arm in arm_inputs or fills_path in fills_to_arm:
            raise ValueError(f"duplicate arm or fill ledger assignment: {arm}")
        positions = _load_positions(position_path)
        arm_inputs[arm] = {
            "positions_identity": position_identity,
            "positions_path": position_path,
            "fills_identity": fills_identity,
            "fills_path": fills_path,
            "positions": positions,
        }
        fills_to_arm[fills_path] = arm

    carried_by_arm: dict[str, list[dict[str, Any]]] = defaultdict(list)
    event_type_counts: Counter[str] = Counter()
    raw_group_sizes: Counter[str] = Counter()
    ages_ms: list[float] = []
    carried_events: list[dict[str, Any]] = []
    for event in events:
        if not event.get("stable_parser_required_side_carried"):
            continue
        source_value = event.get("event_ledger_source")
        if not source_value:
            raise ValueError("carried event has no source fill ledger")
        source_path = _resolve(Path(str(source_value)), root).resolve()
        mapped_arm = fills_to_arm.get(source_path)
        if mapped_arm is None:
            raise ValueError(f"carried event source is not assigned to an arm: {source_value}")
        group = event.get("timestamp_group") or {}
        side = str(event.get("required_quote_side", "")).lower()
        side_missing_key = "missing_bid_rows" if side == "bid" else "missing_ask_rows"
        if side not in {"bid", "ask"} or int(group.get(side_missing_key, 0)) < 1:
            raise ValueError("carried required side is not missing in its raw timestamp group")
        if not event.get("reported_fill_price_matches_configured_grid_parser_side"):
            raise ValueError("recorded fill does not match the configured-grid parser side")
        age_value = event.get("stable_parser_required_side_age_ms_at_fill_time")
        age_ms = None if age_value is None else float(age_value)
        if age_ms is not None:
            if age_ms < 0.0:
                raise ValueError("carried source-side timestamp is after the fill timestamp")
            ages_ms.append(age_ms)
        position_id = str(event.get("position_id", ""))
        if not position_id:
            raise ValueError("carried fill event has no position_id")
        record = {
            "arm": mapped_arm,
            "event_id": str(event.get("event_id", "")),
            "event_type": str(event.get("event_type", "")),
            "position_id": position_id,
            "event_time_utc": event.get("event_time_utc"),
            "required_quote_side": side,
            "raw_rows_at_timestamp": int(group.get("raw_rows_at_timestamp", 0)),
            "raw_rows_missing_required_side": int(group.get(side_missing_key, 0)),
            "carried_side_source_time_utc": event.get(
                "stable_parser_required_side_source_time_utc"
            ),
            "carried_side_age_ms_at_fill": age_ms,
            "recorded_fill_matches_configured_grid_side": True,
        }
        carried_by_arm[mapped_arm].append(record)
        carried_events.append(record)
        event_type_counts[record["event_type"]] += 1
        raw_group_sizes[str(record["raw_rows_at_timestamp"])] += 1

    recorded_count = int(
        (alignment.get("summary") or {}).get("events_with_stable_parser_carried_required_side", -1)
    )
    if recorded_count != len(carried_events):
        raise ValueError("carried-event count does not reconcile with alignment summary")

    arm_summaries = []
    for arm in sorted(arm_inputs):
        arm_data = arm_inputs[arm]
        events_for_arm = carried_by_arm[arm]
        position_ids = sorted({event["position_id"] for event in events_for_arm})
        positions = arm_data["positions"]
        missing_ids = sorted(set(position_ids) - positions.keys())
        if missing_ids:
            raise ValueError(
                f"carried events do not link to position rows for {arm}: {missing_ids[:5]}"
            )
        cohort = [positions[position_id] for position_id in position_ids]
        pnl_values = [
            Decimal(row["position_net_pnl"])
            for row in cohort
            if row.get("position_net_pnl") not in (None, "")
        ]
        if len(pnl_values) != len(cohort):
            raise ValueError(f"position_net_pnl is missing for a carried-side cohort in {arm}")
        arm_summaries.append(
            {
                "arm": arm,
                "fill_ledger_path": arm_data["fills_identity"].relative_to(root).as_posix(),
                "fill_ledger_sha256": _sha256(arm_data["fills_path"]),
                "position_ledger_path": arm_data["positions_identity"].relative_to(root).as_posix(),
                "position_ledger_sha256": _sha256(arm_data["positions_path"]),
                "positions_in_ledger": len(positions),
                "carried_side_fill_events": len(events_for_arm),
                "event_type_counts": dict(
                    sorted(Counter(e["event_type"] for e in events_for_arm).items())
                ),
                "distinct_positions_with_carried_side_fill": len(position_ids),
                "cohort_position_net_pnl_sum": float(sum(pnl_values, Decimal(0))),
                "cohort_position_net_pnl_mean": (
                    float(sum(pnl_values, Decimal(0)) / len(pnl_values)) if pnl_values else None
                ),
            }
        )

    total_events = len(events)
    return {
        "schema": "qrl.carried_quote_side_cohort.v1",
        "alignment_report_path": alignment_path.relative_to(root.resolve()).as_posix(),
        "alignment_report_sha256": _sha256(alignment_path),
        "alignment_schema_version": alignment.get("schema_version"),
        "campaign_tick_source_path": alignment.get("tick_source_path"),
        "campaign_tick_source_sha256": alignment.get("tick_source_sha256"),
        "alignment_event_count": total_events,
        "carried_required_side_event_count": len(carried_events),
        "carried_required_side_event_fraction": (
            len(carried_events) / total_events if total_events else 0.0
        ),
        "event_type_counts": dict(sorted(event_type_counts.items())),
        "raw_timestamp_group_size_counts": dict(sorted(raw_group_sizes.items())),
        "carried_side_age_ms": {
            "count": len(ages_ms),
            "median": median(ages_ms) if ages_ms else None,
            "maximum": max(ages_ms) if ages_ms else None,
        },
        "arms": arm_summaries,
        "events": sorted(
            carried_events,
            key=lambda event: (event["event_time_utc"] or "", event["arm"], event["event_id"]),
        ),
        "strict_same_row_quote_availability": {
            "events_without_the_required_side_in_the_raw_fill_timestamp_group": len(carried_events),
            "interpretation": (
                "These recorded fills require the configured parser's carried side; under a "
                "strict same-row required-side rule that side is unavailable at the fill timestamp."
            ),
            "counterfactual_prices_or_pnl_replayed": False,
        },
        "interpretation_limits": [
            "The report describes recorded fill events and linked position cohorts; it does not attribute cohort PnL to quote carry.",
            "A strict no-carry rule changes event availability and later account state; no counterfactual execution or PnL was simulated.",
            "Local same-timestamp row order is not treated as authoritative market chronology.",
            "The alignment report's configured timezone and parser behavior are reproduced without external clock or provider claims.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--alignment-report", type=Path, default=ROOT / DEFAULT_ALIGNMENT)
    parser.add_argument("--position-ledger", type=_assignment, action="append", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    output = _resolve(args.out, ROOT)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite evidence: {output}")
    report = build_report(args.alignment_report, args.position_ledger)
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(output, report)
    print(
        f"Wrote {output}: {report['carried_required_side_event_count']} of "
        f"{report['alignment_event_count']} fill events depend on a carried required side"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
