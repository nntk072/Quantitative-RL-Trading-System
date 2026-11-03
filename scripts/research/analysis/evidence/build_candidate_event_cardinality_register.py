#!/usr/bin/env python3
"""Reconcile configured candidate identities with existing producer ledgers.

This register deliberately keeps producer events, scalar feature pulses,
candidate-scoped identities, and downstream actions in separate units. It does
not infer a ground-truth logical-event count from feature outputs.
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from features.context.trade_setup_candidates import (  # noqa: E402
    TRADE_SETUP_EVENT_IDENTITY_VERSION,
    trade_setup_candidate_event_time_fields,
)

OUT = ROOT / "evidence/research/candidate_event_cardinality"

INPUTS = [
    "evidence/research/trade_setup_opportunity_census/candidate_event_identity_summary.csv",
    "evidence/research/trade_setup_opportunity_census/candidate_source_time_tuple_clusters.csv",
    "evidence/research/ifvg_zone_event_ledger/ifvg_zone_event_ledger.csv",
    "evidence/research/ifvg_zone_event_ledger/event_ledger.json",
    "evidence/research/po3_setup_lifecycle/setup_lifecycle_ledger.csv",
    "evidence/research/po3_setup_lifecycle/setup_lifecycle_summary.json",
    "evidence/research/po3_setup_lifecycle/event_ledger.json",
    "evidence/research/standard_deviation_swing_legs/swing_leg_eligibility_ledger.csv",
    "evidence/research/standard_deviation_swing_legs/cross_timeframe_swing_leg_key_groups.csv",
    "evidence/research/standard_deviation_swing_legs/ledger.json",
    "evidence/research/model_observation_and_action_semantics/decision_trace_availability_inventory.json",
    "features/context/trade_setup_candidates.py",
    "decisioning/trade_setup.py",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    if not all(isinstance(key, str) for key in value):
        raise ValueError(f"expected string JSON object keys: {path}")
    return cast(dict[str, Any], value)


def build_identity_contract(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Materialize the production source-time key contract for all categories."""
    result: list[dict[str, str]] = []
    for row in rows:
        candidate_id = int(row["candidate_id"])
        time_fields = [
            {"field": field, "scale_to_nanoseconds": scale}
            for field, scale in trade_setup_candidate_event_time_fields(candidate_id)
        ]
        result.append(
            {
                "candidate_id": str(candidate_id),
                "idea": row["idea"],
                "setup_timeframe": row["timeframe"],
                "direction": row["direction"],
                "support_status": row["support_status"],
                "identity_version": TRADE_SETUP_EVENT_IDENTITY_VERSION,
                "required_source_time_fields": json.dumps(time_fields, sort_keys=True),
                "serialized_key_semantics": (
                    "idea + setup timeframe + numeric direction + ordered field=time_ns values"
                ),
                "numeric_candidate_id_in_serialized_key": "false",
                "deduplication_scope": (
                    "candidate category only; no cross-category or cross-timeframe merge"
                ),
                "active_candidate_rows": row["active_m1_rows"],
                "candidate_scoped_source_time_ids": row["distinct_source_event_ids"],
                "identified_eligibility_episode_starts": row["identified_identity_episode_starts"],
                "adjacent_identity_changes": row["adjacent_active_identity_changes"],
                "missing_source_time_rows": row["missing_source_event_time_rows"],
                "identity_coverage_fraction": row["identity_coverage_fraction"],
                "measurement_scope": "selected local training profile",
            }
        )
    if [int(row["candidate_id"]) for row in rows] != list(range(1, 109)):
        raise ValueError("Expected one source-time contract for every non-NO_TRADE category")
    return result


def verify_packet_checksums(relative_csv: str) -> list[str]:
    packet = (ROOT / relative_csv).parent
    checksum_path = packet / "OUTPUT_SHA256SUMS"
    if not checksum_path.exists():
        raise FileNotFoundError(f"Missing packet checksum file: {checksum_path}")
    verified: list[str] = []
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        expected, name = line.split(maxsplit=1)
        path = packet / name.strip()
        actual = sha256(path)
        if actual != expected:
            raise ValueError(f"Checksum mismatch: {path}")
        verified.append(path.relative_to(ROOT).as_posix())
    return verified


def register_row(
    layer: str,
    family: str,
    timeframe: str,
    measure: str,
    count: int | str,
    unit: str,
    deduplication: str,
    interpretation: str,
    source: str,
) -> dict[str, str]:
    return {
        "evidence_layer": layer,
        "family": family,
        "timeframe_scope": timeframe,
        "measure": measure,
        "count": str(count),
        "unit": unit,
        "deduplication_or_overlap": deduplication,
        "interpretation": interpretation,
        "source_path": source,
    }


def main() -> None:
    verified_packet_files: set[str] = set()
    for relative in INPUTS:
        if not (ROOT / relative).is_file():
            raise FileNotFoundError(ROOT / relative)
    for relative in INPUTS:
        if relative.endswith(".csv"):
            verified_packet_files.update(verify_packet_checksums(relative))

    identity_path = ROOT / INPUTS[0]
    identity_rows = read_csv(identity_path)
    identity_contract = build_identity_contract(identity_rows)
    supported = [row for row in identity_rows if row["support_status"] == "supported"]
    unsupported = [row for row in identity_rows if row["support_status"] == "unsupported_by_config"]
    family_totals: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "candidate_rows": 0,
            "candidate_scoped_ids": 0,
            "missing_source_times": 0,
            "identity_episode_starts": 0,
            "adjacent_identity_changes": 0,
            "candidate_tuples": 0,
        }
    )
    for row in supported:
        totals = family_totals[row["idea"]]
        totals["candidate_rows"] += int(row["active_m1_rows"])
        totals["candidate_scoped_ids"] += int(row["distinct_source_event_ids"])
        totals["missing_source_times"] += int(row["missing_source_event_time_rows"])
        totals["identity_episode_starts"] += int(row["identified_identity_episode_starts"])
        totals["adjacent_identity_changes"] += int(row["adjacent_active_identity_changes"])
        totals["candidate_tuples"] += 1

    total_active_rows = sum(int(row["active_m1_rows"]) for row in supported)
    total_candidate_ids = sum(int(row["distinct_source_event_ids"]) for row in supported)
    total_missing_times = sum(int(row["missing_source_event_time_rows"]) for row in supported)
    if (
        len(supported),
        len(unsupported),
        total_active_rows,
        total_candidate_ids,
        total_missing_times,
    ) != (
        24,
        84,
        488_008,
        109_391,
        0,
    ):
        raise ValueError("Candidate identity census totals do not match its documented scope")

    register: list[dict[str, str]] = []
    identity_source = INPUTS[0]
    for family, totals in sorted(family_totals.items()):
        register.append(
            register_row(
                "candidate_identity",
                family,
                "configured timeframes",
                "active_candidate_row_occurrences",
                totals["candidate_rows"],
                "candidate-row occurrences",
                "Rows can overlap in time and across candidates/timeframes.",
                "Eligibility context only; not proposals, decisions, trades, or unique market events.",
                identity_source,
            )
        )
        register.append(
            register_row(
                "eligibility_episode",
                family,
                "configured timeframes",
                "identified_identity_episode_starts",
                totals["identity_episode_starts"],
                "candidate identity episodes",
                "Counts separated active spans for the same candidate-scoped source-time key.",
                "Repeated eligibility spans are not additional source objects, policy actions, or trades.",
                identity_source,
            )
        )
        register.append(
            register_row(
                "eligibility_episode",
                family,
                "configured timeframes",
                "adjacent_active_identity_changes",
                totals["adjacent_identity_changes"],
                "identity transitions",
                "Adjacent active rows with a changed candidate-scoped source-time key.",
                "Transition count is descriptive and is not event cardinality.",
                identity_source,
            )
        )
        register.append(
            register_row(
                "candidate_identity",
                family,
                "configured timeframes",
                "candidate_scoped_source_time_ids_summed",
                totals["candidate_scoped_ids"],
                "candidate-scoped IDs",
                "Sum across supported candidate tuples; IDs are not globally deduplicated.",
                "Source-time identity coverage, not logical-event cardinality.",
                identity_source,
            )
        )

    po3_path = "evidence/research/po3_setup_lifecycle/event_ledger.json"
    po3 = read_json(ROOT / po3_path)
    po3_counts = po3["counts"]
    register.extend(
        [
            register_row(
                "producer_lifecycle",
                "po3",
                "M1",
                "accepted_setup_sequences",
                po3_counts["accepted_setup_sequence_count"],
                "producer setup sequences",
                "Sequence unit from the configured producer; not a policy event.",
                "Diagnostic lifecycle count for the configured M1 PO3 state path.",
                po3_path,
            ),
            register_row(
                "producer_lifecycle",
                "po3",
                "M1",
                "conflicting_same_bar_sweeps",
                po3_counts["conflicting_same_bar_sweep_count"],
                "conflict rows",
                "Separate from accepted setup sequences.",
                "Producer conflict diagnostic; not accepted setups or actions.",
                po3_path,
            ),
        ]
    )

    swing_path = "evidence/research/standard_deviation_swing_legs/ledger.json"
    swing = read_json(ROOT / swing_path)
    swing_counts = swing["counts"]["totals"]
    register.extend(
        [
            register_row(
                "producer_projection",
                "standard_deviation",
                "M1, M3, M5, M10, M15, M30, H1, H4, D1",
                "latest_confirmed_source_leg_projections",
                swing_counts["source_leg_projection_rows"],
                "timeframe/direction/source-leg projections",
                "One latest confirmed source-leg projection per ledger row.",
                "The producer exposes only its latest confirmed swing pair; overlapping latent legs are absent.",
                swing_path,
            ),
            register_row(
                "producer_projection",
                "standard_deviation",
                "M1, M3, M5, M10, M15, M30, H1, H4, D1",
                "projections_with_retracement_eligibility",
                swing_counts["eligible_source_legs"],
                "source-leg projections",
                "Subset of projection rows.",
                "Eligibility support only; not separate orders or trades.",
                swing_path,
            ),
            register_row(
                "source_key_linkage",
                "standard_deviation",
                "cross-timeframe",
                "exact_source_key_groups_represented_on_multiple_timeframes",
                swing_counts["tuple_groups_on_multiple_timeframes"],
                "source-key groups",
                "Exact ordered pivot-time key matches; not a shared-event ontology.",
                "Descriptive cross-timeframe key linkage only.",
                swing_path,
            ),
        ]
    )

    ifvg_csv = "evidence/research/ifvg_zone_event_ledger/ifvg_zone_event_ledger.csv"
    ifvg_rows = read_csv(ROOT / ifvg_csv)
    selected_ifvg = sum(row["selected_by_scalar"].lower() == "true" for row in ifvg_rows)
    suppressed_ifvg = len(ifvg_rows) - selected_ifvg
    if (len(ifvg_rows), selected_ifvg, suppressed_ifvg) != (72_561, 56_349, 16_212):
        raise ValueError("IFVG per-zone ledger counts do not match its documented scope")
    register.extend(
        [
            register_row(
                "per_zone_detector",
                "ifvg",
                "M1",
                "per_zone_confirmations",
                len(ifvg_rows),
                "source-zone confirmations",
                "One row per source FVG zone confirmation.",
                "Detector confirmations, not logical setups, proposals, orders, or trades.",
                ifvg_csv,
            ),
            register_row(
                "scalar_projection",
                "ifvg",
                "M1",
                "confirmations_selected_by_scalar_feature",
                selected_ifvg,
                "scalar confirmation pulses",
                "Newest matching zone selected by the scalar feature for a row/direction.",
                "Existing feature projection count; not policy action count.",
                ifvg_csv,
            ),
            register_row(
                "scalar_projection",
                "ifvg",
                "M1",
                "per_zone_confirmations_not_selected_by_scalar",
                suppressed_ifvg,
                "source-zone confirmations",
                "Difference between per-zone confirmations and selected scalar rows.",
                "Overlapping confirmations suppressed by scalar projection; not extra trades.",
                ifvg_csv,
            ),
        ]
    )

    trace_path = "evidence/research/model_observation_and_action_semantics/decision_trace_availability_inventory.json"
    trace = read_json(ROOT / trace_path)
    register.extend(
        [
            register_row(
                "historical_traceability",
                "all supported families",
                "scanned artifact roots",
                "per_decision_setup_trace",
                trace["per_decision_setup_trace_status"],
                "availability status",
                "276 recognized artifacts under four supplied roots; directory symlinks are not followed.",
                "No qualifying historical setup-decision trace was found under the supplied physical roots; this is not global absence proof.",
                trace_path,
            ),
            register_row(
                "historical_traceability",
                "all supported families",
                "scanned artifact roots",
                "per_decision_price_geometry_trace",
                trace["per_decision_price_geometry_trace_status"],
                "availability status",
                "276 recognized artifacts under four supplied roots; directory symlinks are not followed.",
                "No qualifying historical price-geometry trace was found under the supplied physical roots; this is not global absence proof.",
                trace_path,
            ),
        ]
    )

    OUT.mkdir(parents=True, exist_ok=True)
    csv_path = OUT / "cardinality_register.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(register[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(register)

    identity_contract_path = OUT / "candidate_identity_contract.csv"
    with identity_contract_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(identity_contract[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(identity_contract)

    provenance = {
        "schema_version": 1,
        "scope": "Configured local training profile; current evidence packets only.",
        "active_candidate_profile": {
            "supported_candidate_tuples": len(supported),
            "unsupported_candidate_tuples": len(unsupported),
            "active_candidate_row_occurrences": total_active_rows,
            "candidate_scoped_source_time_ids_summed": total_candidate_ids,
            "missing_source_time_rows": total_missing_times,
            "supported_families": {name: values for name, values in sorted(family_totals.items())},
        },
        "logical_event_count": "not_established; no ground-truth event ontology is available",
        "candidate_identity_contract": {
            "version": TRADE_SETUP_EVENT_IDENTITY_VERSION,
            "path": identity_contract_path.relative_to(ROOT).as_posix(),
            "sha256": sha256(identity_contract_path),
            "candidate_categories": len(identity_contract),
            "semantics": "candidate-scoped ordered source-time keys from the production identity function",
            "global_source_object_deduplication": False,
        },
        "historical_candidate_to_action_linkage": trace["per_decision_setup_trace_status"],
        "historical_price_geometry_trace": trace["per_decision_price_geometry_trace_status"],
        "input_sha256": {relative: sha256(ROOT / relative) for relative in INPUTS},
        "verified_packet_files": sorted(verified_packet_files),
        "generator": "scripts/research/analysis/evidence/build_candidate_event_cardinality_register.py",
        "generator_sha256": sha256(Path(__file__).resolve()),
        "limitations": [
            "Producer event counts, feature scalar pulses, candidate identities, and eligibility contexts use different units and are not summed into one event count.",
            "The generated v3 identity contract records exact source-time fields and scales for each candidate category; it does not assert that candidate-scoped IDs equal globally unique market source objects.",
            "Candidate-scoped IDs can refer to the same source-time tuple across candidates or timeframes.",
            "The inventory found no qualifying historical per-decision setup or price-geometry traces in its scanned roots; absence is scoped to those roots and recognized filenames.",
            "The broad inventory does not follow directory symlinks; artifacts reachable only through symlink directories outside the supplied physical roots are not included.",
            "Historical trades and fills are not linked back to candidate proposals by this register.",
            "All counts are descriptive local training-profile evidence, not economic performance or holdout evidence.",
        ],
    }
    provenance_path = OUT / "cardinality_register.json"
    provenance_path.write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    readme = """# Candidate event cardinality register

This packet reconciles existing configured-profile producer ledgers, scalar
feature projections, candidate-scoped source-time identities, and the scoped
historical trace search. It deliberately preserves their different counting
units. It does **not** estimate one ground-truth logical-event count.

The selected profile supports 24 candidate tuples and disables 84. Across the
24 supported tuples, the identity census has 488,008 active candidate-row
occurrences and 109,391 candidate-scoped source-time IDs, with no missing
required source times. The new `candidate_identity_contract.csv` is generated
from the production v3 identity function and gives the ordered source-time
fields and unit scales for all 108 categories, plus support and episode counts.
Those IDs remain scoped to candidate category; the packet does not infer one
global market-event ontology or deduplicate objects across candidate families
and timeframes.

The register CSV now exposes identity episode starts and adjacent identity
changes alongside candidate rows and IDs. It also reports PO3 producer
sequences, standard-deviation source-leg projections, and IFVG per-zone
confirmations separately from their scalar projections. None is a count of
policy proposals, actions, orders, fills, or trades.

The scoped 276-artifact inventory found no qualifying historical per-decision
setup or price-geometry trace in its scanned roots. That is bounded absence
evidence, not global proof. The scan does not follow directory symlinks and
records the supplied physical roots only. Current rollout telemetry supports future
decision-to-open correlation; it cannot reconstruct missing historical links.

## Files

- `cardinality_register.csv`: each measure, unit, overlap rule, interpretation,
  and source path.
- `candidate_identity_contract.csv`: production source-time key fields, scales,
  and selected-profile coverage for each of the 108 categories.
- `cardinality_register.json`: input hashes, packet checksum verification,
  scope totals, and explicit unresolved counts.
- `OUTPUT_SHA256SUMS`: hashes for this packet and its reusable generator.

## Reproduction

Run from the repository root on a compatible project environment:

```bash
.venv/bin/python scripts/research/analysis/evidence/build_candidate_event_cardinality_register.py
```

The generator verifies the source packets' `OUTPUT_SHA256SUMS` files before
reading their ledgers and refuses to produce the register if documented census
totals or the IFVG scalar/per-zone reconciliation do not match.
"""
    (OUT / "README.md").write_text(readme, encoding="utf-8")

    output_files = [
        "README.md",
        "cardinality_register.csv",
        "candidate_identity_contract.csv",
        "cardinality_register.json",
    ]
    output_prefix = OUT.relative_to(ROOT).as_posix()
    sums = [f"{sha256(OUT / name)}  {output_prefix}/{name}" for name in output_files]
    generator_relative = (
        "scripts/research/analysis/evidence/build_candidate_event_cardinality_register.py"
    )
    sums.append(f"{sha256(ROOT / generator_relative)}  {generator_relative}")
    (OUT / "OUTPUT_SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
    print(f"wrote {len(register)} register rows to {csv_path.relative_to(ROOT)}")
    print(
        f"supported candidates={len(supported)} unsupported={len(unsupported)} active_rows={total_active_rows} candidate_scoped_ids={total_candidate_ids}"
    )
    print(f"ifvg per_zone={len(ifvg_rows)} scalar={selected_ifvg} suppressed={suppressed_ifvg}")
    print(
        f"candidate identity contract rows={len(identity_contract)} version={TRADE_SETUP_EVENT_IDENTITY_VERSION}"
    )
    print(f"verified source packet files={len(verified_packet_files)}")


if __name__ == "__main__":
    main()
