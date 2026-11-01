#!/usr/bin/env python3
"""Validate tutorial notebook metadata, paths, outputs, and execution results."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, cast

import nbformat
from nbclient import NotebookClient
from nbformat.notebooknode import NotebookNode

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
MAX_NOTEBOOK_BYTES = 300_000
PRIVATE_PATH = re.compile(r"(?:/scratch/work/nguyenl37|/home/nguyenl37|C:\\Users\\)", re.IGNORECASE)
SECRET_HINT = re.compile(
    r"(?i)(api[_-]?key|password|secret|token)\s*[:=]\s*['\"]?[A-Za-z0-9_./+-]{16,}"
)


def notebook_paths() -> tuple[Path, ...]:
    """Return maintained notebooks under the documentation source tree."""
    return tuple(sorted(path for path in DOCS.rglob("*.ipynb") if "_build" not in path.parts))


def validate_notebook(path: Path) -> list[str]:
    """Return metadata and content errors for one notebook."""
    errors: list[str] = []
    relative = path.relative_to(ROOT).as_posix()
    if path.stat().st_size > MAX_NOTEBOOK_BYTES:
        errors.append(f"{relative}: notebook exceeds {MAX_NOTEBOOK_BYTES} byte policy")
    try:
        notebook: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return [f"{relative}: invalid notebook JSON: {error}"]
    metadata = notebook.get("metadata", {})
    qrl = metadata.get("qrl", {})
    title = metadata.get("title")
    if not isinstance(title, str) or not title.strip():
        errors.append(f"{relative}: missing notebook title metadata")
    if not isinstance(metadata.get("kernelspec", {}).get("name"), str):
        errors.append(f"{relative}: missing kernel metadata")
    if qrl.get("tier") not in {"A", "B", "C"}:
        errors.append(f"{relative}: qrl.tier must be A, B, or C")
    if not isinstance(qrl.get("runtime"), str) or not qrl["runtime"].strip():
        errors.append(f"{relative}: missing qrl.runtime metadata")
    if not isinstance(qrl.get("hardware"), str) or not qrl["hardware"].strip():
        errors.append(f"{relative}: missing qrl.hardware metadata")
    expected_mode = "force" if qrl.get("tier") == "A" else "off"
    actual_mode = metadata.get("mystnb", {}).get("execution_mode")
    if actual_mode != expected_mode:
        errors.append(
            f"{relative}: tier {qrl.get('tier')} requires mystnb.execution_mode={expected_mode}"
        )
    cells = notebook.get("cells", [])

    def source_text(cell: dict[str, Any]) -> str:
        """Return notebook source whether JSON encodes it as text or lines."""
        source = cell.get("source", "")
        return "".join(source) if isinstance(source, list) else str(source)

    if (
        not cells
        or cells[0].get("cell_type") != "markdown"
        or not source_text(cells[0]).lstrip().startswith("# ")
    ):
        errors.append(f"{relative}: first cell must begin with a Markdown title")
    if not any(cell.get("cell_type") == "code" for cell in cells):
        errors.append(f"{relative}: no executable code cells")
    text = "\n".join(source_text(cell) for cell in cells)
    if PRIVATE_PATH.search(text):
        errors.append(f"{relative}: contains a machine-specific private path")
    if SECRET_HINT.search(text):
        errors.append(f"{relative}: possible secret-like assignment")
    return errors


def execute_tier_a(paths: tuple[Path, ...]) -> list[str]:
    """Execute every Tier A notebook and require a generated cell output."""
    errors: list[str] = []
    for path in paths:
        notebook: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        if notebook.get("metadata", {}).get("qrl", {}).get("tier") != "A":
            continue
        relative = path.relative_to(ROOT).as_posix()
        for cell in notebook.get("cells", []):
            source = cell.get("source", "")
            if isinstance(source, list):
                cell["source"] = "".join(source)
        try:
            executed = NotebookClient(
                cast(NotebookNode, nbformat.from_dict(notebook)),  # type: ignore[no-untyped-call]
                timeout=120,
                allow_errors=False,
                resources={"metadata": {"path": str(ROOT)}},
            ).execute()
        except Exception as error:  # noqa: BLE001 - include kernel and cell failures in the report
            errors.append(f"{relative}: execution failed: {error}")
            continue
        if not any(
            cell.get("cell_type") == "code" and cell.get("outputs")
            for cell in executed.get("cells", [])
        ):
            errors.append(f"{relative}: execution generated no cell outputs")
        print(f"Executed {relative}")
    return errors


def main() -> int:
    """Validate notebook files and execute the documented CI tier."""
    paths = notebook_paths()
    errors = [error for path in paths for error in validate_notebook(path)]
    if not paths:
        errors.append("no documentation notebooks found")
    if errors:
        print("Notebook checks failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    errors = execute_tier_a(paths)
    if errors:
        print("Notebook execution failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"Notebook quality checks passed ({len(paths)} notebooks).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
