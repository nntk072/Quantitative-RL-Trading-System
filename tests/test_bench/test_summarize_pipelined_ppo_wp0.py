from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts.research.benchmarks.summarize_pipelined_ppo_wp0 import (
    REQUIRED,
    build_report,
)


def _case(*, fps: float, backend: str = "sharded_bundle") -> dict[str, object]:
    return {
        "measured_ppo_core_steps_per_second": fps,
        "measured_rollout_seconds_after_warmup": 150.0,
        "measured_update_seconds_after_warmup": 85.0,
        "measured_ppo_core_seconds_after_warmup": 235.0,
        "rollout_wall_seconds_total": 180.0,
        "unattributed_training_wall_seconds": 5.0,
        "bundle_manifest_sha256": "bundle-sha",
        "benchmark_source_sha256": "source-sha",
        "source_patch_identity_sha256": "patch-sha",
        "seed": 42,
        "n_envs": 64,
        "rollout_steps_per_env": 256,
        "aggregate_rollout_size": 16384,
        "batch_size": 4096,
        "n_epochs": 15,
        "arch": "mtf_shared_tcn_reasoning",
        "algo": "ppo",
        "action_schema": {"thesis_category_count": 109},
        "ppo_class": "PPO",
        "configured_vector_backend": backend,
        "physical_worker_count": 16,
        "logical_envs_per_worker": [4] * 16,
        "env_step_shard_seconds": [12.0] * 16,
        "env_observation_construction_seconds": 200.0,
        "env_observation_construction_calls": 16000,
        "final_cuda_wait_seconds": 0.2,
        "average_cpu_cores_used": 3.5,
        "gpu_peak_allocated_bytes": 10 * 1024**3,
        "gpu_telemetry": {
            "sample_count": 10,
            "fields": {
                "utilization.gpu": {"p50": 20.0, "p95": 35.0},
                "memory.used": {"p50": 12000.0, "p95": 13000.0},
            },
            "limitations": "coarse device telemetry",
        },
        "phase_cpu_process_seconds": {
            "collect_rollouts": {"total": 100.0},
            "train": {"total": 90.0},
        },
        "method_wall_ms": {"vec_step_wait": {"sample_count": 100, "total": 120000.0}},
        "phase_cuda_stream_elapsed_ms": {"train": {"sample_count": 10, "total": 85000.0}},
        "process_thread_telemetry": {
            "phases": {
                "ppo.train": {
                    "sample_count": 10,
                    "mean_busy_cpu_cores": 2.0,
                    "mean_thread_count": 40.0,
                    "major_page_faults": 0,
                    "voluntary_context_switches_per_second": 10.0,
                    "involuntary_context_switches_per_second": 2.0,
                    "mean_state_counts_per_sample": {"R": 2.0, "S": 38.0, "D": 0.0},
                    "sampled_sleep_wait_channels": {"futex_wait": 100},
                }
            }
        },
    }


def _write_cases(directory: Path) -> None:
    for index, label in enumerate(REQUIRED):
        backend = "subproc" if label.endswith("subproc64") else "sharded_bundle"
        payload = _case(fps=950.0 + index, backend=backend)
        if label == "e64-high-phase-profile":
            payload["phase_profile_enabled"] = True
        (directory / f"{label}.json").write_text(json.dumps(payload))


def test_summary_reports_repeats_topology_and_unknown_hardware_metrics(tmp_path: Path) -> None:
    _write_cases(tmp_path)
    for label in REQUIRED[:3]:
        path = tmp_path / f"{label}.json"
        payload = json.loads(path.read_text())
        payload["git_sha"] = "historical-baseline-commit"
        payload["benchmark_source_sha256"] = "historical-baseline-source"
        payload["source_patch_identity_sha256"] = "historical-baseline-patch"
        path.write_text(json.dumps(payload))

    report = build_report(tmp_path)

    assert "Mean ± sample SD" in report
    assert "New measurement working-tree patch identity SHA-256" in report
    assert "historical-baseline-commit" in report
    assert "historical-baseline-source" in report
    assert "e64-high-subproc64" in report
    assert "SM-active / occupancy | UNKNOWN" in report
    assert "DRAM bandwidth | UNKNOWN" in report
    assert "Worker send/serialize time and IPC bytes | UNKNOWN" in report
    assert "Runnable threads" in report
    assert "futex_wait (100)" in report
    assert "Worker step-time balance" in report
    assert "Worker send/serialize time and IPC bytes | UNKNOWN" in report
    assert "H2D / D2H transfer totals | UNKNOWN" in report
    assert "Warmup-excluded rollout + update sum | 235.00 s" in report
    assert "Warmup-excluded PPO-core total | 235.00 s" in report


def test_summary_rejects_mismatched_fixed_policy_geometry(tmp_path: Path) -> None:
    _write_cases(tmp_path)
    path = tmp_path / "e64-high-subproc64.json"
    payload = json.loads(path.read_text())
    payload["n_epochs"] = 10
    path.write_text(json.dumps(payload))

    with pytest.raises(ValueError, match="n_epochs"):
        build_report(tmp_path)


def test_summary_rejects_mixed_working_tree_patch_identity(tmp_path: Path) -> None:
    _write_cases(tmp_path)
    path = tmp_path / "e64-high-subproc64.json"
    payload = json.loads(path.read_text())
    payload["source_patch_identity_sha256"] = "different-patch"
    path.write_text(json.dumps(payload))

    with pytest.raises(ValueError, match="source_patch_identity_sha256"):
        build_report(tmp_path)


def test_summary_rejects_mixed_new_measurement_sources(tmp_path: Path) -> None:
    _write_cases(tmp_path)
    path = tmp_path / "e64-high-subproc64.json"
    payload = json.loads(path.read_text())
    payload["benchmark_source_sha256"] = "different-source"
    path.write_text(json.dumps(payload))

    with pytest.raises(ValueError, match="benchmark_source_sha256"):
        build_report(tmp_path)


def test_summary_reports_missing_nsight_evidence_as_unknown(tmp_path: Path) -> None:
    _write_cases(tmp_path)
    (tmp_path / "nsys-status.txt").write_text("nsys=UNKNOWN (not installed on allocated node)\n")

    report = build_report(tmp_path)

    assert "## Nsight Systems evidence" in report
    assert "nsys=UNKNOWN (not installed on allocated node)" in report
    assert "Raw trace: unavailable" in report
    assert "Kernel and memory-copy statistics: unavailable" in report
    assert (
        "SM-active cycles, occupancy, Tensor Core activity, and DRAM bandwidth remain UNKNOWN"
        in report
    )


def test_summary_links_and_embeds_captured_nsight_statistics(tmp_path: Path) -> None:
    _write_cases(tmp_path)
    (tmp_path / "e64-high-nsys.nsys-rep").write_bytes(b"captured trace")
    (tmp_path / "e64-high-nsys-stats.txt").write_text(
        "CUDA GPU Kernel Summary\nexample_kernel 1.25 ms\n"
    )

    report = build_report(tmp_path)

    assert "[e64-high-nsys.nsys-rep](e64-high-nsys.nsys-rep)" in report
    assert "[e64-high-nsys-stats.txt](e64-high-nsys-stats.txt)" in report
    assert "CUDA GPU Kernel Summary" in report
    assert "example_kernel 1.25 ms" in report
