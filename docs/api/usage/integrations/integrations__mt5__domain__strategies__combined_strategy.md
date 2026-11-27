# Integrations · `mt5.domain.strategies.combined_strategy`

This page contains 3 public callable records owned by `integrations.mt5.domain.strategies.combined_strategy`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `CombinedStrategy`

**Kind:** class · **Status:** stable · **Owner:** `integrations.mt5.domain.strategies.combined_strategy`

**Purpose:** Combined Strategy that uses multiple strategies and requires consensus.

**Exact API:** {py:obj}`integrations.mt5.domain.strategies.combined_strategy.CombinedStrategy` · **Source:** [integrations/mt5/domain/strategies/combined_strategy.py:10](../../../../integrations/mt5/domain/strategies/combined_strategy.py#L10)

**Observed usage:**

1. [test fixture: `test_combined_strategy_handles_empty_and_failed_consensus`](../../../../tests/unit/integrations/test_mt5_strategies.py#L144)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_combined_strategy_handles_empty_and_failed_consensus() -> None:
    data = PriceData(_bars([1.0]))
    no_strategies = CombinedStrategy(data, strategies=[])
    assert no_strategies.signal() == ("US100", Signal.NONE)

    combined = CombinedStrategy(data, strategies=[])
    combined.strategies = cast(
        Any,
# … caller assertions omitted …
```

2. [test fixture: `test_combined_strategy_skips_failed_children`](../../../../tests/unit/integrations/test_mt5_strategies.py#L163)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_combined_strategy_skips_failed_children() -> None:
    combined = CombinedStrategy(PriceData(_bars([1.0])), strategies=[])
    combined.strategies = cast(
        Any,
        {
            "failed": SimpleNamespace(signal=lambda: (_ for _ in ()).throw(RuntimeError("failed"))),
            "buy": SimpleNamespace(signal=lambda: ("US100", Signal.BUY)),
        },
    )

    assert combined.signal() == ("US100", Signal.BUY)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `CombinedStrategy`

**Kind:** class · **Status:** stable · **Owner:** `integrations.mt5.domain.strategies.combined_strategy`

**Purpose:** Combined Strategy that uses multiple strategies and requires consensus.

**Exact API:** {py:obj}`integrations.mt5.domain.strategies.combined_strategy.CombinedStrategy` · **Source:** [integrations/mt5/domain/strategies/combined_strategy.py:10](../../../../integrations/mt5/domain/strategies/combined_strategy.py#L10)

**Observed usage:**

1. [test fixture: `test_combined_strategy_handles_empty_and_failed_consensus`](../../../../tests/unit/integrations/test_mt5_strategies.py#L144)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_combined_strategy_handles_empty_and_failed_consensus() -> None:
    data = PriceData(_bars([1.0]))
    no_strategies = CombinedStrategy(data, strategies=[])
    assert no_strategies.signal() == ("US100", Signal.NONE)

    combined = CombinedStrategy(data, strategies=[])
    combined.strategies = cast(
        Any,
# … caller assertions omitted …
```

2. [test fixture: `test_combined_strategy_skips_failed_children`](../../../../tests/unit/integrations/test_mt5_strategies.py#L163)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_combined_strategy_skips_failed_children() -> None:
    combined = CombinedStrategy(PriceData(_bars([1.0])), strategies=[])
    combined.strategies = cast(
        Any,
        {
            "failed": SimpleNamespace(signal=lambda: (_ for _ in ()).throw(RuntimeError("failed"))),
            "buy": SimpleNamespace(signal=lambda: ("US100", Signal.BUY)),
        },
    )

    assert combined.signal() == ("US100", Signal.BUY)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

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

**Observed usage:**

1. [test fixture: `test_combined_strategy_handles_empty_and_failed_consensus`](../../../../tests/unit/integrations/test_mt5_strategies.py#L145)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_combined_strategy_handles_empty_and_failed_consensus() -> None:
    data = PriceData(_bars([1.0]))
    no_strategies = CombinedStrategy(data, strategies=[])
    assert no_strategies.signal() == ("US100", Signal.NONE)

    combined = CombinedStrategy(data, strategies=[])
    combined.strategies = cast(
        Any,
        {
# … caller assertions omitted …
```

2. [test fixture: `test_combined_strategy_skips_failed_children`](../../../../tests/unit/integrations/test_mt5_strategies.py#L172)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_combined_strategy_skips_failed_children() -> None:
    combined = CombinedStrategy(PriceData(_bars([1.0])), strategies=[])
    combined.strategies = cast(
        Any,
        {
            "failed": SimpleNamespace(signal=lambda: (_ for _ in ()).throw(RuntimeError("failed"))),
            "buy": SimpleNamespace(signal=lambda: ("US100", Signal.BUY)),
        },
    )

    assert combined.signal() == ("US100", Signal.BUY)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`
