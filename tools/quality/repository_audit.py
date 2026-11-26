#!/usr/bin/env python3
"""Build a static inventory of production documentation and test structure."""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import tokenize
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
INTERNAL_TOOL_PACKAGES = {"research_tools"}
GOOGLE_SECTION = re.compile(
    r"^\s*(?:Args|Arguments|Attributes|Examples?|Keyword Args|Keyword Arguments|"
    r"Other Parameters|Raises|Receives|References|Returns|See Also|Yields|Warnings?):\s*$",
    re.MULTILINE,
)
NUMPY_SECTION = re.compile(
    r"^\s*(?:Parameters|Returns|Yields|Raises|Attributes|Notes|Examples)\s*\n"
    r"\s*-{3,}\s*$",
    re.MULTILINE,
)
LOW_SIGNAL_COMMENT = re.compile(
    r"^(?:[-=#_* ]{5,}|(?:train|save|load|export)\s+(?:the\s+)?(?:agent|model|file|config|data)"
    r"|helpers|public api|todo:?\s*$|v\d+\b)",
    re.IGNORECASE,
)


def _package_names(root: Path) -> tuple[str, ...]:
    """Read the wheel package list, which defines production source roots."""
    import tomllib

    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    packages = pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"]
    return tuple(packages)


def _git_paths(root: Path) -> list[Path]:
    """Return Git-known tracked and unignored paths, including deleted files."""
    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return [root / item.decode() for item in result.stdout.split(b"\0") if item]


def _tracked_paths(root: Path) -> list[Path]:
    """Return existing tracked and unignored worktree files."""
    return [path for path in _git_paths(root) if path.is_file()]


def _definitions(tree: ast.AST) -> list[ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef]:
    """Return definitions that own runtime behavior and need source documentation."""

    def overloaded(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        """Return whether a function definition is a static overload stub."""
        return any(
            (isinstance(decorator, ast.Name) and decorator.id == "overload")
            or (isinstance(decorator, ast.Attribute) and decorator.attr == "overload")
            for decorator in node.decorator_list
        )

    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and not node.name.startswith("_")
        and not (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and overloaded(node))
    ]


def _literal_exports(tree: ast.Module) -> list[str]:
    """Read literal string names assigned to module ``__all__`` declarations."""
    names: list[str] = []
    for node in tree.body:
        value: ast.expr | None = None
        if (
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets
            )
            or (
                isinstance(node, ast.AnnAssign)
                and isinstance(node.target, ast.Name)
                or isinstance(node, ast.AugAssign)
                and isinstance(node.target, ast.Name)
            )
            and node.target.id == "__all__"
        ):
            value = node.value
        if value is None:
            continue
        try:
            declared = ast.literal_eval(value)
        except (TypeError, ValueError):
            continue
        if isinstance(declared, (list, tuple, set)):
            names.extend(name for name in declared if isinstance(name, str))
    return names


def _comment_metrics(path: Path) -> tuple[int, int, int, list[dict[str, Any]]]:
    """Count comment tokens and return low-signal candidates for human review."""
    total = standalone = inline = 0
    candidates: list[dict[str, Any]] = []
    lines = path.read_text(encoding="utf-8").splitlines()
    with path.open("rb") as source:
        for token in tokenize.tokenize(source.readline):
            if token.type != tokenize.COMMENT:
                continue
            total += 1
            text = token.string.lstrip("# ").strip()
            prefix = lines[token.start[0] - 1][: token.start[1]].strip()
            if prefix:
                inline += 1
            else:
                standalone += 1
            if LOW_SIGNAL_COMMENT.match(text):
                candidates.append({"line": token.start[0], "text": text})
    return total, standalone, inline, candidates


def audit_sources(root: Path, source_paths: Iterable[Path]) -> dict[str, Any]:
    """Measure AST docstring and lexical comment inventory for source paths."""
    source_paths = sorted(source_paths)
    definitions = all_documented = module_docstrings = documented = google = numpy = 0
    comments = standalone = inline = 0
    lines = 0
    low_signal: list[dict[str, Any]] = []
    export_names: set[str] = set()
    export_symbols: list[str] = []
    parse_errors: list[dict[str, str]] = []

    for path in sorted(source_paths):
        relative = path.relative_to(root).as_posix()
        source = path.read_text(encoding="utf-8")
        lines += len(source.splitlines())
        try:
            tree = ast.parse(source, filename=relative)
        except SyntaxError as error:
            parse_errors.append({"path": relative, "error": str(error)})
            continue
        module_doc = ast.get_docstring(tree)
        module_docstrings += module_doc is not None
        all_documented += sum(
            ast.get_docstring(node) is not None
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        )
        names = _literal_exports(tree)
        export_names.update(names)
        if names:
            module_name = relative.removesuffix(".py").replace("/", ".")
            if module_name.endswith(".__init__"):
                module_name = module_name.removesuffix(".__init__")
            export_symbols.extend(f"{module_name}.{name}" for name in names)
        for node in _definitions(tree):
            definitions += 1
            docstring = ast.get_docstring(node)
            if docstring is None:
                continue
            documented += 1
            google += bool(GOOGLE_SECTION.search(docstring))
            numpy += bool(NUMPY_SECTION.search(docstring))
        file_comments, file_standalone, file_inline, candidates = _comment_metrics(path)
        comments += file_comments
        standalone += file_standalone
        inline += file_inline
        for candidate in candidates:
            low_signal.append({"path": relative, **candidate})

    return {
        "files": len(source_paths),
        "lines": lines,
        "public_definition_candidates": definitions,
        "definitions_with_docstrings": documented,
        "all_definitions_with_docstrings": all_documented,
        "definition_docstring_coverage_pct": _percent(documented, definitions),
        "module_docstrings": module_docstrings,
        "google_style_docstrings": google,
        "numpy_style_docstrings": numpy,
        "explicit_all_export_symbols": len(export_symbols),
        "explicit_all_export_unique_names": len(export_names),
        "comment_tokens": comments,
        "standalone_comment_lines": standalone,
        "inline_comment_tokens": inline,
        "low_signal_comment_candidates": len(low_signal),
        "low_signal_candidates": low_signal,
        "parse_errors": parse_errors,
    }


def audit_tests(root: Path, test_paths: Iterable[Path]) -> dict[str, Any]:
    """Count test modules and AST test cases by path-based suite ownership."""
    suite_python_files: Counter[str] = Counter()
    suite_test_modules: Counter[str] = Counter()
    suite_cases: Counter[str] = Counter()
    total_cases = total_classes = test_modules = 0
    for path in sorted(test_paths):
        relative = path.relative_to(root).as_posix()
        parts = Path(relative).parts
        suite = parts[1] if len(parts) > 1 and parts[0] == "tests" else "legacy"
        suite_python_files[suite] += 1
        is_test_module = path.name.startswith("test_") or path.name.endswith("_test.py")
        if is_test_module:
            suite_test_modules[suite] += 1
            test_modules += 1
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        cases = sum(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test_")
            for node in ast.walk(tree)
        )
        classes = sum(
            isinstance(node, ast.ClassDef)
            and any(
                isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                and child.name.startswith("test_")
                for child in node.body
            )
            for node in ast.walk(tree)
        )
        suite_cases[suite] += cases
        total_cases += cases
        total_classes += classes
    return {
        "python_files": sum(suite_python_files.values()),
        "test_module_files": test_modules,
        "test_functions_and_methods": total_cases,
        "test_classes": total_classes,
        "python_files_by_suite": dict(sorted(suite_python_files.items())),
        "test_modules_by_suite": dict(sorted(suite_test_modules.items())),
        "test_functions_by_suite": dict(sorted(suite_cases.items())),
    }


def _audit_file_accountability(root: Path, paths: Iterable[Path]) -> dict[str, Any]:
    """Classify repository files for review, deriving ownership from path rules."""
    paths = list(paths)
    owners = {
        "configuration": "ml_engineer",
        "config": "ml_engineer",
        "decisioning": "ml_engineer",
        "models": "ml_engineer",
        "learning": "ml_engineer",
        "training": "ml_engineer",
        "experiments": "ml_engineer",
        "compute": "ml_engineer",
        "market_data": "data_scientist_engineer",
        "features": "data_scientist_engineer",
        "trading": "quantitative_trading_engineer",
        "simulation": "quantitative_trading_engineer",
        "artifacts": "evidence_reporting_engineer",
        "evaluation": "evidence_reporting_engineer",
        "docs": "evidence_reporting_engineer",
        "tests": "architect",
        "tools": "evidence_reporting_engineer",
        ".github": "ci_operation_engineer",
    }
    test_owners = {
        "__init__.py": "architect",
        "configuration": "ml_engineer",
        "decisioning": "ml_engineer",
        "compute": "ml_engineer",
        "experiments": "ml_engineer",
        "market_data": "data_scientist_engineer",
        "features": "data_scientist_engineer",
        "trading": "quantitative_trading_engineer",
        "simulation": "quantitative_trading_engineer",
        "learning": "ml_engineer",
        "models": "ml_engineer",
        "training": "ml_engineer",
        "evaluation": "evidence_reporting_engineer",
        "artifacts": "evidence_reporting_engineer",
        "research": "evidence_reporting_engineer",
        "tooling": "evidence_reporting_engineer",
        "live": "quantitative_trading_engineer",
    }
    integration_owners = {
        "__init__.py": "architect",
        "backtest": "quantitative_trading_engineer",
        "evaluation": "evidence_reporting_engineer",
        "test_pipeline_splits.py": "data_scientist_engineer",
        "test_bar_cache_manifest.py": "data_scientist_engineer",
        "test_loader.py": "data_scientist_engineer",
        "test_resample_m10.py": "data_scientist_engineer",
        "test_sac_agent_integration.py": "ml_engineer",
        "test_sb3_adapter.py": "ml_engineer",
        "test_runner.py": "ml_engineer",
        "test_device.py": "ml_engineer",
        "test_configuration_wheel.py": "ml_engineer",
        "test_metric_input_contract.py": "evidence_reporting_engineer",
        "test_evaluation_pipeline.py": "evidence_reporting_engineer",
        "test_matched_comparison.py": "evidence_reporting_engineer",
        "test_bootstrap_drawdown_interval.py": "evidence_reporting_engineer",
        "test_calibration_ci.py": "evidence_reporting_engineer",
        "test_position_fill_accounting.py": "quantitative_trading_engineer",
        "test_trade_setup.py": "quantitative_trading_engineer",
        "test_strategy_integration.py": "quantitative_trading_engineer",
        "test_session_levels_integration.py": "data_scientist_engineer",
        "test_price_grid.py": "data_scientist_engineer",
        "test_lstm_classifier.py": "ml_engineer",
        "test_action_schema_contract.py": "ml_engineer",
        "test_measure_ppo_throughput.py": "ml_engineer",
        "test_activity.py": "ml_engineer",
        "test_ablation_oos_smoke.py": "evidence_reporting_engineer",
        "test_leakage.py": "data_scientist_engineer",
        "test_scripts_smoke.py": "architect",
    }
    excluded_dirs = {"docs/api/usage", "docs/_build", "site"}
    seen: set[str] = set()
    duplicates: set[str] = set()
    files: list[dict[str, Any]] = []
    for path in paths:
        relative = path.relative_to(root).as_posix()
        if relative in seen:
            duplicates.add(relative)
            continue
        seen.add(relative)
        parts = Path(relative).parts
        generated = any(
            relative == prefix or relative.startswith(f"{prefix}/") for prefix in excluded_dirs
        )
        asset = path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico"}
        if generated:
            disposition, reason = "generated", "generated output"
        elif asset:
            disposition, reason = "asset", "non-source asset"
        elif parts[0] == "tests":
            disposition, reason = "test", None
        elif path.suffix == ".py":
            disposition, reason = "production_source", None
        elif parts[0] == "docs":
            disposition, reason = "documentation", None
        elif parts[0] in {"config", "configuration"}:
            disposition, reason = "configuration", None
        else:
            disposition, reason = "project_file", None
        if parts[0] == "tests":
            suite = parts[1] if len(parts) > 1 else ""
            if suite == "unit":
                owner = test_owners.get(parts[2]) if len(parts) > 2 else "architect"
            elif suite == "integration":
                key = parts[2] if len(parts) > 3 else path.name
                owner = integration_owners.get(key)
            elif (
                suite == "fixtures"
                and len(parts) > 2
                and parts[2] == "research"
                or suite == "research"
            ):
                owner = "evidence_reporting_engineer"
            elif suite == "architecture" or len(parts) == 2:
                owner = "architect"
            else:
                owner = None
        elif parts[0] == "tools" and len(parts) > 1 and parts[1] == "documentation":
            owner = "evidence_reporting_engineer"
        elif parts[0] == "tools" and len(parts) > 1 and parts[1] == "check":
            owner = "ci_operation_engineer"
        elif parts[0] == "tools" and len(parts) > 1 and parts[1] == "quality":
            owner = "architect"
        else:
            owner = owners.get(parts[0], "architect")
        eligible = reason is None
        files.append(
            {
                "path": relative,
                "owner": owner,
                "disposition": disposition,
                "eligible": eligible,
                "exclusion_reason": reason,
                "exists": path.is_file(),
            }
        )
    missing = sorted(item["path"] for item in files if not item["exists"])
    return {
        "eligibility_rule": (
            "all Git-known tracked or unignored files except generated outputs and non-source assets; "
            "unmapped test ownership remains unassigned"
        ),
        "files": sorted(files, key=lambda item: item["path"]),
        "duplicate_paths": sorted(duplicates),
        "missing_paths": missing,
        "unassigned_paths": sorted(item["path"] for item in files if item["owner"] is None),
    }


def _percent(numerator: int, denominator: int) -> float | None:
    """Convert a numerator and denominator to a percentage when defined."""
    return round(100 * numerator / denominator, 2) if denominator else None


def build_audit(root: Path = ROOT) -> dict[str, Any]:
    """Return a deterministic snapshot of tracked and unignored repository files."""
    git_paths = _git_paths(root)
    tracked = [path for path in git_paths if path.is_file()]
    packages = _package_names(root)
    source_paths = [
        path
        for path in tracked
        if path.suffix == ".py"
        and any(
            path.is_relative_to(root / package)
            for package in packages
            if package not in INTERNAL_TOOL_PACKAGES
        )
    ]
    test_paths = [
        path for path in tracked if path.suffix == ".py" and "tests" in path.relative_to(root).parts
    ]
    docs_pages = [
        path
        for path in tracked
        if path.suffix.lower() == ".md" and "docs" in path.relative_to(root).parts
    ]
    package_readmes = {package: (root / package / "README.md").is_file() for package in packages}
    git = subprocess.run(
        ["git", "rev-parse", "HEAD", "--abbrev-ref", "HEAD"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    result = {
        "repository": str(root),
        "head_and_branch": git.stdout.splitlines(),
        "production": audit_sources(root, source_paths),
        "tests": audit_tests(root, test_paths),
        "file_accountability": _audit_file_accountability(root, git_paths),
        "documentation": {
            "tracked_markdown_pages": len(docs_pages),
            "package_readmes_present": sum(package_readmes.values()),
            "package_readme_total": len(package_readmes),
            "missing_package_readmes": [
                name for name, present in package_readmes.items() if not present
            ],
        },
    }
    return result


def main(argv: list[str] | None = None) -> int:
    """Print the repository source, test, and documentation inventory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--include-comment-candidates", action="store_true")
    args = parser.parse_args(argv)
    audit = build_audit(args.root.resolve())
    if not args.include_comment_candidates:
        audit["production"].pop("low_signal_candidates", None)
    print(json.dumps(audit, indent=2, sort_keys=True))
    return 1 if audit["production"]["parse_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
