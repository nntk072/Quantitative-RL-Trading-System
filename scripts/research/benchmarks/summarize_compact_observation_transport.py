"""Summarize matched stock versus compact-observation PPO-core repeats."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any, cast


def _load_case(directory: Path, mode: str, seed: int) -> dict[str, Any]:
    path = directory / f"{mode}-seed{seed}.json"
    if not path.is_file():
        raise FileNotFoundError(f"missing benchmark case: {path}")
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _mean_sd(values: list[float]) -> tuple[float, float]:
    return statistics.mean(values), statistics.stdev(values) if len(values) > 1 else 0.0


def summarize(directory: Path) -> str:
    seeds = (42, 43, 44)
    stock = {seed: _load_case(directory, "stock", seed) for seed in seeds}
    compact = {seed: _load_case(directory, "compact", seed) for seed in seeds}
    identity_fields = (
        "config_sha256",
        "bundle_manifest_sha256",
        "n_envs",
        "effective_ppo_n_steps_per_env",
        "batch_size",
        "ppo_epochs_completed",
        "actual_env_steps",
    )
    for seed in seeds:
        for field in identity_fields:
            if stock[seed].get(field) != compact[seed].get(field):
                raise ValueError(
                    f"paired seed {seed} differs on {field}: "
                    f"{stock[seed].get(field)!r} != {compact[seed].get(field)!r}"
                )
        if stock[seed].get("compact_observation_transport") is not False:
            raise ValueError(f"stock seed {seed} is not the stock transport arm")
        if compact[seed].get("compact_observation_transport") is not True:
            raise ValueError(f"compact seed {seed} is not the compact transport arm")

    stock_fps = [float(stock[seed]["measured_ppo_core_steps_per_second"]) for seed in seeds]
    compact_fps = [float(compact[seed]["measured_ppo_core_steps_per_second"]) for seed in seeds]
    speedups = [
        (
            compact[seed]["measured_ppo_core_steps_per_second"]
            / stock[seed]["measured_ppo_core_steps_per_second"]
            - 1.0
        )
        * 100.0
        for seed in seeds
    ]
    stock_mean, stock_sd = _mean_sd(stock_fps)
    compact_mean, compact_sd = _mean_sd(compact_fps)
    speedup_mean, speedup_sd = _mean_sd(speedups)
    stock_bytes = [int(stock[seed]["ipc_transport"]["recv_bytes"]) for seed in seeds]
    compact_bytes = [int(compact[seed]["ipc_transport"]["recv_bytes"]) for seed in seeds]
    reductions = [
        (
            1.0
            - compact[seed]["ipc_transport"]["recv_bytes"]
            / stock[seed]["ipc_transport"]["recv_bytes"]
        )
        * 100.0
        for seed in seeds
    ]
    stock_bytes_mean, stock_bytes_sd = _mean_sd([float(value) for value in stock_bytes])
    compact_bytes_mean, compact_bytes_sd = _mean_sd([float(value) for value in compact_bytes])
    reduction_mean, reduction_sd = _mean_sd(reductions)
    compact_validation = directory / "validation2.json"
    validation_ok = (
        compact_validation.is_file()
        and json.loads(compact_validation.read_text(encoding="utf-8")).get(
            "compact_market_validation"
        )
        is True
    )
    adoption_gate = speedup_mean >= 20.0 and all(value > 0.0 for value in speedups)

    lines = [
        "# Compact Observation Transport A/B",
        "",
        f"- Benchmark directory: `{directory}`",
        f"- Validation smoke with per-observation market hashes: {'PASS' if validation_ok else 'MISSING/FAIL'}",
        "- Paired seeds: 42, 43, 44; same frozen bundle, resolved config, and PPO geometry.",
        "- Throughput includes rollout collection and PPO updates; two rollout warmups are excluded.",
        "- Each timed run requested 81,920 transitions (two warmups plus three measured rollouts).",
        "- Compact transport sends the absolute source row and per-environment account vector; the parent reconstructs other fields from the same immutable bundle.",
        "",
        "## PPO-core throughput",
        "",
        "| Seed | Stock transitions/s | Compact transitions/s | Paired change |",
        "|---:|---:|---:|---:|",
    ]
    for seed, old, new, gain in zip(seeds, stock_fps, compact_fps, speedups, strict=True):
        lines.append(f"| {seed} | {old:.2f} | {new:.2f} | {gain:+.2f}% |")
    lines.extend(
        [
            f"| Mean ± sample SD | {stock_mean:.2f} ± {stock_sd:.2f} | {compact_mean:.2f} ± {compact_sd:.2f} | {speedup_mean:+.2f}% ± {speedup_sd:.2f} pp |",
            "",
            "## Parent receive-buffer bytes",
            "",
            "| Seed | Stock IPC bytes | Compact IPC bytes | Reduction |",
            "|---:|---:|---:|---:|",
        ]
    )
    for seed, old, new, gain in zip(seeds, stock_bytes, compact_bytes, reductions, strict=True):
        lines.append(f"| {seed} | {old:,} | {new:,} | {gain:.2f}% |")
    lines.extend(
        [
            f"| Mean ± sample SD | {stock_bytes_mean:,.0f} ± {stock_bytes_sd:,.0f} | {compact_bytes_mean:,.0f} ± {compact_bytes_sd:,.0f} | {reduction_mean:.2f}% ± {reduction_sd:.2f} pp |",
            "",
            "## Decision",
            "",
            f"- >=20% repeatable PPO-core speedup gate: {'PASS' if adoption_gate else 'NOT MET'}.",
            "- A reduction in IPC bytes alone does not justify integration; use the measured PPO-core result and correctness gate.",
            "- This prototype reconstructs observations from the same market bundle in the parent. It is not production training behavior and is not a GPU-native simulator.",
            "- Detailed IPC serialization CPU and device-link bandwidth are not measured by the parent receive-buffer counter.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    report = summarize(args.directory)
    if args.output is None:
        print(report)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
        print(args.output)


if __name__ == "__main__":
    main()
