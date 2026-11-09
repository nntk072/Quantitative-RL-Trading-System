#!/usr/bin/env python3
"""Freeze source/config identities for the outcome-free prospective protocol."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from omegaconf import OmegaConf

from artifacts.atomic import write_json_atomic
from configuration.configuration_loader import load_config
from configuration.paths import repository_root
from training.configuration.research_protocol import (
    load_research_protocol,
    research_protocol_sha256,
)

ROOT = repository_root(__file__)
DEFAULT_PROTOCOL = ROOT / "config/research/prospective_research_protocol.yaml"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _resolved_config_sha256(path: Path) -> str:
    cfg = load_config(config_path=path)
    payload = OmegaConf.to_container(cfg, resolve=True)
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def build_manifest(protocol_path: Path) -> dict[str, Any]:
    """Build a manifest containing no model outcomes or report-period results."""
    protocol = load_research_protocol(protocol_path)
    policy = protocol["policy"]
    configs: dict[str, dict[str, str]] = {}
    for role, key in (
        ("control", "control_config"),
        ("canonical", "canonical_survival_config"),
        ("price_geometry", "price_geometry_config"),
    ):
        relative = Path(str(policy[key]))
        path = ROOT / relative
        if not path.is_file():
            raise FileNotFoundError(f"protocol config is missing: {relative}")
        configs[role] = {
            "path": relative.as_posix(),
            "file_sha256": _sha256(path),
            "resolved_config_sha256": _resolved_config_sha256(path),
        }

    source_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    dirty = subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=ROOT, text=True
    ).splitlines()
    return {
        "schema_version": "prospective-execution-manifest-v1",
        "artifact_role": "prospective_no_outcome_information",
        "source_commit": source_commit,
        "source_dirty": bool(dirty),
        "dirty_paths": dirty,
        "protocol_path": protocol_path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "protocol_file_sha256": _sha256(protocol_path),
        "protocol_semantic_sha256": research_protocol_sha256(protocol),
        "configs": configs,
        "forbidden_inputs": [
            "exposed_report_period_outcomes",
            "candidate_realized_returns",
            "future_market_values",
            "post_selection_metric_threshold_changes",
        ],
        "protocol": protocol,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    protocol = args.protocol if args.protocol.is_absolute() else ROOT / args.protocol
    output = args.output if args.output.is_absolute() else ROOT / args.output
    manifest = build_manifest(protocol)
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(output, manifest)
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
