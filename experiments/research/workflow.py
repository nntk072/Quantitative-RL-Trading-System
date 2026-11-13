"""High-level research workflow composition."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from experiments.research.catalog import DEFAULT_CATALOG, ResearchCatalog, load_research_catalog
from experiments.research.command_group import build_command_group_bundle
from experiments.research.execution import (
    CommandBundle,
    bundle_from_payload,
    bundle_payload,
    execute_command_bundle,
)
from experiments.research.portfolio import build_portfolio_bundle
from experiments.research.qualification import build_qualification_bundle
from experiments.research.repeatability import build_repeatability_bundle
from experiments.research.robustness import build_exposed_report_bundle, build_robustness_bundle


def current_source_commit() -> str:
    """Return the Git commit used to bind frozen research commands.

    Returns:
        Result produced by current_source_commit.
    """
    root = Path(__file__).resolve().parents[2]
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()


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


def freeze_experiment(
    catalog: ResearchCatalog,
    experiment_id: str,
    *,
    output_root: str,
    readiness: Path | None = None,
    survival_gate: Path | None = None,
    finalist_runs: dict[int, Path] | None = None,
    robustness_record: Path | None = None,
    exposure_marker: Path | None = None,
    selected_variants: tuple[str, ...] = (),
) -> CommandBundle:
    """Freeze one registered experiment into source-bound commands.

    Args:
        catalog: Value used for catalog.
        experiment_id: Registered research experiment identifier.
        output_root: Base directory for generated research artifacts.
        readiness: Source-bound scientific-readiness record.
        survival_gate: Value used for survival gate.
        finalist_runs: Mapping from seed to frozen finalist run directory.
        robustness_record: Path to the robustness disposition artifact.
        exposure_marker: Path recording the one-time exposed-period opening.
        selected_variants: Variant identifiers selected for this operation.

    Returns:
        Result produced by freeze_experiment.
    """
    experiment = catalog.experiment(experiment_id)
    unknown = set(selected_variants) - {variant.variant_id for variant in experiment.variants}
    if unknown:
        raise ValueError(f"{experiment_id} has no variants named {sorted(unknown)}")
    source_commit = current_source_commit()
    kind = experiment.execution.kind
    if kind == "command_group":
        return build_command_group_bundle(
            experiment,
            source_commit=source_commit,
            output_root=output_root,
            selected_variants=selected_variants,
            readiness=_object(readiness) if readiness is not None else None,
        )
    if kind == "survival_qualification":
        if readiness is None:
            raise ValueError("survival qualification requires a scientific readiness record")
        return build_qualification_bundle(
            experiment,
            source_commit=source_commit,
            readiness=_object(readiness),
            output_root=output_root,
            selected_variants=selected_variants,
        )
    if kind == "checkpoint_repeatability":
        if survival_gate is None:
            raise ValueError("checkpoint repeatability requires a survival qualification artifact")
        return build_repeatability_bundle(
            experiment,
            source_commit=source_commit,
            gate_path=survival_gate,
            output_root=output_root,
        )
    if kind == "checkpoint_continuation":
        if survival_gate is None:
            raise ValueError("portfolio continuation requires a survival qualification artifact")
        canonical = catalog.experiment("survival_policy").variant("setup_conditioned")
        if canonical.config is None:
            raise ValueError("canonical survival policy has no config")
        return build_portfolio_bundle(
            experiment,
            source_commit=source_commit,
            gate_path=survival_gate,
            canonical_config=canonical.config,
            output_root=output_root,
            selected_variants=selected_variants,
        )
    if kind == "checkpoint_replay":
        if finalist_runs is None:
            raise ValueError("robustness replay requires finalist runs")
        return build_robustness_bundle(
            experiment,
            source_commit=source_commit,
            finalist_runs=finalist_runs,
            output_root=output_root,
            selected_variants=selected_variants,
        )
    if kind == "report_only_replay":
        if finalist_runs is None or robustness_record is None or exposure_marker is None:
            raise ValueError(
                "report-only replay requires finalist runs, robustness evidence, and exposure marker"
            )
        return build_exposed_report_bundle(
            experiment,
            source_commit=source_commit,
            finalist_runs=finalist_runs,
            robustness_record=robustness_record,
            output_root=output_root,
            exposure_marker=exposure_marker,
        )
    raise ValueError(f"unsupported research execution kind: {kind}")


def write_bundle(bundle: CommandBundle, path: Path) -> None:
    """Write a frozen command bundle.

    Args:
        bundle: Frozen source-bound command bundle.
        path: Path to the input or output artifact.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(bundle_payload(bundle), indent=2, sort_keys=True) + "\n")


def load_bundle(path: Path) -> CommandBundle:
    """Load a frozen command bundle.

    Args:
        path: Path to the input or output artifact.

    Returns:
        Result produced by load_bundle.
    """
    return bundle_from_payload(_object(path))


__all__ = [
    "DEFAULT_CATALOG",
    "current_source_commit",
    "execute_command_bundle",
    "freeze_experiment",
    "load_bundle",
    "load_research_catalog",
    "write_bundle",
]
