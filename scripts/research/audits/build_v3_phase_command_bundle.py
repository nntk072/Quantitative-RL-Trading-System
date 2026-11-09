#!/usr/bin/env python3
"""Convert a passing V3 phase review's frozen commands into an executable bundle."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from scripts.research.audits.record_pretraining_scientific_gate import file_sha256

from artifacts.atomic import write_json_atomic
from configuration.paths import repository_root

ROOT = repository_root(__file__)
SUPPORTED_REVIEW_SCHEMAS = {"v3-phase-review-v2"}


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def build_bundle(review: dict[str, Any], *, source_sha: str, source_clean: bool) -> dict[str, Any]:
    """Build a source-bound command bundle from an already reviewed phase."""
    if not source_clean:
        raise ValueError("phase command bundle requires a clean source tree")
    if review.get("schema_version") not in SUPPORTED_REVIEW_SCHEMAS:
        raise ValueError("phase review does not support frozen commands")
    if review.get("status") != "pass":
        raise ValueError("phase review is not passing")
    if review.get("source_commit") != source_sha:
        raise ValueError("phase review source SHA is stale")
    evidence = review.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        raise ValueError("phase review has no evidence")
    for row in evidence:
        path = Path(str(row.get("path", "")))
        if not path.is_file() or file_sha256(path) != row.get("sha256"):
            raise ValueError(f"phase review evidence changed: {path}")
    commands = review.get("frozen_commands")
    if not isinstance(commands, list) or not commands:
        raise ValueError("phase review has no frozen commands")
    return {
        "schema_version": "v3-frozen-command-bundle-v1",
        "source_commit": source_sha,
        "source_clean": source_clean,
        "phase": review.get("gate_id"),
        "review_claim": review.get("claim"),
        "reviewed_at_utc": review.get("reviewed_at_utc"),
        "frozen_parameters": review.get("frozen_parameters", {}),
        "commands": commands,
        "allocates_compute": False,
        "executes_commands": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase-review", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    clean = not subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=ROOT, text=True
    ).strip()
    bundle = build_bundle(
        _object(args.phase_review.expanduser().resolve()),
        source_sha=source_sha,
        source_clean=clean,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(args.output, bundle)
    print(json.dumps(bundle, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
