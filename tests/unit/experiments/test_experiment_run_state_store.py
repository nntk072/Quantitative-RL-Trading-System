from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

from experiments.runs.state_store import atomic_json, read_manifest, validate_inputs


def test_experiment_run_manifest_uses_shared_strict_atomic_json_writer(tmp_path: Path) -> None:
    path = tmp_path / "experiment_run" / "experiment_run.json"
    manifest = {"state": "running", "completed": 2}

    atomic_json(path, manifest)

    assert path.read_text(encoding="utf-8") == '{\n  "completed": 2,\n  "state": "running"\n}\n'
    assert json.loads(path.read_text(encoding="utf-8")) == manifest
    assert read_manifest(path) == manifest


def test_resolved_comparison_arms_expand_into_one_run_matrix(tmp_path: Path) -> None:
    args = Namespace(
        variant_file=tmp_path / "no_variant_file_required_for_catalog_selection.txt",
        seeds="42 43",
        timesteps=100,
        workers=1,
        n_envs=8,
    )

    jobs = validate_inputs(args, ["control", "history"])

    assert [job["key"] for job in jobs] == [
        "control__seed42",
        "control__seed43",
        "history__seed42",
        "history__seed43",
    ]
