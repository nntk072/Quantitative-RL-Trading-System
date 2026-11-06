# Evaluation · `rollout.baseline_signal_actions`

This page contains 1 public callable records owned by `evaluation.rollout.baseline_signal_actions`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `discrete_actions_for_position_targets`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.rollout.baseline_signal_actions`

**Purpose:** Convert ``-1/0/+1`` targets to the discrete trading action contract.

**Exact API:** {py:obj}`evaluation.rollout.baseline_signal_actions.discrete_actions_for_position_targets` · **Source:** [evaluation/rollout/baseline_signal_actions.py:11](../../../../evaluation/rollout/baseline_signal_actions.py#L11)

**Inputs and outputs:**

- **Args:**

  ```text
  targets: Causal position targets aligned to the evaluated bars.
  ```

- **Returns:**

  ```text
  Discrete actions aligned to ``targets.index``.
  ```

- **Raises:**

  ```text
  TypeError: If ``targets`` is not a pandas Series.
  ValueError: If values are empty, non-finite, or outside ``{-1, 0, 1}``.
  ```

**Observed usage:**

1. [test fixture: `test_position_targets_emit_explicit_holds_exits_and_delayed_reversals`](../../../../tests/unit/evaluation/test_baseline_signal_actions.py#L17)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_position_targets_emit_explicit_holds_exits_and_delayed_reversals() -> None:
    index = pd.RangeIndex(9)
    targets = pd.Series([0, 1, 1, 0, -1, -1, 1, 1, 0], index=index)

    actions = discrete_actions_for_position_targets(targets)

    schema = build_discrete_trading_action_schema()
    long_action = schema.names.index("enter_long_risk_high_rr_low")
    short_action = schema.names.index("enter_short_risk_high_rr_low")
    exit_action = schema.names.index("exit")
# … caller assertions omitted …
```

2. [test fixture: `test_position_target_converter_rejects_invalid_values`](../../../../tests/unit/evaluation/test_baseline_signal_actions.py#L47)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_position_target_converter_rejects_invalid_values(targets: pd.Series) -> None:
    with pytest.raises(ValueError):
        discrete_actions_for_position_targets(targets)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`
