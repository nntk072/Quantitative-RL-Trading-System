#!/usr/bin/env python3
"""Emit frozen qualification commands without executing or allocating compute."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from configuration.paths import repository_root
from training.configuration.research_protocol import load_research_protocol

ROOT = repository_root(__file__)
DEFAULT_PROTOCOL = ROOT / "config/research/prospective_research_protocol.yaml"


def _command(config: str, output: str, protocol: dict[str, Any]) -> list[str]:
    replication = protocol["replication"]
    wf = replication["walk_forward"]
    policy = protocol["policy"]
    return [
        ".venv/bin/python",
        "-m",
        "training.runner.training",
        "--config",
        config,
        "--algo",
        "ppo",
        "--arch",
        str(policy["canonical_architecture"]),
        "--seeds",
        *[str(seed) for seed in replication["seeds"]],
        "--walk-forward",
        "--wf-splits",
        str(wf["splits"]),
        "--purge-bars",
        str(wf["purge_bars"]),
        "--embargo-bars",
        str(wf["embargo_bars"]),
        "--out",
        output,
    ]


def _authorization(
    readiness_manifest: Mapping[str, Any] | None,
    current_source_sha: str | None,
    current_source_clean: bool,
) -> tuple[bool, bool]:
    """Resolve authorization only from a current reviewed scientific manifest.

    Args:
        readiness_manifest: Optional separately reviewed scientific readiness record.
        current_source_sha: Full Git SHA for the source that will execute the plan.
        current_source_clean: Whether the executing checkout has no source changes.

    Returns:
        Scientific qualification authorization and independent PRICE authorization.
    """
    if readiness_manifest is None or not current_source_sha or not current_source_clean:
        return False, False
    if readiness_manifest.get("schema_version") != "pretraining-scientific-readiness-v1":
        return False, False
    if readiness_manifest.get("status") != "pass":
        return False, False
    if readiness_manifest.get("source_commit") != current_source_sha:
        return False, False

    scientific_authorized = readiness_manifest.get("scientific_training_authorized") is True
    price_authorized = readiness_manifest.get("price_training_authorized") is True
    return scientific_authorized, scientific_authorized and price_authorized


def build_launch_plan(
    protocol: dict[str, Any],
    output_root: str,
    *,
    readiness_manifest: Mapping[str, Any] | None = None,
    current_source_sha: str | None = None,
    current_source_clean: bool = False,
) -> dict[str, Any]:
    """Build qualification commands with a fail-closed scientific gate.

    Args:
        protocol: Validated prospective research protocol.
        output_root: Parent output directory used by frozen command arguments.
        readiness_manifest: Optional separately reviewed scientific authorization.
        current_source_sha: Full source SHA to compare with the manifest.
        current_source_clean: Whether the executing checkout has no source changes.

    Returns:
        Non-executing launch plan with per-arm authorization status.
    """
    policy = protocol["policy"]
    scientific_ready, price_ready = _authorization(
        readiness_manifest, current_source_sha, current_source_clean
    )
    rows = []
    for role, key, allowed in (
        ("control", "control_config", True),
        ("canonical", "canonical_survival_config", True),
        ("price_geometry", "price_geometry_config", False),
    ):
        config = str(policy[key])
        command = _command(config, f"{output_root}/{role}", protocol)
        rows.append(
            {
                "role": role,
                "config": config,
                "command_argv": command,
                "command_shell": shlex.join(command),
                "authorized_before_candidate_acceptance": allowed,
                "authorized_now": price_ready if role == "price_geometry" else scientific_ready,
                "gate": (
                    "candidate_geometry_acceptance_required"
                    if role == "price_geometry"
                    else "pretraining_readiness_required"
                ),
            }
        )
    return {
        "schema_version": "survival-launch-plan-v1",
        "executes_commands": False,
        "allocates_compute": False,
        "portfolio_phase_command": None,
        "portfolio_phase_blocked_until_survival_gate": True,
        "readiness_manifest_attached": readiness_manifest is not None,
        "current_source_commit": current_source_sha,
        "current_source_clean": current_source_clean,
        "scientific_training_authorized": scientific_ready,
        "price_training_authorized": price_ready,
        "qualification_commands": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output-root", default="outputs/survival_research")
    parser.add_argument("--readiness-manifest", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    protocol_path = args.protocol if args.protocol.is_absolute() else ROOT / args.protocol
    readiness = None
    if args.readiness_manifest is not None:
        readiness_path = (
            args.readiness_manifest
            if args.readiness_manifest.is_absolute()
            else ROOT / args.readiness_manifest
        )
        loaded_readiness = json.loads(readiness_path.read_text(encoding="utf-8"))
        if not isinstance(loaded_readiness, dict):
            raise ValueError("readiness manifest must be a JSON object")
        readiness = loaded_readiness
    source_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    source_clean = not subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=ROOT, text=True
    ).strip()
    plan = build_launch_plan(
        load_research_protocol(protocol_path),
        args.output_root,
        readiness_manifest=readiness,
        current_source_sha=source_sha,
        current_source_clean=source_clean,
    )
    text = json.dumps(plan, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        output = args.output if args.output.is_absolute() else ROOT / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
