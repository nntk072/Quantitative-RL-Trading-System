# Trading · `risk.execution_reserve`

This page contains 1 public callable records owned by `trading.risk.execution_reserve`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `modeled_execution_reserve_usd`

**Kind:** function · **Status:** stable · **Owner:** `trading.risk.execution_reserve`

**Purpose:** Estimate execution costs reserved before sizing a trade.

**Exact API:** {py:obj}`trading.risk.execution_reserve.modeled_execution_reserve_usd` · **Source:** [trading/risk/execution_reserve.py:6](../../../../trading/risk/execution_reserve.py#L6)

**Inputs and outputs:**

- **Args:**

  ```text
  lots: Proposed position size in lots.
  slippage_points: Adverse slippage estimate in points per fill.
  commission_per_lot: Commission charged per lot per side.
  contract_size: Units represented by one lot.
  ```

- **Returns:**

  ```text
  Dollar reserve for adverse stop slippage and round-trip commission.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = modeled_execution_reserve_usd(lots=..., slippage_points=..., commission_per_lot=..., contract_size=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`
