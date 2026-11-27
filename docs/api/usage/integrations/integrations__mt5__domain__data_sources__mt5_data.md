# Integrations · `mt5.domain.data_sources.mt5_data`

This page contains 4 public callable records owned by `integrations.mt5.domain.data_sources.mt5_data`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `MT5Data`

**Kind:** class · **Status:** stable · **Owner:** `integrations.mt5.domain.data_sources.mt5_data`

**Purpose:** Market-data source that reads recent rates from the MetaTrader terminal.

**Exact API:** {py:obj}`integrations.mt5.domain.data_sources.mt5_data.MT5Data` · **Source:** [integrations/mt5/domain/data_sources/mt5_data.py:7](../../../../integrations/mt5/domain/data_sources/mt5_data.py#L7)

**Inputs and outputs:**

**Observed usage:**

1. [test fixture: `test_get_data_requests_configured_symbol_and_converts_epoch_bar_times`](../../../../tests/unit/integrations/test_mt5_data_source.py#L30)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    def copy_rates(symbol: str, timeframe: int, start: int, count: int) -> list[dict[str, int]]:
        calls.append((symbol, timeframe, start, count))
        return [{"time": 1_700_000_000, "open": 100}, {"time": 1_700_000_060, "open": 101}]

    monkeypatch.setattr(mt5, "copy_rates_from_pos", copy_rates, raising=False)
    source = MT5Data("US100.cash", 5)

    bars = source.get_data()

    assert calls == [("US100.cash", 5, 0, 1000)]
    assert source.get_symbol() == "US100.cash"
# … caller assertions omitted …
```

2. [test fixture: `test_get_data_preserves_empty_result_without_inventing_bar_columns`](../../../../tests/unit/integrations/test_mt5_data_source.py#L43)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_get_data_preserves_empty_result_without_inventing_bar_columns(monkeypatch) -> None:
    monkeypatch.setattr(mt5, "copy_rates_from_pos", lambda *_args: None, raising=False)

    bars = MT5Data("US500", 60).get_data()

    assert bars.empty
    assert list(bars.columns) == []
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `MT5Data`

**Kind:** class · **Status:** stable · **Owner:** `integrations.mt5.domain.data_sources.mt5_data`

**Purpose:** Market-data source that reads recent rates from the MetaTrader terminal.

**Exact API:** {py:obj}`integrations.mt5.domain.data_sources.mt5_data.MT5Data` · **Source:** [integrations/mt5/domain/data_sources/mt5_data.py:7](../../../../integrations/mt5/domain/data_sources/mt5_data.py#L7)

**Inputs and outputs:**

**Observed usage:**

1. [test fixture: `test_get_data_requests_configured_symbol_and_converts_epoch_bar_times`](../../../../tests/unit/integrations/test_mt5_data_source.py#L30)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    def copy_rates(symbol: str, timeframe: int, start: int, count: int) -> list[dict[str, int]]:
        calls.append((symbol, timeframe, start, count))
        return [{"time": 1_700_000_000, "open": 100}, {"time": 1_700_000_060, "open": 101}]

    monkeypatch.setattr(mt5, "copy_rates_from_pos", copy_rates, raising=False)
    source = MT5Data("US100.cash", 5)

    bars = source.get_data()

    assert calls == [("US100.cash", 5, 0, 1000)]
    assert source.get_symbol() == "US100.cash"
# … caller assertions omitted …
```

2. [test fixture: `test_get_data_preserves_empty_result_without_inventing_bar_columns`](../../../../tests/unit/integrations/test_mt5_data_source.py#L43)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_get_data_preserves_empty_result_without_inventing_bar_columns(monkeypatch) -> None:
    monkeypatch.setattr(mt5, "copy_rates_from_pos", lambda *_args: None, raising=False)

    bars = MT5Data("US500", 60).get_data()

    assert bars.empty
    assert list(bars.columns) == []
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

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

**Observed usage:**

1. [test fixture: `test_get_data_requests_configured_symbol_and_converts_epoch_bar_times`](../../../../tests/unit/integrations/test_mt5_data_source.py#L32)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        return [{"time": 1_700_000_000, "open": 100}, {"time": 1_700_000_060, "open": 101}]

    monkeypatch.setattr(mt5, "copy_rates_from_pos", copy_rates, raising=False)
    source = MT5Data("US100.cash", 5)

    bars = source.get_data()

    assert calls == [("US100.cash", 5, 0, 1000)]
    assert source.get_symbol() == "US100.cash"
    assert list(bars.columns) == ["time", "open"]
    assert bars["time"].tolist() == list(pd.to_datetime([1_700_000_000, 1_700_000_060], unit="s"))
```

2. [test fixture: `test_get_data_preserves_empty_result_without_inventing_bar_columns`](../../../../tests/unit/integrations/test_mt5_data_source.py#L43)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_get_data_preserves_empty_result_without_inventing_bar_columns(monkeypatch) -> None:
    monkeypatch.setattr(mt5, "copy_rates_from_pos", lambda *_args: None, raising=False)

    bars = MT5Data("US500", 60).get_data()

    assert bars.empty
    assert list(bars.columns) == []
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

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

**Observed usage:**

1. [test fixture: `test_get_data_requests_configured_symbol_and_converts_epoch_bar_times`](../../../../tests/unit/integrations/test_mt5_data_source.py#L35)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    source = MT5Data("US100.cash", 5)

    bars = source.get_data()

    assert calls == [("US100.cash", 5, 0, 1000)]
    assert source.get_symbol() == "US100.cash"
    assert list(bars.columns) == ["time", "open"]
    assert bars["time"].tolist() == list(pd.to_datetime([1_700_000_000, 1_700_000_060], unit="s"))
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`
