from __future__ import annotations

import json
from pathlib import Path

import pytest

from compute.slurm.continuation import resolve_handoff


def _handoff_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    repo = tmp_path / "repo"
    source = repo / "outputs/experiment_runs/parent"
    (source / "reports").mkdir(parents=True)
    (source / "experiment_run.json").write_text(
        json.dumps({"fingerprint": "a" * 64}), encoding="utf-8"
    )
    spec = repo / "config/experiment_runs/child.yaml"
    spec.parent.mkdir(parents=True)
    spec.write_text(
        "experiment_run_id: child_recovery\nvariants: [variant]\nseeds: [50]\n", encoding="utf-8"
    )
    checkpoint_map = repo / "outputs/experiment_runs/child_recovery/initial_checkpoints.json"
    checkpoint_map.parent.mkdir(parents=True)
    checkpoint_map.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "checkpoints": [
                    {
                        "key": "variant__seed50",
                        "source_experiment_run_id": "parent",
                        "source_experiment_run_fingerprint": "a" * 64,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    handoff = source / "reports/continuation_handoff.json"
    handoff.write_text(
        json.dumps(
            {
                "schema": "aalto.experiment_run_continuation_handoff.v1",
                "source_experiment_run_id": "parent",
                "source_experiment_run_fingerprint": "a" * 64,
                "target_experiment_run_id": "child_recovery",
                "experiment_run_spec": "config/experiment_runs/child.yaml",
                "checkpoint_map": "outputs/experiment_runs/child_recovery/initial_checkpoints.json",
            }
        ),
        encoding="utf-8",
    )
    return repo, source, handoff


def test_resolve_handoff_requires_valid_source_and_complete_target_map(tmp_path: Path) -> None:
    repo, source, handoff = _handoff_fixture(tmp_path)

    assert resolve_handoff(repo, source, handoff) == (
        "child_recovery",
        "config/experiment_runs/child.yaml",
        str(source.resolve()),
    )

    payload = json.loads(handoff.read_text(encoding="utf-8"))
    payload["source_experiment_run_fingerprint"] = "b" * 64
    handoff.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="source experiment run fingerprint"):
        resolve_handoff(repo, source, handoff)
