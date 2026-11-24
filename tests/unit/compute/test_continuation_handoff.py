"""Validation of a checkpoint-continuation handoff against its preserved source run."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from compute.slurm import continuation
from compute.slurm.continuation import resolve_handoff

SOURCE_ID = "source_run"
TARGET_ID = "target_run"
FINGERPRINT = "abc123"
VARIANTS = ["alpha", "beta"]
SEEDS = [1, 2]


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _fixture(tmp_path: Path) -> dict[str, Path]:
    """Build a repository with a preserved source run and a valid handoff."""
    repo = tmp_path / "repo"
    source = repo / "runs" / SOURCE_ID
    _write_json(source / "experiment_run.json", {"fingerprint": FINGERPRINT})
    spec = repo / "specs" / f"{TARGET_ID}.yaml"
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text(
        yaml.safe_dump({"experiment_run_id": TARGET_ID, "variants": VARIANTS, "seeds": SEEDS}),
        encoding="utf-8",
    )
    checkpoints = [
        {
            "key": f"{variant}__seed{seed}",
            "source_experiment_run_id": SOURCE_ID,
            "source_experiment_run_fingerprint": FINGERPRINT,
        }
        for variant in VARIANTS
        for seed in SEEDS
    ]
    checkpoint_map = repo / "maps" / "checkpoints.json"
    _write_json(checkpoint_map, {"schema_version": 1, "checkpoints": checkpoints})
    handoff = source / "handoff.json"
    _write_json(
        handoff,
        {
            "schema": "aalto.experiment_run_continuation_handoff.v1",
            "source_experiment_run_id": SOURCE_ID,
            "source_experiment_run_fingerprint": FINGERPRINT,
            "target_experiment_run_id": TARGET_ID,
            "experiment_run_spec": "specs/target_run.yaml",
            "checkpoint_map": "maps/checkpoints.json",
        },
    )
    return {"repo": repo, "source": source, "handoff": handoff, "map": checkpoint_map}


def _reload_handoff(path: Path, **changes: Any) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.update(changes)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_valid_handoff_returns_target_spec_and_source(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)

    target, spec, source = resolve_handoff(paths["repo"], paths["source"], paths["handoff"])

    assert target == TARGET_ID
    assert spec == "specs/target_run.yaml"
    assert source == str(paths["source"].resolve())


def test_handoff_outside_the_source_run_is_refused(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    outside = tmp_path / "elsewhere.json"
    _write_json(outside, {})

    with pytest.raises(ValueError, match="must remain inside"):
        resolve_handoff(paths["repo"], paths["source"], outside)


def test_source_run_outside_the_repository_is_refused(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    elsewhere = tmp_path / "other" / SOURCE_ID
    _write_json(elsewhere / "experiment_run.json", {"fingerprint": FINGERPRINT})
    _write_json(elsewhere / "handoff.json", {})

    with pytest.raises(ValueError, match="must remain inside"):
        resolve_handoff(paths["repo"], elsewhere, elsewhere / "handoff.json")


def test_unsupported_schema_is_refused(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    _reload_handoff(paths["handoff"], schema="wrong")

    with pytest.raises(ValueError, match="unsupported experiment run continuation handoff"):
        resolve_handoff(paths["repo"], paths["source"], paths["handoff"])


def test_non_dict_handoff_is_refused(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    paths["handoff"].write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported experiment run continuation handoff"):
        resolve_handoff(paths["repo"], paths["source"], paths["handoff"])


def test_fingerprint_mismatch_is_refused(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    _reload_handoff(paths["handoff"], source_experiment_run_fingerprint="other")

    with pytest.raises(ValueError, match="does not identify the preserved source"):
        resolve_handoff(paths["repo"], paths["source"], paths["handoff"])


@pytest.mark.parametrize("bad_id", ["", "has space", "-leading", 7])
def test_invalid_target_id_is_refused(tmp_path: Path, bad_id: Any) -> None:
    paths = _fixture(tmp_path)
    _reload_handoff(paths["handoff"], target_experiment_run_id=bad_id)

    with pytest.raises(ValueError, match="target experiment run ID is invalid"):
        resolve_handoff(paths["repo"], paths["source"], paths["handoff"])


def test_missing_spec_or_map_path_is_refused(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    _reload_handoff(paths["handoff"], experiment_run_spec=None)

    with pytest.raises(ValueError, match="spec or checkpoint map is missing"):
        resolve_handoff(paths["repo"], paths["source"], paths["handoff"])


def test_target_path_escaping_the_repository_is_refused(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    _reload_handoff(paths["handoff"], experiment_run_spec="../escape.yaml")

    with pytest.raises(ValueError, match="must remain inside the repository"):
        resolve_handoff(paths["repo"], paths["source"], paths["handoff"])


def test_absent_target_file_is_refused(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    paths["map"].unlink()

    with pytest.raises(ValueError, match="spec or checkpoint map is absent"):
        resolve_handoff(paths["repo"], paths["source"], paths["handoff"])


def test_spec_with_wrong_id_is_refused(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    spec = paths["repo"] / "specs" / "target_run.yaml"
    spec.write_text(yaml.safe_dump({"experiment_run_id": "different"}), encoding="utf-8")

    with pytest.raises(ValueError, match="spec ID does not match"):
        resolve_handoff(paths["repo"], paths["source"], paths["handoff"])


def test_unsupported_checkpoint_map_schema_is_refused(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    _write_json(paths["map"], {"schema_version": 2, "checkpoints": []})

    with pytest.raises(ValueError, match="unsupported schema"):
        resolve_handoff(paths["repo"], paths["source"], paths["handoff"])


def test_checkpoint_map_without_a_list_is_refused(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    _write_json(paths["map"], {"schema_version": 1, "checkpoints": "nope"})

    with pytest.raises(ValueError, match="has no checkpoints list"):
        resolve_handoff(paths["repo"], paths["source"], paths["handoff"])


def test_checkpoint_map_must_cover_the_run_keys_exactly(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    data = json.loads(paths["map"].read_text(encoding="utf-8"))
    data["checkpoints"] = data["checkpoints"][:-1]
    _write_json(paths["map"], data)

    with pytest.raises(ValueError, match="does not cover the experiment run keys exactly"):
        resolve_handoff(paths["repo"], paths["source"], paths["handoff"])


def test_checkpoint_with_another_source_lineage_is_refused(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    data = json.loads(paths["map"].read_text(encoding="utf-8"))
    data["checkpoints"][0]["source_experiment_run_fingerprint"] = "other"
    _write_json(paths["map"], data)

    with pytest.raises(ValueError, match="different source experiment run lineage"):
        resolve_handoff(paths["repo"], paths["source"], paths["handoff"])


def test_main_prints_target_spec_and_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = _fixture(tmp_path)
    monkeypatch.setattr(
        "sys.argv",
        [
            "continuation",
            "--repo",
            str(paths["repo"]),
            "--source-experiment-run",
            str(paths["source"]),
            "--handoff",
            str(paths["handoff"]),
        ],
    )

    assert continuation.main() == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines == [TARGET_ID, "specs/target_run.yaml", str(paths["source"].resolve())]
