"""Contracts for source-backed public API usage pages."""

from __future__ import annotations

import ast
from pathlib import Path

from tools.documentation import api_usage
from tools.documentation.api_usage import OUTPUT
from tools.documentation.public_api_inventory import (
    PUBLIC_CLASSIFICATIONS,
    PUBLIC_KINDS,
    ROOT,
    build_inventory,
)


def test_public_api_usage_guides_cover_inventory_and_are_current() -> None:
    """Every public callable should have a maintained, reproducible usage record."""
    inventory = build_inventory()
    entries = [
        entry
        for entry in inventory["entries"]
        if entry["classification"] in PUBLIC_CLASSIFICATIONS and entry["kind"] in PUBLIC_KINDS
    ]
    outputs = api_usage.render_usage_pages()
    records = sum(
        content.count("**Kind:**") for path, content in outputs.items() if path.name != "index.md"
    )

    assert records == len(entries)
    assert len(entries) >= 599
    assert sum(
        content.count("**Observed usage:**")
        + content.count("**Documented usage from the source contract:**")
        + content.count("**Usage status:** No statically resolved project call site")
        for path, content in outputs.items()
        if path.name != "index.md"
    ) == len(entries)
    assert all(
        "**Invocation shape (placeholders):**" in content
        for path, content in outputs.items()
        if path.name != "index.md"
        and "**Usage status:** No statically resolved project call site" in content
    )
    assert all(
        path.is_file() and path.read_text(encoding="utf-8") == content
        for path, content in outputs.items()
    )
    assert all(
        "**Observed usage:**" in content
        or "**Documented usage from the source contract:**" in content
        or "**Usage status:** No statically resolved project call site" in content
        for path, content in outputs.items()
        if path.name != "index.md"
    )


def test_method_usage_resolves_a_public_base_class_method(monkeypatch) -> None:
    """Inherited self-calls should resolve to the owning public contract."""
    entry = {"name": "Base.dispatch", "source_module": "sample.base", "kind": "method"}
    monkeypatch.setattr(
        api_usage, "METHODS_BY_OWNER", {("sample.base", "Base", "dispatch"): [entry]}
    )
    monkeypatch.setattr(
        api_usage, "BASE_CLASSES", {("sample.impl", "Derived"): (("sample.base", "Base"),)}
    )
    tree = ast.parse("class Derived:\n    def run(self):\n        self.dispatch()\n")
    call = next(node for node in ast.walk(tree) if isinstance(node, ast.Call))
    parents = api_usage._parent_index(tree)

    matches = api_usage._candidate_entries(
        call,
        module="sample.impl",
        imports={},
        module_aliases={},
        class_aliases={},
        parents=parents,
    )

    assert matches == [entry]


def test_function_usage_generator_is_repository_relative() -> None:
    """Generated source and destination paths stay within the checked-out project."""
    assert ROOT == Path(__file__).resolve().parents[3]
    assert OUTPUT.is_relative_to(ROOT / "docs" / "api")
