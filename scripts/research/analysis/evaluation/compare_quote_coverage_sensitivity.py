#!/usr/bin/env python3
"""Compare strict and reconstructed quote-coverage conditional replay packets.

This is *not* a performance evaluation: conditional brackets reuse proposals,
and resolved-only returns are selection-biased. Reconstructed quote availability
is neither evidence of full source-tape coverage nor MT5 broker fill parity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from configuration.paths import repository_root

ROOT = repository_root(__file__)
FIELDS = (
    "outcome_id",
    "status",
    "unresolved_reason",
    "fill_time",
    "fill_price",
    "exit_time",
    "exit_price",
    "exit_reason",
    "net_r",
)
IDENTICAL_INPUTS = (
    "proposal_manifest_sha256",
    "proposal_parquet_sha256",
    "tickbook_sha256",
    "proposal_rows_replayed",
    "conditional_outcome_rows",
    "execution_parameters",
    "training_cutoff_utc_exclusive",
    "estimand",
    "account_state_evaluated",
    "config",
    "resolved_config_sha256",
    "proposal_resolved_config_sha256",
    "config_relationship",
    "local_data_manifest_sha256",
    "source_commit",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_packet(packet_dir: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    manifest_path = packet_dir / "outcome_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "training_conditional_outcomes_with_coverage_dispositions":
        raise ValueError(f"incomplete pilot or noncanonical replay: {packet_dir}")
    data_path = packet_dir / "conditional_outcomes.parquet"
    if sha256(data_path) != manifest["output_sha256"][data_path.name]:
        raise ValueError(f"conditional replay hash mismatch: {data_path}")
    frame = pd.read_parquet(data_path, columns=list(FIELDS))
    if len(frame) != manifest["conditional_outcome_rows"] or not frame["outcome_id"].is_unique:
        raise ValueError("outcome row count or IDs do not match the replay manifest")
    observed_counts = frame["status"].value_counts().to_dict()
    if observed_counts != manifest["outcome_status_counts"]:
        raise ValueError("outcome status totals do not match the replay manifest")
    return frame, manifest


def compare_frames(strict: pd.DataFrame, alternative: pd.DataFrame) -> dict[str, Any]:
    """Fail on changed stable evidence while accounting for censoring transitions."""
    if len(strict) != len(alternative):
        raise ValueError("replays have unequal bracket populations")
    if not strict["outcome_id"].is_unique or not alternative["outcome_id"].is_unique:
        raise ValueError("conditional IDs must be unique in each replay")
    merged = strict.merge(
        alternative,
        on="outcome_id",
        how="outer",
        validate="one_to_one",
        suffixes=("_strict", "_alternative"),
        indicator=True,
    )
    if not merged["_merge"].eq("both").all():
        raise ValueError("alternative replay changed the proposal/bracket population")
    strict_status = merged["status_strict"]
    alternative_status = merged["status_alternative"]
    transition_frame = (
        merged.groupby(["status_strict", "status_alternative"], dropna=False)
        .size()
        .reset_index(name="rows")
    )
    unchanged_finished = strict_status.isin(("filled_resolved", "unfilled_expired"))
    if not (strict_status[unchanged_finished] == alternative_status[unchanged_finished]).all():
        raise ValueError("a completed strict outcome changed status under relaxed coverage")
    for column in ("fill_time", "exit_time", "exit_reason"):
        left = merged.loc[unchanged_finished, f"{column}_strict"].fillna("<null>")
        right = merged.loc[unchanged_finished, f"{column}_alternative"].fillna("<null>")
        if not left.eq(right).all():
            raise ValueError(f"already-completed outcome changed {column}")
    for column in ("fill_price", "exit_price", "net_r"):
        left_numeric = merged.loc[unchanged_finished, f"{column}_strict"].to_numpy(dtype=float)
        right_numeric = merged.loc[unchanged_finished, f"{column}_alternative"].to_numpy(
            dtype=float
        )
        if not np.allclose(left_numeric, right_numeric, rtol=0.0, atol=1e-12, equal_nan=True):
            raise ValueError(f"already-completed outcome changed {column}")

    left_unresolved = (strict_status == "unresolved_data") & (
        alternative_status != "unresolved_data"
    )
    newly_filled = left_unresolved & (alternative_status == "filled_resolved")
    newly_unfilled = left_unresolved & (alternative_status == "unfilled_expired")
    now_censored = left_unresolved & alternative_status.isin(
        ("censored_order_horizon", "censored_exit_horizon")
    )
    reason_counts = Counter(
        str(reason) for reason in merged.loc[left_unresolved, "unresolved_reason_strict"]
    )
    status_transition_counts = [
        {
            "strict_status": str(row["status_strict"]),
            "alternative_status": str(row["status_alternative"]),
            "rows": int(row["rows"]),
        }
        for _, row in transition_frame.iterrows()
    ]
    return {
        "rows_compared": len(merged),
        "outcomes_with_status_changed": int((strict_status != alternative_status).sum()),
        "strict_unresolved": int((strict_status == "unresolved_data").sum()),
        "alternative_unresolved": int((alternative_status == "unresolved_data").sum()),
        "unresolved_that_left_unresolved_data": int(left_unresolved.sum()),
        "unresolved_that_became_administratively_censored": int(now_censored.sum()),
        "unresolved_that_became_filled_resolved": int(newly_filled.sum()),
        "unresolved_that_became_unfilled_expired": int(newly_unfilled.sum()),
        "original_completed_outcomes_stable": True,
        "status_transitions": status_transition_counts,
        "original_unresolved_reasons_of_reclassified": dict(sorted(reason_counts.items())),
        "conditional_return_claim": False,
        "newly_resolved_mean_r": (
            float(merged.loc[newly_filled, "net_r_alternative"].mean())
            if newly_filled.any()
            else None
        ),
        "newly_resolved_mean_r_is_descriptive_only": True,
    }


def compare_packets(
    *, strict_dir: Path, alternative_dirs: list[Path], output_dir: Path
) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(f"output dir already exists: {output_dir}")
    strict, strict_manifest = load_packet(strict_dir)
    if not alternative_dirs:
        raise ValueError("at least one alternate coverage profile is required")
    comparisons: dict[str, Any] = {}
    for packet_dir in alternative_dirs:
        other, other_manifest = load_packet(packet_dir)
        for key in IDENTICAL_INPUTS:
            if strict_manifest[key] != other_manifest[key]:
                raise ValueError(f"unmatched replay input {key}: {packet_dir}")
        # Strict and alternative must use identical production code; only the
        # coverage packet/assumption may differ.
        if strict_manifest["source_sha256"] != other_manifest["source_sha256"]:
            raise ValueError("execution source changed; experiment is not paired")
        profile = packet_dir.name
        if profile in comparisons:
            raise ValueError(f"duplicate profile: {profile}")
        result = compare_frames(strict, other)
        comparisons[profile] = {
            **result,
            "manifest_sha256": sha256(packet_dir / "outcome_manifest.json"),
            "parquet_sha256": sha256(packet_dir / "conditional_outcomes.parquet"),
            "quote_coverage_rule": other_manifest["quote_coverage_rule"],
        }
    output_dir.mkdir(parents=True, exist_ok=False)
    report = {
        "schema_version": "candidate-outcome-coverage-sensitivity-comparison-v1",
        "status": "paired_local_censoring_sensitivity_verified",
        "estimand": "conditional_fixed_entry_only",
        "broker_equivalence_claim": False,
        "no_candidate_value_or_rl_performance_claim": True,
        "strict_manifest_sha256": sha256(strict_dir / "outcome_manifest.json"),
        "strict_parquet_sha256": sha256(strict_dir / "conditional_outcomes.parquet"),
        "source_sha256": {str(Path(__file__).resolve().relative_to(ROOT)): sha256(Path(__file__))},
        "comparisons": comparisons,
    }
    report_path = output_dir / "comparison.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")
    (output_dir / "OUTPUT_SHA256SUMS").write_text(f"{sha256(report_path)}  {report_path.name}\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict-outcomes", type=Path, required=True)
    parser.add_argument("--alternative-outcomes", type=Path, nargs="+", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    def resolve(path: Path) -> Path:
        return path if path.is_absolute() else ROOT / path

    result = compare_packets(
        strict_dir=resolve(args.strict_outcomes),
        alternative_dirs=[resolve(path) for path in args.alternative_outcomes],
        output_dir=resolve(args.output_dir),
    )
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
