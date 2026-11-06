# Market data · `loading.bars`

This page contains 3 public callable records owned by `market_data.loading.bars`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `load_bars`

**Kind:** function · **Status:** stable · **Owner:** `market_data.loading.bars`

**Purpose:** Parse a raw MT5 bar CSV into a DataFrame with a UTC-aware DatetimeIndex.

**Exact API:** {py:obj}`market_data.loading.bars.load_bars` · **Source:** [market_data/loading/bars.py:22](../../../../market_data/loading/bars.py#L22)

**Inputs and outputs:**

- **Args:**

  ```text
  path: Path to the input file or directory.
  ```

- **Returns:**

  ```text
  DataFrame returned by ``load_bars``.
  ```

**Observed usage:**

1. [test fixture: `test_load_bars_accepts_date_only_daily_export`](../../../../tests/integration/test_loader.py#L18)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_load_bars_accepts_date_only_daily_export(tmp_path: Path) -> None:
    path = tmp_path / "daily.tsv"
    path.write_text(
        "<DATE>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>\n"
        "2025.01.02\t10\t12\t9\t11\t100\t0\t2\n",
        encoding="utf-8",
    )

    bars = load_bars(path)

    assert bars.index.tolist() == [pd.Timestamp("2025-01-02 00:00:00")]
    assert bars.iloc[0]["close"] == 11
    assert bars.iloc[0]["spread"] == 2
```

2. [test fixture: `test_load_bars_keeps_intraday_time_from_export`](../../../../tests/integration/test_loader.py#L33)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_load_bars_keeps_intraday_time_from_export(tmp_path: Path) -> None:
    path = tmp_path / "minute.tsv"
    path.write_text(
        "<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>\n"
        "2025.01.02\t09:31:00\t10\t12\t9\t11\t100\t0\t2\n",
        encoding="utf-8",
    )

    bars = load_bars(path)

    assert bars.index.tolist() == [pd.Timestamp("2025-01-02 09:31:00")]
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `iter_ticks_chunks`

**Kind:** function · **Status:** stable · **Owner:** `market_data.loading.bars`

**Purpose:** Stream a raw MT5 tick CSV in bounded-size chunks.

**Exact API:** {py:obj}`market_data.loading.bars.iter_ticks_chunks` · **Source:** [market_data/loading/bars.py:108](../../../../market_data/loading/bars.py#L108)

**Inputs and outputs:**

- **Args:**

  ```text
  path: Path to the input file or directory.
  chunksize: Numeric value used for the chunksize.
  ```

- **Yields:**

  ```text
  Raw ``DataFrame`` chunks with ``date``, ``time``, ``bid``, and ``ask``
  columns. Date and time remain strings so callers can carry forward-fill
  state across chunk boundaries while parsing timestamps.
  ```

**Observed usage:**

1. [production caller: `build_tick_book`](../../../../market_data/loading/ticks.py#L991)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    last_bid = np.nan
    last_ask = np.nan
    n_rows_total = 0
    n_rows_kept = 0

    for raw_chunk in iter_ticks_chunks(path, chunksize=chunksize):
        n_rows_total += len(raw_chunk)
        if diagnostics is not None:
            diagnostics.source_rows_read += len(raw_chunk)

        # Chunk-local datetime parse (bounded memory) — Etc/GMT-3 etc. are
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `load_bars`

**Kind:** function · **Status:** stable · **Owner:** `market_data.loading.bars`

**Purpose:** Parse a raw MT5 bar CSV into a DataFrame with a UTC-aware DatetimeIndex.

**Exact API:** {py:obj}`market_data.loading.bars.load_bars` · **Source:** [market_data/loading/bars.py:22](../../../../market_data/loading/bars.py#L22)

**Inputs and outputs:**

- **Args:**

  ```text
  path: Path to the input file or directory.
  ```

- **Returns:**

  ```text
  DataFrame returned by ``load_bars``.
  ```

**Observed usage:**

1. [test fixture: `test_load_bars_accepts_date_only_daily_export`](../../../../tests/integration/test_loader.py#L18)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_load_bars_accepts_date_only_daily_export(tmp_path: Path) -> None:
    path = tmp_path / "daily.tsv"
    path.write_text(
        "<DATE>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>\n"
        "2025.01.02\t10\t12\t9\t11\t100\t0\t2\n",
        encoding="utf-8",
    )

    bars = load_bars(path)

    assert bars.index.tolist() == [pd.Timestamp("2025-01-02 00:00:00")]
    assert bars.iloc[0]["close"] == 11
    assert bars.iloc[0]["spread"] == 2
```

2. [test fixture: `test_load_bars_keeps_intraday_time_from_export`](../../../../tests/integration/test_loader.py#L33)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_load_bars_keeps_intraday_time_from_export(tmp_path: Path) -> None:
    path = tmp_path / "minute.tsv"
    path.write_text(
        "<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>\n"
        "2025.01.02\t09:31:00\t10\t12\t9\t11\t100\t0\t2\n",
        encoding="utf-8",
    )

    bars = load_bars(path)

    assert bars.index.tolist() == [pd.Timestamp("2025-01-02 09:31:00")]
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`
