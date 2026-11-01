# Trading · `baselines.classical`

This page contains 3 public callable records owned by `trading.baselines.classical`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `BuyAndHoldStrategy`

**Kind:** class · **Status:** stable · **Owner:** `trading.baselines.classical`

**Purpose:** Long-only hold. ``mode`` selects how often a new long is requested.

**Exact API:** {py:obj}`trading.baselines.classical.BuyAndHoldStrategy` · **Source:** [trading/baselines/classical.py:34](../../../../trading/baselines/classical.py#L34)

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = BuyAndHoldStrategy(n_bars=..., size=..., bars=..., mode=..., tz=..., entry_from=...)
```

**Lifecycle context:** Long-only hold. ``mode`` selects how often a new long is requested.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `EMAMACDRSIStrategy`

**Kind:** class · **Status:** stable · **Owner:** `trading.baselines.classical`

**Purpose:** Trend-following baseline combining EMA cross, MACD and RSI filter.

**Exact API:** {py:obj}`trading.baselines.classical.EMAMACDRSIStrategy` · **Source:** [trading/baselines/classical.py:102](../../../../trading/baselines/classical.py#L102)

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = EMAMACDRSIStrategy(bars=..., ema_fast=..., ema_slow=..., rsi_period=..., rsi_overbought=..., rsi_oversold=...)
```

**Lifecycle context:** Trend-following baseline combining EMA cross, MACD and RSI filter.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `SessionMomentumStrategy`

**Kind:** class · **Status:** stable · **Owner:** `trading.baselines.classical`

**Purpose:** Hold the sign of the previous NY session's close-to-close return.

**Exact API:** {py:obj}`trading.baselines.classical.SessionMomentumStrategy` · **Source:** [trading/baselines/classical.py:157](../../../../trading/baselines/classical.py#L157)

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = SessionMomentumStrategy(bars=..., tz=...)
```

**Lifecycle context:** Hold the sign of the previous NY session's close-to-close return.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`
