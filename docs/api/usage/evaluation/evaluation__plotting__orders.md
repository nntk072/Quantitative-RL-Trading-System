# Evaluation · `plotting.orders`

This page contains 2 public callable records owned by `evaluation.plotting.orders`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `plot_per_trade_orders`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.plotting.orders`

**Purpose:** Generate 2-panel PNG per trade with datetime axes, EMA50, MACD, and trade info.

**Exact API:** {py:obj}`evaluation.plotting.orders.plot_per_trade_orders` · **Source:** [evaluation/plotting/orders.py:626](../../../../evaluation/plotting/orders.py#L626)

**Inputs and outputs:**

- **Args:**

  ```text
  bars: M1 price bars with a ``DatetimeIndex`` and OHLC columns.
  trades: Trade log with type, direction, price, time, and PnL columns.
  orders_dir: Destination folder, created if absent.
  context_bars: M1 bars shown before entry and after exit.
  max_charts: Maximum number of charts; larger sets are sampled evenly.
  dpi: PNG resolution.
  max_loss_per_trade_usd: Maximum loss limit used for stop-loss calculation.
  take_profit_per_trade_usd: Take-profit limit used for target calculation.
  lots: Position size in lots.
  contract_size: Contract size used by chart price conversion.
  show_mae_mfe: Whether to display maximum adverse/favorable excursion lines.
  show_sl_tp: Whether to display stop-loss and take-profit lines.
  show_vwap: Whether to draw session VWAP. It requires real tick volume.
  secondary_bars: Optional correlated instrument bars used for SMT lines.
  features: Optional feature frame used for structure and setup overlays.
  order_block_timeframes: Timeframes whose order-block levels are displayed.
  fvg_timeframes: Timeframes whose fair-value gaps are displayed.
  ifvg_timeframes: Timeframes whose inverse fair-value gaps are displayed.
  ema_timeframes: Timeframes used for EMA overlays.
  swing_timeframes: Timeframes used for swing overlays.
  breakeven_buffer_pts: Buffer applied to displayed break-even levels.
  entry_idea_plot_config: Optional per-idea overlay configuration.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = plot_per_trade_orders(bars=..., trades=..., orders_dir=..., context_bars=..., max_charts=..., dpi=..., max_loss_per_trade_usd=..., take_profit_per_trade_usd=..., lots=..., contract_size=..., show_mae_mfe=..., show_sl_tp=..., show_vwap=..., secondary_bars=..., features=..., breakeven_buffer_pts=..., order_block_timeframes=..., fvg_timeframes=..., ifvg_timeframes=..., ema_timeframes=..., swing_timeframes=..., entry_idea_plot_config=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `plot_price_with_orders`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.plotting.orders`

**Purpose:** Candlestick chart with buy/sell/close markers.

**Exact API:** {py:obj}`evaluation.plotting.orders.plot_price_with_orders` · **Source:** [evaluation/plotting/orders.py:37](../../../../evaluation/plotting/orders.py#L37)

**Inputs and outputs:**

- **Args:**

  ```text
  bars: Market bars to process.
  trades: Trade records used to calculate the requested report or metric.
  max_points: Numeric value used for the max points.
  candle_tf: Text or path value identifying the candle tf.
  out_path: Path or filename identifying the out.
  dpi: Resolution of generated plots, in dots per inch.
  ```

- **Returns:**

  ```text
  Result of candlestick chart with buy/sell/close markers.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = plot_price_with_orders(bars=..., trades=..., max_points=..., candle_tf=..., out_path=..., dpi=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`
