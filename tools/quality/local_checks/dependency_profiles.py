"""Isolated CPU, GPU and analyzer lock resolution and cache namespaces."""

from __future__ import annotations

import re
import shutil
import tomllib
from pathlib import Path
from typing import Any

from tools.quality.local_checks.run_evidence import (
    OUTPUT, ROOT, quality_file_sha256, read_quality_json, run_quality_process, write_quality_json,
)

ANALYZER_REQUIREMENTS = ("diff-cover", "semgrep", "bandit", "vulture", "radon", "xenon",
    "pip-audit", "checkov", "sqlfluff", "duckdb", "pyarrow", "atheris")


def _profile_lock_versions(path: Path) -> dict[str, set[str]]:
    """Read each package's exact version set from a uv lock."""
    rows: dict[str, set[str]] = {}
    for row in tomllib.loads(path.read_text())["package"]:
        rows.setdefault(row["name"], set()).add(row["version"])
    return rows


def _accelerator_package(name: str) -> bool:
    """Identify accelerator-dependent packages separately from ordinary dependency drift."""
    return name == "torch" or name.startswith(("nvidia-", "cuda-", "triton"))


def dependency_profile_drift(lock: Path) -> dict[str, Any]:
    """Report non-accelerator drift from the project's authoritative lock."""
    old, new = _profile_lock_versions(ROOT / "uv.lock"), _profile_lock_versions(lock)
    return {
        "non_accelerator_drift": {n: {"project": sorted(old.get(n,set())), "profile": sorted(new.get(n,set()))}
            for n in sorted(old.keys() | new.keys()) if not _accelerator_package(n) and old.get(n) != new.get(n)},
        "torch": sorted(new.get("torch", set())),
        "accelerator_packages": sorted(n for n in new if _accelerator_package(n) and n != "torch"),
    }


def configure_dependency_profile(
    out: Path, timeout: int, profile: str, action: str, allow_drift: bool,
) -> dict[str, Any]:
    """Resolve or synchronize an isolated environment only on explicit request."""
    if profile not in {"analyzers", "cpu", "gpu"} or action not in {"plan", "resolve", "sync"}:
        raise ValueError("Unknown dependency profile or operation")
    base = OUTPUT / "envs" / profile
    if base.is_symlink() or not base.resolve().is_relative_to(OUTPUT.resolve()):
        raise ValueError("Unsafe environment location")
    env = base / ".venv"
    python = env / "bin/python"
    lock = base / ("requirements.lock" if profile == "analyzers" else "uv.lock")
    project_hash = quality_file_sha256(ROOT / "uv.lock")
    config_hash = quality_file_sha256(ROOT / "pyproject.toml")
    result: dict[str, Any] = {"status": "ok", "profile": profile, "action": action,
        "directory": str(base), "python": str(python), "lock": str(lock),
        "project_lock_sha256": project_hash, "network_may_be_used": action != "plan"}
    if action == "plan":
        return {**result, "lock_sha256": quality_file_sha256(lock) if lock.is_file() else None}
    base.mkdir(parents=True, exist_ok=True)
    if action == "resolve":
        if profile == "analyzers":
            inputs = base / "requirements.in"
            inputs.write_text("\n".join(ANALYZER_REQUIREMENTS) + "\n")
            result["execution"] = run_quality_process(["uv", "pip", "compile", str(inputs),
                "--python-version", "3.12", "--generate-hashes", "--output-file", str(lock)],
                out / "resolve.log", timeout)
        else:
            source = (ROOT / "pyproject.toml").read_text()
            if profile == "cpu":
                source, count = re.subn(r'(?m)^torch = \{ index = "pytorch-gpu" \}$',
                                         'torch = { index = "pytorch-cpu" }', source)
                if count != 1:
                    raise ValueError("CPU torch source changed; review the project configuration")
            tomllib.loads(source)
            (base / "pyproject.toml").write_text(source)
            for name in ("README.md", "LICENSE"):
                if (ROOT / name).is_file():
                    shutil.copyfile(ROOT / name, base / name)
            shutil.copyfile(ROOT / "uv.lock", lock)
            result["execution"] = (run_quality_process(["uv", "lock", "--project", str(base)],
                out / "resolve.log", timeout) if profile == "cpu" else {"status": "ok"})
        if result["execution"]["status"] != "ok" or not lock.is_file():
            return {**result, "status": "incomplete"}
        if profile != "analyzers":
            result.update(dependency_profile_drift(lock))
            if profile == "cpu" and (result["accelerator_packages"] or not result["torch"] or
                                     any("+cpu" not in v for v in result["torch"])):
                return {**result, "status": "incomplete", "reason": "Resolved CPU lock still requires accelerators"}
        write_quality_json(base / "resolution.json", {"project_lock_sha256": project_hash,
            "project_configuration_sha256": config_hash, "lock_sha256": quality_file_sha256(lock),
            "profile": profile})
    else:
        receipt = read_quality_json(base / "resolution.json")
        if (receipt["project_lock_sha256"] != project_hash or receipt["project_configuration_sha256"] != config_hash
            or receipt["lock_sha256"] != quality_file_sha256(lock) or receipt["profile"] != profile):
            raise ValueError("Dependency profile resolution is stale or modified")
        if profile == "analyzers":
            if not python.is_file():
                created = run_quality_process(["uv", "venv", "--python", "3.12", str(env)],
                                              out / "venv.log", timeout)
                if created["status"] != "ok":
                    return {**result, "status": "incomplete", "execution": created}
            command = ["uv", "pip", "sync", "--python", str(python), "--require-hashes", str(lock)]
        else:
            result.update(dependency_profile_drift(lock))
            if result["non_accelerator_drift"] and not allow_drift:
                return {**result, "status": "not_run", "reason": "Review non-accelerator dependency drift"}
            if profile == "cpu" and result["accelerator_packages"]:
                raise ValueError("CPU profile requires accelerators")
            command = ["uv", "sync", "--project", str(base), "--frozen", "--extra", "dev", "--no-install-project"]
        result["execution"] = run_quality_process(command, out / "sync.log", timeout,
                                                   env={"UV_PROJECT_ENVIRONMENT": str(env)})
        result["status"] = result["execution"]["status"]
    if quality_file_sha256(ROOT / "uv.lock") != project_hash or quality_file_sha256(ROOT / "pyproject.toml") != config_hash:
        raise RuntimeError("Primary project dependency configuration unexpectedly changed")
    result["lock_sha256"] = quality_file_sha256(lock)
    return result
