#!/usr/bin/env python3
"""Freeze authorized survival qualification commands without executing them."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from scripts.research.analysis.evidence.build_survival_launch_plan import build_launch_plan

from artifacts.atomic import write_json_atomic
from configuration.paths import repository_root
from training.configuration.research_protocol import load_research_protocol

ROOT = repository_root(__file__)
DEFAULT_PROTOCOL = ROOT / "config/research/prospective_research_protocol.yaml"


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _git_state() -> tuple[str, bool]:
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()
    return sha, not dirty


def build_bundle(
    *,
    protocol: dict[str, Any],
    readiness: dict[str, Any],
    source_sha: str,
    source_clean: bool,
    output_root: str,
    roles: list[str],
) -> dict[str, Any]:
    """Build a direct-command bundle for requested authorized survival roles."""
    plan = build_launch_plan(
        protocol,
        output_root,
        readiness_manifest=readiness,
        current_source_sha=source_sha,
        current_source_clean=source_clean,
    )
    rows_by_role = {row["role"]: row for row in plan["qualification_commands"]}
    commands: list[dict[str, Any]] = []
    previous: str | None = None
    for role in roles:
        if role not in rows_by_role:
            raise ValueError(f"unsupported survival role: {role}")
        row = rows_by_role[role]
        if row["authorized_now"] is not True:
            raise ValueError(f"survival role is not scientifically authorized: {role}")
        command_id = f"survival_{role}"
        commands.append(
            {
                "id": command_id,
                "argv": list(row["command_argv"]),
                "depends_on": [] if previous is None else [previous],
                "resource_lock": "GPU_TRAIN_LOCK",
                "artifact_roots": [f"{output_root}/{role}"],
                "experiment": True,
            }
        )
        previous = command_id
    return {
        "schema_version": "v3-frozen-command-bundle-v1",
        "source_commit": source_sha,
        "source_clean": source_clean,
        "phase": "survival_qualification",
        "commands": commands,
        "allocates_compute": False,
        "executes_commands": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--scientific-readiness", type=Path, required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument(
        "--role",
        action="append",
        choices=("canonical", "control", "price_geometry"),
        required=True,
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source_sha, clean = _git_state()
    if not clean:
        raise SystemExit("survival command freezing requires a clean source tree")
    protocol_path = args.protocol if args.protocol.is_absolute() else ROOT / args.protocol
    bundle = build_bundle(
        protocol=load_research_protocol(protocol_path),
        readiness=_object(args.scientific_readiness.expanduser().resolve()),
        source_sha=source_sha,
        source_clean=clean,
        output_root=args.output_root,
        roles=args.role,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(args.output, bundle)
    print(json.dumps(bundle, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
