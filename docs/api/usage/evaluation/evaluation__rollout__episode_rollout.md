# Evaluation · `rollout.episode_rollout`

This page contains 2 public callable records owned by `evaluation.rollout.episode_rollout`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `run_episode`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.rollout.episode_rollout`

**Purpose:** Run one full episode and return performance metrics.

**Exact API:** {py:obj}`evaluation.rollout.episode_rollout.run_episode` · **Source:** [evaluation/rollout/episode_rollout.py:26](../../../../evaluation/rollout/episode_rollout.py#L26)

**Inputs and outputs:**

- **Args:**

  ```text
  env: A gym-style environment (e.g. ``TradingEnv``) exposing
      ``reset()``, ``step()`` and, ideally, ``trade_log`` /
      ``breach_events`` lists.
  action_fn: Maps the observation to an action accepted by ``env``.
  max_steps: Safety cap on the number of environment steps.
  periods_per_year: Bars per year used to annualise ratios.
  ```

- **Returns:**

  ```text
  Metrics computed over the collected equity curve and trades.
  ```

**Observed usage:**

1. [test fixture: `test_evaluation_counts_two_fills_as_one_completed_position`](../../../../tests/integration/test_position_fill_accounting.py#L79)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            return {}, {}

        def step(self, action):
            return {}, 0.0, True, False, {"equity": 110.0}

    metrics = run_episode(Episode(), lambda _obs: 0)
    assert metrics.n_trades == 1
    assert metrics.win_rate == pytest.approx(1.0)
    assert metrics.expectancy == pytest.approx(10.0)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `run_episode`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.rollout.episode_rollout`

**Purpose:** Run one full episode and return performance metrics.

**Exact API:** {py:obj}`evaluation.rollout.episode_rollout.run_episode` · **Source:** [evaluation/rollout/episode_rollout.py:26](../../../../evaluation/rollout/episode_rollout.py#L26)

**Inputs and outputs:**

- **Args:**

  ```text
  env: A gym-style environment (e.g. ``TradingEnv``) exposing
      ``reset()``, ``step()`` and, ideally, ``trade_log`` /
      ``breach_events`` lists.
  action_fn: Maps the observation to an action accepted by ``env``.
  max_steps: Safety cap on the number of environment steps.
  periods_per_year: Bars per year used to annualise ratios.
  ```

- **Returns:**

  ```text
  Metrics computed over the collected equity curve and trades.
  ```

**Observed usage:**

1. [test fixture: `test_evaluation_counts_two_fills_as_one_completed_position`](../../../../tests/integration/test_position_fill_accounting.py#L79)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            return {}, {}

        def step(self, action):
            return {}, 0.0, True, False, {"equity": 110.0}

    metrics = run_episode(Episode(), lambda _obs: 0)
    assert metrics.n_trades == 1
    assert metrics.win_rate == pytest.approx(1.0)
    assert metrics.expectancy == pytest.approx(10.0)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`
