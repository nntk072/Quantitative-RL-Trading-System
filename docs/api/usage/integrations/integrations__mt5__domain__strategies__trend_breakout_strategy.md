# Integrations · `mt5.domain.strategies.trend_breakout_strategy`

This page contains 8 public callable records owned by `integrations.mt5.domain.strategies.trend_breakout_strategy`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `TrendBreakoutStrategy`

**Kind:** class · **Status:** stable · **Owner:** `integrations.mt5.domain.strategies.trend_breakout_strategy`

**Purpose:** Trend Breakout Strategy.

**Exact API:** {py:obj}`integrations.mt5.domain.strategies.trend_breakout_strategy.TrendBreakoutStrategy` · **Source:** [integrations/mt5/domain/strategies/trend_breakout_strategy.py:9](../../../../integrations/mt5/domain/strategies/trend_breakout_strategy.py#L9)

**Observed usage:**

1. [test fixture: `test_trend_breakout_limits_short_history_and_confirms_breakouts`](../../../../tests/unit/integrations/test_mt5_strategies.py#L197)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_trend_breakout_limits_short_history_and_confirms_breakouts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    strategy = TrendBreakoutStrategy(PriceData(pd.DataFrame()), lookback_period=3)
    short = _bars([1.0, 1.0])
    assert strategy.identify_support_resistance(short) == (0.0, 0.0)
    assert not strategy.identify_consolidation(short)
    assert strategy.calculate_trend_strength(short) == 0.0

# … caller assertions omitted …
```

2. [test fixture: `test_trend_breakout_volume_profile_uses_available_volume_or_price_proxy`](../../../../tests/unit/integrations/test_mt5_strategies.py#L220)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_trend_breakout_volume_profile_uses_available_volume_or_price_proxy() -> None:
    strategy = TrendBreakoutStrategy(PriceData(pd.DataFrame()))
    frame = pd.DataFrame({"high": [12.0, 14.0], "low": [8.0, 10.0], "close": [10.0, 12.0]})
    typical = (frame["high"] + frame["low"] + frame["close"]) / 3

    expected_proxy = (typical * typical).cumsum() / typical.cumsum()
    pd.testing.assert_series_equal(strategy.calculate_volume_profile(frame), expected_proxy)
    frame["real_volume"] = [2.0, 1.0]
    expected_real = (typical * frame["real_volume"]).cumsum() / frame["real_volume"].cumsum()
    pd.testing.assert_series_equal(strategy.calculate_volume_profile(frame), expected_real)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `TrendBreakoutStrategy`

**Kind:** class · **Status:** stable · **Owner:** `integrations.mt5.domain.strategies.trend_breakout_strategy`

**Purpose:** Trend Breakout Strategy.

**Exact API:** {py:obj}`integrations.mt5.domain.strategies.trend_breakout_strategy.TrendBreakoutStrategy` · **Source:** [integrations/mt5/domain/strategies/trend_breakout_strategy.py:9](../../../../integrations/mt5/domain/strategies/trend_breakout_strategy.py#L9)

**Observed usage:**

1. [test fixture: `test_trend_breakout_limits_short_history_and_confirms_breakouts`](../../../../tests/unit/integrations/test_mt5_strategies.py#L197)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_trend_breakout_limits_short_history_and_confirms_breakouts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    strategy = TrendBreakoutStrategy(PriceData(pd.DataFrame()), lookback_period=3)
    short = _bars([1.0, 1.0])
    assert strategy.identify_support_resistance(short) == (0.0, 0.0)
    assert not strategy.identify_consolidation(short)
    assert strategy.calculate_trend_strength(short) == 0.0

# … caller assertions omitted …
```

2. [test fixture: `test_trend_breakout_volume_profile_uses_available_volume_or_price_proxy`](../../../../tests/unit/integrations/test_mt5_strategies.py#L220)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_trend_breakout_volume_profile_uses_available_volume_or_price_proxy() -> None:
    strategy = TrendBreakoutStrategy(PriceData(pd.DataFrame()))
    frame = pd.DataFrame({"high": [12.0, 14.0], "low": [8.0, 10.0], "close": [10.0, 12.0]})
    typical = (frame["high"] + frame["low"] + frame["close"]) / 3

    expected_proxy = (typical * typical).cumsum() / typical.cumsum()
    pd.testing.assert_series_equal(strategy.calculate_volume_profile(frame), expected_proxy)
    frame["real_volume"] = [2.0, 1.0]
    expected_real = (typical * frame["real_volume"]).cumsum() / frame["real_volume"].cumsum()
    pd.testing.assert_series_equal(strategy.calculate_volume_profile(frame), expected_real)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

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

1. [test fixture: `test_trend_breakout_limits_short_history_and_confirms_breakouts`](../../../../tests/unit/integrations/test_mt5_strategies.py#L201)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
) -> None:
    strategy = TrendBreakoutStrategy(PriceData(pd.DataFrame()), lookback_period=3)
    short = _bars([1.0, 1.0])
    assert strategy.identify_support_resistance(short) == (0.0, 0.0)
    assert not strategy.identify_consolidation(short)
    assert strategy.calculate_trend_strength(short) == 0.0

    frame = pd.DataFrame({"high": [10.0, 10.0], "low": [9.0, 8.8], "close": [9.5, 9.0]})
    assert strategy.detect_breakout(frame, support=8.5, resistance=10.0) == (False, "")
    frame.loc[1, "high"] = 10.1
    assert strategy.detect_breakout(frame, support=8.5, resistance=10.0) == (True, "bullish")
# … caller assertions omitted …
```

2. [test fixture: `test_trend_breakout_levels_consolidation_and_adx_result_paths`](../../../../tests/unit/integrations/test_mt5_strategies.py#L257)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    assert not strategy.identify_consolidation(frame)

    monkeypatch.setattr(
        trend_module, "calculate_adx", lambda *_args, **_kwargs: pd.DataFrame({"adx": [31.0]})
    )
    assert strategy.calculate_trend_strength(_bars([float(i + 1) for i in range(27)])) == 31.0
    monkeypatch.setattr(
        trend_module, "calculate_adx", lambda *_args, **_kwargs: pd.DataFrame({"adx": [np.nan]})
    )
    assert strategy.calculate_trend_strength(_bars([float(i + 1) for i in range(27)])) == 0.0
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

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

1. [test fixture: `test_trend_breakout_volume_profile_uses_available_volume_or_price_proxy`](../../../../tests/unit/integrations/test_mt5_strategies.py#L225)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_trend_breakout_volume_profile_uses_available_volume_or_price_proxy() -> None:
    strategy = TrendBreakoutStrategy(PriceData(pd.DataFrame()))
    frame = pd.DataFrame({"high": [12.0, 14.0], "low": [8.0, 10.0], "close": [10.0, 12.0]})
    typical = (frame["high"] + frame["low"] + frame["close"]) / 3

    expected_proxy = (typical * typical).cumsum() / typical.cumsum()
    pd.testing.assert_series_equal(strategy.calculate_volume_profile(frame), expected_proxy)
    frame["real_volume"] = [2.0, 1.0]
    expected_real = (typical * frame["real_volume"]).cumsum() / frame["real_volume"].cumsum()
    pd.testing.assert_series_equal(strategy.calculate_volume_profile(frame), expected_real)
```

2. [production caller: `signal`](../../../../integrations/mt5/domain/strategies/trend_breakout_strategy.py#L192)

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

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

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

1. [test fixture: `test_trend_breakout_limits_short_history_and_confirms_breakouts`](../../../../tests/unit/integrations/test_mt5_strategies.py#L204)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    assert strategy.identify_support_resistance(short) == (0.0, 0.0)
    assert not strategy.identify_consolidation(short)
    assert strategy.calculate_trend_strength(short) == 0.0

    frame = pd.DataFrame({"high": [10.0, 10.0], "low": [9.0, 8.8], "close": [9.5, 9.0]})
    assert strategy.detect_breakout(frame, support=8.5, resistance=10.0) == (False, "")
    frame.loc[1, "high"] = 10.1
    assert strategy.detect_breakout(frame, support=8.5, resistance=10.0) == (True, "bullish")
    frame.loc[1, "high"] = 10.0
    frame.loc[1, "low"] = 8.0
    assert strategy.detect_breakout(frame, support=8.5, resistance=10.0) == (True, "bearish")
# … caller assertions omitted …
```

2. [production caller: `signal`](../../../../integrations/mt5/domain/strategies/trend_breakout_strategy.py#L178)

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

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

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

**Observed usage:**

1. [test fixture: `test_trend_breakout_limits_short_history_and_confirms_breakouts`](../../../../tests/unit/integrations/test_mt5_strategies.py#L200)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    strategy = TrendBreakoutStrategy(PriceData(pd.DataFrame()), lookback_period=3)
    short = _bars([1.0, 1.0])
    assert strategy.identify_support_resistance(short) == (0.0, 0.0)
    assert not strategy.identify_consolidation(short)
    assert strategy.calculate_trend_strength(short) == 0.0

    frame = pd.DataFrame({"high": [10.0, 10.0], "low": [9.0, 8.8], "close": [9.5, 9.0]})
    assert strategy.detect_breakout(frame, support=8.5, resistance=10.0) == (False, "")
    frame.loc[1, "high"] = 10.1
# … caller assertions omitted …
```

2. [test fixture: `test_trend_breakout_levels_consolidation_and_adx_result_paths`](../../../../tests/unit/integrations/test_mt5_strategies.py#L250)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            "close": [10.0, 10.01, 9.99],
        }
    )

    assert strategy.identify_support_resistance(frame) == (9.97, 10.03)
    assert strategy.identify_consolidation(frame)
    frame.loc[:, "high"] = [12.0, 13.0, 14.0]
    assert not strategy.identify_consolidation(frame)

    monkeypatch.setattr(
        trend_module, "calculate_adx", lambda *_args, **_kwargs: pd.DataFrame({"adx": [31.0]})
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

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

1. [test fixture: `test_trend_breakout_limits_short_history_and_confirms_breakouts`](../../../../tests/unit/integrations/test_mt5_strategies.py#L199)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_trend_breakout_limits_short_history_and_confirms_breakouts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    strategy = TrendBreakoutStrategy(PriceData(pd.DataFrame()), lookback_period=3)
    short = _bars([1.0, 1.0])
    assert strategy.identify_support_resistance(short) == (0.0, 0.0)
    assert not strategy.identify_consolidation(short)
    assert strategy.calculate_trend_strength(short) == 0.0

    frame = pd.DataFrame({"high": [10.0, 10.0], "low": [9.0, 8.8], "close": [9.5, 9.0]})
    assert strategy.detect_breakout(frame, support=8.5, resistance=10.0) == (False, "")
# … caller assertions omitted …
```

2. [test fixture: `test_trend_breakout_levels_consolidation_and_adx_result_paths`](../../../../tests/unit/integrations/test_mt5_strategies.py#L249)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            "low": [9.98, 9.99, 9.97],
            "close": [10.0, 10.01, 9.99],
        }
    )

    assert strategy.identify_support_resistance(frame) == (9.97, 10.03)
    assert strategy.identify_consolidation(frame)
    frame.loc[:, "high"] = [12.0, 13.0, 14.0]
    assert not strategy.identify_consolidation(frame)

    monkeypatch.setattr(
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `TrendBreakoutStrategy.signal`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.strategies.trend_breakout_strategy`

**Purpose:** Generate trading signal based on trend breakouts.

**Exact API:** {py:obj}`integrations.mt5.domain.strategies.trend_breakout_strategy.TrendBreakoutStrategy.signal` · **Source:** [integrations/mt5/domain/strategies/trend_breakout_strategy.py:158](../../../../integrations/mt5/domain/strategies/trend_breakout_strategy.py#L158)

**Inputs and outputs:**

- **Returns:**

  ```text
  Tuple of (symbol, signal)
  ```

**Observed usage:**

1. [test fixture: `test_smc_signal_is_neutral_before_its_minimum_history`](../../../../tests/unit/integrations/test_mt5_strategies.py#L139)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_smc_signal_is_neutral_before_its_minimum_history() -> None:
    strategy = SMCStrategy(PriceData(_bars([1.0] * 24)))

    assert strategy.signal() == ("US100", Signal.NONE)
```

2. [test fixture: `test_trend_breakout_signal_is_neutral_before_minimum_history`](../../../../tests/unit/integrations/test_mt5_strategies.py#L234)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_trend_breakout_signal_is_neutral_before_minimum_history() -> None:
    strategy = TrendBreakoutStrategy(PriceData(_bars([1.0] * 24)), lookback_period=20)

    assert strategy.signal() == ("US100", Signal.NONE)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`
