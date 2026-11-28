from pathlib import Path

import yaml


def test_ci_unit_shards_cover_each_unit_test_package_once() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    workflow = yaml.safe_load((repository_root / ".github/workflows/ci.yml").read_text())
    shards = workflow["jobs"]["unit-shards"]["strategy"]["matrix"]["include"]
    assigned = [path for shard in shards for path in shard["paths"].split()]
    expected = {
        (Path(test_path).relative_to(repository_root / "tests/unit").parts[0])
        for test_path in (repository_root / "tests/unit").rglob("test_*.py")
    }
    expected_paths = {f"tests/unit/{package}" for package in expected}

    assert len(assigned) == len(set(assigned))
    assert set(assigned) == expected_paths
