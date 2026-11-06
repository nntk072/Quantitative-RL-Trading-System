# Features · `context.reachability`

This page contains 6 public callable records owned by `features.context.reachability`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `attach_reachable_r`

**Kind:** function · **Status:** stable · **Owner:** `features.context.reachability`

**Purpose:** Append ``reachable_r`` after raw price columns have been dropped.

**Exact API:** {py:obj}`features.context.reachability.attach_reachable_r` · **Source:** [features/context/reachability.py:161](../../../../features/context/reachability.py#L161)

**Inputs and outputs:**

- **Args:**

  ```text
  obs: Tabular data used for the obs.
  bars: Market bars to process.
  features: Feature values supplied to the operation.
  include_validity_mask: Append a sequence feature marking known reachability values.
  ```

- **Returns:**

  ```text
  DataFrame returned by ``attach_reachable_r``.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = attach_reachable_r(obs=..., bars=..., features=..., include_validity_mask=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`

## `attach_reachable_r`

**Kind:** function · **Status:** stable · **Owner:** `features.context.reachability`

**Purpose:** Append ``reachable_r`` after raw price columns have been dropped.

**Exact API:** {py:obj}`features.context.reachability.attach_reachable_r` · **Source:** [features/context/reachability.py:161](../../../../features/context/reachability.py#L161)

**Inputs and outputs:**

- **Args:**

  ```text
  obs: Tabular data used for the obs.
  bars: Market bars to process.
  features: Feature values supplied to the operation.
  include_validity_mask: Append a sequence feature marking known reachability values.
  ```

- **Returns:**

  ```text
  DataFrame returned by ``attach_reachable_r``.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = attach_reachable_r(obs=..., bars=..., features=..., include_validity_mask=...)
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
  ```

- **Returns:**

  ```text
  Result of price distance a take-profit may sit from entry at each bar.
  ```

**Observed usage:**

1. [test fixture: `test_rr_cap_scales_with_atr_not_a_fixed_point_distance`](../../../../tests/unit/evaluation/test_order_chart.py#L734)

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

2. [production caller: `_reachable_r_values`](../../../../features/context/reachability.py#L99)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    if "atr_5" not in features.columns or "close" not in bars.columns:
        return (
            pd.Series(0.0, index=idx, name="reachable_r"),
            pd.Series(False, index=idx, name="reachable_r_valid"),
        )
    dist = max_tp_distance(bars, features["atr_5"]).reindex(idx)
    close = pd.to_numeric(bars["close"], errors="coerce")
    atr = pd.to_numeric(features["atr_5"].reindex(idx), errors="coerce")
    if "po3_manipulation_low" in features.columns and "po3_manipulation_high" in features.columns:
        risk_long = (
            close - pd.to_numeric(features["po3_manipulation_low"].reindex(idx), errors="coerce")
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`

## `reachable_r_series`

**Kind:** function · **Status:** stable · **Owner:** `features.context.reachability`

**Purpose:** Causal reward room: max take-profit distance divided by structural stop.

**Exact API:** {py:obj}`features.context.reachability.reachable_r_series` · **Source:** [features/context/reachability.py:144](../../../../features/context/reachability.py#L144)

**Inputs and outputs:**

- **Args:**

  ```text
  bars: Market bars to process.
  features: Feature values supplied to the operation.
  ```

- **Returns:**

  ```text
  Result of causal reward room: max take-profit distance divided by structural stop.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = reachable_r_series(bars=..., features=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`

## `rr_reaches`

**Kind:** function · **Status:** stable · **Owner:** `features.context.reachability`

**Purpose:** True when ``rr_ratio * |entry - sl|`` fits inside ``max_distance``.

**Exact API:** {py:obj}`features.context.reachability.rr_reaches` · **Source:** [features/context/reachability.py:187](../../../../features/context/reachability.py#L187)

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

1. [test fixture: `test_rr_cap_scales_with_atr_not_a_fixed_point_distance`](../../../../tests/unit/evaluation/test_order_chart.py#L737)

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

2. [production caller: `_rr_fits`](../../../../simulation/environment/entry_runtime.py#L305)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def _rr_fits(self, entry_price: float, sl_price: float, rr_ratio: float) -> bool:
    from features.context.reachability import rr_reaches

    return rr_reaches(entry_price, sl_price, rr_ratio, self._max_tp_here())
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`

## `attach_reachable_r`

**Kind:** function · **Status:** stable · **Owner:** `features.context.reachability`

**Purpose:** Append ``reachable_r`` after raw price columns have been dropped.

**Exact API:** {py:obj}`features.context.reachability.attach_reachable_r` · **Source:** [features/context/reachability.py:161](../../../../features/context/reachability.py#L161)

**Inputs and outputs:**

- **Args:**

  ```text
  obs: Tabular data used for the obs.
  bars: Market bars to process.
  features: Feature values supplied to the operation.
  include_validity_mask: Append a sequence feature marking known reachability values.
  ```

- **Returns:**

  ```text
  DataFrame returned by ``attach_reachable_r``.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = attach_reachable_r(obs=..., bars=..., features=..., include_validity_mask=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`
