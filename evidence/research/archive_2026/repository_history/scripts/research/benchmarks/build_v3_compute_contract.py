#!/usr/bin/env python3
"""Freeze the V3 full-path, PPO-geometry, WF-budget, and wall-time contract."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from scripts.research.benchmarks.plan_survival_compute_budget import (
    build_budget_table,
)

from artifacts.atomic import write_json_atomic


def _round_up(value: int, boundary: int) -> int:
    if value <= 0 or boundary <= 0:
        raise ValueError("rollout rounding values must be positive")
    return int(math.ceil(value / boundary) * boundary)


def _fps_map(values: list[str]) -> dict[int, float]:
    result: dict[int, float] = {}
    for raw in values:
        left, sep, right = raw.partition("=")
        if not sep:
            raise ValueError("--fps entries require N_ENVS=FPS")
        n_envs, fps = int(left), float(right)
        if n_envs in result or n_envs <= 0 or not math.isfinite(fps) or fps <= 0.0:
            raise ValueError(f"invalid FPS entry: {raw}")
        result[n_envs] = fps
    return result


def build_compute_contract(
    *,
    decisions_per_full_path: int,
    wf_decisions_per_full_path: list[int],
    n_envs_values: list[int],
    rollout_steps_per_env: int,
    batch_size: int,
    epochs: int,
    minimum_full_paths_per_env: float,
    supplied_total_timesteps: int | None,
    fps_by_n_envs: dict[int, float],
    seed_count: int,
    wf_split_count: int,
    allocation_hours: float,
) -> dict[str, Any]:
    """Build one prospective semantic compute contract."""
    for name, value in (
        ("decisions_per_full_path", decisions_per_full_path),
        ("rollout_steps_per_env", rollout_steps_per_env),
        ("batch_size", batch_size),
        ("epochs", epochs),
        ("seed_count", seed_count),
        ("wf_split_count", wf_split_count),
    ):
        if isinstance(value, bool) or value <= 0:
            raise ValueError(f"{name} must be positive")
    if len(wf_decisions_per_full_path) != wf_split_count:
        raise ValueError("one WF decision count is required per split")
    if any(value <= 0 for value in wf_decisions_per_full_path):
        raise ValueError("WF decision counts must be positive")

    raw_rows = build_budget_table(
        decisions_per_full_path=decisions_per_full_path,
        n_envs_values=n_envs_values,
        minimum_full_paths_per_env=minimum_full_paths_per_env,
        supplied_aggregate_timesteps=supplied_total_timesteps,
        fps_by_n_envs=fps_by_n_envs or None,
    )
    rows: list[dict[str, Any]] = []
    for row in raw_rows:
        rollout_boundary = int(row.n_envs * rollout_steps_per_env)
        rounded_main_steps = _round_up(row.minimum_aggregate_timesteps, rollout_boundary)
        wf_rows = []
        wf_total = 0
        for split, decisions in enumerate(wf_decisions_per_full_path, start=1):
            minimum = math.ceil(row.n_envs * decisions * minimum_full_paths_per_env)
            rounded = _round_up(int(minimum), rollout_boundary)
            wf_total += rounded
            wf_rows.append(
                {
                    "split": split,
                    "decisions_per_full_path": decisions,
                    "minimum_aggregate_timesteps": int(minimum),
                    "rounded_aggregate_timesteps": rounded,
                    "full_paths_per_env": rounded / float(row.n_envs * decisions),
                }
            )
        fps = row.fps
        per_seed_steps = rounded_main_steps + wf_total
        all_seed_steps = seed_count * per_seed_steps
        estimated_seconds = None if fps is None else all_seed_steps / fps
        rows.append(
            {
                "n_envs": row.n_envs,
                "rollout_steps_per_env": rollout_steps_per_env,
                "aggregate_rollout_size": rollout_boundary,
                "batch_size": batch_size,
                "minibatches_per_epoch": math.ceil(rollout_boundary / batch_size),
                "epochs": epochs,
                "decisions_per_main_full_path": decisions_per_full_path,
                "minimum_full_paths_per_env": minimum_full_paths_per_env,
                "main_minimum_aggregate_timesteps": row.minimum_aggregate_timesteps,
                "main_rounded_aggregate_timesteps": rounded_main_steps,
                "main_full_paths_per_env": rounded_main_steps
                / float(row.n_envs * decisions_per_full_path),
                "supplied_total_timesteps": supplied_total_timesteps,
                "supplied_full_paths_per_env": row.supplied_full_paths_per_env,
                "supplied_budget_is_semantically_sufficient": (
                    row.supplied_budget_is_semantically_sufficient
                ),
                "walk_forward": wf_rows,
                "per_seed_main_plus_wf_steps": per_seed_steps,
                "all_seed_main_plus_wf_steps": all_seed_steps,
                "measured_end_to_end_fps": fps,
                "estimated_main_plus_wf_wall_seconds": estimated_seconds,
                "fits_one_allocation": (
                    None
                    if estimated_seconds is None
                    else estimated_seconds <= allocation_hours * 3600.0
                ),
            }
        )

    measured = [
        row
        for row in rows
        if row["measured_end_to_end_fps"] is not None
        and row["main_full_paths_per_env"] + 1e-12 >= minimum_full_paths_per_env
    ]
    recommendation = (
        min(measured, key=lambda row: row["estimated_main_plus_wf_wall_seconds"])["n_envs"]
        if measured
        else 8
    )
    return {
        "schema_version": "v3-semantic-compute-contract-v1",
        "decision_count_current_source_required": True,
        "minimum_full_paths_per_env": minimum_full_paths_per_env,
        "seed_count": seed_count,
        "walk_forward_split_count": wf_split_count,
        "allocation_hours": allocation_hours,
        "recommended_n_envs": recommendation,
        "default_to_eight_if_uncertain": True,
        "raw_fps_is_not_semantic_budget": True,
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decisions-per-full-path", type=int, required=True)
    parser.add_argument("--wf-decisions-per-full-path", type=int, nargs="+", required=True)
    parser.add_argument("--n-envs", type=int, nargs="+", default=[8, 16, 32, 64])
    parser.add_argument("--rollout-steps-per-env", type=int, required=True)
    parser.add_argument("--batch-size", type=int, required=True)
    parser.add_argument("--epochs", type=int, required=True)
    parser.add_argument("--minimum-full-paths-per-env", type=float, default=2.0)
    parser.add_argument("--supplied-total-timesteps", type=int)
    parser.add_argument("--fps", action="append", default=[])
    parser.add_argument("--seed-count", type=int, default=6)
    parser.add_argument("--wf-split-count", type=int, default=5)
    parser.add_argument("--allocation-hours", type=float, default=12.0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = build_compute_contract(
        decisions_per_full_path=args.decisions_per_full_path,
        wf_decisions_per_full_path=args.wf_decisions_per_full_path,
        n_envs_values=args.n_envs,
        rollout_steps_per_env=args.rollout_steps_per_env,
        batch_size=args.batch_size,
        epochs=args.epochs,
        minimum_full_paths_per_env=args.minimum_full_paths_per_env,
        supplied_total_timesteps=args.supplied_total_timesteps,
        fps_by_n_envs=_fps_map(args.fps),
        seed_count=args.seed_count,
        wf_split_count=args.wf_split_count,
        allocation_hours=args.allocation_hours,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(args.output, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
