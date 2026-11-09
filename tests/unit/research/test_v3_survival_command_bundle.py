from pathlib import Path
from typing import Any

from scripts.research.audits.build_v3_survival_command_bundle import build_bundle

from training.configuration.research_protocol import load_research_protocol

ROOT = Path(__file__).resolve().parents[3]
SOURCE = "a" * 40


def _readiness(price: bool) -> dict[str, Any]:
    return {
        "schema_version": "pretraining-scientific-readiness-v1",
        "status": "pass",
        "source_commit": SOURCE,
        "scientific_training_authorized": True,
        "price_training_authorized": price,
    }


def test_survival_bundle_serializes_requested_roles_and_keeps_price_separate() -> None:
    protocol = load_research_protocol(ROOT / "config/research/prospective_research_protocol.yaml")
    bundle = build_bundle(
        protocol=protocol,
        readiness=_readiness(False),
        source_sha=SOURCE,
        source_clean=True,
        output_root="/scratch/v3",
        roles=["canonical", "control"],
    )
    assert [row["id"] for row in bundle["commands"]] == [
        "survival_canonical",
        "survival_control",
    ]
    assert bundle["commands"][1]["depends_on"] == ["survival_canonical"]
