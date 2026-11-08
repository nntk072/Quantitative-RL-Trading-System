# Market data · `cache.ticks`

This page contains 5 public callable records owned by `market_data.cache.ticks`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `build_tick_cache_identity`

**Kind:** function · **Status:** stable · **Owner:** `market_data.cache.ticks`

**Purpose:** Identify source bytes and every setting that changes a TickBook.

**Exact API:** {py:obj}`market_data.cache.ticks.build_tick_cache_identity` · **Source:** [market_data/cache/ticks.py:35](../../../../market_data/cache/ticks.py#L35)

**Inputs and outputs:**

- **Args:**

  ```text
  source_path: Path or filename identifying the source.
  source_sha256: Text or path value identifying the source sha256.
  timezone: Text or path value identifying the timezone.
  session_start: Session start used by the operation described above.
  session_end: Session end used by the operation described above.
  price_grid_identity: Text or path value identifying the price grid identity.
  cache_version: Text or path value identifying the cache version.
  ```

- **Returns:**

  ```text
  Mapping from ``str`` keys to ``Any`` values.
  ```

**Observed usage:**

1. [production caller: `build_tick_book`](../../../../market_data/loading/ticks.py#L973)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    cache_identity: dict[str, Any] | None = None
    if cache_path:
        if diagnostics is not None:
            raise ValueError("pass cache_path=None when collecting TickBook build diagnostics")
        cache_path = Path(cache_path)
        cache_identity = build_tick_cache_identity(
            source_path=path,
            source_sha256=file_sha256(path),
            timezone=tz,
            session_start=session_start,
            session_end=session_end,
            price_grid_identity=price_grid_identity(price_grid_increment),
            cache_version=TICK_CACHE_VERSION,
        )
        cached_frame = None if force else load_tick_cache(cache_path, cache_identity)
        if cached_frame is not None:
            log.info("Loading tick cache: %s", cache_path)
            return TickBook(
                cast(np.ndarray[Any, Any], cached_frame["ts_ns"].to_numpy()),
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `load_tick_cache`

**Kind:** function · **Status:** stable · **Owner:** `market_data.cache.ticks`

**Purpose:** Load a tick cache only when its semantic identity and timestamp order match.

**Exact API:** {py:obj}`market_data.cache.ticks.load_tick_cache` · **Source:** [market_data/cache/ticks.py:100](../../../../market_data/cache/ticks.py#L100)

**Inputs and outputs:**

- **Args:**

  ```text
  cache_path: Path or filename identifying the cache.
  expected_identity: Key-value data used for the expected identity.
  ```

- **Returns:**

  ```text
  DataFrame returned by ``load_tick_cache``.
  ```

**Observed usage:**

1. [production caller: `build_tick_book`](../../../../market_data/loading/ticks.py#L982)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            session_start=session_start,
            session_end=session_end,
            price_grid_identity=price_grid_identity(price_grid_increment),
            cache_version=TICK_CACHE_VERSION,
        )
        cached_frame = None if force else load_tick_cache(cache_path, cache_identity)
        if cached_frame is not None:
            log.info("Loading tick cache: %s", cache_path)
            return TickBook(
                cast(np.ndarray[Any, Any], cached_frame["ts_ns"].to_numpy()),
                cast(np.ndarray[Any, Any], cached_frame["bid"].to_numpy()),
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `tick_cache_is_complete`

**Kind:** function · **Status:** stable · **Owner:** `market_data.cache.ticks`

**Purpose:** Check that a tick parquet has its semantic completion manifest.

**Exact API:** {py:obj}`market_data.cache.ticks.tick_cache_is_complete` · **Source:** [market_data/cache/ticks.py:82](../../../../market_data/cache/ticks.py#L82)

**Inputs and outputs:**

- **Args:**

  ```text
  cache_path: Path or filename identifying the cache.
  ```

- **Returns:**

  ```text
  Whether tick cache is complete meets the requested condition.
  ```

**Observed usage:**

1. [production caller: `main`](../../../../market_data/commands/prebuild_experiment_run_cache.py#L206)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        / (str(dataset_name) if dataset_name is not None else "")
        / tick_cache_filename(symbol, grid_increment, TICK_CACHE_VERSION)
        for dataset_name in cache_sets
        for symbol in cfg.data.symbols
    ]
    missing_ticks = [str(path) for path in tick_cache_paths if not tick_cache_is_complete(path)]
    if missing_ticks:
        raise RuntimeError(f"tick cache build left missing/empty outputs: {missing_ticks}")

    summary = {
        "cache_dir": str(cache_dir.resolve()),
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `tick_cache_manifest_path`

**Kind:** function · **Status:** stable · **Owner:** `market_data.cache.ticks`

**Purpose:** Return the completion manifest path associated with a tick parquet.

**Exact API:** {py:obj}`market_data.cache.ticks.tick_cache_manifest_path` · **Source:** [market_data/cache/ticks.py:23](../../../../market_data/cache/ticks.py#L23)

**Inputs and outputs:**

- **Args:**

  ```text
  cache_path: Path or filename identifying the cache.
  ```

- **Returns:**

  ```text
  Path returned by ``tick_cache_manifest_path``.
  ```

**Observed usage:**

1. [production caller: `tick_cache_is_complete`](../../../../market_data/cache/ticks.py#L93)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def tick_cache_is_complete(cache_path: str | Path) -> bool:
    if not parquet_cache_is_complete(cache_path):
        return False
    manifest = json.loads(tick_cache_manifest_path(cache_path).read_text(encoding="utf-8"))
    return bool(
        manifest["identity"].get("schema_version") == TICK_CACHE_MANIFEST_SCHEMA_VERSION
        and manifest["identity"].get("transform") == TICK_CACHE_TRANSFORM_ID
    )
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `write_tick_cache`

**Kind:** function · **Status:** stable · **Owner:** `market_data.cache.ticks`

**Purpose:** Atomically publish tick arrays and their semantic completion manifest.

**Exact API:** {py:obj}`market_data.cache.ticks.write_tick_cache` · **Source:** [market_data/cache/ticks.py:119](../../../../market_data/cache/ticks.py#L119)

**Inputs and outputs:**

- **Args:**

  ```text
  cache_path: Path or filename identifying the cache.
  frame: Input data frame to process.
  identity: Key-value data used for the identity.
  ```

- **Returns:**

  ```text
  Path returned by ``write_tick_cache``.
  ```

**Observed usage:**

1. [test fixture: `test_tick_cache_writer_rejects_empty_cache`](../../../../tests/unit/market_data/test_ticks.py#L990)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_tick_cache_writer_rejects_empty_cache(tmp_path: Path) -> None:
    cache_path = tmp_path / "empty_ticks.parquet"
    empty = pd.DataFrame(
        {
            "ts_ns": pd.Series(dtype="int64"),
            "bid": pd.Series(dtype="float64"),
            "ask": pd.Series(dtype="float64"),
        }
    )

    with pytest.raises(ValueError, match="empty tick cache"):
        write_tick_cache(cache_path, empty, {"cache_id": "empty"})

    assert not cache_path.exists()
```

2. [production caller: `build_tick_book`](../../../../market_data/loading/ticks.py#L1126)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        # source-row order when several ticks share a millisecond timestamp.
        order = np.argsort(ts_ns, kind="stable")
        ts_ns, bid, ask = ts_ns[order], bid[order], ask[order]

    if cache_path and cache_identity is not None:
        write_tick_cache(
            cache_path,
            pd.DataFrame({"ts_ns": ts_ns, "bid": bid, "ask": ask}),
            cache_identity,
        )
        log.info("Tick cache written: %s (%d ticks)", cache_path, len(ts_ns))

    return TickBook(ts_ns, bid, ask)
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`
