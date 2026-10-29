#!/usr/bin/env python3
"""Summarize the bounded WP3 collector-feasibility experiment."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any

SEEDS = (42, 43, 44)
TOPOLOGIES = {
    "sequential64": "Sequential 64-env SB3 collector",
    "pipeline2x32": "Pipelined 2 x 32 cohorts",
    "pipeline4x16": "Pipelined 4 x 16 cohorts",
}


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"{path} does not contain a JSON object")
    return value


def _stats(values: list[float]) -> tuple[float, float]:
    return statistics.mean(values), statistics.stdev(values) if len(values) > 1 else 0.0


def _fmt(value: Any, digits: int = 2) -> str:
    return f"{value:,.{digits}f}" if isinstance(value, (float, int)) else "unknown"


def _repeat(directory: Path, topology: str, seed: int) -> dict[str, Any]:
    return _load(directory / f"{topology}-seed{seed}.json")


def _pipeline_smoke_checks(value: dict[str, Any]) -> dict[str, bool]:
    pipeline = value.get("cohort_pipeline")
    if not isinstance(pipeline, dict):
        return {"report_present": False}
    raw_completed = pipeline.get("completed_rollouts")
    completed = raw_completed if isinstance(raw_completed, list) else []
    return {
        "report_present": True,
        "runtime_identity": bool(
            value.get("high_throughput_runtime_identity_validation", {}).get("passed")
        ),
        "64_env_geometry": value.get("n_envs") == 64
        and value.get("aggregate_rollout_size") == 16384
        and value.get("batch_size") == 4096
        and value.get("n_epochs") == 15,
        "single_policy_version_per_rollout": bool(completed)
        and all(isinstance(item, dict) and item.get("policy_version") == 0 for item in completed),
        "buffer_full_and_gae_finite": bool(completed)
        and all(
            item.get("rollout_buffer_full") is True and item.get("gae_finite") is True
            for item in completed
        ),
        "invalid_thesis_actions_zero": pipeline.get("thesis_invalid") == 0
        and pipeline.get("thesis_bad_center") == 0,
        "action_order_in_buffer": pipeline.get("rollout_action_order_checks") == 1,
        "worker_transition_alignment": pipeline.get("sb3_steps_accepted") == 256
        and pipeline.get("transition_batches") == 256
        and pipeline.get("transition_rows") == 16384
        and pipeline.get("observation_rows_mismatch") == 0,
        "finite_rewards_and_termination_types": pipeline.get("nonfinite_rewards") == 0,
        "one_update_after_rollout": value.get("update_calls") == 1,
        "finite_ppo_core_rate": isinstance(
            value.get("measured_ppo_core_steps_per_second"), (int, float)
        )
        and value["measured_ppo_core_steps_per_second"] > 0,
    }


def _percentile(report: dict[str, Any], method: str, percentile: str) -> Any:
    timings = report.get("method_wall_ms")
    row = timings.get(method) if isinstance(timings, dict) else None
    return row.get(percentile) if isinstance(row, dict) else None


def _mean_overlap(report: dict[str, Any]) -> float | None:
    overlap = report.get("cpu_step_overlap_with_later_cohort_inference")
    rows = overlap.get("by_later_cohort") if isinstance(overlap, dict) else None
    if not isinstance(rows, list):
        return None
    fractions = [
        float(row["mean_fraction_with_earlier_cpu_step_active"])
        for row in rows[1:]
        if isinstance(row, dict)
        and isinstance(row.get("mean_fraction_with_earlier_cpu_step_active"), (float, int))
    ]
    return statistics.mean(fractions) if fractions else None


def build_report(directory: Path) -> str:
    profile = _load(directory / "sequential64-profile.json")
    smoke = _load(directory / "cohort2-contract-smoke.json")
    checks = _pipeline_smoke_checks(smoke)

    rows = ["# WP3 Cohort-Pipeline Feasibility", ""]
    rows.extend(
        [
            f"- Allocation/job: `{profile.get('slurm_job_id', directory.name)}` on `{profile.get('hostname', 'gpuarm1')}`; see `allocation.txt`.",
            f"- Config: `{profile.get('config_path')}`, SHA-256 `{profile.get('config_sha256')}`.",
            f"- Shared training bundle manifest SHA-256: `{profile.get('bundle_manifest_sha256')}`.",
            f"- PPO geometry: {profile.get('n_envs')} environments x {profile.get('rollout_steps_per_env')} steps; batch {profile.get('batch_size')}; {profile.get('n_epochs')} epochs.",
            "- Scope: one bounded rollout-contract smoke; one profiled sequential baseline; three warmed PPO-core repeats per topology. No training campaign, checkpoint, or production collector change.",
            "",
            "## Correctness and on-policy checks",
            "",
            "| Check | Result |",
            "|---|---|",
        ]
    )
    for name, passed in checks.items():
        rows.append(f"| {name.replace('_', ' ')} | {'PASS' if passed else 'FAIL'} |")
    rows.extend(
        [
            "",
            "The prototype leaves SB3's `collect_rollouts`, `step_wait` response ordering, callback sequence, rollout buffer insertion, GAE calculation, and PPO update in control. It dispatches each contiguous environment cohort immediately after that cohort's inference. The rollout smoke checks exact raw-action ordering in the PPO buffer, finite rewards and advantages, one policy version across the rollout, complete 256-step/64-env transition batches, boolean terminations, and masked thesis selections.",
            "",
            "## Full PPO-core throughput",
            "",
            "PPO-core FPS includes completed rollout collection **and** PPO updates; the first two rollouts per repeat are warmup and excluded. All topologies use paired seeds 42/43/44, the same bundle, 64 environments, 256 steps per environment, batch 4096, 15 epochs, and one GH200 at a time.",
            "",
            "| Topology | Repeat FPS (42, 43, 44) | Mean +/- sample SD | Gain vs sequential |",
            "|---|---:|---:|---:|",
        ]
    )
    means: dict[str, float] = {}
    repeat_values: dict[str, list[float]] = {}
    for topology, label in TOPOLOGIES.items():
        reports = [_repeat(directory, topology, seed) for seed in SEEDS]
        values = [float(item["measured_ppo_core_steps_per_second"]) for item in reports]
        repeat_values[topology] = values
        means[topology], sd = _stats(values)
        gain = None
        if topology != "sequential64":
            gain = (means[topology] / means["sequential64"] - 1.0) * 100.0
        rows.append(
            f"| {label} | {', '.join(_fmt(value) for value in values)} | {_fmt(means[topology])} +/- {_fmt(sd)} | {'baseline' if gain is None else f'{gain:+.2f}%'} |"
        )
    rows.append("")
    per_seed_gains: dict[str, list[float]] = {}
    for topology in ("pipeline2x32", "pipeline4x16"):
        per_seed_gains[topology] = [
            (candidate / baseline - 1.0) * 100.0
            for candidate, baseline in zip(
                repeat_values[topology], repeat_values["sequential64"], strict=True
            )
        ]
    rows.extend(
        [
            "## CPU/GPU and IPC profile",
            "",
            f"- Parent policy inference latency, p50/p95: {_fmt(_percentile(profile, 'policy_forward', 'p50'))}/{_fmt(_percentile(profile, 'policy_forward', 'p95'))} ms per 64-env batch.",
            f"- Parent `step_wait`, p50/p95: {_fmt(_percentile(profile, 'vec_step_wait', 'p50'))}/{_fmt(_percentile(profile, 'vec_step_wait', 'p95'))} ms; it is the collector's post-dispatch wait proxy, not a direct GPU idle or SM-active measurement.",
            f"- Sampled worker `TradingEnv.step`, p50/p95: {_fmt(profile.get('env_step_sampled_latency_ms', {}).get('p50'))}/{_fmt(profile.get('env_step_sampled_latency_ms', {}).get('p95'))} ms per worker step.",
            f"- Parent IPC calls: {profile.get('ipc_transport', {}).get('send_calls')} sends / {profile.get('ipc_transport', {}).get('recv_calls')} receives; transport buffers {profile.get('ipc_transport', {}).get('send_bytes')} bytes sent / {profile.get('ipc_transport', {}).get('recv_bytes')} bytes received.",
            f"- IPC transport latency p50/p95: send {_fmt(profile.get('ipc_transport', {}).get('send_transport_latency', {}).get('p50_ms'))}/{_fmt(profile.get('ipc_transport', {}).get('send_transport_latency', {}).get('p95_ms'))} ms; receive {_fmt(profile.get('ipc_transport', {}).get('recv_transport_latency', {}).get('p50_ms'))}/{_fmt(profile.get('ipc_transport', {}).get('recv_transport_latency', {}).get('p95_ms'))} ms.",
            f"- Coarse GPU utilization p50/p95: {_fmt(profile.get('gpu_telemetry', {}).get('fields', {}).get('utilization.gpu', {}).get('p50'))}%/{_fmt(profile.get('gpu_telemetry', {}).get('fields', {}).get('utilization.gpu', {}).get('p95'))}%.",
            "- CPU/GPU cohort overlap is reported in each pipeline run as the measured fraction of later-cohort inference overlapped by earlier-cohort environment stepping. Nsight SM-active/occupancy was not measured unless the allocation log shows a successful supported trace.",
            "",
            "### Measured CPU-step / later-inference overlap",
            "",
            "| Pipeline topology | Per-repeat mean fraction (42, 43, 44) | Across-repeat mean |",
            "|---|---:|---:|",
        ]
    )
    for topology in ("pipeline2x32", "pipeline4x16"):
        reports = [_repeat(directory, topology, seed) for seed in SEEDS]
        overlaps = [_mean_overlap(item) for item in reports]
        numeric = [value for value in overlaps if value is not None]
        rows.append(
            f"| {TOPOLOGIES[topology]} | {', '.join(_fmt(value * 100.0 if value is not None else None) + '%' for value in overlaps)} | {_fmt(statistics.mean(numeric) * 100.0 if numeric else None)}% |"
        )
    rows.extend(
        [
            "",
            "## Decision",
            "",
        ]
    )
    for topology in ("pipeline2x32", "pipeline4x16"):
        gain = (means[topology] / means["sequential64"] - 1.0) * 100.0
        gains = per_seed_gains[topology]
        repeatable = all(value > 0 for value in gains)
        meets_gate = gain >= 20.0 and repeatable and all(checks.values())
        rows.append(
            f"- **{TOPOLOGIES[topology]}:** mean core gain {gain:+.2f}%; seed-wise gains {', '.join(f'{value:+.2f}%' for value in gains)}. {'Meets' if meets_gate else 'Does not meet'} the >=20% repeatable gain gate."
        )
    rows.extend(
        [
            "",
            "A result below the gate supports retaining this as a benchmark prototype and not adopting a production collector rewrite. A passing result justifies a separately reviewed implementation proposal; this feasibility experiment does not authorize a production integration.",
            "",
            "## Evidence and limitations",
            "",
            "- Raw timing JSON, case logs, allocation identity, runtime preflight, and focused test log are retained beside this report.",
            "- IPC counters measure parent-side multiprocessing transport buffers and method time; they exclude child execution and pickle encode/decode CPU time.",
            "- `step_wait` includes worker finish time and response IPC. Coarse `nvidia-smi` utilization is not a kernel-level GPU idle trace.",
            "- The prototype is benchmark-only. It does not implement asynchronous environments, overlap PPO updates with collection, or relax the on-policy barrier.",
            "",
        ]
    )
    return "\n".join(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    text = build_report(args.directory)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text)
    print(args.output)


if __name__ == "__main__":
    main()
