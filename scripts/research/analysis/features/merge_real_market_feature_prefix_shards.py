#!/usr/bin/env python3
"""Validate and merge independently computed real-market prefix audit shards."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from scripts.research.analysis.features.verify_real_market_feature_prefix_invariance import (
    AUDIT_SCRIPT_SHA256,
    DEFAULT_CUTOFFS,
    ROOT,
    feature_config_key,
    load_inventory_profiles,
)


def merge_reports(
    reports: list[dict[str, Any]],
    expected_groups: dict[str, set[str]],
    *,
    expected_cutoff_count: int = len(DEFAULT_CUTOFFS),
) -> dict[str, Any]:
    """Merge reports only when shard identity and group coverage are exact."""
    if not reports:
        raise ValueError("at least one shard report is required")
    count_values = {
        int((report.get("profile_group_shard") or {}).get("count", 0)) for report in reports
    }
    if len(count_values) != 1:
        raise ValueError("shards disagree on shard count")
    shard_count = count_values.pop()
    if shard_count <= 0 or len(reports) != shard_count:
        raise ValueError("the report set does not contain every declared shard")
    indexed: dict[int, dict[str, Any]] = {}
    for report in reports:
        shard = report.get("profile_group_shard")
        if not isinstance(shard, dict):
            raise ValueError("report is not a profile-group shard")
        index = int(shard.get("index", -1))
        if index < 0 or index >= shard_count or index in indexed:
            raise ValueError("shard indices must be unique and in range")
        indexed[index] = report
    if set(indexed) != set(range(shard_count)):
        raise ValueError("shard indices are incomplete")
    ordered = [indexed[index] for index in range(shard_count)]

    invariant_keys = (
        "audit",
        "profile_inventory_sha256",
        "profile_inventory_mode",
        "feature_version",
        "audit_script_sha256",
        "source_hashes",
        "rows",
        "start",
        "end",
        "train_start",
        "train_end",
        "test_start",
    )
    first = ordered[0]
    if first.get("audit_script_sha256") != AUDIT_SCRIPT_SHA256:
        raise ValueError("shard audit script hash does not match the current source")
    for report in ordered[1:]:
        for key in invariant_keys:
            if report.get(key) != first.get(key):
                raise ValueError(f"shards disagree on {key}")

    expected_profiles = sorted(
        {profile_id for profile_ids in expected_groups.values() for profile_id in profile_ids}
    )
    for report in ordered:
        if sorted(str(item) for item in report.get("resolved_profiles", [])) != expected_profiles:
            raise ValueError("shard does not record the complete resolved profile inventory")
        if report.get("input_files") != first.get("input_files"):
            raise ValueError("shards disagree on the local input files or hashes")

    actual_groups: dict[str, set[str]] = {}
    group_records: list[dict[str, Any]] = []
    cutoff_signature: list[str] | None = None
    for index, report in enumerate(ordered):
        shard = report["profile_group_shard"]
        if int(shard["index"]) != index:
            raise ValueError("reports must be supplied in shard-index order")
        groups = report.get("profile_groups")
        if not isinstance(groups, list) or len(groups) != int(shard.get("selected_groups", -1)):
            raise ValueError("shard group count does not match its report metadata")
        for group in groups:
            group_id = str(group["profile_id"])
            if group_id in actual_groups:
                raise ValueError(f"duplicate feature-builder group across shards: {group_id}")
            profile_ids = {str(item) for item in group.get("profile_ids", [])}
            cutoff_records = group.get("cutoffs")
            if not isinstance(cutoff_records, list) or len(cutoff_records) != expected_cutoff_count:
                raise ValueError(f"feature-builder group {group_id} has an incomplete cutoff set")
            group_cutoff_signature = [str(item["cutoff"]) for item in cutoff_records]
            if cutoff_signature is None:
                cutoff_signature = group_cutoff_signature
            elif group_cutoff_signature != cutoff_signature:
                raise ValueError(f"feature-builder group {group_id} has different cutoffs")
            group_summary = group.get("summary", {})
            expected_group_summary = {
                "passed": sum(bool(item["passed"]) for item in cutoff_records),
                "failed": sum(not bool(item["passed"]) for item in cutoff_records),
                "cutoffs": len(cutoff_records),
            }
            if any(
                group_summary.get(key) != value for key, value in expected_group_summary.items()
            ):
                raise ValueError(
                    f"feature-builder group {group_id} summary does not match its cutoffs"
                )
            actual_groups[group_id] = profile_ids
            group_records.append(group)
    if actual_groups != expected_groups:
        missing = sorted(set(expected_groups) - set(actual_groups))
        unexpected = sorted(set(actual_groups) - set(expected_groups))
        wrong_profiles = sorted(
            group_id
            for group_id in set(actual_groups) & set(expected_groups)
            if actual_groups[group_id] != expected_groups[group_id]
        )
        raise ValueError(
            "profile-group coverage mismatch: "
            f"missing={missing}, unexpected={unexpected}, wrong_profiles={wrong_profiles}"
        )

    input_files = {str(path): str(digest) for path, digest in first["input_files"].items()}
    group_records.sort(key=lambda item: str(item["profile_id"]))
    cutoffs = [cutoff for group in group_records for cutoff in group["cutoffs"]]
    merged = dict(first)
    merged.update(
        {
            "resolved_profiles": expected_profiles,
            "base_configs": sorted(
                {str(path) for report in ordered for path in report.get("base_configs", [])}
            ),
            "profile_group_shard": {"merged_count": shard_count},
            "profile_groups": group_records,
            "input_files": dict(sorted(input_files.items())),
            "cutoffs": cutoffs,
            "summary": {
                "passed": sum(bool(item["passed"]) for item in cutoffs),
                "failed": sum(not bool(item["passed"]) for item in cutoffs),
                "cutoffs": len(cutoffs),
                "feature_profiles": len(group_records),
            },
            "shards": [
                {
                    "index": index,
                    "count": shard_count,
                    "selected_groups": len(report["profile_groups"]),
                    "slurm_job_id": report.get("runtime", {}).get("slurm_job_id"),
                }
                for index, report in enumerate(ordered)
            ],
        }
    )
    return merged


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--inventory",
        type=Path,
        default=ROOT / "evidence/research/feature_causality/feature_configuration_inventory.json",
    )
    parser.add_argument("--shards", type=Path, nargs="+", required=True)
    parser.add_argument("--expected-cutoff-count", type=int, default=len(DEFAULT_CUTOFFS))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    profiles, _inventory_hash = load_inventory_profiles(args.inventory)
    expected_groups: dict[str, set[str]] = {}
    for profile_id, cfg, _metadata in profiles:
        expected_groups.setdefault(feature_config_key(cfg), set()).add(profile_id)
    reports = [json.loads(path.read_text(encoding="utf-8")) for path in args.shards]
    merged = merge_reports(
        reports,
        expected_groups,
        expected_cutoff_count=args.expected_cutoff_count,
    )
    merged["merge_script_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    output = args.out if args.out.is_absolute() else ROOT / args.out
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    print(f"report={output} summary={merged['summary']}", flush=True)
    return 0 if merged["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
