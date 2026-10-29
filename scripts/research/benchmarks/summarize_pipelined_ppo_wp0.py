#!/usr/bin/env python3
"""Create the evidence summary for one WP0/WP1 measurement directory."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any

BASELINES = (
    "e64-high-baseline-repeat1",
    "e64-high-baseline-repeat2",
    "e64-high-baseline-repeat3",
)
PROFILE = "e64-high-phase-profile"
TOPOLOGIES = ("e64-high-subproc64",)
REQUIRED = (*BASELINES, PROFILE, *TOPOLOGIES)


def _load_case(directory: Path, label: str) -> dict[str, Any]:
    path = directory / f"{label}.json"
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    for field in (
        "measured_ppo_core_steps_per_second",
        "measured_rollout_seconds_after_warmup",
        "measured_update_seconds_after_warmup",
    ):
        if not isinstance(value.get(field), (int, float)):
            raise ValueError(f"{path} has no numeric {field}")
    return value


def _mean_sd(values: list[float]) -> str:
    mean = statistics.mean(values)
    sd = statistics.stdev(values) if len(values) > 1 else 0.0
    return f"{mean:,.2f} ± {sd:,.2f}"


def _fmt(value: Any, digits: int = 2) -> str:
    return "unknown" if not isinstance(value, (int, float)) else f"{value:,.{digits}f}"


def _sum_numeric_values(values: list[Any]) -> int | None:
    total = 0
    for value in values:
        if not isinstance(value, (int, float)):
            return None
        total += int(value)
    return total


def _telemetry_value(value: dict[str, Any], field: str, percentile: str = "p50") -> Any:
    telemetry = value.get("gpu_telemetry")
    if not isinstance(telemetry, dict):
        return None
    fields = telemetry.get("fields")
    if not isinstance(fields, dict):
        return None
    summary = fields.get(field)
    return summary.get(percentile) if isinstance(summary, dict) else None


def _profile_lines(value: dict[str, Any]) -> list[str]:
    measured_rollout = value.get("measured_rollout_seconds_after_warmup")
    measured_update = value.get("measured_update_seconds_after_warmup")
    measured_core = value.get("measured_ppo_core_seconds_after_warmup")
    measured_component_sum = (
        float(measured_rollout) + float(measured_update)
        if isinstance(measured_rollout, (int, float)) and isinstance(measured_update, (int, float))
        else None
    )
    lines = [
        "## Profiled diagnostic run",
        "",
        "This run is instrumented and is not compared as an unprofiled FPS repeat.",
        "",
        "| Measurement | Observed |",
        "|---|---:|",
        f"| PPO-core transitions/s | {_fmt(value.get('measured_ppo_core_steps_per_second'))} |",
        f"| Warmup-excluded rollout + update sum | {_fmt(measured_component_sum)} s |",
        f"| Warmup-excluded PPO-core total | {_fmt(measured_core)} s |",
        f"| Rollout seconds after warmup | {_fmt(value.get('measured_rollout_seconds_after_warmup'))} |",
        f"| PPO update seconds after warmup | {_fmt(value.get('measured_update_seconds_after_warmup'))} |",
        f"| All-rollout measured wall | {_fmt(value.get('rollout_wall_seconds_total'))} s |",
        f"| Unattributed training wall remainder | {_fmt(value.get('unattributed_training_wall_seconds'))} s |",
        f"| Worker observation construction | {_fmt(value.get('env_observation_construction_seconds'))} s across {_fmt(value.get('env_observation_construction_calls'), 0)} calls |",
        f"| Final CUDA boundary wait | {_fmt(value.get('final_cuda_wait_seconds'))} s |",
        f"| Sampled coarse GPU utilization p50 / p95 | {_fmt(_telemetry_value(value, 'utilization.gpu', 'p50'))}% / {_fmt(_telemetry_value(value, 'utilization.gpu', 'p95'))}% |",
        f"| GPU memory used p95 | {_fmt(_telemetry_value(value, 'memory.used', 'p95'))} MiB |",
        f"| Peak PyTorch allocated HBM | {_fmt(value.get('gpu_peak_allocated_bytes', 0) / (1024**3) if value.get('gpu_peak_allocated_bytes') else None)} GiB |",
        "| SM-active / occupancy | UNKNOWN unless a supported Nsight metric was actually captured |",
        "| H2D / D2H transfer totals | UNKNOWN in the Python summary; inspect the captured Nsight trace if available |",
        "| DRAM bandwidth | UNKNOWN unless a supported Nsight metric was actually captured |",
        "| Worker send/serialize time and IPC bytes | UNKNOWN as a separate component; `vec_step_wait` includes worker completion and IPC, while Nsight OS-runtime traces are retained when available |",
        "",
    ]
    phase_cpu = value.get("phase_cpu_process_seconds")
    if isinstance(phase_cpu, dict):
        lines.extend(
            ("### Phase CPU time", "", "| Phase | Process-tree CPU seconds |", "|---|---:|")
        )
        for phase, metric in sorted(phase_cpu.items()):
            seconds = metric.get("total") if isinstance(metric, dict) else None
            lines.append(f"| {phase} | {_fmt(seconds)} |")
        lines.append("")
    shard_seconds = value.get("env_step_shard_seconds")
    if isinstance(shard_seconds, list):
        logical_workers = value.get("logical_envs_per_worker", [])
        lines.extend(
            (
                "### Worker step-time balance",
                "",
                "Times sum each worker's serial environment `step()` calls. Parent `step_wait` also includes worker result serialization/IPC; the explicit host-method table separates parent stacking. These components are diagnostic and not all additive.",
                "",
                "| Worker | Logical envs | Serial env-step seconds |",
                "|---:|---:|---:|",
            )
        )
        for index, seconds in enumerate(shard_seconds):
            width = logical_workers[index] if index < len(logical_workers) else "unknown"
            lines.append(f"| {index} | {width} | {_fmt(seconds)} |")
        lines.append("")
    method_wall = value.get("method_wall_ms")
    if isinstance(method_wall, dict):
        lines.extend(
            (
                "### Instrumented host method time",
                "",
                "These timings are diagnostic and nested phases must not be summed with their enclosing rollout/update wall time.",
                "",
                "| Method/range | Samples | Total ms | p50 ms | p95 ms |",
                "|---|---:|---:|---:|---:|",
            )
        )
        for name, metrics in sorted(method_wall.items()):
            if not isinstance(metrics, dict):
                continue
            lines.append(
                f"| {name} | {_fmt(metrics.get('sample_count'), 0)} "
                f"| {_fmt(metrics.get('total'))} "
                f"| {_fmt(metrics.get('p50'))} "
                f"| {_fmt(metrics.get('p95'))} |"
            )
        lines.append("")
    cuda_phases = value.get("phase_cuda_stream_elapsed_ms")
    if isinstance(cuda_phases, dict):
        lines.extend(
            (
                "### CUDA stream elapsed time",
                "",
                "CUDA event duration includes stream gaps; it is not SM-active time.",
                "",
                "| Phase | Samples | Total ms | p50 ms | p95 ms |",
                "|---|---:|---:|---:|---:|",
            )
        )
        for name, metrics in sorted(cuda_phases.items()):
            if not isinstance(metrics, dict):
                continue
            lines.append(
                f"| {name} | {_fmt(metrics.get('sample_count'), 0)} "
                f"| {_fmt(metrics.get('total'))} "
                f"| {_fmt(metrics.get('p50'))} "
                f"| {_fmt(metrics.get('p95'))} |"
            )
        lines.append("")
    thread_data = value.get("process_thread_telemetry")
    phases = thread_data.get("phases") if isinstance(thread_data, dict) else None
    if isinstance(phases, dict):
        lines.extend(
            (
                "### Process/thread wait and CPU samples",
                "",
                "| Phase | Samples | Busy cores | Runnable threads | Sleeping threads | Uninterruptible threads | Major faults | Top wait channels |",
                "|---|---:|---:|---:|---:|---:|---:|---|",
            )
        )
        for phase, metrics in sorted(phases.items()):
            states = metrics.get("mean_state_counts_per_sample", {})
            wait_channels = metrics.get("sampled_sleep_wait_channels", {})
            top_wait_channels = (
                ", ".join(
                    f"{name} ({count})"
                    for name, count in sorted(
                        wait_channels.items(), key=lambda item: item[1], reverse=True
                    )[:3]
                )
                or "unknown"
            )
            lines.append(
                f"| {phase} | {_fmt(metrics.get('sample_count'), 0)} "
                f"| {_fmt(metrics.get('mean_busy_cpu_cores'))} "
                f"| {_fmt(states.get('R'), 1)} "
                f"| {_fmt(states.get('S'), 1)} "
                f"| {_fmt(states.get('D'), 1)} "
                f"| {_fmt(metrics.get('major_page_faults'), 0)} "
                f"| {top_wait_channels} |"
            )
        lines.append("")
    gpu_data = value.get("gpu_telemetry")
    if isinstance(gpu_data, dict):
        lines.append(f"GPU telemetry samples: {_fmt(gpu_data.get('sample_count'), 0)}. ")
        lines.append(str(gpu_data.get("limitations", "")))
        lines.append("")
    return lines


def _nsys_lines(directory: Path) -> list[str]:
    """Expose the optional Nsight evidence alongside the generated report."""
    status_path = directory / "nsys-status.txt"
    stats_path = directory / "e64-high-nsys-stats.txt"
    trace_path = directory / "e64-high-nsys.nsys-rep"

    rows = [
        "## Nsight Systems evidence",
        "",
    ]
    if status_path.is_file():
        status = status_path.read_text().strip() or "status file was empty"
        rows.append(f"- Profile status: `{status}`")
    elif trace_path.is_file():
        rows.append("- Profile status: trace file was captured.")
    else:
        rows.append("- Profile status: no Nsight profile status or trace was produced.")

    if trace_path.is_file():
        rows.append(
            f"- Raw trace: [{trace_path.name}]({trace_path.name}) ({trace_path.stat().st_size:,} bytes)."
        )
    else:
        rows.append("- Raw trace: unavailable.")

    if stats_path.is_file():
        rows.append(f"- Kernel and memory-copy statistics: [{stats_path.name}]({stats_path.name}).")
        stats_text = stats_path.read_text().strip()
        if stats_text:
            excerpt = stats_text.splitlines()[:80]
            rows.extend(("", "```text", *excerpt, "```"))
            if len(stats_text.splitlines()) > len(excerpt):
                rows.append("")
                rows.append(
                    "The excerpt is limited to the first 80 lines; see the linked file for the full output."
                )
    else:
        rows.append("- Kernel and memory-copy statistics: unavailable.")

    rows.extend(
        (
            "",
            "SM-active cycles, occupancy, Tensor Core activity, and DRAM bandwidth remain UNKNOWN unless the captured Nsight data explicitly reports those metrics. A kernel-duration or memory-copy summary alone does not establish those utilization measures.",
            "",
        )
    )
    return rows


def build_report(directory: Path) -> str:
    cases = {label: _load_case(directory, label) for label in REQUIRED}
    baseline = [cases[label] for label in BASELINES]
    reference = baseline[0]
    invariant_fields = (
        "bundle_manifest_sha256",
        "seed",
        "n_envs",
        "rollout_steps_per_env",
        "aggregate_rollout_size",
        "batch_size",
        "n_epochs",
        "arch",
        "algo",
        "action_schema",
        "ppo_class",
    )
    for label, case in cases.items():
        for field in invariant_fields:
            if case.get(field) != reference.get(field):
                raise ValueError(f"{label} differs from baseline in supposedly fixed field {field}")

    current_cases = [cases[label] for label in (PROFILE, *TOPOLOGIES)]
    for field in ("benchmark_source_sha256", "source_patch_identity_sha256"):
        current_values = {case.get(field) for case in current_cases}
        if len(current_values) != 1:
            raise ValueError(f"new measurement cases do not share the same {field}")

    fps_values = [float(case["measured_ppo_core_steps_per_second"]) for case in baseline]
    mean_fps = statistics.mean(fps_values)
    baseline_git_shas = sorted({str(case.get("git_sha", "unknown")) for case in baseline})
    baseline_source_shas = sorted(
        {str(case.get("benchmark_source_sha256", "unknown")) for case in baseline}
    )
    current_reference = current_cases[0]
    requested_values = [case.get("total_timesteps") for case in current_cases]
    measured_values = [case.get("measured_env_steps_after_warmup") for case in current_cases]
    requested_steps = _sum_numeric_values(requested_values)
    measured_steps = _sum_numeric_values(measured_values)
    rows = [
        "# GH200 Pipelined PPO WP0/WP1 Measurement Results",
        "",
        f"**Measurement directory:** `{directory}`  ",
        f"**New measurement source SHA:** `{current_reference.get('benchmark_source_sha256')}`  ",
        f"**New measurement working-tree patch identity SHA-256:** `{current_reference.get('source_patch_identity_sha256')}`  ",
        f"**Historical baseline source commit(s):** `{', '.join(baseline_git_shas)}`  ",
        f"**Historical baseline benchmark source SHA-256:** `{', '.join(baseline_source_shas)}`  ",
        f"**Bundle manifest SHA-256:** `{reference.get('bundle_manifest_sha256')}`  ",
        f"**Policy:** {reference.get('arch')} / {reference.get('ppo_class')}; seed {reference.get('seed')}; {reference.get('n_envs')} envs; {reference.get('aggregate_rollout_size')} transitions/rollout; batch {reference.get('batch_size')}; {reference.get('n_epochs')} epochs.",
        "",
        "These are PPO-core measurements without production evaluation callbacks, checkpoint selection, or full train/test replay. They are throughput evidence, not trading-performance evidence.",
        "",
        f"The new profile/topology screen requested {_fmt(requested_steps, 0)} environment steps and measured {_fmt(measured_steps, 0)} after warmup. Each topology is a single short pass; treat differences as directional, not as a stable performance win.",
        "",
        "## Unprofiled baseline repeats",
        "",
        "| Repeat | Backend | Workers | Envs/worker | PPO-core steps/s | Rollout s | Update s | CPU cores used | GPU coarse utilization p50 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in BASELINES:
        case = cases[label]
        rows.append(
            f"| {label} | {case.get('configured_vector_backend')} "
            f"| {case.get('physical_worker_count')} "
            f"| `{case.get('logical_envs_per_worker')}` "
            f"| {_fmt(case.get('measured_ppo_core_steps_per_second'))} "
            f"| {_fmt(case.get('measured_rollout_seconds_after_warmup'))} "
            f"| {_fmt(case.get('measured_update_seconds_after_warmup'))} "
            f"| {_fmt(case.get('average_cpu_cores_used'))} "
            f"| {_fmt(_telemetry_value(case, 'utilization.gpu'))}% |"
        )
    rows.extend(
        (
            f"| **Mean ± sample SD** | — | — | — | **{_mean_sd(fps_values)}** | — | — | — | — |",
            "",
            "## Worker-topology screen",
            "",
            "| Case | Backend | Workers | Envs/worker | PPO-core steps/s | Change vs baseline mean | Rollout s | Update s |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        )
    )
    for label in TOPOLOGIES:
        case = cases[label]
        fps = float(case["measured_ppo_core_steps_per_second"])
        rows.append(
            f"| {label} | {case.get('configured_vector_backend')} "
            f"| {case.get('physical_worker_count')} "
            f"| `{case.get('logical_envs_per_worker')}` "
            f"| {_fmt(fps)} | {(fps / mean_fps - 1.0) * 100:+.2f}% "
            f"| {_fmt(case.get('measured_rollout_seconds_after_warmup'))} "
            f"| {_fmt(case.get('measured_update_seconds_after_warmup'))} |"
        )
    rows.extend(("", *_profile_lines(cases[PROFILE])))
    rows.extend(_nsys_lines(directory))
    rows.extend(
        (
            "## Interpretation limits",
            "",
            "- The three baseline repeats define the unprofiled reference. The profiler case is diagnostic and excluded from that mean.",
            "- A topology winner is only a throughput candidate; this benchmark does not establish identical PPO learning trajectories or policy quality.",
            "- Coarse `nvidia-smi utilization.gpu` is not SM occupancy or active-cycle percentage. CUDA event elapsed time includes stream gaps.",
            "- Full training callbacks, checkpointing, train-year replay, report-only test replay, and end-to-end makespan are outside this PPO-core probe.",
            "- Any absent metric remains UNKNOWN. Do not infer occupancy or memory bandwidth from allocated/reserved HBM.",
            "",
        )
    )
    return "\n".join(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("measurement_dir", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    report = build_report(args.measurement_dir)
    output = args.output or args.measurement_dir / "RESULTS.md"
    output.write_text(report)
    print(output)


if __name__ == "__main__":
    main()
