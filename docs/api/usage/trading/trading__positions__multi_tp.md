# Trading · `positions.multi_tp`

This page contains 2 public callable records owned by `trading.positions.multi_tp`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `reorder_remaining_targets`

**Kind:** function · **Status:** stable · **Owner:** `trading.positions.multi_tp`

**Purpose:** Disable invalid remaining TP slots without fabricating target prices.

**Exact API:** {py:obj}`trading.positions.multi_tp.reorder_remaining_targets` · **Source:** [trading/positions/multi_tp.py:50](../../../../trading/positions/multi_tp.py#L50)

**Inputs and outputs:**

- **Args:**

  ```text
  pos: Pos used by the operation described above.
  point_size: Number specifying the point size for this operation.
  price_tolerance: Numeric value used for the price tolerance.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = reorder_remaining_targets(pos=..., point_size=..., price_tolerance=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `target_close_size`

**Kind:** function · **Status:** stable · **Owner:** `trading.positions.multi_tp`

**Purpose:** Return a target leg's close size while preserving a configured runner.

**Exact API:** {py:obj}`trading.positions.multi_tp.target_close_size` · **Source:** [trading/positions/multi_tp.py:10](../../../../trading/positions/multi_tp.py#L10)

**Inputs and outputs:**

- **Args:**

  ```text
  pos: Position containing initial size and target allocation settings.
  slot_num: Take-profit slot being closed.
  is_final: Whether this is the last active target slot.
  ```

- **Returns:**

  ```text
  Lot size to close while retaining the configured runner when applicable.
  ```

**Observed usage:**

1. [test fixture: `_run_sizing_case`](../../../../tests/unit/trading/test_semantic_oracle_fixture_replay.py#L176)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            ema_runner_fraction=float(args["runner_fraction"]),
        )
        for slot in (1, 2, 3):
            if slot in slots:
                setattr(position, f"tp{slot}_price", 100.0 + slot)
        return target_close_size(position, int(args["slot"]), is_final=bool(args["is_final"]))
    raise UnknownOperationError(op)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`
