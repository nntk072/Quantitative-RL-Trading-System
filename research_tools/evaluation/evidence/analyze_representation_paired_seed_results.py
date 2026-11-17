#!/usr/bin/env python3
"""Analyze the registered C−B representation effect without dropping breaches."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from research_tools.evaluation.evidence.analyze_paired_seed_results import (
    analyze_paired_seed_metrics,
)
from research_tools.evaluation.evidence.build_representation_paired_seed_payload import (
    SOURCE_SCHEMA,
    build_payload,
)

from training.configuration.representation_study import (
    EXPECTED_SEEDS,
    PAYLOAD_SCHEMA,
    SCIENTIFIC_INVALID_REASONS,
    VALID_ECONOMIC_OUTCOMES,
    load_representation_study,
)


def _source_spec(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict) or payload.get("schema") != PAYLOAD_SCHEMA:
        raise ValueError(f"input schema must be {PAYLOAD_SCHEMA}")
    if payload.get("contrast") != "C_minus_B":
        raise ValueError("representation contrast must be C_minus_B")
    study = load_representation_study(
        Path(__file__).resolve().parents[3] / "config/research/representation_study.yaml"
    )
    if payload.get("protocol_schema_version") != study["schema_version"]:
        raise ValueError("representation payload protocol version mismatch")
    if payload.get("valid_economic_outcomes") != sorted(VALID_ECONOMIC_OUTCOMES):
        raise ValueError("representation payload economic outcome registry differs")
    if payload.get("scientific_invalid_reasons") != sorted(SCIENTIFIC_INVALID_REASONS):
        raise ValueError("representation payload invalid-reason registry differs")
    pairs = payload.get("pairs")
    if not isinstance(pairs, list):
        raise ValueError("pairs must be a list")
    source_pairs = []
    for pair in pairs:
        if not isinstance(pair, dict):
            raise ValueError("pair must be an object")
        source_pair: dict[str, Any] = {"seed": pair.get("seed")}
        for arm_name in ("B", "C"):
            arm = pair.get(arm_name)
            if not isinstance(arm, dict):
                raise ValueError(f"pair arm {arm_name} must be an object")
            allowed_fields = {
                "run_id",
                "run_dir",
                "partition",
                "scientific_status",
                "invalid_reason",
                "history_availability",
                "observed_evaluation_start",
                "observed_evaluation_end",
                "source_identity_sha256",
                "provenance",
                "source_artifacts",
                "outcome",
                "evaluation_complete",
                "hard_risk_gate_passed",
                "initial_operating_equity",
                "ending_retained_equity",
                "cumulative_payouts",
                "trade_count",
                "net_return_initial_equity_pct",
            }
            if set(arm).difference(allowed_fields):
                raise ValueError(f"arm {arm_name} contains unknown payload fields")
            source_pair[arm_name] = {
                "run_dir": arm.get("run_dir"),
                "partition": arm.get("partition"),
            }
        source_pairs.append(source_pair)
    return {
        "schema_version": SOURCE_SCHEMA,
        "comparison_id": payload.get("comparison_id"),
        "evaluation_exposure": payload.get("evaluation_exposure"),
        "purpose": payload.get("purpose"),
        "declared_interval": payload.get("declared_interval"),
        "expected_seeds": payload.get("expected_seeds"),
        "pairs": source_pairs,
    }


def _generic_payload(payload: dict[str, Any], pairs: list[dict[str, Any]]) -> dict[str, Any]:
    generic_pairs = []
    for pair in pairs:
        arms = {}
        for arm_name in ("B", "C"):
            arm = pair[arm_name]
            arms[arm_name] = {
                "run_id": arm["run_id"],
                "status": "succeeded",
                "evidence_role": "matched_exploratory",
                "provenance": arm["provenance"],
                "metrics": {"net_return_initial_equity_pct": arm["net_return_initial_equity_pct"]},
            }
        generic_pairs.append({"seed": pair["seed"], "control": arms["B"], "treatment": arms["C"]})
    return {
        "schema": "aalto.paired_seed_metrics.v1",
        "comparison_id": payload["comparison_id"],
        "evidence_role": "matched_exploratory",
        "evaluation_exposure": payload["evaluation_exposure"],
        "intervention_field": "environment_sha256",
        "metrics": ["net_return_initial_equity_pct"],
        "expected_seeds": [pair["seed"] for pair in pairs],
        "pairs": generic_pairs,
    }


def analyze_payload(payload: Any) -> dict[str, Any]:
    """Revalidate the source contract, then report C−B and survival separately."""
    source = _source_spec(payload)
    if source["expected_seeds"] != list(EXPECTED_SEEDS):
        raise ValueError("representation payload has a different fixed seed set")
    validated = build_payload(source)
    if payload != validated:
        raise ValueError("representation payload differs from its source-backed artifacts")

    valid_pairs = []
    excluded = []
    for pair in validated["pairs"]:
        reasons = {
            arm_name: pair[arm_name]["invalid_reason"]
            for arm_name in ("B", "C")
            if pair[arm_name]["scientific_status"] == "invalid"
        }
        if reasons:
            excluded.append({"seed": pair["seed"], "reasons": reasons})
        else:
            valid_pairs.append(pair)

    survival_rows = [
        {
            "seed": pair["seed"],
            **{
                arm_name: {
                    "outcome": pair[arm_name]["outcome"],
                    "hard_risk_gate_passed": pair[arm_name]["hard_risk_gate_passed"],
                }
                for arm_name in ("B", "C")
                if pair[arm_name]["scientific_status"] == "valid"
            },
        }
        for pair in validated["pairs"]
    ]
    valid_seeds = [pair["seed"] for pair in valid_pairs]
    returns = np.asarray(
        [
            pair["C"]["net_return_initial_equity_pct"] - pair["B"]["net_return_initial_equity_pct"]
            for pair in valid_pairs
        ],
        dtype=np.float64,
    )
    result: dict[str, Any] = {
        "schema": "aalto.representation_paired_seed_statistics.v1",
        "comparison_id": validated["comparison_id"],
        "contrast": "C_minus_B",
        "metric": "net_return_initial_equity_pct",
        "purpose": validated["purpose"],
        "evaluation_exposure": validated["evaluation_exposure"],
        "expected_seeds": list(EXPECTED_SEEDS),
        "valid_pair_seeds": valid_seeds,
        "excluded_scientific_invalid_pairs": excluded,
        "survival_co_outcome_by_seed": survival_rows,
        "q0_disposition": "separate_survival_vs_flat_protocol",
        "n_valid_pairs": len(valid_pairs),
        "mean_C_minus_B": float(returns.mean()) if len(returns) else None,
        "median_C_minus_B": float(np.median(returns)) if len(returns) else None,
    }
    if (
        validated["purpose"] == "selection"
        and validated["evaluation_exposure"] == "development"
        and len(valid_pairs) == len(EXPECTED_SEEDS)
    ):
        generic = analyze_paired_seed_metrics(
            _generic_payload(validated, valid_pairs), rng_seed=42, bootstrap_draws=10_000
        )
        result["inference_status"] = "development_selection_all_six_pairs"
        result["statistics"] = generic["metrics"]["net_return_initial_equity_pct"]
        result["bootstrap"] = generic["bootstrap"]
        result["multiple_testing"] = generic["multiple_testing"]
    else:
        result["inference_status"] = "descriptive_only_inference_not_performed"
        result["statistics"] = None
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to replace statistics output: {args.output}")
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    result = analyze_payload(payload)
    result["input_path"] = str(args.input.resolve())
    result["input_sha256"] = hashlib.sha256(args.input.read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "valid_pairs": result["n_valid_pairs"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
