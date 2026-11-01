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

1. [test fixture: `test_env_uses_armed_candidate_after_per_bar_setup_disappears`](../../../../tests/unit/simulation/test_environment/test_entry_state_machine.py#L288)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        allow_agent_sl_mode=False,
        allow_ema_exit=False,
    )
    observation, _ = env.reset()
    assert observation["account"].shape == (10,)
    assert tuple(observation["account"][6:]) == entry_state_one_hot("FLAT")
    decoded_states: list[str] = []
    original_decode = env._decode_action

    def track_decoded_state(action: Any, feat_row: Any = None) -> tuple[int, float, float, str]:
        assert env.entry_state_machine is not None
# … caller assertions omitted …
```

2. [test fixture: `test_a3_shape_and_action_space_are_unchanged`](../../../../tests/unit/simulation/test_environment/test_entry_state_machine.py#L401)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    assert legacy.observation_space.spaces["account"].shape == (6,)
    assert hidden.observation_space.spaces["account"].shape == (6,)
    assert stateful.observation_space.spaces["account"].shape == (10,)
    raw_obs, _ = raw.reset()
    assert raw_obs["account"].shape == (10,)
    assert tuple(raw_obs["account"][6:]) == entry_state_one_hot("FLAT")
    assert legacy.action_space.shape == stateful.action_space.shape
    obs, _, _, _, info = legacy.step(np.zeros(5, dtype=np.float32))
    assert obs["account"].shape == (6,)
    assert "entry_state" not in info
    assert tuple(stateful.reset()[0]["account"][6:]) == entry_state_one_hot(ENTRY_STATES[0])
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`
