from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_distribution_and_command_names_are_project_oriented() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    scripts = project["scripts"]

    assert project["name"] == "quantitative-rl-trading-system"
    assert "Add your description here" not in project["description"]
    expected = {
        "data": "market_data.cli:main",
        "train": "training.cli:main",
        "evaluate": "evaluation.cli:main",
        "experiment": "experiments.cli:main",
        "compute": "compute.cli:main",
    }
    for command, target in expected.items():
        assert scripts[f"qrl-{command}"] == target

    legacy_aliases = {
        "thesis-data": "qrl-data",
        "thesis-train": "qrl-train",
        "thesis-evaluate": "qrl-evaluate",
        "thesis-experiment-run": "qrl-experiment",
        "thesis-compute": "qrl-compute",
    }
    for legacy, canonical in legacy_aliases.items():
        assert scripts[legacy] == scripts[canonical]


def test_command_reference_marks_legacy_names_as_deprecated_aliases() -> None:
    reference = (ROOT / "docs/reference/cli.md").read_text(encoding="utf-8")
    assert "qrl-experiment" in reference
    assert "deprecated compatibility aliases" in reference.lower()
    for command in (
        "thesis-data",
        "thesis-train",
        "thesis-evaluate",
        "thesis-experiment-run",
        "thesis-compute",
    ):
        assert command in reference
