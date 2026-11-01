"""Generate and check the source-defined Python API inventory."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from tools.documentation.public_api_inventory import (
    PUBLIC_CLASSIFICATIONS,
    PUBLIC_KINDS,
    ROOT,
    _missing_public_docstrings,
    _production_function_docstring_gaps,
    _production_numpy_docstrings,
    build_inventory,
)


def _render_markdown(inventory: dict[str, Any]) -> str:
    """Render the stable and compatibility export list for Sphinx."""
    entries = inventory["entries"]
    visible = [item for item in entries if item["classification"] in PUBLIC_CLASSIFICATIONS]
    totals = Counter(item["classification"] for item in entries)
    by_package: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in visible:
        by_package[entry["package"]].append(entry)
    lines = [
        "# Public Python API inventory",
        "",
        "This file is generated from production ``__all__`` declarations and the source definitions",
        "they re-export. Do not edit it by hand. Regenerate it with ``python -m",
        "tools.documentation.public_api --write``.",
        "",
        "Package initializers define stable public boundaries. Names exported from individual",
        "modules are recorded as cross-package internal contracts in the companion JSON file.",
        "Compatibility names and experimental exports remain labeled explicitly.",
        "",
        "| Classification | Exported names |",
        "|---|---:|",
    ]
    for category in (
        "stable",
        "experimental",
        "compatibility-only",
        "cross-package internal",
        "private implementation",
    ):
        lines.append(f"| {category} | {totals[category]} |")
    lines.extend(["", "## Public package exports", ""])
    for package in sorted(by_package):
        lines.extend(
            [
                f"### `{package}`",
                "",
                "| Exported name | Kind | Source | Status |",
                "|---|---|---|---|",
            ]
        )
        for item in sorted(
            by_package[package], key=lambda row: (row["exported_from"], row["name"])
        ):
            line = f"#L{item['source_line']}" if item["source_line"] else ""
            source = (
                f"[{item['source_module']}]({Path('../../', item['source_path']).as_posix()}{line})"
            )
            lines.append(
                f"| `{item['name']}` | {item['kind']} | {source} | {item['classification']} |"
            )
        lines.append("")
    commands = inventory["cli_commands"]
    lines.extend(
        ["## Installed commands", "", "| Command | Entry point | Source |", "|---|---|---|"]
    )
    for command in commands:
        source = f"[{command['source_path']}](../../{command['source_path']})"
        lines.append(f"| `{command['name']}` | `{command['target']}` | {source} |")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _json_text(inventory: dict[str, Any]) -> str:
    """Serialize the complete symbol inventory deterministically."""
    return json.dumps(inventory, indent=2, sort_keys=True) + "\n"


def _write_inventory(root: Path, inventory: dict[str, Any]) -> None:
    """Write generated API data and its browsable summary."""
    json_path = root / "docs/reference/public_api.json"
    markdown_path = root / "docs/reference/public_api.md"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(_json_text(inventory), encoding="utf-8")
    markdown_path.write_text(_render_markdown(inventory), encoding="utf-8")


def _check_generated(root: Path, inventory: dict[str, Any]) -> list[str]:
    """Check that committed generated inventory matches the current sources."""
    expected = {
        root / "docs/reference/public_api.json": _json_text(inventory),
        root / "docs/reference/public_api.md": _render_markdown(inventory),
    }
    return [
        str(path.relative_to(root))
        for path, content in expected.items()
        if not path.is_file() or path.read_text(encoding="utf-8") != content
    ]


def _print_report(root: Path, inventory: dict[str, Any]) -> list[str]:
    """Print coverage totals and return public API documentation failures."""
    entries = inventory["entries"]
    classes = [
        row
        for row in entries
        if row["classification"] in PUBLIC_CLASSIFICATIONS and row["kind"] in PUBLIC_KINDS
    ]
    documented = sum(bool(row["documented"]) for row in classes)
    missing = _missing_public_docstrings(inventory)
    function_gaps = _production_function_docstring_gaps(root)
    numpy = _production_numpy_docstrings(root)
    print(
        f"Public API callables: {documented}/{len(classes)} documented "
        f"({100 * documented / len(classes):.2f}%); {len(missing)} undocumented; "
        f"{len(function_gaps)} function Google-style gaps; "
        f"{len(numpy)} production modules contain NumPy-style sections."
    )
    failures = [*(f"undocumented public API: {item}" for item in missing)]
    failures.extend(f"production function docstring: {item}" for item in function_gaps)
    failures.extend(f"NumPy-style docstring section: {item}" for item in numpy)
    return failures


def main(argv: list[str] | None = None) -> int:
    """Generate or validate the source-derived API inventory and docstrings."""
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="regenerate inventory files")
    mode.add_argument("--check", action="store_true", help="check inventory and docstring quality")
    mode.add_argument("--report", action="store_true", help="report current docstring quality only")
    args = parser.parse_args(argv)
    root = ROOT
    inventory = build_inventory(root)
    if args.write:
        _write_inventory(root, inventory)
    if args.check:
        stale = _check_generated(root, inventory)
        if stale:
            parser.error("generated API inventory is stale: " + ", ".join(stale))
    failures = _print_report(root, inventory)
    if failures and args.check:
        for failure in failures:
            print(f"- {failure}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
