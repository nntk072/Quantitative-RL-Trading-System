# Trading · `orders.entries`

This page contains 5 public callable records owned by `trading.orders.entries`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `OrderGeometry`

**Kind:** class · **Status:** stable · **Owner:** `trading.orders.entries`

**Purpose:** One working stop and one exit, or a refusal.

**Exact API:** {py:obj}`trading.orders.entries.OrderGeometry` · **Source:** [trading/orders/entries.py:45](../../../../trading/orders/entries.py#L45)

**Observed usage:**

1. [production caller: `place_strategy_order`](../../../../trading/orders/entries.py#L285)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        htf=htf,
        min_timeframe=entry_timeframe_floor,
        standard_deviation_timeframes=standard_deviation_timeframes,
        price_increment=price_increment,
    )
    empty = OrderGeometry(
        None,
        None,
        "",
        "",
        buf,
        None,
        mode,
        state,
        len(stops),
        0,
        True,
        "sl",
    )
    if not stops:
        return _with_menus(empty, stops, [], stop_audit=stop_audit)
    anchor = None
    anchor_dist = None
    for name, price, dist in stops:
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `TargetReference`

**Kind:** class · **Status:** stable · **Owner:** `trading.orders.entries`

**Purpose:** Provenance for one executable candidate; None means unverified metadata.

**Exact API:** {py:obj}`trading.orders.entries.TargetReference` · **Source:** [trading/orders/entries.py:31](../../../../trading/orders/entries.py#L31)

**Observed usage:**

1. [production caller: `_with_menus`](../../../../trading/orders/entries.py#L126)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        names = tuple(name.split("|"))
        first = names[0]
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
                fallback_reason=fallback_reason,
            )
        )
    return replace(
        geometry,
        sl_menu=_menu_pairs(stops),
        tp_menu=_menu_pairs(targets),
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `dynamic_tp`

**Kind:** function · **Status:** stable · **Owner:** `trading.orders.entries`

**Purpose:** Legacy reachable-reward target used by the chart helper.

**Exact API:** {py:obj}`trading.orders.entries.dynamic_tp` · **Source:** [trading/orders/entries.py:165](../../../../trading/orders/entries.py#L165)

**Inputs and outputs:**

- **Args:**

  ```text
  direction: Signed trade direction: 1 for long and -1 for short.
  entry_price: Price at which the position was opened.
  sl_price: Numeric value used for the sl price.
  reward_fraction: Numeric value used for the reward fraction.
  max_tp_distance: Max tp distance used by the operation described above.
  ```

- **Returns:**

  ```text
  Whether dynamic tp meets the requested condition.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = dynamic_tp(direction=..., entry_price=..., sl_price=..., reward_fraction=..., max_tp_distance=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `place_strategy_order`

**Kind:** function · **Status:** stable · **Owner:** `trading.orders.entries`

**Purpose:** Pick the stop, then a structural target or an EMA-21 exit.

**Exact API:** {py:obj}`trading.orders.entries.place_strategy_order` · **Source:** [trading/orders/entries.py:202](../../../../trading/orders/entries.py#L202)

**Inputs and outputs:**

- **Args:**

  ```text
  strategy: Strategy used to select or evaluate trades.
  direction: Signed trade direction: 1 for long and -1 for short.
  entry_price: Price at which the position was opened.
  feat_row: Feature values for the current market bar.
  min_dist: Numeric value used for the min dist.
  sl_fraction: Numeric value used for the sl fraction.
  tp_fraction: Numeric value used for the tp fraction.
  exit_mode: Text or path value identifying the exit mode.
  buffer_pts: Numeric value used for the buffer pts.
  max_tp_distance: Numeric value used for the max tp distance.
  rr_bounds: Items supplied for the rr bounds, in input order.
  htf: Items supplied for the htf, in input order.
  entry_timeframe_floor: Text or path value identifying the entry timeframe floor.
  standard_deviation_timeframes: Items supplied for the standard deviation timeframes, in input order.
  tp_selections: Items supplied for the tp selections, in input order.
  tp_z: Items supplied for the tp z, in input order.
  allow_multi_tp: Whether to enable or require the allow multi tp.
  allow_simplex: Whether to enable or require the allow simplex.
  target_front_run_pts: Numeric value used for the target front run pts.
  price_increment: Price increment used by the operation described above.
  ema_runner_fraction: Numeric value used for the ema runner fraction.
  trade_setup: Trade setup used by the operation described above.
  ```

- **Returns:**

  ```text
  Result of pick the stop, then a structural target or an EMA-21 exit.
  ```

**Observed usage:**

1. [test fixture: `_place`](../../../../tests/integration/backtest/test_entry_levels.py#L68)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    max_tp: float = float("nan"),
    stops: list[tuple[str, float]] | None = None,
    price_increment: float | None = None,
    ema_runner_fraction: float = 0.0,
) -> OrderGeometry:
    return place_strategy_order(
        _Menu(stops),
        direction=direction,
        entry_price=entry,
        feat_row=row,
        min_dist=min_dist,
        sl_fraction=sl_fraction,
        tp_fraction=tp_fraction,
        exit_mode=exit_mode,
        buffer_pts=buffer_pts,
        max_tp_distance=max_tp,
        price_increment=price_increment,
        ema_runner_fraction=ema_runner_fraction,
    )
```

2. [test fixture: `test_strategy_order_uses_setup_floor_for_stops_and_all_timeframes_for_targets`](../../../../tests/integration/backtest/test_entry_levels.py#L244)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        M3_last_swing_high=108.0,
        M5_last_swing_high=109.0,
        H1_last_swing_high=110.0,
    )
    trade_setup = trade_setup_candidate(trade_setup_candidate_id("fvg_retest", "M5", 1))
    geometry = place_strategy_order(
        _Menu(),
        direction=1,
        entry_price=100.0,
        feat_row=row,
        min_dist=1.0,
        sl_fraction=1.0,
        tp_fraction=0.0,
        exit_mode="structural",
        buffer_pts=0.0,
        max_tp_distance=float("nan"),
        htf=("M3", "M5", "H1"),
        trade_setup=trade_setup,
    )
    assert not geometry.rejected
    sl_names = {part for name, _price in geometry.sl_menu for part in name.split("|")}
    tp_names = {part for name, _price in geometry.tp_menu for part in name.split("|")}
    assert "last_swing_low" not in sl_names
    assert "M3_last_swing_low" not in sl_names
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `resolve_strategy_entry`

**Kind:** function · **Status:** stable · **Owner:** `trading.orders.entries`

**Purpose:** Return ``(sl, tp, rr_rejected)`` for a structural target.

**Exact API:** {py:obj}`trading.orders.entries.resolve_strategy_entry` · **Source:** [trading/orders/entries.py:636](../../../../trading/orders/entries.py#L636)

**Inputs and outputs:**

- **Args:**

  ```text
  strategy: Strategy used to select or evaluate trades.
  direction: Signed trade direction: 1 for long and -1 for short.
  entry_price: Price at which the position was opened.
  reward_fraction: Numeric value used for the reward fraction.
  feat_row: Feature values for the current market bar.
  min_dist: Numeric value used for the min dist.
  sl_anchor: Numeric value used for the sl anchor.
  buffer_pts: Numeric value used for the buffer pts.
  max_tp_distance: Numeric value used for the max tp distance.
  htf: Items supplied for the htf, in input order.
  ```

- **Returns:**

  ```text
  Whether resolve strategy entry meets the requested condition.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = resolve_strategy_entry(strategy=..., direction=..., entry_price=..., reward_fraction=..., feat_row=..., min_dist=..., sl_anchor=..., buffer_pts=..., max_tp_distance=..., htf=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`
