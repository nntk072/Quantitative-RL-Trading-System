"""Immutable release assembly for completed research evidence."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from artifacts.atomic import write_json_atomic
from artifacts.identity import file_sha256
from configuration.paths import repository_root

ROOT = repository_root(__file__)


def _git_state() -> tuple[str, bool]:
    """Return the current source commit and clean-tree state.

    Returns:
        Result produced by _git_state.
    """
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()
    return sha, not dirty


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


def assemble_release(
    *,
    consolidated_results: Path,
    protocol: Path,
    catalog: Path,
    output_dir: Path,
    extra_artifacts: tuple[Path, ...] = (),
) -> dict[str, Any]:
    """Create a source-bound immutable evidence packet from execution outputs.

    Args:
        consolidated_results: Value used for consolidated results.
        protocol: Value used for protocol.
        catalog: Value used for catalog.
        output_dir: Directory that receives generated artifacts.
        extra_artifacts: Value used for extra artifacts.

    Returns:
        Result produced by assemble_release.
    """
    source_sha, clean = _git_state()
    if not clean:
        raise ValueError("research release requires a clean source tree")
    results = _object(consolidated_results)
    if results.get("schema_version") != 1:
        raise ValueError("unsupported consolidated research result schema")
    if output_dir.exists():
        raise FileExistsError(output_dir)
    output_dir.mkdir(parents=True)

    sources = (consolidated_results, protocol, catalog, *extra_artifacts)
    records: list[dict[str, str]] = []
    for source in sources:
        resolved = source.expanduser().resolve()
        if not resolved.is_file():
            raise FileNotFoundError(resolved)
        destination = output_dir / resolved.name
        if destination.exists():
            raise ValueError(f"release filename collision: {destination.name}")
        shutil.copy2(resolved, destination)
        records.append(
            {
                "path": destination.name,
                "sha256": file_sha256(destination),
                "source_path": str(resolved),
            }
        )
    manifest = {
        "schema_version": 1,
        "source_commit": source_sha,
        "results_domains": results.get("domains", []),
        "results_experiments": results.get("experiments", []),
        "artifacts": records,
    }
    write_json_atomic(output_dir / "release_manifest.json", manifest)
    return manifest


__all__ = ["assemble_release"]
