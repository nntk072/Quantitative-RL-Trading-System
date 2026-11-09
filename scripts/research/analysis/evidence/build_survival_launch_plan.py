#!/usr/bin/env python3
"""Emit frozen qualification commands without executing or allocating compute."""

from __future__ import annotations

import argparse
import json
import shlex
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


def build_launch_plan(protocol: dict[str, Any], output_root: str) -> dict[str, Any]:
    """Build commands for control, canonical, and gated PRICE qualification."""
    policy = protocol["policy"]
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
        "qualification_commands": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output-root", default="outputs/survival_research")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    protocol_path = args.protocol if args.protocol.is_absolute() else ROOT / args.protocol
    plan = build_launch_plan(load_research_protocol(protocol_path), args.output_root)
    text = json.dumps(plan, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        output = args.output if args.output.is_absolute() else ROOT / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
