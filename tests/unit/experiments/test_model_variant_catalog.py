from __future__ import annotations

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
    metadata = yaml.safe_load(catalog.CATALOG_PATH.read_text(encoding="utf-8"))
    metadata["families"] = [
        {
            "id": "historical_status_test",
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
                    "historical_sources": ["config/experiment_runs/18_variant_seed42_20m.yaml"],
                },
            ],
        }
    ]
    index_path = tmp_path / "variant_catalog.yaml"
    index_path.write_text(yaml.safe_dump(metadata), encoding="utf-8")
    monkeypatch.setattr(catalog, "CATALOG_PATH", index_path)
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
            "limit_value_mode": "fixed_usd",
            "risk_per_trade_limit": 1000.0,
            "daily_loss_limit": 5000.0,
            "max_loss_limit": 10000.0,
            "risk_sizing_limit_usd": 900.0,
        },
    )

    result = catalog.build_catalog()
    retired = result["families"][0]["entries"][1]
    assert retired["status"] == "Historical"
    rendered = catalog.render_catalog(result)
    assert "| B | `retired_variant` | Historical |" in rendered
    assert "../config/experiment_runs/18_variant_seed42_20m.yaml" in rendered
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
    assert "fixed_usd; trade $1,000; daily $5,000; max $10,000; size cap $900" in rendered


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
