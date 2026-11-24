"""Profile the production PPO throughput probe with torch.profiler (CPU and GPU activities).

Systems evidence only. Runs the same probe as measure_ppo_throughput, inside a profiler
context, and writes a key-average table plus a Chrome trace. Works on CUDA and ROCm builds.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import torch
from research_tools.learning.benchmarks.measure_ppo_throughput import _train_probe


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--bundle-dir", type=Path, required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--n-envs", type=int, default=8)
    parser.add_argument("--rollout-steps-per-env", type=int, default=256)
    parser.add_argument("--rollouts", type=int, default=1, help="measured rollouts after warm-up")
    parser.add_argument("--overrides", nargs="*", default=[])
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    total = args.n_envs * args.rollout_steps_per_env * (args.rollouts + 1)
    activities = [torch.profiler.ProfilerActivity.CPU]
    if torch.cuda.is_available():
        activities.append(torch.profiler.ProfilerActivity.CUDA)
    with torch.profiler.profile(activities=activities, record_shapes=False) as prof:
        report: dict[str, Any] = _train_probe(
            n_envs=args.n_envs,
            rollout_steps_per_env=args.rollout_steps_per_env,
            total_timesteps=total,
            device=args.device,
            output=args.out_dir / "probe.json",
            config_path=args.config,
            bundle_dir=args.bundle_dir,
            overrides=args.overrides,
            warmup_rollouts=1,
        )
    sort_key = "self_cuda_time_total" if torch.cuda.is_available() else "self_cpu_time_total"
    table = prof.key_averages().table(sort_by=sort_key, row_limit=40)
    (args.out_dir / "profile_table.txt").write_text(table)
    prof.export_chrome_trace(str(args.out_dir / "trace.json"))
    summary = {
        "steps_per_second": report.get("measured_ppo_core_steps_per_second"),
        "env_steps_per_second": report.get("env_steps_per_second"),
        "update_share_of_wallclock": report.get("update_share_of_wallclock"),
        "sort_key": sort_key,
        "device_name": report.get("gpu_name"),
    }
    (args.out_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
