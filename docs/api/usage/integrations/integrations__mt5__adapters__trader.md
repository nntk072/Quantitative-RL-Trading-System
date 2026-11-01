# Integrations · `mt5.adapters.trader`

This page contains 7 public callable records owned by `integrations.mt5.adapters.trader`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `Trader`

**Kind:** class · **Status:** stable · **Owner:** `integrations.mt5.adapters.trader`

**Purpose:** Broker-neutral interface for managing and sizing open positions.

**Exact API:** {py:obj}`integrations.mt5.adapters.trader.Trader` · **Source:** [integrations/mt5/adapters/trader.py:5](../../../../integrations/mt5/adapters/trader.py#L5)

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = Trader(...)
```

**Lifecycle context:** Broker-neutral interface for managing and sizing open positions.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `Trader.calculate_position_size`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.adapters.trader`

**Purpose:** Calculate a broker-compatible position size for a stop distance.

**Exact API:** {py:obj}`integrations.mt5.adapters.trader.Trader.calculate_position_size` · **Source:** [integrations/mt5/adapters/trader.py:74](../../../../integrations/mt5/adapters/trader.py#L74)

**Inputs and outputs:**

- **Args:**

  ```text
  *args: Parsed command-line arguments for this operation.
  **kwargs: Kwargs used by the operation described above.
  ```

- **Returns:**

  ```text
  Result of calculate a broker-compatible position size for a stop distance.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = Trader(...)
result = instance.calculate_position_size(*args, **kwargs)
```

**Lifecycle context:** This callable participates in `Trader`: Broker-neutral interface for managing and sizing open positions. Related public lifecycle methods: {py:obj}`integrations.mt5.adapters.trader.Trader.open_position`, {py:obj}`integrations.mt5.adapters.trader.Trader.close_positions`, {py:obj}`integrations.mt5.adapters.trader.Trader.get_opened_positions`, {py:obj}`integrations.mt5.adapters.trader.Trader.get_all_positions`, {py:obj}`integrations.mt5.adapters.trader.Trader.send_to_break_even`, {py:obj}`integrations.mt5.adapters.trader.Trader.calculate_position_size`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `Trader.close_positions`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.adapters.trader`

**Purpose:** Close positions selected by adapter-specific filters.

**Exact API:** {py:obj}`integrations.mt5.adapters.trader.Trader.close_positions` · **Source:** [integrations/mt5/adapters/trader.py:22](../../../../integrations/mt5/adapters/trader.py#L22)

**Inputs and outputs:**

- **Args:**

  ```text
  *args: Parsed command-line arguments for this operation.
  **kwargs: Kwargs used by the operation described above.
  ```

- **Returns:**

  ```text
  Result of close positions selected by adapter-specific filters.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = Trader(...)
result = instance.close_positions(*args, **kwargs)
```

**Lifecycle context:** This callable participates in `Trader`: Broker-neutral interface for managing and sizing open positions. Related public lifecycle methods: {py:obj}`integrations.mt5.adapters.trader.Trader.open_position`, {py:obj}`integrations.mt5.adapters.trader.Trader.close_positions`, {py:obj}`integrations.mt5.adapters.trader.Trader.get_opened_positions`, {py:obj}`integrations.mt5.adapters.trader.Trader.get_all_positions`, {py:obj}`integrations.mt5.adapters.trader.Trader.send_to_break_even`, {py:obj}`integrations.mt5.adapters.trader.Trader.calculate_position_size`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `Trader.get_all_positions`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.adapters.trader`

**Purpose:** Return all positions visible through the adapter.

**Exact API:** {py:obj}`integrations.mt5.adapters.trader.Trader.get_all_positions` · **Source:** [integrations/mt5/adapters/trader.py:48](../../../../integrations/mt5/adapters/trader.py#L48)

**Inputs and outputs:**

- **Args:**

  ```text
  *args: Parsed command-line arguments for this operation.
  **kwargs: Kwargs used by the operation described above.
  ```

- **Returns:**

  ```text
  Result of return all positions visible through the adapter.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = Trader(...)
result = instance.get_all_positions(*args, **kwargs)
```

**Lifecycle context:** This callable participates in `Trader`: Broker-neutral interface for managing and sizing open positions. Related public lifecycle methods: {py:obj}`integrations.mt5.adapters.trader.Trader.open_position`, {py:obj}`integrations.mt5.adapters.trader.Trader.close_positions`, {py:obj}`integrations.mt5.adapters.trader.Trader.get_opened_positions`, {py:obj}`integrations.mt5.adapters.trader.Trader.get_all_positions`, {py:obj}`integrations.mt5.adapters.trader.Trader.send_to_break_even`, {py:obj}`integrations.mt5.adapters.trader.Trader.calculate_position_size`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `Trader.get_opened_positions`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.adapters.trader`

**Purpose:** Return open positions matching adapter-specific filters.

**Exact API:** {py:obj}`integrations.mt5.adapters.trader.Trader.get_opened_positions` · **Source:** [integrations/mt5/adapters/trader.py:35](../../../../integrations/mt5/adapters/trader.py#L35)

**Inputs and outputs:**

- **Args:**

  ```text
  *args: Parsed command-line arguments for this operation.
  **kwargs: Kwargs used by the operation described above.
  ```

- **Returns:**

  ```text
  Result of return open positions matching adapter-specific filters.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = Trader(...)
result = instance.get_opened_positions(*args, **kwargs)
```

**Lifecycle context:** This callable participates in `Trader`: Broker-neutral interface for managing and sizing open positions. Related public lifecycle methods: {py:obj}`integrations.mt5.adapters.trader.Trader.open_position`, {py:obj}`integrations.mt5.adapters.trader.Trader.close_positions`, {py:obj}`integrations.mt5.adapters.trader.Trader.get_opened_positions`, {py:obj}`integrations.mt5.adapters.trader.Trader.get_all_positions`, {py:obj}`integrations.mt5.adapters.trader.Trader.send_to_break_even`, {py:obj}`integrations.mt5.adapters.trader.Trader.calculate_position_size`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `Trader.open_position`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.adapters.trader`

**Purpose:** Open a position; returns the broker result object or None on failure.

**Exact API:** {py:obj}`integrations.mt5.adapters.trader.Trader.open_position` · **Source:** [integrations/mt5/adapters/trader.py:9](../../../../integrations/mt5/adapters/trader.py#L9)

**Inputs and outputs:**

- **Args:**

  ```text
  *args: Parsed command-line arguments for this operation.
  **kwargs: Kwargs used by the operation described above.
  ```

- **Returns:**

  ```text
  Result of open a position; returns the broker result object or None on failure.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = Trader(...)
result = instance.open_position(*args, **kwargs)
```

**Lifecycle context:** This callable participates in `Trader`: Broker-neutral interface for managing and sizing open positions. Related public lifecycle methods: {py:obj}`integrations.mt5.adapters.trader.Trader.open_position`, {py:obj}`integrations.mt5.adapters.trader.Trader.close_positions`, {py:obj}`integrations.mt5.adapters.trader.Trader.get_opened_positions`, {py:obj}`integrations.mt5.adapters.trader.Trader.get_all_positions`, {py:obj}`integrations.mt5.adapters.trader.Trader.send_to_break_even`, {py:obj}`integrations.mt5.adapters.trader.Trader.calculate_position_size`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `Trader.send_to_break_even`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.adapters.trader`

**Purpose:** Adjust selected positions to their break-even stop level.

**Exact API:** {py:obj}`integrations.mt5.adapters.trader.Trader.send_to_break_even` · **Source:** [integrations/mt5/adapters/trader.py:61](../../../../integrations/mt5/adapters/trader.py#L61)

**Inputs and outputs:**

- **Args:**

  ```text
  *args: Parsed command-line arguments for this operation.
  **kwargs: Kwargs used by the operation described above.
  ```

- **Returns:**

  ```text
  Result of adjust selected positions to their break-even stop level.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = Trader(...)
result = instance.send_to_break_even(*args, **kwargs)
```

**Lifecycle context:** This callable participates in `Trader`: Broker-neutral interface for managing and sizing open positions. Related public lifecycle methods: {py:obj}`integrations.mt5.adapters.trader.Trader.open_position`, {py:obj}`integrations.mt5.adapters.trader.Trader.close_positions`, {py:obj}`integrations.mt5.adapters.trader.Trader.get_opened_positions`, {py:obj}`integrations.mt5.adapters.trader.Trader.get_all_positions`, {py:obj}`integrations.mt5.adapters.trader.Trader.send_to_break_even`, {py:obj}`integrations.mt5.adapters.trader.Trader.calculate_position_size`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`
