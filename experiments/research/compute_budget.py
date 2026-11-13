"""Semantic compute-budget construction for survival experiments."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class BudgetRow:
    """Semantic budget for one vector-environment shape."""

    n_envs: int
    minimum_aggregate_timesteps: int
    supplied_full_paths_per_env: float | None
    supplied_budget_is_semantically_sufficient: bool | None
    fps: float | None


def _full_path_equivalents(
    aggregate_timesteps: int,
    *,
    n_envs: int,
    decisions_per_full_path: int,
) -> float:
    """Convert aggregate environment steps to complete paths per environment.

    Args:
        aggregate_timesteps: Aggregate environment-step budget.
        n_envs: Number of parallel environments.
        decisions_per_full_path: Decision count in one complete chronological path.

    Returns:
        Result produced by _full_path_equivalents.
    """
    if aggregate_timesteps < 1 or n_envs < 1 or decisions_per_full_path < 1:
        raise ValueError("budget inputs must be positive")
    return aggregate_timesteps / float(n_envs * decisions_per_full_path)


def _budget_rows(
    *,
    decisions_per_full_path: int,
    n_envs_values: list[int],
    minimum_full_paths_per_env: float,
    supplied_total_timesteps: int | None,
    fps_by_n_envs: dict[int, float] | None,
) -> list[BudgetRow]:
    """Build semantic budget rows without depending on command-line scripts.

    Args:
        decisions_per_full_path: Decision count in one complete chronological path.
        n_envs_values: Candidate parallel-environment counts.
        minimum_full_paths_per_env: Required complete-path equivalents per environment.
        supplied_total_timesteps: Optional pre-existing aggregate step budget.
        fps_by_n_envs: Measured end-to-end throughput by environment count.

    Returns:
        Result produced by _budget_rows.
    """
    if len(set(n_envs_values)) != len(n_envs_values):
        raise ValueError("n_envs values must be unique")
    if decisions_per_full_path < 1 or minimum_full_paths_per_env <= 0.0:
        raise ValueError("semantic budget inputs must be positive")
    rows: list[BudgetRow] = []
    for n_envs in n_envs_values:
        if n_envs < 1:
            raise ValueError("n_envs values must be positive")
        minimum_steps = int(
            math.ceil(n_envs * decisions_per_full_path * minimum_full_paths_per_env)
        )
        supplied_paths = (
            None
            if supplied_total_timesteps is None
            else _full_path_equivalents(
                supplied_total_timesteps,
                n_envs=n_envs,
                decisions_per_full_path=decisions_per_full_path,
            )
        )
        fps = None if fps_by_n_envs is None else fps_by_n_envs.get(n_envs)
        if fps is not None and (not math.isfinite(fps) or fps <= 0.0):
            raise ValueError(f"FPS for n_envs={n_envs} must be finite and positive")
        rows.append(
            BudgetRow(
                n_envs=n_envs,
                minimum_aggregate_timesteps=minimum_steps,
                supplied_full_paths_per_env=supplied_paths,
                supplied_budget_is_semantically_sufficient=(
                    None
                    if supplied_paths is None
                    else supplied_paths + 1e-12 >= minimum_full_paths_per_env
                ),
                fps=fps,
            )
        )
    return rows


def _round_up(value: int, boundary: int) -> int:
    """Round a positive value up to an execution boundary.

    Args:
        value: Value to validate or transform.
        boundary: Execution boundary used for upward rounding.

    Returns:
        Result produced by _round_up.
    """
    if value <= 0 or boundary <= 0:
        raise ValueError("rollout rounding values must be positive")
    return int(math.ceil(value / boundary) * boundary)


def build_compute_budget(
    *,
    decisions_per_full_path: int,
    wf_decisions_per_full_path: list[int],
    n_envs_values: list[int],
    rollout_steps_per_env: int,
    batch_size: int,
    epochs: int,
    minimum_full_paths_per_env: float = 2.0,
    supplied_total_timesteps: int | None = None,
    fps_by_n_envs: dict[int, float] | None = None,
    seed_count: int = 6,
    wf_split_count: int = 5,
    allocation_hours: float = 12.0,
) -> dict[str, Any]:
    """Build the full-path-equivalent budget used to size expensive training.

    Args:
        decisions_per_full_path: Decision count in one complete chronological path.
        wf_decisions_per_full_path: Decision counts for each walk-forward split.
        n_envs_values: Candidate parallel-environment counts.
        rollout_steps_per_env: Rollout steps collected per environment.
        batch_size: Optimizer minibatch size.
        epochs: Optimizer epochs per rollout.
        minimum_full_paths_per_env: Required complete-path equivalents per environment.
        supplied_total_timesteps: Optional pre-existing aggregate step budget.
        fps_by_n_envs: Measured end-to-end throughput by environment count.
        seed_count: Number of independent training seeds.
        wf_split_count: Number of walk-forward splits.
        allocation_hours: Maximum allocation duration used for feasibility reporting.

    Returns:
        Result produced by build_compute_budget.
    """
    if len(wf_decisions_per_full_path) != wf_split_count:
        raise ValueError("one walk-forward decision count is required per split")
    if any(value <= 0 for value in wf_decisions_per_full_path):
        raise ValueError("walk-forward decision counts must be positive")
    raw_rows = _budget_rows(
        decisions_per_full_path=decisions_per_full_path,
        n_envs_values=n_envs_values,
        minimum_full_paths_per_env=minimum_full_paths_per_env,
        supplied_total_timesteps=supplied_total_timesteps,
        fps_by_n_envs=fps_by_n_envs,
    )
    rows: list[dict[str, Any]] = []
    for row in raw_rows:
        rollout_boundary = int(row.n_envs * rollout_steps_per_env)
        rounded_main = _round_up(row.minimum_aggregate_timesteps, rollout_boundary)
        wf_rows: list[dict[str, Any]] = []
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
        all_seed_steps = seed_count * (rounded_main + wf_total)
        estimated_seconds = None if row.fps is None else all_seed_steps / row.fps
        rows.append(
            {
                "n_envs": row.n_envs,
                "rollout_steps_per_env": rollout_steps_per_env,
                "aggregate_rollout_size": rollout_boundary,
                "batch_size": batch_size,
                "minibatches_per_epoch": math.ceil(rollout_boundary / batch_size),
                "epochs": epochs,
                "main_rounded_aggregate_timesteps": rounded_main,
                "main_full_paths_per_env": rounded_main
                / float(row.n_envs * decisions_per_full_path),
                "walk_forward": wf_rows,
                "all_seed_main_plus_wf_steps": all_seed_steps,
                "measured_end_to_end_fps": row.fps,
                "estimated_main_plus_wf_wall_seconds": estimated_seconds,
                "fits_one_allocation": (
                    None
                    if estimated_seconds is None
                    else estimated_seconds <= allocation_hours * 3600.0
                ),
                "supplied_total_timesteps": supplied_total_timesteps,
                "supplied_full_paths_per_env": row.supplied_full_paths_per_env,
                "supplied_budget_is_semantically_sufficient": row.supplied_budget_is_semantically_sufficient,
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
        "schema_version": 1,
        "comparison_unit": "full_path_equivalents_per_environment",
        "minimum_full_paths_per_env": minimum_full_paths_per_env,
        "seed_count": seed_count,
        "walk_forward_split_count": wf_split_count,
        "allocation_hours": allocation_hours,
        "recommended_n_envs": recommendation,
        "default_n_envs_if_unmeasured": 8,
        "raw_fps_is_not_semantic_budget": True,
        "rows": rows,
    }


__all__ = ["build_compute_budget"]
