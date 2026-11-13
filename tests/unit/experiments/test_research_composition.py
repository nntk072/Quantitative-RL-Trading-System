"""Regression tests for research component identity and reusable result storage."""

from __future__ import annotations

import csv
import json
from dataclasses import replace
from pathlib import Path

import pytest

from artifacts.identity import file_sha256
from experiments.research.catalog import load_research_catalog
from experiments.research.command_group import build_command_group_bundle
from experiments.research.execution import (
    CommandBundle,
    CommandSpec,
    bundle_from_payload,
    bundle_payload,
)
from experiments.research.reporting import (
    ResultRow,
    consolidate_results,
    rows_from_execution_manifest,
)
from experiments.research.reporting_tables import build_research_tables


def test_catalog_groups_reusable_components_without_new_experiments() -> None:
    catalog = load_research_catalog()
    experiment = catalog.experiment("feature_inputs")
    components = {item.variant_id: item.component for item in experiment.variants}

    assert components == {
        "observation_validity": "observations",
        "opportunity_census": "opportunities",
        "candidate_geometry_support": "candidate_support",
    }
    assert catalog.experiment("survival_policy").variant("setup_conditioned").component == "policy"


def test_command_bundle_preserves_explicit_component_identity() -> None:
    command = CommandSpec(
        command_id="opportunity_census",
        argv=("python", "-m", "example"),
        variant_id="opportunity_census",
        component="opportunities",
    )
    bundle = CommandBundle(
        source_commit="a" * 40,
        experiment_id="feature_inputs",
        domain="features",
        commands=(command,),
    )

    assert bundle_from_payload(bundle_payload(bundle)) == bundle


def test_selected_component_cannot_discard_its_dependencies() -> None:
    experiment = load_research_catalog().experiment("feature_inputs")
    variants = tuple(
        replace(
            item,
            depends_on=("observation_validity",) if item.variant_id == "opportunity_census" else (),
        )
        for item in experiment.variants
    )
    experiment = replace(experiment, variants=variants)

    with pytest.raises(ValueError, match="requires variants"):
        build_command_group_bundle(
            experiment,
            source_commit="a" * 40,
            output_root="outputs/research",
            selected_variants=("opportunity_census",),
        )


def test_results_retain_command_and_source_identity(tmp_path: Path) -> None:
    artifact = tmp_path / "summary.json"
    artifact.write_text(
        json.dumps({"status": "passed", "metrics": {"eligible_events": 12}}),
        encoding="utf-8",
    )
    manifest = tmp_path / "execution_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source_commit": "a" * 40,
                "domain": "features",
                "experiment_id": "feature_inputs",
                "commands": [
                    {
                        "command_id": "opportunity_census",
                        "variant_id": "opportunity_census",
                        "component": "opportunities",
                        "status": "passed",
                        "artifact_sha256": {str(artifact): file_sha256(artifact)},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    rows = rows_from_execution_manifest(manifest)
    assert len(rows) == 1
    assert rows[0].component == "opportunities"
    assert rows[0].command_id == "opportunity_census"
    assert rows[0].source_commit == "a" * 40
    assert rows[0].metrics["eligible_events"] == 12

    output = tmp_path / "results"
    payload = consolidate_results((*rows, *rows), output)
    assert len(payload["results"]) == 1
    with (output / "results.csv").open(encoding="utf-8", newline="") as stream:
        csv_rows = list(csv.DictReader(stream))
    assert csv_rows[0]["component"] == "opportunities"
    assert csv_rows[0]["source_commit"] == "a" * 40

    table = build_research_tables(output / "results.json", output / "tables")
    assert table["row_count"] == 1
    with (output / "tables" / "research_result_inventory.csv").open(
        encoding="utf-8", newline=""
    ) as stream:
        summary = list(csv.DictReader(stream))
    assert summary[0]["component"] == "opportunities"
    assert summary[0]["passed"] == "1"


def test_consolidation_rejects_conflicting_records(tmp_path: Path) -> None:
    record = ResultRow(
        domain="data",
        experiment="data_integrity",
        variant="denominator_register",
        component="data",
        command_id="denominator_register",
        seed=None,
        source_commit="a" * 40,
        status="passed",
        artifact=str(tmp_path / "data.json"),
        metrics={"rows": 3},
    )
    with pytest.raises(ValueError, match="conflicting results"):
        consolidate_results((record, replace(record, status="failed")), tmp_path / "out")
