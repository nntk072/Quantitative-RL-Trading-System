# Features · `context.policy_market`

This page contains 1 public callable records owned by `features.context.policy_market`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `attach_policy_market_context`

**Kind:** function · **Status:** stable · **Owner:** `features.context.policy_market`

**Purpose:** Attach policy-session context derived from bars and the tick schedule.

**Exact API:** {py:obj}`features.context.policy_market.attach_policy_market_context` · **Source:** [features/context/policy_market.py:130](../../../../features/context/policy_market.py#L130)

**Inputs and outputs:**

- **Args:**

  ```text
  bars: Market bars used to determine session dates and ranges.
  features: Existing feature frame to extend.
  tickbook: Optional tick data used by the context builder.
  schedule_path: Session schedule used to resolve policy windows.
  session_start: Local session start time in HH:MM form.
  session_end: Local session end time in HH:MM form.
  ```

- **Returns:**

  ```text
  Feature frame with policy-market context columns appended.
  ```

**Observed usage:**

1. [production caller: `reconstruct_reanalysis_datasets`](../../../../evaluation/reanalysis/datasets.py#L169)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            )

    schedule_path = Path(str(cfg.data.session_schedule_file))
    if not schedule_path.is_absolute():
        schedule_path = repository_root(__file__) / schedule_path
    features = attach_policy_market_context(
        primary_m1,
        features,
        primary_ticks,
        schedule_path=schedule_path,
        session_start=str(cfg.session.start),
        session_end=str(cfg.session.end),
    )

    train_bars, test_bars, train_features, test_features = split_train_test(
        primary_m1, features, train_end, test_start, train_start
    )
    train_secondary = test_secondary = None
# … caller assertions omitted …
```

2. [production caller: `_prepare_training_data`](../../../../training/runner/data_stage.py#L169)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        secondary_timeframe_bars=secondary_timeframe_bars,
    )
    schedule_path = Path(str(cfg.data.session_schedule_file))
    if not schedule_path.is_absolute():
        schedule_path = repository_root(__file__) / schedule_path
    features = attach_policy_market_context(
        primary_m1,
        features,
        primary_ticks,
        schedule_path=schedule_path,
        session_start=str(cfg.session.start),
        session_end=str(cfg.session.end),
    )
    feature_columns = [str(column) for column in features.columns]

    # Split
    train_bars, test_bars, train_feat, test_feat = split_train_test(
        primary_m1, features, train_end, test_start, train_start
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`
