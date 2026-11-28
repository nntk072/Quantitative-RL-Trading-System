"""Profile one bundle env's step under cProfile with random actions from the action space.

Systems evidence only: it times the environment's own step, not policy inference or the update.
Writes the step timing and the top functions by cumulative time as JSON.
"""

from __future__ import annotations

import argparse
import cProfile
import io
import json
import pstats
import time
from functools import partial
from pathlib import Path
from typing import Any

import numpy as np
from research_tools.learning.benchmarks.measure_ppo_throughput import (
    _json_default,
    _prepare_bundle,
)

from simulation.environment.spec import EnvSpec
from simulation.environment.worker import make_bundle_env
from training.setup.environments import _training_episodic


def _latency_percentiles_ms(samples_ns: np.ndarray[Any, Any]) -> dict[str, float | None]:
    """Summarize per-step latency samples in milliseconds."""
    if samples_ns.size == 0:
        return {"p50": None, "p95": None, "p99": None}
    p50, p95, p99 = np.percentile(samples_ns, [50, 95, 99]) / 1_000_000.0
    return {"p50": float(p50), "p95": float(p95), "p99": float(p99)}


def _profile(
    env: Any,
    steps: int,
    seed: int,
    *,
    capture_profile: bool = True,
) -> tuple[float, cProfile.Profile, list[int]]:
    """Step ``env`` and return wall time, optional cProfile stats, and latencies."""
    env.action_space.seed(seed)
    env.reset(seed=seed)
    profiler = cProfile.Profile()
    latency_samples_ns: list[int] = []
    started = time.perf_counter()
    if capture_profile:
        profiler.enable()
    for _ in range(steps):
        step_started_ns = time.perf_counter_ns()
        out = env.step(env.action_space.sample())
        latency_samples_ns.append(time.perf_counter_ns() - step_started_ns)
        if out[2] or (len(out) > 3 and out[3]):
            env.reset()
    if capture_profile:
        profiler.disable()
    wall = time.perf_counter() - started
    return wall, profiler, latency_samples_ns


def _time_subproc(spec: EnvSpec, n_envs: int, steps: int, seed: int) -> dict[str, float]:
    """Time vector steps through one worker process per env, with pre-sampled actions."""
    from stable_baselines3.common.vec_env import SubprocVecEnv

    vec = SubprocVecEnv(
        [partial(make_bundle_env, spec) for _ in range(n_envs)], start_method="forkserver"
    )
    try:
        vec.action_space.seed(seed)
        vec.reset()
        actions = np.stack([vec.action_space.sample() for _ in range(n_envs)])
        vec.step(actions)
        started = time.perf_counter()
        for _ in range(steps):
            vec.step(actions)
        wall = time.perf_counter() - started
    finally:
        vec.close()
    return {
        "workers": n_envs,
        "vec_steps": steps,
        "wall_seconds": wall,
        "mean_vec_step_ms": 1000.0 * wall / steps,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--bundle-dir", type=Path, required=True)
    parser.add_argument("--steps", type=int, default=5000)
    parser.add_argument("--top", type=int, default=40)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--vec-envs",
        type=int,
        default=0,
        help="Also time a SubprocVecEnv with this many workers (0 skips it).",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.steps < 1:
        raise SystemExit("--steps must be positive")

    cfg, bundle_path, algo, arch = _prepare_bundle(args.bundle_dir, None, args.config, None)
    cfg.env.data_source = "bundle"
    spec = EnvSpec.from_cfg(
        cfg,
        algo=algo,
        reward=str(cfg.env.get("reward_mode", "dsr")),
        arch=arch,
        bundle_dir=str(bundle_path),
        episodic=_training_episodic(cfg),
    )
    env = make_bundle_env(spec)
    # Warm the caches once so the profile measures steady-state stepping.
    _profile(env, min(200, args.steps), args.seed, capture_profile=False)
    wall, _, latency_samples_ns = _profile(env, args.steps, args.seed, capture_profile=False)
    _, profiler, _ = _profile(env, args.steps, args.seed, capture_profile=True)

    stream = io.StringIO()
    pstats.Stats(profiler, stream=stream).sort_stats("cumulative").print_stats(args.top)
    report = {
        "steps": args.steps,
        "wall_seconds": wall,
        "mean_step_ms": 1000.0 * wall / args.steps,
        "step_latency_ms": _latency_percentiles_ms(np.asarray(latency_samples_ns, dtype=np.int64)),
        "top_cumulative": stream.getvalue(),
    }
    if args.vec_envs > 0:
        report["vec"] = _time_subproc(spec, args.vec_envs, args.steps, args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, default=_json_default))
    print(json.dumps({k: v for k, v in report.items() if k != "top_cumulative"}, indent=2))


if __name__ == "__main__":
    main()
