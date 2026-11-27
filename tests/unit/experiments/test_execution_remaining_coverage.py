"""Resume fingerprint-override contracts for the experiment-run controller."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from experiments.runs import execution


def test_resume_fingerprint_override_requires_and_records_canonical_attempt_identity(
    tmp_path: Path, monkeypatch: Any
) -> None:
    repository = tmp_path / "repo"
    config_dir = repository / "config"
    base_dir = config_dir / "base"
    base_dir.mkdir(parents=True)
    experiment_config = config_dir / "experiments.yaml"
    experiment_config.write_text("variants:\n  - name: sample_variant\n", encoding="utf-8")
    (base_dir / "default.yaml").write_text(
        "data:\n  split:\n    train_end: '2025-12-31'\n    test_start: '2026-01-01'\n",
        encoding="utf-8",
    )
    variant_file = repository / "variants.txt"
    variant_file.write_text("sample_variant\n", encoding="utf-8")
    monkeypatch.setattr(execution, "ROOT", repository)
    monkeypatch.setattr(execution, "STOP", False)
    monkeypatch.setattr(
        execution,
        "runtime_metadata",
        lambda: {"python": "test", "machine": "test", "packages": {}},
    )
    monkeypatch.setattr(
        execution,
        "experiment_run_source_files",
        lambda *_args: [experiment_config, variant_file],
    )
    monkeypatch.setattr(execution, "experiment_run_data_inputs", lambda _data: {})
    monkeypatch.setattr(
        execution,
        "write_experiment_run_source_snapshot",
        lambda *_args, **_kwargs: {
            "path": "source_snapshot.zip",
            "sha256": "a" * 64,
            "manifest_sha256": "b" * 64,
            "file_count": 2,
        },
    )
    monkeypatch.setattr(
        execution, "verify_experiment_run_source_snapshot", lambda *_args: (True, "")
    )
    monkeypatch.setattr(execution, "verify_run_artifacts", lambda *_args, **_kwargs: (True, ""))
    monkeypatch.setattr(
        execution,
        "validate_inputs",
        lambda *_args: [
            {
                "key": "sample_variant__seed7",
                "variant": "sample_variant",
                "seed": 7,
                "status": "pending",
                "attempts": 0,
            }
        ],
    )
    monkeypatch.setattr(
        execution,
        "available_resources",
        lambda: {"cpu_affinity": 4, "memory_limit_bytes": 128 * 1024**3},
    )
    monkeypatch.setattr(execution, "sample_resources", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(execution, "resolve_worker_nodes", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(execution.__dict__["signal"], "signal", lambda *_args: None)

    git_sha = "a" * 40

    def git_output(*_args: Any, **_kwargs: Any) -> str:
        return git_sha

    monkeypatch.setattr(execution.__dict__["subprocess"], "check_output", git_output)
    process_calls: list[list[str]] = []

    class CompletedWorker:
        pid = 2468

        def poll(self) -> int:
            return 0

    def fake_popen(command: list[str], **_kwargs: Any) -> CompletedWorker:
        process_calls.append(command)
        return CompletedWorker()

    monkeypatch.setattr(execution.__dict__["subprocess"], "Popen", fake_popen)
    monkeypatch.setattr(
        execution.__dict__["subprocess"],
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )

    argv = [
        "experiment_run_controller.py",
        "--variant-file",
        str(variant_file),
        "--seeds",
        "7",
        "--timesteps",
        "100",
        "--workers",
        "1",
        "--n-envs",
        "4",
        "--test-worker",
        "/test/fake-worker",
        "--experiment-run-id",
        "resume-fingerprint-coverage",
    ]
    monkeypatch.setattr(sys, "argv", argv)

    assert execution.main() == 0
    assert len(process_calls) == 1
    output = repository / "outputs" / "gpu_experiment_runs" / "resume-fingerprint-coverage"
    original_manifest = json.loads((output / "experiment_run.json").read_text(encoding="utf-8"))
    canonical_fingerprint = original_manifest["fingerprint"]

    git_sha = "b" * 40
    monkeypatch.setattr(
        sys,
        "argv",
        [
            *argv,
            "--resume",
            "--resume-fingerprint-override-reason",
            "approved source refresh",
        ],
    )

    assert execution.main() == 0
    assert len(process_calls) == 1
    updated_manifest = json.loads((output / "experiment_run.json").read_text(encoding="utf-8"))
    overrides = updated_manifest["resume_fingerprint_overrides"]
    assert len(overrides) == 1
    assert overrides[0]["reason"] == "approved source refresh"
    assert overrides[0]["canonical_fingerprint"] == canonical_fingerprint
    assert overrides[0]["effective_fingerprint"] != canonical_fingerprint
    assert "effective_identity" not in overrides[0]
    assert (
        output
        / "reports"
        / f"resume_fingerprint_override_{overrides[0]['effective_fingerprint']}.json"
    ).is_file()
