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
    commands = bundle["commands"]
    assert len(commands) == 74
    assert commands[0]["id"] == "survival_train_seed_42"
    assert commands[1]["id"] == "survival_walk_forward_fold_42_0"
    assert commands[36]["id"] == "survival_finalize"
    assert commands[37]["id"] == "survival_control_train_seed_42"
    assert commands[-1]["id"] == "survival_control_finalize"
    assert len([item for item in commands if "walk_forward_fold" in item["id"]]) == 60
    assert all(
        "/walk_forward_folds/fold_" in item["artifact_roots"][0]
        for item in commands
        if "walk_forward_fold" in item["id"]
    )
    control_train = commands[37]
    assert "run_manifest.json" in control_train["artifact_roots"][0]
    assert bundle["selection_allowed"] is False
    assert all(command.get("selection_allowed") is False for command in commands[:-1])
    assert all(command["resource_lock"] == "GPU_TRAIN_LOCK" for command in commands)


def test_correctness_smoke_is_separate_from_scientific_training_authorization() -> None:
    protocol = load_research_protocol(ROOT / "config/research/prospective_research_protocol.yaml")
    bundle = build_bundle(
        protocol=protocol,
        readiness=None,
        source_sha=SOURCE,
        source_clean=True,
        output_root="/scratch/survival-smoke",
        roles=["correctness_smoke"],
    )

    assert bundle["phase"] == "survival_correctness_smoke"
    assert bundle["scientific_training_authorized"] is False
    assert bundle["commands"] == [
        {
            "id": "survival_correctness_smoke",
            "argv": [
                ".venv/bin/python",
                "-m",
                "scripts.research.audits.run_survival_correctness_smoke",
                "--config",
                "config/research/survival_trade_setup_mtf_conditioned.yaml",
                "--output-dir",
                "/scratch/survival-smoke/correctness_smoke",
            ],
            "depends_on": [],
            "resource_lock": "GPU_TRAIN_LOCK",
            "artifact_roots": ["/scratch/survival-smoke/correctness_smoke"],
            "experiment": True,
            "scientific_training_authorization_required": False,
            "claim_scope": "synthetic_implementation_correctness_only",
            "selection_allowed": False,
        }
    ]


def test_correctness_smoke_does_not_authorize_training_roles() -> None:
    protocol = load_research_protocol(ROOT / "config/research/prospective_research_protocol.yaml")
    try:
        build_bundle(
            protocol=protocol,
            readiness=None,
            source_sha=SOURCE,
            source_clean=True,
            output_root="/scratch/survival-smoke",
            roles=["correctness_smoke", "canonical"],
        )
    except ValueError as error:
        assert "not scientifically authorized: canonical" in str(error)
    else:
        raise AssertionError("correctness smoke must not authorize canonical training")


def test_survival_bundle_requires_clean_source_even_for_smoke() -> None:
    protocol = load_research_protocol(ROOT / "config/research/prospective_research_protocol.yaml")
    try:
        build_bundle(
            protocol=protocol,
            readiness=None,
            source_sha=SOURCE,
            source_clean=False,
            output_root="/scratch/survival-smoke",
            roles=["correctness_smoke"],
        )
    except ValueError as error:
        assert "clean source tree" in str(error)
    else:
        raise AssertionError("survival bundle must require a clean source tree")
