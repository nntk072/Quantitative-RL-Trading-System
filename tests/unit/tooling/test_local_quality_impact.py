"""Test advisory selection and resource planning with small synthetic inputs."""

from __future__ import annotations

from pathlib import Path

import pytest
from tools.quality.local_checks.impact import (
    reverse_imports,
    select_impacted_tests,
    transitive_import_dependants,
)
from tools.quality.local_checks.resources import (
    quality_cache_key,
    schedule_resource_waves,
    worker_capacity_budget,
)


def test_impact_combines_transitive_imports_and_contexts() -> None:
    sources = {
        "trading/risk/budget.py": "x = 1",
        "simulation/env.py": "from trading.risk import budget",
        "tests/unit/test_env.py": "import simulation.env",
        "tests/unit/test_dynamic.py": "",
        "tests/unit/test_other.py": "",
    }
    tests = {p for p in sources if p.startswith("tests/")}
    result = select_impacted_tests(
        {"trading/risk/budget.py"},
        sources,
        tests,
        {"trading/risk/budget.py": {"tests/unit/test_dynamic.py"}},
    )
    assert result["mode"] == "impacted"
    assert result["tests"] == ["tests/unit/test_dynamic.py", "tests/unit/test_env.py"]


def test_impact_relative_imports_and_deleted_sources() -> None:
    sources = {"pkg/a.py": "", "pkg/b.py": "from . import a", "tests/test_b.py": "import pkg.b"}
    assert transitive_import_dependants(reverse_imports(sources), {"pkg/a.py"}) == set(sources)
    result = select_impacted_tests({"pkg/deleted.py"}, sources, {"tests/test_b.py"}, {})
    assert result["mode"] == "full"
    assert result["tests"] == ["tests/test_b.py"]


def test_memory_and_cpu_limits_are_both_respected() -> None:
    mib = 1024 * 1024
    result = worker_capacity_budget(
        8, 1000, available_bytes=3500 * mib, affinity_cpus=6, quota_cpus=4
    )
    assert result["workers"] == 2
    assert (
        worker_capacity_budget(8, 1000, available_bytes=100 * mib, affinity_cpus=6)["workers"] == 0
    )
    assert worker_capacity_budget(8, 1000, available_bytes=None, affinity_cpus=6)["workers"] == 1


def test_cache_keys_separate_profiles_and_lock_revisions(tmp_path: Path) -> None:
    lock = tmp_path / "uv.lock"
    lock.write_text("first")
    cpu = quality_cache_key(lock, "cpu", {"uv": "1"})
    assert cpu != quality_cache_key(lock, "gpu", {"uv": "1"})
    lock.write_text("second")
    assert cpu != quality_cache_key(lock, "cpu", {"uv": "1"})


def test_waves_do_not_oversubscribe_memory() -> None:
    groups = {"a": (10.0, 8), "b": (9.0, 8), "c": (4.0, 2)}
    waves = schedule_resource_waves(groups, 3, 10)
    assert sorted(name for wave in waves for name in wave) == sorted(groups)
    assert all(sum(groups[name][1] for name in wave) <= 10 for wave in waves)
    with pytest.raises(ValueError, match="memory"):
        schedule_resource_waves({"too_large": (1.0, 11)}, 3, 10)
