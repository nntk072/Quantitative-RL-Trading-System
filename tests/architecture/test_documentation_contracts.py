from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from tools.documentation.check_docs import (
    SUBPACKAGE_GUIDES,
    broken_links,
    missing_source_paths,
    validate,
)
from tools.documentation.package_dependency_model import (
    DEFAULT_PAGE,
    PACKAGES,
    package_imports,
    render_graph,
    replace_generated_block,
)

ROOT = Path(__file__).resolve().parents[2]


def test_package_dependency_diagram_is_deterministic_and_current() -> None:
    first = render_graph(ROOT)
    second = render_graph(ROOT)
    page = DEFAULT_PAGE.read_text(encoding="utf-8")

    assert first == second
    assert replace_generated_block(page, first) == page
    assert tuple(package_imports(ROOT)) == PACKAGES


def test_dependency_model_check_mode_succeeds_from_repository_root() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "tools/documentation/package_dependency_model.py",
            "--check",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_maintained_documentation_has_local_guides_and_resolving_links() -> None:
    assert validate(ROOT) == []


def test_each_module_guide_has_its_own_uml_view() -> None:
    guides = sorted((ROOT / "docs/modules").glob("*.md"))
    assert guides
    missing = [
        str(guide.relative_to(ROOT))
        for guide in guides
        if "```mermaid\nclassDiagram" not in guide.read_text(encoding="utf-8")
    ]
    assert not missing, f"module guides without a UML class view: {missing}"


def test_each_subpackage_guide_has_its_own_uml_view() -> None:
    missing = [
        relative
        for relative in SUBPACKAGE_GUIDES
        if "```mermaid\nclassDiagram" not in (ROOT / relative).read_text(encoding="utf-8")
    ]
    assert not missing, f"subpackage guides without a UML class view: {missing}"


def test_markdown_link_checker_reports_broken_relative_targets(tmp_path: Path) -> None:
    page = tmp_path / "guide.md"
    (tmp_path / "reference.md").write_text("# Reference\n", encoding="utf-8")
    page.write_text(
        "[good](reference.md) [anchor](#section) [bad](missing.md)\n",
        encoding="utf-8",
    )

    assert broken_links(page) == [(1, "missing.md")]


def test_source_path_checker_reports_missing_code_references(tmp_path: Path) -> None:
    page = tmp_path / "guide.md"
    page.write_text("See `features/missing.py` and `<feature>.py`.\n", encoding="utf-8")

    assert missing_source_paths(page) == [(1, "features/missing.py")]
