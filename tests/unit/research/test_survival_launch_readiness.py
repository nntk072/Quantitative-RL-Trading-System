from pathlib import Path
from typing import Any

import pytest
from scripts.research.analysis.evidence.build_survival_launch_plan import build_launch_plan

from training.configuration.research_protocol import load_research_protocol

ROOT = Path(__file__).resolve().parents[3]
PROTOCOL = ROOT / "config/research/prospective_research_protocol.yaml"
CURRENT_SOURCE = "a" * 40


def _plan(
    readiness: dict[str, Any] | None = None,
    source: str | None = CURRENT_SOURCE,
    *,
    clean: bool = True,
) -> dict[str, Any]:
    return build_launch_plan(
        load_research_protocol(PROTOCOL),
        "outputs/test-survival",
        readiness_manifest=readiness,
        current_source_sha=source,
        current_source_clean=clean,
    )


def _roles(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["role"]: row for row in plan["qualification_commands"]}


def test_missing_readiness_manifest_fails_closed() -> None:
    assert all(not row["authorized_now"] for row in _roles(_plan()).values())


@pytest.mark.parametrize(
    "manifest",
    [
        {
            "schema_version": "pretraining-parallel-readiness-run-v1",
            "execution_status": "pass",
            "source_commit": CURRENT_SOURCE,
            "scientific_training_authorized": True,
            "price_training_authorized": True,
        },
        {
            "schema_version": "pretraining-scientific-readiness-v1",
            "status": "fail",
            "source_commit": CURRENT_SOURCE,
            "scientific_training_authorized": True,
            "price_training_authorized": True,
        },
        {
            "schema_version": "pretraining-scientific-readiness-v1",
            "status": "pass",
            "source_commit": "b" * 40,
            "scientific_training_authorized": True,
            "price_training_authorized": True,
        },
        {
            "schema_version": "pretraining-scientific-readiness-v1",
            "status": "pass",
            "source_commit": CURRENT_SOURCE,
            "scientific_training_authorized": "true",
            "price_training_authorized": True,
        },
    ],
)
def test_unreviewed_failed_stale_or_malformed_manifest_fails_closed(
    manifest: dict[str, Any],
) -> None:
    assert all(not row["authorized_now"] for row in _roles(_plan(manifest)).values())


def test_reviewed_manifest_authorizes_scientific_work_and_gates_price_separately() -> None:
    readiness = {
        "schema_version": "pretraining-scientific-readiness-v1",
        "status": "pass",
        "source_commit": CURRENT_SOURCE,
        "scientific_training_authorized": True,
        "price_training_authorized": False,
    }

    roles = _roles(_plan(readiness))

    assert roles["control"]["authorized_now"] is True
    assert roles["canonical"]["authorized_now"] is True
    assert roles["price_geometry"]["authorized_now"] is False


def test_price_authorization_does_not_imply_scientific_authorization() -> None:
    readiness = {
        "schema_version": "pretraining-scientific-readiness-v1",
        "status": "pass",
        "source_commit": CURRENT_SOURCE,
        "scientific_training_authorized": False,
        "price_training_authorized": True,
    }

    assert all(not row["authorized_now"] for row in _roles(_plan(readiness)).values())


def test_current_source_sha_is_required_for_authorization() -> None:
    readiness = {
        "schema_version": "pretraining-scientific-readiness-v1",
        "status": "pass",
        "source_commit": CURRENT_SOURCE,
        "scientific_training_authorized": True,
        "price_training_authorized": True,
    }

    assert all(not row["authorized_now"] for row in _roles(_plan(readiness, source=None)).values())


def test_dirty_current_source_fails_closed() -> None:
    readiness = {
        "schema_version": "pretraining-scientific-readiness-v1",
        "status": "pass",
        "source_commit": CURRENT_SOURCE,
        "scientific_training_authorized": True,
        "price_training_authorized": True,
    }

    plan = _plan(readiness, clean=False)

    assert plan["current_source_clean"] is False
    assert all(not row["authorized_now"] for row in _roles(plan).values())
