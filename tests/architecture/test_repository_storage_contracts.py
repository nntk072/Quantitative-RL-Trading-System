from __future__ import annotations

import csv
import shutil
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_architecture_inventory_covers_active_git_tracked_paths() -> None:
    inventory_path = ROOT / "docs/architecture/repository_file_ownership_inventory.csv"
    with inventory_path.open(newline="", encoding="utf-8") as source:
        rows = list(csv.DictReader(source))
    inventory_paths = [row["path"] for row in rows]
    tracked_paths = set(
        filter(
            None,
            subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0"),
        )
    )
    active_tracked_paths = {
        path for path in tracked_paths if (ROOT / path).exists() or (ROOT / path).is_symlink()
    }

    assert len(inventory_paths) == len(set(inventory_paths)), "inventory paths must be unique"
    assert not (active_tracked_paths - set(inventory_paths)), sorted(
        active_tracked_paths - set(inventory_paths)
    )


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
