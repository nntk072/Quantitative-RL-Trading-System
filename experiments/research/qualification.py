"""Command construction for survival-qualified research experiments."""

from __future__ import annotations

import sys
from collections.abc import Mapping
from pathlib import Path

from experiments.research.catalog import ExperimentSpec
from experiments.research.execution import CommandBundle, CommandSpec

PYTHON = sys.executable


def _authorized(variant_authorization: str | None, readiness: Mapping[str, object]) -> bool:
    """Return whether readiness authorizes the requested variant.

    Args:
        variant_authorization: Value used for variant authorization.
        readiness: Source-bound scientific-readiness record.

    Returns:
        Result produced by _authorized.
    """
    if readiness.get("status") != "pass":
        return False
    if variant_authorization is None:
        return readiness.get("scientific_training_authorized") is True
    return readiness.get(variant_authorization) is True


def build_qualification_bundle(
    experiment: ExperimentSpec,
    *,
    source_commit: str,
    readiness: Mapping[str, object],
    output_root: str,
    selected_variants: tuple[str, ...] = (),
) -> CommandBundle:
    """Build independent seed/fold work units for one survival experiment.

    Args:
        experiment: Registered research experiment specification.
        source_commit: Git commit binding the research artifacts.
        readiness: Source-bound scientific-readiness record.
        output_root: Base directory for generated research artifacts.
        selected_variants: Variant identifiers selected for this operation.

    Returns:
        Result produced by build_qualification_bundle.
    """
    execution = experiment.execution
    if execution.kind != "survival_qualification":
        raise ValueError(f"{experiment.experiment_id} is not a survival qualification experiment")
    if len(execution.seeds) < 6 or execution.walk_forward_splits < 5:
        raise ValueError("survival qualification requires six seeds and five walk-forward folds")

    selected = set(selected_variants)
    if selected:
        unknown = selected - {variant.variant_id for variant in experiment.variants}
        if unknown:
            raise ValueError(f"{experiment.experiment_id} has no variants named {sorted(unknown)}")
    commands: list[CommandSpec] = []
    for variant in experiment.variants:
        if selected and variant.variant_id not in selected:
            continue
        if variant.config is None or variant.architecture is None:
            raise ValueError(
                f"{experiment.experiment_id}/{variant.variant_id} needs config and architecture"
            )
        if not _authorized(variant.authorization, readiness):
            if variant.authorization is not None:
                continue
            raise ValueError(
                f"{experiment.experiment_id}/{variant.variant_id} is not scientifically authorized"
            )
        campaign_root = f"{output_root}/{experiment.experiment_id}/{variant.variant_id}"
        common = (
            PYTHON,
            "-m",
            "training.runner.training",
            "--config",
            variant.config,
            "--algo",
            "ppo",
            "--arch",
            variant.architecture,
            "--seeds",
            *(str(seed) for seed in execution.seeds),
            "--walk-forward",
            "--wf-splits",
            str(execution.walk_forward_splits),
            "--purge-bars",
            str(execution.purge_bars),
            "--embargo-bars",
            str(execution.embargo_bars),
            "--out",
            campaign_root,
            "--survival-campaign-dir",
            campaign_root,
        )
        seed_completion_ids: list[str] = []
        for seed in execution.seeds:
            train_id = f"{variant.variant_id}.seed{seed}.train"
            seed_completion_ids.append(train_id)
            seed_dir = f"{campaign_root}/seeds/seed{seed}"
            commands.append(
                CommandSpec(
                    command_id=train_id,
                    seed=seed,
                    argv=(
                        *common,
                        "--survival-campaign-phase",
                        "train_seed",
                        "--survival-campaign-seed",
                        str(seed),
                    ),
                    resource_lock=execution.resource_lock,
                    artifact_roots=(
                        f"{seed_dir}/run_manifest.json",
                        f"{seed_dir}/model/ppo_final.zip",
                        f"{seed_dir}/train_path_outcome.json",
                    ),
                    experiment=True,
                    variant_id=variant.variant_id,
                    component=variant.component,
                )
            )
            for fold in range(execution.walk_forward_splits):
                fold_id = f"{variant.variant_id}.seed{seed}.fold{fold}"
                commands.append(
                    CommandSpec(
                        command_id=fold_id,
                        seed=seed,
                        argv=(
                            *common,
                            "--survival-campaign-phase",
                            "walk_forward_fold",
                            "--survival-campaign-seed",
                            str(seed),
                            "--survival-campaign-fold",
                            str(fold),
                        ),
                        depends_on=(train_id,),
                        resource_lock=execution.resource_lock,
                        artifact_roots=(f"{seed_dir}/walk_forward_folds/fold_{fold}.json",),
                        experiment=True,
                        variant_id=variant.variant_id,
                        component=variant.component,
                    )
                )
        fold_ids = tuple(
            f"{variant.variant_id}.seed{seed}.fold{fold}"
            for seed in execution.seeds
            for fold in range(execution.walk_forward_splits)
        )
        commands.append(
            CommandSpec(
                command_id=f"{variant.variant_id}.finalize",
                argv=(
                    *common,
                    "--survival-campaign-phase",
                    "finalize",
                ),
                depends_on=fold_ids,
                resource_lock=execution.resource_lock,
                artifact_roots=(f"{campaign_root}/survival_phase_gate.json",),
                experiment=True,
                continue_on_dependency_failure=True,
                accepted_return_codes=(0, 1),
                variant_id=variant.variant_id,
                component=variant.component,
            )
        )

    if not commands:
        raise ValueError(f"{experiment.experiment_id} selected no qualification variants")
    return CommandBundle(
        source_commit=source_commit,
        experiment_id=experiment.experiment_id,
        domain=experiment.domain,
        commands=tuple(commands),
    )


def qualified_checkpoint_by_seed(gate_path: Path) -> dict[int, Path]:
    """Return exact qualified checkpoint paths from a passing survival artifact.

    Args:
        gate_path: Path to the survival qualification artifact.

    Returns:
        Result produced by qualified_checkpoint_by_seed.
    """
    import json

    value = json.loads(gate_path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("status") != "pass":
        raise ValueError("survival qualification artifact is not passing")
    evidence = value.get("evidence")
    if not isinstance(evidence, list):
        raise ValueError("survival qualification artifact has no evidence list")
    checkpoints: dict[int, Path] = {}
    for row in evidence:
        if not isinstance(row, dict):
            raise ValueError("survival evidence rows must be mappings")
        seed = row.get("seed")
        checkpoint = row.get("checkpoint")
        if isinstance(seed, bool) or not isinstance(seed, int) or not isinstance(checkpoint, str):
            raise ValueError("survival evidence row has invalid seed/checkpoint")
        path = Path(checkpoint).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        checkpoints[seed] = path
    return checkpoints
