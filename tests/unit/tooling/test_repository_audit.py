from __future__ import annotations

from pathlib import Path

from tools.quality.repository_audit import (
    _audit_file_accountability,
    _git_paths,
    _tracked_paths,
    audit_sources,
    audit_tests,
)


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


def test_file_accountability_classifies_owned_and_generated_paths(tmp_path: Path) -> None:
    paths = (
        "market_data/loading.py",
        "tests/unit/trading/test_risk.py",
        "tests/unit/configuration/test_config.py",
        "tests/integration/test_pipeline_splits.py",
        "tests/integration/test_resample_m10.py",
        "tools/quality/repository_audit.py",
        "tools/check",
        "tools/documentation/public_api.py",
        "config/base/default.yaml",
        "docs/how-to/README.md",
        "docs/api/usage/market_data/example.md",
        "assets/logo.svg",
    )
    for relative in paths:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture", encoding="utf-8")

    report = _audit_file_accountability(tmp_path, [tmp_path / path for path in paths])
    by_path = {item["path"]: item for item in report["files"]}

    assert by_path["market_data/loading.py"] == {
        "path": "market_data/loading.py",
        "owner": "data_scientist_engineer",
        "disposition": "production_source",
        "eligible": True,
        "exclusion_reason": None,
        "exists": True,
    }
    assert by_path["tests/unit/trading/test_risk.py"]["owner"] == "quantitative_trading_engineer"
    assert by_path["tests/unit/configuration/test_config.py"]["owner"] == "ml_engineer"
    assert (
        by_path["tests/integration/test_pipeline_splits.py"]["owner"] == "data_scientist_engineer"
    )
    assert by_path["tests/integration/test_resample_m10.py"]["owner"] == "data_scientist_engineer"
    assert by_path["tools/quality/repository_audit.py"]["owner"] == "architect"
    assert by_path["tools/check"]["owner"] == "ci_operation_engineer"
    assert by_path["tools/documentation/public_api.py"]["owner"] == "evidence_reporting_engineer"
    assert by_path["config/base/default.yaml"]["owner"] == "ml_engineer"
    assert by_path["docs/how-to/README.md"]["disposition"] == "documentation"
    assert by_path["docs/api/usage/market_data/example.md"]["disposition"] == "generated"
    assert by_path["docs/api/usage/market_data/example.md"]["eligible"] is False
    assert by_path["assets/logo.svg"]["exclusion_reason"]
    assert report["duplicate_paths"] == []
    assert report["missing_paths"] == []


def test_file_accountability_reports_duplicate_and_missing_paths(tmp_path: Path) -> None:
    existing = tmp_path / "market_data" / "file.py"
    existing.parent.mkdir()
    existing.write_text("value = 1\n", encoding="utf-8")
    missing = tmp_path / "features" / "removed.py"
    unassigned = tmp_path / "tests" / "unit" / "unknown" / "test_unknown.py"
    unassigned.parent.mkdir(parents=True)
    unassigned.write_text("test", encoding="utf-8")

    report = _audit_file_accountability(tmp_path, [existing, existing, missing, unassigned])

    assert report["duplicate_paths"] == ["market_data/file.py"]
    assert report["missing_paths"] == ["features/removed.py"]
    assert len(report["files"]) == 3
    assert (
        next(item for item in report["files"] if item["path"] == "features/removed.py")["exists"]
        is False
    )
    assert report["unassigned_paths"] == ["tests/unit/unknown/test_unknown.py"]


def test_tracked_paths_include_unignored_and_exclude_ignored_files(tmp_path: Path) -> None:
    import subprocess

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text("ignored.tmp\n", encoding="utf-8")
    (tmp_path / "tracked.py").write_text("value = 1\n", encoding="utf-8")
    (tmp_path / "deleted.py").write_text("value = 3\n", encoding="utf-8")
    (tmp_path / "ignored.tmp").write_text("ignored", encoding="utf-8")
    (tmp_path / "untracked.py").write_text("value = 2\n", encoding="utf-8")
    (tmp_path / "docs/api/usage").mkdir(parents=True)
    generated = tmp_path / "docs/api/usage/generated.md"
    generated.write_text("generated", encoding="utf-8")
    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "add",
            ".gitignore",
            "tracked.py",
            "deleted.py",
            str(generated),
        ],
        check=True,
    )
    (tmp_path / "deleted.py").unlink()

    included = {path.relative_to(tmp_path).as_posix() for path in _tracked_paths(tmp_path)}
    all_git_paths = {path.relative_to(tmp_path).as_posix() for path in _git_paths(tmp_path)}

    assert included == {".gitignore", "tracked.py", "untracked.py", "docs/api/usage/generated.md"}
    assert "deleted.py" in all_git_paths
    assert "deleted.py" not in included
    report = _audit_file_accountability(tmp_path, _git_paths(tmp_path))
    assert report["missing_paths"] == ["deleted.py"]
