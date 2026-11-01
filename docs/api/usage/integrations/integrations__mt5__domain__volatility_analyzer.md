# Integrations · `mt5.domain.volatility_analyzer`

This page contains 6 public callable records owned by `integrations.mt5.domain.volatility_analyzer`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `VolatilityAnalyzer`

**Kind:** class · **Status:** stable · **Owner:** `integrations.mt5.domain.volatility_analyzer`

**Purpose:** Analyze symbol volatility using ATR and related metrics.

**Exact API:** {py:obj}`integrations.mt5.domain.volatility_analyzer.VolatilityAnalyzer` · **Source:** [integrations/mt5/domain/volatility_analyzer.py:11](../../../../integrations/mt5/domain/volatility_analyzer.py#L11)

**Observed usage:**

1. [production caller: `select_volatile_symbols`](../../../../integrations/mt5/cli/multi_symbol_trading.py#L106)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
    logger.info(f"Analyzing volatility for {len(candidates)} symbol candidates...")

    try:
        analyzer = VolatilityAnalyzer(
            login=LOGIN, server=SERVER, password=PASSWORD, terminal_path=TERMINAL_PATH
        )

        # Get volatility config
        config = load_config()
        volatility_config = config.get("volatility_config", {})
        min_threshold = volatility_config.get("min_volatility_threshold", 0.5)
# … caller assertions omitted …
```

2. [production caller: `initialize_trading_system`](../../../../integrations/mt5/cli/multi_symbol_trading.py#L204)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        symbols=selected_symbols,
        timeframe=timeframe,
    )

    # Update volatility metrics
    analyzer = VolatilityAnalyzer(
        login=LOGIN, server=SERVER, password=PASSWORD, terminal_path=TERMINAL_PATH
    )
    symbol_manager.update_volatility_metrics(analyzer)

    # Create strategies for each symbol
    strategies: dict[str, TradingStrategy] = {}
    for symbol in selected_symbols:
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `VolatilityAnalyzer.calculate_atr`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.volatility_analyzer`

**Purpose:** Calculate Average True Range (ATR) for the given dataframe.

**Exact API:** {py:obj}`integrations.mt5.domain.volatility_analyzer.VolatilityAnalyzer.calculate_atr` · **Source:** [integrations/mt5/domain/volatility_analyzer.py:50](../../../../integrations/mt5/domain/volatility_analyzer.py#L50)

**Inputs and outputs:**

- **Args:**

  ```text
  df: DataFrame with OHLC data
  ```

- **Returns:**

  ```text
  Average ATR value over the lookback period
  ```

**Observed usage:**

1. [production caller: `calculate_volatility_metrics`](../../../../integrations/mt5/domain/volatility_analyzer.py#L126)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            if len(df) < self.atr_period + self.lookback_period:
                logger.warning(f"Insufficient data for {symbol}")
                return None

                # Calculate ATR
            atr = self.calculate_atr(df)

            # Calculate price range volatility (standard deviation of returns)
            returns = df["close"].pct_change().dropna()
            volatility = returns.std() * np.sqrt(252) if len(returns) > 0 else 0.0  # Annualized

# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `VolatilityAnalyzer.calculate_volatility_metrics`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.volatility_analyzer`

**Purpose:** Calculate volatility metrics for a symbol.

**Exact API:** {py:obj}`integrations.mt5.domain.volatility_analyzer.VolatilityAnalyzer.calculate_volatility_metrics` · **Source:** [integrations/mt5/domain/volatility_analyzer.py:94](../../../../integrations/mt5/domain/volatility_analyzer.py#L94)

**Inputs and outputs:**

- **Args:**

  ```text
  symbol: Trading symbol
  timeframe: MT5 timeframe
  ```

- **Returns:**

  ```text
  Dictionary with volatility metrics
  ```

**Observed usage:**

1. [production caller: `update_volatility_metrics`](../../../../integrations/mt5/domain/multi_symbol_manager.py#L102)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def update_volatility_metrics(self, analyzer: VolatilityAnalyzer) -> None:
    for symbol in self.symbols:
        try:
            metrics = analyzer.calculate_volatility_metrics(symbol, self.timeframe)
            if metrics:
                self.volatility_metrics[symbol] = metrics
        except Exception as e:
            logger.error(f"Error updating volatility metrics for {symbol}: {e}")
```

2. [production caller: `rank_symbols_by_volatility`](../../../../integrations/mt5/domain/volatility_analyzer.py#L170)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def rank_symbols_by_volatility(
    self, symbols: list[str], timeframe: int = mt5.TIMEFRAME_H1
) -> list[dict[str, Any]]:
    results = []

    for symbol in symbols:
        metrics = self.calculate_volatility_metrics(symbol, timeframe)
        if metrics:
            results.append(metrics)

            # Sort by combined score (highest volatility first)
    results.sort(key=lambda x: x["score"], reverse=True)

    return results
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `VolatilityAnalyzer.get_symbol_info`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.volatility_analyzer`

**Purpose:** Get basic information about a symbol.

**Exact API:** {py:obj}`integrations.mt5.domain.volatility_analyzer.VolatilityAnalyzer.get_symbol_info` · **Source:** [integrations/mt5/domain/volatility_analyzer.py:212](../../../../integrations/mt5/domain/volatility_analyzer.py#L212)

**Inputs and outputs:**

- **Args:**

  ```text
  symbol: Trading symbol
  ```

- **Returns:**

  ```text
  Dictionary with symbol information
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = VolatilityAnalyzer(...)
result = instance.get_symbol_info(symbol=...)
```

**Lifecycle context:** This callable participates in `VolatilityAnalyzer`: Analyze symbol volatility using ATR and related metrics. Related public lifecycle methods: {py:obj}`integrations.mt5.domain.volatility_analyzer.VolatilityAnalyzer.calculate_atr`, {py:obj}`integrations.mt5.domain.volatility_analyzer.VolatilityAnalyzer.calculate_volatility_metrics`, {py:obj}`integrations.mt5.domain.volatility_analyzer.VolatilityAnalyzer.rank_symbols_by_volatility`, {py:obj}`integrations.mt5.domain.volatility_analyzer.VolatilityAnalyzer.select_top_volatile_symbols`, {py:obj}`integrations.mt5.domain.volatility_analyzer.VolatilityAnalyzer.get_symbol_info`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `VolatilityAnalyzer.rank_symbols_by_volatility`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.volatility_analyzer`

**Purpose:** Rank symbols by volatility (highest first).

**Exact API:** {py:obj}`integrations.mt5.domain.volatility_analyzer.VolatilityAnalyzer.rank_symbols_by_volatility` · **Source:** [integrations/mt5/domain/volatility_analyzer.py:155](../../../../integrations/mt5/domain/volatility_analyzer.py#L155)

**Inputs and outputs:**

- **Args:**

  ```text
  symbols: List of symbols to analyze
  timeframe: MT5 timeframe for analysis
  ```

- **Returns:**

  ```text
  List of symbol metrics sorted by volatility score (highest first)
  ```

**Observed usage:**

1. [production caller: `select_top_volatile_symbols`](../../../../integrations/mt5/domain/volatility_analyzer.py#L197)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def select_top_volatile_symbols(
    self,
    symbols: list[str],
    max_symbols: int = 3,
    min_volatility_threshold: float = 0.0,
    timeframe: int = mt5.TIMEFRAME_H1,
) -> list[str]:
    ranked = self.rank_symbols_by_volatility(symbols, timeframe)

    # Filter by threshold and take top N
    filtered = [r["symbol"] for r in ranked if r["score"] >= min_volatility_threshold]
    selected = filtered[:max_symbols]

    logger.info(f"Selected {len(selected)} symbols: {selected}")
    for symbol_info in ranked[:max_symbols]:
        logger.info(
            f"  {symbol_info['symbol']}: ATR%={symbol_info['atr_percentage']:.2f}, "
            f"Volatility={symbol_info['volatility']:.4f}, Score={symbol_info['score']:.4f}"
        )

    return selected
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `VolatilityAnalyzer.select_top_volatile_symbols`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.volatility_analyzer`

**Purpose:** Select top N most volatile symbols.

**Exact API:** {py:obj}`integrations.mt5.domain.volatility_analyzer.VolatilityAnalyzer.select_top_volatile_symbols` · **Source:** [integrations/mt5/domain/volatility_analyzer.py:179](../../../../integrations/mt5/domain/volatility_analyzer.py#L179)

**Inputs and outputs:**

- **Args:**

  ```text
  symbols: List of symbols to analyze
  max_symbols: Maximum number of symbols to select (default: 3)
  min_volatility_threshold: Minimum volatility score threshold
  timeframe: MT5 timeframe for analysis
  ```

- **Returns:**

  ```text
  List of top volatile symbol names
  ```

**Observed usage:**

1. [production caller: `select_volatile_symbols`](../../../../integrations/mt5/cli/multi_symbol_trading.py#L116)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        config = load_config()
        volatility_config = config.get("volatility_config", {})
        min_threshold = volatility_config.get("min_volatility_threshold", 0.5)

        # Select top volatile symbols
        selected = analyzer.select_top_volatile_symbols(
            symbols=candidates, max_symbols=max_symbols, min_volatility_threshold=min_threshold
        )

        return selected

    except Exception as e:
        logger.exception(f"Error selecting volatile symbols: {e}")
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`
