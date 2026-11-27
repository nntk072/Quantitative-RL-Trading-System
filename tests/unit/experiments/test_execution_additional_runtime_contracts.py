"""Additional experiment-controller continuation contracts."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from experiments.runs import execution


def test_interrupted_worker_resumes_as_a_new_attempt_without_duplicate_identity(
    tmp_path: Path, monkeypatch: Any
) -> None:
    repository = tmp_path / "repo"
    config = repository / "config"
    (config / "base").mkdir(parents=True)
    (config / "experiments.yaml").write_text(
        "variants:\n  - name: resume_probe\n", encoding="utf-8"
    )
    (config / "base" / "default.yaml").write_text(
        "data:\n  raw_dir: data\n  cache_dir: null\n  split:\n"
        "    train_end: '2025-12-31'\n    test_start: '2026-01-01'\n",
        encoding="utf-8",
    )
    variant_file = repository / "variants.txt"
    variant_file.write_text("resume_probe\n", encoding="utf-8")
    spec = config / "run.yaml"
    spec.write_text(
        "experiment_run_id: resume-probe\n"
        "variant_file: variants.txt\n"
        "variants: [resume_probe]\n"
        "seeds: [7]\n"
        "timesteps: 100\n"
        "data_source: frames\n"
        "split:\n  train_end: '2025-12-31'\n  test_start: '2026-01-01'\n"
        "evaluation:\n  locked_oos_role: final_report_only\n"
        "  selection_allowed: false\n  deterministic: true\n",
        encoding="utf-8",
    )
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
        lambda *_args: [config / "experiments.yaml", variant_file],
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
        "verify_experiment_run_source_snapshot",
        lambda *_args, **_kwargs: (True, ""),
    )
    monkeypatch.setattr(
        execution,
        "available_resources",
        lambda: {"cpu_affinity": 4, "memory_limit_bytes": 128 * 1024**3},
    )
    monkeypatch.setattr(execution, "sample_resources", lambda *_args: None)
    monkeypatch.setattr(execution, "resolve_worker_nodes", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(execution.__dict__["signal"], "signal", lambda *_args: None)
    monkeypatch.setattr(
        execution.__dict__["subprocess"], "check_output", lambda *_args, **_kwargs: "a" * 40
    )
    monkeypatch.setattr(
        execution.__dict__["subprocess"],
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )

    class InterruptedWorker:
        pid = 5678
        polls = iter([None, -15, -15])

        def poll(self) -> int | None:
            return next(self.polls)

    class CompletedWorker:
        pid = 5679

        def poll(self) -> int:
            return 0

    workers = iter([InterruptedWorker(), CompletedWorker()])
    monkeypatch.setattr(
        execution.__dict__["subprocess"], "Popen", lambda *_args, **_kwargs: next(workers)
    )
    monkeypatch.setattr(execution.__dict__["os"], "killpg", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        execution.__dict__["time"], "sleep", lambda _seconds: setattr(execution, "STOP", True)
    )
    common_argv = [
        "experiment_run_controller.py",
        "--experiment-run-spec",
        str(spec),
        "--workers",
        "1",
        "--n-envs",
        "4",
        "--test-worker",
        "/test/fake-worker",
    ]
    monkeypatch.setattr(sys, "argv", common_argv)

    assert execution.main() == 1

    run_dir = repository / "outputs" / "gpu_experiment_runs" / "resume-probe"
    interrupted = json.loads((run_dir / "experiment_run.json").read_text(encoding="utf-8"))
    assert interrupted["jobs"][0]["status"] == "interrupted"
    assert interrupted["jobs"][0]["attempts"] == 1
    assert not (run_dir / "markers" / "resume_probe__seed7.done").exists()
    initial_fingerprint = interrupted["fingerprint"]

    monkeypatch.setattr(execution, "STOP", False)
    monkeypatch.setattr(sys, "argv", [*common_argv, "--resume"])
    assert execution.main() == 0

    completed = json.loads((run_dir / "experiment_run.json").read_text(encoding="utf-8"))
    second_attempt = json.loads(
        (
            run_dir
            / "runs"
            / "attempts"
            / "resume_probe__seed7"
            / "attempt2"
            / "attempt_provenance.json"
        ).read_text(encoding="utf-8")
    )
    assert completed["jobs"][0]["status"] == "succeeded"
    assert completed["jobs"][0]["attempts"] == 2
    assert completed["fingerprint"] == initial_fingerprint
    assert second_attempt["resume_from_attempt"] == 1
    assert second_attempt["experiment_run_fingerprint"] == initial_fingerprint
    assert (run_dir / "markers" / "resume_probe__seed7.done").is_file()
