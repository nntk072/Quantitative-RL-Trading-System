# Integrations · `mt5.adapters.strategy`

This page contains 2 public callable records owned by `integrations.mt5.adapters.strategy`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `TradingStrategy`

**Kind:** class · **Status:** stable · **Owner:** `integrations.mt5.adapters.strategy`

**Purpose:** Interface for strategies that convert market data into signals.

**Exact API:** {py:obj}`integrations.mt5.adapters.strategy.TradingStrategy` · **Source:** [integrations/mt5/adapters/strategy.py:10](../../../../integrations/mt5/adapters/strategy.py#L10)

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = TradingStrategy(...)
```

**Lifecycle context:** Interface for strategies that convert market data into signals.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `TradingStrategy.signal`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.adapters.strategy`

**Purpose:** Return the current signal for the strategy's configured market.

**Exact API:** {py:obj}`integrations.mt5.adapters.strategy.TradingStrategy.signal` · **Source:** [integrations/mt5/adapters/strategy.py:14](../../../../integrations/mt5/adapters/strategy.py#L14)

**Inputs and outputs:**

- **Returns:**

  ```text
  Values returned by ``signal``, in the declared order.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = TradingStrategy(...)
result = instance.signal()
```

**Lifecycle context:** This callable participates in `TradingStrategy`: Interface for strategies that convert market data into signals. Related public lifecycle methods: {py:obj}`integrations.mt5.adapters.strategy.TradingStrategy.signal`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`
