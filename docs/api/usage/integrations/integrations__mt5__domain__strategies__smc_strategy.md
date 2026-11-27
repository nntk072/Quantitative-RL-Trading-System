# Integrations · `mt5.domain.strategies.smc_strategy`

This page contains 6 public callable records owned by `integrations.mt5.domain.strategies.smc_strategy`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `SMCStrategy`

**Kind:** class · **Status:** stable · **Owner:** `integrations.mt5.domain.strategies.smc_strategy`

**Purpose:** Smart Money Concepts (SMC) Strategy.

**Exact API:** {py:obj}`integrations.mt5.domain.strategies.smc_strategy.SMCStrategy` · **Source:** [integrations/mt5/domain/strategies/smc_strategy.py:7](../../../../integrations/mt5/domain/strategies/smc_strategy.py#L7)

**Observed usage:**

1. [test fixture: `test_smc_order_blocks_require_a_strong_candle_followed_by_consolidation`](../../../../tests/unit/integrations/test_mt5_strategies.py#L82)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_smc_order_blocks_require_a_strong_candle_followed_by_consolidation() -> None:
    strategy = SMCStrategy(PriceData(pd.DataFrame()), order_block_periods=1)
    frame = pd.DataFrame(
        {
            "open": [10.0, 10.0, 20.0],
            "high": [11.0, 20.0, 21.0],
            "low": [9.0, 10.0, 19.0],
# … caller assertions omitted …
```

2. [test fixture: `test_smc_fair_value_gaps_detect_bullish_and_bearish_separation`](../../../../tests/unit/integrations/test_mt5_strategies.py#L116)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_smc_fair_value_gaps_detect_bullish_and_bearish_separation(
    frame: pd.DataFrame, bullish_at: int | None, bearish_at: int | None
) -> None:
    bullish, bearish = SMCStrategy(PriceData(frame)).identify_fair_value_gaps(frame)

    assert (bullish_at is not None) is bool(bullish.any())
    assert (bearish_at is not None) is bool(bearish.any())
    if bullish_at is not None:
        assert bullish.iloc[bullish_at]
    if bearish_at is not None:
        assert bearish.iloc[bearish_at]
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `SMCStrategy`

**Kind:** class · **Status:** stable · **Owner:** `integrations.mt5.domain.strategies.smc_strategy`

**Purpose:** Smart Money Concepts (SMC) Strategy.

**Exact API:** {py:obj}`integrations.mt5.domain.strategies.smc_strategy.SMCStrategy` · **Source:** [integrations/mt5/domain/strategies/smc_strategy.py:7](../../../../integrations/mt5/domain/strategies/smc_strategy.py#L7)

**Observed usage:**

1. [test fixture: `test_smc_order_blocks_require_a_strong_candle_followed_by_consolidation`](../../../../tests/unit/integrations/test_mt5_strategies.py#L82)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_smc_order_blocks_require_a_strong_candle_followed_by_consolidation() -> None:
    strategy = SMCStrategy(PriceData(pd.DataFrame()), order_block_periods=1)
    frame = pd.DataFrame(
        {
            "open": [10.0, 10.0, 20.0],
            "high": [11.0, 20.0, 21.0],
            "low": [9.0, 10.0, 19.0],
# … caller assertions omitted …
```

2. [test fixture: `test_smc_fair_value_gaps_detect_bullish_and_bearish_separation`](../../../../tests/unit/integrations/test_mt5_strategies.py#L116)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_smc_fair_value_gaps_detect_bullish_and_bearish_separation(
    frame: pd.DataFrame, bullish_at: int | None, bearish_at: int | None
) -> None:
    bullish, bearish = SMCStrategy(PriceData(frame)).identify_fair_value_gaps(frame)

    assert (bullish_at is not None) is bool(bullish.any())
    assert (bearish_at is not None) is bool(bearish.any())
    if bullish_at is not None:
        assert bullish.iloc[bullish_at]
    if bearish_at is not None:
        assert bearish.iloc[bearish_at]
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `SMCStrategy.identify_fair_value_gaps`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.strategies.smc_strategy`

**Purpose:** Identify bullish and bearish Fair Value Gaps (FVG).

**Exact API:** {py:obj}`integrations.mt5.domain.strategies.smc_strategy.SMCStrategy.identify_fair_value_gaps` · **Source:** [integrations/mt5/domain/strategies/smc_strategy.py:74](../../../../integrations/mt5/domain/strategies/smc_strategy.py#L74)

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

1. [test fixture: `test_smc_fair_value_gaps_detect_bullish_and_bearish_separation`](../../../../tests/unit/integrations/test_mt5_strategies.py#L116)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_smc_fair_value_gaps_detect_bullish_and_bearish_separation(
    frame: pd.DataFrame, bullish_at: int | None, bearish_at: int | None
) -> None:
    bullish, bearish = SMCStrategy(PriceData(frame)).identify_fair_value_gaps(frame)

    assert (bullish_at is not None) is bool(bullish.any())
    assert (bearish_at is not None) is bool(bearish.any())
    if bullish_at is not None:
        assert bullish.iloc[bullish_at]
    if bearish_at is not None:
        assert bearish.iloc[bearish_at]
```

2. [production caller: `signal`](../../../../integrations/mt5/domain/strategies/smc_strategy.py#L163)

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

**Exact API:** {py:obj}`integrations.mt5.domain.strategies.smc_strategy.SMCStrategy.identify_market_structure` · **Source:** [integrations/mt5/domain/strategies/smc_strategy.py:108](../../../../integrations/mt5/domain/strategies/smc_strategy.py#L108)

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

1. [test fixture: `test_smc_market_structure_follows_ordered_highs_and_lows`](../../../../tests/unit/integrations/test_mt5_strategies.py#L133)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_smc_market_structure_follows_ordered_highs_and_lows(direction: str) -> None:
    levels: np.ndarray[Any, Any] = np.arange(20, dtype=float)
    if direction == "bearish":
        levels = levels[::-1]
    frame = pd.DataFrame({"high": levels + 1.0, "low": levels})

    assert SMCStrategy(PriceData(frame)).identify_market_structure(frame) == direction
```

2. [production caller: `signal`](../../../../integrations/mt5/domain/strategies/smc_strategy.py#L166)

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

1. [test fixture: `test_smc_detects_bearish_order_block_followed_by_consolidation`](../../../../tests/unit/integrations/test_mt5_strategy_signal_contracts.py#L131)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            "low": [19.0, 9.5, 9.5],
            "close": [20.0, 10.0, 10.0],
        }
    )

    bullish, bearish = strategy.identify_order_blocks(frame)

    assert bearish.iloc[1]
    assert not bullish.any()
```

2. [production caller: `signal`](../../../../integrations/mt5/domain/strategies/smc_strategy.py#L160)

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

**Exact API:** {py:obj}`integrations.mt5.domain.strategies.smc_strategy.SMCStrategy.signal` · **Source:** [integrations/mt5/domain/strategies/smc_strategy.py:147](../../../../integrations/mt5/domain/strategies/smc_strategy.py#L147)

**Inputs and outputs:**

- **Returns:**

  ```text
  Tuple of (symbol, signal)
  ```

**Observed usage:**

1. [test fixture: `test_trend_breakout_signal_requires_breakout_trend_and_moving_average_alignment`](../../../../tests/unit/integrations/test_mt5_strategy_signal_contracts.py#L76)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    else:
        levels = (float(frame["low"].iloc[-1]) + 0.5, 110.0)
    monkeypatch.setattr(strategy, "identify_support_resistance", lambda _frame: levels)
    monkeypatch.setattr(strategy, "calculate_trend_strength", lambda _frame: 30.0)

    assert strategy.signal() == ("US100", expected)
```

2. [test fixture: `test_trend_continuation_signal_requires_nearby_support_and_volume_confirmation`](../../../../tests/unit/integrations/test_mt5_strategy_signal_contracts.py#L87)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_trend_continuation_signal_requires_nearby_support_and_volume_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame = _bars(np.linspace(90.0, 100.0, 30))
    strategy = TrendBreakoutStrategy(FrameData(frame), lookback_period=20)
    monkeypatch.setattr(strategy, "identify_support_resistance", lambda _frame: (99.8, 120.0))
    monkeypatch.setattr(strategy, "calculate_trend_strength", lambda _frame: 35.0)

    assert strategy.signal() == ("US100", Signal.BUY)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`
