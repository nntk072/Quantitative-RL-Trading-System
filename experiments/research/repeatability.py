"""Deterministic checkpoint-repeatability experiment construction."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from artifacts.identity import file_sha256
from experiments.research.catalog import ExperimentSpec
from experiments.research.execution import CommandBundle, CommandSpec

PYTHON = sys.executable


def _object(path: Path) -> dict[str, Any]:
    """Load one JSON object from disk.

    Args:
        path: Path to the input or output artifact.

    Returns:
        Result produced by _object.
    """
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def build_repeatability_bundle(
    experiment: ExperimentSpec,
    *,
    source_commit: str,
    gate_path: Path,
    output_root: str,
) -> CommandBundle:
    """Replay every qualified checkpoint twice and compare complete train-only ledgers.

    Args:
        experiment: Registered research experiment specification.
        source_commit: Git commit binding the research artifacts.
        gate_path: Path to the survival qualification artifact.
        output_root: Base directory for generated research artifacts.

    Returns:
        Result produced by build_repeatability_bundle.
    """
    if experiment.execution.kind != "checkpoint_repeatability":
        raise ValueError(f"{experiment.experiment_id} is not a repeatability experiment")
    gate = _object(gate_path.expanduser().resolve())
    if gate.get("status") != "pass":
        raise ValueError("checkpoint repeatability requires passing survival qualification")
    evidence = gate.get("evidence")
    if not isinstance(evidence, list):
        raise ValueError("survival qualification has no evidence")
    by_seed = {
        int(row["seed"]): row
        for row in evidence
        if isinstance(row, dict) and isinstance(row.get("seed"), int)
    }
    if set(by_seed) != set(experiment.execution.seeds):
        raise ValueError("qualified seed set differs from repeatability experiment")
    commands: list[CommandSpec] = []
    for seed in experiment.execution.seeds:
        row = by_seed[seed]
        manifest_path = Path(str(row["run_manifest"])).expanduser().resolve()
        checkpoint = Path(str(row["checkpoint"])).expanduser().resolve()
        if file_sha256(manifest_path) != row.get("run_manifest_sha256"):
            raise ValueError(f"qualified run manifest changed for seed {seed}")
        if file_sha256(checkpoint) != row.get("checkpoint_sha256"):
            raise ValueError(f"qualified checkpoint changed for seed {seed}")
        source_run = manifest_path.parent
        first = f"{output_root}/{experiment.experiment_id}/seed{seed}/first"
        second = f"{output_root}/{experiment.experiment_id}/seed{seed}/second"
        for label, output in (("first", first), ("second", second)):
            commands.append(
                CommandSpec(
                    command_id=f"seed{seed}.{label}",
                    seed=seed,
                    argv=(
                        PYTHON,
                        "-m",
                        "evaluation.reanalysis.checkpoint_reanalysis",
                        "--run",
                        str(source_run),
                        "--checkpoint",
                        str(checkpoint),
                        "--output",
                        output,
                        "--train-only-screen",
                        "--export-replay-ledger",
                        "--deterministic",
                        "--seed",
                        str(seed),
                    ),
                    artifact_roots=(f"{output}/train_only_screen.json",),
                    experiment=True,
                    variant_id="deterministic_replay",
                    component="validation",
                )
            )
        comparison = f"{output_root}/{experiment.experiment_id}/seed{seed}/repeatability.json"
        commands.append(
            CommandSpec(
                command_id=f"seed{seed}.compare",
                seed=seed,
                argv=(
                    PYTHON,
                    "-m",
                    "scripts.research.analysis.evidence.compare_deterministic_reanalysis",
                    first,
                    second,
                    "--train-only-screen",
                    "--output",
                    comparison,
                ),
                depends_on=(f"seed{seed}.first", f"seed{seed}.second"),
                artifact_roots=(comparison,),
                experiment=True,
                variant_id="deterministic_replay",
                component="validation",
            )
        )
    return CommandBundle(
        source_commit=source_commit,
        experiment_id=experiment.experiment_id,
        domain=experiment.domain,
        commands=tuple(commands),
    )


def summarize_repeatability(execution_manifest: Path) -> dict[str, Any]:
    """Require every per-seed comparison produced by the execution to pass.

    Args:
        execution_manifest: Value used for execution manifest.

    Returns:
        Result produced by summarize_repeatability.
    """
    manifest = _object(execution_manifest)
    commands = manifest.get("commands")
    if not isinstance(commands, list):
        raise ValueError("repeatability execution manifest has no commands")
    comparisons = [
        row
        for row in commands
        if isinstance(row, dict) and str(row.get("command_id", "")).endswith(".compare")
    ]
    failures: list[str] = []
    for row in comparisons:
        artifacts = row.get("artifact_sha256")
        if row.get("status") != "passed" or not isinstance(artifacts, dict):
            failures.append(str(row.get("command_id")))
            continue
        paths = [Path(str(path)) for path in artifacts if str(path).endswith("repeatability.json")]
        if len(paths) != 1 or _object(paths[0]).get("status") != "passed":
            failures.append(str(row.get("command_id")))
    expected = len(comparisons)
    return {
        "schema_version": 1,
        "status": "pass" if expected == 6 and not failures else "fail",
        "comparison_count": expected,
        "failures": failures,
    }


__all__ = ["build_repeatability_bundle", "summarize_repeatability"]
