from __future__ import annotations

from pathlib import Path

import yaml
from research_tools.studies.handlers.repository import audit_script_migrations


def test_script_migration_audit_checks_all_legacy_wrappers_without_mutation() -> None:
    root = Path(__file__).resolve().parents[3]

    report = audit_script_migrations(
        root, {}, root / "logs/agents/ci_operation_engineer/20261117_test"
    )

    assert report["diagnostic_status"] == "passed"
    assert report["manifest_count"] == 158
    assert report["completed_count"] == 158
    assert report["errors"] == []
    assert report["unregistered_sources"] == []
    assert report["stale_manifest_sources"] == []
    assert report["legacy_package_imports"] == []


def test_script_migration_audit_checks_repo_tooling_package_imports(tmp_path: Path) -> None:
    legacy = tmp_path / "scripts/research/inspect.py"
    legacy.parent.mkdir(parents=True)
    legacy.write_text(
        '"""Compatibility wrapper."""\n'
        '_TARGET = "tools.research_tools.inspect"\n'
        "_run_module(_TARGET)\n",
        encoding="utf-8",
    )
    package = tmp_path / "tools/research_tools/inspect.py"
    package.parent.mkdir(parents=True)
    package.write_text(
        "from scripts.research.other import inspect\n",
        encoding="utf-8",
    )
    manifest = tmp_path / "config/studies/script_migrations.yaml"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "scripts": [
                    {
                        "path": "scripts/research/inspect.py",
                        "owner_module": "repo_tooling",
                        "target": "tools.research_tools.inspect",
                        "entrypoint": "cli",
                        "migration_state": "complete",
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    report = audit_script_migrations(tmp_path, {}, tmp_path / "logs")

    assert report["diagnostic_status"] == "failed"
    assert report["legacy_package_imports"] == [
        {
            "path": "tools/research_tools/inspect.py",
            "line": 1,
            "module": "scripts.research.other",
        }
    ]
