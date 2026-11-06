# Integrations · `mt5.domain.multi_symbol_manager`

This page contains 10 public callable records owned by `integrations.mt5.domain.multi_symbol_manager`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `MultiSymbolManager`

**Kind:** class · **Status:** stable · **Owner:** `integrations.mt5.domain.multi_symbol_manager`

**Purpose:** Manage multiple symbol data sources and their configurations.

**Exact API:** {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager` · **Source:** [integrations/mt5/domain/multi_symbol_manager.py:11](../../../../integrations/mt5/domain/multi_symbol_manager.py#L11)

**Observed usage:**

1. [production caller: `initialize_trading_system`](../../../../integrations/mt5/cli/multi_symbol_trading.py#L200)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        "D1": mt5.TIMEFRAME_D1,
    }
    timeframe = timeframe_map.get(timeframe_str, mt5.TIMEFRAME_H1)

    # Initialize symbol manager
    symbol_manager = MultiSymbolManager(
        login=LOGIN,
        server=SERVER,
        password=PASSWORD,
        terminal_path=TERMINAL_PATH,
        symbols=selected_symbols,
        timeframe=timeframe,
    )

    # Update volatility metrics
    analyzer = VolatilityAnalyzer(
        login=LOGIN, server=SERVER, password=PASSWORD, terminal_path=TERMINAL_PATH
    )
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `MultiSymbolManager.add_symbol`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.multi_symbol_manager`

**Purpose:** Add a new symbol to the manager.

**Exact API:** {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.add_symbol` · **Source:** [integrations/mt5/domain/multi_symbol_manager.py:127](../../../../integrations/mt5/domain/multi_symbol_manager.py#L127)

**Inputs and outputs:**

- **Args:**

  ```text
  symbol: Trading symbol to add
  ```

- **Returns:**

  ```text
  True if successfully added, False otherwise
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = MultiSymbolManager(...)
result = instance.add_symbol(symbol=...)
```

**Lifecycle context:** This callable participates in `MultiSymbolManager`: Manage multiple symbol data sources and their configurations. Related public lifecycle methods: {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.get_data_source`, {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.get_all_data_sources`, {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.update_volatility_metrics`, {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.get_volatility_metrics`, {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.get_all_volatility_metrics`, {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.add_symbol`, {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.remove_symbol`, {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.refresh_data`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `MultiSymbolManager.get_active_symbols`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.multi_symbol_manager`

**Purpose:** Get list of active (available) symbols.

**Exact API:** {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.get_active_symbols` · **Source:** [integrations/mt5/domain/multi_symbol_manager.py:193](../../../../integrations/mt5/domain/multi_symbol_manager.py#L193)

**Inputs and outputs:**

- **Returns:**

  ```text
  List of symbol names that are available and initialized
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = MultiSymbolManager(...)
result = instance.get_active_symbols()
```

**Lifecycle context:** This callable participates in `MultiSymbolManager`: Manage multiple symbol data sources and their configurations. Related public lifecycle methods: {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.get_data_source`, {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.get_all_data_sources`, {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.update_volatility_metrics`, {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.get_volatility_metrics`, {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.get_all_volatility_metrics`, {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.add_symbol`, {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.remove_symbol`, {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.refresh_data`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `MultiSymbolManager.get_all_data_sources`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.multi_symbol_manager`

**Purpose:** Get all data sources.

**Exact API:** {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.get_all_data_sources` · **Source:** [integrations/mt5/domain/multi_symbol_manager.py:86](../../../../integrations/mt5/domain/multi_symbol_manager.py#L86)

**Inputs and outputs:**

- **Returns:**

  ```text
  Dictionary mapping symbol names to MT5Data instances
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = MultiSymbolManager(...)
result = instance.get_all_data_sources()
```

**Lifecycle context:** This callable participates in `MultiSymbolManager`: Manage multiple symbol data sources and their configurations. Related public lifecycle methods: {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.get_data_source`, {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.get_all_data_sources`, {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.update_volatility_metrics`, {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.get_volatility_metrics`, {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.get_all_volatility_metrics`, {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.add_symbol`, {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.remove_symbol`, {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.refresh_data`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `MultiSymbolManager.get_all_volatility_metrics`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.multi_symbol_manager`

**Purpose:** Get volatility metrics for all symbols.

**Exact API:** {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.get_all_volatility_metrics` · **Source:** [integrations/mt5/domain/multi_symbol_manager.py:119](../../../../integrations/mt5/domain/multi_symbol_manager.py#L119)

**Inputs and outputs:**

- **Returns:**

  ```text
  Dictionary mapping symbol names to volatility metrics
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = MultiSymbolManager(...)
result = instance.get_all_volatility_metrics()
```

**Lifecycle context:** This callable participates in `MultiSymbolManager`: Manage multiple symbol data sources and their configurations. Related public lifecycle methods: {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.get_data_source`, {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.get_all_data_sources`, {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.update_volatility_metrics`, {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.get_volatility_metrics`, {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.get_all_volatility_metrics`, {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.add_symbol`, {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.remove_symbol`, {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.refresh_data`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `MultiSymbolManager.get_data_source`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.multi_symbol_manager`

**Purpose:** Get data source for a symbol.

**Exact API:** {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.get_data_source` · **Source:** [integrations/mt5/domain/multi_symbol_manager.py:75](../../../../integrations/mt5/domain/multi_symbol_manager.py#L75)

**Inputs and outputs:**

- **Args:**

  ```text
  symbol: Trading symbol
  ```

- **Returns:**

  ```text
  MT5Data instance or None if not found
  ```

**Observed usage:**

1. [production caller: `initialize_trading_system`](../../../../integrations/mt5/cli/multi_symbol_trading.py#L218)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    symbol_manager.update_volatility_metrics(analyzer)

    # Create strategies for each symbol
    strategies: dict[str, TradingStrategy] = {}
    for symbol in selected_symbols:
        data_source = symbol_manager.get_data_source(symbol)
        if data_source:
            strategies[symbol] = create_strategy(data_source, STRATEGY_TYPE)
            logger.info(f"Created {STRATEGY_TYPE} strategy for {symbol}")

            # Initialize risk manager
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `MultiSymbolManager.get_volatility_metrics`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.multi_symbol_manager`

**Purpose:** Get volatility metrics for a symbol.

**Exact API:** {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.get_volatility_metrics` · **Source:** [integrations/mt5/domain/multi_symbol_manager.py:108](../../../../integrations/mt5/domain/multi_symbol_manager.py#L108)

**Inputs and outputs:**

- **Args:**

  ```text
  symbol: Trading symbol
  ```

- **Returns:**

  ```text
  Dictionary with volatility metrics or None
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = MultiSymbolManager(...)
result = instance.get_volatility_metrics(symbol=...)
```

**Lifecycle context:** This callable participates in `MultiSymbolManager`: Manage multiple symbol data sources and their configurations. Related public lifecycle methods: {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.get_data_source`, {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.get_all_data_sources`, {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.update_volatility_metrics`, {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.get_volatility_metrics`, {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.get_all_volatility_metrics`, {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.add_symbol`, {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.remove_symbol`, {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.refresh_data`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `MultiSymbolManager.refresh_data`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.multi_symbol_manager`

**Purpose:** Refresh data for all symbols.

**Exact API:** {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.refresh_data` · **Source:** [integrations/mt5/domain/multi_symbol_manager.py:183](../../../../integrations/mt5/domain/multi_symbol_manager.py#L183)

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = MultiSymbolManager(...)
result = instance.refresh_data()
```

**Lifecycle context:** This callable participates in `MultiSymbolManager`: Manage multiple symbol data sources and their configurations. Related public lifecycle methods: {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.get_data_source`, {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.get_all_data_sources`, {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.update_volatility_metrics`, {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.get_volatility_metrics`, {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.get_all_volatility_metrics`, {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.add_symbol`, {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.remove_symbol`, {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.refresh_data`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `MultiSymbolManager.remove_symbol`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.multi_symbol_manager`

**Purpose:** Remove a symbol from the manager.

**Exact API:** {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.remove_symbol` · **Source:** [integrations/mt5/domain/multi_symbol_manager.py:158](../../../../integrations/mt5/domain/multi_symbol_manager.py#L158)

**Inputs and outputs:**

- **Args:**

  ```text
  symbol: Trading symbol to remove
  ```

- **Returns:**

  ```text
  True if successfully removed, False otherwise
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = MultiSymbolManager(...)
result = instance.remove_symbol(symbol=...)
```

**Lifecycle context:** This callable participates in `MultiSymbolManager`: Manage multiple symbol data sources and their configurations. Related public lifecycle methods: {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.get_data_source`, {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.get_all_data_sources`, {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.update_volatility_metrics`, {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.get_volatility_metrics`, {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.get_all_volatility_metrics`, {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.add_symbol`, {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.remove_symbol`, {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.refresh_data`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `MultiSymbolManager.update_volatility_metrics`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.multi_symbol_manager`

**Purpose:** Update volatility metrics for all symbols.

**Exact API:** {py:obj}`integrations.mt5.domain.multi_symbol_manager.MultiSymbolManager.update_volatility_metrics` · **Source:** [integrations/mt5/domain/multi_symbol_manager.py:94](../../../../integrations/mt5/domain/multi_symbol_manager.py#L94)

**Inputs and outputs:**

- **Args:**

  ```text
  analyzer: VolatilityAnalyzer instance
  ```

**Observed usage:**

1. [production caller: `initialize_trading_system`](../../../../integrations/mt5/cli/multi_symbol_trading.py#L213)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …

    # Update volatility metrics
    analyzer = VolatilityAnalyzer(
        login=LOGIN, server=SERVER, password=PASSWORD, terminal_path=TERMINAL_PATH
    )
    symbol_manager.update_volatility_metrics(analyzer)

    # Create strategies for each symbol
    strategies: dict[str, TradingStrategy] = {}
    for symbol in selected_symbols:
        data_source = symbol_manager.get_data_source(symbol)
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`
