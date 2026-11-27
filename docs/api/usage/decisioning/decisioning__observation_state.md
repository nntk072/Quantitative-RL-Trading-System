# Decisioning · `observation_state`

This page contains 1 public callable records owned by `decisioning.observation_state`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `entry_state_one_hot`

**Kind:** function · **Status:** stable · **Owner:** `decisioning.observation_state`

**Purpose:** Encode the entry lifecycle state using the stable observation order.

**Exact API:** {py:obj}`decisioning.observation_state.entry_state_one_hot` · **Source:** [decisioning/observation_state.py:13](../../../../decisioning/observation_state.py#L13)

**Inputs and outputs:**

- **Args:**

  ```text
  state: State object read or updated by the operation.
  ```

- **Returns:**

  ```text
  Values returned by ``entry_state_one_hot``, in the declared order.
  ```

**Observed usage:**

1. [test fixture: `test_scalar_backtest_entry_state_tracks_causal_candidate_and_arming`](../../../../tests/integration/backtest/test_setup_mask_backtest_boundary.py#L927)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    )

    states = [
        tuple(int(value) for value in observation["account"][6:]) for observation in observations
    ]
    assert entry_state_one_hot("FLAT") in states
    assert entry_state_one_hot("CANDIDATE") in states
    assert entry_state_one_hot("ARMED") in states
    assert result["entry_state_diagnostics"]["candidate_created"] == 1
    assert result["entry_state_diagnostics"]["entered"] == 0
```

2. [test fixture: `test_entry_state_one_hot_rejects_unknown_lifecycle_state`](../../../../tests/unit/decisioning/test_observations.py#L149)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_entry_state_one_hot_rejects_unknown_lifecycle_state() -> None:
    with pytest.raises(ValueError, match="unknown entry state"):
        entry_state_one_hot("CLOSED")
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`
