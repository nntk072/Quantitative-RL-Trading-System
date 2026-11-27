# Market data · `cache.storage`

This page contains 6 public callable records owned by `market_data.cache.storage`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `cache_is_complete`

**Kind:** function · **Status:** stable · **Owner:** `market_data.cache.storage`

**Purpose:** Return whether a cache entry has a valid completion marker.

**Exact API:** {py:obj}`market_data.cache.storage.cache_is_complete` · **Source:** [market_data/cache/storage.py:42](../../../../market_data/cache/storage.py#L42)

**Inputs and outputs:**

- **Args:**

  ```text
  entry: Entry used by the operation described above.
  ```

- **Returns:**

  ```text
  Whether cache is complete meets the requested condition.
  ```

**Observed usage:**

1. [test fixture: `test_directory_completion_marker_is_written_atomically`](../../../../tests/unit/market_data/test_cache_storage_contract.py#L36)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_directory_completion_marker_is_written_atomically(tmp_path: Path) -> None:
    entry = tmp_path / "cache-entry"

    assert mark_cache_complete(entry, {"identity": "fixture"}) == entry

    assert cache_is_complete(entry)
    assert cache_metadata_path(entry).read_text(encoding="utf-8").find("fixture") >= 0
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `load_parquet_cache`

**Kind:** function · **Status:** stable · **Owner:** `market_data.cache.storage`

**Purpose:** Load a parquet cache only when identity and recorded ordering still match.

**Exact API:** {py:obj}`market_data.cache.storage.load_parquet_cache` · **Source:** [market_data/cache/storage.py:131](../../../../market_data/cache/storage.py#L131)

**Inputs and outputs:**

- **Args:**

  ```text
  cache_path: Path or filename identifying the cache.
  expected_identity: Key-value data used for the expected identity.
  ordered_column: Ordered column used by the operation described above.
  unique_order: Whether to enable or require the unique order.
  ```

- **Returns:**

  ```text
  DataFrame returned by ``load_parquet_cache``.
  ```

**Observed usage:**

1. [test fixture: `test_parquet_cache_rejects_duplicate_order_when_requested`](../../../../tests/integration/test_bar_cache_manifest.py#L136)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_parquet_cache_rejects_duplicate_order_when_requested(tmp_path: Path) -> None:
    cache_path = tmp_path / "ordered.parquet"
    identity = {"cache_id": "ordered"}
    frame = pd.DataFrame({"ts_ns": [1, 1, 2], "bid": [100.0, 100.1, 100.2]})
    write_parquet_cache(cache_path, frame, identity, index=False, ordered_column="ts_ns")

    assert (
        load_parquet_cache(cache_path, identity, ordered_column="ts_ns", unique_order=True) is None
    )
```

2. [test fixture: `test_parquet_cache_treats_corrupt_manifest_and_unordered_rows_as_misses`](../../../../tests/integration/test_bar_cache_manifest.py#L158)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_parquet_cache_treats_corrupt_manifest_and_unordered_rows_as_misses(
    tmp_path: Path,
) -> None:
    identity = {"cache_id": "ordering"}
    unordered_path = tmp_path / "unordered.parquet"
    frame = pd.DataFrame({"ts_ns": [2, 1], "bid": [101.0, 100.0]})
    write_parquet_cache(unordered_path, frame, identity, index=False, ordered_column="ts_ns")

    assert load_parquet_cache(unordered_path, identity, ordered_column="ts_ns") is None

    manifest_path = parquet_cache_manifest_path(unordered_path)
    manifest_path.write_text("{invalid-json", encoding="utf-8")
    assert load_parquet_cache(unordered_path, identity, ordered_column="ts_ns") is None
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `mark_cache_complete`

**Kind:** function · **Status:** stable · **Owner:** `market_data.cache.storage`

**Purpose:** Write completion metadata after all cache files are ready.

**Exact API:** {py:obj}`market_data.cache.storage.mark_cache_complete` · **Source:** [market_data/cache/storage.py:26](../../../../market_data/cache/storage.py#L26)

**Inputs and outputs:**

- **Args:**

  ```text
  entry: Cache directory or identity path.
  metadata: JSON-compatible provenance and completeness fields.
  ```

- **Returns:**

  ```text
  Path returned by ``mark_cache_complete``.
  ```

**Observed usage:**

1. [test fixture: `test_directory_completion_marker_is_written_atomically`](../../../../tests/unit/market_data/test_cache_storage_contract.py#L34)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_directory_completion_marker_is_written_atomically(tmp_path: Path) -> None:
    entry = tmp_path / "cache-entry"

    assert mark_cache_complete(entry, {"identity": "fixture"}) == entry

    assert cache_is_complete(entry)
    assert cache_metadata_path(entry).read_text(encoding="utf-8").find("fixture") >= 0
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `parquet_cache_is_complete`

**Kind:** function · **Status:** stable · **Owner:** `market_data.cache.storage`

**Purpose:** Check for a non-empty parquet plus a structurally valid completion manifest.

**Exact API:** {py:obj}`market_data.cache.storage.parquet_cache_is_complete` · **Source:** [market_data/cache/storage.py:109](../../../../market_data/cache/storage.py#L109)

**Inputs and outputs:**

- **Args:**

  ```text
  cache_path: Path or filename identifying the cache.
  ```

- **Returns:**

  ```text
  Whether parquet cache is complete meets the requested condition.
  ```

**Observed usage:**

1. [test fixture: `test_parquet_cache_load_requires_matching_identity_and_ordering`](../../../../tests/unit/market_data/test_cache_storage_contract.py#L48)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_parquet_cache_load_requires_matching_identity_and_ordering(
    tmp_path: Path, pickle_backed_parquet: None
) -> None:
    path = tmp_path / "nested" / "bars.parquet"
    identity = {"cache_id": "fixture-v1", "feature_version": "v3"}
    frame = pd.DataFrame({"timestamp": [10, 20, 30], "close": [1.0, 2.0, 3.0]})
    write_parquet_cache(path, frame, identity, index=False, ordered_column="timestamp")

    assert parquet_cache_is_complete(path)
    cached = load_parquet_cache(path, identity, ordered_column="timestamp", unique_order=True)
    assert cached is not None
    pd.testing.assert_frame_equal(cached, frame)
    assert load_parquet_cache(path, {"cache_id": "other"}, ordered_column="timestamp") is None
```

2. [test fixture: `test_parquet_cache_reader_rejects_malformed_manifest_payloads`](../../../../tests/unit/market_data/test_cache_storage_contract.py#L114)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        index=False,
        ordered_column="timestamp",
    )
    Path(f"{path}.manifest.json").write_text(json.dumps(payload), encoding="utf-8")

    assert not parquet_cache_is_complete(path)
    assert load_parquet_cache(path, {"cache_id": "fixture"}, ordered_column="timestamp") is None
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `parquet_cache_manifest_path`

**Kind:** function · **Status:** stable · **Owner:** `market_data.cache.storage`

**Purpose:** Return the completion manifest path for a parquet cache file.

**Exact API:** {py:obj}`market_data.cache.storage.parquet_cache_manifest_path` · **Source:** [market_data/cache/storage.py:54](../../../../market_data/cache/storage.py#L54)

**Inputs and outputs:**

- **Args:**

  ```text
  cache_path: Path or filename identifying the cache.
  ```

- **Returns:**

  ```text
  Path returned by ``parquet_cache_manifest_path``.
  ```

**Observed usage:**

1. [test fixture: `test_parquet_cache_treats_corrupt_manifest_and_unordered_rows_as_misses`](../../../../tests/integration/test_bar_cache_manifest.py#L160)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_parquet_cache_treats_corrupt_manifest_and_unordered_rows_as_misses(
    tmp_path: Path,
) -> None:
    identity = {"cache_id": "ordering"}
    unordered_path = tmp_path / "unordered.parquet"
    frame = pd.DataFrame({"ts_ns": [2, 1], "bid": [101.0, 100.0]})
    write_parquet_cache(unordered_path, frame, identity, index=False, ordered_column="ts_ns")

    assert load_parquet_cache(unordered_path, identity, ordered_column="ts_ns") is None

    manifest_path = parquet_cache_manifest_path(unordered_path)
    manifest_path.write_text("{invalid-json", encoding="utf-8")
    assert load_parquet_cache(unordered_path, identity, ordered_column="ts_ns") is None
```

2. [test fixture: `fake_build_tick_books`](../../../../tests/unit/experiments/test_triton_prebuild_cache.py#L88)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        for symbol in cfg.data.symbols:
            for dataset_name in cfg.data.datasets:
                path = cache_dir / dataset_name / f"{symbol}_ticks_{TICK_CACHE_VERSION}.parquet"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"prepared")
                parquet_cache_manifest_path(path).write_text(
                    json.dumps(
                        {
                            "identity": {
                                "schema_version": TICK_CACHE_MANIFEST_SCHEMA_VERSION,
                                "transform": TICK_CACHE_TRANSFORM_ID,
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `write_parquet_cache`

**Kind:** function · **Status:** stable · **Owner:** `market_data.cache.storage`

**Purpose:** Atomically publish a parquet file and its semantic completion manifest.

**Exact API:** {py:obj}`market_data.cache.storage.write_parquet_cache` · **Source:** [market_data/cache/storage.py:184](../../../../market_data/cache/storage.py#L184)

**Inputs and outputs:**

- **Args:**

  ```text
  cache_path: Path or filename identifying the cache.
  frame: Input data frame to process.
  identity: Key-value data used for the identity.
  index: Position or label identifying the requested item.
  ordered_column: Ordered column used by the operation described above.
  ```

- **Returns:**

  ```text
  Path returned by ``write_parquet_cache``.
  ```

**Observed usage:**

1. [test fixture: `test_parquet_cache_rejects_duplicate_order_when_requested`](../../../../tests/integration/test_bar_cache_manifest.py#L133)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_parquet_cache_rejects_duplicate_order_when_requested(tmp_path: Path) -> None:
    cache_path = tmp_path / "ordered.parquet"
    identity = {"cache_id": "ordered"}
    frame = pd.DataFrame({"ts_ns": [1, 1, 2], "bid": [100.0, 100.1, 100.2]})
    write_parquet_cache(cache_path, frame, identity, index=False, ordered_column="ts_ns")

    assert (
        load_parquet_cache(cache_path, identity, ordered_column="ts_ns", unique_order=True) is None
    )
```

2. [test fixture: `test_parquet_cache_writer_requires_order_column_when_configured`](../../../../tests/integration/test_bar_cache_manifest.py#L142)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_parquet_cache_writer_requires_order_column_when_configured(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="missing ordering column"):
        write_parquet_cache(
            tmp_path / "missing.parquet",
            pd.DataFrame({"close": [100.0]}),
            {"cache_id": "missing-order"},
            ordered_column="ts_ns",
        )
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`
