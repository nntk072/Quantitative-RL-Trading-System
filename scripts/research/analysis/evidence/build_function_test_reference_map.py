#!/usr/bin/env python3
"""Build a deterministic static map from production symbols to test references.

This inventory detects imports and statically visible module-attribute access.
It does not measure execution, assertion quality, branch coverage, or behavioral
test adequacy. Every row is labeled ``static_reference_only`` for that reason.
"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import os
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DEFAULT_OUTPUT_DIR = ROOT / "evidence/research/function_test_coverage"
EXCLUDED_DIRS = {
    ".git",
    ".venv",
    ".venv-x86",
    ".venv-mi210",
    "build",
    "dist",
    "node_modules",
    "orchestra",
    "site-packages",
    "tests",
    "__pycache__",
    "_build",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _python_files(root: Path, *, tests: bool = False) -> list[Path]:
    root = root.resolve()
    try:
        output = subprocess.check_output(
            [
                "git",
                "-C",
                str(root),
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
                "--",
                "*.py",
            ],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        listed = [root / line for line in output.splitlines() if line.endswith(".py")]
        return sorted(
            (
                path
                for path in listed
                if path.is_file()
                and _included_relative_path(path.relative_to(root), tests=tests)
                and (not tests or path.name.startswith("test_"))
            ),
            key=lambda path: path.relative_to(root).as_posix(),
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    files: list[Path] = []
    excluded = EXCLUDED_DIRS - ({"tests"} if tests else set())
    for current, directories, names in os.walk(root):
        directories[:] = sorted(
            name for name in directories if name not in excluded and not name.startswith(".venv")
        )
        current_path = Path(current)
        relative_parts = current_path.relative_to(root).parts
        if tests and relative_parts and relative_parts[0] != "tests":
            directories[:] = []
            continue
        for name in names:
            if name.endswith(".py") and (not tests or name.startswith("test_")):
                path = current_path / name
                if _included_relative_path(path.relative_to(root), tests=tests):
                    files.append(path)
    return sorted(files, key=lambda path: path.relative_to(root).as_posix())


def _included_relative_path(relative_path: Path, *, tests: bool) -> bool:
    """Return whether a Python path belongs in the requested source inventory."""
    parts = relative_path.parts
    if tests:
        return (
            bool(parts)
            and parts[0] == "tests"
            and not any(
                part in EXCLUDED_DIRS - {"tests"} or part.startswith(".venv") for part in parts
            )
        )
    return bool(parts) and not any(
        part in EXCLUDED_DIRS or part.startswith(".venv") for part in parts
    )


def _module_name(relative_path: Path) -> str:
    parts = list(relative_path.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _domain_and_tier(relative_path: Path) -> tuple[str, str]:
    parts = relative_path.parts
    if len(parts) >= 5 and parts[:4] == ("scripts", "research", "analysis", "features"):
        return "research.analysis.features", "P0"
    if len(parts) >= 5 and parts[:4] == ("scripts", "research", "analysis", "market_data"):
        return "research.analysis.market_data", "P0"
    if len(parts) >= 5 and parts[:4] == ("scripts", "research", "analysis", "evaluation"):
        return "research.analysis.evaluation", "P1"
    if len(parts) >= 5 and parts[:4] == ("scripts", "research", "analysis", "models"):
        return "research.analysis.models", "P1"
    if len(parts) >= 5 and parts[:4] == ("scripts", "research", "analysis", "evidence"):
        return "research.analysis.evidence", "P1"

    top = parts[0] if parts else "root"
    domains = {
        "configuration": ("configuration", "P1"),
        "config": ("configuration", "P1"),
        "market_data": ("market_data", "P0"),
        "data": ("market_data", "P0"),
        "features": ("features", "P0"),
        "decisioning": ("decisioning", "P0"),
        "simulation": ("simulation", "P0"),
        "trading": ("trading", "P0"),
        "live": ("live", "P0"),
        "integrations": ("integrations", "P0"),
        "models": ("models", "P1"),
        "learning": ("learning", "P1"),
        "training": ("training", "P1"),
        "experiments": ("experiments", "P1"),
        "evaluation": ("evaluation", "P1"),
        "artifacts": ("artifacts", "P1"),
        "compute": ("compute", "P1"),
    }
    if top in domains:
        return domains[top]
    if top == "scripts":
        return "scripts", "P1"
    if top in {"docs", "evidence"}:
        return top, "P2"
    return top.removesuffix(".py"), "P2"


def _qualified_definitions(tree: ast.Module) -> list[tuple[str, str, int]]:
    definitions: list[tuple[str, str, int]] = []

    def visit(node: ast.AST, scope: tuple[str, ...] = ()) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                qualified = (*scope, child.name)
                kind = "class" if isinstance(child, ast.ClassDef) else "function"
                definitions.append((".".join(qualified), kind, child.lineno))
                visit(child, qualified)
            else:
                visit(child, scope)

    visit(tree)
    return definitions


def _attribute_path(node: ast.AST) -> str | None:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    parts.append(node.id)
    return ".".join(reversed(parts))


def _relative_import_module(source_path: Path, module: str | None, level: int) -> str | None:
    if level == 0:
        return module
    package = list(source_path.with_suffix("").parts[:-1])
    trim = level - 1
    if trim > len(package):
        return None
    base = package[: len(package) - trim]
    if module:
        base.extend(module.split("."))
    return ".".join(base) or None


def _package_reexports(
    repo_root: Path, production_paths: list[Path]
) -> dict[tuple[str, str], tuple[str, str]]:
    """Map explicit package ``__init__`` re-exports to their defining module."""
    exports: dict[tuple[str, str], tuple[str, str]] = {}
    for source_path in production_paths:
        if source_path.name != "__init__.py":
            continue
        relative_source = source_path.relative_to(repo_root)
        package = _module_name(relative_source)
        try:
            tree = ast.parse(
                source_path.read_text(encoding="utf-8"),
                filename=relative_source.as_posix(),
            )
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            target_module = _relative_import_module(relative_source, node.module, node.level)
            if target_module is None:
                continue
            for alias in node.names:
                if alias.name == "*":
                    continue
                exports[(package, alias.asname or alias.name)] = (target_module, alias.name)
    return exports


def _resolve_reexport(
    module: str,
    symbol: str,
    exports: dict[tuple[str, str], tuple[str, str]],
) -> tuple[str, str]:
    """Follow a finite chain of explicit package-level symbol re-exports."""
    current = (module, symbol)
    visited: set[tuple[str, str]] = set()
    while current in exports and current not in visited:
        visited.add(current)
        current = exports[current]
    return current


def _class_symbols(repo_root: Path, production_paths: list[Path]) -> set[tuple[str, str]]:
    """Collect production class definitions for conservative instance-call mapping."""
    classes: set[tuple[str, str]] = set()
    for source_path in production_paths:
        relative_source = source_path.relative_to(repo_root)
        try:
            tree = ast.parse(
                source_path.read_text(encoding="utf-8"),
                filename=relative_source.as_posix(),
            )
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        module = _module_name(relative_source)
        classes.update(
            (module, symbol)
            for symbol, kind, _line in _qualified_definitions(tree)
            if kind == "class"
        )
    return classes


def _static_references(
    repo_root: Path,
    source_paths: list[Path],
    package_reexports: dict[tuple[str, str], tuple[str, str]] | None = None,
    defined_classes: set[tuple[str, str]] | None = None,
) -> dict[tuple[str, str], set[str]]:
    """Map imported symbols and simple class-instance methods to source paths."""
    symbol_tests: dict[tuple[str, str], set[str]] = defaultdict(set)
    exports = package_reexports or {}
    classes = defined_classes or set()
    for source_path in source_paths:
        relative_source = source_path.relative_to(repo_root).as_posix()
        try:
            tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=relative_source)
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue

        imported_modules: set[str] = set()
        imported_symbols: list[tuple[str, str]] = []
        alias_targets: dict[str, str] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported = alias.name
                    imported_modules.add(imported)
                    binding = alias.asname or imported.split(".")[0]
                    alias_targets[binding] = imported if alias.asname else binding
            elif isinstance(node, ast.ImportFrom):
                module = _relative_import_module(
                    source_path.relative_to(repo_root), node.module, node.level
                )
                if module is None:
                    continue
                imported_modules.add(module)
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    imported_symbols.append((module, alias.name))
                    alias_targets[alias.asname or alias.name] = f"{module}.{alias.name}"

        instance_targets: dict[str, set[tuple[str, str]]] = defaultdict(set)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                assigned_names = [target for target in node.targets if isinstance(target, ast.Name)]
                value: ast.expr | None = node.value
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                assigned_names = [node.target]
                value = node.value
            else:
                continue
            if not isinstance(value, ast.Call):
                continue
            call_path = _attribute_path(value.func)
            if call_path is None:
                continue
            parts = call_path.split(".")
            imported_target = alias_targets.get(parts[0])
            target = (
                ".".join((imported_target, *parts[1:]))
                if imported_target is not None
                else call_path
            )
            if "." not in target:
                continue
            target_module, target_symbol = target.rsplit(".", 1)
            class_target = _resolve_reexport(target_module, target_symbol, exports)
            if class_target not in classes:
                continue
            for name in assigned_names:
                instance_targets[name.id].add(class_target)
        for alias_name, targets in instance_targets.items():
            if len(targets) == 1:
                target_module, target_symbol = next(iter(targets))
                alias_targets[alias_name] = f"{target_module}.{target_symbol}"

        attribute_paths = {
            path
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
            if (path := _attribute_path(node)) is not None
        }
        for module, symbol in imported_symbols:
            symbol_tests[_resolve_reexport(module, symbol, exports)].add(relative_source)
        for binding_name, target in alias_targets.items():
            for attribute_path in attribute_paths:
                if not attribute_path.startswith(f"{binding_name}."):
                    continue
                suffix = attribute_path[len(binding_name) + 1 :]
                if target in imported_modules:
                    source_module, qualified_symbol = target, suffix
                elif "." in target:
                    source_module, imported_symbol = target.rsplit(".", 1)
                    qualified_symbol = f"{imported_symbol}.{suffix}"
                else:
                    continue
                symbol_tests[_resolve_reexport(source_module, qualified_symbol, exports)].add(
                    relative_source
                )

    return symbol_tests


def build_rows(root: Path) -> list[dict[str, str]]:
    """Inventory production definitions and statically visible direct test references."""
    source_paths = [
        path
        for path in _python_files(root)
        if "tests" not in path.relative_to(root).parts
        and "orchestra" not in path.relative_to(root).parts
    ]
    package_reexports = _package_reexports(root, source_paths)
    defined_classes = _class_symbols(root, source_paths)
    test_references = _static_references(
        root, _python_files(root, tests=True), package_reexports, defined_classes
    )
    production_references = _static_references(
        root, source_paths, package_reexports, defined_classes
    )
    rows: list[dict[str, str]] = []
    for source_path in source_paths:
        relative_source = source_path.relative_to(root)
        module = _module_name(relative_source)
        domain, risk_tier = _domain_and_tier(relative_source)
        try:
            content = source_path.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=relative_source.as_posix())
            definitions = _qualified_definitions(tree)
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        source_hash = _sha256(source_path)
        for symbol, kind, line in definitions:
            references = set(test_references.get((module, symbol), set()))
            production_uses = set(production_references.get((module, symbol), set()))
            hashes = [f"{test}={_sha256(root / test)}" for test in sorted(references)]
            visibility = (
                "internal_by_name"
                if any(part.startswith("_") for part in symbol.split("."))
                else "public_by_name"
            )
            rows.append(
                {
                    "source_path": relative_source.as_posix(),
                    "module": module,
                    "symbol": symbol,
                    "symbol_kind": kind,
                    "source_line": str(line),
                    "domain": domain,
                    "risk_tier": risk_tier,
                    "api_visibility_by_name": visibility,
                    "direct_static_production_references": ";".join(sorted(production_uses)),
                    "direct_static_test_references": ";".join(sorted(references)),
                    "source_sha256": source_hash,
                    "test_sha256s": ";".join(hashes),
                    "evidence_status": "static_reference_only",
                }
            )
    return sorted(
        rows, key=lambda row: (row["source_path"], int(row["source_line"]), row["symbol"])
    )


CSV_FIELDS = (
    "source_path",
    "module",
    "symbol",
    "symbol_kind",
    "source_line",
    "domain",
    "risk_tier",
    "api_visibility_by_name",
    "direct_static_production_references",
    "direct_static_test_references",
    "source_sha256",
    "test_sha256s",
    "evidence_status",
)


def write_csv(
    path: Path, rows: list[dict[str, str]], *, fieldnames: tuple[str, ...] | None = None
) -> None:
    """Write stable CSV bytes using an atomic replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = fieldnames or (tuple(rows[0]) if rows else CSV_FIELDS)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as output:
            temporary = Path(output.name)
            writer = csv.DictWriter(output, fieldnames=columns, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
            output.flush()
            os.fsync(output.fileno())
        temporary.replace(path)
    except BaseException:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise


def _package_path(source_path: str) -> str:
    """Return the source directory used for the package-level summary."""
    parent = Path(source_path).parent.as_posix()
    return "root" if parent == "." else parent.replace("/", ".")


def write_package_views(output_dir: Path, rows: list[dict[str, str]]) -> None:
    """Write domain/package reference rates and prioritized no-reference symbols."""
    packages: dict[str, list[dict[str, str]]] = defaultdict(list)
    dependency_symbols: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
    dependency_callers: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in rows:
        packages[_package_path(row["source_path"])].append(row)
        target_package = _package_path(row["source_path"])
        for caller_path in filter(None, row["direct_static_production_references"].split(";")):
            caller_package = _package_path(caller_path)
            if caller_package == target_package:
                continue
            edge = (caller_package, target_package)
            dependency_symbols[edge].add((row["module"], row["symbol"]))
            dependency_callers[edge].add(caller_path)

    package_rows: list[dict[str, str]] = []
    for package, members in sorted(packages.items()):
        referenced = [row for row in members if row["direct_static_test_references"]]
        p0_members = [row for row in members if row["risk_tier"] == "P0"]
        p0_referenced = [row for row in p0_members if row["direct_static_test_references"]]
        package_rows.append(
            {
                "package": package,
                "domain": members[0]["domain"],
                "source_files": str(len({row["source_path"] for row in members})),
                "definitions": str(len(members)),
                "definitions_with_direct_test_reference": str(len(referenced)),
                "definitions_without_direct_test_reference": str(len(members) - len(referenced)),
                "p0_definitions": str(len(p0_members)),
                "p0_with_direct_test_reference": str(len(p0_referenced)),
                "p0_without_direct_test_reference": str(len(p0_members) - len(p0_referenced)),
            }
        )

    priority_rows = [
        {
            "source_path": row["source_path"],
            "source_line": row["source_line"],
            "module": row["module"],
            "symbol": row["symbol"],
            "symbol_kind": row["symbol_kind"],
            "domain": row["domain"],
            "risk_tier": row["risk_tier"],
            "direct_static_production_references": row["direct_static_production_references"],
        }
        for row in rows
        if row["risk_tier"] == "P0" and not row["direct_static_test_references"]
    ]
    dependency_rows = [
        {
            "caller_package": caller_package,
            "target_package": target_package,
            "referenced_symbols": str(len(dependency_symbols[(caller_package, target_package)])),
            "caller_files": str(len(dependency_callers[(caller_package, target_package)])),
        }
        for caller_package, target_package in sorted(dependency_symbols)
    ]
    write_csv(
        output_dir / "package_reference_summary.csv",
        package_rows,
        fieldnames=(
            "package",
            "domain",
            "source_files",
            "definitions",
            "definitions_with_direct_test_reference",
            "definitions_without_direct_test_reference",
            "p0_definitions",
            "p0_with_direct_test_reference",
            "p0_without_direct_test_reference",
        ),
    )
    write_csv(
        output_dir / "priority_symbols_without_direct_test_references.csv",
        priority_rows,
        fieldnames=(
            "source_path",
            "source_line",
            "module",
            "symbol",
            "symbol_kind",
            "domain",
            "risk_tier",
            "direct_static_production_references",
        ),
    )
    write_csv(
        output_dir / "package_dependency_edges.csv",
        dependency_rows,
        fieldnames=("caller_package", "target_package", "referenced_symbols", "caller_files"),
    )


def write_readme(path: Path, rows: list[dict[str, str]], source_file_count: int) -> None:
    """Write the method and scope for the generated static map."""
    referenced = sum(bool(row["direct_static_test_references"]) for row in rows)
    tiers = {tier: sum(row["risk_tier"] == tier for row in rows) for tier in ("P0", "P1", "P2")}
    visibility = {
        value: sum(row["api_visibility_by_name"] == value for row in rows)
        for value in ("public_by_name", "internal_by_name")
    }
    tier_references = {
        tier: sum(
            row["risk_tier"] == tier and bool(row["direct_static_test_references"]) for row in rows
        )
        for tier in ("P0", "P1", "P2")
    }
    text = f"""# Function to test reference map

`function_test_reference_map.csv` is a deterministic static inventory generated
from the current production Python tree. It includes **{source_file_count}**
source files, **{len(rows)}** function, async-function, and class definitions,
of which **{referenced}** have at least one statically visible direct test
reference. Risk-tier row counts: P0 **{tiers["P0"]}**, P1 **{tiers["P1"]}**,
P2 **{tiers["P2"]}**.

Name-based visibility counts: public **{visibility["public_by_name"]}**, internal
**{visibility["internal_by_name"]}**. These follow leading-underscore naming
conventions; they do not establish the supported public API. Direct static test
reference counts by risk tier: P0 **{tier_references["P0"]}/{tiers["P0"]}**,
P1 **{tier_references["P1"]}/{tiers["P1"]}**, P2
**{tier_references["P2"]}/{tiers["P2"]}**.

## Meaning of a reference

The generator detects Python `import` / `from ... import ...` statements in
`tests/test_*.py`, exact symbol imports, statically visible module attribute
access, and simple explicit symbol re-exports in package `__init__.py` files.
It also follows a simple named variable assigned from one unambiguous
production-class constructor imported by that file; this links instance method
references such as `env.step` to their class definition. It does not resolve
dynamic imports, runtime dispatch, fixture return types, or generated tests. A
listed test may import a symbol without calling it; an unlisted test can still
exercise it through a fixture or higher-level path. This is a navigation aid
only.

Every CSV row has `evidence_status=static_reference_only`. The `domain` column
is a semantic source-owner area, not a named maintainer. The production and
test reference columns list imports or statically visible module attribute
paths; neither is a call graph. Missing references do not prove that code is
unused or untested. The map does not claim that a test was run, that an
assertion is meaningful, that a branch was covered, or that behavior is
correct. Test/source SHA-256 columns pin the exact bytes inspected for each
static test reference. Rebuild it after source or test changes with:

```bash
.venv/bin/python scripts/research/analysis/evidence/build_function_test_reference_map.py
```

Use the architecture-matched repository environment when running this command.

## Package review views

`package_reference_summary.csv` groups definitions by their source directory
and reports direct static test-reference counts, with P0 totals broken out.
`priority_symbols_without_direct_test_references.csv` lists P0 definitions
that the static scan did not connect to a test and includes statically visible
production references where available. These are audit queues, not coverage
claims: indirect test paths, generated tests, runtime dispatch, and assertion
quality are not resolved. Review the prioritized rows against source and
behavior evidence before deciding whether code is dead or needs a contract.
`package_dependency_edges.csv` aggregates statically visible production
references between source directories. It omits intra-package references and
cannot represent dynamic imports, dependency inversion, or runtime call flow.

Production files are discovered recursively while excluding tests, orchestra,
virtual environments, build outputs, package installations, and bytecode
caches. The risk tier is a coarse review priority, not a severity score:

- **P0:** data, features, decisioning, simulation, trading, live and broker
  integration code, plus feature/data analysis tools.
- **P1:** model, learning, training, experiments, evaluation, artifact,
  configuration, compute, and evidence analysis code.
- **P2:** remaining support/documentation modules.

The source path and risk tier should be reviewed when new top-level domains or
analysis subdomains are added. Do not substitute this map for targeted
behavioral contracts, the release test gate, or a measured coverage report.
"""
    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    root = args.repo_root.resolve()
    output_dir = args.output_dir if args.output_dir.is_absolute() else root / args.output_dir
    rows = build_rows(root)
    source_count = len(
        [
            path
            for path in _python_files(root)
            if "tests" not in path.relative_to(root).parts
            and "orchestra" not in path.relative_to(root).parts
        ]
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "function_test_reference_map.csv", rows)
    write_package_views(output_dir, rows)
    write_readme(output_dir / "README.md", rows, source_count)
    print(f"source_files={source_count} definitions={len(rows)}")
    print(
        f"referenced_definitions={sum(bool(row['direct_static_test_references']) for row in rows)}"
    )
    print(f"csv={output_dir / 'function_test_reference_map.csv'}")
    print(f"readme={output_dir / 'README.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
