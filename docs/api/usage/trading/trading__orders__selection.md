# Trading · `orders.selection`

This page contains 4 public callable records owned by `trading.orders.selection`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `decode_tp_fractions`

**Kind:** function · **Status:** stable · **Owner:** `trading.orders.selection`

**Purpose:** Decode 2-D simplex logits into normalized fractions for active TP slots.

**Exact API:** {py:obj}`trading.orders.selection.decode_tp_fractions` · **Source:** [trading/orders/selection.py:148](../../../../trading/orders/selection.py#L148)

**Inputs and outputs:**

- **Args:**

  ```text
  z1: First simplex logit.
  z2: Second simplex logit.
  active_slots: Optional sequence of 3 slot states (index or bool) indicating
      which of (TP1, TP2, TP3) are active.
  ```

- **Returns:**

  ```text
  tuple of normalized fractions summing to 1.0 for the active slots.
  ```

**Observed usage:**

1. [test fixture: `test_simplex_decoder_sums_to_one`](../../../../tests/unit/simulation/test_environment/test_tp_action_contracts.py#L17)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_simplex_decoder_sums_to_one(self) -> None:
    f1, f2, f3 = decode_tp_fractions(0.0, 0.0)
    assert pytest.approx(f1 + f2 + f3, rel=1e-6) == 1.0
    assert pytest.approx(f1, rel=1e-6) == 1.0 / 3.0
    assert pytest.approx(f2, rel=1e-6) == 1.0 / 3.0
    assert pytest.approx(f3, rel=1e-6) == 1.0 / 3.0
```

2. [test fixture: `test_simplex_renormalize_active_levels`](../../../../tests/unit/simulation/test_environment/test_tp_action_contracts.py#L24)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_simplex_renormalize_active_levels(self) -> None:
    fracs = decode_tp_fractions(1.0, -1.0, active_slots=(True, True, True))
    assert len(fracs) == 3
    assert pytest.approx(sum(fracs), rel=1e-6) == 1.0
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `decode_tp_mode`

**Kind:** function · **Status:** stable · **Owner:** `trading.orders.selection`

**Purpose:** Decode TP mode from continuous action.

**Exact API:** {py:obj}`trading.orders.selection.decode_tp_mode` · **Source:** [trading/orders/selection.py:15](../../../../trading/orders/selection.py#L15)

**Inputs and outputs:**

- **Args:**

  ```text
  action_val: Action value in [-1, 1] (or [0, 1] if is_unit=True).
  default_mode: Fallback mode when within defer threshold.
  defer_threshold: Band around neutral (0.5 for unit, 0.0 for raw).
  is_unit: If True, action_val is in [0, 1]. If False, action_val is in [-1, 1].
  ```

- **Returns:**

  ```text
  tuple of (effective_mode, is_explicit).
  ```

**Observed usage:**

1. [test fixture: `test_hybrid_mode_centers_match_existing_box_decoders`](../../../../tests/unit/models/test_hybrid_actor.py#L62)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    assert _encoded_centers("exit", 0.0) == (-0.5, 0.5)
    assert _encoded_centers("entry_execution", 0.0) == (-0.5, 0.5)

    tp_centers = _encoded_centers("tp_mode", 0.1)
    decoded = [
        decode_tp_mode((center + 1.0) / 2.0, "fixed", 0.1, is_unit=True) for center in tp_centers
    ]
    assert decoded == [
        ("fixed", True),
        ("breakeven", True),
        ("fixed", False),
# … caller assertions omitted …
```

2. [test fixture: `test_tp_mode_agent_override`](../../../../tests/unit/simulation/test_environment/test_tp_mode_state.py#L175)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_tp_mode_agent_override(self) -> None:
    u_tp = 0.9  # Outside defer threshold of 0.1 (abs(0.9 - 0.5) = 0.4 > 0.1)
    default_mode = "fixed"
    defer_threshold = 0.1

    mode, is_explicit = decode_tp_mode(u_tp, default_mode, defer_threshold)

    assert mode == "trailing"  # Decoded to trailing (index 2)
    assert is_explicit  # Explicit, outside defer band
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `decode_tp_selections`

**Kind:** function · **Status:** stable · **Owner:** `trading.orders.selection`

**Purpose:** Decode raw TP selections into deterministic, slot-preserving menu indices.

**Exact API:** {py:obj}`trading.orders.selection.decode_tp_selections` · **Source:** [trading/orders/selection.py:74](../../../../trading/orders/selection.py#L74)

**Inputs and outputs:**

- **Args:**

  ```text
  tp1_raw: Raw selection for slot TP1 (int index, float continuous, or sentinel).
  tp2_raw: Raw selection for slot TP2.
  tp3_raw: Raw selection for slot TP3.
  menu_size: Number of available targets in target menu.
  continuous: If True, floats in [0, 1] are treated as continuous box coordinates.
  ```

- **Returns:**

  ```text
  tuple of (tp1_idx, tp2_idx, tp3_idx) where each is int or None (DISABLED).
  ```

**Observed usage:**

1. [test fixture: `test_tp_selection_disabled_middle_slot`](../../../../tests/unit/simulation/test_environment/test_tp_action_contracts.py#L82)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_tp_selection_disabled_middle_slot(self) -> None:
    # TP1 active, TP2 disabled, TP3 active
    s1, s2, s3 = decode_tp_selections(0, DISABLED, 2, menu_size=5)
    assert s1 == 0
    assert s2 is None
    assert s3 == 2
```

2. [test fixture: `test_tp_selection_duplicate_resolution`](../../../../tests/unit/simulation/test_environment/test_tp_action_contracts.py#L89)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
    def test_tp_selection_duplicate_resolution(self) -> None:
        # Duplicate 1, 1, 2 -> disable nearer slot (TP1)
        s1, s2, s3 = decode_tp_selections(1, 1, 2, menu_size=5)
        assert s1 is None
        assert s2 == 1
        assert s3 == 2

        # Duplicate 1, 2, 2 -> disable nearer slot (TP2)
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `validate_tp_levels`

**Kind:** function · **Status:** stable · **Owner:** `trading.orders.selection`

**Purpose:** Validate TP ordering and SL/TP crossing protection invariants.

**Exact API:** {py:obj}`trading.orders.selection.validate_tp_levels` · **Source:** [trading/orders/selection.py:198](../../../../trading/orders/selection.py#L198)

**Inputs and outputs:**

- **Args:**

  ```text
  direction: Trade direction (+1 long, -1 short).
  entry_price: Entry price.
  sl_price: Stop loss price or None.
  tp_prices: Sequence of (tp1_price, tp2_price, tp3_price) or active levels.
  raise_exc: Whether to raise ValueError on invalid ordering.
  ```

- **Returns:**

  ```text
  True if all invariants hold, False otherwise.
  ```

**Observed usage:**

1. [test fixture: `test_validate_tp_levels_long`](../../../../tests/unit/simulation/test_environment/test_tp_action_contracts.py#L203)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_validate_tp_levels_long(self) -> None:
    entry = 100.0
    sl = 98.0
    # Valid: SL < Entry <= TP1 < TP2 < TP3
    assert validate_tp_levels(1, entry, sl, [102.0, 104.0, 106.0])
    # Valid with middle disabled: SL < Entry <= TP1 < TP3
    assert validate_tp_levels(1, entry, sl, [102.0, None, 106.0])
    # Invalid: TP below entry
    assert not validate_tp_levels(1, entry, sl, [99.0, 104.0, 106.0])
    # Invalid: non-monotonic
    assert not validate_tp_levels(1, entry, sl, [105.0, 103.0, 106.0])
    # Invalid: TP below SL
    assert not validate_tp_levels(1, entry, sl, [97.0, None, 106.0])
```

2. [test fixture: `test_validate_tp_levels_short`](../../../../tests/unit/simulation/test_environment/test_tp_action_contracts.py#L218)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_validate_tp_levels_short(self) -> None:
    entry = 100.0
    sl = 102.0
    # Valid: TP3 < TP2 < TP1 <= Entry < SL
    # In slot order [TP1, TP2, TP3]: [98.0, 96.0, 94.0]
    assert validate_tp_levels(-1, entry, sl, [98.0, 96.0, 94.0])
    # Valid with middle disabled:
    assert validate_tp_levels(-1, entry, sl, [98.0, None, 94.0])
    # Invalid: TP above entry
    assert not validate_tp_levels(-1, entry, sl, [101.0, 96.0, 94.0])
    # Invalid: non-monotonic
    assert not validate_tp_levels(-1, entry, sl, [95.0, 97.0, 94.0])
    # Invalid: TP above SL
    assert not validate_tp_levels(-1, entry, sl, [103.0, None, 94.0])
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`
