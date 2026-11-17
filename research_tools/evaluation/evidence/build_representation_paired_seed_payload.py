#!/usr/bin/env python3
"""Build source-backed six-seed B/C representation evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from research_tools.artifacts.evidence.representation_run_artifacts import (
    load_source_backed_arm,
)

from artifacts.atomic import write_json_atomic
from training.configuration.representation_study import (
    DEVELOPMENT_PERIOD,
    EQUAL_FIELDS,
    EXPECTED_SEEDS,
    EXPOSED_PERIOD,
    PAYLOAD_SCHEMA,
    SCIENTIFIC_INVALID_REASONS,
    VALID_ECONOMIC_OUTCOMES,
    load_representation_study,
)

SOURCE_SCHEMA = "qrl.representation_pair_sources.v1"
HISTORY_BY_ARM = {"B": "masked", "C": "completed_htf"}


def _load_arm(
    value: Any,
    *,
    arm_name: str,
    seed: int,
    interval: tuple[str, str],
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"pair arm {arm_name} must identify its persisted run directory")
    unknown = set(value).difference({"run_dir", "partition"})
    if unknown:
        raise ValueError(f"pair arm {arm_name} may not supply derived evidence: {sorted(unknown)}")
    if not isinstance(value.get("run_dir"), str) or not str(value["run_dir"]).strip():
        raise ValueError(f"pair arm {arm_name} requires run_dir")
    partition = value.get("partition")
    if partition not in {"training", "testing"}:
        raise ValueError(f"pair arm {arm_name} partition must be training or testing")
    return load_source_backed_arm(
        run_dir=value["run_dir"],
        partition=partition,
        arm_name=arm_name,
        seed=seed,
        declared_interval=interval,
        allowed_interval=interval,
    )


def _pair(pair: Any, *, seed: int, interval: tuple[str, str]) -> dict[str, Any]:
    if not isinstance(pair, dict):
        raise ValueError("pair must be an object")
    if set(pair) != {"seed", "B", "C"}:
        raise ValueError("pair may contain only seed and persisted B/C run references")
    arms = {
        name: _load_arm(pair.get(name), arm_name=name, seed=seed, interval=interval)
        for name in ("B", "C")
    }
    if any(arm["scientific_status"] == "invalid" for arm in arms.values()):
        invalid = {
            name: arm.get("invalid_reason")
            for name, arm in arms.items()
            if arm["scientific_status"] == "invalid"
        }
        return {
            "seed": seed,
            "source_identity_sha256": (
                arms["B"]["source_identity_sha256"]
                if arms["B"]["source_identity_sha256"] == arms["C"]["source_identity_sha256"]
                else None
            ),
            **arms,
            "inference_eligible": False,
            "inference_block_reasons": invalid,
        }

    left = arms["B"]["provenance"]
    right = arms["C"]["provenance"]
    for field in EQUAL_FIELDS:
        if left[field] != right[field]:
            raise ValueError(f"seed {seed} source-backed B/C mismatch: {field}")
    if left["environment_sha256"] == right["environment_sha256"]:
        raise ValueError("B/C completed-history environment identities must differ")
    if arms["B"]["history_availability"] != HISTORY_BY_ARM["B"]:
        raise ValueError("B must use masked HTF history")
    if arms["C"]["history_availability"] != HISTORY_BY_ARM["C"]:
        raise ValueError("C must use completed HTF history")
    if arms["B"]["run_dir"] == arms["C"]["run_dir"]:
        raise ValueError(f"seed {seed} B/C must come from distinct run directories")
    return {
        "seed": seed,
        "source_identity_sha256": left["source_identity_sha256"],
        **arms,
        "inference_eligible": True,
        "inference_block_reasons": [],
    }


def build_payload(spec: dict[str, Any], *, study_path: Path | None = None) -> dict[str, Any]:
    """Build a payload from checksummed persisted run artifacts, not supplied metrics."""
    if spec.get("schema_version") != SOURCE_SCHEMA:
        raise ValueError("unsupported representation pair source schema")
    allowed_fields = {
        "schema_version",
        "comparison_id",
        "evaluation_exposure",
        "purpose",
        "declared_interval",
        "expected_seeds",
        "pairs",
    }
    if set(spec).difference(allowed_fields):
        raise ValueError(
            "source spec may contain only registered metadata and persisted run references"
        )
    if study_path is None:
        root = Path(__file__).resolve().parents[3]
        study_path = root / "config/research/representation_study.yaml"
    study = load_representation_study(study_path)
    exposure = spec.get("evaluation_exposure")
    purpose = spec.get("purpose")
    if exposure not in {"development", "exposed_report_only"}:
        raise ValueError("unsupported evaluation exposure")
    if purpose not in {"selection", "report_only"}:
        raise ValueError("purpose must be selection or report_only")
    if exposure == "development" and purpose == "selection":
        period = DEVELOPMENT_PERIOD
    elif exposure == "exposed_report_only" and purpose == "report_only":
        period = EXPOSED_PERIOD
    else:
        raise ValueError("exposed report-period results cannot be selected")
    declared = spec.get("declared_interval")
    if declared != {"start": period[0], "end_inclusive": period[1]}:
        raise ValueError(
            "declared evaluation interval differs from the registered local-time period"
        )
    if spec.get("expected_seeds") != list(EXPECTED_SEEDS):
        raise ValueError(f"expected_seeds must be exactly {list(EXPECTED_SEEDS)}")
    pairs = spec.get("pairs")
    if not isinstance(pairs, list) or len(pairs) != len(EXPECTED_SEEDS):
        raise ValueError("representation study requires all six registered seed pairs")
    by_seed: dict[int, Any] = {}
    for pair in pairs:
        if not isinstance(pair, dict):
            raise ValueError("pair must be an object")
        seed = pair.get("seed")
        if isinstance(seed, bool) or not isinstance(seed, int) or seed in by_seed:
            raise ValueError("pair seeds must be unique integers")
        by_seed[seed] = pair
    if sorted(by_seed) != list(EXPECTED_SEEDS):
        raise ValueError("pair seeds do not match the fixed prospective seed set")
    built = [_pair(by_seed[seed], seed=seed, interval=period) for seed in EXPECTED_SEEDS]
    seen_run_dirs: set[str] = set()
    for pair in built:
        for name in ("B", "C"):
            path = pair[name]["run_dir"]
            if path in seen_run_dirs:
                raise ValueError(f"duplicate run directory: {path}")
            seen_run_dirs.add(path)
    comparison_id = spec.get("comparison_id")
    if not isinstance(comparison_id, str) or not comparison_id.strip():
        raise ValueError("comparison_id must be a non-empty string")
    return {
        "schema": PAYLOAD_SCHEMA,
        "comparison_id": comparison_id,
        "contrast": "C_minus_B",
        "intervention_field": "completed_htf_history_availability",
        "purpose": purpose,
        "evaluation_exposure": exposure,
        "declared_interval": declared,
        "expected_seeds": list(EXPECTED_SEEDS),
        "valid_economic_outcomes": sorted(VALID_ECONOMIC_OUTCOMES),
        "scientific_invalid_reasons": sorted(SCIENTIFIC_INVALID_REASONS),
        "pairs": built,
        "protocol_schema_version": study["schema_version"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to replace representation payload: {args.output}")
    spec = json.loads(args.source_spec.read_text(encoding="utf-8"))
    if not isinstance(spec, dict):
        raise ValueError("source spec must be a JSON object")
    payload = build_payload(spec)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(args.output, payload)
    print(json.dumps({"output": str(args.output), "seed_pairs": len(payload["pairs"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
