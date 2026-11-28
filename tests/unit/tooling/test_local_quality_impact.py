"""Test advisory selection and resource planning with small synthetic inputs."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from tools.quality.local_checks.coverage_tools import (
    changed_coverage_metrics,
    changed_source_lines,
    validate_coverage_report,
)
from tools.quality.local_checks.impact import (
    reverse_imports,
    select_impacted_tests,
    transitive_import_dependants,
)
from tools.quality.local_checks.receipts import read_collected_inventory, validate_test_receipts
from tools.quality.local_checks.resources import (
    quality_cache_key,
    schedule_resource_waves,
    worker_capacity_budget,
)
from tools.quality.local_checks.run_evidence import (
    quality_file_sha256,
    verify_quality_manifest,
    write_quality_json,
)
from tools.quality.local_checks.test_scheduling import balance_test_shards


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


def test_impact_falls_back_for_dynamic_import_resolution() -> None:
    sources = {
        "pkg/a.py": "import importlib\nimportlib.import_module(name)",
        "tests/test_a.py": "import pkg.a",
    }
    result = select_impacted_tests(
        {"pkg/a.py"}, sources, {"tests/test_a.py"}, {"pkg/a.py": {"tests/test_a.py"}}
    )
    assert result["mode"] == "full"


def test_changed_coverage_counts_branches_without_counting_exclusions() -> None:
    path = "trading/risk/sample.py"
    changed = changed_source_lines(
        "diff --git a/trading/risk/sample.py b/trading/risk/sample.py\n"
        "+++ b/trading/risk/sample.py\n@@ -3,0 +4,3 @@\n"
    )
    row = {
        "executed_lines": [4],
        "missing_lines": [5],
        "excluded_lines": [6],
        "executed_branches": [[4, 5]],
        "missing_branches": [[4, 7]],
        "summary": {
            "covered_lines": 1,
            "num_statements": 2,
            "covered_branches": 1,
            "num_branches": 2,
        },
    }
    report = {"files": {path: row}, "meta": {"branch_coverage": True}}
    validate_coverage_report(report, False)
    result = changed_coverage_metrics(report, changed, ["trading/"])["files"][path]
    assert result["statement_total"] == 2
    assert result["branch_total"] == 2
    assert result["excluded_changed_lines"] == [6]
    row["missing_lines"] = [4]
    with pytest.raises(ValueError, match="Overlapping"):
        validate_coverage_report(report, False)


def test_receipts_reject_partial_and_duplicate_evidence(tmp_path: Path) -> None:
    path = tmp_path / "receipts.jsonl"
    node = "tests/test_a.py::test_a"
    rows = [
        {"nodeid": node, "phase": phase, "outcome": "passed", "seconds": 0.1, "xfail": False}
        for phase in ("setup", "call", "teardown")
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows))
    assert validate_test_receipts(path, {node})[node]["status"] == "passed"
    with pytest.raises(ValueError, match="missing"):
        validate_test_receipts(path, {node, "tests/test_b.py::test_b"})
    path.write_text("\n".join(json.dumps(row) for row in rows + [rows[0]]))
    with pytest.raises(ValueError, match="Duplicate"):
        validate_test_receipts(path, {node})


def test_inventory_and_shards_reject_missing_or_duplicate_nodes(tmp_path: Path) -> None:
    rows = [{"nodeid": "tests/test_a.py::test_a"}, {"nodeid": "tests/test_b.py::test_b"}]
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    write_quality_json(first, rows)
    write_quality_json(second, rows[:1])
    with pytest.raises(ValueError, match="different"):
        read_collected_inventory([first, second])
    plan = balance_test_shards(rows, {rows[0]["nodeid"]: 10.0}, 2, True)
    assert sorted(node for shard in plan for node in shard["nodes"]) == sorted(
        row["nodeid"] for row in rows
    )
    with pytest.raises(ValueError, match="Invalid"):
        balance_test_shards(rows + rows[:1], {}, 2, True)


def test_manifest_rejects_tampered_or_unexpected_artifacts(tmp_path: Path) -> None:
    data = tmp_path / "result.json"
    data.write_text("{}")
    manifest = tmp_path / "manifest.json"
    write_quality_json(
        manifest,
        {
            "schema_version": 1,
            "source_unchanged": True,
            "artifacts": {"result.json": quality_file_sha256(data)},
        },
    )
    assert verify_quality_manifest(manifest)["status"] == "ok"
    data.write_text("tampered")
    with pytest.raises(ValueError, match="integrity"):
        verify_quality_manifest(manifest)
    data.write_text("{}")
    (tmp_path / "unexpected.json").write_text("{}")
    with pytest.raises(ValueError, match="unexpected"):
        verify_quality_manifest(manifest)


def test_receipt_destination_survives_test_environment_changes(tmp_path: Path) -> None:
    source = tmp_path / "test_environment.py"
    source.write_text(
        "def test_environment(monkeypatch):\n"
        "    monkeypatch.delenv('QRL_LOCAL_RECEIPTS')\n"
        "    assert True\n"
    )
    receipts = tmp_path / "receipts.jsonl"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "tools.quality.local_checks.pytest_receipts",
            "--rootdir",
            str(tmp_path),
            "-q",
            str(source),
        ],
        env={
            **{key: value for key, value in os.environ.items() if not key.startswith("QRL_LOCAL_")},
            "QRL_LOCAL_RECEIPTS": str(receipts),
        },
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    outcomes = validate_test_receipts(receipts, {"test_environment.py::test_environment"})
    assert outcomes["test_environment.py::test_environment"]["status"] == "passed"
