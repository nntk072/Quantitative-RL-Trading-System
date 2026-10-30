"""Contracts for test execution-marker defaults and gate declarations."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from tests.conftest import execution_markers_for_test

ROOT = Path(__file__).resolve().parents[2]


def test_test_directory_assignments_describe_execution_not_ownership() -> None:
    assert execution_markers_for_test(Path("tests/integration/test_flow.py")) == ("integration",)
    assert execution_markers_for_test(Path("tests/integration/backtest/test_fills.py")) == (
        "integration",
    )
    assert execution_markers_for_test(Path("tests/research/test_report.py")) == ("research",)
    assert execution_markers_for_test(Path("tests/research/benchmarks/test_profile.py")) == (
        "research",
    )
    assert execution_markers_for_test(Path("tests/architecture/test_dependency_rules.py")) == (
        "architecture",
    )
    assert execution_markers_for_test(Path("tests/unit/simulation/test_backtest/test_fill.py")) == (
        "unit",
    )
    assert execution_markers_for_test(Path("tests/unit/features/test_cache.py")) == ("unit",)
    assert (
        execution_markers_for_test(Path("tests/unit/features/test_cache.py"), frozenset({"slow"}))
        == ()
    )
    with pytest.raises(ValueError, match="classified suite directory"):
        execution_markers_for_test(Path("tests/test_unclassified.py"))


def test_pytest_declares_every_execution_marker() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text())
    declared = {
        entry.split(":", maxsplit=1)[0]
        for entry in config["tool"]["pytest"]["ini_options"]["markers"]
    }
    assert declared == {
        "unit",
        "integration",
        "architecture",
        "slow",
        "gpu",
        "triton",
        "research",
    }


def test_named_test_gates_exclude_other_execution_requirements() -> None:
    dispatcher = (ROOT / "tools/check").read_text()
    assert (
        "unit and not slow and not integration and not architecture and not gpu and not triton and not research"
        in dispatcher
    )
    assert "tests/unit" in dispatcher
    assert 'pytest -q -m "integration and not slow" tests' in dispatcher
    assert 'pytest -q -m "research and not slow" tests' in dispatcher
    assert "integration and not slow" in dispatcher
    assert "research and not slow" in dispatcher


def test_nightly_workflow_uses_the_same_tier_c_gate_commands() -> None:
    workflow = (ROOT / ".github/workflows/nightly.yml").read_text()
    assert "./tools/check research" in workflow
    assert "./tools/check slow" in workflow
    assert "uv run pytest" not in workflow


def test_release_workflow_uses_canonical_validation_and_buildkit_cache() -> None:
    workflow = (ROOT / ".github/workflows/release.yml").read_text()
    assert "./tools/check full" in workflow
    assert "/var/lib/docker" not in workflow
    assert "cache-from: type=gha" in workflow
