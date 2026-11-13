"""Development-only robustness and one-time report-only command construction."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

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


def build_robustness_bundle(
    experiment: ExperimentSpec,
    *,
    source_commit: str,
    finalist_runs: dict[int, Path],
    output_root: str,
    selected_variants: tuple[str, ...] = (),
) -> CommandBundle:
    """Build development-only checkpoint replays for registered stress variants.

    Args:
        experiment: Registered research experiment specification.
        source_commit: Git commit binding the research artifacts.
        finalist_runs: Mapping from seed to frozen finalist run directory.
        output_root: Base directory for generated research artifacts.
        selected_variants: Variant identifiers selected for this operation.

    Returns:
        Result produced by build_robustness_bundle.
    """
    if experiment.execution.kind != "checkpoint_replay":
        raise ValueError(f"{experiment.experiment_id} is not a checkpoint replay experiment")
    if set(finalist_runs) != set(experiment.execution.seeds):
        raise ValueError("finalist run set differs from the robustness seed set")
    selected = set(selected_variants)
    if selected:
        unknown = selected - {variant.variant_id for variant in experiment.variants}
        if unknown:
            raise ValueError(f"{experiment.experiment_id} has no variants named {sorted(unknown)}")
    commands: list[CommandSpec] = []
    for seed in experiment.execution.seeds:
        source_run = finalist_runs[seed].expanduser().resolve()
        if not (source_run / "run_manifest.json").is_file():
            raise FileNotFoundError(source_run / "run_manifest.json")
        for variant in experiment.variants:
            if selected and variant.variant_id not in selected:
                continue
            out = f"{output_root}/{experiment.experiment_id}/{variant.variant_id}/seed{seed}"
            argv = [
                PYTHON,
                "-m",
                "evaluation.reanalysis.checkpoint_reanalysis",
                "--run",
                str(source_run),
                "--output",
                out,
                "--train-only-screen",
                "--deterministic",
                "--seed",
                str(seed),
            ]
            for override in variant.overrides:
                key, separator, raw = override.partition("=")
                if not separator:
                    raise ValueError(
                        f"{experiment.experiment_id}/{variant.variant_id}: invalid override {override}"
                    )
                if key == "ftmo.max_drawdown_mode":
                    argv.extend(("--max-drawdown-mode", raw))
                elif key == "evaluation.tick_fill_slippage_points":
                    argv.extend(("--tick-fill-slippage-points", raw))
                elif key == "execution.max_tick_quote_wait_ms":
                    argv.extend(("--max-tick-quote-wait-ms", raw))
                elif key == "env.candidate_max_age_bars":
                    argv.extend(("--candidate-max-age-bars", raw))
                elif key == "env.risk_band_max_usd":
                    argv.extend(("--risk-band-max-usd", raw))
                else:
                    raise ValueError(f"unsupported robustness override: {key}")
            commands.append(
                CommandSpec(
                    command_id=f"{variant.variant_id}.seed{seed}",
                    seed=seed,
                    argv=tuple(argv),
                    artifact_roots=(f"{out}/train_only_screen.json",),
                    experiment=True,
                    variant_id=variant.variant_id,
                    component=variant.component,
                )
            )
    if not commands:
        raise ValueError(f"{experiment.experiment_id} selected no robustness variants")
    return CommandBundle(
        source_commit=source_commit,
        experiment_id=experiment.experiment_id,
        domain=experiment.domain,
        commands=tuple(commands),
    )


def _screen_is_safe(screen: dict[str, Any]) -> bool:
    """Return whether a development replay completed without hard-risk breach.

    Args:
        screen: Value used for screen.

    Returns:
        Result produced by _screen_is_safe.
    """
    split = screen.get("training_split")
    if not isinstance(split, dict):
        return False
    return (
        split.get("completed_data_split") is True
        and split.get("survived_full_period") is True
        and split.get("fail_time") is None
    )


def summarize_robustness(execution_manifests: list[Path]) -> dict[str, Any]:
    """Require every recorded development-only robustness replay to be hard-risk safe.

    Args:
        execution_manifests: Source-bound prerequisite execution records.

    Returns:
        Result produced by summarize_robustness.
    """
    records: list[dict[str, Any]] = []
    failures: list[str] = []
    for manifest_path in execution_manifests:
        manifest = _object(manifest_path.expanduser().resolve())
        experiment = str(manifest.get("experiment_id", ""))
        if experiment not in {"account_robustness", "execution_robustness"}:
            raise ValueError(f"unexpected robustness experiment: {experiment}")
        commands = manifest.get("commands")
        if not isinstance(commands, list):
            raise ValueError(f"execution manifest has no commands: {manifest_path}")
        for command in commands:
            if not isinstance(command, dict):
                continue
            command_id = str(command.get("command_id", ""))
            artifacts = command.get("artifact_sha256")
            screen_paths = (
                [
                    Path(str(path))
                    for path in artifacts
                    if str(path).endswith("train_only_screen.json")
                ]
                if isinstance(artifacts, dict)
                else []
            )
            safe = False
            if command.get("status") == "passed" and len(screen_paths) == 1:
                safe = _screen_is_safe(_object(screen_paths[0]))
            records.append(
                {
                    "experiment": experiment,
                    "command_id": command_id,
                    "hard_risk_safe": safe,
                    "screen": str(screen_paths[0]) if len(screen_paths) == 1 else None,
                }
            )
            if not safe:
                failures.append(f"{experiment}/{command_id}")
    return {
        "schema_version": 1,
        "status": "pass" if records and not failures else "fail",
        "records": records,
        "failures": failures,
        "selection_allowed": False,
        "scope": "development_only",
    }


def build_exposed_report_bundle(
    experiment: ExperimentSpec,
    *,
    source_commit: str,
    finalist_runs: dict[int, Path],
    robustness_record: Path,
    output_root: str,
    exposure_marker: Path,
) -> CommandBundle:
    """Open the exposed interval once, then replay the frozen finalist without selection.

    Args:
        experiment: Registered research experiment specification.
        source_commit: Git commit binding the research artifacts.
        finalist_runs: Mapping from seed to frozen finalist run directory.
        robustness_record: Path to the robustness disposition artifact.
        output_root: Base directory for generated research artifacts.
        exposure_marker: Path recording the one-time exposed-period opening.

    Returns:
        Result produced by build_exposed_report_bundle.
    """
    if experiment.execution.kind != "report_only_replay":
        raise ValueError(f"{experiment.experiment_id} is not report-only")
    record_path = robustness_record.expanduser().resolve()
    record = _object(record_path)
    if record.get("status") != "pass":
        raise ValueError("exposed-period reporting requires passing robustness evidence")
    marker = exposure_marker.expanduser().resolve()
    if marker.exists():
        raise ValueError(f"exposed report period was already opened: {marker}")
    if set(finalist_runs) != set(experiment.execution.seeds):
        raise ValueError("finalist run set differs from the report-only seed set")
    commands: list[CommandSpec] = [
        CommandSpec(
            command_id="open_exposed_report",
            argv=(
                PYTHON,
                "-m",
                "experiments.research.exposure",
                "--marker",
                str(marker),
                "--robustness-record",
                str(record_path),
            ),
            artifact_roots=(str(marker),),
            experiment=True,
        )
    ]
    for seed in experiment.execution.seeds:
        source_run = finalist_runs[seed].expanduser().resolve()
        if not (source_run / "run_manifest.json").is_file():
            raise FileNotFoundError(source_run / "run_manifest.json")
        out = f"{output_root}/{experiment.experiment_id}/frozen_finalist/seed{seed}"
        commands.append(
            CommandSpec(
                command_id=f"frozen_finalist.seed{seed}",
                seed=seed,
                argv=(
                    PYTHON,
                    "-m",
                    "evaluation.reanalysis.checkpoint_reanalysis",
                    "--run",
                    str(source_run),
                    "--output",
                    out,
                    "--allow-historical",
                    "--deterministic",
                    "--seed",
                    str(seed),
                ),
                depends_on=("open_exposed_report",),
                artifact_roots=(f"{out}/reanalysis_manifest.json",),
                experiment=True,
                variant_id="frozen_finalist",
                component="reporting",
            )
        )
    return CommandBundle(
        source_commit=source_commit,
        experiment_id=experiment.experiment_id,
        domain=experiment.domain,
        commands=tuple(commands),
    )


__all__ = [
    "build_exposed_report_bundle",
    "build_robustness_bundle",
    "summarize_robustness",
]
