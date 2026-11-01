# Market data · `cache.identity`

This page contains 1 public callable records owned by `market_data.cache.identity`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `market_data_cache_id`

**Kind:** function · **Status:** stable · **Owner:** `market_data.cache.identity`

**Purpose:** Build a stable cache identity from dataset and transform semantics.

**Exact API:** {py:obj}`market_data.cache.identity.market_data_cache_id` · **Source:** [market_data/cache/identity.py:8](../../../../market_data/cache/identity.py#L8)

**Inputs and outputs:**

- **Args:**

  ```text
  dataset_id: Identity of the source market data.
  transform: Name of the applied transform pipeline.
  config: Values that affect transformed output.
  schema_version: Cache schema revision.
  ```

- **Returns:**

  ```text
  Deterministic cache identifier.
  ```

**Observed usage:**

1. [production caller: `build_bar_cache_identity`](../../../../market_data/cache/bars.py#L108)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        "price_grid_identity": price_grid_identity,
    }
    return {
        "schema_version": BAR_CACHE_MANIFEST_SCHEMA_VERSION,
        "transform": BAR_CACHE_TRANSFORM_ID,
        "cache_id": market_data_cache_id(
            dataset_id=f"{dataset_id}:{symbol}:{timeframe}:{source_identity}",
            transform=BAR_CACHE_TRANSFORM_ID,
            config=transform_config,
            schema_version=BAR_CACHE_MANIFEST_SCHEMA_VERSION,
        ),
        "inputs": transform_config,
    }
```

2. [production caller: `build_tick_cache_identity`](../../../../market_data/cache/ticks.py#L72)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        "cache_version": cache_version,
    }
    return {
        "schema_version": TICK_CACHE_MANIFEST_SCHEMA_VERSION,
        "transform": TICK_CACHE_TRANSFORM_ID,
        "cache_id": market_data_cache_id(
            dataset_id=resolved_source_path,
            transform=TICK_CACHE_TRANSFORM_ID,
            config=inputs,
            schema_version=TICK_CACHE_MANIFEST_SCHEMA_VERSION,
        ),
        "inputs": inputs,
    }
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`
