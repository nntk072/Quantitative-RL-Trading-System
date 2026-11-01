from __future__ import annotations

from pathlib import Path

from tools.quality.repository_audit import audit_sources, audit_tests


def test_source_audit_counts_docstrings_and_flags_comment_candidates(tmp_path: Path) -> None:
    source = tmp_path / "pkg" / "module.py"
    source.parent.mkdir()
    source.write_text(
        '"""Module summary."""\n'
        "# Helpers\n"
        "def public(value: int) -> int:\n"
        '    """Return the value.\n\n    Args:\n        value: Number to return.\n    """\n'
        "    return value  # keep caller value\n"
        "\n"
        "def _private() -> None:\n"
        "    pass\n",
        encoding="utf-8",
    )

    metrics = audit_sources(tmp_path, [source])

    assert metrics["files"] == 1
    assert metrics["public_definition_candidates"] == 1
    assert metrics["definitions_with_docstrings"] == 1
    assert metrics["google_style_docstrings"] == 1
    assert metrics["module_docstrings"] == 1
    assert metrics["comment_tokens"] == 2
    assert metrics["standalone_comment_lines"] == 1
    assert metrics["inline_comment_tokens"] == 1
    assert metrics["low_signal_comment_candidates"] == 1


def test_source_audit_counts_overload_implementation_once(tmp_path: Path) -> None:
    source = tmp_path / "pkg" / "overloaded.py"
    source.parent.mkdir()
    source.write_text(
        "from typing import overload\n"
        "@overload\n"
        "def parse(value: int) -> int: ...\n"
        "@overload\n"
        "def parse(value: str) -> str: ...\n"
        "def parse(value: int | str) -> int | str:\n"
        '    """Return the input in its existing representation."""\n'
        "    return value\n",
        encoding="utf-8",
    )

    metrics = audit_sources(tmp_path, [source])

    assert metrics["public_definition_candidates"] == 1
    assert metrics["definitions_with_docstrings"] == 1


def test_test_audit_reports_suite_files_and_test_functions(tmp_path: Path) -> None:
    test_file = tmp_path / "tests" / "unit" / "test_sample.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text(
        "class TestNumbers:\n"
        "    def test_positive(self):\n"
        "        assert 1 > 0\n"
        "\n"
        "def test_zero():\n"
        "    assert 0 == 0\n",
        encoding="utf-8",
    )

    metrics = audit_tests(tmp_path, [test_file])

    assert metrics["python_files"] == 1
    assert metrics["test_module_files"] == 1
    assert metrics["test_functions_and_methods"] == 2
    assert metrics["test_classes"] == 1
    assert metrics["python_files_by_suite"] == {"unit": 1}
    assert metrics["test_modules_by_suite"] == {"unit": 1}
    assert metrics["test_functions_by_suite"] == {"unit": 2}
