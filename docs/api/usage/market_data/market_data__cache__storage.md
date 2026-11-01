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

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = cache_is_complete(entry=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

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

1. [production caller: `load_bar_cache`](../../../../market_data/cache/bars.py#L130)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def load_bar_cache(
    cache_path: str | Path, expected_identity: dict[str, Any]
) -> pd.DataFrame | None:
    return load_parquet_cache(cache_path, expected_identity, unique_order=True)
```

2. [production caller: `load_tick_cache`](../../../../market_data/cache/ticks.py#L112)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def load_tick_cache(
    cache_path: str | Path, expected_identity: dict[str, Any]
) -> pd.DataFrame | None:
    return load_parquet_cache(
        cache_path,
        expected_identity,
        ordered_column="ts_ns",
    )
```

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

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = mark_cache_complete(entry=..., metadata=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

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

1. [production caller: `bar_cache_is_complete`](../../../../market_data/cache/bars.py#L59)

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

2. [production caller: `load_parquet_cache`](../../../../market_data/cache/storage.py#L156)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        return None
    manifest = _read_parquet_cache_manifest(path)
    if (
        manifest is None
        or manifest.get("identity") != expected_identity
        or not parquet_cache_is_complete(path)
    ):
        return None
    try:
        frame = pd.read_parquet(path)
    except (OSError, ValueError):
# … caller assertions omitted …
```

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

1. [test fixture: `fake_build_tick_books`](../../../../tests/unit/experiments/test_triton_prebuild_cache.py#L88)

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

2. [production caller: `bar_cache_manifest_path`](../../../../market_data/cache/bars.py#L47)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def bar_cache_manifest_path(cache_path: str | Path) -> Path:
    return parquet_cache_manifest_path(cache_path)
```

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

1. [production caller: `write_bar_cache`](../../../../market_data/cache/bars.py#L150)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def write_bar_cache(
    cache_path: str | Path,
    frame: pd.DataFrame,
    identity: dict[str, Any],
) -> Path:
    if frame.empty:
        raise ValueError("cannot publish an empty bar cache")
    return write_parquet_cache(cache_path, frame, identity)
```

2. [production caller: `write_tick_cache`](../../../../market_data/cache/ticks.py#L140)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def write_tick_cache(
    cache_path: str | Path,
    frame: pd.DataFrame,
    identity: dict[str, Any],
) -> Path:
    required_columns = {"ts_ns", "bid", "ask"}
    missing = required_columns.difference(frame.columns)
    if missing:
        raise ValueError(f"tick cache frame is missing columns: {sorted(missing)}")
    if frame.empty:
        raise ValueError("cannot publish an empty tick cache")
    return write_parquet_cache(
        cache_path,
        frame,
        identity,
        index=False,
        ordered_column="ts_ns",
    )
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`
