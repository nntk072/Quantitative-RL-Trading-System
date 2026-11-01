# Market data · `loading.tick_book_pipeline`

This page contains 2 public callable records owned by `market_data.loading.tick_book_pipeline`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `build_tick_books`

**Kind:** function · **Status:** stable · **Owner:** `market_data.loading.tick_book_pipeline`

**Purpose:** Build (or load from cache) a ``TickBook`` for each selected symbol.

**Exact API:** {py:obj}`market_data.loading.tick_book_pipeline.build_tick_books` · **Source:** [market_data/loading/tick_book_pipeline.py:20](../../../../market_data/loading/tick_book_pipeline.py#L20)

**Inputs and outputs:**

- **Args:**

  ```text
  cfg: Run configuration used by this operation.
  force: Whether to enable or require the force.
  symbols: Items supplied for the symbols, in input order.
  datasets: Items supplied for the datasets, in input order.
  ```

- **Returns:**

  ```text
  Mapping from ``str`` keys to ``TickBook | None`` values.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = build_tick_books(cfg=..., force=..., symbols=..., datasets=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `build_tick_books`

**Kind:** function · **Status:** stable · **Owner:** `market_data.loading.tick_book_pipeline`

**Purpose:** Build (or load from cache) a ``TickBook`` for each selected symbol.

**Exact API:** {py:obj}`market_data.loading.tick_book_pipeline.build_tick_books` · **Source:** [market_data/loading/tick_book_pipeline.py:20](../../../../market_data/loading/tick_book_pipeline.py#L20)

**Inputs and outputs:**

- **Args:**

  ```text
  cfg: Run configuration used by this operation.
  force: Whether to enable or require the force.
  symbols: Items supplied for the symbols, in input order.
  datasets: Items supplied for the datasets, in input order.
  ```

- **Returns:**

  ```text
  Mapping from ``str`` keys to ``TickBook | None`` values.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = build_tick_books(cfg=..., force=..., symbols=..., datasets=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`
