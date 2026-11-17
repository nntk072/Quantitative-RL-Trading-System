#!/usr/bin/env python3
"""Plan terminal-survival PPO budgets in full-path equivalents, not raw FPS."""

from __future__ import annotations

import argparse
import json
import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BudgetRow:
    n_envs: int
    decisions_per_full_path: int
    minimum_full_paths_per_env: float
    minimum_aggregate_timesteps: int
    supplied_aggregate_timesteps: int | None
    supplied_full_paths_per_env: float | None
    supplied_budget_is_semantically_sufficient: bool | None
    fps: float | None
    estimated_wall_seconds_for_minimum: float | None


def full_path_equivalents_per_env(
    aggregate_timesteps: int,
    *,
    n_envs: int,
    decisions_per_full_path: int,
) -> float:
    """Convert SB3 aggregate steps into terminal-signal paths per environment."""
    for name, value in (
        ("aggregate_timesteps", aggregate_timesteps),
        ("n_envs", n_envs),
        ("decisions_per_full_path", decisions_per_full_path),
    ):
        if isinstance(value, bool) or int(value) < 1:
            raise ValueError(f"{name} must be a positive integer")
    return float(aggregate_timesteps) / float(n_envs * decisions_per_full_path)


def minimum_aggregate_timesteps(
    *,
    n_envs: int,
    decisions_per_full_path: int,
    minimum_full_paths_per_env: float,
) -> int:
    """Return the aggregate step budget required for a terminal-signal path target."""
    if isinstance(n_envs, bool) or n_envs < 1:
        raise ValueError("n_envs must be a positive integer")
    if isinstance(decisions_per_full_path, bool) or decisions_per_full_path < 1:
        raise ValueError("decisions_per_full_path must be a positive integer")
    if not math.isfinite(minimum_full_paths_per_env) or minimum_full_paths_per_env <= 0.0:
        raise ValueError("minimum_full_paths_per_env must be finite and positive")
    return int(math.ceil(n_envs * decisions_per_full_path * minimum_full_paths_per_env))


def build_budget_table(
    *,
    decisions_per_full_path: int,
    n_envs_values: Sequence[int],
    minimum_full_paths_per_env: float = 2.0,
    supplied_aggregate_timesteps: int | None = None,
    fps_by_n_envs: dict[int, float] | None = None,
) -> list[BudgetRow]:
    """Build semantically matched budgets for candidate vector-environment shapes."""
    if len(set(map(int, n_envs_values))) != len(n_envs_values):
        raise ValueError("n_envs values must be unique")
    rows: list[BudgetRow] = []
    for raw_n_envs in n_envs_values:
        n_envs = int(raw_n_envs)
        minimum_steps = minimum_aggregate_timesteps(
            n_envs=n_envs,
            decisions_per_full_path=decisions_per_full_path,
            minimum_full_paths_per_env=minimum_full_paths_per_env,
        )
        supplied_paths = (
            None
            if supplied_aggregate_timesteps is None
            else full_path_equivalents_per_env(
                supplied_aggregate_timesteps,
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
                decisions_per_full_path=int(decisions_per_full_path),
                minimum_full_paths_per_env=float(minimum_full_paths_per_env),
                minimum_aggregate_timesteps=minimum_steps,
                supplied_aggregate_timesteps=supplied_aggregate_timesteps,
                supplied_full_paths_per_env=supplied_paths,
                supplied_budget_is_semantically_sufficient=(
                    None
                    if supplied_paths is None
                    else supplied_paths + 1e-12 >= minimum_full_paths_per_env
                ),
                fps=fps,
                estimated_wall_seconds_for_minimum=(None if fps is None else minimum_steps / fps),
            )
        )
    return rows


def _parse_fps(values: Sequence[str]) -> dict[int, float]:
    result: dict[int, float] = {}
    for value in values:
        left, separator, right = value.partition("=")
        if not separator:
            raise ValueError("--fps entries must use N_ENVS=FPS")
        n_envs = int(left)
        if n_envs in result:
            raise ValueError(f"duplicate FPS entry for n_envs={n_envs}")
        result[n_envs] = float(right)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decisions-per-full-path", type=int, required=True)
    parser.add_argument("--n-envs", type=int, nargs="+", default=[1, 8, 16, 32, 64])
    parser.add_argument("--minimum-full-paths-per-env", type=float, default=2.0)
    parser.add_argument("--aggregate-timesteps", type=int, default=None)
    parser.add_argument(
        "--fps",
        action="append",
        default=[],
        metavar="N_ENVS=FPS",
        help="optional measured end-to-end throughput; repeat for each shape",
    )
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    rows = build_budget_table(
        decisions_per_full_path=args.decisions_per_full_path,
        n_envs_values=args.n_envs,
        minimum_full_paths_per_env=args.minimum_full_paths_per_env,
        supplied_aggregate_timesteps=args.aggregate_timesteps,
        fps_by_n_envs=_parse_fps(args.fps) if args.fps else None,
    )
    payload: dict[str, Any] = {
        "schema_version": "survival-full-path-budget-v1",
        "budget_semantics": (
            "SB3 total_timesteps is aggregate across environments; terminal survival reward "
            "must be budgeted by complete path equivalents per environment"
        ),
        "rows": [asdict(row) for row in rows],
    }
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
