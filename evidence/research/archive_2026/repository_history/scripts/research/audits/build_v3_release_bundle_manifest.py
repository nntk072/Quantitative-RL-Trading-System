#!/usr/bin/env python3
"""Validate and hash the complete final V3 release package."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.research.audits.record_pretraining_scientific_gate import file_sha256

from artifacts.atomic import write_json_atomic

REQUIRED_FILES = (
    "README.md",
    "RELEASE_MANIFEST.json",
    "FINAL_READINESS_REPORT.md",
    "RESEARCH_QUESTIONS_AND_METHODS.md",
    "DATA_PROVENANCE_AND_ACCESS.md",
    "MODEL_AND_BASELINE_CATALOG.md",
    "CONSOLIDATED_RESEARCH_RESULTS.md",
    "EXPERIMENT_AND_ATTEMPT_LEDGER.jsonl",
    "FUNCTION_TEST_EVIDENCE_INDEX.csv",
    "RESULTS_REPRODUCIBILITY_MATRIX.csv",
    "REGENERATION_COMMANDS.md",
    "ENVIRONMENT_AND_COMPUTE_PROFILE.md",
    "CHECKPOINT_REGISTRY.json",
    "THESIS_FIGURE_TABLE_INDEX.md",
    "KNOWN_LIMITATIONS.md",
)


def build_release_bundle(root: Path, *, verdict: str) -> dict[str, Any]:
    """Require every final package component and record its exact bytes."""
    allowed = {"READY", "READY WITH SCIENTIFIC LIMITATIONS", "BLOCKED / NEGATIVE RESULT"}
    if verdict not in allowed:
        raise ValueError("invalid final readiness verdict")
    root = root.expanduser().resolve()
    artifacts: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    for relative in REQUIRED_FILES:
        path = root / relative
        if not path.is_file():
            missing.append(relative)
            continue
        artifacts[relative] = {
            "path": str(path),
            "sha256": file_sha256(path),
            "bytes": path.stat().st_size,
        }
    return {
        "schema_version": "v3-final-release-bundle-v1",
        "release_root": str(root),
        "verdict": verdict,
        "status": "pass" if not missing else "fail",
        "required_file_count": len(REQUIRED_FILES),
        "artifact_count": len(artifacts),
        "missing": missing,
        "artifacts": artifacts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-root", type=Path, required=True)
    parser.add_argument(
        "--verdict",
        choices=("READY", "READY WITH SCIENTIFIC LIMITATIONS", "BLOCKED / NEGATIVE RESULT"),
        required=True,
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = build_release_bundle(args.release_root, verdict=args.verdict)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(args.output, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
