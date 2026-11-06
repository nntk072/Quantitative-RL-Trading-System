# Training · `artifacts.aggregation`

This page contains 2 public callable records owned by `training.artifacts.aggregation`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `aggregate_seed_results`

**Kind:** function · **Status:** stable · **Owner:** `training.artifacts.aggregation`

**Purpose:** Aggregate per-seed results into a multi-seed training_log.json.

**Exact API:** {py:obj}`training.artifacts.aggregation.aggregate_seed_results` · **Source:** [training/artifacts/aggregation.py:73](../../../../training/artifacts/aggregation.py#L73)

**Inputs and outputs:**

- **Args:**

  ```text
  seed_results: Items supplied for the seed results, in input order.
  seed: Random seed used to make sampling reproducible.
  mvp: Whether to enable or require the mvp.
  algo: Text or path value identifying the algo.
  arch: Text or path value identifying the arch.
  reward: Text or path value identifying the reward.
  timesteps: Numeric value used for the timesteps.
  train_bars: Market bar or price data used for aggregate per-seed results into a multi-seed training_log.json.
  test_bars: Market bar or price data used for aggregate per-seed results into a multi-seed training_log.json.
  strategy: Strategy used to select or evaluate trades.
  strategy_actions: Whether to enable or require the strategy actions.
  cfg: Run configuration used by this operation.
  args: Parsed command-line arguments for this operation.
  run_dir: Text or path value identifying the run dir.
  ```

- **Returns:**

  ```text
  Mapping from ``str`` keys to ``Any`` values.
  ```

**Observed usage:**

1. [test fixture: `test_training_aggregation_requires_explicit_boolean_gate_passes`](../../../../tests/unit/training/test_train_rl_decomposition.py#L81)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        "train_activity_gate": {"ok": "false", "status": "INACTIVE", "n_trades": 0},
        "abort_reason": "",
        "model_num_timesteps": 10,
    }

    aggregated = aggregate_seed_results(
        seed_results=[result],
        seed=7,
        mvp=False,
        algo="ppo",
        arch="mlp",
        reward="survival",
        timesteps=10,
        train_bars=20,
        test_bars=10,
        strategy="baseline",
        strategy_actions=False,
        cfg=SimpleNamespace(env={}),
        args=SimpleNamespace(allow_locked_oos_for_selection=False),
        run_dir=Path("."),
    )

    assert aggregated["train_equity_ok"] is False
    assert aggregated["train_activity_ok_by_seed"] == {"7": False}
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/training/index`

## `save_seed_artifacts`

**Kind:** function · **Status:** stable · **Owner:** `training.artifacts.aggregation`

**Purpose:** Write per-seed artifacts for multi-seed mode.

**Exact API:** {py:obj}`training.artifacts.aggregation.save_seed_artifacts` · **Source:** [training/artifacts/aggregation.py:29](../../../../training/artifacts/aggregation.py#L29)

**Inputs and outputs:**

- **Args:**

  ```text
  seed_dir: Text or path value identifying the seed dir.
  seed: Random seed used to make sampling reproducible.
  cfg: Run configuration used by this operation.
  train_result: Key-value data used for the train result.
  test_result: Key-value data used for the test result.
  train_m: Train m used by the operation described above.
  test_m: Test m used by the operation described above.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = save_seed_artifacts(seed_dir=..., seed=..., cfg=..., train_result=..., test_result=..., train_m=..., test_m=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/training/index`
