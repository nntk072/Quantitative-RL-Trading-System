# Features · `context.reachability`

This page contains 6 public callable records owned by `features.context.reachability`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `attach_reachable_r`

**Kind:** function · **Status:** stable · **Owner:** `features.context.reachability`

**Purpose:** Append ``reachable_r`` after raw price columns have been dropped.

**Exact API:** {py:obj}`features.context.reachability.attach_reachable_r` · **Source:** [features/context/reachability.py:193](../../../../features/context/reachability.py#L193)

**Inputs and outputs:**

- **Args:**

  ```text
  obs: Tabular data used for the obs.
  bars: Market bars to process.
  features: Feature values supplied to the operation.
  include_validity_mask: Append a sequence feature marking known reachability values.
  session_tz: IANA session timezone; ``None`` keeps legacy fixed-clock behavior.
  source_clock_model: Interpretation of source index wall labels.
  ```

- **Returns:**

  ```text
  DataFrame returned by ``attach_reachable_r``.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = attach_reachable_r(obs=..., bars=..., features=..., include_validity_mask=..., session_tz=..., source_clock_model=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`

## `attach_reachable_r`

**Kind:** function · **Status:** stable · **Owner:** `features.context.reachability`

**Purpose:** Append ``reachable_r`` after raw price columns have been dropped.

**Exact API:** {py:obj}`features.context.reachability.attach_reachable_r` · **Source:** [features/context/reachability.py:193](../../../../features/context/reachability.py#L193)

**Inputs and outputs:**

- **Args:**

  ```text
  obs: Tabular data used for the obs.
  bars: Market bars to process.
  features: Feature values supplied to the operation.
  include_validity_mask: Append a sequence feature marking known reachability values.
  session_tz: IANA session timezone; ``None`` keeps legacy fixed-clock behavior.
  source_clock_model: Interpretation of source index wall labels.
  ```

- **Returns:**

  ```text
  DataFrame returned by ``attach_reachable_r``.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = attach_reachable_r(obs=..., bars=..., features=..., include_validity_mask=..., session_tz=..., source_clock_model=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`

## `max_tp_distance`

**Kind:** function · **Status:** stable · **Owner:** `features.context.reachability`

**Purpose:** Price distance a take-profit may sit from entry at each bar.

**Exact API:** {py:obj}`features.context.reachability.max_tp_distance` · **Source:** [features/context/reachability.py:17](../../../../features/context/reachability.py#L17)

**Inputs and outputs:**

- **Args:**

  ```text
  bars: Market bars to process.
  atr: Tabular data used for the atr.
  n_sessions: Numeric value used for the n sessions.
  quantile: Numeric value used for the quantile.
  session_tz: IANA session timezone; ``None`` keeps legacy fixed-clock behavior.
  source_clock_model: Interpretation of source index wall labels.
  ```

- **Returns:**

  ```text
  Result of price distance a take-profit may sit from entry at each bar.
  ```

**Observed usage:**

1. [test fixture: `test_rr_cap_scales_with_atr_not_a_fixed_point_distance`](../../../../tests/unit/evaluation/test_order_chart.py#L1139)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_rr_cap_scales_with_atr_not_a_fixed_point_distance() -> None:
    quiet_bars, quiet_atr = _session("2026-01-02 16:30", 30, 100.0, span=20.0, atr=2.0)
    quiet_bars2, quiet_atr2 = _session("2026-01-05 16:30", 30, 100.0, span=20.0, atr=2.0)
    quiet = pd.concat([quiet_bars, quiet_bars2])
    qatr = pd.concat([quiet_atr, quiet_atr2])
    qdist = max_tp_distance(quiet, qatr)
    # Prior session range 20 / atr 2 = 10 ATR, times current atr 2 → 20 points.
    assert qdist.iloc[-1] == 20.0
    assert not rr_reaches(100.0, 50.0, 4.0, float(qdist.iloc[-1]))

    big_bars, big_atr = _session("2200-01-02 16:30", 30, 1_000_000.0, span=2000.0, atr=200.0)
# … caller assertions omitted …
```

2. [test fixture: `test_reachability_uses_dst_aware_new_york_session_window`](../../../../tests/unit/features/test_stage_a_observation.py#L272)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    bars = pd.DataFrame(
        {"open": close, "high": close + 5.0, "low": close - 5.0, "close": close}, index=idx
    )
    atr = pd.Series(1.0, index=idx)

    distances = max_tp_distance(
        bars,
        atr,
        session_tz="America/Chicago",
        source_clock_model="europe_helsinki",
    )

    assert distances.iloc[:4].isna().all()
    assert distances.iloc[4:].eq(10.0).all()
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`

## `reachable_r_series`

**Kind:** function · **Status:** stable · **Owner:** `features.context.reachability`

**Purpose:** Causal reward room: max take-profit distance divided by structural stop.

**Exact API:** {py:obj}`features.context.reachability.reachable_r_series` · **Source:** [features/context/reachability.py:163](../../../../features/context/reachability.py#L163)

**Inputs and outputs:**

- **Args:**

  ```text
  bars: Market bars to process.
  features: Feature values supplied to the operation.
  session_tz: IANA session timezone; ``None`` keeps legacy fixed-clock behavior.
  source_clock_model: Interpretation of source index wall labels.
  ```

- **Returns:**

  ```text
  Result of causal reward room: max take-profit distance divided by structural stop.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = reachable_r_series(bars=..., features=..., session_tz=..., source_clock_model=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`

## `rr_reaches`

**Kind:** function · **Status:** stable · **Owner:** `features.context.reachability`

**Purpose:** True when ``rr_ratio * |entry - sl|`` fits inside ``max_distance``.

**Exact API:** {py:obj}`features.context.reachability.rr_reaches` · **Source:** [features/context/reachability.py:228](../../../../features/context/reachability.py#L228)

**Inputs and outputs:**

- **Args:**

  ```text
  entry: Numeric value used for the entry.
  sl: Numeric value used for the sl.
  rr_ratio: Numeric value used for the rr ratio.
  max_distance: Numeric value used for the max distance.
  ```

- **Returns:**

  ```text
  Whether rr reaches meets the requested condition.
  ```

**Observed usage:**

1. [test fixture: `test_rr_cap_scales_with_atr_not_a_fixed_point_distance`](../../../../tests/unit/evaluation/test_order_chart.py#L1142)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    quiet = pd.concat([quiet_bars, quiet_bars2])
    qatr = pd.concat([quiet_atr, quiet_atr2])
    qdist = max_tp_distance(quiet, qatr)
    # Prior session range 20 / atr 2 = 10 ATR, times current atr 2 → 20 points.
    assert qdist.iloc[-1] == 20.0
    assert not rr_reaches(100.0, 50.0, 4.0, float(qdist.iloc[-1]))

    big_bars, big_atr = _session("2200-01-02 16:30", 30, 1_000_000.0, span=2000.0, atr=200.0)
    big_bars2, big_atr2 = _session("2200-01-05 16:30", 30, 1_000_000.0, span=2000.0, atr=200.0)
    big = pd.concat([big_bars, big_bars2])
    batr = pd.concat([big_atr, big_atr2])
# … caller assertions omitted …
```

2. [test fixture: `test_reachability_allows_trade_before_any_session_range_is_known`](../../../../tests/unit/features/test_stage_a_observation.py#L327)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_reachability_allows_trade_before_any_session_range_is_known() -> None:
    assert rr_reaches(100.0, 98.0, 10.0, float("nan"))
    assert rr_reaches(100.0, 98.0, 10.0, float("inf"))
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`

## `attach_reachable_r`

**Kind:** function · **Status:** stable · **Owner:** `features.context.reachability`

**Purpose:** Append ``reachable_r`` after raw price columns have been dropped.

**Exact API:** {py:obj}`features.context.reachability.attach_reachable_r` · **Source:** [features/context/reachability.py:193](../../../../features/context/reachability.py#L193)

**Inputs and outputs:**

- **Args:**

  ```text
  obs: Tabular data used for the obs.
  bars: Market bars to process.
  features: Feature values supplied to the operation.
  include_validity_mask: Append a sequence feature marking known reachability values.
  session_tz: IANA session timezone; ``None`` keeps legacy fixed-clock behavior.
  source_clock_model: Interpretation of source index wall labels.
  ```

- **Returns:**

  ```text
  DataFrame returned by ``attach_reachable_r``.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = attach_reachable_r(obs=..., bars=..., features=..., include_validity_mask=..., session_tz=..., source_clock_model=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`
