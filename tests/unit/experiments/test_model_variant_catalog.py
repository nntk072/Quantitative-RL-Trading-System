from __future__ import annotations

import runpy
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

from experiments.variants import catalog
from models.architecture_ids import ENCODER_ARCHITECTURE_IDS
from models.factory.encoder_registry import ENCODER_TYPES
from training.configuration.variant_resolution import ARCHS, PROJECT_ROOT, load_experiments


def _minimal_index(*, historical_source: str | None = None) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "variant": "current",
        "label": "A",
        "role": "control",
        "description": "Current control arm.",
        "changed_factors": [],
    }
    entries: list[dict[str, Any]] = [entry]
    if historical_source is not None:
        entries.append(
            {
                "variant": "retired",
                "label": "B",
                "role": "treatment",
                "description": "Preserved historical treatment.",
                "changed_factors": ["encoder"],
                "historical_sources": [historical_source],
            }
        )
    return {
        "schema_version": 1,
        "algorithms": {"ppo": {"title": "PPO", "description": "Policy optimizer."}},
        "architectures": [{"id": "tcn", "title": "TCN", "description": "Temporal encoder."}],
        "families": [
            {
                "id": "test_pair",
                "domain": "representation",
                "title": "Test comparison",
                "question": "Does the treatment change the result?",
                "comparison_type": "matched",
                "entries": entries,
            }
        ],
    }


def test_catalog_covers_each_selectable_variant_with_resolved_settings() -> None:
    resolved_catalog = catalog.build_catalog()
    expected = {str(row["name"]) for row in load_experiments()["variants"]}
    selectable = {
        entry["variant"]
        for family in resolved_catalog["families"]
        for entry in family["entries"]
        if entry["status"] == "Selectable"
    }

    assert selectable == expected
    assert expected
    mtf_treatment = next(
        entry
        for family in resolved_catalog["families"]
        for entry in family["entries"]
        if entry["variant"] == "rq_mtf_treatment_mtf" and family["id"] == "mtf_encoder"
    )
    assert mtf_treatment["resolved"]["algo"] == "ppo"
    assert mtf_treatment["resolved"]["arch"] == "mtf"
    assert mtf_treatment["resolved"]["reward_mode"] == "dsr"
    assert mtf_treatment["resolved"]["risk"]["risk_sizing_limit_usd"] == 900.0


def test_comparison_family_resolves_only_currently_configured_arms() -> None:
    family = catalog.resolve_family("mtf_encoder")

    assert [arm["variant"] for arm in family["entries"]] == [
        "rq_mtf_control_tcn",
        "rq_mtf_treatment_mtf",
    ]
    assert family["comparison_type"] == "matched"
    assert family["domain"] == "representation"


def test_comparison_family_rejects_unknown_id() -> None:
    with pytest.raises(catalog.CatalogError, match="unknown comparison family"):
        catalog.resolve_family("not_a_comparison")


def test_catalog_rejects_unknown_research_domain() -> None:
    metadata = _minimal_index()
    metadata["families"][0]["domain"] = "miscellaneous"

    with pytest.raises(catalog.CatalogError, match="unsupported domain"):
        catalog.validate_catalog_index(
            metadata,
            {"variants": [{"name": "current"}]},
            root=Path("."),
            architecture_ids=("tcn",),
            algorithms=("ppo",),
        )


def test_encoder_ids_match_config_resolution_and_factory() -> None:
    assert ARCHS == ENCODER_ARCHITECTURE_IDS
    assert set(ENCODER_TYPES) == set(ENCODER_ARCHITECTURE_IDS)


def test_variant_resolution_does_not_import_torch() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import training.configuration.variant_resolution; "
            "assert 'torch' not in sys.modules",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_catalog_rejects_duplicate_labels_within_a_family() -> None:
    metadata = _minimal_index()
    family = metadata["families"][0]
    family["entries"].append(
        {
            "variant": "current",
            "label": "A",
            "role": "treatment",
            "description": "Duplicate arm label.",
            "changed_factors": ["encoder"],
        }
    )

    with pytest.raises(catalog.CatalogError, match="duplicate arm label"):
        catalog.validate_catalog_index(
            metadata,
            {"variants": [{"name": "current"}]},
            root=Path("."),
            architecture_ids=("tcn",),
            algorithms=("ppo",),
        )


def test_catalog_index_rejects_malformed_metadata_at_each_boundary(tmp_path: Path) -> None:
    unset = object()

    def invalid_case(
        *,
        metadata: dict[str, Any] | None = None,
        variants: object = unset,
        message: str,
    ) -> tuple[dict[str, Any], dict[str, Any], str]:
        catalog_metadata = _minimal_index() if metadata is None else metadata
        experiment_rows = [{"name": "current"}] if variants is unset else variants
        return catalog_metadata, {"variants": experiment_rows}, message

    cases: list[tuple[dict[str, Any], dict[str, Any], str]] = []
    metadata = _minimal_index()
    metadata["schema_version"] = 2
    cases.append(invalid_case(metadata=metadata, message="schema_version"))
    cases.append(invalid_case(variants=None, message="variants list"))
    cases.append(invalid_case(variants=[None], message="variant must be a mapping"))
    cases.append(invalid_case(variants=[{"name": " "}], message="non-empty string"))
    cases.append(
        invalid_case(
            variants=[{"name": "current"}, {"name": "current"}], message="declared more than once"
        )
    )

    metadata = _minimal_index()
    metadata["algorithms"] = {"other": {"title": "Other", "description": "Other."}}
    cases.append(invalid_case(metadata=metadata, message="supported algorithm IDs"))
    metadata = _minimal_index()
    metadata["algorithms"]["ppo"] = None
    cases.append(invalid_case(metadata=metadata, message="algorithm metadata must be a mapping"))
    metadata = _minimal_index()
    metadata["architectures"] = None
    cases.append(invalid_case(metadata=metadata, message="architectures must be a list"))
    metadata = _minimal_index()
    metadata["architectures"] = [None]
    cases.append(invalid_case(metadata=metadata, message="architecture metadata entry"))
    metadata = _minimal_index()
    metadata["architectures"].append(dict(metadata["architectures"][0]))
    cases.append(invalid_case(metadata=metadata, message="architecture IDs must be unique"))
    metadata = _minimal_index()
    metadata["architectures"][0]["id"] = "other"
    cases.append(invalid_case(metadata=metadata, message="lightweight encoder registry"))
    metadata = _minimal_index()
    metadata["families"] = []
    cases.append(invalid_case(metadata=metadata, message="at least one research family"))
    metadata = _minimal_index()
    metadata["families"] = [None]
    cases.append(invalid_case(metadata=metadata, message="family must be a mapping"))
    metadata = _minimal_index()
    metadata["families"][0]["comparison_type"] = "descriptive"
    metadata["families"].append(dict(metadata["families"][0]))
    cases.append(invalid_case(metadata=metadata, message="duplicate family ID"))
    metadata = _minimal_index()
    metadata["families"][0]["entries"][0]["role"] = "observer"
    cases.append(invalid_case(metadata=metadata, message="invalid role"))
    metadata = _minimal_index()
    metadata["families"][0]["entries"][0]["changed_factors"] = None
    cases.append(invalid_case(metadata=metadata, message="changed_factors"))
    metadata = _minimal_index()
    metadata["families"][0]["entries"][0]["historical_sources"] = "bad-path"
    cases.append(invalid_case(metadata=metadata, message="historical_sources"))
    metadata = _minimal_index()
    metadata["families"][0]["entries"] = []
    cases.append(invalid_case(metadata=metadata, message="must contain entries"))
    metadata = _minimal_index()
    metadata["families"][0]["entries"] = [None]
    cases.append(invalid_case(metadata=metadata, message="every entry"))
    metadata = _minimal_index()
    metadata["families"][0]["comparison_type"] = "unregistered"
    cases.append(invalid_case(metadata=metadata, message="unsupported comparison type"))

    for metadata, experiments, message in cases:
        with pytest.raises(catalog.CatalogError, match=message):
            catalog.validate_catalog_index(
                metadata,
                experiments,
                root=tmp_path,
                architecture_ids=("tcn",),
                algorithms=("ppo",),
            )


def test_catalog_reports_selectable_variants_missing_from_a_valid_historical_family(
    tmp_path: Path,
) -> None:
    source = tmp_path / "frozen.yaml"
    source.write_text("experiment_run_id: frozen\n", encoding="utf-8")
    metadata = _minimal_index(historical_source="frozen.yaml")
    metadata["families"][0]["comparison_type"] = "descriptive"
    metadata["families"][0]["entries"] = metadata["families"][0]["entries"][1:]

    with pytest.raises(catalog.CatalogError, match="selectable variants missing"):
        catalog.validate_catalog_index(
            metadata,
            {"variants": [{"name": "current"}]},
            root=tmp_path,
            architecture_ids=("tcn",),
            algorithms=("ppo",),
        )


def test_catalog_builder_reports_unreadable_and_non_mapping_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "catalog.yaml"
    monkeypatch.setattr(catalog, "CATALOG_PATH", path)

    with pytest.raises(catalog.CatalogError, match="cannot read catalog metadata"):
        catalog.build_catalog()
    path.write_text("- not-a-mapping\n", encoding="utf-8")
    with pytest.raises(catalog.CatalogError, match="metadata must be a mapping"):
        catalog.build_catalog()
    with pytest.raises(catalog.CatalogError, match="metadata must be a mapping"):
        catalog.resolve_family("test_pair")


def test_catalog_module_entrypoint_runs_check_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    expected_page = catalog.render_catalog(catalog.build_catalog())
    read_text = Path.read_text

    def read_catalog_page(path: Path, *args: Any, **kwargs: Any) -> str:
        if path == catalog.CATALOG_PAGE_PATH:
            return expected_page
        return read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_catalog_page)
    monkeypatch.setattr(sys, "argv", ["catalog.py", "--check"])

    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path(str(Path(catalog.__file__)), run_name="__main__")

    assert exit_info.value.code == 0


def test_historical_variant_requires_an_existing_frozen_source(tmp_path: Path) -> None:
    frozen_record = tmp_path / "config" / "experiment_runs" / "frozen.yaml"
    frozen_record.parent.mkdir(parents=True)
    frozen_record.write_text("variants: [retired]\n", encoding="utf-8")
    metadata = _minimal_index(historical_source="config/experiment_runs/frozen.yaml")

    catalog.validate_catalog_index(
        metadata,
        {"variants": [{"name": "current"}]},
        root=tmp_path,
        architecture_ids=("tcn",),
        algorithms=("ppo",),
    )

    without_history = _minimal_index()
    without_history["families"][0]["entries"][0]["variant"] = "not_selectable"
    with pytest.raises(catalog.CatalogError, match="needs a frozen historical source"):
        catalog.validate_catalog_index(
            without_history,
            {"variants": [{"name": "current"}]},
            root=tmp_path,
            architecture_ids=("tcn",),
            algorithms=("ppo",),
        )

    missing_source = _minimal_index(historical_source="config/experiment_runs/missing.yaml")
    with pytest.raises(catalog.CatalogError, match="historical source is missing"):
        catalog.validate_catalog_index(
            missing_source,
            {"variants": [{"name": "current"}]},
            root=tmp_path,
            architecture_ids=("tcn",),
            algorithms=("ppo",),
        )


def test_retired_variant_renders_as_historical_with_its_source(tmp_path: Path, monkeypatch) -> None:
    historical_source = tmp_path / "config" / "experiment_runs" / "frozen_comparison.yaml"
    historical_source.parent.mkdir(parents=True)
    historical_source.write_text("experiment_run_id: frozen-comparison\n", encoding="utf-8")
    metadata = yaml.safe_load(catalog.CATALOG_PATH.read_text(encoding="utf-8"))
    metadata["families"] = [
        {
            "id": "historical_status_test",
            "domain": "representation",
            "title": "Historical status test",
            "question": "Does the preserved historical variant remain selectable?",
            "comparison_type": "descriptive",
            "entries": [
                {
                    "variant": "ladder_a0_flat",
                    "label": "A",
                    "role": "reference",
                    "description": "Current reference.",
                    "changed_factors": [],
                },
                {
                    "variant": "retired_variant",
                    "label": "B",
                    "role": "candidate",
                    "description": "No longer selectable.",
                    "changed_factors": ["encoder"],
                    "historical_sources": ["config/experiment_runs/frozen_comparison.yaml"],
                },
            ],
        }
    ]
    index_path = tmp_path / "variant_catalog.yaml"
    index_path.write_text(yaml.safe_dump(metadata), encoding="utf-8")
    monkeypatch.setattr(catalog, "CATALOG_PATH", index_path)
    validate = catalog.validate_catalog_index
    monkeypatch.setattr(
        catalog,
        "validate_catalog_index",
        lambda metadata, experiments: validate(metadata, experiments, root=tmp_path),
    )
    monkeypatch.setattr(
        catalog,
        "load_experiments",
        lambda: {"variants": [{"name": "ladder_a0_flat"}]},
    )
    monkeypatch.setattr(
        catalog,
        "resolve_variant",
        lambda *_args, **_kwargs: {
            "algo": "ppo",
            "arch": "tcn",
            "reward_mode": "dsr",
            "strategy": "baseline",
        },
    )
    monkeypatch.setattr(
        catalog,
        "load_variant_ftmo_config",
        lambda _name: {
            "limit_value_mode": "percent_equity",
            "max_drawdown_mode": "static",
            "risk_per_trade_limit": 1000.0,
            "daily_loss_limit_pct": 0.05,
            "max_loss_limit_initial_pct": 0.1,
            "risk_sizing_limit_usd": 900.0,
        },
    )

    result = catalog.build_catalog()
    retired = result["families"][0]["entries"][1]
    assert retired["status"] == "Historical"
    rendered = catalog.render_catalog(result)
    assert "**Research domain:** `representation`" in rendered
    assert "| B | `retired_variant` | Historical |" in rendered
    assert "../config/experiment_runs/frozen_comparison.yaml" in rendered
    assert "retired_variant` | Selectable" not in rendered


def test_matched_family_requires_one_control_and_a_treatment() -> None:
    metadata = _minimal_index()
    metadata["families"][0]["entries"][0]["role"] = "candidate"

    with pytest.raises(catalog.CatalogError, match="one control and at least one treatment"):
        catalog.validate_catalog_index(
            metadata,
            {"variants": [{"name": "current"}]},
            root=Path("."),
            architecture_ids=("tcn",),
            algorithms=("ppo",),
        )


def test_rendered_catalog_is_stable_and_explains_family_local_labels() -> None:
    resolved_catalog = catalog.build_catalog()

    rendered = catalog.render_catalog(resolved_catalog)

    assert rendered == catalog.render_catalog(resolved_catalog)
    assert "A/B labels are local to each family" in rendered
    assert "`rq_mtf_control_tcn`" in rendered
    assert "`rq_mtf_treatment_mtf`" in rendered
    assert (
        "percent_equity; trade $1,000; daily 5.0% of initial balance from session-open equity; "
        "max 10.0% of initial balance (static); size cap $900"
    ) in rendered


def test_catalog_check_reports_a_stale_generated_page(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(catalog, "CATALOG_PAGE_PATH", tmp_path / "model_variants.md")
    monkeypatch.setattr(catalog, "build_catalog", lambda: {})
    monkeypatch.setattr(catalog, "render_catalog", lambda _: "new page\n")
    catalog.CATALOG_PAGE_PATH.write_text("old page\n", encoding="utf-8")

    assert catalog.main(["--check"]) == 1


def test_catalog_write_updates_only_the_generated_page(tmp_path: Path, monkeypatch) -> None:
    output = tmp_path / "model_variants.md"
    monkeypatch.setattr(catalog, "CATALOG_PAGE_PATH", output)
    resolved_catalog = catalog.build_catalog()
    monkeypatch.setattr(catalog, "build_catalog", lambda: resolved_catalog)

    assert catalog.main(["--write"]) == 0
    assert output.read_text(encoding="utf-8") == catalog.render_catalog(resolved_catalog)
