"""Contracts for the generated documentation inventory and notebook metadata."""

from __future__ import annotations

import json

from tools.documentation.check_notebooks import notebook_paths, validate_notebook
from tools.documentation.coverage import DIMENSIONS, build_coverage
from tools.documentation.coverage import OUTPUT as COVERAGE_OUTPUT
from tools.documentation.figures import validate as validate_figures
from tools.documentation.function_docstrings import missing_docstrings
from tools.documentation.inventory import OUTPUT, ROOT, build_inventory


def test_documentation_inventory_is_current_and_has_no_orphan_pages() -> None:
    """The checked-in inventory should exactly describe maintained source pages."""
    expected = json.dumps(build_inventory(), indent=2, sort_keys=True) + "\n"
    assert OUTPUT.read_text(encoding="utf-8") == expected
    report = json.loads(expected)
    assert report["page_count"] >= 100
    assert all(page["orphan_status"] == "in toctree" for page in report["pages"])


def test_subject_coverage_snapshot_is_machine_readable_and_current() -> None:
    """Coverage JSON should preserve the reviewed dimensions and topic count."""
    expected = json.dumps(build_coverage(), indent=2, sort_keys=True) + "\n"
    assert COVERAGE_OUTPUT.read_text(encoding="utf-8") == expected
    report = json.loads(expected)
    assert len(report["dimensions"]) == len(DIMENSIONS)
    assert report["subject_count"] >= 30
    assert all(set(row["dimensions"]) == set(DIMENSIONS) for row in report["subjects"])


def test_figure_registry_has_provenance_and_no_orphan_assets() -> None:
    """Every maintained image and diagram should have traceable context."""
    assert validate_figures() == []


def test_every_production_and_tooling_function_has_a_docstring() -> None:
    """Keep concise source docstrings present across the maintained code surface."""
    assert missing_docstrings() == []


def test_tutorial_notebooks_have_valid_tier_metadata_and_local_links() -> None:
    """Every notebook should pass metadata, privacy-path, and link validation."""
    failures = {
        path.relative_to(ROOT).as_posix(): validate_notebook(path)
        for path in notebook_paths()
        if validate_notebook(path)
    }
    assert failures == {}
    assert len(notebook_paths()) == 14


def test_notebook_runner_marks_only_cpu_tier_a_for_execution() -> None:
    """CI-executed notebooks must be deterministic CPU examples."""
    for path in notebook_paths():
        notebook = json.loads(path.read_text(encoding="utf-8"))
        qrl = notebook["metadata"]["qrl"]
        if qrl["tier"] == "A":
            assert qrl["hardware"] == "CPU"
            assert notebook["metadata"]["mystnb"]["execution_mode"] == "force"
