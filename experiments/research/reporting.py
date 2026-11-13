"""Research result consolidation by domain, experiment, variant, and seed."""

from __future__ import annotations

import csv
import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from artifacts.atomic import write_json_atomic
from artifacts.identity import file_sha256

PREFERRED_RESULT_FILES = (
    "train_only_screen.json",
    "train_path_outcome.json",
    "metrics.json",
    "summary.json",
    "reanalysis_manifest.json",
    "run_manifest.json",
)


@dataclass(frozen=True, slots=True)
class ResultRow:
    """One normalized research result record."""

    domain: str
    experiment: str
    variant: str
    seed: int | None
    status: str
    artifact: str
    metrics: dict[str, float | int | bool | str | None]
    component: str | None = None
    command_id: str | None = None
    source_commit: str | None = None
    artifact_sha256: str | None = None


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


def _scalar_metrics(value: Any, prefix: str = "") -> dict[str, float | int | bool | str | None]:
    """Flatten scalar metrics from a nested result mapping.

    Args:
        value: Value to validate or transform.
        prefix: Value used for prefix.

    Returns:
        Result produced by _scalar_metrics.
    """
    result: dict[str, float | int | bool | str | None] = {}
    if not isinstance(value, dict):
        return result
    for key, item in value.items():
        name = f"{prefix}.{key}" if prefix else str(key)
        if item is None or isinstance(item, (bool, int, float, str)):
            result[name] = item
        elif isinstance(item, dict):
            result.update(_scalar_metrics(item, name))
    return result


def read_result_artifact(
    path: Path,
    *,
    domain: str,
    experiment: str,
    variant: str,
    seed: int | None,
    component: str | None = None,
    command_id: str | None = None,
    source_commit: str | None = None,
    artifact_sha256: str | None = None,
) -> ResultRow:
    """Normalize one JSON result artifact without experiment-specific parsing code.

    Args:
        path: Path to the input or output artifact.
        domain: Research domain identifier.
        experiment: Registered research experiment specification.
        variant: Value used for variant.
        seed: Random seed used for deterministic sampling.
        component: Reusable research component that produced the artifact.
        command_id: Exact command identity in the execution manifest.
        source_commit: Source revision used to produce the result.
        artifact_sha256: Recorded content digest of the selected result artifact.

    Returns:
        Structured observation with verified artifact identity when a digest is supplied.
    """
    if artifact_sha256 is not None:
        if (
            re.fullmatch(r"[0-9a-f]{64}", artifact_sha256) is None
            or file_sha256(path) != artifact_sha256
        ):
            raise ValueError(f"result artifact SHA-256 mismatch: {path}")
    value = _object(path)
    status = value.get("status")
    if not isinstance(status, str):
        if value.get("breached") is True:
            status = "failed"
        elif value.get("completed_data_split") is True or value.get("survived_full_period") is True:
            status = "passed"
        else:
            status = "recorded"
    metrics_source = value.get("metrics") if isinstance(value.get("metrics"), dict) else value
    return ResultRow(
        domain=domain,
        experiment=experiment,
        variant=variant,
        seed=seed,
        status=status,
        artifact=str(path.resolve()),
        metrics=_scalar_metrics(metrics_source),
        component=component,
        command_id=command_id,
        source_commit=source_commit,
        artifact_sha256=artifact_sha256,
    )


def _variant_and_seed(command_id: str) -> tuple[str, int | None]:
    """Recover variant and seed identity from a command identifier.

    Args:
        command_id: Value used for command id.

    Returns:
        Result produced by _variant_and_seed.
    """
    variant = command_id.split(".", maxsplit=1)[0]
    match = re.search(r"(?:^|\.)seed(\d+)(?:\.|$)", command_id)
    return variant, int(match.group(1)) if match is not None else None


def _preferred_artifact(paths: Iterable[str]) -> Path | None:
    """Choose the strongest result artifact from declared paths.

    Args:
        paths: Value used for paths.

    Returns:
        Result produced by _preferred_artifact.
    """
    candidates = [
        Path(path)
        for path in paths
        if not path.startswith(("MISSING::", "EMPTY::")) and Path(path).suffix.lower() == ".json"
    ]
    if not candidates:
        return None
    by_name = {path.name: path for path in candidates}
    for name in PREFERRED_RESULT_FILES:
        if name in by_name:
            return by_name[name]
    return sorted(candidates)[0]


def rows_from_execution_manifest(path: Path) -> tuple[ResultRow, ...]:
    """Convert one command execution manifest into normalized result rows.

    Args:
        path: Path to the input or output artifact.

    Returns:
        Observations that retain execution status, seed, and source provenance.
    """
    manifest = _object(path)
    if manifest.get("schema_version") != 1:
        raise ValueError(f"unsupported execution manifest schema: {path}")
    domain = manifest.get("domain")
    experiment = manifest.get("experiment_id")
    commands = manifest.get("commands")
    if not isinstance(domain, str) or not isinstance(experiment, str):
        raise ValueError(f"execution manifest lacks domain/experiment identity: {path}")
    if not isinstance(commands, list):
        raise ValueError(f"execution manifest lacks command records: {path}")
    source_commit = manifest.get("source_commit")
    if not isinstance(source_commit, str):
        source_commit = None
    rows: list[ResultRow] = []
    for command in commands:
        if not isinstance(command, dict):
            raise ValueError(f"invalid command record in {path}")
        command_id = command.get("command_id")
        status = command.get("status")
        artifacts = command.get("artifact_sha256")
        if not isinstance(command_id, str) or not isinstance(status, str):
            raise ValueError(f"invalid command identity in {path}")
        if not isinstance(artifacts, dict):
            artifacts = {}
        inferred_variant, inferred_seed = _variant_and_seed(command_id)
        recorded_seed = command.get("seed")
        if recorded_seed is None:
            seed = inferred_seed
        elif isinstance(recorded_seed, bool) or not isinstance(recorded_seed, int):
            raise ValueError(f"invalid seed for command {command_id}")
        else:
            seed = recorded_seed
        recorded_variant = command.get("variant_id")
        variant = (
            recorded_variant
            if isinstance(recorded_variant, str) and recorded_variant
            else inferred_variant
        )
        recorded_component = command.get("component")
        component = (
            recorded_component
            if isinstance(recorded_component, str) and recorded_component
            else domain
        )
        artifact: Path | None
        declared_artifact = command.get("result_artifact")
        if declared_artifact is not None:
            if not isinstance(declared_artifact, str) or not declared_artifact.strip():
                raise ValueError(f"{command_id}: invalid declared result artifact")
            if declared_artifact not in artifacts:
                if status == "passed":
                    raise ValueError(f"{command_id}: result artifact not present in artifact manifest")
                artifact = None
            else:
                artifact = Path(declared_artifact)
        else:
            artifact = _preferred_artifact(str(item) for item in artifacts)
        if declared_artifact is not None and artifact is not None and not artifact.is_file():
            if status == "passed":
                raise FileNotFoundError(
                    f"{command_id}: declared result artifact is missing: {artifact}"
                )
        if artifact is not None and artifact.is_file():
            recorded_digest = artifacts.get(str(artifact))
            if status == "passed" and not isinstance(recorded_digest, str):
                raise ValueError(f"{command_id}: result artifact has no recorded SHA-256")
            row = read_result_artifact(
                artifact,
                domain=domain,
                experiment=experiment,
                variant=variant,
                seed=seed,
                component=component,
                command_id=command_id,
                source_commit=source_commit,
                artifact_sha256=recorded_digest if isinstance(recorded_digest, str) else None,
            )
            rows.append(
                ResultRow(
                    domain=row.domain,
                    experiment=row.experiment,
                    variant=row.variant,
                    seed=row.seed,
                    status=status if status != "passed" else row.status,
                    artifact=row.artifact,
                    metrics=row.metrics,
                    component=row.component,
                    command_id=row.command_id,
                    source_commit=row.source_commit,
                    artifact_sha256=row.artifact_sha256,
                )
            )
            continue
        rows.append(
            ResultRow(
                domain=domain,
                experiment=experiment,
                variant=variant,
                seed=seed,
                status=status,
                artifact=str(path.resolve()),
                metrics={},
                component=component,
                command_id=command_id,
                source_commit=source_commit,
            )
        )
    return tuple(rows)


def consolidate_execution_manifests(
    manifests: Iterable[Path],
    output_dir: Path,
) -> dict[str, Any]:
    """Consolidate execution manifests into one domain-oriented result catalog.

    Args:
        manifests: Execution manifests to consolidate.
        output_dir: Directory that receives generated artifacts.

    Returns:
        Result produced by consolidate_execution_manifests.
    """
    rows = [
        row
        for manifest in manifests
        for row in rows_from_execution_manifest(manifest.expanduser().resolve())
    ]
    return consolidate_results(rows, output_dir)


def consolidate_results(rows: Iterable[ResultRow], output_dir: Path) -> dict[str, Any]:
    """Write one JSON catalog and one flat CSV for active research results.

    Args:
        rows: Normalized result rows to consolidate.
        output_dir: Directory that receives generated artifacts.

    Returns:
        Structured result catalog also written as wide and long-form CSV datasets.
    """
    unique: dict[tuple[str | None, str, str, int | None, str | None, str], ResultRow] = {}
    for row in rows:
        identity = (
            row.source_commit,
            row.experiment,
            row.variant,
            row.seed,
            row.command_id,
            row.artifact,
        )
        previous = unique.get(identity)
        if previous is not None and previous != row:
            raise ValueError(f"conflicting results for {identity}")
        unique[identity] = row
    materialized = tuple(
        sorted(
            unique.values(),
            key=lambda row: (
                row.domain,
                row.experiment,
                row.component or "",
                row.variant,
                row.seed if row.seed is not None else -1,
                row.command_id or "",
                row.artifact,
            ),
        )
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "domains": sorted({row.domain for row in materialized}),
        "experiments": sorted({row.experiment for row in materialized}),
        "results": [
            {
                "domain": row.domain,
                "experiment": row.experiment,
                "variant": row.variant,
                "component": row.component,
                "command_id": row.command_id,
                "source_commit": row.source_commit,
                "seed": row.seed,
                "status": row.status,
                "artifact": row.artifact,
                "artifact_sha256": row.artifact_sha256,
                "metrics": row.metrics,
            }
            for row in materialized
        ],
    }
    write_json_atomic(output_dir / "results.json", payload)

    metric_names = sorted({key for row in materialized for key in row.metrics})
    fieldnames = [
        "domain",
        "experiment",
        "component",
        "variant",
        "seed",
        "command_id",
        "source_commit",
        "status",
        "artifact",
        "artifact_sha256",
        *metric_names,
    ]
    with (output_dir / "results.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for row in materialized:
            record: dict[str, object] = {
                "domain": row.domain,
                "experiment": row.experiment,
                "component": row.component,
                "variant": row.variant,
                "seed": row.seed,
                "command_id": row.command_id,
                "source_commit": row.source_commit,
                "status": row.status,
                "artifact": row.artifact,
                "artifact_sha256": row.artifact_sha256,
            }
            record.update(row.metrics)
            writer.writerow(record)

    metric_fields = [
        "domain",
        "experiment",
        "component",
        "variant",
        "seed",
        "command_id",
        "source_commit",
        "status",
        "artifact",
        "artifact_sha256",
        "metric",
        "value",
    ]
    with (output_dir / "metrics.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=metric_fields)
        writer.writeheader()
        for row in materialized:
            metric_identity = {
                "domain": row.domain,
                "experiment": row.experiment,
                "component": row.component,
                "variant": row.variant,
                "seed": row.seed,
                "command_id": row.command_id,
                "source_commit": row.source_commit,
                "status": row.status,
                "artifact": row.artifact,
                "artifact_sha256": row.artifact_sha256,
            }
            for metric in sorted(row.metrics):
                writer.writerow({**metric_identity, "metric": metric, "value": row.metrics[metric]})
    return payload


__all__ = [
    "ResultRow",
    "consolidate_execution_manifests",
    "consolidate_results",
    "read_result_artifact",
    "rows_from_execution_manifest",
]
