# Integrations · `mt5.domain.strategies.trend_breakout_strategy`

This page contains 8 public callable records owned by `integrations.mt5.domain.strategies.trend_breakout_strategy`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `TrendBreakoutStrategy`

**Kind:** class · **Status:** stable · **Owner:** `integrations.mt5.domain.strategies.trend_breakout_strategy`

**Purpose:** Trend Breakout Strategy.

**Exact API:** {py:obj}`integrations.mt5.domain.strategies.trend_breakout_strategy.TrendBreakoutStrategy` · **Source:** [integrations/mt5/domain/strategies/trend_breakout_strategy.py:9](../../../../integrations/mt5/domain/strategies/trend_breakout_strategy.py#L9)

**Observed usage:**

1. [production caller: `create_strategy`](../../../../integrations/mt5/cli/multi_symbol_trading.py#L143)

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

2. [production caller: `__init__`](../../../../integrations/mt5/domain/strategies/combined_strategy.py#L49)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …

        if "smc" in strategies:
            self.strategies["smc"] = SMCStrategy(trading_data)

        if "trend_breakout" in strategies:
            self.strategies["trend_breakout"] = TrendBreakoutStrategy(trading_data)
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `TrendBreakoutStrategy`

**Kind:** class · **Status:** stable · **Owner:** `integrations.mt5.domain.strategies.trend_breakout_strategy`

**Purpose:** Trend Breakout Strategy.

**Exact API:** {py:obj}`integrations.mt5.domain.strategies.trend_breakout_strategy.TrendBreakoutStrategy` · **Source:** [integrations/mt5/domain/strategies/trend_breakout_strategy.py:9](../../../../integrations/mt5/domain/strategies/trend_breakout_strategy.py#L9)

**Observed usage:**

1. [production caller: `create_strategy`](../../../../integrations/mt5/cli/multi_symbol_trading.py#L143)

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

2. [production caller: `__init__`](../../../../integrations/mt5/domain/strategies/combined_strategy.py#L49)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …

        if "smc" in strategies:
            self.strategies["smc"] = SMCStrategy(trading_data)

        if "trend_breakout" in strategies:
            self.strategies["trend_breakout"] = TrendBreakoutStrategy(trading_data)
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `TrendBreakoutStrategy.calculate_trend_strength`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.strategies.trend_breakout_strategy`

**Purpose:** Calculate trend strength using ADX (Average Directional Index).

**Exact API:** {py:obj}`integrations.mt5.domain.strategies.trend_breakout_strategy.TrendBreakoutStrategy.calculate_trend_strength` · **Source:** [integrations/mt5/domain/strategies/trend_breakout_strategy.py:140](../../../../integrations/mt5/domain/strategies/trend_breakout_strategy.py#L140)

**Inputs and outputs:**

- **Args:**

  ```text
  df: Input DataFrame supplying the rows used by this calculation.
  ```

- **Returns:**

  ```text
  ADX value (0-100, higher = stronger trend)
  ```

**Observed usage:**

1. [production caller: `signal`](../../../../integrations/mt5/domain/strategies/trend_breakout_strategy.py#L186)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …

            # Detect breakout
        is_breakout, direction = self.detect_breakout(df, support, resistance)

        # Calculate trend strength
        trend_strength = self.calculate_trend_strength(df)

        # Calculate moving averages for confirmation
        sma_fast = df["close"].rolling(window=9).mean()
        sma_slow = df["close"].rolling(window=21).mean()

# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `TrendBreakoutStrategy.calculate_volume_profile`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.strategies.trend_breakout_strategy`

**Purpose:** Calculate volume-weighted average price (VWAP) for trend confirmation.

**Exact API:** {py:obj}`integrations.mt5.domain.strategies.trend_breakout_strategy.TrendBreakoutStrategy.calculate_volume_profile` · **Source:** [integrations/mt5/domain/strategies/trend_breakout_strategy.py:82](../../../../integrations/mt5/domain/strategies/trend_breakout_strategy.py#L82)

**Inputs and outputs:**

- **Args:**

  ```text
  df: Input DataFrame supplying the rows used by this calculation.
  ```

- **Returns:**

  ```text
  VWAP series
  ```

**Observed usage:**

1. [production caller: `signal`](../../../../integrations/mt5/domain/strategies/trend_breakout_strategy.py#L197)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        current_price = df["close"].iloc[-1]
        price_above_sma_fast = current_price > sma_fast.iloc[-1]
        price_above_sma_slow = current_price > sma_slow.iloc[-1]

        # Calculate VWAP
        vwap = self.calculate_volume_profile(df)
        price_above_vwap = current_price > vwap.iloc[-1]

        symbol = self.data.get_symbol()

        # Bullish breakout signal
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `TrendBreakoutStrategy.detect_breakout`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.strategies.trend_breakout_strategy`

**Purpose:** Detect breakout from support or resistance.

**Exact API:** {py:obj}`integrations.mt5.domain.strategies.trend_breakout_strategy.TrendBreakoutStrategy.detect_breakout` · **Source:** [integrations/mt5/domain/strategies/trend_breakout_strategy.py:105](../../../../integrations/mt5/domain/strategies/trend_breakout_strategy.py#L105)

**Inputs and outputs:**

- **Args:**

  ```text
  df: Input DataFrame supplying the rows used by this calculation.
  support: Numeric value used for the support.
  resistance: Numeric value used for the resistance.
  ```

- **Returns:**

  ```text
  Tuple of (is_breakout, direction) where direction is 'bullish' or 'bearish'
  ```

**Observed usage:**

1. [production caller: `signal`](../../../../integrations/mt5/domain/strategies/trend_breakout_strategy.py#L183)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        if support == 0.0 or resistance == 0.0:
            symbol = self.data.get_symbol()
            return symbol, Signal.NONE

            # Detect breakout
        is_breakout, direction = self.detect_breakout(df, support, resistance)

        # Calculate trend strength
        trend_strength = self.calculate_trend_strength(df)

        # Calculate moving averages for confirmation
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `TrendBreakoutStrategy.identify_consolidation`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.strategies.trend_breakout_strategy`

**Purpose:** Identify if market is in consolidation (ranging).

**Exact API:** {py:obj}`integrations.mt5.domain.strategies.trend_breakout_strategy.TrendBreakoutStrategy.identify_consolidation` · **Source:** [integrations/mt5/domain/strategies/trend_breakout_strategy.py:58](../../../../integrations/mt5/domain/strategies/trend_breakout_strategy.py#L58)

**Inputs and outputs:**

- **Args:**

  ```text
  df: Input DataFrame supplying the rows used by this calculation.
  ```

- **Returns:**

  ```text
  True if market is consolidating, False otherwise
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = TrendBreakoutStrategy(...)
result = instance.identify_consolidation(df=...)
```

**Lifecycle context:** This callable participates in `TrendBreakoutStrategy`: Trend Breakout Strategy. Related public lifecycle methods: {py:obj}`integrations.mt5.domain.strategies.trend_breakout_strategy.TrendBreakoutStrategy.identify_support_resistance`, {py:obj}`integrations.mt5.domain.strategies.trend_breakout_strategy.TrendBreakoutStrategy.identify_consolidation`, {py:obj}`integrations.mt5.domain.strategies.trend_breakout_strategy.TrendBreakoutStrategy.calculate_volume_profile`, {py:obj}`integrations.mt5.domain.strategies.trend_breakout_strategy.TrendBreakoutStrategy.detect_breakout`, {py:obj}`integrations.mt5.domain.strategies.trend_breakout_strategy.TrendBreakoutStrategy.calculate_trend_strength`, {py:obj}`integrations.mt5.domain.strategies.trend_breakout_strategy.TrendBreakoutStrategy.signal`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `TrendBreakoutStrategy.identify_support_resistance`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.strategies.trend_breakout_strategy`

**Purpose:** Identify support and resistance levels.

**Exact API:** {py:obj}`integrations.mt5.domain.strategies.trend_breakout_strategy.TrendBreakoutStrategy.identify_support_resistance` · **Source:** [integrations/mt5/domain/strategies/trend_breakout_strategy.py:36](../../../../integrations/mt5/domain/strategies/trend_breakout_strategy.py#L36)

**Inputs and outputs:**

- **Args:**

  ```text
  df: Input DataFrame supplying the rows used by this calculation.
  ```

- **Returns:**

  ```text
  Tuple of (support_level, resistance_level)
  ```

**Observed usage:**

1. [production caller: `signal`](../../../../integrations/mt5/domain/strategies/trend_breakout_strategy.py#L176)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        if len(df) < self.lookback_period + 5:
            symbol = self.data.get_symbol()
            return symbol, Signal.NONE

            # Identify support and resistance
        support, resistance = self.identify_support_resistance(df)

        if support == 0.0 or resistance == 0.0:
            symbol = self.data.get_symbol()
            return symbol, Signal.NONE

# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `TrendBreakoutStrategy.signal`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.strategies.trend_breakout_strategy`

**Purpose:** Generate trading signal based on trend breakouts.

**Exact API:** {py:obj}`integrations.mt5.domain.strategies.trend_breakout_strategy.TrendBreakoutStrategy.signal` · **Source:** [integrations/mt5/domain/strategies/trend_breakout_strategy.py:163](../../../../integrations/mt5/domain/strategies/trend_breakout_strategy.py#L163)

**Inputs and outputs:**

- **Returns:**

  ```text
  Tuple of (symbol, signal)
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = TrendBreakoutStrategy(...)
result = instance.signal()
```

**Lifecycle context:** This callable participates in `TrendBreakoutStrategy`: Trend Breakout Strategy. Related public lifecycle methods: {py:obj}`integrations.mt5.domain.strategies.trend_breakout_strategy.TrendBreakoutStrategy.identify_support_resistance`, {py:obj}`integrations.mt5.domain.strategies.trend_breakout_strategy.TrendBreakoutStrategy.identify_consolidation`, {py:obj}`integrations.mt5.domain.strategies.trend_breakout_strategy.TrendBreakoutStrategy.calculate_volume_profile`, {py:obj}`integrations.mt5.domain.strategies.trend_breakout_strategy.TrendBreakoutStrategy.detect_breakout`, {py:obj}`integrations.mt5.domain.strategies.trend_breakout_strategy.TrendBreakoutStrategy.calculate_trend_strength`, {py:obj}`integrations.mt5.domain.strategies.trend_breakout_strategy.TrendBreakoutStrategy.signal`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`
