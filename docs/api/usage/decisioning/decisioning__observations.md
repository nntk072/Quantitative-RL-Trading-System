# Decisioning · `observations`

This page contains 6 public callable records owned by `decisioning.observations`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `ObservationSchema`

**Kind:** class · **Status:** stable · **Owner:** `decisioning.observations`

**Purpose:** Explicit coordinate names and version for the account branch.

**Exact API:** {py:obj}`decisioning.observations.ObservationSchema` · **Source:** [decisioning/observations.py:129](../../../../decisioning/observations.py#L129)

**Observed usage:**

1. [production caller: `build_observation_schema`](../../../../decisioning/observations.py#L182)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def build_observation_schema(
    version: str = OBSERVATION_SCHEMA_V1,
    *,
    entry_state_visibility: bool = False,
) -> ObservationSchema:
    coordinates: tuple[str, ...]
    if version == OBSERVATION_SCHEMA_V1:
        coordinates = V1_COORDINATES
    elif version in (OBSERVATION_SCHEMA_V2, OBSERVATION_SCHEMA_V3):
        coordinates = V2_COORDINATES
    else:
        raise ValueError(f"unknown observation schema version: {version!r}")
    if entry_state_visibility:
        coordinates = (*coordinates, *(f"entry_state_{name.lower()}" for name in ENTRY_STATES))
    return ObservationSchema(version, coordinates, entry_state_visibility)
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `build_observation_schema`

**Kind:** function · **Status:** stable · **Owner:** `decisioning.observations`

**Purpose:** Return a named schema; never infer semantics from a vector width.

**Exact API:** {py:obj}`decisioning.observations.build_observation_schema` · **Source:** [decisioning/observations.py:159](../../../../decisioning/observations.py#L159)

**Inputs and outputs:**

- **Args:**

  ```text
  version: Text or path value identifying the version.
  entry_state_visibility: Whether to enable or require the entry state visibility.
  ```

- **Returns:**

  ```text
  Result of return a named schema; never infer semantics from a vector width.
  ```

**Observed usage:**

1. [test fixture: `_StubModel`](../../../../tests/unit/features/test_stage_a_observation.py#L24)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
class _StubModel:
    _observation_schema = build_observation_schema(OBSERVATION_SCHEMA_V1).to_dict()
    _action_schema = build_discrete_trading_action_schema().to_dict()
    action_space: Any = spaces.Discrete(20)

    def predict(self, obs: dict[str, Any], deterministic: bool = True) -> np.ndarray[Any, Any]:  # noqa: ARG002
        return np.array([1])
```

2. [test fixture: `_StubModel`](../../../../tests/unit/live/test_rl_bridge.py#L164)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
class _StubModel:
    """Duck-typed SB3 model: action = +1 (long) always."""

    _observation_schema = build_observation_schema(OBSERVATION_SCHEMA_V1).to_dict()
    action_space: Any = spaces.Discrete(20)
    _action_schema: dict[str, object] = build_discrete_trading_action_schema().to_dict()

    def predict(self, obs: dict[str, Any], deterministic: bool = True) -> np.ndarray[Any, Any]:  # noqa: ARG002
        return np.array([1])
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `normalized_account_vector`

**Kind:** function · **Status:** stable · **Owner:** `decisioning.observations`

**Purpose:** Build the legacy normalized account input coordinates.

**Exact API:** {py:obj}`decisioning.observations.normalized_account_vector` · **Source:** [decisioning/observations.py:47](../../../../decisioning/observations.py#L47)

**Inputs and outputs:**

- **Args:**

  ```text
  equity: Current account equity in account currency.
  initial_balance: Numeric value used for the initial balance.
  pos_dir: Numeric value used for the pos dir.
  open_pnl: Numeric value used for the open pnl.
  dist_to_sl: Numeric value used for the dist to sl.
  trailing_dd: Numeric value used for the trailing dd.
  close: Numeric value used for the close.
  entry_state: Entry state used by the operation described above.
  ```

- **Returns:**

  ```text
  Array returned by ``normalized_account_vector``.
  ```

**Observed usage:**

1. [production caller: `build_observation`](../../../../live/runtime/strategy.py#L288)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
                tp_mode=str(st["tp_mode"]),
                exit_mode=str(st["exit_mode"]),
                entry_state=str(st["entry_state"]) if "entry_state" in st else None,
            )
        else:
            account = normalized_account_vector(
                equity=equity,
                initial_balance=self._initial_balance,
                pos_dir=pos_dir,
                open_pnl=open_pnl,
                dist_to_sl=dist_to_sl,
                trailing_dd=trailing_dd,
                close=close,
            )
        return {"seq": seq, "seq_mask": seq_mask, "account": account}
```

2. [production caller: `_get_observation`](../../../../simulation/environment/observation_runtime.py#L155)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            )
        elif self.normalize_account:
            # Rescale so the account vector matches the ~O(1) magnitude of
            # the z-scored seq features. Without this, equity (1e5) and
            # raw open_pnl dwarf the time-series signal.
            account_state = normalized_account_vector(
                equity=float(self.account.equity),
                initial_balance=float(self.initial_balance),
                pos_dir=pos_dir,
                open_pnl=open_pnl,
                dist_to_sl=dist_to_sl,
                trailing_dd=trailing_dd,
                close=current_close,
                entry_state=exposed_entry_state,
            )
        else:
            raw_account = [
                self.account.equity,
                pos_dir,
                open_pnl,
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `pad_observation_window`

**Kind:** function · **Status:** stable · **Owner:** `decisioning.observations`

**Purpose:** Left-pad a sequence window and mark which rows contain real events.

**Exact API:** {py:obj}`decisioning.observations.pad_observation_window` · **Source:** [decisioning/observations.py:17](../../../../decisioning/observations.py#L17)

**Inputs and outputs:**

- **Args:**

  ```text
  seq: Seq used by the operation described above.
  window: Numeric value used for the window.
  ```

- **Returns:**

  ```text
  Array returned by ``pad_observation_window``.
  ```

**Observed usage:**

1. [production caller: `build_observation`](../../../../live/runtime/strategy.py#L213)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        feats = select_obs_columns(self._features, self._raw_columns())
        if self._bars is not None:
            feats = attach_reachable_r(feats, self._bars, self._features)
        window = feats.iloc[-self.obs_window :]
        seq = np.nan_to_num(np.asarray(window.values, dtype=np.float32), nan=0.0)
        seq, seq_mask = pad_observation_window(seq, self.obs_window)

        st = account_state or {}
        equity = float(st.get("equity", self._initial_balance))
        pos_dir = float(st.get("position_direction", 0.0))
        open_pnl = float(st.get("open_pnl", 0.0))
# … caller assertions omitted …
```

2. [production caller: `_get_observation`](../../../../simulation/environment/observation_runtime.py#L79)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        if self.mtf and self._m1_idx.size:
            seq = seq[:, self._m1_idx]
        elif self.mtf:
            seq = np.zeros((seq.shape[0], 1), dtype=np.float32)
        seq = cast(np.ndarray[Any, Any], np.nan_to_num(seq, nan=0.0))
        seq, seq_mask = pad_observation_window(seq, self.obs_window)

        # Account state
        pos_dir = float(self.position.direction) if self.position is not None else 0.0
        open_pnl = float(self.account.open_pnl) if self.position is not None else 0.0
        unrealised_r = (open_pnl / self.account.equity * 100) if self.account.equity > 0 else 0.0
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `ObservationSchema.to_dict`

**Kind:** method · **Status:** stable · **Owner:** `decisioning.observations`

**Purpose:** Return the ordered observation contract as JSON-compatible data.

**Exact API:** {py:obj}`decisioning.observations.ObservationSchema.to_dict` · **Source:** [decisioning/observations.py:145](../../../../decisioning/observations.py#L145)

**Inputs and outputs:**

- **Returns:**

  ```text
  Mapping from ``str`` keys to ``Any`` values.
  ```

**Observed usage:**

1. [test fixture: `_StubModel`](../../../../tests/unit/features/test_stage_a_observation.py#L24)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
class _StubModel:
    _observation_schema = build_observation_schema(OBSERVATION_SCHEMA_V1).to_dict()
    _action_schema = build_discrete_trading_action_schema().to_dict()
    action_space: Any = spaces.Discrete(20)

    def predict(self, obs: dict[str, Any], deterministic: bool = True) -> np.ndarray[Any, Any]:  # noqa: ARG002
        return np.array([1])
```

2. [test fixture: `_StubModel`](../../../../tests/unit/live/test_rl_bridge.py#L164)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
class _StubModel:
    """Duck-typed SB3 model: action = +1 (long) always."""

    _observation_schema = build_observation_schema(OBSERVATION_SCHEMA_V1).to_dict()
    action_space: Any = spaces.Discrete(20)
    _action_schema: dict[str, object] = build_discrete_trading_action_schema().to_dict()

    def predict(self, obs: dict[str, Any], deterministic: bool = True) -> np.ndarray[Any, Any]:  # noqa: ARG002
        return np.array([1])
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `ObservationSchema.width`

**Kind:** method · **Status:** stable · **Owner:** `decisioning.observations`

**Purpose:** Return the total number of flattened observation coordinates.

**Exact API:** {py:obj}`decisioning.observations.ObservationSchema.width` · **Source:** [decisioning/observations.py:137](../../../../decisioning/observations.py#L137)

**Inputs and outputs:**

- **Returns:**

  ```text
  Numeric result returned by ``width``.
  ```

**Observed usage:**

1. [test fixture: `test_v2_schema_has_exact_named_width`](../../../../tests/unit/simulation/test_environment/test_observation_schema.py#L60)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_v2_schema_has_exact_named_width() -> None:
    schema = build_observation_schema(OBSERVATION_SCHEMA_V2)
    assert schema.width == len(V2_COORDINATES) == 28
    assert schema.coordinates == V2_COORDINATES
```

2. [production caller: `to_dict`](../../../../decisioning/observations.py#L153)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def to_dict(self) -> dict[str, Any]:
    return {
        "version": self.version,
        "observation_width": self.width,
        "observation_coordinates": list(self.coordinates),
        "entry_state_visibility": self.entry_state_visibility,
    }
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`
