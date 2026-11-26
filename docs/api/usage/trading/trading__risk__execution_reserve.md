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
  point_value: Account-currency value of one price unit per contract.
  ```

- **Returns:**

  ```text
  Dollar reserve for adverse stop slippage and round-trip commission.
  ```

**Observed usage:**

1. [test fixture: `_run_sizing_case`](../../../../tests/unit/trading/test_semantic_oracle_fixture_replay.py#L154)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    if op == "compute_lots":
        return compute_lots(**args)
    if op == "compute_lots_with_execution_reserve":
        return compute_lots_with_execution_reserve(**args)
    if op == "modeled_execution_reserve_usd":
        return modeled_execution_reserve_usd(**args)
    if op == "compute_sl_tp_long":
        return list(compute_sl_tp_long(**args))
    if op == "compute_sl_tp_short":
        return list(compute_sl_tp_short(**args))
    if op == "compute_sl_tp_from_structure":
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`
