"""Keep legacy research paths as wrappers around research-tools modules."""

from __future__ import annotations

import ast
import os
import re
import subprocess
from pathlib import Path
from typing import Any


class MigrationPlanError(ValueError):
    """Raised when a legacy script cannot be moved without manual review."""


_ROOT_EXPRESSION = re.compile(
    r"(?P<expression>(?:pathlib\.)?Path\(__file__\)\.resolve\(\)\.parents\[)"
    r"(?P<index>\d+)(?P<close>\])"
)
_SOURCE_PATH_ALIAS = re.compile(
    r"(?m)^\s*(?P<name>[A-Za-z_]\w*)\s*=\s*(?:pathlib\.)?Path\(__file__\)\.resolve\(\)\s*$"
)


def rebase_repository_root_expressions(
    source: str,
    legacy_path: Path,
    target_path: Path,
    root: Path,
) -> str:
    """Adjust indexed ``__file__`` parents after moving a script into a package."""
    repository = root.resolve()
    legacy = legacy_path.resolve()
    target = target_path.resolve()
    try:
        target.relative_to(repository)
    except ValueError as exc:
        raise MigrationPlanError(f"target path escapes repository: {target_path}") from exc
    target_index = len(target.relative_to(repository).parent.parts)

    def check_root(index_text: str, source_path: Path, expression: str) -> None:
        """Verify a legacy root expression resolves to this repository."""
        index = int(index_text)
        if index >= len(source_path.parents) or source_path.parents[index] != repository:
            raise MigrationPlanError(
                f"{expression} does not resolve to repository root in {source_path}"
            )

    aliases = {match.group("name") for match in _SOURCE_PATH_ALIAS.finditer(source)}

    def replace_direct(match: re.Match[str]) -> str:
        """Adjust a direct root expression to the moved module depth."""
        check_root(match.group("index"), legacy, match.group("expression"))
        return f"{match.group('expression')}{target_index}{match.group('close')}"

    updated = _ROOT_EXPRESSION.sub(replace_direct, source)
    for alias in aliases:
        pattern = re.compile(
            rf"(?P<expression>\b{re.escape(alias)}\.parents\[)(?P<index>\d+)(?P<close>\])"
        )

        def replace_alias(match: re.Match[str]) -> str:
            """Adjust an aliased root expression to the moved module depth."""
            check_root(match.group("index"), legacy, match.group("expression"))
            return f"{match.group('expression')}{target_index}{match.group('close')}"

        updated = pattern.sub(replace_alias, updated)
    return updated


def rebase_research_module_imports(source: str, module_targets: dict[str, str]) -> str:
    """Point imports between moved scripts at their research-tools modules."""
    updated = source
    for old_module, target_module in sorted(module_targets.items(), key=lambda item: -len(item[0])):
        if not old_module.startswith("scripts.research."):
            raise MigrationPlanError(f"legacy module is outside scripts.research: {old_module}")
        if re.fullmatch(r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+", target_module) is None:
            raise MigrationPlanError(f"invalid Python target module: {target_module}")
        from_pattern = re.compile(
            rf"(?m)^(?P<prefix>\s*from\s+){re.escape(old_module)}(?=\s+import\b)"
        )
        import_pattern = re.compile(
            rf"(?m)^(?P<prefix>\s*import\s+){re.escape(old_module)}(?=\s|,|$)"
        )
        updated = from_pattern.sub(rf"\g<prefix>{target_module}", updated)
        updated = import_pattern.sub(rf"\g<prefix>{target_module}", updated)
    return updated


def python_compatibility_wrapper(target: str, repository_root_index: int) -> str:
    """Build a small import-compatible wrapper that preserves direct CLI use."""
    if re.fullmatch(r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+", target) is None:
        raise MigrationPlanError(f"invalid Python target module: {target}")
    return f'''from __future__ import annotations

import sys as _sys
from importlib import import_module as _import_module
from pathlib import Path as _Path
from runpy import run_module as _run_module
from typing import Any as _Any

_ROOT = _Path(__file__).resolve().parents[{repository_root_index}]
if str(_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_ROOT))

_TARGET = "{target}"
if __name__ == "__main__":
    _run_module(_TARGET, run_name="__main__", alter_sys=True)
else:
    _module = _import_module(_TARGET)
    __all__ = [name for name in vars(_module) if not name.startswith("_")]
    globals().update({{name: getattr(_module, name) for name in __all__}})

    def __getattr__(name: str) -> _Any:
        return getattr(_module, name)

    def __dir__() -> list[str]:
        return sorted(set(globals()) | set(dir(_module)))
'''


def shell_compatibility_wrapper(target_relative_path: str) -> str:
    """Build a shell wrapper that forwards all arguments and exit status."""
    if Path(target_relative_path).is_absolute() or "\n" in target_relative_path:
        raise MigrationPlanError("shell target must be a relative single-line path")
    return f"""#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${{BASH_SOURCE[0]}}")" && pwd)"
exec "$SCRIPT_DIR/{target_relative_path}" "$@"
"""


def _target_path(root: Path, target: str, entrypoint: str) -> Path:
    """Resolve a migration target and reject paths that escape the repository."""
    if entrypoint == "shell":
        path = root / target
        if path.suffix != ".sh":
            raise MigrationPlanError(f"shell target must end in .sh: {target}")
    else:
        if re.fullmatch(r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+", target) is None:
            raise MigrationPlanError(f"invalid Python target module: {target}")
        path = root.joinpath(*target.split(".")).with_suffix(".py")
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise MigrationPlanError(f"target path escapes repository: {target}") from exc
    return path


def migrate_research_scripts(
    root: str | Path,
    manifest_path: str | Path = "config/studies/script_migrations.yaml",
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Move registered implementations into owner packages and write wrappers.

    Existing target files and dirty legacy files are rejected. A dry run
    reports every planned path without writing any source or configuration.
    """
    import yaml

    repository = Path(root).resolve()
    manifest = Path(manifest_path)
    manifest = manifest if manifest.is_absolute() else repository / manifest
    try:
        manifest.resolve().relative_to(repository)
    except ValueError as exc:
        raise MigrationPlanError("manifest path escapes repository") from exc
    data = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    rows = data.get("scripts") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise MigrationPlanError("manifest requires a scripts list")
    manifest_text = manifest.read_text(encoding="utf-8")
    if manifest_text.count("migration_state: pending") != len(rows):
        raise MigrationPlanError("manifest migration_state is not uniformly pending")

    plan: list[tuple[Path, Path, str, str, int]] = []
    targets: set[Path] = set()
    module_targets: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise MigrationPlanError("script entries must be mappings")
        legacy = repository / row["path"]
        entrypoint = row.get("entrypoint")
        target_name = row.get("target")
        if entrypoint not in {"cli", "module", "shell"} or not isinstance(target_name, str):
            raise MigrationPlanError("each script requires a valid entrypoint and target")
        if entrypoint != "shell":
            legacy_module = Path(row["path"]).with_suffix("")
            module_targets[legacy_module.as_posix().replace("/", ".")] = target_name
        target = _target_path(repository, target_name, entrypoint)
        try:
            legacy.resolve().relative_to(repository)
        except ValueError as exc:
            raise MigrationPlanError(f"legacy path escapes repository: {legacy}") from exc
        if legacy in targets or target in targets:
            raise MigrationPlanError(f"duplicate source or target path: {target}")
        if not legacy.is_file() or target.exists():
            raise MigrationPlanError(f"missing source or existing target: {legacy} -> {target}")
        mode = legacy.stat().st_mode & 0o777
        if entrypoint == "shell":
            if legacy.suffix != ".sh":
                raise MigrationPlanError(f"shell entrypoint is not a shell file: {legacy}")
        else:
            if legacy.suffix != ".py":
                raise MigrationPlanError(f"Python entrypoint is not a Python file: {legacy}")
            try:
                tree = ast.parse(legacy.read_text(encoding="utf-8"), filename=str(legacy))
            except (OSError, UnicodeError, SyntaxError) as exc:
                raise MigrationPlanError(f"cannot parse source script {legacy}: {exc}") from exc
            has_main = any(
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "main"
                for node in tree.body
            )
            if (entrypoint == "cli") != has_main:
                raise MigrationPlanError(
                    f"entrypoint classification disagrees with source: {legacy}"
                )
        targets.add(legacy)
        targets.add(target)
        plan.append((legacy, target, target_name, entrypoint, mode))

    if (repository / ".git").exists():
        legacy_paths = [str(legacy.relative_to(repository)) for legacy, *_ in plan]
        status = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all", "--", *legacy_paths],
            cwd=repository,
            capture_output=True,
            text=True,
            check=False,
        )
        if status.returncode != 0 or status.stdout.strip():
            raise MigrationPlanError("legacy script paths must be clean before migration")

    outputs: list[tuple[Path, str, int]] = []
    for legacy, target, target_name, entrypoint, mode in plan:
        if entrypoint == "shell":
            moved_source = legacy.read_bytes().decode("utf-8")
            wrapper = shell_compatibility_wrapper(
                Path(os.path.relpath(target, legacy.parent)).as_posix()
            )
        else:
            source = legacy.read_bytes().decode("utf-8")
            source = rebase_research_module_imports(source, module_targets)
            moved_source = rebase_repository_root_expressions(source, legacy, target, repository)
            wrapper_index = len(legacy.resolve().relative_to(repository).parent.parts)
            wrapper = python_compatibility_wrapper(target_name, wrapper_index)
        outputs.extend(((target, moved_source, mode), (legacy, wrapper, mode)))

    if dry_run:
        return {
            "source_count": len(plan),
            "targets": [str(target.relative_to(repository)) for _, target, _, _, _ in plan],
            "written": False,
        }

    for path, content, mode in outputs:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode("utf-8"))
        path.chmod(mode)
    manifest.write_text(
        manifest_text.replace("migration_state: pending", "migration_state: complete"),
        encoding="utf-8",
    )
    return {"source_count": len(plan), "written": True}
