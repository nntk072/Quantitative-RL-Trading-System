# Market data · `transforms.cleaning`

This page contains 1 public callable records owned by `market_data.transforms.cleaning`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `clean`

**Kind:** function · **Status:** stable · **Owner:** `market_data.transforms.cleaning`

**Purpose:** Deduplicate, sort, localise timezone, and add a ``gap_flag`` column.

**Exact API:** {py:obj}`market_data.transforms.cleaning.clean` · **Source:** [market_data/transforms/cleaning.py:10](../../../../market_data/transforms/cleaning.py#L10)

**Inputs and outputs:**

- **Args:**

  ```text
  df: Raw bar DataFrame from :func:`market_data.loading.bars.load_bars`.
  tz: Timezone used to carry naive source wall-clock labels in the index.
      It is not an absolute-timezone claim when the source clock observes DST.
  ```

- **Returns:**

  ```text
  A sorted copy with duplicate timestamps removed (keeping the last),
  a ``gap_flag`` column, and a timezone-aware index when the input index
  was naive. A gap is larger than twice the modal bar interval.
  ```

**Observed usage:**

1. [test fixture: `test_load_bars_records_raw_order_and_conflicting_duplicate_diagnostics`](../../../../tests/integration/test_loader.py#L110)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    assert bars.attrs["source_diagnostics"] == {
        "out_of_order_rows": 1,
        "duplicate_rows": 1,
        "conflicting_duplicate_timestamps": 1,
    }
    assert clean(bars).attrs["source_diagnostics"] == bars.attrs["source_diagnostics"]
```

2. [production caller: `run_pipeline`](../../../../market_data/loading/market_data_ingestion.py#L272)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
                """
                if path not in source_hashes:
                    source_hashes[path] = file_sha256(path)
                return source_hashes[path]

            m1_clean = clean(m1_raw, tz=tz)
            m1_full = add_session_labels(
                m1_clean,
                tz=session_tz,
                ny_end=ny_end,
                source_clock_model=source_clock_model,
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`
