from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.research.benchmarks.summarize_wp3_cohort_feasibility import build_report


def _write(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value))


def test_report_compares_paired_repeats_and_applies_material_gain_gate(tmp_path: Path) -> None:
    common = {
        "n_envs": 64,
        "aggregate_rollout_size": 16384,
        "batch_size": 4096,
        "n_epochs": 15,
    }
    _write(
        tmp_path / "sequential64-profile.json",
        {
            **common,
            "slurm_job_id": "job-1",
            "hostname": "gpuarm1",
            "config_path": "config.yaml",
            "config_sha256": "config-hash",
            "bundle_manifest_sha256": "bundle-hash",
            "rollout_steps_per_env": 256,
            "method_wall_ms": {
                "policy_forward": {"p50": 10.0, "p95": 12.0},
                "vec_step_wait": {"p50": 20.0, "p95": 30.0},
            },
            "env_step_sampled_latency_ms": {"p50": 2.0, "p95": 3.0},
            "ipc_transport": {
                "send_calls": 64,
                "recv_calls": 64,
                "send_bytes": 640,
                "recv_bytes": 640,
                "send_transport_latency": {"p50_ms": 1.0, "p95_ms": 2.0},
                "recv_transport_latency": {"p50_ms": 1.0, "p95_ms": 2.0},
            },
            "gpu_telemetry": {"fields": {"utilization.gpu": {"p50": 20.0, "p95": 80.0}}},
        },
    )
    _write(
        tmp_path / "cohort2-contract-smoke.json",
        {
            **common,
            "high_throughput_runtime_identity_validation": {"passed": True},
            "update_calls": 1,
            "measured_ppo_core_steps_per_second": 100.0,
            "cohort_pipeline": {
                "completed_rollouts": [
                    {
                        "policy_version": 0,
                        "rollout_buffer_full": True,
                        "gae_finite": True,
                    }
                ],
                "thesis_invalid": 0,
                "thesis_bad_center": 0,
                "rollout_action_order_checks": 1,
                "sb3_steps_accepted": 256,
                "transition_batches": 256,
                "transition_rows": 16384,
                "observation_rows_mismatch": 0,
                "nonfinite_rewards": 0,
            },
        },
    )
    for topology, values in (
        ("sequential64", (100.0, 102.0, 98.0)),
        ("pipeline2x32", (105.0, 104.0, 106.0)),
        ("pipeline4x16", (103.0, 102.0, 104.0)),
    ):
        for seed, fps in zip((42, 43, 44), values, strict=True):
            _write(
                tmp_path / f"{topology}-seed{seed}.json",
                {
                    **common,
                    "measured_ppo_core_steps_per_second": fps,
                },
            )

    report = build_report(tmp_path)

    assert "WP3 Cohort-Pipeline Feasibility" in report
    assert "Does not meet the >=20% repeatable gain gate" in report
    assert "action order in buffer | PASS" in report
