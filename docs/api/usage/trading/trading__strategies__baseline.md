# Trading · `strategies.baseline`

This page contains 4 public callable records owned by `trading.strategies.baseline`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `BaselineStrategy`

**Kind:** class · **Status:** stable · **Owner:** `trading.strategies.baseline`

**Purpose:** Control-group strategy (Idea 3, P2).

**Exact API:** {py:obj}`trading.strategies.baseline.BaselineStrategy` · **Source:** [trading/strategies/baseline.py:11](../../../../trading/strategies/baseline.py#L11)

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = BaselineStrategy(...)
```

**Lifecycle context:** Control-group strategy (Idea 3, P2).

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `BaselineStrategy.sl_reference`

**Kind:** method · **Status:** stable · **Owner:** `trading.strategies.baseline`

**Purpose:** No structural stop: baseline keeps its existing SL behaviour.

**Exact API:** {py:obj}`trading.strategies.baseline.BaselineStrategy.sl_reference` · **Source:** [trading/strategies/baseline.py:34](../../../../trading/strategies/baseline.py#L34)

**Inputs and outputs:**

- **Args:**

  ```text
  direction: Signed trade direction: 1 for long and -1 for short.
  row: Row index or record being processed.
  ```

- **Returns:**

  ```text
  Result of no structural stop: baseline keeps its existing SL behaviour.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = BaselineStrategy(...)
result = instance.sl_reference(direction=..., row=...)
```

**Lifecycle context:** This callable participates in `BaselineStrategy`: Control-group strategy (Idea 3, P2). Related public lifecycle methods: {py:obj}`trading.strategies.baseline.BaselineStrategy.validate_entry`, {py:obj}`trading.strategies.baseline.BaselineStrategy.sl_reference`, {py:obj}`trading.strategies.baseline.BaselineStrategy.target_candidates`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `BaselineStrategy.target_candidates`

**Kind:** method · **Status:** stable · **Owner:** `trading.strategies.baseline`

**Purpose:** No structural targets: baseline keeps its existing TP behaviour.

**Exact API:** {py:obj}`trading.strategies.baseline.BaselineStrategy.target_candidates` · **Source:** [trading/strategies/baseline.py:46](../../../../trading/strategies/baseline.py#L46)

**Inputs and outputs:**

- **Args:**

  ```text
  direction: Signed trade direction: 1 for long and -1 for short.
  row: Row index or record being processed.
  ```

- **Returns:**

  ```text
  Mapping from ``str`` keys to ``float`` values.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = BaselineStrategy(...)
result = instance.target_candidates(direction=..., row=...)
```

**Lifecycle context:** This callable participates in `BaselineStrategy`: Control-group strategy (Idea 3, P2). Related public lifecycle methods: {py:obj}`trading.strategies.baseline.BaselineStrategy.validate_entry`, {py:obj}`trading.strategies.baseline.BaselineStrategy.sl_reference`, {py:obj}`trading.strategies.baseline.BaselineStrategy.target_candidates`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `BaselineStrategy.validate_entry`

**Kind:** method · **Status:** stable · **Owner:** `trading.strategies.baseline`

**Purpose:** No gate: the baseline agent decides freely.

**Exact API:** {py:obj}`trading.strategies.baseline.BaselineStrategy.validate_entry` · **Source:** [trading/strategies/baseline.py:22](../../../../trading/strategies/baseline.py#L22)

**Inputs and outputs:**

- **Args:**

  ```text
  direction: Signed trade direction: 1 for long and -1 for short.
  row: Row index or record being processed.
  ```

- **Returns:**

  ```text
  Whether validate entry meets the requested condition.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = BaselineStrategy(...)
result = instance.validate_entry(direction=..., row=...)
```

**Lifecycle context:** This callable participates in `BaselineStrategy`: Control-group strategy (Idea 3, P2). Related public lifecycle methods: {py:obj}`trading.strategies.baseline.BaselineStrategy.validate_entry`, {py:obj}`trading.strategies.baseline.BaselineStrategy.sl_reference`, {py:obj}`trading.strategies.baseline.BaselineStrategy.target_candidates`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`
