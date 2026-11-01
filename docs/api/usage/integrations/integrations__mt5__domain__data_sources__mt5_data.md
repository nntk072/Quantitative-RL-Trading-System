# Integrations · `mt5.domain.data_sources.mt5_data`

This page contains 4 public callable records owned by `integrations.mt5.domain.data_sources.mt5_data`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `MT5Data`

**Kind:** class · **Status:** stable · **Owner:** `integrations.mt5.domain.data_sources.mt5_data`

**Purpose:** Market-data source that reads recent rates from the MetaTrader terminal.

**Exact API:** {py:obj}`integrations.mt5.domain.data_sources.mt5_data.MT5Data` · **Source:** [integrations/mt5/domain/data_sources/mt5_data.py:7](../../../../integrations/mt5/domain/data_sources/mt5_data.py#L7)

**Inputs and outputs:**

**Observed usage:**

1. [production caller: `_initialize_data_sources`](../../../../integrations/mt5/domain/multi_symbol_manager.py#L67)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
                if not mt5.symbol_select(symbol, True):
                    logger.warning(f"Symbol {symbol} not available, skipping")
                    continue

                    # Create data source
                data_source = MT5Data(symbol, self.timeframe)

                self.data_sources[symbol] = data_source
                logger.info(f"Initialized data source for {symbol}")

            except Exception as e:
# … caller assertions omitted …
```

2. [production caller: `add_symbol`](../../../../integrations/mt5/domain/multi_symbol_manager.py#L147)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            if not mt5.symbol_select(symbol, True):
                logger.error(f"Symbol {symbol} not available")
                return False

                # Create data source
            data_source = MT5Data(symbol, self.timeframe)

            self.data_sources[symbol] = data_source
            self.symbols.append(symbol)
            logger.info(f"Added symbol {symbol}")
            return True
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `MT5Data`

**Kind:** class · **Status:** stable · **Owner:** `integrations.mt5.domain.data_sources.mt5_data`

**Purpose:** Market-data source that reads recent rates from the MetaTrader terminal.

**Exact API:** {py:obj}`integrations.mt5.domain.data_sources.mt5_data.MT5Data` · **Source:** [integrations/mt5/domain/data_sources/mt5_data.py:7](../../../../integrations/mt5/domain/data_sources/mt5_data.py#L7)

**Inputs and outputs:**

**Observed usage:**

1. [production caller: `_initialize_data_sources`](../../../../integrations/mt5/domain/multi_symbol_manager.py#L67)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
                if not mt5.symbol_select(symbol, True):
                    logger.warning(f"Symbol {symbol} not available, skipping")
                    continue

                    # Create data source
                data_source = MT5Data(symbol, self.timeframe)

                self.data_sources[symbol] = data_source
                logger.info(f"Initialized data source for {symbol}")

            except Exception as e:
# … caller assertions omitted …
```

2. [production caller: `add_symbol`](../../../../integrations/mt5/domain/multi_symbol_manager.py#L147)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            if not mt5.symbol_select(symbol, True):
                logger.error(f"Symbol {symbol} not available")
                return False

                # Create data source
            data_source = MT5Data(symbol, self.timeframe)

            self.data_sources[symbol] = data_source
            self.symbols.append(symbol)
            logger.info(f"Added symbol {symbol}")
            return True
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `MT5Data.get_data`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.data_sources.mt5_data`

**Purpose:** Fetch recent rates for the configured symbol and timeframe.

**Exact API:** {py:obj}`integrations.mt5.domain.data_sources.mt5_data.MT5Data.get_data` · **Source:** [integrations/mt5/domain/data_sources/mt5_data.py:25](../../../../integrations/mt5/domain/data_sources/mt5_data.py#L25)

**Inputs and outputs:**

- **Returns:**

  ```text
  Bar frame with timestamps converted from terminal epoch seconds.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = MT5Data(...)
result = instance.get_data()
```

**Lifecycle context:** This callable participates in `MT5Data`: Market-data source that reads recent rates from the MetaTrader terminal. Related public lifecycle methods: {py:obj}`integrations.mt5.domain.data_sources.mt5_data.MT5Data.get_data`, {py:obj}`integrations.mt5.domain.data_sources.mt5_data.MT5Data.get_symbol`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `MT5Data.get_symbol`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.data_sources.mt5_data`

**Purpose:** Return the configured broker symbol.

**Exact API:** {py:obj}`integrations.mt5.domain.data_sources.mt5_data.MT5Data.get_symbol` · **Source:** [integrations/mt5/domain/data_sources/mt5_data.py:37](../../../../integrations/mt5/domain/data_sources/mt5_data.py#L37)

**Inputs and outputs:**

- **Returns:**

  ```text
  Text returned by ``get_symbol``.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = MT5Data(...)
result = instance.get_symbol()
```

**Lifecycle context:** This callable participates in `MT5Data`: Market-data source that reads recent rates from the MetaTrader terminal. Related public lifecycle methods: {py:obj}`integrations.mt5.domain.data_sources.mt5_data.MT5Data.get_data`, {py:obj}`integrations.mt5.domain.data_sources.mt5_data.MT5Data.get_symbol`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`
