from __future__ import annotations

import json
import tomllib
from collections import Counter
from pathlib import Path

import pytest
import yaml
from research_tools.studies.study_catalog import (
    StudyCatalogError,
    _module_import_inventories,
    _read_yaml,
    _validate_evidence_index,
    build_study_plan,
    validate_study_catalog,
)
from research_tools.studies.study_cli import main

ROOT = Path(__file__).resolve().parents[3]


def test_import_inventory_resolves_package_before_shadowed_module(tmp_path: Path) -> None:
    (tmp_path / "features/candidate").mkdir(parents=True)
    (tmp_path / "simulation").mkdir()
    (tmp_path / "features/candidate.py").write_text("value = 'module'\n", encoding="utf-8")
    (tmp_path / "features/candidate/__init__.py").write_text(
        "value = 'package'\n", encoding="utf-8"
    )
    (tmp_path / "simulation/caller.py").write_text(
        "from features.candidate import value\n", encoding="utf-8"
    )
    profiles = {
        "features": {"source_roots": ["features"]},
        "simulation": {"source_roots": ["simulation"]},
    }

    inventories = _module_import_inventories(
        tmp_path,
        profiles,
        ["features", "simulation"],
    )

    assert inventories["features"] == (
        ["features/candidate/__init__.py"],
        ["simulation/caller.py"],
    )


def test_repository_study_catalog_covers_owned_modules_and_configures_only_registered_studies() -> (
    None
):
    plan = build_study_plan(ROOT)

    assert len(plan["modules"]) >= 16
    assert all(module["source_roots"] for module in plan["modules"])
    assert all(module["source_file_count"] > 0 for module in plan["modules"])
    assert all(module["uncovered_source_files"] == [] for module in plan["modules"])
    assert all(module["studies"] for module in plan["modules"])
    assert all(module["api_paths"] for module in plan["modules"])
    assert all(module["caller_paths"] for module in plan["modules"])
    assert all(
        path.is_file()
        for module in plan["modules"]
        for path in (ROOT / value for value in module["api_paths"] + module["caller_paths"])
    )
    assert len(plan["catalog_study_ids"]) == 92
    assert Counter(study["type"] for module in plan["modules"] for study in module["studies"]) == {
        "code_check": 79,
        "audit": 8,
        "empirical": 5,
    }
    assert all(study["id"] for module in plan["modules"] for study in module["studies"])
    assert all(
        study["acceptance_rule"] for module in plan["modules"] for study in module["studies"]
    )
    assert all(
        len(study["effective_config_sha256"]) == 64
        for module in plan["modules"]
        for study in module["studies"]
    )
    assert all(
        set(study["source_sha256"]) == set(study["source_paths"])
        and all(len(digest) == 64 for digest in study["source_sha256"].values())
        and all(len(digest) == 64 for digest in study["migration_target_sha256"].values())
        and len(study["effective_inputs_sha256"]) == 64
        for module in plan["modules"]
        for study in module["studies"]
    )
    migrations = plan["script_migrations"]
    assert migrations["count"] == 162
    assert migrations["completed_count"] == migrations["count"]
    assert all(
        len(digest) == 64
        for module in plan["modules"]
        for digest in module["research_tool_targets_sha256"].values()
    )
    experiment_configs = next(item for item in plan["modules"] if item["id"] == "experiments")[
        "config_paths"
    ]
    assert "config/research/prospective_research_protocol.yaml" in experiment_configs
    assert "config/variants/ladder_a0_flat.yaml" in experiment_configs
    assert all(
        "arms" not in study or isinstance(study["arms"], list)
        for module in plan["modules"]
        for study in module["studies"]
    )


def test_repository_inventory_lists_source_symbols_config_keys_tests_and_evidence() -> None:
    plan = build_study_plan(ROOT, include_inventory=True)
    inventory = plan["inventory"]
    source_files = [unit for module in inventory["source"]["modules"] for unit in module["files"]]
    config_files = {item["path"]: item for item in inventory["config"]["files"]}
    evidence_paths = {item["path"] for item in inventory["evidence"]["files"]}

    assert inventory["source"]["file_count"] == sum(
        module["source_file_count"] for module in plan["modules"]
    )
    assert inventory["source"]["symbol_count"] > inventory["source"]["file_count"]
    assert all(unit["study_ids"] for unit in source_files)
    assert "config/base/default.yaml" in config_files
    runtime_settings = config_files["config/base/default.yaml"]
    assert runtime_settings["keys"]
    assert all("value" not in key for key in runtime_settings["keys"])
    assert "docs/research/validation_protocol.md" in evidence_paths
    assert "evidence/research/data_identity/raw_data_manifest.json" in evidence_paths
    assert inventory["evidence"]["file_count"] == 26
    assert inventory["tests"]["file_count"] > 0


def test_study_yaml_loader_rejects_duplicate_keys(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.yaml"
    path.write_text("schema_version: 1\nschema_version: 2\n", encoding="utf-8")

    with pytest.raises(StudyCatalogError, match="duplicate key"):
        _read_yaml(path)


def test_evidence_index_rejects_unregistered_artifact_paths(tmp_path: Path) -> None:
    root = tmp_path
    evidence_dir = root / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "new_report.json").write_text("{}\n", encoding="utf-8")
    index = root / "index.yaml"
    index.write_text("schema_version: 1\nroots: [evidence]\nitems: []\n", encoding="utf-8")

    with pytest.raises(StudyCatalogError, match="unregistered"):
        _validate_evidence_index(root, "index.yaml", {"sample.study"})


def test_empirical_questions_stay_separate_from_diagnostic_audits() -> None:
    plan = build_study_plan(ROOT)
    studies = {study["id"]: study for module in plan["modules"] for study in module["studies"]}
    expected = {
        "evaluation.candidate_geometry_value",
        "training.full_path_survival_qualification",
        "evaluation.primary_value_vs_no_trade",
        "evaluation.secondary_matched_comparisons",
        "trading.frozen_finalist_robustness",
    }

    assert {study_id for study_id, study in studies.items() if study["type"] == "empirical"} == (
        expected
    )
    assert {
        "market_data.raw_data_quality_and_coverage",
        "features.prefix_causality_and_fit_scope",
        "features.candidate_geometry_and_proposal_preflight",
        "simulation.tick_execution_accounting_parity",
    } <= {study_id for study_id, study in studies.items() if study["type"] == "audit"}
    for study_id in expected:
        study = studies[study_id]
        assert study["acceptance"].strip()
        assert study["arms"]
        assert all(
            arm["config_paths"] and arm["factors"] and len(arm["config_sha256"]) == 64
            for arm in study["arms"]
        )


def test_script_migration_manifest_covers_every_research_module_and_script() -> None:
    manifest_path = ROOT / "config/studies/script_migrations.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    expected = {
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "scripts/research").rglob("*")
        if path.is_file() and path.suffix in {".py", ".sh"} and path.name != "__init__.py"
    }
    rows = manifest["scripts"]
    registered = [row["path"] for row in rows]

    assert manifest["schema_version"] == 1
    assert len(rows) == 162
    assert len(registered) == len(set(registered))
    assert set(registered) == expected
    assert all(row["owner_module"] and row["target"] and row["tests"] for row in rows)
    assert validate_study_catalog(ROOT)


def test_research_scripts_are_thin_compatibility_wrappers_for_package_modules() -> None:
    manifest = yaml.safe_load(
        (ROOT / "config/studies/script_migrations.yaml").read_text(encoding="utf-8")
    )

    assert all(row["migration_state"] == "complete" for row in manifest["scripts"])
    for row in manifest["scripts"]:
        legacy = ROOT / row["path"]
        if row["entrypoint"] == "shell":
            target = ROOT / row["target"]
            assert target.is_file()
            assert legacy.stat().st_size < 512
            assert "exec" in legacy.read_text(encoding="utf-8")
            continue
        target = ROOT.joinpath(*row["target"].split(".")).with_suffix(".py")
        wrapper = legacy.read_text(encoding="utf-8")
        assert target.is_file()
        assert len(wrapper) < 2_000
        assert row["target"] in wrapper
        assert "_import_module" in wrapper and "__getattr__" in wrapper


def test_catalog_rejects_research_script_missing_from_migration_manifest(tmp_path: Path) -> None:
    profile_dir = tmp_path / "config/studies/profiles"
    profile_dir.mkdir(parents=True)
    (tmp_path / "source").mkdir()
    (tmp_path / "source/module.py").write_text("value = 1\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_contract.py").write_text(
        "def test_contract(): pass\n", encoding="utf-8"
    )
    (tmp_path / "scripts/research").mkdir(parents=True)
    (tmp_path / "scripts/research/audit.py").write_text("def main(): pass\n", encoding="utf-8")
    (profile_dir / "sample.yaml").write_text(
        """module_id: sample
source_roots: [source]
source_scopes: [{path: source, study_ids: [sample.contract]}]
config_paths: []
test_paths: [tests]
studies:
  - id: sample.contract
    type: code_check
    question: Does the contract hold?
    source_paths: [source/module.py]
    checks: [tests/test_contract.py]
    outputs: [contract_check]
""",
        encoding="utf-8",
    )
    (tmp_path / "config/studies/script_migrations.yaml").write_text(
        "schema_version: 1\nscripts: []\n", encoding="utf-8"
    )
    (tmp_path / "config/studies/default.yaml").write_text(
        """schema_version: 1
profile_dir: profiles
script_migrations: config/studies/script_migrations.yaml
modules:
  sample: {enabled: true}
""",
        encoding="utf-8",
    )

    with pytest.raises(StudyCatalogError, match="script migration inventory mismatch"):
        validate_study_catalog(tmp_path)


def test_master_switch_disables_studies_but_keeps_profile_settings_visible(tmp_path: Path) -> None:
    (tmp_path / "config/studies/profiles").mkdir(parents=True)
    (tmp_path / "source").mkdir()
    (tmp_path / "source/module.py").write_text("value = 1\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "settings.yaml").write_text("value: 1\n", encoding="utf-8")
    (tmp_path / "tests/test_contract.py").write_text(
        "def test_contract(): pass\n", encoding="utf-8"
    )
    (tmp_path / "config/studies/profiles/sample.yaml").write_text(
        """module_id: sample
source_roots: [source]
source_scopes: [{path: source, study_ids: [sample.contract]}]
config_paths: [settings.yaml]
test_paths: [tests/test_contract.py]
studies:
  - id: sample.contract
    type: code_check
    question: Does the sample contract hold?
    source_paths: [source]
    checks: [tests/test_contract.py]
    outputs: [pass_or_fail]
""",
        encoding="utf-8",
    )
    master = {
        "schema_version": 1,
        "profile_dir": "profiles",
        "modules": {"sample": {"enabled": False}},
    }
    master_path = tmp_path / "config/studies/default.yaml"
    master_path.write_text(yaml.safe_dump(master), encoding="utf-8")

    plan = build_study_plan(tmp_path)

    assert plan["selected_studies"] == []
    assert plan["modules"][0]["enabled"] is False
    assert plan["modules"][0]["config_paths"] == ["settings.yaml"]
    assert plan["modules"][0]["studies"][0]["enabled"] is False


def test_workflow_section_switches_modules_and_hashes_runtime_config(tmp_path: Path) -> None:
    profile_dir = tmp_path / "config/studies/profiles"
    profile_dir.mkdir(parents=True)
    (tmp_path / "source").mkdir()
    (tmp_path / "source/module.py").write_text("value = 1\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "settings.yaml").write_text("value: 1\n", encoding="utf-8")
    (tmp_path / "tests/test_contract.py").write_text(
        "def test_contract(): pass\n", encoding="utf-8"
    )
    (profile_dir / "sample.yaml").write_text(
        """module_id: sample
source_roots: [source]
source_scopes: [{path: source, study_ids: [sample.contract]}]
config_paths: [settings.yaml]
test_paths: [tests/test_contract.py]
studies:
  - id: sample.contract
    type: code_check
    question: Does the sample contract hold?
    source_paths: [source]
    checks: [tests/test_contract.py]
    outputs: [pass_or_fail]
""",
        encoding="utf-8",
    )
    master = {
        "schema_version": 1,
        "profile_dir": "profiles",
        "runtime": {"config": "settings.yaml"},
        "workflow": {"testing": {"enabled": False, "modules": ["sample"]}},
        "modules": {"sample": {"enabled": True}},
    }
    master_path = tmp_path / "config/studies/default.yaml"
    master_path.write_text(yaml.safe_dump(master), encoding="utf-8")

    plan = build_study_plan(tmp_path)

    assert plan["runtime_config"] == "settings.yaml"
    assert len(plan["runtime_config_sha256"]) == 64
    assert plan["modules"][0]["workflow_section"] == "testing"
    assert plan["modules"][0]["enabled"] is False
    assert plan["selected_studies"] == []


def test_catalog_rejects_missing_referenced_test_path(tmp_path: Path) -> None:
    (tmp_path / "config/studies/profiles").mkdir(parents=True)
    (tmp_path / "source").mkdir()
    (tmp_path / "source/module.py").write_text("value = 1\n", encoding="utf-8")
    (tmp_path / "config/studies/profiles/sample.yaml").write_text(
        """module_id: sample
source_roots: [source]
source_scopes: [{path: source, study_ids: [sample.contract]}]
config_paths: []
test_paths: [tests/missing.py]
studies: []
""",
        encoding="utf-8",
    )
    (tmp_path / "config/studies/default.yaml").write_text(
        "schema_version: 1\nprofile_dir: profiles\nmodules:\n  sample:\n    enabled: true\n",
        encoding="utf-8",
    )

    with pytest.raises(StudyCatalogError, match="tests/missing.py"):
        validate_study_catalog(tmp_path)


def test_cli_validate_and_plan_never_execute_studies(capsys: pytest.CaptureFixture[str]) -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert project["project"]["scripts"]["qrl-study"] == "research_tools.studies.study_cli:main"

    assert main(["validate", "--root", str(ROOT)]) == 0
    assert "validated" in capsys.readouterr().out

    assert main(["list", "--root", str(ROOT)]) == 0
    assert "features.causal_availability" in capsys.readouterr().out

    assert main(["plan", "--root", str(ROOT)]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["execution"] == "not_started"
    assert plan["selected_studies"]


def test_cli_inventory_can_select_a_module(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["inventory", "--module", "features", "--root", str(ROOT)]) == 0
    inventory = json.loads(capsys.readouterr().out)

    assert inventory["source"]["modules"][0]["id"] == "features"
    assert inventory["source"]["file_count"] == len(inventory["source"]["modules"][0]["files"])
    assert all(
        "features." in study
        for item in inventory["evidence"]["files"]
        for study in item["study_ids"]
    )


def test_cli_check_dry_run_plans_non_empirical_checks_without_running_them(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["check", "--dry-run", "--root", str(ROOT)]) == 0
    result = json.loads(capsys.readouterr().out)

    assert result["execution"] == "dry_run"
    assert result["steps"]
    assert all(step["type"] != "empirical" for step in result["steps"])
    assert all(step["status"] == "planned" for step in result["steps"])
    assert result["empirical_studies_not_run"]


def test_cli_check_can_select_one_module_without_expanding_to_other_modules(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["check", "--module", "features", "--dry-run", "--root", str(ROOT)]) == 0
    result = json.loads(capsys.readouterr().out)

    assert result["selected_studies"]
    assert all(study_id.startswith("features.") for study_id in result["selected_studies"])
    assert all(step["module_id"] == "features" for step in result["steps"])


def test_catalog_rejects_unknown_study_toggle(tmp_path: Path) -> None:
    (tmp_path / "config/studies/profiles").mkdir(parents=True)
    (tmp_path / "source").mkdir()
    (tmp_path / "source/module.py").write_text("value = 1\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_contract.py").write_text(
        "def test_contract(): pass\n", encoding="utf-8"
    )
    (tmp_path / "config/studies/profiles/sample.yaml").write_text(
        """module_id: sample
source_roots: [source]
source_scopes: [{path: source, study_ids: [sample.contract]}]
config_paths: []
test_paths: []
studies:
  - id: sample.contract
    type: code_check
    question: Does the sample contract hold?
    source_paths: [source]
    checks: [tests/test_contract.py]
    outputs: [pass_or_fail]
""",
        encoding="utf-8",
    )
    (tmp_path / "config/studies/default.yaml").write_text(
        """schema_version: 1
profile_dir: profiles
modules:
  sample:
    enabled: true
    studies:
      sample.not_registered: true
""",
        encoding="utf-8",
    )

    with pytest.raises(StudyCatalogError, match="sample.not_registered"):
        build_study_plan(tmp_path)


def test_empirical_study_requires_explicit_arms_and_factors(tmp_path: Path) -> None:
    (tmp_path / "config/studies/profiles").mkdir(parents=True)
    (tmp_path / "source").mkdir()
    (tmp_path / "source/module.py").write_text("value = 1\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_contract.py").write_text(
        "def test_contract(): pass\n", encoding="utf-8"
    )
    (tmp_path / "config/studies/profiles/sample.yaml").write_text(
        """module_id: sample
source_roots: [source]
source_scopes: [{path: source, study_ids: [sample.empirical]}]
config_paths: []
test_paths: [tests]
studies:
  - id: sample.empirical
    type: empirical
    question: Which registered arm answers the question?
    acceptance: All registered arms meet the frozen outcome rule.
    source_paths: [source]
    checks: [tests/test_contract.py]
    outputs: [result]
""",
        encoding="utf-8",
    )
    (tmp_path / "config/studies/default.yaml").write_text(
        "schema_version: 1\nprofile_dir: profiles\nmodules:\n  sample:\n    enabled: true\n",
        encoding="utf-8",
    )

    with pytest.raises(StudyCatalogError, match="explicit registered arms"):
        validate_study_catalog(tmp_path)


def test_plan_preserves_only_explicit_empirical_arms(tmp_path: Path) -> None:
    profile_dir = tmp_path / "config/studies/profiles"
    profile_dir.mkdir(parents=True)
    (tmp_path / "source").mkdir()
    (tmp_path / "source/module.py").write_text("value = 1\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_contract.py").write_text(
        "def test_contract(): pass\n", encoding="utf-8"
    )
    for arm in ("control", "treatment"):
        (tmp_path / f"{arm}.yaml").write_text(f"arm: {arm}\n", encoding="utf-8")
    (profile_dir / "sample.yaml").write_text(
        """module_id: sample
source_roots: [source]
source_scopes: [{path: source, study_ids: [sample.comparison]}]
config_paths: []
test_paths: [tests]
studies:
  - id: sample.comparison
    type: empirical
    question: Does the treatment factor change the registered result?
    acceptance: The paired result is reported for both declared arms.
    source_paths: [source/module.py]
    checks: [tests/test_contract.py]
    outputs: [paired_result]
    arms:
      - id: control
        config_paths: [control.yaml]
        factors: [baseline]
      - id: treatment
        config_paths: [treatment.yaml]
        factors: [treatment_feature]
""",
        encoding="utf-8",
    )
    (tmp_path / "config/studies/default.yaml").write_text(
        "schema_version: 1\nprofile_dir: profiles\nmodules:\n  sample:\n    enabled: true\n",
        encoding="utf-8",
    )

    plan = build_study_plan(tmp_path)

    arms = plan["selected_studies"][0]["arms"]
    assert [arm["id"] for arm in arms] == ["control", "treatment"]
    assert [arm["factors"] for arm in arms] == [["baseline"], ["treatment_feature"]]
    resolved_configs = plan["selected_studies"][0]["resolved_config_paths"]
    assert "control.yaml" in resolved_configs
    assert "treatment.yaml" in resolved_configs
    before = plan["selected_studies"][0]["effective_config_sha256"]
    source_before = plan["selected_studies"][0]["source_sha256"]["source/module.py"]
    arm_hashes_before = {
        arm["id"]: arm["config_sha256"] for arm in plan["selected_studies"][0]["arms"]
    }
    (tmp_path / "treatment.yaml").write_text("arm: changed\n", encoding="utf-8")
    updated = build_study_plan(tmp_path)["selected_studies"][0]
    after = updated["effective_config_sha256"]
    assert before != after
    arm_hashes_after = {arm["id"]: arm["config_sha256"] for arm in updated["arms"]}
    assert arm_hashes_before["control"] == arm_hashes_after["control"]
    assert arm_hashes_before["treatment"] != arm_hashes_after["treatment"]
    (tmp_path / "source/module.py").write_text("value = 2\n", encoding="utf-8")
    source_updated = build_study_plan(tmp_path)["selected_studies"][0]
    assert source_updated["source_sha256"]["source/module.py"] != source_before
    assert source_updated["effective_inputs_sha256"] != updated["effective_inputs_sha256"]


def test_catalog_rejects_unregistered_study_prerequisite(tmp_path: Path) -> None:
    profile_dir = tmp_path / "config/studies/profiles"
    profile_dir.mkdir(parents=True)
    source = tmp_path / "source"
    source.mkdir()
    (source / "module.py").write_text("value = 1\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_contract.py").write_text(
        "def test_contract(): pass\n", encoding="utf-8"
    )
    (profile_dir / "sample.yaml").write_text(
        """module_id: sample
source_roots: [source]
source_scopes: [{path: source, study_ids: [sample.contract]}]
config_paths: []
test_paths: [tests]
studies:
  - id: sample.contract
    type: code_check
    question: Does the sample contract hold?
    source_paths: [source/module.py]
    checks: [tests/test_contract.py]
    outputs: [pass_or_fail]
    prerequisites: [sample.not_registered]
""",
        encoding="utf-8",
    )
    (tmp_path / "config/studies/default.yaml").write_text(
        "schema_version: 1\nprofile_dir: profiles\nmodules:\n  sample:\n    enabled: true\n",
        encoding="utf-8",
    )

    with pytest.raises(StudyCatalogError, match="unregistered prerequisites"):
        validate_study_catalog(tmp_path)


def test_catalog_rejects_unmapped_source_modules(tmp_path: Path) -> None:
    (tmp_path / "config/studies/profiles").mkdir(parents=True)
    (tmp_path / "source").mkdir()
    (tmp_path / "source/module.py").write_text("value = 1\n", encoding="utf-8")
    (tmp_path / "source/other.py").write_text("value = 2\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_contract.py").write_text(
        "def test_contract(): pass\n", encoding="utf-8"
    )
    (tmp_path / "config/studies/profiles/sample.yaml").write_text(
        """module_id: sample
source_roots: [source]
source_scopes: [{path: source/other.py, study_ids: [sample.contract]}]
config_paths: []
test_paths: [tests]
studies:
  - id: sample.contract
    type: code_check
    question: Does the sample contract hold?
    source_paths: [source/module.py]
    checks: [tests/test_contract.py]
    outputs: [pass_or_fail]
""",
        encoding="utf-8",
    )
    (tmp_path / "config/studies/default.yaml").write_text(
        "schema_version: 1\nprofile_dir: profiles\nmodules:\n  sample:\n    enabled: true\n",
        encoding="utf-8",
    )

    with pytest.raises(StudyCatalogError, match="uncovered source files"):
        validate_study_catalog(tmp_path)


def test_catalog_rejects_unassigned_runtime_config_yaml(tmp_path: Path) -> None:
    (tmp_path / "config/studies/profiles").mkdir(parents=True)
    (tmp_path / "config/base").mkdir()
    (tmp_path / "config/base/default.yaml").write_text("value: 1\n", encoding="utf-8")
    (tmp_path / "source").mkdir()
    (tmp_path / "source/module.py").write_text("value = 1\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_contract.py").write_text(
        "def test_contract(): pass\n", encoding="utf-8"
    )
    (tmp_path / "config/studies/profiles/sample.yaml").write_text(
        """module_id: sample
source_roots: [source]
source_scopes: [{path: source, study_ids: [sample.contract]}]
config_paths: []
test_paths: [tests]
studies:
  - id: sample.contract
    type: code_check
    question: Does the sample contract hold?
    source_paths: [source]
    checks: [tests/test_contract.py]
    outputs: [pass_or_fail]
""",
        encoding="utf-8",
    )
    (tmp_path / "config/studies/default.yaml").write_text(
        "schema_version: 1\nprofile_dir: profiles\nmodules:\n  sample:\n    enabled: true\n",
        encoding="utf-8",
    )

    with pytest.raises(StudyCatalogError, match="config/base/default.yaml"):
        validate_study_catalog(tmp_path)
