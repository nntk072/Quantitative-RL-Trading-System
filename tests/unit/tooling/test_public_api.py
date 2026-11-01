from __future__ import annotations

from pathlib import Path

from tools.documentation.public_api_inventory import (
    _missing_public_docstrings,
    _production_function_docstring_gaps,
    build_inventory,
)


def _write_package(root: Path) -> None:
    (root / "pyproject.toml").write_text(
        '[tool.hatch.build.targets.wheel]\npackages = ["sample"]\n', encoding="utf-8"
    )
    package = root / "sample"
    package.mkdir()
    (package / "__init__.py").write_text(
        '"""Stable sample package API."""\n'
        "from .models import PublicModel\n"
        '_PUBLIC_EXPORTS = {"LazyModel": ("sample.lazy", "LazyModel")}\n'
        '__all__ = ["PublicModel"] + list(_PUBLIC_EXPORTS)\n',
        encoding="utf-8",
    )
    (package / "models.py").write_text(
        '"""Public model and a local helper."""\n'
        '__all__ = ["PublicModel", "module_helper"]\n'
        "class PublicModel:\n"
        '    """Model exported through the package facade."""\n'
        "    def ready(self) -> bool:\n"
        '        """Return whether the model is ready."""\n'
        "        return True\n"
        "    def unready(self) -> bool:\n"
        "        return False\n"
        "    def _internal(self) -> None:\n"
        "        pass\n"
        "def module_helper() -> None:\n"
        '    """Support another symbol within the package."""\n'
        "    return None\n",
        encoding="utf-8",
    )
    (package / "lazy.py").write_text(
        '"""Lazy public implementation."""\n'
        "class LazyModel:\n"
        '    """Model imported only when requested."""\n'
        "    pass\n",
        encoding="utf-8",
    )


def test_inventory_resolves_facade_and_lazy_exports_and_flags_public_gaps(
    tmp_path: Path,
) -> None:
    _write_package(tmp_path)

    inventory = build_inventory(tmp_path)
    entries = inventory["entries"]
    stable = [
        entry
        for entry in entries
        if entry["exported_from"] == "sample" and entry["kind"] == "class"
    ]
    method = next(entry for entry in entries if entry["name"] == "PublicModel.unready")

    assert {entry["name"] for entry in stable} == {"PublicModel", "LazyModel"}
    assert {entry["source_module"] for entry in stable} == {"sample.models", "sample.lazy"}
    assert not method["documented"]
    assert "PublicModel._internal" not in {entry["name"] for entry in entries}
    assert len(_missing_public_docstrings(inventory)) == 1


def test_inventory_classifies_non_facade_exports_as_internal(tmp_path: Path) -> None:
    _write_package(tmp_path)

    entries = build_inventory(tmp_path)["entries"]
    helper = next(entry for entry in entries if entry["name"] == "module_helper")

    assert helper["classification"] == "cross-package internal"
    assert helper["documented"]


def test_function_docstring_gate_checks_private_parameters_and_results(tmp_path: Path) -> None:
    _write_package(tmp_path)
    (tmp_path / "sample" / "quality.py").write_text(
        "def _missing_argument(value: int) -> int:\n"
        '    """Return a value.\n\n'
        "    Returns:\n"
        "        The value.\n"
        '    """\n'
        "    return value\n\n"
        "def _missing_result(value: int) -> int:\n"
        '    """Return a value.\n\n'
        "    Args:\n"
        "        value: Value to return.\n"
        '    """\n'
        "    return value\n\n"
        "def _documented(value: int) -> int:\n"
        '    """Return the value.\n\n'
        "    Args:\n"
        "        value: Value to return.\n\n"
        "    Returns:\n"
        "        The supplied value.\n"
        '    """\n'
        "    return value\n",
        encoding="utf-8",
    )

    failures = _production_function_docstring_gaps(tmp_path)

    assert any("_missing_argument: missing Args entry for value" in item for item in failures)
    assert any("_missing_result: missing Returns description" in item for item in failures)
    assert not any("_documented" in item for item in failures)
