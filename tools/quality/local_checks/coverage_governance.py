"""Trusted local baseline candidates, source inventory and exclusion review."""

from __future__ import annotations

import io
import re
import tokenize
import tomllib
from pathlib import Path
from typing import Any

from tools.quality.coverage_report import PRODUCT_PACKAGES, aggregate_coverage
from tools.quality.local_checks.coverage_tools import validate_coverage_report
from tools.quality.local_checks.run_evidence import (
    ROOT,
    quality_file_sha256,
    quality_git,
    quality_source_paths,
    read_quality_json,
    verify_quality_manifest,
)


def verified_baseline_candidate(manifest_path: Path, ref: str) -> dict[str, Any]:
    """Validate a clean, complete, commit-bound local measurement without promoting it."""
    if ref.startswith("-"):
        raise ValueError("Invalid trusted ref")
    verify_quality_manifest(manifest_path)
    manifest = read_quality_json(manifest_path)
    commit = quality_git("rev-parse", "--verify", ref + "^{commit}").decode().strip()
    tree = quality_git("rev-parse", "--verify", commit + "^{tree}").decode().strip()
    result = manifest["result"]
    if (
        manifest.get("source_commit") != commit
        or manifest.get("git_tree_sha") != tree
        or manifest.get("dirty") is not False
        or manifest.get("action") != "coverage"
        or manifest.get("execution_status") not in {"ok", "findings"}
        or result.get("scope") != "full"
    ):
        raise ValueError("Baseline requires a successful clean full run of the chosen ref")
    root = manifest_path.parent
    for name, key in (
        (".coverage", "coverage_sha256"),
        ("test-inventory.json", "inventory_sha256"),
        ("coverage.ini", "coverage_config_sha256"),
    ):
        if result[key] != quality_file_sha256(root / name):
            raise ValueError(f"Baseline evidence hash mismatch: {name}")
    lock = quality_git("show", f"{commit}:uv.lock")
    import hashlib

    if hashlib.sha256(lock).hexdigest() != manifest.get("lock_sha256"):
        raise ValueError("Baseline lock does not match its Git commit")
    raw = read_quality_json(root / "coverage.json")
    validate_coverage_report(raw, True)
    return {
        "status": "ok",
        "source_commit": commit,
        "git_tree_sha": tree,
        "manifest_sha256": quality_file_sha256(manifest_path),
        "summary": aggregate_coverage(raw),
        "promoted": False,
        "qualification": "Local integrity checks are not a remote authenticity attestation.",
    }


def source_quality_inventory() -> dict[str, Any]:
    """Classify every tracked or unignored file by role and applicable language."""
    rows = []
    languages = {".py": "python", ".rs": "rust", ".c": "c", ".cpp": "cpp", ".cc": "cpp",
                 ".cxx": "cpp", ".cu": "cuda", ".cuh": "cuda", ".sql": "sql",
                 ".ts": "typescript", ".tsx": "typescript", ".js": "javascript", ".jsx": "javascript",
                 ".sh": "shell", ".yaml": "configuration", ".yml": "configuration",
                 ".toml": "configuration"}
    for name in quality_source_paths():
        head = name.split("/")[0]
        role = (
            "product" if head in PRODUCT_PACKAGES else
            "test" if head == "tests" else
            "research" if head in {"research_tools", "evidence"} or name.startswith("scripts/research/") else
            "tooling" if head in {"tools", "scripts", ".agents", ".github"} else
            "configuration" if head == "config" else
            "generated" if name.startswith("docs/api/generated/") else
            "vendored" if head in {"vendor", "third_party"} else "other"
        )
        language = languages.get(Path(name).suffix.lower(), "other")
        rows.append({"path": name, "role": role, "language": language,
                     "symlink": (ROOT / name).is_symlink()})
    return {"status": "ok", "count": len(rows), "files": rows}


def _coverage_pragmas(text: str) -> list[dict[str, Any]]:
    """Extract coverage exclusions only from real Python comment tokens."""
    rows = []
    for tok in tokenize.generate_tokens(io.StringIO(text).readline):
        if tok.type == tokenize.COMMENT and re.search(r"pragma:\s*no (cover|branch)\b", tok.string):
            rows.append({"line": tok.start[0], "comment": tok.string})
    return rows


def audit_quality_exclusions(base: str) -> dict[str, Any]:
    """Compare current coverage pragmas and config with a trusted local Git ref."""
    if base.startswith("-"):
        raise ValueError("Invalid base")
    merged = quality_git("merge-base", base, "HEAD").decode().strip()
    old_names = set(quality_git("ls-tree", "-r", "--name-only", merged).decode().splitlines())
    current = {}
    prior = {}
    for name in sorted(set(quality_source_paths()) | old_names):
        if name.split("/")[0] not in PRODUCT_PACKAGES or not name.endswith(".py"):
            continue
        path = ROOT / name
        if path.is_file() and not path.is_symlink():
            current[name] = _coverage_pragmas(path.read_text())
        if name in old_names and current.get(name):
            prior[name] = _coverage_pragmas(quality_git("show", f"{merged}:{name}").decode())
    changed = []
    for name, rows in current.items():
        # Match comment text and location; a moved pragma remains a review lead.
        for row in rows:
            if row not in prior.get(name, []):
                changed.append({"path": name, **row})
    cfg = tomllib.loads((ROOT / "pyproject.toml").read_text())["tool"]["coverage"]
    old_cfg = tomllib.loads(quality_git("show", f"{merged}:pyproject.toml").decode())["tool"]["coverage"]
    doc = (ROOT / "docs/architecture/coverage-policy.md").read_text()
    undocumented = [{"path": name, **row} for name, rows in current.items()
                    for row in rows if f"`{name}`" not in doc]
    findings = bool(changed or undocumented or cfg != old_cfg)
    return {"status": "findings" if findings else "ok", "new_or_moved": changed,
            "undocumented": undocumented, "configuration_changed": cfg != old_cfg,
            "base": merged, "inventory": {k: v for k, v in current.items() if v}}
