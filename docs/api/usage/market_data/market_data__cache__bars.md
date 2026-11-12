# Market data · `cache.bars`

This page contains 6 public callable records owned by `market_data.cache.bars`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `bar_cache_is_complete`

**Kind:** function · **Status:** stable · **Owner:** `market_data.cache.bars`

**Purpose:** Check for a non-empty parquet and structurally valid completion manifest.

**Exact API:** {py:obj}`market_data.cache.bars.bar_cache_is_complete` · **Source:** [market_data/cache/bars.py:50](../../../../market_data/cache/bars.py#L50)

**Inputs and outputs:**

- **Args:**

  ```text
  cache_path: Path or filename identifying the cache.
  ```

- **Returns:**

  ```text
  Whether bar cache is complete meets the requested condition.
  ```

**Observed usage:**

1. [test fixture: `test_bar_cache_write_failure_preserves_completed_cache`](../../../../tests/integration/test_bar_cache_manifest.py#L30)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        "transform": BAR_CACHE_TRANSFORM_ID,
        "cache_id": "cache:original",
        "inputs": {},
    }
    write_bar_cache(cache_path, original, identity)
    assert bar_cache_is_complete(cache_path)
    original_bytes = cache_path.read_bytes()
    manifest_path = Path(f"{cache_path}.manifest.json")
    original_manifest = manifest_path.read_bytes()

    def fail_parquet_write(self: pd.DataFrame, path: str | Path, **kwargs: object) -> None:
# … caller assertions omitted …
```

2. [test fixture: `test_failed_manifest_publish_cannot_reuse_replaced_parquet`](../../../../tests/integration/test_bar_cache_manifest.py#L63)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        "transform": BAR_CACHE_TRANSFORM_ID,
        "cache_id": "cache:manifest-failure",
        "inputs": {},
    }
    write_bar_cache(cache_path, original, identity)
    assert bar_cache_is_complete(cache_path)

    def fail_manifest_write(*_args: object, **_kwargs: object) -> None:
        raise OSError("simulated interrupted manifest publish")

    monkeypatch.setattr("market_data.cache.storage.write_json_atomic", fail_manifest_write)
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `bar_cache_manifest_path`

**Kind:** function · **Status:** stable · **Owner:** `market_data.cache.bars`

**Purpose:** Return the completion manifest path associated with a bar parquet.

**Exact API:** {py:obj}`market_data.cache.bars.bar_cache_manifest_path` · **Source:** [market_data/cache/bars.py:38](../../../../market_data/cache/bars.py#L38)

**Inputs and outputs:**

- **Args:**

  ```text
  cache_path: Path or filename identifying the cache.
  ```

- **Returns:**

  ```text
  Path returned by ``bar_cache_manifest_path``.
  ```

**Observed usage:**

1. [test fixture: `fake_run_pipeline`](../../../../tests/unit/experiments/test_triton_prebuild_cache.py#L60)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
                        / dataset_name
                        / f"{symbol}_{timeframe}_{BAR_CACHE_VERSION}.parquet"
                    )
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(b"prepared")
                    bar_cache_manifest_path(path).write_text(
                        json.dumps(
                            {
                                "identity": {
                                    "schema_version": BAR_CACHE_MANIFEST_SCHEMA_VERSION,
                                    "transform": BAR_CACHE_TRANSFORM_ID,
# … caller assertions omitted …
```

2. [production caller: `bar_cache_is_complete`](../../../../market_data/cache/bars.py#L61)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def bar_cache_is_complete(cache_path: str | Path) -> bool:
    if not parquet_cache_is_complete(cache_path):
        return False
    manifest = json.loads(bar_cache_manifest_path(cache_path).read_text(encoding="utf-8"))
    return bool(
        manifest["identity"].get("schema_version") == BAR_CACHE_MANIFEST_SCHEMA_VERSION
        and manifest["identity"].get("transform") == BAR_CACHE_TRANSFORM_ID
        and manifest["row_count"] > 0
    )
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `bar_cache_path`

**Kind:** function · **Status:** stable · **Owner:** `market_data.cache.bars`

**Purpose:** Build the canonical bar-cache path from its semantic cache version.

**Exact API:** {py:obj}`market_data.cache.bars.bar_cache_path` · **Source:** [market_data/cache/bars.py:23](../../../../market_data/cache/bars.py#L23)

**Inputs and outputs:**

- **Args:**

  ```text
  cache_dir: Directory used to store or read cached data.
  symbol: Text or path value identifying the symbol.
  timeframe: Text or path value identifying the timeframe.
  cache_version: Text or path value identifying the cache version.
  ```

- **Returns:**

  ```text
  Path returned by ``bar_cache_path``.
  ```

**Observed usage:**

1. [production caller: `run_pipeline`](../../../../market_data/loading/market_data_ingestion.py#L147)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            m1_clean = clean(m1_raw, tz=tz)
            m1_full = add_session_labels(m1_clean, tz=tz, ny_end=ny_end)
            m1_full = add_session_id(m1_full)
            for tf in cfg.data.timeframes:
                tf = str(tf)
                cp = bar_cache_path(part_cache, str(symbol), tf, BAR_CACHE_VERSION)
                native_file = timeframe_files.get(tf, {}).get(symbol)
                if tf == "M1":
                    source_path = m1_path
                    source_identity = f"native:{input_hash(source_path)}{grid_identity}"
                elif native_file:
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `build_bar_cache_identity`

**Kind:** function · **Status:** stable · **Owner:** `market_data.cache.bars`

**Purpose:** Describe every source and configuration input that changes cached bars.

**Exact API:** {py:obj}`market_data.cache.bars.build_bar_cache_identity` · **Source:** [market_data/cache/bars.py:69](../../../../market_data/cache/bars.py#L69)

**Inputs and outputs:**

- **Args:**

  ```text
  dataset_id: Text or path value identifying the dataset id.
  symbol: Text or path value identifying the symbol.
  timeframe: Text or path value identifying the timeframe.
  source_identity: Text or path value identifying the source identity.
  timezone: Text or path value identifying the timezone.
  ny_session_end: Text or path value identifying the ny session end.
  timestamp_convention: Text or path value identifying the timestamp convention.
  price_grid_identity: Price grid identity used by the operation described above.
  ```

- **Returns:**

  ```text
  Mapping from ``str`` keys to ``Any`` values.
  ```

**Observed usage:**

1. [production caller: `run_pipeline`](../../../../market_data/loading/market_data_ingestion.py#L172)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
                        )
                    source_path = m1_path
                    source_identity = (
                        f"derived-from-M1:{input_hash(source_path)}:{tf}{grid_identity}"
                    )
                cache_identity = build_bar_cache_identity(
                    dataset_id=dataset_name,
                    symbol=str(symbol),
                    timeframe=tf,
                    source_identity=source_identity,
                    timezone=tz,
                    ny_session_end=ny_end,
                    timestamp_convention=timestamp_convention,
                    price_grid_identity=(
                        price_grid_identity(grid_increment) if grid_increment is not None else None
                    ),
                )
                cached_frame = None if force else load_bar_cache(cp, cache_identity)
                if cached_frame is not None:
                    df = cached_frame
                else:
                    if tf == "M1":
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `load_bar_cache`

**Kind:** function · **Status:** stable · **Owner:** `market_data.cache.bars`

**Purpose:** Load a complete cache only when its semantic identity and shape match.

**Exact API:** {py:obj}`market_data.cache.bars.load_bar_cache` · **Source:** [market_data/cache/bars.py:118](../../../../market_data/cache/bars.py#L118)

**Inputs and outputs:**

- **Args:**

  ```text
  cache_path: Path or filename identifying the cache.
  expected_identity: Key-value data used for the expected identity.
  ```

- **Returns:**

  ```text
  DataFrame returned by ``load_bar_cache``.
  ```

**Observed usage:**

1. [test fixture: `test_bar_cache_write_failure_preserves_completed_cache`](../../../../tests/integration/test_bar_cache_manifest.py#L45)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        write_bar_cache(cache_path, original.assign(close=[0.0, 0.0]), {"cache_id": "new"})

    assert cache_path.read_bytes() == original_bytes
    assert manifest_path.read_bytes() == original_manifest
    assert bar_cache_is_complete(cache_path)
    loaded = load_bar_cache(cache_path, identity)
    assert loaded is not None
    pd.testing.assert_frame_equal(loaded, original, check_freq=False)
```

2. [test fixture: `test_failed_manifest_publish_cannot_reuse_replaced_parquet`](../../../../tests/integration/test_bar_cache_manifest.py#L73)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    monkeypatch.setattr("market_data.cache.storage.write_json_atomic", fail_manifest_write)
    with pytest.raises(OSError, match="interrupted manifest"):
        write_bar_cache(cache_path, original.assign(close=[90.0, 91.0]), identity)

    assert not bar_cache_is_complete(cache_path)
    assert load_bar_cache(cache_path, identity) is None
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `write_bar_cache`

**Kind:** function · **Status:** stable · **Owner:** `market_data.cache.bars`

**Purpose:** Atomically publish a parquet cache, then its completion manifest.

**Exact API:** {py:obj}`market_data.cache.bars.write_bar_cache` · **Source:** [market_data/cache/bars.py:133](../../../../market_data/cache/bars.py#L133)

**Inputs and outputs:**

- **Args:**

  ```text
  cache_path: Path or filename identifying the cache.
  frame: Input data frame to process.
  identity: Key-value data used for the identity.
  ```

- **Returns:**

  ```text
  Path returned by ``write_bar_cache``.
  ```

**Observed usage:**

1. [test fixture: `test_bar_cache_write_failure_preserves_completed_cache`](../../../../tests/integration/test_bar_cache_manifest.py#L29)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        "schema_version": BAR_CACHE_MANIFEST_SCHEMA_VERSION,
        "transform": BAR_CACHE_TRANSFORM_ID,
        "cache_id": "cache:original",
        "inputs": {},
    }
    write_bar_cache(cache_path, original, identity)
    assert bar_cache_is_complete(cache_path)
    original_bytes = cache_path.read_bytes()
    manifest_path = Path(f"{cache_path}.manifest.json")
    original_manifest = manifest_path.read_bytes()

# … caller assertions omitted …
```

2. [test fixture: `test_failed_manifest_publish_cannot_reuse_replaced_parquet`](../../../../tests/integration/test_bar_cache_manifest.py#L62)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        "schema_version": BAR_CACHE_MANIFEST_SCHEMA_VERSION,
        "transform": BAR_CACHE_TRANSFORM_ID,
        "cache_id": "cache:manifest-failure",
        "inputs": {},
    }
    write_bar_cache(cache_path, original, identity)
    assert bar_cache_is_complete(cache_path)

    def fail_manifest_write(*_args: object, **_kwargs: object) -> None:
        raise OSError("simulated interrupted manifest publish")

# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`
