# Features · `pipeline.feature_matrix_builder`

This page contains 2 public callable records owned by `features.pipeline.feature_matrix_builder`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `build_features`

**Kind:** function · **Status:** stable · **Owner:** `features.pipeline.feature_matrix_builder`

**Purpose:** Build the full feature matrix for the primary instrument.

**Exact API:** {py:obj}`features.pipeline.feature_matrix_builder.build_features` · **Source:** [features/pipeline/feature_matrix_builder.py:80](../../../../features/pipeline/feature_matrix_builder.py#L80)

**Inputs and outputs:**

- **Args:**

  ```text
  primary: Cleaned, session-filtered M1 DataFrame (US100).
  secondary: US500 M1 DataFrame for SMT divergence (optional but recommended).
  cfg: Full OmegaConf config; ``cfg.features`` sub-node is used.
  train_mask: Boolean Series aligned to primary index; True = training bar.
  cache_path: If given, save/load feature parquet here.
  force: Ignore existing cache.
  normalization_mode: Normalization behavior used for continuous feature columns.
  timeframe_bars: Optional precomputed primary bars indexed by timeframe.
  secondary_timeframe_bars: Optional precomputed correlated-symbol bars by timeframe.
  ```

- **Returns:**

  ```text
  DataFrame returned by ``build_features``.
  ```

**Observed usage:**

1. [production caller: `_replot_split`](../../../../evaluation/reporting/order_chart_regeneration.py#L409)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            ifvg_timeframes=ifvg_timeframes,
            swing_timeframes=swing_timeframes,
            standard_deviation_timeframes=standard_deviation_timeframes,
            entry_idea_timeframes=idea_timeframes,
        )
        chart_features = build_features(bars, secondary=secondary, cfg=feature_cfg)

    bar_tz = pd.DatetimeIndex(bars.index).tz

    def align_trade_time(value: Any) -> pd.Timestamp:
        """Localize or convert a trade timestamp to the bar-index timezone.
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`

## `build_features`

**Kind:** function · **Status:** stable · **Owner:** `features.pipeline.feature_matrix_builder`

**Purpose:** Build the full feature matrix for the primary instrument.

**Exact API:** {py:obj}`features.pipeline.feature_matrix_builder.build_features` · **Source:** [features/pipeline/feature_matrix_builder.py:80](../../../../features/pipeline/feature_matrix_builder.py#L80)

**Inputs and outputs:**

- **Args:**

  ```text
  primary: Cleaned, session-filtered M1 DataFrame (US100).
  secondary: US500 M1 DataFrame for SMT divergence (optional but recommended).
  cfg: Full OmegaConf config; ``cfg.features`` sub-node is used.
  train_mask: Boolean Series aligned to primary index; True = training bar.
  cache_path: If given, save/load feature parquet here.
  force: Ignore existing cache.
  normalization_mode: Normalization behavior used for continuous feature columns.
  timeframe_bars: Optional precomputed primary bars indexed by timeframe.
  secondary_timeframe_bars: Optional precomputed correlated-symbol bars by timeframe.
  ```

- **Returns:**

  ```text
  DataFrame returned by ``build_features``.
  ```

**Observed usage:**

1. [production caller: `_replot_split`](../../../../evaluation/reporting/order_chart_regeneration.py#L409)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            ifvg_timeframes=ifvg_timeframes,
            swing_timeframes=swing_timeframes,
            standard_deviation_timeframes=standard_deviation_timeframes,
            entry_idea_timeframes=idea_timeframes,
        )
        chart_features = build_features(bars, secondary=secondary, cfg=feature_cfg)

    bar_tz = pd.DatetimeIndex(bars.index).tz

    def align_trade_time(value: Any) -> pd.Timestamp:
        """Localize or convert a trade timestamp to the bar-index timezone.
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`
