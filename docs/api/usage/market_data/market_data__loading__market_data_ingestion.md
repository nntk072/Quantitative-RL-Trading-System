# Market data · `loading.market_data_ingestion`

This page contains 2 public callable records owned by `market_data.loading.market_data_ingestion`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `run_pipeline`

**Kind:** function · **Status:** stable · **Owner:** `market_data.loading.market_data_ingestion`

**Purpose:** Load, resample, clean, label and cache all symbols / timeframes.

**Exact API:** {py:obj}`market_data.loading.market_data_ingestion.run_pipeline` · **Source:** [market_data/loading/market_data_ingestion.py:46](../../../../market_data/loading/market_data_ingestion.py#L46)

**Inputs and outputs:**

- **Args:**

  ```text
  cfg: OmegaConf config (config/base/default.yaml).
  force: If True, ignore existing parquet cache and reprocess from CSV.
  datasets: Optional configured dataset names to process; None selects all datasets.
  ```

- **Returns:**

  ```text
  Mapping from ``str`` keys to ``dict[str, pd.DataFrame]`` values.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = run_pipeline(cfg=..., force=..., datasets=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `run_pipeline`

**Kind:** function · **Status:** stable · **Owner:** `market_data.loading.market_data_ingestion`

**Purpose:** Load, resample, clean, label and cache all symbols / timeframes.

**Exact API:** {py:obj}`market_data.loading.market_data_ingestion.run_pipeline` · **Source:** [market_data/loading/market_data_ingestion.py:46](../../../../market_data/loading/market_data_ingestion.py#L46)

**Inputs and outputs:**

- **Args:**

  ```text
  cfg: OmegaConf config (config/base/default.yaml).
  force: If True, ignore existing parquet cache and reprocess from CSV.
  datasets: Optional configured dataset names to process; None selects all datasets.
  ```

- **Returns:**

  ```text
  Mapping from ``str`` keys to ``dict[str, pd.DataFrame]`` values.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = run_pipeline(cfg=..., force=..., datasets=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`
