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

1. [test fixture: `test_attach_policy_market_context_preserves_features_and_appends_context`](../../../../tests/unit/features/test_policy_market_context.py#L89)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    schedule.write_text(
        "session_date,scheduled_ny_close_broker_time,scheduled_short\n",
        encoding="utf-8",
    )

    result = attach_policy_market_context(
        bars,
        features,
        _book(index, [5, 30, 60, 90]),
        schedule_path=schedule,
    )

    assert result.index.equals(features.index)
    pd.testing.assert_frame_equal(result.loc[:, features.columns], features)
    assert result["tick_quote_available"].eq(1.0).all()
```

2. [test fixture: `test_attach_policy_market_context_rejects_duplicate_context_columns`](../../../../tests/unit/features/test_policy_market_context.py#L112)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        "session_date,scheduled_ny_close_broker_time,scheduled_short\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="columns already exist"):
        attach_policy_market_context(
            bars,
            features,
            _book(index, [5]),
            schedule_path=schedule,
        )
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`
