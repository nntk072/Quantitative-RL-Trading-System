"""Build a read-only inventory of code, tests, config keys, and research evidence."""

from __future__ import annotations

import ast
import configparser
import hashlib
import json
import os
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

_CONFIG_SUFFIXES = {".ini", ".json", ".toml", ".yaml", ".yml"}
_CONFIG_NAMES = {".env.example", "Dockerfile", "Makefile"}
_SKIP_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    ".venv-arm",
    ".venv-mi210",
    ".venv-v100",
    ".venv-x86",
    ".codex",
    "__pycache__",
    "data",
    "logs",
    "outputs",
}


class StudyInventoryError(ValueError):
    """Raised when a tracked source, config, test, or evidence input cannot be inventoried."""


class UniqueKeyLoader(yaml.SafeLoader):  # type: ignore[misc]  # PyYAML does not type SafeLoader.
    """Safe YAML loader that rejects duplicate keys instead of overwriting them."""

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
        self.flatten_mapping(node)
        mapping: dict[Any, Any] = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            try:
                duplicate = key in mapping
            except TypeError as exc:
                raise yaml.constructor.ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    "found an unhashable key",
                    key_node.start_mark,
                ) from exc
            if duplicate:
                raise yaml.constructor.ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    f"found duplicate key {key!r}",
                    key_node.start_mark,
                )
            mapping[key] = self.construct_object(value_node, deep=deep)
        return mapping


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _repo_files(root: Path, *, suffixes: set[str], names: set[str] | None = None) -> list[Path]:
    found: list[Path] = []
    for directory, child_dirs, filenames in os.walk(root, followlinks=False):
        child_dirs[:] = sorted(name for name in child_dirs if name not in _SKIP_DIRS)
        current = Path(directory)
        for name in filenames:
            path = current / name
            if path.suffix.lower() in suffixes or (names is not None and name in names):
                found.append(path)
    return sorted(found)


def _symbols(path: Path) -> list[dict[str, Any]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, UnicodeError, SyntaxError):
        return []
    rows: list[dict[str, Any]] = []

    def visit(body: list[ast.stmt], prefix: str = "") -> None:
        for node in body:
            if not isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            name = f"{prefix}.{node.name}" if prefix else node.name
            kind = "class" if isinstance(node, ast.ClassDef) else "function"
            rows.append(
                {
                    "name": name,
                    "kind": kind,
                    "line": node.lineno,
                    "end_line": node.end_lineno,
                }
            )
            visit(node.body, name)

    visit(tree.body)
    return rows


def _source_inventory(root: Path, profiles: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    modules: list[dict[str, Any]] = []
    file_count = 0
    symbol_count = 0
    direct_owners: dict[str, set[str]] = {}
    for profile in profiles.values():
        for study in profile["studies"]:
            for source_path in study["source_paths"]:
                direct_owners.setdefault(source_path, set()).add(study["id"])
    for module_id, profile in profiles.items():
        source_roots = [root / value for value in profile["source_roots"]]
        files: set[Path] = set()
        for source_root in source_roots:
            if source_root.is_file() and source_root.suffix == ".py":
                files.add(source_root)
            elif source_root.is_dir():
                files.update(
                    path
                    for path in source_root.rglob("*.py")
                    if path.is_file() and "__pycache__" not in path.parts
                )
        scopes = profile["source_scopes"]
        units: list[dict[str, Any]] = []
        for path in sorted(files):
            relative = path.relative_to(root).as_posix()
            owners = sorted(
                {
                    study_id
                    for scope in scopes
                    if relative == scope["path"]
                    or relative.startswith(f"{scope['path'].rstrip('/')}/")
                    for study_id in scope["study_ids"]
                }
                | {
                    study_id
                    for source_path, study_ids in direct_owners.items()
                    if relative == source_path or relative.startswith(f"{source_path.rstrip('/')}/")
                    for study_id in study_ids
                }
            )
            symbols = _symbols(path)
            units.append(
                {
                    "path": relative,
                    "sha256": _sha256(path),
                    "study_ids": owners,
                    "symbols": symbols,
                }
            )
            symbol_count += len(symbols)
        modules.append({"id": module_id, "files": units})
        file_count += len(units)
    return {"file_count": file_count, "symbol_count": symbol_count, "modules": modules}


def _flatten_keys(value: Any, prefix: str = "") -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if isinstance(value, Mapping):
        if not value and prefix:
            rows.append({"path": prefix, "value_type": "mapping"})
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            rows.extend(_flatten_keys(child, path))
    elif isinstance(value, list):
        if not value and prefix:
            rows.append({"path": prefix, "value_type": "list"})
        for index, child in enumerate(value):
            rows.extend(_flatten_keys(child, f"{prefix}[{index}]"))
    elif prefix:
        if value is None:
            kind = "null"
        elif isinstance(value, bool):
            kind = "boolean"
        elif isinstance(value, (int, float)):
            kind = "number"
        else:
            kind = "string"
        rows.append({"path": prefix, "value_type": kind})
    return rows


def _config_keys(path: Path) -> list[dict[str, str]]:
    try:
        suffix = path.suffix.lower()
        if suffix in {".yaml", ".yml"}:
            value = yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueKeyLoader)
        elif suffix == ".json":
            value = json.loads(path.read_text(encoding="utf-8"))
        elif suffix == ".toml":
            value = tomllib.loads(path.read_text(encoding="utf-8"))
        elif suffix == ".ini":
            parser = configparser.ConfigParser()
            parser.read(path, encoding="utf-8")
            value = {section: dict(parser.items(section)) for section in parser.sections()}
        elif path.name == ".env.example":
            return [
                {"path": line.split("=", 1)[0].strip(), "value_type": "environment"}
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.lstrip().startswith("#") and "=" in line
            ]
        else:
            return []
    except (OSError, UnicodeError, ValueError, yaml.YAMLError, configparser.Error) as exc:
        raise StudyInventoryError(f"cannot parse config inventory input {path}: {exc}") from exc
    return _flatten_keys(value)


def _config_inventory(
    root: Path,
    profiles: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    owners_by_path: dict[str, dict[str, set[str]]] = {}
    studies_by_module = {
        module_id: {study["id"] for study in profile["studies"]}
        for module_id, profile in profiles.items()
    }

    def add_owner(path: str, module_id: str, study_id: str | None = None) -> None:
        row = owners_by_path.setdefault(path, {"modules": set(), "studies": set()})
        row["modules"].add(module_id)
        if study_id:
            row["studies"].add(study_id)

    for module_id, profile in profiles.items():
        paths = set(profile.get("config_paths", []))
        for pattern in profile.get("config_globs", []):
            paths.update(path.relative_to(root).as_posix() for path in root.glob(pattern))
        for path in paths:
            for study_id in studies_by_module[module_id]:
                add_owner(path, module_id, study_id)
        for study in profile["studies"]:
            study_paths = set(study.get("config_paths", []))
            for pattern in study.get("config_globs", []):
                study_paths.update(path.relative_to(root).as_posix() for path in root.glob(pattern))
            for arm in study.get("arms", []):
                study_paths.update(arm.get("config_paths", []))
            for path in study_paths:
                add_owner(path, module_id, study["id"])

    candidates = _repo_files(
        root,
        suffixes=_CONFIG_SUFFIXES | {".csv", ".txt"},
        names=_CONFIG_NAMES,
    )
    candidates = [
        path
        for path in candidates
        if not {"docs", "evidence", "tests"}.intersection(path.relative_to(root).parts[:-1])
    ]
    # Project-wide build and tool settings have no package directory to infer from.
    fallback_module = "repo_tooling" if "repo_tooling" in profiles else next(iter(profiles))
    for path in candidates:
        relative = path.relative_to(root).as_posix()
        if relative in owners_by_path:
            continue
        parts = Path(relative).parts
        inferred = parts[0] if parts and parts[0] in profiles else fallback_module
        if len(parts) > 1 and parts[0] == "scripts" and parts[1] == "compute":
            inferred = "compute"
        elif len(parts) > 1 and parts[0] == "schemas":
            inferred = "experiments" if "trial_ledger" in parts[-1] else "artifacts"
        elif len(parts) > 1 and parts[0] == "orchestra":
            inferred = "orchestra"
        if relative.startswith("config/studies/profiles/"):
            inferred = Path(relative).stem
        elif (
            relative == "config/studies/default.yaml"
            or relative == "config/studies/script_migrations.yaml"
        ):
            for module_id in profiles:
                for study_id in studies_by_module[module_id]:
                    add_owner(relative, module_id, study_id)
            continue
        if inferred not in profiles:
            inferred = fallback_module
        for study_id in studies_by_module[inferred]:
            add_owner(relative, inferred, study_id)

    rows: list[dict[str, Any]] = []
    key_count = 0
    for path in candidates:
        relative = path.relative_to(root).as_posix()
        owners = owners_by_path.get(relative, {"modules": set(), "studies": set()})
        keys = _config_keys(path)
        rows.append(
            {
                "path": relative,
                "sha256": _sha256(path),
                "module_ids": sorted(owners["modules"]),
                "study_ids": sorted(owners["studies"]),
                "keys": keys,
            }
        )
        key_count += len(keys)
    return {"file_count": len(rows), "key_count": key_count, "files": rows}


def _test_inventory(root: Path, profiles: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    module_by_path: dict[str, set[str]] = {}
    studies_by_test: dict[str, set[str]] = {}
    all_studies: dict[str, set[str]] = {}
    for module_id, profile in profiles.items():
        module_studies = {study["id"] for study in profile["studies"]}
        all_studies[module_id] = module_studies
        for caller in profile.get("caller_paths", []):
            if caller.startswith("tests/"):
                module_by_path.setdefault(caller, set()).add(module_id)
        for study in profile["studies"]:
            for check in study["checks"]:
                module_by_path.setdefault(check, set()).add(module_id)
                studies_by_test.setdefault(check, set()).add(study["id"])
    rows: list[dict[str, Any]] = []
    for path in sorted((root / "tests").rglob("test_*.py")):
        if "__pycache__" in path.parts:
            continue
        relative = path.relative_to(root).as_posix()
        module_ids = sorted(module_by_path.get(relative, set()))
        study_ids = sorted(studies_by_test.get(relative, set()))
        if not study_ids:
            study_ids = sorted(
                study_id for module_id in module_ids for study_id in all_studies[module_id]
            )
        rows.append(
            {
                "path": relative,
                "module_ids": module_ids,
                "study_ids": study_ids,
                "sha256": _sha256(path),
            }
        )
    return {
        "file_count": len(rows),
        "unmapped_files": [row["path"] for row in rows if not row["module_ids"]],
        "files": rows,
    }


def build_repository_inventory(
    root: str | Path,
    profiles: Mapping[str, Mapping[str, Any]],
    evidence_index_path: str,
) -> dict[str, Any]:
    """Return detailed static inventories without reading run data or output caches."""
    repo = Path(root).resolve()
    evidence_index = repo / evidence_index_path
    evidence_catalog = yaml.load(evidence_index.read_text(encoding="utf-8"), Loader=UniqueKeyLoader)
    evidence_rows = []
    for item in evidence_catalog["items"]:
        path = repo / item["path"]
        evidence_rows.append(
            {
                **item,
                "sha256": _sha256(path),
                "size_bytes": path.stat().st_size,
            }
        )
    source = _source_inventory(repo, profiles)
    config = _config_inventory(repo, profiles)
    tests = _test_inventory(repo, profiles)
    return {
        "schema_version": 1,
        "source": source,
        "config": config,
        "tests": tests,
        "evidence": {
            "index_path": evidence_index_path,
            "index_sha256": _sha256(evidence_index),
            "file_count": len(evidence_rows),
            "files": evidence_rows,
        },
    }
