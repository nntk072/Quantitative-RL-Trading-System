from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from tools.quality.research_script_migration import (
    MigrationPlanError,
    migrate_research_scripts,
    python_compatibility_wrapper,
    rebase_repository_root_expressions,
    rebase_research_module_imports,
    shell_compatibility_wrapper,
)


def test_migration_rebases_repository_root_parent_indexes() -> None:
    root = Path("/repo")
    legacy = root / "scripts/research/analysis/features/audit.py"
    target = root / "research_tools/features/features/audit.py"
    source = (
        "ROOT = Path(__file__).resolve().parents[4]\n"
        "SCRIPT = Path(__file__).resolve()\n"
        "ROOT_COPY = SCRIPT.parents[4]\n"
    )

    updated = rebase_repository_root_expressions(source, legacy, target, root)

    assert updated == (
        "ROOT = Path(__file__).resolve().parents[3]\n"
        "SCRIPT = Path(__file__).resolve()\n"
        "ROOT_COPY = SCRIPT.parents[3]\n"
    )


def test_migration_rejects_parent_indexes_that_do_not_name_repository_root() -> None:
    root = Path("/repo")
    legacy = root / "scripts/research/analysis/features/audit.py"
    target = root / "research_tools/features/features/audit.py"

    with pytest.raises(MigrationPlanError, match="does not resolve to repository root"):
        rebase_repository_root_expressions(
            "ROOT = Path(__file__).resolve().parents[2]\n", legacy, target, root
        )


def test_migration_rebases_imports_between_moved_research_modules() -> None:
    source = (
        "from scripts.research.group.helper import build\n"
        "import scripts.research.group.other as other\n"
        "EXAMPLE = 'from scripts.research.group.helper import build'\n"
    )

    updated = rebase_research_module_imports(
        source,
        {
            "scripts.research.group.helper": "research_tools.sample.group.helper",
            "scripts.research.group.other": "research_tools.sample.group.other",
        },
    )

    assert "from research_tools.sample.group.helper import build" in updated
    assert "import research_tools.sample.group.other as other" in updated
    assert "EXAMPLE = 'from scripts.research.group.helper import build'" in updated


def test_python_compatibility_wrapper_preserves_import_and_cli_entrypoints() -> None:
    wrapper = python_compatibility_wrapper(
        "research_tools.features.features.audit", repository_root_index=4
    )

    assert "research_tools.features.features.audit" in wrapper
    assert "_import_module" in wrapper
    assert "__getattr__" in wrapper
    assert "run_module" in wrapper
    assert "parents[4]" in wrapper


def test_shell_compatibility_wrapper_executes_the_package_owned_target() -> None:
    wrapper = shell_compatibility_wrapper("../../../../research_tools/training/probe.sh")

    assert wrapper.startswith("#!/usr/bin/env bash")
    assert "exec" in wrapper
    assert '"$@"' in wrapper


def test_migration_dry_run_then_move_preserves_body_and_updates_manifest(tmp_path: Path) -> None:
    legacy = tmp_path / "scripts/research/group/tool.py"
    legacy.parent.mkdir(parents=True)
    legacy.write_text(
        "from scripts.research.group.helper import utility\n\ndef run():\n    return utility()\n",
        encoding="utf-8",
    )
    legacy_helper = tmp_path / "scripts/research/group/helper.py"
    legacy_helper.write_text("def utility():\n    return 7\n", encoding="utf-8")
    manifest = tmp_path / "config/studies/script_migrations.yaml"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        """schema_version: 1
scripts:
  - path: scripts/research/group/tool.py
    owner_module: sample
    target: research_tools.sample.group.tool
    entrypoint: module
    tests: [tests/test_contract.py]
    migration_state: pending
  - path: scripts/research/group/helper.py
    owner_module: sample
    target: research_tools.sample.group.helper
    entrypoint: module
    tests: [tests/test_contract.py]
    migration_state: pending
""",
        encoding="utf-8",
    )

    preview = migrate_research_scripts(tmp_path, dry_run=True)
    assert preview["written"] is False
    assert "from scripts.research.group.helper" in legacy.read_text(encoding="utf-8")

    report = migrate_research_scripts(tmp_path)

    target = tmp_path / "research_tools/sample/group/tool.py"
    moved_tool = target.read_text(encoding="utf-8")
    assert report["written"] is True
    assert "from research_tools.sample.group.helper import utility" in moved_tool
    assert "return utility()" in moved_tool
    assert "research_tools.sample.group.tool" in legacy.read_text(encoding="utf-8")
    assert "return 7" in (tmp_path / "research_tools/sample/group/helper.py").read_text(
        encoding="utf-8"
    )
    states = [
        row["migration_state"]
        for row in yaml.safe_load(manifest.read_text(encoding="utf-8"))["scripts"]
    ]
    assert states == ["complete", "complete"]
