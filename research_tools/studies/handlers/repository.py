"""Audit the compatibility wrappers and packaged research tools."""

from __future__ import annotations

import ast
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml


def audit_script_migrations(
    root: Path, study: Mapping[str, Any], output_dir: Path
) -> dict[str, Any]:
    """Check manifest targets, wrappers, and owner counts without writing sources."""
    del study, output_dir
    manifest_path = root / "config/studies/script_migrations.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    rows = manifest.get("scripts") if isinstance(manifest, dict) else None
    if not isinstance(rows, list):
        raise ValueError("research script migration manifest requires a scripts list")

    owner_counts: Counter[str] = Counter()
    errors: list[dict[str, str]] = []
    for row in rows:
        source = root / row["path"]
        owner_counts[str(row["owner_module"])] += 1
        if row.get("migration_state") != "complete":
            errors.append({"path": row["path"], "reason": "migration is not complete"})
            continue
        if not source.is_file():
            errors.append({"path": row["path"], "reason": "legacy wrapper is missing"})
            continue
        if row["entrypoint"] == "shell":
            target = root / row["target"]
            wrapper_text = source.read_text(encoding="utf-8")
            if not target.is_file() or "exec" not in wrapper_text:
                errors.append(
                    {"path": row["path"], "reason": "shell target or forwarding is missing"}
                )
            continue
        target = root.joinpath(*row["target"].split(".")).with_suffix(".py")
        wrapper_text = source.read_text(encoding="utf-8")
        if not target.is_file():
            errors.append({"path": row["path"], "reason": "research-tools target is missing"})
        elif row["target"] not in wrapper_text or "_run_module" not in wrapper_text:
            errors.append(
                {"path": row["path"], "reason": "Python wrapper does not forward to target"}
            )

    expected_sources = {
        path.relative_to(root).as_posix()
        for path in (root / "scripts/research").rglob("*")
        if path.is_file() and path.suffix in {".py", ".sh"} and path.name != "__init__.py"
    }
    registered_sources = {str(row.get("path")) for row in rows}
    missing = sorted(expected_sources - registered_sources)
    stale = sorted(registered_sources - expected_sources)
    legacy_package_imports: list[dict[str, Any]] = []
    for owner_module in owner_counts:
        package_name = "tools" if owner_module == "repo_tooling" else owner_module
        package_root = root / package_name / "research_tools"
        for package_source in sorted(package_root.rglob("*.py")):
            tree = ast.parse(
                package_source.read_text(encoding="utf-8"), filename=str(package_source)
            )
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    imported_modules = [node.module] if node.module is not None else []
                elif isinstance(node, ast.Import):
                    imported_modules = [alias.name for alias in node.names]
                else:
                    continue
                for imported_module in imported_modules:
                    if imported_module.startswith("scripts.research."):
                        legacy_package_imports.append(
                            {
                                "path": package_source.relative_to(root).as_posix(),
                                "line": node.lineno,
                                "module": imported_module,
                            }
                        )
    return {
        "diagnostic_status": (
            "passed"
            if not errors and not missing and not stale and not legacy_package_imports
            else "failed"
        ),
        "manifest_count": len(rows),
        "owner_counts": dict(sorted(owner_counts.items())),
        "completed_count": sum(row.get("migration_state") == "complete" for row in rows),
        "errors": errors,
        "unregistered_sources": missing,
        "stale_manifest_sources": stale,
        "legacy_package_imports": legacy_package_imports,
    }
