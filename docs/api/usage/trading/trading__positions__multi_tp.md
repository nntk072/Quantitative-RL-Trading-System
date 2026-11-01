# Trading · `positions.multi_tp`

This page contains 1 public callable records owned by `trading.positions.multi_tp`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `reorder_remaining_targets`

**Kind:** function · **Status:** stable · **Owner:** `trading.positions.multi_tp`

**Purpose:** Disable invalid remaining TP slots without fabricating target prices.

**Exact API:** {py:obj}`trading.positions.multi_tp.reorder_remaining_targets` · **Source:** [trading/positions/multi_tp.py:10](../../../../trading/positions/multi_tp.py#L10)

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
