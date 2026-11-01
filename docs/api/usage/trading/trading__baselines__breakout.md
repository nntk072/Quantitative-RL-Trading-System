# Trading · `baselines.breakout`

This page contains 1 public callable records owned by `trading.baselines.breakout`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `MultiLevelBreakoutStrategy`

**Kind:** class · **Status:** stable · **Owner:** `trading.baselines.breakout`

**Purpose:** Breakout baseline over Asian/London liquidity levels with ATR stops.

**Exact API:** {py:obj}`trading.baselines.breakout.MultiLevelBreakoutStrategy` · **Source:** [trading/baselines/breakout.py:17](../../../../trading/baselines/breakout.py#L17)

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = MultiLevelBreakoutStrategy(bars=..., volume_spike_threshold=..., atr_period=..., atr_stop_mult=..., size=...)
```

**Lifecycle context:** Breakout baseline over Asian/London liquidity levels with ATR stops.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`
