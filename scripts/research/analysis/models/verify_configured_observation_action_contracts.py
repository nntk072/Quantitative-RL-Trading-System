#!/usr/bin/env python3
"""Verify the current paired 109-choice observation/action contract evidence."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[4]
PACKET = ROOT / "evidence/research/model_observation_and_action_semantics"
OUTPUT = PACKET / "current_109_action_audit"
CONTRACTS = (
    PACKET / "configured_trade_setup_mtf_contract.json",
    PACKET / "configured_trade_setup_mtf_conditioned_contract.json",
)
SUPPORT_CSV = ROOT / "evidence/research/trade_setup_opportunity_census/candidate_support_review.csv"
HISTORY_TEST = ROOT / "tests/unit/models/test_encoders.py"
MASK_TEST = ROOT / "tests/unit/models/test_hybrid_actor.py"
TRACE_INVENTORY = PACKET / "decision_trace_availability_inventory.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    if not all(isinstance(key, str) for key in value):
        raise ValueError(f"expected string JSON object keys: {path}")
    return cast(dict[str, Any], value)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def contract_record(
    path: Path,
    report: dict[str, Any],
    current_input_hashes: dict[str, str],
) -> dict[str, Any]:
    identity = report["identity"]
    sources = identity["implementation_sources"]
    source_checks = [
        {
            "path": item["path"],
            "expected_sha256": item["sha256"],
            "observed_sha256": sha256(ROOT / item["path"]),
        }
        for item in sources
    ]
    mismatches = [
        item["path"] for item in source_checks if item["expected_sha256"] != item["observed_sha256"]
    ]
    if mismatches:
        raise ValueError(f"Implementation source hash mismatch in {path.name}: {mismatches}")

    input_checks = []
    for item in identity["source_files"]:
        observed = current_input_hashes[item["path"]]
        if observed != item["sha256"]:
            raise ValueError(f"Raw input hash mismatch in {path.name}: {item['path']}")
        input_checks.append(
            {
                "path": item["path"],
                "role": item["role"],
                "expected_sha256": item["sha256"],
                "observed_sha256": observed,
            }
        )

    shape = report["observation"]["reset_output_shapes"]
    schema = report["action"]["schema"]
    scope = report["scope"]
    if schema["trade_setup_category_count"] != 109 or shape["trade_setup_mask"] != [109]:
        raise ValueError(f"109-choice action/mask contract mismatch in {path.name}")
    if scope["environment_steps"] or scope["policy_actions"] or scope["report_period_rows_used"]:
        raise ValueError(f"Unexpected evaluation activity in {path.name}")
    if scope["trades_or_economics"]:
        raise ValueError(f"Unexpected economic output in {path.name}")

    return {
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": sha256(path),
        "config": scope["config"],
        "resolved_config_sha256": identity["resolved_config_sha256"],
        "implementation_source_count": len(source_checks),
        "implementation_source_hashes_match": True,
        "source_files": input_checks,
        "raw_input_file_hashes_current": True,
        "observation_shapes": shape,
        "action_schema": schema,
        "policy_configuration": report["policy_configuration"],
        "scope": scope,
        "declared_dataset_records": identity["dataset_records"],
    }


def main() -> None:
    reports = [load_json(path) for path in CONTRACTS]
    source_paths = sorted(
        {item["path"] for report in reports for item in report["identity"]["source_files"]}
    )
    current_input_hashes = {relative: sha256(ROOT / relative) for relative in source_paths}
    records = [
        contract_record(path, report, current_input_hashes)
        for path, report in zip(CONTRACTS, reports, strict=True)
    ]
    if records[0]["action_schema"] != records[1]["action_schema"]:
        raise ValueError("Matched control and conditioned action schemas differ")
    if records[0]["observation_shapes"] != records[1]["observation_shapes"]:
        raise ValueError("Matched control and conditioned observation shapes differ")
    if (
        records[0]["scope"]["train_start"] != records[1]["scope"]["train_start"]
        or records[0]["scope"]["train_end"] != records[1]["scope"]["train_end"]
    ):
        raise ValueError("Matched control and conditioned training windows differ")
    if records[0]["declared_dataset_records"] != records[1]["declared_dataset_records"]:
        raise ValueError("Matched control and conditioned processed datasets differ")
    if records[0]["policy_configuration"]["setup_conditioned_execution"]:
        raise ValueError("Control unexpectedly conditions execution on setup ID")
    if not records[1]["policy_configuration"]["setup_conditioned_execution"]:
        raise ValueError("Conditioned variant does not condition execution on setup ID")

    support = read_csv(SUPPORT_CSV)
    support_counts: dict[str, int] = {}
    for row in support:
        status = row["support_review_status"]
        support_counts[status] = support_counts.get(status, 0) + 1
    if len(support) != 108:
        raise ValueError(f"Expected 108 catalog rows, found {len(support)}")
    configured_supported = sum(row["family_enabled_by_audit_config"] == "True" for row in support)
    if configured_supported != 24:
        raise ValueError(
            f"Expected 24 config-supported candidate tuples, found {configured_supported}"
        )

    trace = load_json(TRACE_INVENTORY)
    if trace["artifact_count"] != 276:
        raise ValueError("Scoped artifact scan count changed; review this verifier's fixed scope")
    if any(
        item["per_decision_setup_trace"] or item["per_decision_price_geometry_trace"]
        for item in trace["artifacts"]
    ):
        raise ValueError("The scoped trace inventory now contains a qualifying decision trace")

    report = {
        "schema_version": 1,
        "status": "verified_current_implementation_hashes_and_matched_config_contracts",
        "interpretation": "Current configured contract audit only; it does not establish historical checkpoint shapes, policy behavior, or economic performance.",
        "contracts": records,
        "matched_contract_checks": {
            "same_action_schema": True,
            "same_observation_shapes": True,
            "same_training_window": True,
            "same_dataset_records": records[0]["declared_dataset_records"]
            == records[1]["declared_dataset_records"],
            "current_raw_input_hashes_match": True,
            "control_setup_id_conditions_execution": False,
            "conditioned_setup_id_conditions_execution": True,
        },
        "candidate_support": {
            "catalog_entries": len(support),
            "configured_supported_entries": configured_supported,
            "support_review_status_counts": support_counts,
            "input_path": SUPPORT_CSV.relative_to(ROOT).as_posix(),
            "input_sha256": sha256(SUPPORT_CSV),
        },
        "source_history_test_reference": {
            "path": HISTORY_TEST.relative_to(ROOT).as_posix(),
            "sha256": sha256(HISTORY_TEST),
            "test": "test_mtf_reasoning_encoder_uses_earlier_history_with_latest_candle_fixed",
            "execution_status": "referenced_source_test; not run by this verifier",
        },
        "masked_action_test_references": [
            {
                "path": MASK_TEST.relative_to(ROOT).as_posix(),
                "sha256": sha256(MASK_TEST),
                "test": "test_trade_setup_hybrid_distribution_samples_only_each_rows_valid_candidates",
            },
            {
                "path": MASK_TEST.relative_to(ROOT).as_posix(),
                "sha256": sha256(MASK_TEST),
                "test": "test_trade_setup_conditioned_distribution_masks_and_conditions_execution",
            },
        ],
        "trace_inventory": {
            "path": TRACE_INVENTORY.relative_to(ROOT).as_posix(),
            "sha256": sha256(TRACE_INVENTORY),
            "scanned_artifacts": trace["artifact_count"],
            "scope_limitation": "Four supplied roots; directory symlinks were not followed; not global absence proof.",
            "qualifying_setup_decision_trace": False,
            "qualifying_price_geometry_trace": False,
        },
        "limitations": [
            "The configured contract reports verify reset shapes without taking policy actions or stepping the environment.",
            "Recorded dataset array hashes are declared by the contract reports and are not recomputed by this verifier; current local input-file hashes are audited separately in market_data_quality.",
            "Class-ID conditioning is not proposed entry/stop/target/TTL price geometry.",
            "Current configured shapes are not claimed to be shapes of every historical checkpoint.",
        ],
        "generator": "scripts/research/analysis/models/verify_configured_observation_action_contracts.py",
    }
    report["generator_sha256"] = sha256(Path(__file__).resolve())
    OUTPUT.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT / "verification.json"
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    readme = """# Current 109-choice model contract audit

This packet verifies the current matched MTF control and setup-conditioned
configuration contracts against their recorded implementation source hashes.
Both have the same six-coordinate action schema, 109-category setup mask, and
observation shapes. The control does not condition execution on setup ID; the
conditioned variant uses a 32-dimensional setup embedding for its 128-unit
execution head. The setup selector remains market-latent-driven. The contracts
use training data only and record zero environment steps, policy actions, and
report-period rows.

The support review covers all 108 catalog entries: 24 are enabled by the
selected configuration and 84 are unsupported there. Source-test references
cover use of earlier valid history and valid-candidate masking. The scoped
276-artifact scan found no qualifying historical per-decision setup or
candidate price-geometry trace; this is not global absence proof.

This audit distinguishes categorical setup-ID conditioning from candidate
price geometry. It does not verify every historical checkpoint's tensor
shapes, replay a policy, or establish economic performance. Declared processed
dataset-array hashes are not recomputed here; current source-file hash evidence
is maintained in the market-data quality packet.

Regenerate with:

```bash
PYTHONPATH=. .venv/bin/python scripts/research/analysis/models/verify_configured_observation_action_contracts.py
```
"""
    (OUTPUT / "README.md").write_text(readme, encoding="utf-8")
    output_files = ["README.md", "verification.json"]
    output_prefix = OUTPUT.relative_to(ROOT).as_posix()
    sums = [f"{sha256(OUTPUT / name)}  {output_prefix}/{name}" for name in output_files]
    sums.append(
        f"{report['generator_sha256']}  {Path(__file__).resolve().relative_to(ROOT).as_posix()}"
    )
    (OUTPUT / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
    print(
        f"verified 2 matched contracts, {sum(r['implementation_source_count'] for r in records)} source references, "
        f"{configured_supported}/108 configured candidates; wrote {output_path.relative_to(ROOT)}"
    )


if __name__ == "__main__":
    main()
