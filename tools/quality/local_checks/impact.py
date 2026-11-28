"""Advisory impacted-test selection from coverage contexts and import dependencies."""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any

from coverage import CoverageData


def _impact_git(root: Path, *args: str) -> str:
    """Run a read-only Git query in the selected checkout."""
    return subprocess.check_output(["git", *args], cwd=root).decode()


def changed_paths(root: Path, base: str) -> tuple[str, list[str]]:
    """Include committed, staged, unstaged and untracked paths; keep rename endpoints."""
    if base.startswith("-"):
        raise ValueError("Invalid base ref")
    merge_base = _impact_git(root, "merge-base", base, "HEAD").strip()
    tracked = _impact_git(root, "diff", "--no-renames", "--name-only", "-z", merge_base, "--")
    untracked = _impact_git(root, "ls-files", "--others", "--exclude-standard", "-z")
    return merge_base, sorted(set(filter(None, (tracked + untracked).split("\0"))))


def _python_module_name(path: str) -> str:
    """Translate a Python source path into its import name."""
    return path.removesuffix(".py").removesuffix("/__init__").replace("/", ".")


def _module_prefixes(module: str) -> set[str]:
    """Return all package prefixes of a module name."""
    parts = module.split(".")
    return {".".join(parts[:i]) for i in range(1, len(parts) + 1)}


def _source_import_names(path: str, tree: ast.AST) -> set[str]:
    """Extract explicit absolute and relative imports."""
    names: set[str] = set()
    package = (
        _python_module_name(path)
        if path.endswith("/__init__.py")
        else _python_module_name(path).rpartition(".")[0]
    )
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.update(_module_prefixes(alias.name))
        elif isinstance(node, ast.ImportFrom):
            prefix = node.module or ""
            if node.level:
                parts = package.split(".")
                offset = len(parts) - node.level + 1
                if offset < 1:
                    raise ValueError(f"Invalid relative import in {path}")
                prefix = ".".join(filter(None, [".".join(parts[:offset]), prefix]))
            if prefix:
                names.update(_module_prefixes(prefix))
                for alias in node.names:
                    names.update(_module_prefixes(f"{prefix}.{alias.name}"))
    return names


def reverse_imports(sources: dict[str, str]) -> dict[str, set[str]]:
    """Build a reverse file dependency graph without executing imported modules."""
    by_module = {_python_module_name(path): path for path in sources}
    reverse: dict[str, set[str]] = defaultdict(set)
    for path, source in sources.items():
        for name in _source_import_names(path, ast.parse(source, filename=path)):
            target = by_module.get(name)
            if target and target != path:
                reverse[target].add(path)
    return dict(reverse)


def transitive_import_dependants(graph: dict[str, set[str]], changed: set[str]) -> set[str]:
    """Return transitive import dependants, including the changed files."""
    result = set(changed)
    pending = list(changed)
    while pending:
        for dependant in graph.get(pending.pop(), set()):
            if dependant not in result:
                result.add(dependant)
                pending.append(dependant)
    return result


def coverage_contexts(root: Path, data_path: Path) -> dict[str, set[str]]:
    """Map covered source files to pytest module paths, retaining fixture contexts."""
    if not data_path.is_file():
        raise ValueError("Coverage data does not exist")
    data = CoverageData(basename=str(data_path))
    data.read()
    rows: dict[str, set[str]] = defaultdict(set)
    for name in data.measured_files():
        path = (root / name).resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError("Coverage data contains paths outside the checkout")
        source = path.relative_to(root.resolve()).as_posix()
        for contexts in data.contexts_by_lineno(name).values():
            for context in contexts:
                test, separator, _ = context.partition("::")
                if separator and test.startswith("tests/") and test.endswith(".py"):
                    rows[source].add(test)
    if not rows:
        raise ValueError("No pytest coverage contexts were recorded")
    return dict(rows)


def select_impacted_tests(
    changed: set[str],
    sources: dict[str, str],
    tests: set[str],
    contexts: dict[str, set[str]],
) -> dict[str, Any]:
    """Select tests conservatively; unknown changes explicitly require full validation."""
    reasons: list[str] = []
    if not tests:
        raise ValueError("Empty test inventory")
    if any(path not in sources or path.endswith("conftest.py") for path in changed):
        reasons.append("unclassified, deleted, non-Python or shared fixture change")
    if not contexts:
        reasons.append("missing validated coverage contexts")
    try:
        graph = reverse_imports(sources)
        affected = transitive_import_dependants(graph, changed)
    except (SyntaxError, ValueError) as exc:
        graph = {}
        affected = changed
        reasons.append(str(exc))
    selected = affected & tests
    for path in affected:
        selected.update(contexts.get(path, set()) & tests)
    for path in changed - tests:
        if path not in contexts and not (transitive_import_dependants(graph, {path}) & tests):
            reasons.append(f"no test evidence for {path}")
    if changed and not selected:
        reasons.append("no tests selected for nonempty change")
    return {
        "mode": "full" if reasons else "impacted",
        "tests": sorted(tests if reasons else selected),
        "affected": sorted(affected),
        "reasons": reasons,
        "advisory": True,
        "required_full_gate_unchanged": True,
    }


def plan_impacted_tests(
    root: Path,
    base: str,
    inventory: Path,
    data_path: Path,
    receipt: Path,
) -> dict[str, Any]:
    """Use only coverage evidence bound to the exact merge base and inventory digest."""
    merge_base, changed = changed_paths(root, base)
    paths = set(filter(None, _impact_git(root, "ls-files", "-z").split("\0"))) | set(changed)
    sources = {
        path: (root / path).read_text(encoding="utf-8")
        for path in paths
        if path.endswith(".py") and (root / path).is_file() and not (root / path).is_symlink()
    }
    rows = json.loads(inventory.read_text())
    tests = {row["nodeid"].split("::", 1)[0] for row in rows}
    if not tests or not all(p.startswith("tests/") for p in tests):
        raise ValueError("Invalid collected test inventory")
    metadata = json.loads(receipt.read_text())
    from tools.quality.local_checks.run_evidence import verify_quality_manifest

    verify_quality_manifest(receipt)
    coverage_result = metadata["result"]
    valid = (
        metadata.get("source_commit") == merge_base
        and metadata.get("dirty") is False
        and metadata.get("execution_status") in {"ok", "findings"}
        and metadata.get("action") == "coverage"
        and coverage_result.get("scope") == "full"
        and coverage_result.get("coverage_sha256")
        == hashlib.sha256(data_path.read_bytes()).hexdigest()
        and coverage_result.get("inventory_sha256")
        == hashlib.sha256(inventory.read_bytes()).hexdigest()
    )
    contexts = coverage_contexts(root, data_path) if valid else {}
    newly_added = {
        p
        for p in changed
        if p.startswith("tests/") and Path(p).name.startswith("test_") and p in sources
    }
    if newly_added - tests or not tests.issubset(sources):
        contexts = {}
        tests = (tests & sources.keys()) | newly_added
    result = select_impacted_tests(set(changed), sources, tests, contexts)
    return {**result, "merge_base": merge_base, "changed": changed, "evidence_valid": valid}
