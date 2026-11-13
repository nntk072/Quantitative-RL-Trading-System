"""Reuse and provenance contracts for research configuration and metrics."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
import yaml

from artifacts.identity import file_sha256
from experiments.research.catalog import DEFAULT_CATALOG, load_research_catalog
from experiments.research.command_group import build_command_group_bundle
from experiments.research.execution import (
    CommandBundle,
    CommandSpec,
    bundle_from_payload,
    bundle_payload,
)
from experiments.research.reporting import consolidate_execution_manifests


def test_library_implementations_can_be_shared_across_studies(tmp_path: Path) -> None:
    config = yaml.safe_load(DEFAULT_CATALOG.read_text(encoding="utf-8"))
    config["experiments"]["research_contract"]["variants"]["observation_probe"] = {
        "use": "observations.observation_validity",
        "role": "prerequisite",
    }
    config["experiments"]["research_contract"]["assemblies"]["source_and_observations"] = [
        "static_contract",
        "observation_probe",
    ]
    path = tmp_path / "catalog.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    catalog = load_research_catalog(path)
    probe = catalog.experiment("research_contract").variant("observation_probe")
    original = catalog.experiment("feature_inputs").variant("observation_validity")
    assert probe.component == original.component == "observations"
    assert probe.command == original.command
    reused = build_command_group_bundle(
        catalog.experiment("research_contract"),
        source_commit="a" * 40,
        output_root="outputs/research",
    )
    existing = build_command_group_bundle(
        catalog.experiment("feature_inputs"),
        source_commit="a" * 40,
        output_root="outputs/research",
    )
    probe_output = next(
        command for command in reused.commands if command.variant_id == "observation_probe"
    )
    original_output = next(
        command for command in existing.commands if command.variant_id == "observation_validity"
    )
    assert probe_output.artifact_roots == ("outputs/research/research_contract/observation_probe",)
    assert original_output.artifact_roots == (
        "outputs/research/feature_inputs/observation_validity",
    )
    assert set(probe_output.artifact_roots).isdisjoint(original_output.artifact_roots)
    selected = catalog.experiment("research_contract").variants_for_assembly(
        "source_and_observations"
    )
    assert [item.variant_id for item in selected] == ["static_contract", "observation_probe"]


def test_assemblies_reject_ambiguous_component_combinations(tmp_path: Path) -> None:
    config = yaml.safe_load(DEFAULT_CATALOG.read_text(encoding="utf-8"))
    config["experiments"]["survival_policy"]["assemblies"]["conflicting"] = [
        "setup_conditioned",
        "hybrid_control",
    ]
    path = tmp_path / "catalog.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    with pytest.raises(ValueError, match="multiple variants"):
        load_research_catalog(path)


def test_explicit_seed_and_result_artifact_survive_consolidation(tmp_path: Path) -> None:
    result = tmp_path / "record.json"
    result.write_text(json.dumps({"metrics": {"quality": {"coverage": 0.95}}}), encoding="utf-8")
    digest = file_sha256(result)
    bundle = CommandBundle(
        source_commit="a" * 40,
        experiment_id="data_integrity",
        domain="data",
        commands=(
            CommandSpec(
                command_id="capture",
                argv=("python", "-m", "example"),
                variant_id="capture",
                component="data",
                seed=27,
                result_artifact=str(result),
                artifact_roots=(str(result),),
            ),
        ),
    )
    assert bundle_from_payload(bundle_payload(bundle)) == bundle
    manifest = tmp_path / "execution_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source_commit": "a" * 40,
                "experiment_id": "data_integrity",
                "domain": "data",
                "commands": [
                    {
                        "command_id": "capture",
                        "status": "passed",
                        "seed": 27,
                        "variant_id": "capture",
                        "component": "data",
                        "result_artifact": str(result),
                        "artifact_sha256": {str(result): digest},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "consolidated"
    payload = consolidate_execution_manifests([manifest], output)
    assert payload["results"][0]["seed"] == 27
    assert payload["results"][0]["artifact_sha256"] == digest
    with (output / "metrics.csv").open(encoding="utf-8", newline="") as stream:
        metrics = list(csv.DictReader(stream))
    assert len(metrics) == 1
    assert metrics[0]["metric"] == "quality.coverage"
    assert metrics[0]["value"] == "0.95"
    assert metrics[0]["seed"] == "27"


def test_unknown_component_implementation_is_rejected(tmp_path: Path) -> None:
    catalog = yaml.safe_load(DEFAULT_CATALOG.read_text(encoding="utf-8"))
    catalog["experiments"]["feature_inputs"]["variants"]["observation_validity"]["use"] = (
        "observations.missing"
    )
    path = tmp_path / "catalog.yaml"
    path.write_text(yaml.safe_dump(catalog), encoding="utf-8")
    with pytest.raises(ValueError, match="unknown component"):
        load_research_catalog(path)
