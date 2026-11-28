# Simulation · `environment.diagnostics.errors`

This page contains 6 public callable records owned by `simulation.environment.diagnostics.errors`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `DebugStepError`

**Kind:** class · **Status:** stable · **Owner:** `simulation.environment.diagnostics.errors`

**Purpose:** A step failure carrying the action, reward parts, and position.

**Exact API:** {py:obj}`simulation.environment.diagnostics.errors.DebugStepError` · **Source:** [simulation/environment/diagnostics/errors.py:18](../../../../simulation/environment/diagnostics/errors.py#L18)

**Observed usage:**

1. [production caller: `note_debug_step`](../../../../simulation/environment/diagnostics/errors.py#L96)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
    if not math.isfinite(float(reward)):
        raise DebugStepError(
            "non-finite reward",
            {
                "action": jsonable(action),
                "reward": None if not math.isfinite(float(reward)) else float(reward),
                "reward_parts": jsonable(dict(reward_parts)),
                "position": bool(position),
                "position_direction": int(position_direction),
            },
        )
    window["n"] += 1
    for key, value in reward_parts.items():
        window["parts"][str(key)] = float(window["parts"].get(str(key), 0.0)) + float(value)
    shaped = float(reward_parts.get("strategy", 0.0))
    if opened:
# … caller assertions omitted …
```

2. [production caller: `transition`](../../../../simulation/environment/env.py#L507)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            return self._step_untraced(action)
        except DebugStepError:
            raise
        except Exception as exc:
            position = self.position
            raise DebugStepError(
                "exception",
                {
                    "action": action.tolist() if isinstance(action, np.ndarray) else action,
                    "reward": None,
                    "reward_parts": {},
                    "position": position is not None,
                    "position_direction": 0 if position is None else int(position.direction),
                },
                exc,
            ) from exc
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `jsonable`

**Kind:** function · **Status:** stable · **Owner:** `simulation.environment.diagnostics.errors`

**Purpose:** Convert nested NumPy values into finite JSON-compatible values.

**Exact API:** {py:obj}`simulation.environment.diagnostics.errors.jsonable` · **Source:** [simulation/environment/diagnostics/errors.py:224](../../../../simulation/environment/diagnostics/errors.py#L224)

**Inputs and outputs:**

- **Args:**

  ```text
  value: Value to process.
  ```

- **Returns:**

  ```text
  Result of convert nested NumPy values into finite JSON-compatible values.
  ```

**Observed usage:**

1. [test fixture: `test_jsonable_converts_nested_numpy_values_and_non_finite_numbers`](../../../../tests/unit/simulation/test_environment/test_diagnostics_coverage.py#L129)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_jsonable_converts_nested_numpy_values_and_non_finite_numbers() -> None:
    result = jsonable(
        {
            np.int64(4): (np.asarray([1, np.nan]), [np.float32(np.inf), float("-inf")]),
            "integer": np.int32(7),
        }
    )

    assert result == {"4": [[1.0, None], [None, None]], "integer": 7}
```

2. [production caller: `note_debug_step`](../../../../simulation/environment/diagnostics/errors.py#L99)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
    if not math.isfinite(float(reward)):
        raise DebugStepError(
            "non-finite reward",
            {
                "action": jsonable(action),
                "reward": None if not math.isfinite(float(reward)) else float(reward),
                "reward_parts": jsonable(dict(reward_parts)),
                "position": bool(position),
                "position_direction": int(position_direction),
            },
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `new_debug_window`

**Kind:** function · **Status:** stable · **Owner:** `simulation.environment.diagnostics.errors`

**Purpose:** Empty per-env counters for one rollout.

**Exact API:** {py:obj}`simulation.environment.diagnostics.errors.new_debug_window` · **Source:** [simulation/environment/diagnostics/errors.py:40](../../../../simulation/environment/diagnostics/errors.py#L40)

**Inputs and outputs:**

- **Returns:**

  ```text
  Mapping from ``str`` keys to ``Any`` values.
  ```

**Observed usage:**

1. [test fixture: `test_window_summary_tracks_reward_parts_and_step_events`](../../../../tests/unit/simulation/test_environment/test_diagnostics_coverage.py#L48)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_window_summary_tracks_reward_parts_and_step_events() -> None:
    window = new_debug_window()
    _note(
        window,
        reward=1.0,
        reward_parts={"strategy": 0.5, "soft_daily": -0.1},
        opened=True,
# … caller assertions omitted …
```

2. [test fixture: `test_non_finite_reward_raises_snapshot_without_mutating_window`](../../../../tests/unit/simulation/test_environment/test_diagnostics_coverage.py#L101)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_non_finite_reward_raises_snapshot_without_mutating_window(reward: float) -> None:
    window = new_debug_window()
    snapshot_action = {np.int64(2): (np.float32(0.5), np.float64(np.inf))}

    with pytest.raises(DebugStepError, match="non-finite reward") as caught:
        note_debug_step(
            window,
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `note_debug_step`

**Kind:** function · **Status:** stable · **Owner:** `simulation.environment.diagnostics.errors`

**Purpose:** Update counters. A non-finite reward raises :class:`DebugStepError`.

**Exact API:** {py:obj}`simulation.environment.diagnostics.errors.note_debug_step` · **Source:** [simulation/environment/diagnostics/errors.py:68](../../../../simulation/environment/diagnostics/errors.py#L68)

**Inputs and outputs:**

- **Args:**

  ```text
  window: Key-value data used for the window.
  reward: Numeric value used for the reward.
  reward_parts: Key-value data used for the reward parts.
  opened: Whether to enable or require the opened.
  entered: Whether to enable or require the entered.
  risk_frac: Numeric value used for the risk frac.
  close_reason: Text or path value identifying the close reason.
  action: Action to apply to the current state.
  position: Whether to enable or require the position.
  position_direction: Numeric value used for the position direction.
  ```

**Observed usage:**

1. [test fixture: `_note`](../../../../tests/unit/simulation/test_environment/test_diagnostics_coverage.py#L33)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    opened: bool = False,
    entered: bool = False,
    risk_frac: float = 0.0,
    close_reason: str = "",
) -> None:
    note_debug_step(
        window,
        reward=reward,
        reward_parts=reward_parts,
        opened=opened,
        entered=entered,
        risk_frac=risk_frac,
        close_reason=close_reason,
        action=np.asarray([1, 0.25]),
        position=opened,
        position_direction=1 if opened else 0,
    )
```

2. [test fixture: `test_non_finite_reward_raises_snapshot_without_mutating_window`](../../../../tests/unit/simulation/test_environment/test_diagnostics_coverage.py#L105)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_non_finite_reward_raises_snapshot_without_mutating_window(reward: float) -> None:
    window = new_debug_window()
    snapshot_action = {np.int64(2): (np.float32(0.5), np.float64(np.inf))}

    with pytest.raises(DebugStepError, match="non-finite reward") as caught:
        note_debug_step(
            window,
            reward=reward,
            reward_parts={"pnl": 3.0},
            opened=True,
            entered=True,
            risk_frac=0.02,
            close_reason="structure_sl",
            action=snapshot_action,
            position=True,
            position_direction=1,
        )

    assert caught.value.snapshot == {
        "action": {"2": [0.5, None]},
        "reward": None,
        "reward_parts": {"pnl": 3.0},
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `summarize_window`

**Kind:** function · **Status:** stable · **Owner:** `simulation.environment.diagnostics.errors`

**Purpose:** Turn one env window into a JSON-ready summary.

**Exact API:** {py:obj}`simulation.environment.diagnostics.errors.summarize_window` · **Source:** [simulation/environment/diagnostics/errors.py:142](../../../../simulation/environment/diagnostics/errors.py#L142)

**Inputs and outputs:**

- **Args:**

  ```text
  window: Key-value data used for the window.
  ```

- **Returns:**

  ```text
  Mapping from ``str`` keys to ``Any`` values.
  ```

**Observed usage:**

1. [test fixture: `test_window_summary_tracks_reward_parts_and_step_events`](../../../../tests/unit/simulation/test_environment/test_diagnostics_coverage.py#L73)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        reward=-1.0,
        reward_parts={"breach": -1.0, "soft_year": -0.1},
        close_reason="other",
    )

    summary = summarize_window(window)

    assert summary["n"] == 3
    assert summary["parts"] == {
        "strategy": 0.7,
        "soft_daily": -0.2,
# … caller assertions omitted …
```

2. [test fixture: `test_non_finite_reward_raises_snapshot_without_mutating_window`](../../../../tests/unit/simulation/test_environment/test_diagnostics_coverage.py#L125)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        "reward": None,
        "reward_parts": {"pnl": 3.0},
        "position": True,
        "position_direction": 1,
    }
    assert summarize_window(window) == summarize_window(new_debug_window())
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `wiring_from_env`

**Kind:** function · **Status:** stable · **Owner:** `simulation.environment.diagnostics.errors`

**Purpose:** Reward and risk settings the train env was built with.

**Exact API:** {py:obj}`simulation.environment.diagnostics.errors.wiring_from_env` · **Source:** [simulation/environment/diagnostics/errors.py:175](../../../../simulation/environment/diagnostics/errors.py#L175)

**Inputs and outputs:**

- **Args:**

  ```text
  env: Environment whose state is read or updated.
  ```

- **Returns:**

  ```text
  Mapping from ``str`` keys to ``Any`` values.
  ```

**Observed usage:**

1. [test fixture: `test_wiring_from_env_uses_pnl_reward_and_composite_base_settings`](../../../../tests/unit/simulation/test_environment/test_diagnostics_coverage.py#L148)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        reward_mode="pnl",
        episodic=True,
        risk_floor=0.01,
        risk_frac_range=(0.01, 0.05),
    )
    pnl_wiring = wiring_from_env(pnl_env)
    assert pnl_wiring == {
        "reward_mode": "pnl",
        "episodic": True,
        "breach_penalty": -3.0,
        "eval_breach_penalty": -10.0,
# … caller assertions omitted …
```

2. [production caller: `debug_wiring`](../../../../simulation/environment/diagnostics/runtime.py#L52)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def debug_wiring(self) -> dict[str, Any]:
    return wiring_from_env(self)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`
