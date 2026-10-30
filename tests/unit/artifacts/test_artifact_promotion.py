from __future__ import annotations

import json
from pathlib import Path

import pytest

from artifacts import ArtifactManifest, BaselineValidation, RetentionClass, promote_to_baseline


def _baseline_manifest() -> ArtifactManifest:
    return ArtifactManifest(
        kind="evaluation",
        artifact_id="evaluation:abc123",
        retention=RetentionClass.BASELINE_PROMOTABLE,
        parents=("run:seed42",),
        provenance={"source_revision": "abc123"},
    )


def test_validated_promotion_copies_directory_and_writes_manifest(tmp_path: Path) -> None:
    source = tmp_path / "candidate"
    source.mkdir()
    (source / "metrics.json").write_text('{"net_return": 0.12}\n', encoding="utf-8")
    destination = tmp_path / "baseline" / "candidate-v1"
    validated: list[Path] = []

    def validate(path: Path) -> BaselineValidation:
        assert json.loads((path / "metrics.json").read_text(encoding="utf-8"))["net_return"] > 0
        validated.append(path)
        return BaselineValidation("validate-candidate", ("net_return",))

    result = promote_to_baseline(source, destination, _baseline_manifest(), validate=validate)

    assert result == destination
    assert len(validated) == 1
    assert validated[0].name == "payload"
    assert not validated[0].exists()
    assert (destination / "payload" / "metrics.json").read_bytes() == (
        source / "metrics.json"
    ).read_bytes()
    stored = ArtifactManifest.read(destination / "manifest.json")
    assert stored.artifact_id == "evaluation:abc123"
    assert stored.parents == ("run:seed42",)
    assert stored.retention is RetentionClass.BASELINE_PROMOTABLE
    promotion = stored.provenance["promotion"]
    assert promotion["source"] == str(source.resolve())
    assert len(promotion["payload_sha256"]) == 64
    assert promotion["validator"] == f"{validate.__module__}.{validate.__qualname__}"
    assert promotion["validation"] == {
        "accepted": True,
        "command": "validate-candidate",
        "checks": ["net_return"],
    }


def test_validated_promotion_accepts_a_single_file(tmp_path: Path) -> None:
    source = tmp_path / "metrics.json"
    source.write_text('{"net_return": 0.12}\n', encoding="utf-8")
    destination = tmp_path / "baseline" / "metrics-v1"

    def validate(path: Path) -> BaselineValidation:
        assert path.is_file()
        assert json.loads(path.read_text(encoding="utf-8"))["net_return"] > 0
        return BaselineValidation("validate-metrics", ("net_return",))

    promote_to_baseline(source, destination, _baseline_manifest(), validate=validate)

    assert (destination / "payload").is_file()
    assert (destination / "payload").read_bytes() == source.read_bytes()


def test_failed_validation_leaves_no_baseline_artifact(tmp_path: Path) -> None:
    source = tmp_path / "candidate.json"
    source.write_text("{}\n", encoding="utf-8")
    destination = tmp_path / "baseline" / "candidate-v1"

    def reject(_: Path) -> BaselineValidation:
        raise ValueError("validation failed")

    with pytest.raises(ValueError, match="validation failed"):
        promote_to_baseline(source, destination, _baseline_manifest(), validate=reject)

    assert not destination.exists()
    assert list(destination.parent.iterdir()) == []


def test_promotion_rejects_validator_that_changes_staged_payload(tmp_path: Path) -> None:
    source = tmp_path / "candidate.json"
    source.write_text('{"net_return": 0.12}\n', encoding="utf-8")
    destination = tmp_path / "baseline" / "candidate-v1"

    def mutate(path: Path) -> BaselineValidation:
        path.write_text('{"net_return": 0.99}\n', encoding="utf-8")
        return BaselineValidation("validate-candidate", ("net_return",))

    with pytest.raises(ValueError, match="modified the staged payload"):
        promote_to_baseline(source, destination, _baseline_manifest(), validate=mutate)

    assert not destination.exists()
    assert source.read_text(encoding="utf-8") == '{"net_return": 0.12}\n'


def test_existing_destination_is_never_overwritten_or_validated(tmp_path: Path) -> None:
    source = tmp_path / "candidate.json"
    source.write_text("{}\n", encoding="utf-8")
    destination = tmp_path / "baseline"
    destination.mkdir()
    sentinel = destination / "curated.txt"
    sentinel.write_text("keep\n", encoding="utf-8")
    validator_called = False

    def validate(_: Path) -> BaselineValidation:
        nonlocal validator_called
        validator_called = True
        return BaselineValidation("validate-candidate", ("manifest",))

    with pytest.raises(FileExistsError):
        promote_to_baseline(source, destination, _baseline_manifest(), validate=validate)

    assert not validator_called
    assert sentinel.read_text(encoding="utf-8") == "keep\n"


def test_promotion_requires_baseline_promotable_retention(tmp_path: Path) -> None:
    source = tmp_path / "candidate.json"
    source.write_text("{}\n", encoding="utf-8")
    manifest = ArtifactManifest(kind="evaluation", artifact_id="evaluation:abc123")

    with pytest.raises(ValueError, match="not baseline-promotable"):
        promote_to_baseline(
            source,
            tmp_path / "baseline",
            manifest,
            validate=lambda _: BaselineValidation("validate", ("manifest",)),
        )


@pytest.mark.parametrize(
    "manifest, message",
    [
        (
            ArtifactManifest(
                kind="evaluation",
                artifact_id="evaluation:abc123",
                retention=RetentionClass.BASELINE_PROMOTABLE,
                provenance={"source_revision": "abc123"},
            ),
            "requires a parent artifact identity",
        ),
        (
            ArtifactManifest(
                kind="evaluation",
                artifact_id="evaluation:abc123",
                retention=RetentionClass.BASELINE_PROMOTABLE,
                parents=("run:seed42",),
            ),
            "requires provenance.source_revision",
        ),
    ],
)
def test_promotion_requires_source_lineage(
    tmp_path: Path, manifest: ArtifactManifest, message: str
) -> None:
    source = tmp_path / "candidate.json"
    source.write_text("{}\n", encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        promote_to_baseline(
            source,
            tmp_path / "baseline",
            manifest,
            validate=lambda _: BaselineValidation("validate", ("manifest",)),
        )


@pytest.mark.parametrize(
    "command,checks",
    [("", ("manifest",)), ("validate", ()), ("validate", ("",))],
)
def test_validation_evidence_requires_command_and_passed_checks(
    command: str, checks: tuple[str, ...]
) -> None:
    with pytest.raises(ValueError, match="baseline validation evidence"):
        BaselineValidation(command, checks)
