# Evaluation · `plotting.equity`

This page contains 2 public callable records owned by `evaluation.plotting.equity`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `plot_drawdown`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.plotting.equity`

**Purpose:** Two-panel chart: peak-to-trough DD (%) and daily DD (USD).

**Exact API:** {py:obj}`evaluation.plotting.equity.plot_drawdown` · **Source:** [evaluation/plotting/equity.py:245](../../../../evaluation/plotting/equity.py#L245)

**Inputs and outputs:**

- **Args:**

  ```text
  equity: Current account equity in account currency.
  out_path: Path or filename identifying the out.
  dpi: Resolution of generated plots, in dots per inch.
  daily_loss_limit: Daily loss limit used by the operation described above.
  ```

- **Returns:**

  ```text
  Result of two-panel chart: peak-to-trough DD (%) and daily DD (USD).
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = plot_drawdown(equity=..., out_path=..., dpi=..., daily_loss_limit=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `plot_equity_curve`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.plotting.equity`

**Purpose:** Equity over time with peak line, FTMO threshold lines, and breach markers.

**Exact API:** {py:obj}`evaluation.plotting.equity.plot_equity_curve` · **Source:** [evaluation/plotting/equity.py:41](../../../../evaluation/plotting/equity.py#L41)

**Inputs and outputs:**

- **Args:**

  ```text
  equity: Current account equity in account currency.
  breaches: Items supplied for the breaches, in input order.
  breach_events: Items supplied for the breach events, in input order.
  initial_balance: Numeric value used for the initial balance.
  daily_loss_limit: Daily loss limit used by the operation described above.
  max_loss_limit: Max loss limit used by the operation described above.
  profit_target: Profit target used by the operation described above.
  trades: Trade records used to calculate the requested report or metric.
  out_path: Path or filename identifying the out.
  dpi: Resolution of generated plots, in dots per inch.
  ```

- **Returns:**

  ```text
  Result of equity over time with peak line, FTMO threshold lines, and breach markers.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = plot_equity_curve(equity=..., breaches=..., breach_events=..., initial_balance=..., daily_loss_limit=..., max_loss_limit=..., profit_target=..., trades=..., out_path=..., dpi=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`
