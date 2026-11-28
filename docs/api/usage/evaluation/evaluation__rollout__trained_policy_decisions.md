# Evaluation · `rollout.trained_policy_decisions`

This page contains 1 public callable records owned by `evaluation.rollout.trained_policy_decisions`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `make_action_fn`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.rollout.trained_policy_decisions`

**Purpose:** Return an observation → action callable with explicit action typing.

**Exact API:** {py:obj}`evaluation.rollout.trained_policy_decisions.make_action_fn` · **Source:** [evaluation/rollout/trained_policy_decisions.py:256](../../../../evaluation/rollout/trained_policy_decisions.py#L256)

**Inputs and outputs:**

- **Args:**

  ```text
  model: Model used for this operation.
  continuous_actions: Whether to enable or require the continuous actions.
  deterministic: Whether to enable or require the deterministic.
  strategy_actions: Whether to enable or require the strategy actions.
  decision_callback: Optional receiver for each typed provider result.
  ```

- **Returns:**

  ```text
  Result of return an observation → action callable with explicit action typing.
  ```

**Observed usage:**

1. [production caller: `evaluate_model`](../../../../evaluation/rollout/trained_policy_rollout.py#L453)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    else:
        obs, _ = env.reset(seed=execution_seed)
    done = False
    truncated = False
    decision_results: list[Any] = []
    action_fn = make_action_fn(
        model,
        continuous_actions,
        deterministic,
        strategy_actions=strategy_actions,
        decision_callback=decision_results.append,
    )
    action_counts: Counter[str] = Counter()
    trade_setup_decision_rows: list[dict[str, Any]] = []
    policy_decision_rows: list[dict[str, Any]] = []
    account_state_rows: list[dict[str, Any]] = []
    account_state_trace_complete = True
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`
