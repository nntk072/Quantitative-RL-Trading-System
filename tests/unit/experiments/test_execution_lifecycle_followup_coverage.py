"""Post-run summary failures do not change accepted worker outcomes."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from experiments.runs import execution


@pytest.mark.parametrize(
    ("summary_failure", "warning"),
    [
        ("exit", "summary generation failed: summary unavailable"),
        ("start", "summary could not start: reporting executable unavailable"),
    ],
)
def test_summary_reporting_failure_keeps_successful_worker_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    summary_failure: str,
    warning: str,
) -> None:
    repository = tmp_path / "repo"
    config_dir = repository / "config"
    base_dir = config_dir / "base"
    base_dir.mkdir(parents=True)
    experiment_config = config_dir / "experiments.yaml"
    experiment_config.write_text("variants:\n  - name: sample_variant\n", encoding="utf-8")
    (base_dir / "default.yaml").write_text(
        "data:\n  raw_dir: data\n  split:\n"
        "    train_end: '2025-12-31'\n    test_start: '2026-01-01'\n",
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
    monkeypatch.setattr(
        execution.__dict__["subprocess"], "check_output", lambda *_args, **_kwargs: "a" * 40
    )
    worker_commands: list[list[str]] = []

    class CompletedWorker:
        pid = 2468

        def poll(self) -> int:
            return 0

    def fake_popen(command: list[str], **_kwargs: Any) -> CompletedWorker:
        worker_commands.append(command)
        return CompletedWorker()

    def failed_summary(*_args: Any, **_kwargs: Any) -> SimpleNamespace:
        if summary_failure == "start":
            raise OSError("reporting executable unavailable")
        return SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="summary unavailable",
        )

    monkeypatch.setattr(execution.__dict__["subprocess"], "Popen", fake_popen)
    monkeypatch.setattr(execution.__dict__["subprocess"], "run", failed_summary)
    monkeypatch.setattr(
        sys,
        "argv",
        [
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
            "summary-failure-probe",
        ],
    )

    assert execution.main() == 0

    run_dir = repository / "outputs" / "gpu_experiment_runs" / "summary-failure-probe"
    output = capsys.readouterr().out
    assert worker_commands == [["/test/fake-worker", "sample_variant__seed7"]]
    assert (run_dir / "markers" / "sample_variant__seed7.done").is_file()
    assert "WARNING: experiment run results summary" in output
    assert warning in output
