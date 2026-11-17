"""Resolve enabled studies and content identities without executing them."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from configuration.hashing import config_sha256
from configuration.paths import repository_root
from research_tools.studies.study_catalog import (
    _DEFAULT_MASTER,
    _acceptance_rules,
    _config_glob_paths,
    _profile_root,
    _read_yaml,
    _repo_path,
    _source_coverage,
    _study_config_paths,
    validate_study_catalog,
)
from research_tools.studies.study_inventory import build_repository_inventory


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_sha256(root: Path, value: str) -> str:
    """Hash a declared file or directory, including stable relative names."""
    path = _repo_path(root, value, "source")
    if path.is_file():
        return _file_sha256(path)
    if not path.is_dir():
        raise ValueError(f"source path is not a file or directory: {value}")

    digest = hashlib.sha256()
    for child in sorted(path.rglob("*")):
        if child.is_dir() or child.suffix == ".pyc" or "__pycache__" in child.parts:
            continue
        child = _repo_path(root, child.relative_to(root).as_posix(), "source")
        if child.is_file():
            relative = child.relative_to(path).as_posix().encode("utf-8")
            content = child.read_bytes()
            digest.update(len(relative).to_bytes(8, "big"))
            digest.update(relative)
            digest.update(len(content).to_bytes(8, "big"))
            digest.update(content)
    return digest.hexdigest()


def _config_identity(root: Path, values: list[str]) -> dict[str, str]:
    return {value: _file_sha256(_repo_path(root, value, "config")) for value in values}


def _migration_target_path(root: Path, row: dict[str, Any]) -> tuple[str, Path]:
    target = row["target"]
    if row["entrypoint"] == "shell":
        return target, _repo_path(root, target, row["path"])
    path = root.joinpath(*target.split(".")).with_suffix(".py")
    return target, _repo_path(root, path.relative_to(root).as_posix(), row["path"])


def _study_enabled(module_settings: dict[str, Any], study: dict[str, Any]) -> bool:
    toggles = module_settings.get("studies", {})
    return bool(module_settings.get("enabled", False) and toggles.get(study["id"], True))


def build_study_plan(
    root: str | Path | None = None,
    master_path: str | Path | None = None,
    *,
    include_inventory: bool = False,
) -> dict[str, Any]:
    """Resolve the enabled study plan and hashes without executing any study."""
    repo = Path(root).resolve() if root is not None else repository_root(__file__)
    master_file = (
        Path(master_path).resolve()
        if master_path is not None and Path(master_path).is_absolute()
        else repo / (Path(master_path) if master_path is not None else _DEFAULT_MASTER)
    )
    study_ids = validate_study_catalog(repo, master_file)
    master = _read_yaml(master_file)
    acceptance = _acceptance_rules(master)
    profile_root = _profile_root(repo, master_file, master["profile_dir"])
    master_sha256 = _file_sha256(master_file)
    workflow = master.get("workflow", {})
    workflow_by_module = {
        module_id: section
        for section, settings in workflow.items()
        for module_id in settings["modules"]
    }
    runtime_config = master.get("runtime", {}).get("config")
    runtime_config_sha256 = (
        _file_sha256(_repo_path(repo, runtime_config, "runtime.config")) if runtime_config else None
    )
    migration_manifest_path = master.get("script_migrations")
    migration_rows: list[dict[str, Any]] = []
    if isinstance(migration_manifest_path, str):
        migration_manifest = _read_yaml(
            _repo_path(repo, migration_manifest_path, "script_migrations")
        )
        migration_rows = migration_manifest["scripts"]

    modules: list[dict[str, Any]] = []
    profiles: dict[str, dict[str, Any]] = {}
    selected: list[dict[str, Any]] = []
    for module_id, module_settings in master["modules"].items():
        profile = _read_yaml(profile_root / f"{module_id}.yaml")
        profiles[module_id] = profile
        module_study_ids = {study["id"] for study in profile["studies"]}
        coverage = _source_coverage(repo, profile, module_id, module_study_ids)
        config_paths = sorted(
            set(profile.get("config_paths", [])) | set(_config_glob_paths(repo, profile, module_id))
        )
        config_hashes = _config_identity(repo, config_paths)
        profile_path = profile_root / f"{module_id}.yaml"
        profile_sha256 = _file_sha256(profile_path)
        workflow_section = workflow_by_module.get(module_id)
        workflow_enabled = (
            workflow[workflow_section]["enabled"] if workflow_section is not None else True
        )
        module_enabled = bool(module_settings["enabled"] and workflow_enabled)
        module_targets = {
            target: _file_sha256(path)
            for row in migration_rows
            if row["owner_module"] == module_id
            for target, path in [_migration_target_path(repo, row)]
            if path.is_file()
        }
        studies: list[dict[str, Any]] = []
        for raw_study in profile["studies"]:
            study = dict(raw_study)
            enabled = module_enabled and _study_enabled(module_settings, study)
            study_configs = _study_config_paths(repo, study, study["id"])
            config_hashes_for_study = _config_identity(repo, study_configs)
            source_paths = study["source_paths"]
            source_hashes = {value: _source_sha256(repo, value) for value in source_paths}
            migration_target_hashes = {
                target: digest
                for source_path in source_paths
                for row in migration_rows
                if row["path"] == source_path
                or row["path"].startswith(f"{source_path.rstrip('/')}/")
                for target, path in [_migration_target_path(repo, row)]
                if path.is_file()
                for digest in [_file_sha256(path)]
            }
            arms = []
            arm_config_hashes: dict[str, str] = {}
            for arm in study.get("arms", []):
                arm_row = dict(arm)
                arm_config_sha256 = config_sha256(_config_identity(repo, arm["config_paths"]))
                arm_config_hashes[arm["id"]] = arm_config_sha256
                arm_row["config_sha256"] = arm_config_sha256
                arms.append(arm_row)
            study["arms"] = arms
            study["enabled"] = enabled
            study["module_id"] = module_id
            study["acceptance_rule"] = study.get("acceptance", acceptance.get(study["type"], ""))
            study["config_paths"] = study_configs
            study["config_sha256"] = config_hashes_for_study
            study["resolved_config_paths"] = study_configs
            study["effective_config_sha256"] = config_sha256(
                {"study": config_hashes_for_study, "arms": arm_config_hashes}
            )
            study["source_sha256"] = source_hashes
            study["migration_target_sha256"] = migration_target_hashes
            study["effective_inputs_sha256"] = config_sha256(
                {
                    "master_sha256": master_sha256,
                    "profile_sha256": profile_sha256,
                    "study": raw_study,
                    "config_sha256": config_hashes_for_study,
                    "arm_config_sha256": arm_config_hashes,
                    "source_sha256": source_hashes,
                    "migration_target_sha256": migration_target_hashes,
                }
            )
            studies.append(study)
            if enabled:
                selected.append(study)

        modules.append(
            {
                "id": module_id,
                "enabled": module_enabled,
                "workflow_section": workflow_section,
                "source_roots": profile["source_roots"],
                "source_file_count": coverage["source_file_count"],
                "uncovered_source_files": coverage["uncovered_source_files"],
                "source_scopes": coverage["source_scopes"],
                "api_paths": profile.get("api_paths", []),
                "caller_paths": profile.get("caller_paths", []),
                "config_paths": config_paths,
                "config_sha256": config_hashes,
                "profile_sha256": profile_sha256,
                "research_tool_targets_sha256": module_targets,
                "test_paths": profile.get("test_paths", []),
                "studies": studies,
            }
        )

    result: dict[str, Any] = {
        "schema_version": 1,
        "master_path": master_file.relative_to(repo).as_posix(),
        "master_sha256": master_sha256,
        "workflow": workflow,
        "runtime_config": runtime_config,
        "runtime_config_sha256": runtime_config_sha256,
        "script_migrations": {
            "manifest_path": migration_manifest_path,
            "manifest_sha256": (
                _file_sha256(_repo_path(repo, migration_manifest_path, "script_migrations"))
                if isinstance(migration_manifest_path, str)
                else None
            ),
            "count": len(migration_rows),
            "completed_count": sum(
                row.get("migration_state") == "complete" for row in migration_rows
            ),
        },
        "catalog_study_ids": study_ids,
        "modules": modules,
        "selected_studies": selected,
        "execution": "not_started",
    }
    evidence_index_path = master.get("evidence_index")
    if include_inventory and isinstance(evidence_index_path, str):
        result["inventory"] = build_repository_inventory(repo, profiles, evidence_index_path)
    return result
