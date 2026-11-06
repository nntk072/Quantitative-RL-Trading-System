# Market data · `transforms.session_schedule`

This page contains 1 public callable records owned by `market_data.transforms.session_schedule`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `scheduled_session_close_map`

**Kind:** function · **Status:** stable · **Owner:** `market_data.transforms.session_schedule`

**Purpose:** Load date-specific NY close times from the resolved data configuration.

**Exact API:** {py:obj}`market_data.transforms.session_schedule.scheduled_session_close_map` · **Source:** [market_data/transforms/session_schedule.py:13](../../../../market_data/transforms/session_schedule.py#L13)

**Inputs and outputs:**

- **Args:**

  ```text
  cfg: Run configuration used by this operation.
  ```

- **Returns:**

  ```text
  Mapping from ``str`` keys to ``str`` values.
  ```

**Observed usage:**

1. [production caller: `build_features`](../../../../features/pipeline/feature_matrix_builder.py#L290)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    secondary_timeframe_frames = {
        str(tf).upper(): frame for tf, frame in (secondary_timeframe_bars or {}).items()
    }
    if secondary is not None:
        secondary_timeframe_frames["M1"] = secondary
    scheduled_closes = scheduled_session_close_map(cfg)
    session_start = str(OmegaConf.select(cfg, "session.start") or "16:30") if cfg else "16:30"

    def primary_tf_bars(tf: str) -> pd.DataFrame:
        """Return cached primary bars or derive them for one timeframe.

# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`
