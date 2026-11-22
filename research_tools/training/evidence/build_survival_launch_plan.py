#!/usr/bin/env python3
"""Emit frozen qualification commands without executing or allocating compute."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shlex
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from omegaconf import OmegaConf

from configuration import load_config
from configuration.paths import repository_root
from training.configuration.research_protocol import load_research_protocol

ROOT = repository_root(__file__)
DEFAULT_PROTOCOL = ROOT / "config/research/prospective_research_protocol.yaml"


def _resolved_config(config_path: str) -> dict[str, Any]:
    cfg = load_config(config_path=ROOT / config_path)
    value = OmegaConf.to_container(cfg, resolve=True)
    if not isinstance(value, dict):
        raise ValueError(f"resolved arm config must be a mapping: {config_path}")
    return cast(dict[str, Any], value)


def _config_identity(config_path: str) -> dict[str, str]:
    path = ROOT / config_path
    resolved = _resolved_config(config_path)
    semantic = json.dumps(resolved, sort_keys=True, separators=(",", ":"), default=str)
    return {
        "config_path": config_path,
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "resolved_config_sha256": hashlib.sha256(semantic.encode("utf-8")).hexdigest(),
    }


def _without_paths(config: dict[str, Any], paths: tuple[tuple[str, ...], ...]) -> dict[str, Any]:
    result = copy.deepcopy(config)
    for path in paths:
        value = result
        for key in path[:-1]:
            value = value[key]
        value.pop(path[-1], None)
    return result


def _selection_preflight(protocol: dict[str, Any]) -> dict[str, Any]:
    policy = protocol["policy"]
    gate_ii = policy["gate_ii_ablation_configs"]
    arm_paths = {
        "q0_control": str(policy["control_config"]),
        "q0_canonical": str(policy["canonical_survival_config"]),
        "q0_price_geometry": str(policy["price_geometry_config"]),
        "representation_a": str(gate_ii["A"]),
        "representation_b": str(gate_ii["B"]),
        "representation_c": str(gate_ii["C"]),
    }
    configs = {arm: _resolved_config(path) for arm, path in arm_paths.items()}
    if _without_paths(
        configs["q0_control"],
        (("ppo", "policy_distribution"), ("ppo", "trade_setup_conditioned")),
    ) != _without_paths(
        configs["q0_canonical"],
        (("ppo", "policy_distribution"), ("ppo", "trade_setup_conditioned")),
    ):
        raise ValueError("Q0 control/canonical arms differ outside their registered intervention")
    if _without_paths(
        configs["representation_b"], (("env", "completed_htf_history_enabled"),)
    ) != _without_paths(configs["representation_c"], (("env", "completed_htf_history_enabled"),)):
        raise ValueError("representation B/C arms differ outside completed HTF history")

    identities = {arm: _config_identity(path) for arm, path in arm_paths.items()}
    q0 = configs["q0_control"]
    wf = protocol["replication"]["walk_forward"]
    return {
        "status": "pass",
        "expected_seeds": list(protocol["replication"]["seeds"]),
        "implicit_cartesian_expansion": False,
        "arm_config_identities": identities,
        "paired_contracts": {
            "q0_primary": {
                "arms": ["q0_control", "q0_canonical"],
                "status": "matched",
                "allowed_intervention_fields": [
                    "ppo.policy_distribution",
                    "ppo.trade_setup_conditioned",
                ],
                "shared_budget": {
                    "ppo_total_timesteps": int(q0["ppo"]["total_timesteps"]),
                    "n_envs": int(q0["env"]["n_envs"]),
                    "walk_forward": dict(wf),
                },
            },
            "representation_c_minus_b": {
                "arms": ["representation_b", "representation_c"],
                "status": "matched",
                "allowed_intervention_fields": ["env.completed_htf_history_enabled"],
            },
        },
    }


def _command(
    config: str,
    output: str,
    protocol: dict[str, Any],
    arm: str,
    identity: dict[str, str],
    source_commit: str,
) -> list[str]:
    replication = protocol["replication"]
    wf = replication["walk_forward"]
    policy = protocol["policy"]
    return [
        ".venv-arm/bin/python",
        "-m",
        "training.runner.training",
        "--config",
        config,
        "--confirmatory",
        "--confirmatory-arm",
        arm,
        "--expected-config-sha256",
        identity["source_sha256"],
        "--expected-resolved-config-sha256",
        identity["resolved_config_sha256"],
        "--expected-source-commit",
        source_commit,
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
    selection_preflight = _selection_preflight(protocol)
    scientific_ready, price_ready = _authorization(
        readiness_manifest, current_source_sha, current_source_clean
    )
    rows = []
    for role, key, arm, allowed in (
        ("control", "control_config", "q0_control", True),
        ("canonical", "canonical_survival_config", "q0_canonical", True),
        ("price_geometry", "price_geometry_config", "q0_price_geometry", False),
    ):
        config = str(policy[key])
        identity = selection_preflight["arm_config_identities"][arm]
        command = _command(
            config,
            f"{output_root}/{role}",
            protocol,
            arm,
            identity,
            current_source_sha or "",
        )
        rows.append(
            {
                "role": role,
                "confirmatory_arm": arm,
                "config": config,
                "config_identity": identity,
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
        "schema_version": "survival-launch-plan-v2",
        "executes_commands": False,
        "allocates_compute": False,
        "portfolio_phase_command": None,
        "portfolio_phase_blocked_until_survival_gate": True,
        "readiness_manifest_attached": readiness_manifest is not None,
        "current_source_commit": current_source_sha,
        "current_source_clean": current_source_clean,
        "scientific_training_authorized": scientific_ready,
        "price_training_authorized": price_ready,
        "selection_preflight": selection_preflight,
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
