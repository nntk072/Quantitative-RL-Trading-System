# Trading · `strategies.strategy_contract`

This page contains 7 public callable records owned by `trading.strategies.strategy_contract`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `TradingStrategy`

**Kind:** class · **Status:** stable · **Owner:** `trading.strategies.strategy_contract`

**Purpose:** Strategy semantics consumed by :class:`TradingEnv`.

**Exact API:** {py:obj}`trading.strategies.strategy_contract.TradingStrategy` · **Source:** [trading/strategies/strategy_contract.py:27](../../../../trading/strategies/strategy_contract.py#L27)

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = TradingStrategy(...)
```

**Lifecycle context:** Strategy semantics consumed by :class:`TradingEnv`.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `TradingStrategy.bind_columns`

**Kind:** method · **Status:** stable · **Owner:** `trading.strategies.strategy_contract`

**Purpose:** Remember column positions once, when the environment is built.

**Exact API:** {py:obj}`trading.strategies.strategy_contract.TradingStrategy.bind_columns` · **Source:** [trading/strategies/strategy_contract.py:81](../../../../trading/strategies/strategy_contract.py#L81)

**Inputs and outputs:**

- **Args:**

  ```text
  columns: Items supplied for the columns, in input order.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = TradingStrategy(...)
result = instance.bind_columns(columns=...)
```

**Lifecycle context:** This callable participates in `TradingStrategy`: Strategy semantics consumed by :class:`TradingEnv`. Related public lifecycle methods: {py:obj}`trading.strategies.strategy_contract.TradingStrategy.validate_entry`, {py:obj}`trading.strategies.strategy_contract.TradingStrategy.sl_reference`, {py:obj}`trading.strategies.strategy_contract.TradingStrategy.target_candidates`, {py:obj}`trading.strategies.strategy_contract.TradingStrategy.bind_columns`, {py:obj}`trading.strategies.strategy_contract.TradingStrategy.context_direction`, {py:obj}`trading.strategies.strategy_contract.TradingStrategy.sl_candidates`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `TradingStrategy.context_direction`

**Kind:** method · **Status:** stable · **Owner:** `trading.strategies.strategy_contract`

**Purpose:** Intended trade side from HTF/PO3 context: -1, 0, or +1.

**Exact API:** {py:obj}`trading.strategies.strategy_contract.TradingStrategy.context_direction` · **Source:** [trading/strategies/strategy_contract.py:88](../../../../trading/strategies/strategy_contract.py#L88)

**Inputs and outputs:**

- **Args:**

  ```text
  row: Row index or record being processed.
  ```

- **Returns:**

  ```text
  Numeric result returned by ``context_direction``.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = TradingStrategy(...)
result = instance.context_direction(row=...)
```

**Lifecycle context:** This callable participates in `TradingStrategy`: Strategy semantics consumed by :class:`TradingEnv`. Related public lifecycle methods: {py:obj}`trading.strategies.strategy_contract.TradingStrategy.validate_entry`, {py:obj}`trading.strategies.strategy_contract.TradingStrategy.sl_reference`, {py:obj}`trading.strategies.strategy_contract.TradingStrategy.target_candidates`, {py:obj}`trading.strategies.strategy_contract.TradingStrategy.bind_columns`, {py:obj}`trading.strategies.strategy_contract.TradingStrategy.context_direction`, {py:obj}`trading.strategies.strategy_contract.TradingStrategy.sl_candidates`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `TradingStrategy.sl_candidates`

**Kind:** method · **Status:** stable · **Owner:** `trading.strategies.strategy_contract`

**Purpose:** Named SL levels for the trader action ``sl_anchor`` picker.

**Exact API:** {py:obj}`trading.strategies.strategy_contract.TradingStrategy.sl_candidates` · **Source:** [trading/strategies/strategy_contract.py:101](../../../../trading/strategies/strategy_contract.py#L101)

**Inputs and outputs:**

- **Args:**

  ```text
  direction: Signed trade direction: 1 for long and -1 for short.
  row: Row index or record being processed.
  ```

- **Returns:**

  ```text
  Values returned by ``sl_candidates``, in the declared order.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = TradingStrategy(...)
result = instance.sl_candidates(direction=..., row=...)
```

**Lifecycle context:** This callable participates in `TradingStrategy`: Strategy semantics consumed by :class:`TradingEnv`. Related public lifecycle methods: {py:obj}`trading.strategies.strategy_contract.TradingStrategy.validate_entry`, {py:obj}`trading.strategies.strategy_contract.TradingStrategy.sl_reference`, {py:obj}`trading.strategies.strategy_contract.TradingStrategy.target_candidates`, {py:obj}`trading.strategies.strategy_contract.TradingStrategy.bind_columns`, {py:obj}`trading.strategies.strategy_contract.TradingStrategy.context_direction`, {py:obj}`trading.strategies.strategy_contract.TradingStrategy.sl_candidates`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `TradingStrategy.sl_reference`

**Kind:** method · **Status:** stable · **Owner:** `trading.strategies.strategy_contract`

**Purpose:** Structural SL reference price, or None if unavailable/invalid.

**Exact API:** {py:obj}`trading.strategies.strategy_contract.TradingStrategy.sl_reference` · **Source:** [trading/strategies/strategy_contract.py:58](../../../../trading/strategies/strategy_contract.py#L58)

**Inputs and outputs:**

- **Args:**

  ```text
  direction: Signed trade direction: 1 for long and -1 for short.
  row: Row index or record being processed.
  ```

- **Returns:**

  ```text
  Result of structural SL reference price, or None if unavailable/invalid.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = TradingStrategy(...)
result = instance.sl_reference(direction=..., row=...)
```

**Lifecycle context:** This callable participates in `TradingStrategy`: Strategy semantics consumed by :class:`TradingEnv`. Related public lifecycle methods: {py:obj}`trading.strategies.strategy_contract.TradingStrategy.validate_entry`, {py:obj}`trading.strategies.strategy_contract.TradingStrategy.sl_reference`, {py:obj}`trading.strategies.strategy_contract.TradingStrategy.target_candidates`, {py:obj}`trading.strategies.strategy_contract.TradingStrategy.bind_columns`, {py:obj}`trading.strategies.strategy_contract.TradingStrategy.context_direction`, {py:obj}`trading.strategies.strategy_contract.TradingStrategy.sl_candidates`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `TradingStrategy.target_candidates`

**Kind:** method · **Status:** stable · **Owner:** `trading.strategies.strategy_contract`

**Purpose:** Named take-profit candidate levels for the TP-target resolver.

**Exact API:** {py:obj}`trading.strategies.strategy_contract.TradingStrategy.target_candidates` · **Source:** [trading/strategies/strategy_contract.py:70](../../../../trading/strategies/strategy_contract.py#L70)

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
instance = TradingStrategy(...)
result = instance.target_candidates(direction=..., row=...)
```

**Lifecycle context:** This callable participates in `TradingStrategy`: Strategy semantics consumed by :class:`TradingEnv`. Related public lifecycle methods: {py:obj}`trading.strategies.strategy_contract.TradingStrategy.validate_entry`, {py:obj}`trading.strategies.strategy_contract.TradingStrategy.sl_reference`, {py:obj}`trading.strategies.strategy_contract.TradingStrategy.target_candidates`, {py:obj}`trading.strategies.strategy_contract.TradingStrategy.bind_columns`, {py:obj}`trading.strategies.strategy_contract.TradingStrategy.context_direction`, {py:obj}`trading.strategies.strategy_contract.TradingStrategy.sl_candidates`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `TradingStrategy.validate_entry`

**Kind:** method · **Status:** stable · **Owner:** `trading.strategies.strategy_contract`

**Purpose:** Whether an entry in ``direction`` is allowed at this bar.

**Exact API:** {py:obj}`trading.strategies.strategy_contract.TradingStrategy.validate_entry` · **Source:** [trading/strategies/strategy_contract.py:46](../../../../trading/strategies/strategy_contract.py#L46)

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
instance = TradingStrategy(...)
result = instance.validate_entry(direction=..., row=...)
```

**Lifecycle context:** This callable participates in `TradingStrategy`: Strategy semantics consumed by :class:`TradingEnv`. Related public lifecycle methods: {py:obj}`trading.strategies.strategy_contract.TradingStrategy.validate_entry`, {py:obj}`trading.strategies.strategy_contract.TradingStrategy.sl_reference`, {py:obj}`trading.strategies.strategy_contract.TradingStrategy.target_candidates`, {py:obj}`trading.strategies.strategy_contract.TradingStrategy.bind_columns`, {py:obj}`trading.strategies.strategy_contract.TradingStrategy.context_direction`, {py:obj}`trading.strategies.strategy_contract.TradingStrategy.sl_candidates`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`
