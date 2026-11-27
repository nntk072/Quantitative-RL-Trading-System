from __future__ import annotations

import ast
import subprocess
import sys
import tomllib
from pathlib import Path

from tools.documentation.check_docs import (
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
from tools.quality.repository_audit import build_audit

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


def test_every_product_package_readme_has_purpose_api_and_invariants() -> None:
    product_packages = (
        "configuration",
        "artifacts",
        "market_data",
        "features",
        "trading",
        "simulation",
        "models",
        "decisioning",
        "learning",
        "training",
        "evaluation",
        "experiments",
        "live",
        "integrations",
        "compute",
    )
    missing: list[str] = []
    for package in product_packages:
        directory = ROOT / package
        readme = next(
            (
                candidate
                for candidate in (directory / "README.md", directory / "README.rst")
                if candidate.is_file()
            ),
            None,
        )
        if readme is None:
            missing.append(f"{directory.relative_to(ROOT)}: missing README")
            continue
        contents = readme.read_text(encoding="utf-8").lower()
        for section in ("purpose", "public api", "invariants"):
            if not any(
                line.lstrip("# ").strip() == section
                for line in contents.splitlines()
                if line.startswith("#")
            ):
                missing.append(f"{readme.relative_to(ROOT)}: missing {section} section")

    assert not missing, "package README contract failures:\n" + "\n".join(missing)


def test_every_product_package_initializer_declares_all() -> None:
    product_packages = (
        "configuration",
        "artifacts",
        "market_data",
        "features",
        "trading",
        "simulation",
        "models",
        "decisioning",
        "learning",
        "training",
        "evaluation",
        "experiments",
        "live",
        "integrations",
        "compute",
    )
    missing = []
    for package in product_packages:
        for init_file in (ROOT / package).rglob("__init__.py"):
            module = ast.parse(init_file.read_text(encoding="utf-8"))
            has_all = any(
                (
                    isinstance(node, ast.Assign)
                    and any(
                        isinstance(target, ast.Name) and target.id == "__all__"
                        for target in node.targets
                    )
                )
                or (
                    isinstance(node, ast.AnnAssign)
                    and isinstance(node.target, ast.Name)
                    and node.target.id == "__all__"
                )
                for node in module.body
            )
            if not has_all:
                missing.append(str(init_file.relative_to(ROOT)))

    assert not missing, "package initializers missing explicit __all__:\n" + "\n".join(missing)


def test_documentation_link_checker_ignores_paths_in_fenced_examples(tmp_path: Path) -> None:
    document = tmp_path / "guide.md"
    document.write_text(
        "Example: `<tests/example.py>`\n\n"
        "```markdown\n[upstream](missing.md)\n`tests/example.py`\n```\n",
        encoding="utf-8",
    )

    assert broken_links(document) == []
    assert missing_source_paths(document) == []


def test_documentation_link_checker_still_rejects_broken_maintained_links(
    tmp_path: Path,
) -> None:
    document = tmp_path / "guide.md"
    document.write_text("[missing](missing.md)\n", encoding="utf-8")

    assert broken_links(document) == [(1, "missing.md")]


def test_repository_documentation_entrypoints_and_site_configuration_exist() -> None:
    required = (
        "ARCHITECTURE.md",
        "CHANGELOG.md",
        "SECURITY.md",
        "SUPPORT.md",
        "CITATION.cff",
        "docs/decisions/repository_standards.md",
        "docs/development/documentation.md",
        "docs/conf.py",
        "docs/index.md",
        "docs/api/index.md",
        "docs/reference/public_api.md",
        "docs/reference/public_api.json",
        ".github/workflows/pages.yml",
    )
    missing = [path for path in required if not (ROOT / path).is_file()]
    assert not missing, f"missing repository documentation entrypoints: {missing}"


def test_project_license_matches_package_and_citation_metadata() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")

    assert project["license"] == "MIT"
    assert project["license-files"] == ["LICENSE"]
    assert "license: MIT" in citation
    assert "MIT License" in license_text


def test_every_public_production_definition_has_a_google_style_docstring() -> None:
    production = build_audit(ROOT)["production"]

    assert production["parse_errors"] == []
    assert production["definitions_with_docstrings"] == production["public_definition_candidates"]
    assert production["numpy_style_docstrings"] == 0


def test_generated_public_api_inventory_matches_source() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "tools.documentation.public_api", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_coverage_floor_is_measured_from_main() -> None:
    import json

    baseline = json.loads(
        (ROOT / "tools/quality/coverage_baseline.json").read_text(encoding="utf-8")
    )
    assert baseline["source_branch"] == "main"
    assert len(baseline["source_commit"]) == 40


def test_documentation_ci_builds_the_site_for_main() -> None:
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    pages = (ROOT / ".github/workflows/pages.yml").read_text(encoding="utf-8")
    sphinx_config = (ROOT / "docs/conf.py").read_text(encoding="utf-8")

    assert "  docs:" in ci
    assert "./tools/check docs" in ci
    assert "branches: [main]" in pages
    assert "github.ref == 'refs/heads/main'" in pages
    assert "sphinx.ext.napoleon" in sphinx_config
    assert "autoapi.extension" in sphinx_config


def test_autoapi_ignores_shadowed_legacy_modules() -> None:
    import runpy

    config = runpy.run_path(str(ROOT / "docs/conf.py"))
    ignored = set(config.get("autoapi_ignore", ()))

    assert {
        "*/evaluation/plotting/orders.py",
        "*/evaluation/plotting/performance.py",
        "*/simulation/environment/diagnostics.py",
    } <= ignored


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
