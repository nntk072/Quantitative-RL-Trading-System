"""Load and validate the declarative repository study catalogue."""

from __future__ import annotations

import ast
import re
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from configuration.paths import repository_root
from research_tools.studies.study_inventory import UniqueKeyLoader

_DEFAULT_MASTER = Path("config/studies/default.yaml")
_STUDY_TYPES = {"code_check", "audit", "empirical"}
_SCRIPT_ENTRYPOINTS = {"cli", "module", "shell"}
_SCRIPT_MIGRATION_STATES = {"pending", "compat_wrapper", "complete"}
_DEFAULT_ACCEPTANCE = {
    "code_check": "Every listed focused check passes, with no uncovered source or config inputs.",
    "audit": "Every registered input has a provenance-backed disposition, and limits are stated.",
}


class StudyCatalogError(ValueError):
    """Raised when a study config is incomplete or refers outside the repository."""


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        value = yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueKeyLoader)
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise StudyCatalogError(f"cannot read YAML {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise StudyCatalogError(f"YAML root must be a mapping: {path}")
    return value


def _validate_evidence_index(
    root: Path,
    index_path: str,
    study_ids: set[str],
) -> dict[str, Any]:
    index = _read_yaml(_repo_path(root, index_path, "evidence_index"))
    if index.get("schema_version") != 1:
        raise StudyCatalogError("evidence index schema_version must be 1")
    roots = index.get("roots")
    items = index.get("items")
    if not isinstance(roots, list) or not roots or any(not isinstance(path, str) for path in roots):
        raise StudyCatalogError("evidence index roots must be repository-relative paths")
    resolved_roots = [_repo_path(root, value, "evidence_index.roots") for value in roots]
    if any(not path.is_dir() for path in resolved_roots):
        raise StudyCatalogError("evidence index roots must exist as directories")
    if not isinstance(items, list):
        raise StudyCatalogError("evidence index items must be a list")
    indexed: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            raise StudyCatalogError("evidence index entries must be mappings")
        path_value = item.get("path")
        kind = item.get("kind")
        status = item.get("status")
        owners = item.get("study_ids")
        if (
            not isinstance(path_value, str)
            or not isinstance(kind, str)
            or not kind.strip()
            or not isinstance(status, str)
            or not status.strip()
            or not isinstance(owners, list)
            or not owners
            or any(not isinstance(owner, str) or owner not in study_ids for owner in owners)
        ):
            raise StudyCatalogError("evidence entries require path, kind, status, and study_ids")
        path = _repo_path(root, path_value, "evidence_index")
        if not path.is_file():
            raise StudyCatalogError(f"evidence index references missing file: {path_value}")
        if not any(path == base or base in path.parents for base in resolved_roots):
            raise StudyCatalogError(f"evidence path is outside configured roots: {path_value}")
        if path_value in indexed:
            raise StudyCatalogError(f"duplicate evidence index path: {path_value}")
        indexed.add(path_value)
    discovered = {
        path.relative_to(root).as_posix()
        for base in resolved_roots
        for path in base.rglob("*")
        if path.is_file()
    }
    missing = sorted(discovered - indexed)
    stale = sorted(indexed - discovered)
    if missing or stale:
        raise StudyCatalogError(f"evidence index mismatch: unregistered={missing}, missing={stale}")
    return index


def _repo_path(root: Path, value: str, owner: str) -> Path:
    path = (root / value).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise StudyCatalogError(f"{owner} path escapes repository: {value}") from exc
    return path


def _profile_root(root: Path, master_file: Path, profile_dir: str) -> Path:
    candidate = master_file.parent / profile_dir
    try:
        relative = candidate.relative_to(root)
    except ValueError as exc:
        raise StudyCatalogError("study profile directory must be inside the repository") from exc
    return _repo_path(root, relative.as_posix(), "profile_dir")


def _acceptance_rules(master: Mapping[str, Any]) -> dict[str, str]:
    rules = master.get("study_defaults", _DEFAULT_ACCEPTANCE)
    if not isinstance(rules, dict) or any(
        key not in _STUDY_TYPES - {"empirical"} or not isinstance(value, str) or not value.strip()
        for key, value in rules.items()
    ):
        raise StudyCatalogError("study_defaults must map code_check or audit to acceptance text")
    return {**_DEFAULT_ACCEPTANCE, **rules}


def _path_list(root: Path, profile: Mapping[str, Any], key: str, module_id: str) -> list[str]:
    values = profile.get(key, [])
    if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
        raise StudyCatalogError(f"{module_id}.{key} must be a list of repository paths")
    for value in values:
        path = _repo_path(root, value, f"{module_id}.{key}")
        if not path.exists():
            raise StudyCatalogError(f"{module_id}.{key} references missing path: {value}")
    return values


def _config_glob_paths(root: Path, profile: Mapping[str, Any], module_id: str) -> list[str]:
    patterns = profile.get("config_globs", [])
    if not isinstance(patterns, list) or any(not isinstance(item, str) for item in patterns):
        raise StudyCatalogError(f"{module_id}.config_globs must be a list of repository patterns")
    matches: list[str] = []
    for pattern in patterns:
        _repo_path(root, pattern, f"{module_id}.config_globs")
        paths = sorted(root.glob(pattern))
        if not paths or any(not path.is_file() for path in paths):
            raise StudyCatalogError(f"{module_id}.config_globs has no file matches: {pattern}")
        for path in paths:
            _repo_path(root, path.relative_to(root).as_posix(), module_id)
        matches.extend(path.relative_to(root).as_posix() for path in paths)
    return matches


def _study_config_paths(root: Path, study: Mapping[str, Any], study_id: str) -> list[str]:
    paths = study.get("config_paths", [])
    patterns = study.get("config_globs", [])
    if not isinstance(paths, list) or any(not isinstance(item, str) for item in paths):
        raise StudyCatalogError(f"{study_id}.config_paths must be a list of repository paths")
    if not isinstance(patterns, list) or any(not isinstance(item, str) for item in patterns):
        raise StudyCatalogError(f"{study_id}.config_globs must be a list of repository patterns")
    for value in paths:
        if not _repo_path(root, value, study_id).is_file():
            raise StudyCatalogError(f"{study_id} references missing config file: {value}")
    matches = list(paths)
    for pattern in patterns:
        _repo_path(root, pattern, study_id)
        found = sorted(root.glob(pattern))
        if not found or any(not path.is_file() for path in found):
            raise StudyCatalogError(f"{study_id} config pattern has no file matches: {pattern}")
        for path in found:
            _repo_path(root, path.relative_to(root).as_posix(), study_id)
        matches.extend(path.relative_to(root).as_posix() for path in found)
    arms = study.get("arms", [])
    if isinstance(arms, list):
        for arm in arms:
            if not isinstance(arm, dict):
                continue
            arm_paths = arm.get("config_paths", [])
            if not isinstance(arm_paths, list):
                continue
            for value in arm_paths:
                if isinstance(value, str) and _repo_path(root, value, study_id).is_file():
                    matches.append(value)
    return sorted(set(matches))


def _source_coverage(
    root: Path,
    profile: Mapping[str, Any],
    module_id: str,
    study_ids: set[str],
) -> dict[str, Any]:
    scopes = profile.get("source_scopes")
    source_roots = profile.get("source_roots", [])
    if not isinstance(scopes, list) or not scopes:
        raise StudyCatalogError(f"{module_id}.source_scopes must map source files to studies")
    roots = [_repo_path(root, value, module_id) for value in source_roots]
    source_files: set[Path] = set()
    for source_root in roots:
        if source_root.is_file() and source_root.suffix == ".py":
            source_files.add(source_root)
        elif source_root.is_dir():
            for path in source_root.rglob("*.py"):
                if path.is_file():
                    _repo_path(root, path.relative_to(root).as_posix(), module_id)
                    source_files.add(path)
    if not source_files:
        raise StudyCatalogError(f"{module_id}.source_roots contain no Python source files")

    resolved_scopes: list[tuple[Path, str, list[str]]] = []
    scope_rows: list[dict[str, Any]] = []
    for scope in scopes:
        if not isinstance(scope, dict) or not isinstance(scope.get("path"), str):
            raise StudyCatalogError(f"{module_id}.source_scopes entries require a path")
        path_value = scope["path"]
        scope_path = _repo_path(root, path_value, module_id)
        if not scope_path.exists():
            raise StudyCatalogError(
                f"{module_id}.source_scopes references missing path: {path_value}"
            )
        owned_roots = [path for path in roots if scope_path == path or path in scope_path.parents]
        if not owned_roots:
            raise StudyCatalogError(
                f"{module_id}.source_scopes path is outside source_roots: {path_value}"
            )
        owners = scope.get("study_ids")
        if (
            not isinstance(owners, list)
            or not owners
            or any(not isinstance(owner, str) or owner not in study_ids for owner in owners)
        ):
            raise StudyCatalogError(
                f"{module_id}.source_scopes has unknown or empty study_ids: {path_value}"
            )
        resolved_scopes.append((scope_path, path_value, owners))

    uncovered = sorted(
        path.relative_to(root).as_posix()
        for path in source_files
        if not any(
            scope_path == path or scope_path in path.parents for scope_path, _, _ in resolved_scopes
        )
    )
    if uncovered:
        raise StudyCatalogError(f"{module_id} has uncovered source files: {uncovered}")
    for scope_path, path_value, owners in resolved_scopes:
        count = sum(scope_path == path or scope_path in path.parents for path in source_files)
        scope_rows.append({"path": path_value, "study_ids": owners, "source_file_count": count})
    return {
        "source_file_count": len(source_files),
        "uncovered_source_files": uncovered,
        "source_scopes": scope_rows,
    }


def _module_import_inventories(
    root: Path,
    profiles: Mapping[str, Mapping[str, Any]],
    all_source_roots: list[str],
) -> dict[str, tuple[list[str], list[str]]]:
    """Return imported API modules and external callers for every module."""
    packages = {
        module_id: {
            Path(value).parts[0]
            for value in profile["source_roots"]
            if Path(value).parts[0] != "research_tools"
        }
        for module_id, profile in profiles.items()
    }
    files: set[Path] = set()
    for value in [*all_source_roots, "tests"]:
        path = _repo_path(root, value, "API inventory")
        if path.is_file() and path.suffix == ".py":
            files.add(path)
        elif path.is_dir():
            files.update(
                _repo_path(root, child.relative_to(root).as_posix(), "API inventory")
                for child in path.rglob("*.py")
                if child.is_file() and "__pycache__" not in child.parts
            )

    file_paths = tuple(sorted(path.relative_to(root).as_posix() for path in files))
    signature = tuple(
        (path, (root / path).stat().st_mtime_ns, (root / path).stat().st_size)
        for path in file_paths
    )
    package_signature = tuple(
        (module_id, tuple(sorted(roots))) for module_id, roots in sorted(packages.items())
    )
    return _parse_module_import_inventories(str(root), package_signature, file_paths, signature)


@lru_cache(maxsize=8)
def _parse_module_import_inventories(
    root_string: str,
    package_signature: tuple[tuple[str, tuple[str, ...]], ...],
    file_paths: tuple[str, ...],
    signature: tuple[tuple[str, int, int], ...],
) -> dict[str, tuple[list[str], list[str]]]:
    """Parse an unchanged repository import tree once per process."""
    del signature
    root = Path(root_string)
    packages = {module_id: set(roots) for module_id, roots in package_signature}
    package_owners: dict[str, set[str]] = {}
    for module_id, roots in packages.items():
        for package in roots:
            package_owners.setdefault(package, set()).add(module_id)

    api_paths: dict[str, set[str]] = {module_id: set() for module_id in packages}
    caller_paths: dict[str, set[str]] = {module_id: set() for module_id in packages}

    def imported_file(module: str) -> Path | None:
        path = root.joinpath(*module.split("."))
        for candidate in (path / "__init__.py", path.with_suffix(".py")):
            if candidate.is_file():
                return _repo_path(root, candidate.relative_to(root).as_posix(), "API inventory")
        return None

    for relative_path in file_paths:
        # Research tools compose production APIs but are not production callers.
        if relative_path.startswith("research_tools/"):
            continue
        caller = root / relative_path
        caller_package = caller.relative_to(root).parts[0]
        try:
            tree = ast.parse(caller.read_text(encoding="utf-8"), filename=str(caller))
        except (OSError, UnicodeError, SyntaxError):
            continue
        for node in ast.walk(tree):
            imported_files: list[tuple[str, Path | None]] = []
            if isinstance(node, ast.Import):
                imported_files.extend(
                    (alias.name.split(".")[0], imported_file(alias.name)) for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                package = node.module.split(".")[0]
                submodules = (
                    [imported_file(f"{node.module}.{alias.name}") for alias in node.names]
                    if len(node.module.split(".")) == 1
                    else []
                )
                resolved_submodules = [path for path in submodules if path is not None]
                module_path = None if resolved_submodules else imported_file(node.module)
                if resolved_submodules:
                    imported_files.extend((package, path) for path in resolved_submodules)
                elif module_path is not None:
                    imported_files.append((package, module_path))
            for package, api_file in imported_files:
                if package not in package_owners:
                    continue
                for module_id in package_owners[package]:
                    if caller_package in packages[module_id]:
                        continue
                    caller_paths[module_id].add(caller.relative_to(root).as_posix())
                    if api_file is not None:
                        api_paths[module_id].add(api_file.relative_to(root).as_posix())

    return {
        module_id: (sorted(api_paths[module_id]), sorted(caller_paths[module_id]))
        for module_id in packages
    }


def _validate_script_migrations(
    root: Path,
    manifest_path: str,
    module_ids: set[str],
) -> dict[str, Any]:
    """Validate the research script ownership ledger against the live tree."""
    manifest_file = _repo_path(root, manifest_path, "script_migrations")
    if not manifest_file.is_file():
        raise StudyCatalogError(f"script migration manifest does not exist: {manifest_path}")
    manifest = _read_yaml(manifest_file)
    if manifest.get("schema_version") != 1 or not isinstance(manifest.get("scripts"), list):
        raise StudyCatalogError("script migration manifest requires schema_version 1 and scripts")

    expected = {
        path.relative_to(root).as_posix()
        for path in (root / "scripts/research").rglob("*")
        if path.is_file() and path.suffix in {".py", ".sh"} and path.name != "__init__.py"
    }
    registered: set[str] = set()
    targets: set[str] = set()
    present_python_targets: set[str] = set()
    package_roots = {
        module_id: ("tools" if module_id == "repo_tooling" else module_id)
        for module_id in module_ids
    }
    for row in manifest["scripts"]:
        if not isinstance(row, dict):
            raise StudyCatalogError("script migration entries must be mappings")
        path_value = row.get("path")
        if not isinstance(path_value, str) or not path_value.startswith("scripts/research/"):
            raise StudyCatalogError("script migration path must be under scripts/research")
        path = _repo_path(root, path_value, "script migration")
        if not path.is_file() or path.suffix not in {".py", ".sh"} or path.name == "__init__.py":
            raise StudyCatalogError(
                f"script migration path is not an executable research file: {path_value}"
            )
        if path_value in registered:
            raise StudyCatalogError(f"duplicate script migration path: {path_value}")
        registered.add(path_value)

        owner = row.get("owner_module")
        if not isinstance(owner, str) or owner not in module_ids:
            raise StudyCatalogError(f"{path_value} has unknown owner module: {owner}")
        entrypoint = row.get("entrypoint")
        if entrypoint not in _SCRIPT_ENTRYPOINTS or (entrypoint == "shell") != (
            path.suffix == ".sh"
        ):
            raise StudyCatalogError(f"{path_value} has invalid entrypoint: {entrypoint}")
        target = row.get("target")
        if not isinstance(target, str):
            raise StudyCatalogError(f"{path_value} requires a package target")
        owner_package = package_roots[owner]
        if entrypoint == "shell":
            target_path = _repo_path(root, target, path_value)
            package_shell = target.startswith(f"research_tools/{owner_package}/")
            tooling_shell = owner_package == "tools" and target.startswith("tools/research_tools/")
            if target_path.suffix != ".sh" or not (package_shell or tooling_shell):
                raise StudyCatalogError(f"{path_value} has invalid shell target: {target}")
        else:
            if re.fullmatch(
                r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+", target
            ) is None or not target.startswith("research_tools."):
                raise StudyCatalogError(f"{path_value} requires a research_tools target")
        if target in targets:
            raise StudyCatalogError(f"duplicate script migration target: {target}")
        targets.add(target)
        state = row.get("migration_state")
        if state not in _SCRIPT_MIGRATION_STATES:
            raise StudyCatalogError(f"{path_value} has invalid migration_state: {state}")
        if state in {"complete", "compat_wrapper"} and entrypoint != "shell":
            present_python_targets.add(target)
        checks = row.get("tests")
        if (
            not isinstance(checks, list)
            or not checks
            or any(not isinstance(item, str) for item in checks)
        ):
            raise StudyCatalogError(f"{path_value} must name focused tests")
        for check in checks:
            if not _repo_path(root, check, path_value).is_file():
                raise StudyCatalogError(f"{path_value} references missing test: {check}")

        if state in {"complete", "compat_wrapper"}:
            if entrypoint != "shell":
                target_path = root.joinpath(*target.split(".")).with_suffix(".py")
            if not target_path.is_file():
                raise StudyCatalogError(f"{path_value} completed target is missing: {target}")
            wrapper = path.read_text(encoding="utf-8")
            if entrypoint == "shell":
                if len(wrapper) >= 512 or 'exec "$SCRIPT_DIR/' not in wrapper:
                    raise StudyCatalogError(f"{path_value} is not a thin shell wrapper")
            elif (
                len(wrapper) >= 2_000
                or target not in wrapper
                or "_import_module" not in wrapper
                or "__getattr__" not in wrapper
            ):
                raise StudyCatalogError(f"{path_value} is not a thin Python compatibility wrapper")

    if registered != expected:
        raise StudyCatalogError(
            "script migration inventory mismatch: "
            f"missing={sorted(expected - registered)}, extra={sorted(registered - expected)}"
        )
    actual_targets = {
        path.relative_to(root).with_suffix("").as_posix().replace("/", ".")
        for package in set(package_roots.values())
        for path in (root / "research_tools" / package).rglob("*.py")
        if path.is_file() and path.name != "__init__.py"
    }
    if actual_targets != present_python_targets:
        raise StudyCatalogError(
            "research package target inventory mismatch: "
            f"missing={sorted(present_python_targets - actual_targets)}, "
            f"unregistered={sorted(actual_targets - present_python_targets)}"
        )
    return manifest


def validate_study_catalog(
    root: str | Path | None = None,
    master_path: str | Path | None = None,
) -> list[str]:
    """Validate module profiles, registered studies, and their source/test/config paths.

    Returns:
        Registered study IDs in module order.
    """
    repo = Path(root).resolve() if root is not None else repository_root(__file__)
    master_file = (
        Path(master_path).resolve()
        if master_path is not None and Path(master_path).is_absolute()
        else repo / (Path(master_path) if master_path is not None else _DEFAULT_MASTER)
    )
    try:
        master_file.relative_to(repo)
    except ValueError as exc:
        raise StudyCatalogError("study master path must be inside the repository") from exc
    master = _read_yaml(master_file)
    if master.get("schema_version") != 1:
        raise StudyCatalogError("study master schema_version must be 1")
    profile_dir = master.get("profile_dir")
    modules = master.get("modules")
    if not isinstance(profile_dir, str) or not isinstance(modules, dict) or not modules:
        raise StudyCatalogError("study master requires profile_dir and a non-empty modules mapping")
    runtime = master.get("runtime", {})
    if not isinstance(runtime, dict):
        raise StudyCatalogError("runtime must be a mapping when present")
    runtime_config = runtime.get("config")
    if runtime_config is not None and (
        not isinstance(runtime_config, str)
        or not _repo_path(repo, runtime_config, "runtime.config").is_file()
    ):
        raise StudyCatalogError("runtime.config must reference a repository config file")
    script_migrations = master.get("script_migrations")
    if script_migrations is not None and not isinstance(script_migrations, str):
        raise StudyCatalogError("script_migrations must be a repository-relative manifest path")
    evidence_index_path = master.get("evidence_index")
    if evidence_index_path is not None and not isinstance(evidence_index_path, str):
        raise StudyCatalogError("evidence_index must be a repository-relative manifest path")
    workflow = master.get("workflow")
    workflow_modules: dict[str, str] = {}
    if workflow is not None:
        if not isinstance(workflow, dict) or not workflow:
            raise StudyCatalogError("workflow must be a non-empty section mapping")
        for section, section_settings in workflow.items():
            if (
                not isinstance(section, str)
                or re.fullmatch(r"[a-z][a-z0-9_]*", section) is None
                or not isinstance(section_settings, dict)
                or not isinstance(section_settings.get("enabled"), bool)
            ):
                raise StudyCatalogError("workflow sections require an ID and enabled boolean")
            section_modules = section_settings.get("modules")
            if not isinstance(section_modules, list) or any(
                not isinstance(item, str) for item in section_modules
            ):
                raise StudyCatalogError(f"workflow.{section}.modules must be a list of module IDs")
            for module_id in section_modules:
                if module_id in workflow_modules:
                    raise StudyCatalogError(
                        f"workflow module is assigned more than once: {module_id}"
                    )
                workflow_modules[module_id] = section
        if set(workflow_modules) != set(modules):
            raise StudyCatalogError(
                "workflow/module mismatch: "
                f"unassigned={sorted(set(modules) - set(workflow_modules))}, "
                f"unknown={sorted(set(workflow_modules) - set(modules))}"
            )
    acceptance = _acceptance_rules(master)
    if script_migrations is not None:
        _validate_script_migrations(repo, script_migrations, set(modules))

    profile_root = _profile_root(repo, master_file, profile_dir)
    if not profile_root.is_dir():
        raise StudyCatalogError(f"study profile directory does not exist: {profile_root}")
    configured_modules = set(modules)
    profile_modules = {path.stem for path in profile_root.glob("*.yaml")}
    if profile_modules != configured_modules:
        raise StudyCatalogError(
            "master/profile module mismatch: "
            f"missing_profiles={sorted(configured_modules - profile_modules)}, "
            f"unconfigured_profiles={sorted(profile_modules - configured_modules)}"
        )

    profiles = {module_id: _read_yaml(profile_root / f"{module_id}.yaml") for module_id in modules}
    all_source_roots = [
        value for profile in profiles.values() for value in profile.get("source_roots", [])
    ]
    import_inventories = _module_import_inventories(repo, profiles, all_source_roots)

    ids: list[str] = []
    dependencies: dict[str, list[str]] = {}
    declared_config_paths: set[str] = {runtime_config} if isinstance(runtime_config, str) else set()
    if isinstance(script_migrations, str):
        declared_config_paths.add(script_migrations)
    if isinstance(evidence_index_path, str):
        declared_config_paths.add(evidence_index_path)
    for module_id, settings in modules.items():
        if (
            not isinstance(module_id, str)
            or re.fullmatch(r"[a-z][a-z0-9_]*", module_id) is None
            or not isinstance(settings, dict)
        ):
            raise StudyCatalogError("modules must map module IDs to settings")
        if not isinstance(settings.get("enabled"), bool):
            raise StudyCatalogError(f"modules.{module_id}.enabled must be a boolean")
        profile_file = profile_root / f"{module_id}.yaml"
        profile = profiles[module_id]
        if profile.get("module_id") != module_id:
            raise StudyCatalogError(f"{profile_file}: module_id must be {module_id!r}")
        source_roots = _path_list(repo, profile, "source_roots", module_id)
        if not source_roots:
            raise StudyCatalogError(f"{module_id}.source_roots must not be empty")
        module_configs = _path_list(repo, profile, "config_paths", module_id)
        if any(not _repo_path(repo, value, module_id).is_file() for value in module_configs):
            raise StudyCatalogError(f"{module_id}.config_paths must reference files")
        api_paths = _path_list(repo, profile, "api_paths", module_id)
        caller_paths = _path_list(repo, profile, "caller_paths", module_id)
        actual_api_paths, actual_caller_paths = import_inventories[module_id]
        if set(api_paths) != set(actual_api_paths) or set(caller_paths) != set(actual_caller_paths):
            raise StudyCatalogError(
                f"{module_id} API/caller inventory mismatch: "
                f"missing_api={sorted(set(actual_api_paths) - set(api_paths))}, "
                f"extra_api={sorted(set(api_paths) - set(actual_api_paths))}, "
                f"missing_callers={sorted(set(actual_caller_paths) - set(caller_paths))}, "
                f"extra_callers={sorted(set(caller_paths) - set(actual_caller_paths))}"
            )
        declared_config_paths.update(module_configs)
        declared_config_paths.update(_config_glob_paths(repo, profile, module_id))
        _path_list(repo, profile, "test_paths", module_id)
        studies = profile.get("studies")
        if not isinstance(studies, list) or not studies:
            raise StudyCatalogError(f"{module_id}.studies must be a non-empty list")

        study_settings = settings.get("studies", {})
        if not isinstance(study_settings, dict):
            raise StudyCatalogError(f"modules.{module_id}.studies must be a mapping when present")
        if any(not isinstance(key, str) for key in study_settings):
            raise StudyCatalogError(f"modules.{module_id}.studies keys must be study IDs")
        if any(not isinstance(value, bool) for value in study_settings.values()):
            raise StudyCatalogError(f"modules.{module_id}.studies values must be booleans")
        known_study_ids: set[str] = set()
        for study in studies:
            if not isinstance(study, dict):
                raise StudyCatalogError(f"{module_id}.studies entries must be mappings")
            study_id = study.get("id")
            if not isinstance(study_id, str) or not study_id.startswith(f"{module_id}."):
                raise StudyCatalogError(f"study IDs must start with {module_id}.")
            if study_id in ids:
                raise StudyCatalogError(f"duplicate study ID: {study_id}")
            known_study_ids.add(study_id)
            ids.append(study_id)
            if study.get("type") not in _STUDY_TYPES:
                raise StudyCatalogError(f"{study_id}.type must be one of {sorted(_STUDY_TYPES)}")
            audit_tool = study.get("audit_tool")
            if study["type"] == "audit":
                if (
                    not isinstance(audit_tool, str)
                    or re.fullmatch(r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+", audit_tool) is None
                ):
                    raise StudyCatalogError(f"{study_id} audit studies require an audit_tool ID")
            elif audit_tool is not None:
                raise StudyCatalogError(f"{study_id} audit_tool is only valid for audit studies")
            acceptance_rule = study.get("acceptance", acceptance.get(study["type"]))
            if not isinstance(acceptance_rule, str) or not acceptance_rule.strip():
                raise StudyCatalogError(f"{study_id}.acceptance is required for this study type")
            if not isinstance(study.get("question"), str) or not study["question"].strip():
                raise StudyCatalogError(f"{study_id}.question is required")
            prerequisites = study.get("prerequisites", [])
            if not isinstance(prerequisites, list) or any(
                not isinstance(item, str) or not item for item in prerequisites
            ):
                raise StudyCatalogError(f"{study_id}.prerequisites must be a list of study IDs")
            dependencies[study_id] = prerequisites
            if (
                not isinstance(study.get("outputs"), list)
                or not study["outputs"]
                or any(not isinstance(item, str) or not item.strip() for item in study["outputs"])
            ):
                raise StudyCatalogError(f"{study_id}.outputs must be a non-empty list of names")
            source_paths = study.get("source_paths")
            if not isinstance(source_paths, list) or not source_paths:
                raise StudyCatalogError(f"{study_id}.source_paths must identify its source")
            checks = study.get("checks")
            if not isinstance(checks, list) or not checks:
                raise StudyCatalogError(f"{study_id}.checks must list focused checks")
            for key in ("source_paths", "config_paths", "checks"):
                values = study.get(key, [])
                if not isinstance(values, list) or any(
                    not isinstance(item, str) for item in values
                ):
                    raise StudyCatalogError(f"{study_id}.{key} must be a list of repository paths")
                for value in values:
                    path = _repo_path(repo, value, study_id)
                    if not path.exists():
                        raise StudyCatalogError(f"{study_id} references missing path: {value}")
                    if key == "checks" and not path.is_file():
                        raise StudyCatalogError(f"{study_id} check must be a file: {value}")
            declared_config_paths.update(_study_config_paths(repo, study, study_id))
            arms = study.get("arms", [])
            if not isinstance(arms, list):
                raise StudyCatalogError(
                    f"{study_id}.arms must be a list of explicit registered arms"
                )
            if study["type"] == "empirical" and not arms:
                raise StudyCatalogError(
                    f"{study_id} empirical study requires explicit registered arms"
                )
            if study["type"] != "empirical" and arms:
                raise StudyCatalogError(f"{study_id} only empirical studies may declare arms")
            arm_ids: set[str] = set()
            for arm in arms:
                if not isinstance(arm, dict) or not isinstance(arm.get("id"), str):
                    raise StudyCatalogError(f"{study_id}.arms entries require an id")
                if arm["id"] in arm_ids:
                    raise StudyCatalogError(f"{study_id} has duplicate arm ID: {arm['id']}")
                arm_ids.add(arm["id"])
                if not isinstance(arm.get("config_paths"), list) or not arm["config_paths"]:
                    raise StudyCatalogError(f"{study_id} arm {arm['id']} requires config_paths")
                if (
                    not isinstance(arm.get("factors"), list)
                    or not arm["factors"]
                    or any(not isinstance(item, str) or not item.strip() for item in arm["factors"])
                ):
                    raise StudyCatalogError(f"{study_id} arm {arm['id']} requires declared factors")
                for value in arm["config_paths"]:
                    if (
                        not isinstance(value, str)
                        or not _repo_path(repo, value, study_id).is_file()
                    ):
                        raise StudyCatalogError(
                            f"{study_id} arm references missing config: {value}"
                        )
                    declared_config_paths.add(value)
        unknown_toggles = set(study_settings) - known_study_ids
        if unknown_toggles:
            raise StudyCatalogError(
                f"modules.{module_id}.studies has unregistered IDs: {sorted(unknown_toggles)}"
            )
        coverage = _source_coverage(repo, profile, module_id, known_study_ids)
        mapped_studies = {
            study_id for scope in coverage["source_scopes"] for study_id in scope["study_ids"]
        }
        unmapped_studies = sorted(known_study_ids - mapped_studies)
        if unmapped_studies:
            raise StudyCatalogError(f"{module_id} studies have no source scope: {unmapped_studies}")
    for study_id, prerequisites in dependencies.items():
        unknown = sorted(set(prerequisites) - set(ids))
        if unknown:
            raise StudyCatalogError(f"{study_id} has unregistered prerequisites: {unknown}")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(study_id: str) -> None:
        if study_id in visiting:
            raise StudyCatalogError(f"study prerequisite cycle includes {study_id}")
        if study_id in visited:
            return
        visiting.add(study_id)
        for prerequisite in dependencies[study_id]:
            visit(prerequisite)
        visiting.remove(study_id)
        visited.add(study_id)

    for study_id in dependencies:
        visit(study_id)
    if isinstance(evidence_index_path, str):
        _validate_evidence_index(repo, evidence_index_path, set(ids))
    study_profile_files = {
        "config/studies/default.yaml",
        *({script_migrations} if isinstance(script_migrations, str) else set()),
        *({evidence_index_path} if isinstance(evidence_index_path, str) else set()),
        *(path.relative_to(repo).as_posix() for path in profile_root.glob("*.yaml")),
    }
    configured_files = {
        path.relative_to(repo).as_posix()
        for path in (repo / "config").rglob("*")
        if path.is_file() and path.suffix in {".yaml", ".yml", ".csv", ".txt"}
    } - study_profile_files
    missing_configs = sorted(configured_files - declared_config_paths)
    if missing_configs:
        raise StudyCatalogError(f"unassigned config files: {missing_configs}")
    return ids


def build_study_plan(
    root: str | Path | None = None,
    master_path: str | Path | None = None,
    *,
    include_inventory: bool = False,
) -> dict[str, Any]:
    """Resolve the enabled study plan without executing it."""
    from research_tools.studies.study_plan import build_study_plan as build

    return build(root, master_path, include_inventory=include_inventory)
