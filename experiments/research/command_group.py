"""Command construction for validation, data, feature, and execution checks."""

from __future__ import annotations

import sys
from collections.abc import Mapping

from experiments.research.catalog import ExperimentSpec
from experiments.research.execution import CommandBundle, CommandSpec

PYTHON = sys.executable


def build_command_group_bundle(
    experiment: ExperimentSpec,
    *,
    source_commit: str,
    output_root: str,
    selected_variants: tuple[str, ...] = (),
    readiness: Mapping[str, object] | None = None,
) -> CommandBundle:
    """Build reusable commands declared directly by experiment variants.

    Args:
        experiment: Registered research experiment specification.
        source_commit: Git commit binding the research artifacts.
        output_root: Base directory for generated research artifacts.
        selected_variants: Variant identifiers selected for this operation.
        readiness: Source-bound scientific-readiness record.

    Returns:
        Source-bound commands with experiment-scoped artifact paths.
    """
    if experiment.execution.kind != "command_group":
        raise ValueError(f"{experiment.experiment_id} is not a command-group experiment")
    selected = set(selected_variants)
    if selected:
        unknown = selected - {variant.variant_id for variant in experiment.variants}
        if unknown:
            raise ValueError(f"{experiment.experiment_id} has no variants named {sorted(unknown)}")
    commands: list[CommandSpec] = []
    for variant in experiment.variants:
        if selected and variant.variant_id not in selected:
            continue
        if not variant.command:
            raise ValueError(f"{experiment.experiment_id}/{variant.variant_id} has no command")
        if variant.authorization is not None:
            if readiness is None or readiness.get("status") != "pass":
                raise ValueError(
                    f"{experiment.experiment_id}/{variant.variant_id} requires readiness evidence"
                )
            if readiness.get(variant.authorization) is not True:
                raise ValueError(
                    f"{experiment.experiment_id}/{variant.variant_id} is not authorized"
                )
        replacements = {
            "{python}": PYTHON,
            "{output_root}": output_root.rstrip("/") or "/",
            "{experiment_id}": experiment.experiment_id,
            "{variant_id}": variant.variant_id,
        }

        def render(template: str) -> str:
            for placeholder, value in replacements.items():
                template = template.replace(placeholder, value)
            return template

        argv = tuple(render(token) for token in variant.command)
        artifact_roots = tuple(render(root) for root in variant.artifact_roots)
        dependencies = variant.depends_on
        missing = set(dependencies) - (
            selected or {item.variant_id for item in experiment.variants}
        )
        if missing:
            raise ValueError(
                f"{experiment.experiment_id}/{variant.variant_id} requires variants "
                f"{sorted(missing)}; select them together"
            )
        commands.append(
            CommandSpec(
                command_id=variant.variant_id,
                argv=argv,
                depends_on=dependencies,
                resource_lock=experiment.execution.resource_lock,
                artifact_roots=artifact_roots,
                variant_id=variant.variant_id,
                component=variant.component,
                result_artifact=(
                    artifact_roots[0]
                    if len(artifact_roots) == 1 and artifact_roots[0].endswith(".json")
                    else None
                ),
            )
        )
    if not commands:
        raise ValueError(f"{experiment.experiment_id} selected no commands")
    return CommandBundle(
        source_commit=source_commit,
        experiment_id=experiment.experiment_id,
        domain=experiment.domain,
        commands=tuple(commands),
    )


__all__ = ["build_command_group_bundle"]
