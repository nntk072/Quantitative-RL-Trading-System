#!/usr/bin/env python3
"""Check that every maintained production/tool function has a docstring."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FUNCTION_ROOTS = (
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
    "tools",
)


def _is_overload(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Return whether a definition is a typing overload signature stub."""
    return any(
        (isinstance(decorator, ast.Name) and decorator.id == "overload")
        or (isinstance(decorator, ast.Attribute) and decorator.attr == "overload")
        for decorator in node.decorator_list
    )


def missing_docstrings(root: Path = ROOT) -> list[str]:
    """Return source locations of functions without a docstring."""
    failures: list[str] = []
    for package in FUNCTION_ROOTS:
        for path in sorted((root / package).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if (
                    isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and not _is_overload(node)
                    and not ast.get_docstring(node)
                ):
                    failures.append(
                        f"{path.relative_to(root)}:{node.lineno}: {node.name} has no docstring"
                    )
    return failures


def main() -> int:
    """Report function documentation gaps for the maintained code surface."""
    failures = missing_docstrings()
    if failures:
        print("Function docstring checks failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("All production and tooling functions have docstrings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
