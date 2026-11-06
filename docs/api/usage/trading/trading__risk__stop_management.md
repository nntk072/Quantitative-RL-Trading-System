# Trading · `risk.stop_management`

This page contains 3 public callable records owned by `trading.risk.stop_management`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `breakeven_stop_price`

**Kind:** function · **Status:** stable · **Owner:** `trading.risk.stop_management`

**Purpose:** Return a tighter breakeven stop when the favorable-R trigger is reached.

**Exact API:** {py:obj}`trading.risk.stop_management.breakeven_stop_price` · **Source:** [trading/risk/stop_management.py:117](../../../../trading/risk/stop_management.py#L117)

**Inputs and outputs:**

- **Args:**

  ```text
  direction: Position direction, ``1`` for long or ``-1`` for short.
  entry_price: Position entry price.
  initial_stop_price: Stop price that defines initial risk, if available.
  current_stop_price: Current stop that the new stop must tighten.
  best_favorable_points: Best favorable movement observed since entry.
  trigger_r: Favorable-movement threshold expressed in initial-risk units.
  buffer_points: Offset beyond entry in instrument points.
  ```

- **Returns:**

  ```text
  Tighter breakeven stop after the threshold, or ``None`` if not triggered.
  ```

- **Raises:**

  ```text
  ValueError: If direction, prices, or management settings are invalid.
  ```

**Observed usage:**

1. [test fixture: `test_breakeven_stop_mirrors_long_and_short`](../../../../tests/unit/trading/test_stop_management.py#L94)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_breakeven_stop_mirrors_long_and_short(
    direction: int, initial_stop: float, current_stop: float, expected: float
) -> None:
    result = breakeven_stop_price(
        direction=direction,
        entry_price=100.0,
        initial_stop_price=initial_stop,
        current_stop_price=current_stop,
        best_favorable_points=1.0,
        trigger_r=1.0,
        buffer_points=2.0,
    )

    assert result == pytest.approx(expected)
```

2. [test fixture: `test_breakeven_stop_never_widens_an_existing_stop`](../../../../tests/unit/trading/test_stop_management.py#L109)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_breakeven_stop_never_widens_an_existing_stop(direction: int, current_stop: float) -> None:
    result = breakeven_stop_price(
        direction=direction,
        entry_price=100.0,
        initial_stop_price=99.0 if direction == 1 else 101.0,
        current_stop_price=current_stop,
        best_favorable_points=5.0,
        trigger_r=1.0,
        buffer_points=2.0,
    )

    assert result is None
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `confirmed_swing_trailing_stop_price`

**Kind:** function · **Status:** stable · **Owner:** `trading.risk.stop_management`

**Purpose:** Return a confirmed-swing stop only when it tightens and stays protective.

**Exact API:** {py:obj}`trading.risk.stop_management.confirmed_swing_trailing_stop_price` · **Source:** [trading/risk/stop_management.py:8](../../../../trading/risk/stop_management.py#L8)

**Inputs and outputs:**

- **Args:**

  ```text
  direction: Position direction, ``1`` for long or ``-1`` for short.
  swing_price: Confirmed structural swing used as the stop reference.
  current_close: Latest close used to keep the stop beyond current price.
  current_stop_price: Existing stop, when one is already set.
  buffer_points: Distance applied beyond the swing in instrument points.
  ```

- **Returns:**

  ```text
  Tighter protective stop price, or ``None`` when it is not valid.
  ```

**Observed usage:**

1. [test fixture: `test_confirmed_swing_trailing_stop_is_tighter_and_protective`](../../../../tests/unit/trading/test_stop_management.py#L47)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    swing: float,
    close: float | None,
    current_stop: float | None,
    expected: float | None,
) -> None:
    result = confirmed_swing_trailing_stop_price(
        direction=direction,
        swing_price=swing,
        current_close=close,
        current_stop_price=current_stop,
        buffer_points=0.1,
    )

    if expected is None:
        assert result is None
    else:
        assert result == pytest.approx(expected)
```

2. [test fixture: `test_confirmed_swing_trailing_stop_rejects_invalid_inputs`](../../../../tests/unit/trading/test_stop_management.py#L78)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    current_stop: float,
    buffer: float,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        confirmed_swing_trailing_stop_price(
            direction=direction,
            swing_price=swing,
            current_close=close,
            current_stop_price=current_stop,
            buffer_points=buffer,
        )
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `tightened_breakeven_stop_price`

**Kind:** function · **Status:** stable · **Owner:** `trading.risk.stop_management`

**Purpose:** Return a buffered breakeven stop only when it tightens the current stop.

**Exact API:** {py:obj}`trading.risk.stop_management.tightened_breakeven_stop_price` · **Source:** [trading/risk/stop_management.py:67](../../../../trading/risk/stop_management.py#L67)

**Inputs and outputs:**

- **Args:**

  ```text
  direction: Position direction, ``1`` for long or ``-1`` for short.
  entry_price: Position entry price used as the breakeven reference.
  current_stop_price: Existing stop price, if present.
  buffer_points: Offset beyond entry in instrument points.
  ```

- **Returns:**

  ```text
  Improved breakeven stop price, or ``None`` if it would not tighten.
  ```

**Observed usage:**

1. [test fixture: `test_tightened_breakeven_stop_only_returns_a_tighter_level`](../../../../tests/unit/trading/test_stop_management.py#L129)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_tightened_breakeven_stop_only_returns_a_tighter_level(
    direction: int, current_stop: float, expected: float | None
) -> None:
    result = tightened_breakeven_stop_price(
        direction=direction,
        entry_price=100.0,
        current_stop_price=current_stop,
        buffer_points=0.2,
    )

    if expected is None:
        assert result is None
    else:
        assert result == pytest.approx(expected)
```

2. [production caller: `breakeven_stop_price`](../../../../trading/risk/stop_management.py#L196)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    if not math.isfinite(risk_points) or not math.isfinite(trigger_points):
        raise ValueError("initial risk and breakeven trigger distance must remain finite")
    if risk_points <= 0.0 or favorable < trigger_points:
        return None

    return tightened_breakeven_stop_price(
        direction=direction,
        entry_price=entry,
        current_stop_price=normalized.get("current_stop_price"),
        buffer_points=buffer,
    )
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`
