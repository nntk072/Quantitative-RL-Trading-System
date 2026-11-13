#!/usr/bin/env python3
"""Build a current-source checkpoint registry from completed run manifests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.research.audits.record_pretraining_scientific_gate import file_sha256

from artifacts.atomic import write_json_atomic


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _candidate_checkpoint(
    manifest: dict[str, Any], manifest_path: Path
) -> tuple[str | None, str | None]:
    checkpoint = manifest.get("checkpoint")
    if isinstance(checkpoint, dict):
        raw_path = checkpoint.get("path")
        raw_hash = checkpoint.get("sha256")
        if isinstance(raw_path, str):
            path = Path(raw_path)
            if not path.is_absolute():
                path = manifest_path.parent / path
            if path.is_file():
                observed = file_sha256(path)
                if isinstance(raw_hash, str) and raw_hash != observed:
                    raise ValueError(f"checkpoint hash mismatch: {path}")
                return str(path.resolve()), observed
    artifacts = manifest.get("artifact_paths")
    if isinstance(artifacts, dict) and isinstance(artifacts.get("checkpoint"), str):
        path = manifest_path.parent / str(artifacts["checkpoint"])
        if path.is_file():
            return str(path.resolve()), file_sha256(path)
    return None, None


def build_registry(run_roots: list[Path]) -> dict[str, Any]:
    """Scan completed run roots and retain one registry row per run manifest."""
    rows: list[dict[str, Any]] = []
    seen: set[Path] = set()
    for root in run_roots:
        root = root.expanduser().resolve()
        if not root.exists():
            raise FileNotFoundError(root)
        for manifest_path in sorted(root.rglob("run_manifest.json")):
            manifest_path = manifest_path.resolve()
            if manifest_path in seen:
                continue
            seen.add(manifest_path)
            manifest = _object(manifest_path)
            checkpoint_path, checkpoint_sha = _candidate_checkpoint(manifest, manifest_path)
            protocol = manifest.get("training_protocol")
            config = manifest.get("config")
            rows.append(
                {
                    "run_manifest": str(manifest_path),
                    "run_manifest_sha256": file_sha256(manifest_path),
                    "run_dir": str(manifest_path.parent),
                    "seed": manifest.get("seed"),
                    "source": manifest.get("source"),
                    "config": config,
                    "datasets": manifest.get("datasets"),
                    "feature_cache": manifest.get("feature_cache"),
                    "action_schema": manifest.get("action_schema"),
                    "observation_schema": manifest.get("observation_schema"),
                    "sequence_feature_schema": manifest.get("sequence_feature_schema"),
                    "training_phase": (
                        protocol.get("training_phase") if isinstance(protocol, dict) else None
                    ),
                    "checkpoint": checkpoint_path,
                    "checkpoint_sha256": checkpoint_sha,
                    "survival_gate": (
                        str((manifest_path.parent / "survival_phase_gate.json").resolve())
                        if (manifest_path.parent / "survival_phase_gate.json").is_file()
                        else None
                    ),
                    "replay_verification": (
                        str((manifest_path.parent / "replay_verification.json").resolve())
                        if (manifest_path.parent / "replay_verification.json").is_file()
                        else None
                    ),
                }
            )
    return {
        "schema_version": "v3-checkpoint-registry-v1",
        "entry_count": len(rows),
        "entries": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    registry = build_registry(args.run_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(args.output, registry)
    print(json.dumps({"output": str(args.output), "entries": registry["entry_count"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
