# Integrations · `mt5.domain.strategies.combined_strategy`

This page contains 3 public callable records owned by `integrations.mt5.domain.strategies.combined_strategy`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `CombinedStrategy`

**Kind:** class · **Status:** stable · **Owner:** `integrations.mt5.domain.strategies.combined_strategy`

**Purpose:** Combined Strategy that uses multiple strategies and requires consensus.

**Exact API:** {py:obj}`integrations.mt5.domain.strategies.combined_strategy.CombinedStrategy` · **Source:** [integrations/mt5/domain/strategies/combined_strategy.py:10](../../../../integrations/mt5/domain/strategies/combined_strategy.py#L10)

**Observed usage:**

1. [production caller: `create_strategy`](../../../../integrations/mt5/cli/multi_symbol_trading.py#L145)

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

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `CombinedStrategy`

**Kind:** class · **Status:** stable · **Owner:** `integrations.mt5.domain.strategies.combined_strategy`

**Purpose:** Combined Strategy that uses multiple strategies and requires consensus.

**Exact API:** {py:obj}`integrations.mt5.domain.strategies.combined_strategy.CombinedStrategy` · **Source:** [integrations/mt5/domain/strategies/combined_strategy.py:10](../../../../integrations/mt5/domain/strategies/combined_strategy.py#L10)

**Observed usage:**

1. [production caller: `create_strategy`](../../../../integrations/mt5/cli/multi_symbol_trading.py#L145)

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

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `CombinedStrategy.signal`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.strategies.combined_strategy`

**Purpose:** Generate trading signal based on combined strategies.

**Exact API:** {py:obj}`integrations.mt5.domain.strategies.combined_strategy.CombinedStrategy.signal` · **Source:** [integrations/mt5/domain/strategies/combined_strategy.py:51](../../../../integrations/mt5/domain/strategies/combined_strategy.py#L51)

**Inputs and outputs:**

- **Returns:**

  ```text
  Tuple of (symbol, signal)
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = CombinedStrategy(...)
result = instance.signal()
```

**Lifecycle context:** This callable participates in `CombinedStrategy`: Combined Strategy that uses multiple strategies and requires consensus. Related public lifecycle methods: {py:obj}`integrations.mt5.domain.strategies.combined_strategy.CombinedStrategy.signal`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`
