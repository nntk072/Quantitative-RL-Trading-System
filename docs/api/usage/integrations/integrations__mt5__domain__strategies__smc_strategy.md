# Integrations · `mt5.domain.strategies.smc_strategy`

This page contains 6 public callable records owned by `integrations.mt5.domain.strategies.smc_strategy`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `SMCStrategy`

**Kind:** class · **Status:** stable · **Owner:** `integrations.mt5.domain.strategies.smc_strategy`

**Purpose:** Smart Money Concepts (SMC) Strategy.

**Exact API:** {py:obj}`integrations.mt5.domain.strategies.smc_strategy.SMCStrategy` · **Source:** [integrations/mt5/domain/strategies/smc_strategy.py:7](../../../../integrations/mt5/domain/strategies/smc_strategy.py#L7)

**Observed usage:**

1. [production caller: `create_strategy`](../../../../integrations/mt5/cli/multi_symbol_trading.py#L141)

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

2. [production caller: `__init__`](../../../../integrations/mt5/domain/strategies/combined_strategy.py#L46)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …

        if "crossover" in strategies:
            self.strategies["crossover"] = CrossOverStrategy(trading_data)

        if "smc" in strategies:
            self.strategies["smc"] = SMCStrategy(trading_data)

        if "trend_breakout" in strategies:
            self.strategies["trend_breakout"] = TrendBreakoutStrategy(trading_data)
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `SMCStrategy`

**Kind:** class · **Status:** stable · **Owner:** `integrations.mt5.domain.strategies.smc_strategy`

**Purpose:** Smart Money Concepts (SMC) Strategy.

**Exact API:** {py:obj}`integrations.mt5.domain.strategies.smc_strategy.SMCStrategy` · **Source:** [integrations/mt5/domain/strategies/smc_strategy.py:7](../../../../integrations/mt5/domain/strategies/smc_strategy.py#L7)

**Observed usage:**

1. [production caller: `create_strategy`](../../../../integrations/mt5/cli/multi_symbol_trading.py#L141)

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

2. [production caller: `__init__`](../../../../integrations/mt5/domain/strategies/combined_strategy.py#L46)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …

        if "crossover" in strategies:
            self.strategies["crossover"] = CrossOverStrategy(trading_data)

        if "smc" in strategies:
            self.strategies["smc"] = SMCStrategy(trading_data)

        if "trend_breakout" in strategies:
            self.strategies["trend_breakout"] = TrendBreakoutStrategy(trading_data)
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `SMCStrategy.identify_fair_value_gaps`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.strategies.smc_strategy`

**Purpose:** Identify bullish and bearish Fair Value Gaps (FVG).

**Exact API:** {py:obj}`integrations.mt5.domain.strategies.smc_strategy.SMCStrategy.identify_fair_value_gaps` · **Source:** [integrations/mt5/domain/strategies/smc_strategy.py:76](../../../../integrations/mt5/domain/strategies/smc_strategy.py#L76)

**Inputs and outputs:**

- **Args:**

  ```text
  df: Input DataFrame supplying the rows used by this calculation.
  ```

- **Returns:**

  ```text
  Tuple of (bullish_fvg, bearish_fvg) as boolean series
  ```

**Observed usage:**

1. [production caller: `signal`](../../../../integrations/mt5/domain/strategies/smc_strategy.py#L165)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …

            # Identify order blocks
        bullish_blocks, bearish_blocks = self.identify_order_blocks(df)

        # Identify Fair Value Gaps
        bullish_fvg, bearish_fvg = self.identify_fair_value_gaps(df)

        # Identify market structure
        market_structure = self.identify_market_structure(df)

        # Calculate EMA for trend confirmation
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `SMCStrategy.identify_market_structure`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.strategies.smc_strategy`

**Purpose:** Identify market structure (trend direction).

**Exact API:** {py:obj}`integrations.mt5.domain.strategies.smc_strategy.SMCStrategy.identify_market_structure` · **Source:** [integrations/mt5/domain/strategies/smc_strategy.py:110](../../../../integrations/mt5/domain/strategies/smc_strategy.py#L110)

**Inputs and outputs:**

- **Args:**

  ```text
  df: Input DataFrame supplying the rows used by this calculation.
  ```

- **Returns:**

  ```text
  'bullish', 'bearish', or 'neutral'
  ```

**Observed usage:**

1. [production caller: `signal`](../../../../integrations/mt5/domain/strategies/smc_strategy.py#L168)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …

        # Identify Fair Value Gaps
        bullish_fvg, bearish_fvg = self.identify_fair_value_gaps(df)

        # Identify market structure
        market_structure = self.identify_market_structure(df)

        # Calculate EMA for trend confirmation
        ema_fast = df["close"].ewm(span=9, adjust=False).mean()
        ema_slow = df["close"].ewm(span=21, adjust=False).mean()

# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `SMCStrategy.identify_order_blocks`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.strategies.smc_strategy`

**Purpose:** Identify bullish and bearish order blocks.

**Exact API:** {py:obj}`integrations.mt5.domain.strategies.smc_strategy.SMCStrategy.identify_order_blocks` · **Source:** [integrations/mt5/domain/strategies/smc_strategy.py:31](../../../../integrations/mt5/domain/strategies/smc_strategy.py#L31)

**Inputs and outputs:**

- **Args:**

  ```text
  df: Input DataFrame supplying the rows used by this calculation.
  ```

- **Returns:**

  ```text
  Tuple of (bullish_blocks, bearish_blocks) as boolean series
  ```

**Observed usage:**

1. [production caller: `signal`](../../../../integrations/mt5/domain/strategies/smc_strategy.py#L162)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        if len(df) < self.order_block_periods + 5:
            symbol = self.data.get_symbol()
            return symbol, Signal.NONE

            # Identify order blocks
        bullish_blocks, bearish_blocks = self.identify_order_blocks(df)

        # Identify Fair Value Gaps
        bullish_fvg, bearish_fvg = self.identify_fair_value_gaps(df)

        # Identify market structure
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `SMCStrategy.signal`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.strategies.smc_strategy`

**Purpose:** Generate trading signal based on SMC concepts.

**Exact API:** {py:obj}`integrations.mt5.domain.strategies.smc_strategy.SMCStrategy.signal` · **Source:** [integrations/mt5/domain/strategies/smc_strategy.py:149](../../../../integrations/mt5/domain/strategies/smc_strategy.py#L149)

**Inputs and outputs:**

- **Returns:**

  ```text
  Tuple of (symbol, signal)
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = SMCStrategy(...)
result = instance.signal()
```

**Lifecycle context:** This callable participates in `SMCStrategy`: Smart Money Concepts (SMC) Strategy. Related public lifecycle methods: {py:obj}`integrations.mt5.domain.strategies.smc_strategy.SMCStrategy.identify_order_blocks`, {py:obj}`integrations.mt5.domain.strategies.smc_strategy.SMCStrategy.identify_fair_value_gaps`, {py:obj}`integrations.mt5.domain.strategies.smc_strategy.SMCStrategy.identify_market_structure`, {py:obj}`integrations.mt5.domain.strategies.smc_strategy.SMCStrategy.signal`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`
