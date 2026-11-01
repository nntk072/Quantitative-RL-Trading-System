from __future__ import annotations

import shutil
import subprocess
import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_architecture_docs_cover_active_production_packages() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    packages = pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"]
    building_blocks = (ROOT / "docs/architecture/building_blocks.md").read_text(encoding="utf-8")
    dependency_model = (ROOT / "docs/architecture/dependency_model.md").read_text(encoding="utf-8")

    for package in packages:
        assert f"`{package}/`" in building_blocks, package
        assert package in dependency_model, package
        assert (ROOT / package / "README.md").is_file(), package

    architecture_views = (
        "context.md",
        "building_blocks.md",
        "dependency_model.md",
        "domain_model.md",
        "data_flow.md",
        "model_and_policy_architecture.md",
        "runtime/data_and_features.md",
        "runtime/environment_step.md",
        "runtime/training.md",
        "runtime/evaluation.md",
        "runtime/experiment_run.md",
        "runtime/live_execution.md",
        "deployment.md",
        "cross_cutting_concerns.md",
        "quality_attributes.md",
        "risks_and_technical_debt.md",
    )
    for view in architecture_views:
        assert (ROOT / "docs/architecture" / view).is_file(), view


def test_generated_data_and_runtime_paths_follow_repository_ignore_policy(
    tmp_path: Path,
) -> None:
    isolated_repo = tmp_path / "ignore_contract_repo"
    isolated_repo.mkdir()
    shutil.copyfile(ROOT / ".gitignore", isolated_repo / ".gitignore")
    subprocess.run(["git", "init", "--quiet"], cwd=isolated_repo, check=True)

    expected = [
        ("data/normal/US100.cash.csv", True),
        ("data/normal/training/US100.cash.csv", True),
        ("data/normal/US100.cash_2024.csv", True),
        ("data/discretion/US100.cash.csv", True),
        ("data/discretion/testing/US100.cash.csv", True),
        ("data/normal/README.md", False),
        ("data/discretion/README.md", False),
        ("data/examples/sample.csv", False),
        ("data/unclassified.csv", True),
        ("cache/generated.parquet", True),
        ("outputs/run/model.zip", True),
        ("logs/service.log", True),
        ("baseline/validated.json", False),
    ]
    for relative_path, ignored in expected:
        result = subprocess.run(
            ["git", "check-ignore", "--quiet", "--no-index", "--", relative_path],
            cwd=isolated_repo,
            check=False,
        )
        assert (result.returncode == 0) is ignored, relative_path


def test_docker_test_services_isolate_writable_runtime_roots() -> None:
    compose_path = ROOT / "docker-compose.yml"
    services = yaml.safe_load(compose_path.read_text(encoding="utf-8"))["services"]
    readonly_inputs = {
        "./config:/app/config:ro",
        "./docs:/app/docs:ro",
        "./data/examples:/app/data/examples:ro",
    }
    isolated_writes = {"/app/outputs", "/app/models", "/app/cache", "/app/logs"}

    for service_name in ("test", "test-gpu"):
        service = services[service_name]
        assert set(service["volumes"]) == readonly_inputs
        assert set(service["tmpfs"]) == isolated_writes
