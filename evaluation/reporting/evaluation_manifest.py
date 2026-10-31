"""Write the canonical provenance envelope for generated evaluation artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from artifacts.atomic import write_json_atomic
from artifacts.identity import file_sha256

EVALUATION_MANIFEST_SCHEMA = "evaluation-artifacts-v1"


def build_evaluation_manifest(
    run_dir: Path,
    *,
    lineage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Describe an evaluation bundle and connect it to its source artifacts."""
    root = run_dir.resolve()
    parents: dict[str, dict[str, str] | str] = {}
    for name in ("run_manifest.json", "reanalysis_manifest.json"):
        path = root / name
        if path.is_file():
            parents[name.removesuffix(".json")] = {
                "path": name,
                "sha256": file_sha256(path),
            }
    config_path = root / "config.yaml"
    partitions = [name for name in ("training", "validation", "testing") if (root / name).is_dir()]
    numerical_artifacts: list[dict[str, Any]] = []
    for partition in partitions:
        for filename in (
            "metrics.json",
            "equity.csv",
            "trades.csv",
            "fills.csv",
            "positions.csv",
            "thesis_decisions.csv",
            "trade_setup_decisions.csv",
        ):
            artifact_path = root / partition / filename
            if artifact_path.is_file():
                numerical_artifacts.append(
                    {
                        "path": artifact_path.relative_to(root).as_posix(),
                        "sha256": file_sha256(artifact_path),
                    }
                )
    parent_lineage = dict(lineage or {})
    return {
        "schema_version": EVALUATION_MANIFEST_SCHEMA,
        "artifact_kind": "evaluation_bundle",
        "root": ".",
        "config_sha256": file_sha256(config_path) if config_path.is_file() else None,
        "partitions": partitions,
        "numerical_artifacts": numerical_artifacts,
        "parent_manifests": parents,
        "lineage": parent_lineage,
    }


def write_evaluation_manifest(
    run_dir: Path,
    *,
    lineage: dict[str, Any] | None = None,
) -> Path:
    """Atomically refresh the canonical evaluation provenance manifest."""
    path = run_dir / "evaluation_manifest.json"
    write_json_atomic(path, build_evaluation_manifest(run_dir, lineage=lineage), default=None)
    return path
