# Simulation · `backtest.event_driven_backtest`

This page contains 1 public callable records owned by `simulation.backtest.event_driven_backtest`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `run_backtest`

**Kind:** function · **Status:** stable · **Owner:** `simulation.backtest.event_driven_backtest`

**Purpose:** Run a full backtest over aligned bars + features.

**Exact API:** {py:obj}`simulation.backtest.event_driven_backtest.run_backtest` · **Source:** [simulation/backtest/event_driven_backtest.py:279](../../../../simulation/backtest/event_driven_backtest.py#L279)

**Inputs and outputs:**

- **Args:**

  ```text
  bars: Market bars to process.
  features: Feature values supplied to the operation.
  policy: Policy used to select or evaluate actions.
  obs_window: Numeric value used for the obs window.
  cost_model: Cost model used by the operation described above.
  broker_kwargs: Key-value data used for the broker kwargs.
  guardrail_kwargs: Key-value data used for the guardrail kwargs.
  initial_balance: Numeric value used for the initial balance.
  lots: Numeric value used for the lots.
  max_loss_per_trade_usd: Max loss per trade usd used by the operation described above.
  take_profit_per_trade_usd: Take profit per trade usd used by the operation described above.
  tickbook: Tickbook used by the operation described above.
  fill_delay_ms: Numeric value used for the fill delay ms.
  randomized_fill_latency_ms: Numeric value used for the randomized fill latency ms.
  max_tick_quote_wait_ms: Numeric value used for the max tick quote wait ms.
  tick_execution_required: Whether to enable or require the tick execution required.
  execution_seed: Numeric value used for the execution seed.
  use_structure_sl_tp: Whether to enable or require the use structure sl tp.
  risk_frac: Numeric value used for the risk frac.
  rr_ratio: Numeric value used for the rr ratio.
  swing_buffer_pts: Numeric value used for the swing buffer pts.
  min_lot: Numeric value used for the min lot.
  max_lot: Numeric value used for the max lot.
  contract_size: Number specifying the contract size for this operation.
  hold_on_zero: Whether to enable or require the hold on zero.
  exit_action: Exit action used by the operation described above.
  block_overnight: Whether to enable or require the block overnight.
  ```

- **Returns:**

  ```text
  Mapping from ``str`` keys to ``Any`` values.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = run_backtest(bars=..., features=..., policy=..., obs_window=..., cost_model=..., broker_kwargs=..., guardrail_kwargs=..., initial_balance=..., lots=..., max_loss_per_trade_usd=..., take_profit_per_trade_usd=..., tickbook=..., fill_delay_ms=..., randomized_fill_latency_ms=..., max_tick_quote_wait_ms=..., tick_execution_required=..., execution_seed=..., use_structure_sl_tp=..., risk_frac=..., rr_ratio=..., swing_buffer_pts=..., min_lot=..., max_lot=..., contract_size=..., hold_on_zero=..., exit_action=..., block_overnight=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`
