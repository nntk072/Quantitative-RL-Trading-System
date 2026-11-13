"""Portfolio continuation, hard-risk verification, and matched controls."""

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


def _gate_entries(gate_path: Path) -> dict[int, dict[str, Any]]:
    """Index qualified survival evidence by training seed.

    Args:
        gate_path: Path to the survival qualification artifact.

    Returns:
        Result produced by _gate_entries.
    """
    gate = _object(gate_path)
    if gate.get("status") != "pass":
        raise ValueError("portfolio continuation requires passing survival qualification")
    rows = gate.get("evidence")
    if not isinstance(rows, list):
        raise ValueError("survival qualification has no evidence list")
    by_seed: dict[int, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("survival evidence rows must be objects")
        seed = row.get("seed")
        if isinstance(seed, bool) or not isinstance(seed, int) or seed in by_seed:
            raise ValueError("survival evidence seeds must be unique integers")
        by_seed[seed] = row
    return by_seed


def _completed_steps(entry: dict[str, Any]) -> int:
    """Read and verify completed training steps from a qualified run.

    Args:
        entry: Value used for entry.

    Returns:
        Result produced by _completed_steps.
    """
    manifest_path = Path(str(entry["run_manifest"])).expanduser().resolve()
    manifest = _object(manifest_path)
    if file_sha256(manifest_path) != entry.get("run_manifest_sha256"):
        raise ValueError(f"qualified run manifest changed: {manifest_path}")
    completed = manifest.get("completed_steps")
    if isinstance(completed, bool) or not isinstance(completed, int) or completed < 1:
        raise ValueError(f"qualified run manifest lacks completed_steps: {manifest_path}")
    return completed


def build_portfolio_bundle(
    experiment: ExperimentSpec,
    *,
    source_commit: str,
    gate_path: Path,
    canonical_config: str,
    output_root: str,
    selected_variants: tuple[str, ...] = (),
) -> CommandBundle:
    """Continue qualified checkpoints and build matched no-trade controls.

    Args:
        experiment: Registered research experiment specification.
        source_commit: Git commit binding the research artifacts.
        gate_path: Path to the survival qualification artifact.
        canonical_config: Repository path to the canonical policy configuration.
        output_root: Base directory for generated research artifacts.
        selected_variants: Variant identifiers selected for this operation.

    Returns:
        Result produced by build_portfolio_bundle.
    """
    if experiment.execution.kind != "checkpoint_continuation":
        raise ValueError(f"{experiment.experiment_id} is not checkpoint continuation")
    gate_path = gate_path.expanduser().resolve()
    entries = _gate_entries(gate_path)
    if set(entries) != set(experiment.execution.seeds):
        raise ValueError("qualified seed set differs from the portfolio experiment")

    selected = set(selected_variants)
    valid = {"qualified_policy", "always_no_trade"}
    if selected - valid:
        raise ValueError(
            f"{experiment.experiment_id} has no variants named {sorted(selected - valid)}"
        )
    treatment = experiment.variant("qualified_policy")
    control = experiment.variant("always_no_trade")
    if treatment.role != "treatment" or control.role != "primary_control":
        raise ValueError("portfolio roles differ from the registered primary contrast")

    commands: list[CommandSpec] = []
    for seed in experiment.execution.seeds:
        entry = entries[seed]
        checkpoint = Path(str(entry["checkpoint"])).expanduser().resolve()
        if not checkpoint.is_file() or file_sha256(checkpoint) != entry.get("checkpoint_sha256"):
            raise ValueError(f"qualified checkpoint changed for seed {seed}")
        target_steps = _completed_steps(entry) + experiment.execution.additional_timesteps

        if not selected or "qualified_policy" in selected:
            run_root = f"{output_root}/{experiment.experiment_id}/qualified_policy/seed{seed}"
            commands.append(
                CommandSpec(
                    command_id=f"qualified_policy.seed{seed}",
                    seed=seed,
                    argv=(
                        PYTHON,
                        "-m",
                        "training.runner.training",
                        "--config",
                        canonical_config,
                        "--seed",
                        str(seed),
                        "--resume-checkpoint",
                        str(checkpoint),
                        "--out",
                        run_root,
                        "env.reward_mode=equity_log_growth",
                        f"training.survival_gate_manifest={gate_path}",
                        f"ppo.total_timesteps={target_steps}",
                    ),
                    resource_lock=experiment.execution.resource_lock,
                    artifact_roots=(run_root,),
                    experiment=True,
                    variant_id=treatment.variant_id,
                    component=treatment.component,
                )
            )

        if not selected or "always_no_trade" in selected:
            control_root = f"{output_root}/{experiment.experiment_id}/always_no_trade/seed{seed}"
            commands.append(
                CommandSpec(
                    command_id=f"always_no_trade.seed{seed}",
                    seed=seed,
                    argv=(
                        PYTHON,
                        "-m",
                        "scripts.research.analysis.evaluation.run_matched_setup_baselines",
                        "--config",
                        canonical_config,
                        "--period-role",
                        "development",
                        "--execution-seed",
                        str(seed),
                        "--random-policy-seed",
                        str(seed),
                        "--absolute-risk-budget-usd",
                        "900",
                        "--baselines",
                        "always_no_trade",
                        "--artifact-root",
                        control_root,
                    ),
                    artifact_roots=(control_root,),
                    experiment=True,
                    variant_id=control.variant_id,
                    component=control.component,
                )
            )
    if not commands:
        raise ValueError(f"{experiment.experiment_id} selected no portfolio variants")
    return CommandBundle(
        source_commit=source_commit,
        experiment_id=experiment.experiment_id,
        domain=experiment.domain,
        commands=tuple(commands),
    )


def find_completed_run(root: Path) -> Path:
    """Resolve exactly one completed run beneath a variant/seed output root.

    Args:
        root: Value used for root.

    Returns:
        Result produced by find_completed_run.
    """
    candidates = sorted(
        path.parent for path in root.expanduser().resolve().rglob("run_manifest.json")
    )
    if len(candidates) != 1:
        raise ValueError(
            f"expected exactly one completed run below {root}, found {len(candidates)}"
        )
    return candidates[0]


def summarize_portfolio_safety(runs: dict[int, Path]) -> dict[str, Any]:
    """Require every portfolio treatment path to complete without hard-risk breach.

    Args:
        runs: Mapping from seed to run-output root.

    Returns:
        Result produced by summarize_portfolio_safety.
    """
    if set(runs) != {42, 43, 44, 45, 46, 47}:
        raise ValueError("portfolio safety requires seeds 42..47")
    records: list[dict[str, Any]] = []
    failures: list[str] = []
    for seed, raw_root in sorted(runs.items()):
        run = find_completed_run(raw_root)
        equity_gate = _object(run / "train_equity_gate.json")
        outcome = _object(run / "train_path_outcome.json")
        safe = (
            equity_gate.get("hard_risk_ok") is True
            and equity_gate.get("breached") is False
            and outcome.get("survived_full_split") is True
            and outcome.get("completed_data_split") is True
            and outcome.get("n_breach_sessions") == 0
        )
        records.append({"seed": seed, "run": str(run), "hard_risk_safe": safe})
        if not safe:
            failures.append(f"seed{seed}")
    return {
        "schema_version": 1,
        "status": "pass" if not failures else "fail",
        "records": records,
        "failures": failures,
    }


__all__ = [
    "build_portfolio_bundle",
    "find_completed_run",
    "summarize_portfolio_safety",
]
