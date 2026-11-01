from __future__ import annotations

import re
import subprocess
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
    assert set(scripts) == {"orchestra", *(f"qrl-{command}" for command in expected)}


def test_command_reference_documents_canonical_names() -> None:
    reference = (ROOT / "docs/reference/cli.md").read_text(encoding="utf-8")
    assert "qrl-experiment" in reference
    assert "deprecated compatibility aliases" not in reference.lower()


def test_runtime_tooling_uses_only_qrl_environment_names() -> None:
    runtime_tools = (
        ROOT / "tools/check",
        ROOT / "tools/setup-venv",
        ROOT / "tools/setup-venv-x86",
        ROOT / "tools/setup-venv-mi210",
        ROOT / "tools/setup-venv-v100",
        ROOT / "scripts/compute/slurm/experiment_run_recovery_supervisor.sh",
    )
    for path in runtime_tools:
        deprecated_prefix = "TH" + "ESIS_"
        assert deprecated_prefix not in path.read_text(encoding="utf-8").upper(), path.relative_to(
            ROOT
        )


def test_current_project_files_use_neutral_identity() -> None:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    preserved_records = ("baseline/", "docs/architecture/migrations/", "evidence/")
    legacy_word = "th" + "esis"
    legacy_pattern = re.compile(rf"\b{legacy_word}\b", re.IGNORECASE)
    text_suffixes = {".cff", ".csv", ".md", ".py", ".sh", ".toml", ".txt", ".yaml", ".yml"}

    for raw_path in result.stdout.split(b"\0"):
        if not raw_path:
            continue
        relative = raw_path.decode()
        if relative.startswith(preserved_records) or Path(relative).suffix not in text_suffixes:
            continue
        path = ROOT / relative
        if not path.is_file():
            continue
        contents = path.read_text(encoding="utf-8")
        assert legacy_pattern.search(relative) is None, relative
        assert legacy_pattern.search(contents) is None, relative
