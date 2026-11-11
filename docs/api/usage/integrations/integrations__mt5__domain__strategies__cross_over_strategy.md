# Integrations · `mt5.domain.strategies.cross_over_strategy`

This page contains 3 public callable records owned by `integrations.mt5.domain.strategies.cross_over_strategy`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `CrossOverStrategy`

**Kind:** class · **Status:** stable · **Owner:** `integrations.mt5.domain.strategies.cross_over_strategy`

**Purpose:** Moving-average crossover strategy for broker-neutral execution.

**Exact API:** {py:obj}`integrations.mt5.domain.strategies.cross_over_strategy.CrossOverStrategy` · **Source:** [integrations/mt5/domain/strategies/cross_over_strategy.py:8](../../../../integrations/mt5/domain/strategies/cross_over_strategy.py#L8)

**Observed usage:**

1. [production caller: `create_strategy`](../../../../integrations/mt5/cli/multi_symbol_trading.py#L139)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def create_strategy(data_source: MT5Data, strategy_type: str) -> TradingStrategy:
    if strategy_type == "crossover":
        return CrossOverStrategy(data_source)
    elif strategy_type == "smc":
        return SMCStrategy(data_source)
    elif strategy_type == "trend_breakout":
        return TrendBreakoutStrategy(data_source)
    elif strategy_type == "combined":
        return CombinedStrategy(data_source)
    else:
        logger.warning(f"Unknown strategy type: {strategy_type}, using combined")
        return CombinedStrategy(data_source)
```

2. [production caller: `__init__`](../../../../integrations/mt5/domain/strategies/combined_strategy.py#L43)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …

        if strategies is None:
            strategies = ["crossover", "smc", "trend_breakout"]

        if "crossover" in strategies:
            self.strategies["crossover"] = CrossOverStrategy(trading_data)

        if "smc" in strategies:
            self.strategies["smc"] = SMCStrategy(trading_data)

        if "trend_breakout" in strategies:
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `CrossOverStrategy`

**Kind:** class · **Status:** stable · **Owner:** `integrations.mt5.domain.strategies.cross_over_strategy`

**Purpose:** Moving-average crossover strategy for broker-neutral execution.

**Exact API:** {py:obj}`integrations.mt5.domain.strategies.cross_over_strategy.CrossOverStrategy` · **Source:** [integrations/mt5/domain/strategies/cross_over_strategy.py:8](../../../../integrations/mt5/domain/strategies/cross_over_strategy.py#L8)

**Observed usage:**

1. [production caller: `create_strategy`](../../../../integrations/mt5/cli/multi_symbol_trading.py#L139)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def create_strategy(data_source: MT5Data, strategy_type: str) -> TradingStrategy:
    if strategy_type == "crossover":
        return CrossOverStrategy(data_source)
    elif strategy_type == "smc":
        return SMCStrategy(data_source)
    elif strategy_type == "trend_breakout":
        return TrendBreakoutStrategy(data_source)
    elif strategy_type == "combined":
        return CombinedStrategy(data_source)
    else:
        logger.warning(f"Unknown strategy type: {strategy_type}, using combined")
        return CombinedStrategy(data_source)
```

2. [production caller: `__init__`](../../../../integrations/mt5/domain/strategies/combined_strategy.py#L43)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …

        if strategies is None:
            strategies = ["crossover", "smc", "trend_breakout"]

        if "crossover" in strategies:
            self.strategies["crossover"] = CrossOverStrategy(trading_data)

        if "smc" in strategies:
            self.strategies["smc"] = SMCStrategy(trading_data)

        if "trend_breakout" in strategies:
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `CrossOverStrategy.signal`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.strategies.cross_over_strategy`

**Purpose:** Evaluate the latest bars and return the crossover signal.

**Exact API:** {py:obj}`integrations.mt5.domain.strategies.cross_over_strategy.CrossOverStrategy.signal` · **Source:** [integrations/mt5/domain/strategies/cross_over_strategy.py:19](../../../../integrations/mt5/domain/strategies/cross_over_strategy.py#L19)

**Inputs and outputs:**

- **Returns:**

  ```text
  Pair of broker symbol and long, short, or neutral signal.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = CrossOverStrategy(...)
result = instance.signal()
```

**Lifecycle context:** This callable participates in `CrossOverStrategy`: Moving-average crossover strategy for broker-neutral execution. Related public lifecycle methods: {py:obj}`integrations.mt5.domain.strategies.cross_over_strategy.CrossOverStrategy.signal`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`
