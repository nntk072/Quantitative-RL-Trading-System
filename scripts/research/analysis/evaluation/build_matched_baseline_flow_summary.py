#!/usr/bin/env python3
"""Summarize verified decision-to-fill denominators for a matched baseline bundle.

The summary keeps each baseline arm separate and reports only rows represented
in its decision trace and fill ledger. It never infers broker order attempts or
accepted orders from selected actions or fills.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from artifacts.atomic import write_json_atomic

ROOT = Path(__file__).resolve().parents[4]
DEFAULT_BUNDLE = Path(
    "evidence/research/matched_setup_baselines/matched_setup_baselines_19770241b07b5b5e"
)
DEFAULT_OUTPUT = Path(
    "evidence/research/pipeline_denominators/current_matched_baseline_flow_summary.json"
)
ARMS = ("always_no_trade", "random_eligible_setup", "structure_priority")


def _sha256(path: Path) -> str:
    """Return the SHA-256 of a file using bounded memory."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


def _manifest_artifacts(manifest: dict[str, Any]) -> dict[str, str]:
    artifacts: dict[str, str] = {}
    for run in manifest.get("runs", []):
        for artifact in run.get("artifacts", []):
            path = str(artifact.get("path", ""))
            digest = str(artifact.get("sha256", ""))
            if path and digest:
                artifacts[path] = digest
    return artifacts


def _verify_artifact(path: Path, relative: str, artifacts: dict[str, str]) -> str:
    expected = artifacts.get(relative)
    if expected is None:
        raise ValueError(f"manifest does not declare artifact: {relative}")
    observed = _sha256(path)
    if observed != expected:
        raise ValueError(f"manifest hash mismatch for {relative}")
    return observed


def _summarize_decisions(path: Path) -> dict[str, Any]:
    required = {
        "decision_id",
        "eligible_trade_setup_count",
        "is_no_trade",
        "trade_setup_candidate_id",
        "entry_rejection_reason",
    }
    rows = 0
    decision_ids: set[str] = set()
    eligible_rows = 0
    trade_candidate_rows = 0
    no_trade_rows = 0
    rejection_reasons: Counter[str] = Counter()
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"decision trace missing columns: {sorted(missing)}")
        for row in reader:
            rows += 1
            decision_id = str(row["decision_id"] or "")
            if not decision_id or decision_id in decision_ids:
                raise ValueError(f"missing or duplicate decision ID in {path}")
            decision_ids.add(decision_id)
            eligible = int(row["eligible_trade_setup_count"] or 0)
            eligible_rows += eligible > 0
            is_no_trade = str(row["is_no_trade"]).strip().lower() in {"true", "1", "yes"}
            no_trade_rows += is_no_trade
            trade_candidate_rows += not is_no_trade and bool(
                str(row["trade_setup_candidate_id"] or "")
            )
            reason = str(row["entry_rejection_reason"] or "").strip()
            if reason:
                rejection_reasons[reason] += 1
    return {
        "decision_rows": rows,
        "unique_decision_ids": len(decision_ids),
        "rows_with_at_least_one_eligible_candidate": int(eligible_rows),
        "rows_selecting_a_trade_candidate": int(trade_candidate_rows),
        "rows_selecting_no_trade": int(no_trade_rows),
        "entry_rejection_rows_by_reason": dict(sorted(rejection_reasons.items())),
        "order_attempt_count": None,
        "order_attempt_count_state": "not_recorded_in_decision_trace",
        "accepted_order_count": None,
        "accepted_order_count_state": "not_recorded_in_decision_trace_or_fill_ledger",
    }


def _summarize_fill_ledger(path: Path, decision_ids: set[str] | None = None) -> dict[str, Any]:
    required = {"type", "decision_id", "position_id", "position_complete"}
    event_types: Counter[str] = Counter()
    decision_ids_with_open: set[str] = set()
    opened_positions: set[str] = set()
    completed_positions: set[str] = set()
    linked_open_rows = 0
    rows = 0
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        missing = required - set(reader.fieldnames or ())
        if not missing and reader.fieldnames == [""]:
            raise ValueError(f"unexpected blank-only ledger header: {path}")
        if missing and path.stat().st_size <= 3 and reader.fieldnames == [""]:
            return {
                "execution_event_rows": 0,
                "execution_event_rows_by_type": {},
                "open_fill_events": 0,
                "unique_opened_positions": 0,
                "unique_positions_with_terminal_close": 0,
                "decision_ids_with_open_fill": 0,
                "open_fill_decision_ids_present_in_decision_trace": 0,
                "closed_position_ids_without_open_fill": [],
                "empty_ledger_reason": "This always-no-trade arm produced no fill events; the writer emitted an empty CSV header.",
            }
        if missing:
            raise ValueError(f"fill ledger missing columns: {sorted(missing)}")
        for row in reader:
            rows += 1
            event_type = str(row["type"] or "<empty>")
            event_types[event_type] += 1
            decision_id = str(row["decision_id"] or "")
            position_id = str(row["position_id"] or "")
            if event_type == "open":
                if not decision_id or not position_id:
                    raise ValueError(f"open event lacks decision or position identity in {path}")
                decision_ids_with_open.add(decision_id)
                opened_positions.add(position_id)
                linked_open_rows += decision_ids is not None and decision_id in decision_ids
            if position_id and str(row["position_complete"]).strip().lower() in {
                "true",
                "1",
                "yes",
            }:
                completed_positions.add(position_id)
    return {
        "execution_event_rows": rows,
        "execution_event_rows_by_type": dict(sorted(event_types.items())),
        "open_fill_events": event_types["open"],
        "unique_opened_positions": len(opened_positions),
        "unique_positions_with_terminal_close": len(completed_positions),
        "decision_ids_with_open_fill": len(decision_ids_with_open),
        "open_fill_decision_ids_present_in_decision_trace": int(linked_open_rows),
        "closed_position_ids_without_open_fill": sorted(completed_positions - opened_positions),
    }


def build_summary(root: Path, bundle: Path) -> dict[str, Any]:
    manifest_path = bundle / "result_manifest.json"
    manifest = _read_object(manifest_path)
    if manifest.get("schema") != "qrl.research_result_manifest.v2":
        raise ValueError("unsupported matched-baseline result manifest schema")
    if manifest.get("manifest_status") != "draft":
        raise ValueError("expected the current draft matched-baseline bundle")
    artifacts = _manifest_artifacts(manifest)
    declared_arms = {Path(str(run.get("run_id", ""))).name for run in manifest.get("runs", [])}
    if declared_arms != set(ARMS):
        raise ValueError(f"unexpected matched-baseline arms: {sorted(declared_arms)}")

    output_arms: dict[str, Any] = {}
    generator_path = Path(__file__).resolve()
    source_hashes = {
        str(manifest_path.relative_to(root)): _sha256(manifest_path),
        str(generator_path.relative_to(root)): _sha256(generator_path),
    }
    for arm in ARMS:
        decision_relative = f"{bundle.name}/{arm}/decisions.csv"
        ledger_relative = f"{bundle.name}/{arm}/trade_fill_event_ledger.csv"
        decision_path = bundle / arm / "decisions.csv"
        ledger_path = bundle / arm / "trade_fill_event_ledger.csv"
        decision_hash = _verify_artifact(decision_path, decision_relative, artifacts)
        ledger_hash = _verify_artifact(ledger_path, ledger_relative, artifacts)
        decision_summary = _summarize_decisions(decision_path)
        decision_ids: set[str] = set()
        with decision_path.open(newline="", encoding="utf-8") as stream:
            for row in csv.DictReader(stream):
                decision_ids.add(str(row["decision_id"]))
        ledger_summary = _summarize_fill_ledger(ledger_path, decision_ids)
        if ledger_summary["open_fill_events"] != ledger_summary["unique_opened_positions"]:
            raise ValueError(f"open-fill/position count mismatch for {arm}")
        if (
            ledger_summary["open_fill_decision_ids_present_in_decision_trace"]
            != ledger_summary["open_fill_events"]
        ):
            raise ValueError(f"open fills do not all link to a decision row for {arm}")
        output_arms[arm] = {
            "decision_trace": {
                "path": decision_relative,
                "sha256": decision_hash,
                **decision_summary,
            },
            "fill_ledger": {
                "path": ledger_relative,
                "sha256": ledger_hash,
                **ledger_summary,
            },
            "interpretation": "Current matched-baseline development-split trace only; not a historical PPO policy flow.",
        }
        source_hashes[decision_relative] = decision_hash
        source_hashes[ledger_relative] = ledger_hash

    return {
        "schema": "qrl.current_matched_baseline_flow_summary.v1",
        "status": "verified_current_baseline_marginals_with_decision_to_open_links",
        "claim_scope": "Three current matched-baseline arms on the local 2025 development split; arms remain separate and are not joined to historical policy or raw-input denominators.",
        "bundle_path": str(bundle.relative_to(root)),
        "bundle_manifest_sha256": source_hashes[str(manifest_path.relative_to(root))],
        "generator_path": str(generator_path.relative_to(root)),
        "generator_sha256": source_hashes[str(generator_path.relative_to(root))],
        "arms": output_arms,
        "unavailable_counts": {
            "broker_order_attempts": None,
            "broker_order_acceptances": None,
            "reason": "The decision traces and fill ledgers contain no order-attempt or accepted-order identity/status fields.",
            "missing_is_zero": False,
        },
        "limitations": [
            "Do not infer attempted or accepted orders from selected actions, entry rejections, or open fills.",
            "Do not combine these arm-level traces with historical A4A/A4B marginals or the raw-market and candidate-census counts as one funnel.",
            "The matched-baseline outcomes are descriptive development evidence, not policy selection or confirmatory OOS evidence.",
        ],
        "source_hashes_sha256": dict(sorted(source_hashes.items())),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-dir", type=Path, default=DEFAULT_BUNDLE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    bundle = args.bundle_dir if args.bundle_dir.is_absolute() else ROOT / args.bundle_dir
    output = args.out if args.out.is_absolute() else ROOT / args.out
    report = build_summary(ROOT, bundle.resolve())
    write_json_atomic(output.resolve(), report)
    print(
        json.dumps(
            {
                "out": str(output.resolve()),
                "status": report["status"],
                "arms": {
                    arm: {
                        "decisions": values["decision_trace"]["decision_rows"],
                        "open_fills": values["fill_ledger"]["open_fill_events"],
                        "positions": values["fill_ledger"]["unique_opened_positions"],
                        "terminal_positions": values["fill_ledger"][
                            "unique_positions_with_terminal_close"
                        ],
                    }
                    for arm, values in report["arms"].items()
                },
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
