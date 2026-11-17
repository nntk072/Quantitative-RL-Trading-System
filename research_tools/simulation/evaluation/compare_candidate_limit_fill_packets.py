#!/usr/bin/env python3
"""Compare paired exact-touch and trade-through candidate outcome packets."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

from configuration.paths import repository_root

ROOT = repository_root(__file__)
REPORT_NAME = "limit_fill_sensitivity.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def compare_limit_fill_frames(
    exact: pd.DataFrame,
    strict: pd.DataFrame,
) -> dict[str, Any]:
    """Compare rows already restricted to paired limit-entry outcomes."""
    required = {"proposal_id", "outcome_id", "status", "net_r"}
    for label, frame in (("exact-touch", exact), ("trade-through", strict)):
        missing = sorted(required - set(frame.columns))
        if missing:
            raise ValueError(f"{label} outcomes are missing columns: {missing}")
        if frame["outcome_id"].isna().any() or frame["outcome_id"].duplicated().any():
            raise ValueError(f"{label} outcomes contain missing or duplicate outcome identities")

    paired = exact.merge(
        strict,
        on="outcome_id",
        how="outer",
        suffixes=("_exact", "_strict"),
        indicator=True,
        validate="one_to_one",
    )
    if not paired["_merge"].eq("both").all():
        raise ValueError("exact-touch and trade-through outcome identities differ")
    if not paired["proposal_id_exact"].equals(paired["proposal_id_strict"]):
        raise ValueError("paired outcomes refer to different candidate proposals")

    transitions = Counter(
        (str(left), str(right))
        for left, right in zip(paired["status_exact"], paired["status_strict"], strict=True)
    )
    resolved = paired.loc[
        paired["status_exact"].eq("filled_resolved") & paired["status_strict"].eq("filled_resolved")
    ].copy()
    exact_net_r = pd.to_numeric(resolved["net_r_exact"], errors="coerce")
    strict_net_r = pd.to_numeric(resolved["net_r_strict"], errors="coerce")
    finite = exact_net_r.map(math.isfinite) & strict_net_r.map(math.isfinite)
    deltas = (strict_net_r[finite] - exact_net_r[finite]).tolist()
    transitions_report = {
        f"{left} -> {right}": count for (left, right), count in sorted(transitions.items())
    }
    return {
        "schema_version": "candidate-limit-fill-sensitivity.v1",
        "status": "paired_outcomes_compared",
        "paired_limit_outcome_count": len(paired),
        "exact_touch_status_counts": dict(sorted(Counter(exact["status"].astype(str)).items())),
        "trade_through_status_counts": dict(sorted(Counter(strict["status"].astype(str)).items())),
        "status_transitions": transitions_report,
        "both_resolved_count": int(finite.sum()),
        "strict_minus_exact_net_r": {
            "mean": float(sum(deltas) / len(deltas)) if deltas else None,
            "median": float(pd.Series(deltas).median()) if deltas else None,
            "minimum": min(deltas) if deltas else None,
            "maximum": max(deltas) if deltas else None,
        },
        "policy_value_claim": False,
        "uncertainty_claim": "not_estimated",
        "interpretation": (
            "Conditional fixed-entry execution sensitivity only; these paired rows "
            "do not include policy redecision, account risk, payouts, or selection inference."
        ),
    }


def _packet_rows(packet: Path, proposals: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    manifest_path = packet / "outcome_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "training_conditional_outcomes_with_coverage_dispositions":
        raise ValueError(f"{packet} is not a complete candidate outcome packet")
    for line in (packet / "OUTPUT_SHA256SUMS").read_text(encoding="utf-8").splitlines():
        expected, name = line.split(maxsplit=1)
        if _sha256(packet / name.strip()) != expected:
            raise ValueError(f"packet checksum mismatch: {packet / name.strip()}")
    parquet_path = packet / "conditional_outcomes.parquet"
    if manifest["output_sha256"]["conditional_outcomes.parquet"] != _sha256(parquet_path):
        raise ValueError(f"manifest output hash mismatch: {parquet_path}")
    execution = manifest.get("execution_parameters", {})
    assumption = execution.get("limit_fill_assumption")
    if assumption not in {"exact_touch", "strict_trade_through"}:
        raise ValueError(f"packet has unsupported limit fill assumption: {assumption!r}")
    rows = pd.read_parquet(parquet_path).merge(
        proposals,
        on="proposal_id",
        how="left",
        validate="many_to_one",
    )
    if rows["entry_type"].isna().any():
        raise ValueError(f"{packet} contains unknown proposal identities")
    return rows.loc[rows["entry_type"].eq("limit")].copy(), manifest


def compare_packets(exact_dir: Path, strict_dir: Path, proposal_dir: Path) -> dict[str, Any]:
    """Validate packet pairing and compare all limit-entry outcome rows."""
    exact_manifest = json.loads((exact_dir / "outcome_manifest.json").read_text(encoding="utf-8"))
    strict_manifest = json.loads((strict_dir / "outcome_manifest.json").read_text(encoding="utf-8"))
    proposal_manifest_path = proposal_dir / "proposal_ledger_manifest.json"
    proposal_path = proposal_dir / "candidate_proposals.parquet"
    if _sha256(proposal_manifest_path) != exact_manifest.get("proposal_manifest_sha256"):
        raise ValueError("exact packet references a different proposal manifest")
    if _sha256(proposal_path) != exact_manifest.get("proposal_parquet_sha256"):
        raise ValueError("exact packet references a different proposal parquet")
    if exact_manifest["execution_parameters"].get("limit_fill_assumption") != "exact_touch":
        raise ValueError("exact packet does not declare exact-touch fills")
    if (
        strict_manifest["execution_parameters"].get("limit_fill_assumption")
        != "strict_trade_through"
    ):
        raise ValueError("strict packet does not declare trade-through fills")
    if exact_manifest["execution_parameters"].get("limit_require_trade_through") is not False:
        raise ValueError("exact packet does not disable the trade-through requirement")
    if strict_manifest["execution_parameters"].get("limit_require_trade_through") is not True:
        raise ValueError("strict packet does not enable the trade-through requirement")
    for key in (
        "proposal_manifest_sha256",
        "proposal_parquet_sha256",
        "quote_coverage_manifest_sha256",
        "local_data_manifest_sha256",
        "tickbook_sha256",
        "training_cutoff_utc_exclusive",
        "source_sha256",
    ):
        if exact_manifest.get(key) != strict_manifest.get(key):
            raise ValueError(f"packets differ outside the limit fill assumption: {key}")
    exact_execution = dict(exact_manifest["execution_parameters"])
    strict_execution = dict(strict_manifest["execution_parameters"])
    exact_execution.pop("limit_fill_assumption", None)
    strict_execution.pop("limit_fill_assumption", None)
    exact_execution.pop("limit_require_trade_through", None)
    strict_execution.pop("limit_require_trade_through", None)
    if exact_execution != strict_execution:
        raise ValueError("packets use different execution parameters beyond the fill rule")

    proposals = pd.read_parquet(proposal_path)[["proposal_id", "entry_type"]]
    exact_rows, _ = _packet_rows(exact_dir, proposals)
    strict_rows, _ = _packet_rows(strict_dir, proposals)
    report = compare_limit_fill_frames(exact_rows, strict_rows)
    report["packet_provenance"] = {
        "exact_touch_manifest_sha256": _sha256(exact_dir / "outcome_manifest.json"),
        "trade_through_manifest_sha256": _sha256(strict_dir / "outcome_manifest.json"),
        "proposal_manifest_sha256": exact_manifest["proposal_manifest_sha256"],
        "execution_parameters_match_except_limit_fill_rule": True,
        "other_run_provenance_verified": True,
    }
    script_path = Path(__file__).resolve()
    report["comparator_source"] = {
        "path": str(script_path.relative_to(ROOT)),
        "sha256": _sha256(script_path),
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--exact-dir", type=Path, default=ROOT / "evidence/research/candidate_outcomes"
    )
    parser.add_argument(
        "--strict-dir",
        type=Path,
        default=ROOT / "evidence/research/candidate_outcomes_trade_through",
    )
    parser.add_argument(
        "--proposal-dir", type=Path, default=ROOT / "evidence/research/candidate_proposals"
    )
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args()
    report = compare_packets(args.exact_dir, args.strict_dir, args.proposal_dir)
    report_path = args.report or (args.exact_dir / REPORT_NAME)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8"
    )
    checksum_path = report_path.parent / "OUTPUT_SHA256SUMS"
    prior = (
        [
            line
            for line in checksum_path.read_text(encoding="utf-8").splitlines()
            if line.split(maxsplit=1)[-1].strip() != report_path.name
        ]
        if checksum_path.exists()
        else []
    )
    prior.append(f"{_sha256(report_path)}  {report_path.name}")
    checksum_path.write_text("\n".join(sorted(prior)) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
