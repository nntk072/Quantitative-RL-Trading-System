# Integrations · `mt5.domain.strategies.cross_over_strategy`

This page contains 3 public callable records owned by `integrations.mt5.domain.strategies.cross_over_strategy`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `CrossOverStrategy`

**Kind:** class · **Status:** stable · **Owner:** `integrations.mt5.domain.strategies.cross_over_strategy`

**Purpose:** Moving-average crossover strategy for broker-neutral execution.

**Exact API:** {py:obj}`integrations.mt5.domain.strategies.cross_over_strategy.CrossOverStrategy` · **Source:** [integrations/mt5/domain/strategies/cross_over_strategy.py:8](../../../../integrations/mt5/domain/strategies/cross_over_strategy.py#L8)

**Observed usage:**

1. [test fixture: `test_crossover_signal_tracks_latest_moving_average_order`](../../../../tests/unit/integrations/test_mt5_strategies.py#L70)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_crossover_signal_tracks_latest_moving_average_order(
    prices: list[float], expected: Signal
) -> None:
    assert CrossOverStrategy(PriceData(_bars(prices))).signal() == ("US100", expected)
```

2. [test fixture: `test_crossover_signal_is_neutral_without_bars`](../../../../tests/unit/integrations/test_mt5_strategies.py#L74)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_crossover_signal_is_neutral_without_bars() -> None:
    assert CrossOverStrategy(PriceData(pd.DataFrame())).signal() == ("US100", Signal.NONE)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `CrossOverStrategy`

**Kind:** class · **Status:** stable · **Owner:** `integrations.mt5.domain.strategies.cross_over_strategy`

**Purpose:** Moving-average crossover strategy for broker-neutral execution.

**Exact API:** {py:obj}`integrations.mt5.domain.strategies.cross_over_strategy.CrossOverStrategy` · **Source:** [integrations/mt5/domain/strategies/cross_over_strategy.py:8](../../../../integrations/mt5/domain/strategies/cross_over_strategy.py#L8)

**Observed usage:**

1. [test fixture: `test_crossover_signal_tracks_latest_moving_average_order`](../../../../tests/unit/integrations/test_mt5_strategies.py#L70)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_crossover_signal_tracks_latest_moving_average_order(
    prices: list[float], expected: Signal
) -> None:
    assert CrossOverStrategy(PriceData(_bars(prices))).signal() == ("US100", expected)
```

2. [test fixture: `test_crossover_signal_is_neutral_without_bars`](../../../../tests/unit/integrations/test_mt5_strategies.py#L74)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_crossover_signal_is_neutral_without_bars() -> None:
    assert CrossOverStrategy(PriceData(pd.DataFrame())).signal() == ("US100", Signal.NONE)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

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

**Observed usage:**

1. [test fixture: `test_crossover_signal_tracks_latest_moving_average_order`](../../../../tests/unit/integrations/test_mt5_strategies.py#L70)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_crossover_signal_tracks_latest_moving_average_order(
    prices: list[float], expected: Signal
) -> None:
    assert CrossOverStrategy(PriceData(_bars(prices))).signal() == ("US100", expected)
```

2. [test fixture: `test_crossover_signal_is_neutral_without_bars`](../../../../tests/unit/integrations/test_mt5_strategies.py#L74)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_crossover_signal_is_neutral_without_bars() -> None:
    assert CrossOverStrategy(PriceData(pd.DataFrame())).signal() == ("US100", Signal.NONE)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`
