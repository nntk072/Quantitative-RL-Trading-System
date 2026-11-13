# Experiments · `research.compute_budget`

This page contains 1 public callable records owned by `experiments.research.compute_budget`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `build_compute_budget`

**Kind:** function · **Status:** experimental · **Owner:** `experiments.research.compute_budget`

**Purpose:** Build the full-path-equivalent budget used to size expensive training.

**Exact API:** {py:obj}`experiments.research.compute_budget.build_compute_budget` · **Source:** [experiments/research/compute_budget.py:116](../../../../experiments/research/compute_budget.py#L116)

**Inputs and outputs:**

- **Args:**

  ```text
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
  ```

- **Returns:**

  ```text
  Result produced by build_compute_budget.
  ```

**Observed usage:**

1. [production caller: `main`](../../../../experiments/research/cli.py#L374)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        for raw in args.fps:
            left, separator, right = raw.partition("=")
            if not separator:
                raise ValueError("--fps entries require N_ENVS=FPS")
            fps[int(left)] = float(right)
        result = build_compute_budget(
            decisions_per_full_path=args.decisions_per_full_path,
            wf_decisions_per_full_path=args.wf_decisions_per_full_path,
            n_envs_values=args.n_envs,
            rollout_steps_per_env=args.rollout_steps_per_env,
            batch_size=args.batch_size,
            epochs=args.epochs,
            supplied_total_timesteps=args.supplied_total_timesteps,
            fps_by_n_envs=fps or None,
        )
        from artifacts.atomic import write_json_atomic

        args.output.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomic(args.output, result)
        print(json.dumps(result, indent=2, sort_keys=True))
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`
