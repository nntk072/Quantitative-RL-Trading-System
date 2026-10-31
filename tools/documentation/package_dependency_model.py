#!/usr/bin/env python3
"""Render the factual package-import graph used by architecture tests."""

from __future__ import annotations

import argparse
import ast
from pathlib import Path

PACKAGES = (
    "configuration",
    "artifacts",
    "market_data",
    "features",
    "trading",
    "decisioning",
    "simulation",
    "models",
    "learning",
    "training",
    "evaluation",
    "experiments",
    "live",
    "integrations",
    "compute",
    "orchestra",
)
START = "<!-- GENERATED PACKAGE IMPORT GRAPH: START -->"
END = "<!-- GENERATED PACKAGE IMPORT GRAPH: END -->"
DEFAULT_PAGE = Path(__file__).resolve().parents[2] / "docs/architecture/dependency_model.md"


def package_imports(root: Path) -> dict[str, tuple[str, ...]]:
    """Collect direct production-package imports with the architecture test's AST rule."""
    package_set = set(PACKAGES)
    graph: dict[str, set[str]] = {package: set() for package in PACKAGES}
    for package in PACKAGES:
        for path in sorted((root / package).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    graph[package].update(
                        name
                        for alias in node.names
                        if (name := alias.name.split(".", 1)[0]) in package_set and name != package
                    )
                elif isinstance(node, ast.ImportFrom) and node.module:
                    name = node.module.split(".", 1)[0]
                    if name in package_set and name != package:
                        graph[package].add(name)
    return {package: tuple(sorted(dependencies)) for package, dependencies in graph.items()}


def render_graph(root: Path) -> str:
    """Return a deterministic Mermaid graph and relationship table."""
    graph = package_imports(root)
    lines = ["```mermaid", "flowchart LR"]
    for package in PACKAGES:
        lines.append(f"    {package}[`{package}/`]")
    for package, dependencies in graph.items():
        for dependency in dependencies:
            lines.append(f"    {package} -->|imports| {dependency}")
    lines.extend(("```", "", "| Package | Imports production packages |", "|---|---|"))
    for package, dependencies in graph.items():
        rendered = ", ".join(f"`{item}`" for item in dependencies) or "None"
        lines.append(f"| `{package}` | {rendered} |")
    return "\n".join(lines)


def replace_generated_block(document: str, rendered: str) -> str:
    """Replace exactly one marked generated block, preserving human commentary."""
    if document.count(START) != 1 or document.count(END) != 1:
        raise ValueError("dependency model page must contain exactly one pair of markers")
    start = document.index(START) + len(START)
    end = document.index(END)
    if start >= end:
        raise ValueError("dependency model generation markers are out of order")
    return document[:start] + "\n\n" + rendered + "\n\n" + document[end:]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="update the generated graph")
    mode.add_argument("--check", action="store_true", help="fail if generated graph is stale")
    parser.add_argument("--page", type=Path, default=DEFAULT_PAGE)
    args = parser.parse_args(argv)

    page = args.page.resolve()
    root = Path(__file__).resolve().parents[2]
    current = page.read_text(encoding="utf-8")
    rendered = render_graph(root)
    updated = replace_generated_block(current, rendered)
    if args.write:
        page.write_text(updated, encoding="utf-8")
        return 0
    if current != updated:
        print(f"generated package dependency graph is stale: {page}")
        return 1
    print("package dependency graph is current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
