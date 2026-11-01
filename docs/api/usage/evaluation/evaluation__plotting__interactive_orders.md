# Evaluation · `plotting.interactive_orders`

This page contains 1 public callable records owned by `evaluation.plotting.interactive_orders`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `plot_per_trade_orders_html`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.plotting.interactive_orders`

**Purpose:** Generate one M1 candlestick HTML per trade in *orders_dir* with MT5-style overlays.

**Exact API:** {py:obj}`evaluation.plotting.interactive_orders.plot_per_trade_orders` · **Source:** [evaluation/plotting/interactive_orders.py:217](../../../../evaluation/plotting/interactive_orders.py#L217)

**Inputs and outputs:**

- **Args:**

  ```text
  bars: M1 OHLC bars indexed by timestamp.
  trades: Trade log containing direction, prices, times, and P&L.
  orders_dir: Destination directory, created when absent.
  context_bars: Number of bars to show around each trade.
  max_charts: Maximum charts to write; over-limit trades are sampled evenly.
  max_loss_per_trade_usd: Optional loss limit used to derive stop levels.
  take_profit_per_trade_usd: Optional profit limit used to derive target levels.
  lots: Position size used to convert price movement to currency.
  contract_size: Units represented by one lot.
  show_mae_mfe: Whether to draw maximum adverse and favorable excursion lines.
  show_sl_tp: Whether to draw stop-loss and take-profit levels.
  show_vwap: Whether to draw session VWAP; disabled by default without real tick volume.
  secondary_bars: Optional correlated-instrument bars used for SMT overlays.
  features: Optional feature frame used for structure and context overlays.
  order_block_timeframes: Timeframes whose order blocks should be shown.
  fvg_timeframes: Timeframes whose fair-value gaps should be shown.
  ifvg_timeframes: Timeframes whose inverse fair-value gaps should be shown.
  ema_timeframes: Timeframes used to draw EMA overlays.
  swing_timeframes: Timeframes used to draw confirmed swing levels.
  entry_idea_plot_config: Optional settings selecting entry-idea overlays.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = plot_per_trade_orders(bars=..., trades=..., orders_dir=..., context_bars=..., max_charts=..., max_loss_per_trade_usd=..., take_profit_per_trade_usd=..., lots=..., contract_size=..., show_mae_mfe=..., show_sl_tp=..., show_vwap=..., secondary_bars=..., features=..., order_block_timeframes=..., fvg_timeframes=..., ifvg_timeframes=..., ema_timeframes=..., swing_timeframes=..., entry_idea_plot_config=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`
