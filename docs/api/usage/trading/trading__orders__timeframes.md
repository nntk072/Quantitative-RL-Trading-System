# Trading · `orders.timeframes`

This page contains 5 public callable records owned by `trading.orders.timeframes`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `normalize_timeframe`

**Kind:** function · **Status:** stable · **Owner:** `trading.orders.timeframes`

**Purpose:** Return the canonical uppercase timeframe label.

**Exact API:** {py:obj}`trading.orders.timeframes.normalize_timeframe` · **Source:** [trading/orders/timeframes.py:8](../../../../trading/orders/timeframes.py#L8)

**Inputs and outputs:**

- **Args:**

  ```text
  timeframe: Text or path value identifying the timeframe.
  ```

- **Returns:**

  ```text
  Text returned by ``normalize_timeframe``.
  ```

**Observed usage:**

1. [production caller: `stop_menu`](../../../../trading/orders/stops.py#L157)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        ref = strategy.sl_reference(direction=direction, row=row)
        if ref is not None and np.isfinite(float(ref)):
            raw = [("sl_reference", float(ref))]
    swing = "last_swing_low" if direction == 1 else "last_swing_high"
    for tf in htf:
        tf_up = normalize_timeframe(str(tf))
        candidate_side = "low" if direction == 1 else "high"
        candidate_prefix = f"{tf_up}_swing_{candidate_side}_candidate_"
        candidate_columns = getattr(row, "index", ())
        has_candidate_schema = any(
            f"{candidate_prefix}{slot}" in candidate_columns for slot in range(1, 4)
# … caller assertions omitted …
```

2. [production caller: `target_menu`](../../../../trading/orders/targets.py#L124)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    for name in names:
        level = finite_level(row, name)
        if level is not None:
            raw.append((name, level))
    for tf in htf:
        tf_up = normalize_timeframe(str(tf))
        level = finite_level(row, f"{tf_up}_{swing_name}")
        if level is not None:
            raw.append((f"{tf_up}_{swing_name}", level))
    row_columns = getattr(row, "index", ())
    for column in row_columns:
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `reference_timeframe`

**Kind:** function · **Status:** stable · **Owner:** `trading.orders.timeframes`

**Purpose:** Infer a reference's timeframe from its canonical source name.

**Exact API:** {py:obj}`trading.orders.timeframes.reference_timeframe` · **Source:** [trading/orders/timeframes.py:32](../../../../trading/orders/timeframes.py#L32)

**Inputs and outputs:**

- **Args:**

  ```text
  reference_name: Text or path value identifying the reference name.
  ```

- **Returns:**

  ```text
  Text returned by ``reference_timeframe``.
  ```

**Observed usage:**

1. [production caller: `target_menu`](../../../../trading/orders/targets.py#L151)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    if not isinstance(decision_at, pd.Timestamp):
        decision_at = None
    available: list[tuple[str, float]] = []
    minimum_rank = timeframe_index(min_timeframe) if min_timeframe is not None else 0
    for name, level in raw:
        if timeframe_index(reference_timeframe(name)) < minimum_rank:
            continue
        confirmed_at = row.get(f"{name}_confirmed_at") if hasattr(row, "get") else None
        if confirmed_at is not None and not pd.isna(confirmed_at):
            if decision_at is None:
                continue  # explicit availability requires an actual decision clock
# … caller assertions omitted …
```

2. [production caller: `source_timeframe`](../../../../trading/orders/timeframes.py#L72)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def source_timeframe(reference_name: str) -> str:
    head = str(reference_name).split("|", 1)[0]
    if not head:
        return ""
    if head.startswith(("asian_", "london_", "prev_day_", "ctx_prev_week_")):
        return ""
    return reference_timeframe(reference_name)
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `reference_timeframe_index`

**Kind:** function · **Status:** stable · **Owner:** `trading.orders.timeframes`

**Purpose:** Return the chronology rank for a named market reference.

**Exact API:** {py:obj}`trading.orders.timeframes.reference_timeframe_index` · **Source:** [trading/orders/timeframes.py:75](../../../../trading/orders/timeframes.py#L75)

**Inputs and outputs:**

- **Args:**

  ```text
  reference_name: Text or path value identifying the reference name.
  ```

- **Returns:**

  ```text
  Numeric result returned by ``reference_timeframe_index``.
  ```

**Observed usage:**

1. [production caller: `_timeframe_rank_for_stop`](../../../../trading/orders/stops.py#L31)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def _timeframe_rank_for_stop(name: str) -> int:
    return reference_timeframe_index(name)
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `source_timeframe`

**Kind:** function · **Status:** stable · **Owner:** `trading.orders.timeframes`

**Purpose:** Return a candle timeframe, leaving session/day references unlabelled.

**Exact API:** {py:obj}`trading.orders.timeframes.source_timeframe` · **Source:** [trading/orders/timeframes.py:54](../../../../trading/orders/timeframes.py#L54)

**Inputs and outputs:**

- **Args:**

  ```text
  reference_name: Text or path value identifying the reference name.
  ```

- **Returns:**

  ```text
  Text returned by ``source_timeframe``.
  ```

**Observed usage:**

1. [production caller: `_with_menus`](../../../../trading/orders/entries.py#L128)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        stamp = row.get(f"{first}_confirmed_at") if row is not None else None
        confirmed = None if stamp is None or pd.isna(stamp) else pd.Timestamp(stamp).isoformat()
        references.append(
            TargetReference(
                name=name,
                timeframe=reference_timeframe(name),
                original_price=original_prices.get(first),
                adjusted_price=float(px),
                confirmed_at=confirmed,
                reason="selected" if idx in selected else "eligible",
                sources=names,
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `timeframe_index`

**Kind:** function · **Status:** stable · **Owner:** `trading.orders.timeframes`

**Purpose:** Return the configured chronology rank for a timeframe label.

**Exact API:** {py:obj}`trading.orders.timeframes.timeframe_index` · **Source:** [trading/orders/timeframes.py:20](../../../../trading/orders/timeframes.py#L20)

**Inputs and outputs:**

- **Args:**

  ```text
  timeframe: Text or path value identifying the timeframe.
  ```

- **Returns:**

  ```text
  Numeric result returned by ``timeframe_index``.
  ```

**Observed usage:**

1. [production caller: `stop_menu`](../../../../trading/orders/stops.py#L272)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
                "reason": "standard_deviation_stop_level_must_be_1",
            }
        )
    raw = [item for item in raw if item not in invalid_deviation_candidates]
    normalized_floor = normalize_timeframe(min_timeframe)
    minimum_rank = timeframe_index(normalized_floor)
    sd_timeframes = tuple(
        normalize_timeframe(timeframe) for timeframe in (standard_deviation_timeframes or ())
    )
    if sd_timeframes:
        expected_sd_stops = {
# … caller assertions omitted …
```

2. [production caller: `target_menu`](../../../../trading/orders/targets.py#L149)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        # origin (`*_time`) is not a confirmation time and is not used here.
    decision_at = getattr(row, "name", None)
    if not isinstance(decision_at, pd.Timestamp):
        decision_at = None
    available: list[tuple[str, float]] = []
    minimum_rank = timeframe_index(min_timeframe) if min_timeframe is not None else 0
    for name, level in raw:
        if timeframe_index(reference_timeframe(name)) < minimum_rank:
            continue
        confirmed_at = row.get(f"{name}_confirmed_at") if hasattr(row, "get") else None
        if confirmed_at is not None and not pd.isna(confirmed_at):
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`
