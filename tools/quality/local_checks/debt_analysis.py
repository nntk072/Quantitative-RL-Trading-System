"""Local technical-debt observations from source ASTs and dependency relationships."""

from __future__ import annotations

import ast
import hashlib
from collections import defaultdict
from pathlib import Path
from typing import Any

from tools.quality.coverage_report import PRODUCT_PACKAGES
from tools.quality.local_checks.impact import reverse_imports
from tools.quality.local_checks.run_evidence import ROOT, quality_source_paths


def _debt_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    """Return strongly connected components using a deterministic depth-first traversal."""
    index = 0
    indices: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    active: set[str] = set()
    components: list[list[str]] = []

    def visit_node(node: str) -> None:
        """Visit a dependency and close its strongly connected component."""
        nonlocal index
        indices[node] = low[node] = index
        index += 1
        stack.append(node)
        active.add(node)
        for target in sorted(graph.get(node, set())):
            if target not in indices:
                visit_node(target)
                low[node] = min(low[node], low[target])
            elif target in active:
                low[node] = min(low[node], indices[target])
        if low[node] == indices[node]:
            component = []
            while stack:
                item = stack.pop()
                active.remove(item)
                component.append(item)
                if item == node:
                    break
            if len(component) > 1:
                components.append(sorted(component))

    for node in sorted(graph):
        if node not in indices:
            visit_node(node)
    return sorted(components)


def audit_technical_debt() -> dict[str, Any]:
    """Report approximate complexity, duplicate bodies, module size and suppression inventory."""
    sources = {p: (ROOT/p).read_text() for p in quality_source_paths()
               if p.endswith(".py") and p.split("/")[0] in PRODUCT_PACKAGES and not (ROOT/p).is_symlink()}
    functions = []
    modules = []
    suppressions = []
    duplicate: dict[str, list[str]] = defaultdict(list)
    for path, source in sources.items():
        tree = ast.parse(source, filename=path)
        modules.append({"file": path, "lines": len(source.splitlines())})
        for number, line in enumerate(source.splitlines(), 1):
            if any(token in line for token in ("# type: ignore", "# noqa", "# pragma: no cover", "# nosec")):
                suppressions.append({"file": path, "line": number})
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                count = 1 + sum(isinstance(x, (ast.If, ast.For, ast.AsyncFor, ast.While,
                            ast.IfExp, ast.ExceptHandler, ast.Match, ast.BoolOp)) for x in ast.walk(node))
                name = f"{path}:{node.lineno}:{node.name}"
                functions.append({"function": name, "lines": (node.end_lineno or node.lineno)-node.lineno+1,
                                  "approximate_complexity": count})
                if len(list(ast.walk(node))) >= 25:
                    key = hashlib.sha256(ast.dump(ast.Module(body=node.body, type_ignores=[]),
                                                  include_attributes=False).encode()).hexdigest()
                    duplicate[key].append(name)
    cycles = _debt_cycles(reverse_imports(sources))
    return {"status": "findings" if cycles or any(len(v)>1 for v in duplicate.values()) else "ok",
            "modules": modules, "functions": functions, "suppressions": suppressions,
            "cycles": cycles, "duplicate_bodies": [v for v in duplicate.values() if len(v)>1],
            "qualification": "AST heuristics are review leads; they do not establish defective or dead code."}
