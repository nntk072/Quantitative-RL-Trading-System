"""Contracts for the generated documentation inventory and notebook metadata."""

from __future__ import annotations

import json

from tools.documentation.check_notebooks import notebook_paths, validate_notebook
from tools.documentation.inventory import OUTPUT, ROOT, build_inventory


def test_documentation_inventory_is_current_and_has_no_orphan_pages() -> None:
    """The checked-in inventory should exactly describe maintained source pages."""
    expected = json.dumps(build_inventory(), indent=2, sort_keys=True) + "\n"
    assert OUTPUT.read_text(encoding="utf-8") == expected
    report = json.loads(expected)
    assert report["page_count"] >= 100
    assert all(page["orphan_status"] == "in toctree" for page in report["pages"])


def test_tutorial_notebooks_have_valid_tier_metadata_and_local_links() -> None:
    """Every notebook should pass metadata, privacy-path, and link validation."""
    failures = {
        path.relative_to(ROOT).as_posix(): validate_notebook(path)
        for path in notebook_paths()
        if validate_notebook(path)
    }
    assert failures == {}
    assert len(notebook_paths()) == 12


def test_notebook_runner_marks_only_cpu_tier_a_for_execution() -> None:
    """CI-executed notebooks must be deterministic CPU examples."""
    for path in notebook_paths():
        notebook = json.loads(path.read_text(encoding="utf-8"))
        qrl = notebook["metadata"]["qrl"]
        if qrl["tier"] == "A":
            assert qrl["hardware"] == "CPU"
            assert notebook["metadata"]["mystnb"]["execution_mode"] == "force"
