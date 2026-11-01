# Integrations · `mt5.adapters.data`

This page contains 3 public callable records owned by `integrations.mt5.adapters.data`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `TradingData`

**Kind:** class · **Status:** stable · **Owner:** `integrations.mt5.adapters.data`

**Purpose:** Broker-neutral interface for market-data access.

**Exact API:** {py:obj}`integrations.mt5.adapters.data.TradingData` · **Source:** [integrations/mt5/adapters/data.py:6](../../../../integrations/mt5/adapters/data.py#L6)

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = TradingData(...)
```

**Lifecycle context:** Broker-neutral interface for market-data access.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `TradingData.get_data`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.adapters.data`

**Purpose:** Fetch market bars for the adapter's configured symbol.

**Exact API:** {py:obj}`integrations.mt5.adapters.data.TradingData.get_data` · **Source:** [integrations/mt5/adapters/data.py:10](../../../../integrations/mt5/adapters/data.py#L10)

**Inputs and outputs:**

- **Returns:**

  ```text
  DataFrame returned by ``get_data``.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = TradingData(...)
result = instance.get_data()
```

**Lifecycle context:** This callable participates in `TradingData`: Broker-neutral interface for market-data access. Related public lifecycle methods: {py:obj}`integrations.mt5.adapters.data.TradingData.get_data`, {py:obj}`integrations.mt5.adapters.data.TradingData.get_symbol`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `TradingData.get_symbol`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.adapters.data`

**Purpose:** Return the symbol configured for this data source.

**Exact API:** {py:obj}`integrations.mt5.adapters.data.TradingData.get_symbol` · **Source:** [integrations/mt5/adapters/data.py:19](../../../../integrations/mt5/adapters/data.py#L19)

**Inputs and outputs:**

- **Returns:**

  ```text
  Text returned by ``get_symbol``.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = TradingData(...)
result = instance.get_symbol()
```

**Lifecycle context:** This callable participates in `TradingData`: Broker-neutral interface for market-data access. Related public lifecycle methods: {py:obj}`integrations.mt5.adapters.data.TradingData.get_data`, {py:obj}`integrations.mt5.adapters.data.TradingData.get_symbol`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`
