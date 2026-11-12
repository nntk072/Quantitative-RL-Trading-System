# Trading · `baselines.rule_based`

This page contains 4 public callable records owned by `trading.baselines.rule_based`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `ema_crossover`

**Kind:** function · **Status:** stable · **Owner:** `trading.baselines.rule_based`

**Purpose:** Return the directional EMA trend signal aligned to ``bars.index``.

**Exact API:** {py:obj}`trading.baselines.rule_based.ema_crossover` · **Source:** [trading/baselines/rule_based.py:28](../../../../trading/baselines/rule_based.py#L28)

**Inputs and outputs:**

- **Args:**

  ```text
  bars: Market bars to process.
  fast: Numeric value used for the fast.
  slow: Numeric value used for the slow.
  atr_period: Legacy compatibility argument; unused by the signal.
  atr_stop_mult: Legacy compatibility argument; unused by the signal.
  ```

- **Returns:**

  ```text
  ``+1`` for a bullish EMA trend, ``-1`` for a bearish trend, or ``0``
  when the averages are equal.
  ```

**Observed usage:**

1. [test fixture: `test_legacy_atr_arguments_do_not_claim_or_change_signal_exit_semantics`](../../../../tests/unit/trading/test_rule_based_baselines_causality.py#L56)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_legacy_atr_arguments_do_not_claim_or_change_signal_exit_semantics() -> None:
    bars = _bars()

    pd.testing.assert_series_equal(
        ema_crossover(bars, atr_period=3, atr_stop_mult=0.5),
        ema_crossover(bars, atr_period=40, atr_stop_mult=5.0),
    )
    pd.testing.assert_series_equal(
        rsi_mean_reversion(bars, atr_period=3),
        rsi_mean_reversion(bars, atr_period=40),
    )
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `macd_baseline`

**Kind:** function · **Status:** stable · **Owner:** `trading.baselines.rule_based`

**Purpose:** MACD histogram sign → signal.

**Exact API:** {py:obj}`trading.baselines.rule_based.macd_baseline` · **Source:** [trading/baselines/rule_based.py:60](../../../../trading/baselines/rule_based.py#L60)

**Inputs and outputs:**

- **Args:**

  ```text
  bars: Market bars to process.
  ```

- **Returns:**

  ```text
  Result of mACD histogram sign → signal.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = macd_baseline(bars=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `macd_ema50_baseline`

**Kind:** function · **Status:** stable · **Owner:** `trading.baselines.rule_based`

**Purpose:** MACD+EMA50 baseline with cross-only entry/exit and 5-bar cooldown.

**Exact API:** {py:obj}`trading.baselines.rule_based.macd_ema50_baseline` · **Source:** [trading/baselines/rule_based.py:76](../../../../trading/baselines/rule_based.py#L76)

**Inputs and outputs:**

- **Args:**

  ```text
  bars: Market bars to process.
  fast: Numeric value used for the fast.
  slow: Numeric value used for the slow.
  signal_period: Numeric value used for the signal period.
  ema50_period: Numeric value used for the ema50 period.
  cooldown_bars: Market bar or price data used for mACD+EMA50 baseline with cross-only entry/exit and 5-bar cooldown.
  ```

- **Returns:**

  ```text
  Result of mACD+EMA50 baseline with cross-only entry/exit and 5-bar cooldown.
  ```

**Observed usage:**

1. [test fixture: `test_macd_backtest_fills_within_bar_and_charts_render`](../../../../tests/unit/evaluation/test_plots_export.py#L574)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        },
        index=idx,
    )

    features = build_features(bars, cfg=None)
    actions = macd_ema50_baseline(bars)

    obs_window = 60
    state = {"i": obs_window}

    def policy(obs):
# … caller assertions omitted …
```

2. [test fixture: `test_macd_baseline_returns_series`](../../../../tests/unit/trading/test_macd_baseline.py#L37)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_macd_baseline_returns_series(sample_bars):
    actions = macd_ema50_baseline(sample_bars)
    assert isinstance(actions, pd.Series)
    assert len(actions) == len(sample_bars)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `rsi_mean_reversion`

**Kind:** function · **Status:** stable · **Owner:** `trading.baselines.rule_based`

**Purpose:** Return an RSI mean-reversion signal with a neutral-zone exit.

**Exact API:** {py:obj}`trading.baselines.rule_based.rsi_mean_reversion` · **Source:** [trading/baselines/rule_based.py:176](../../../../trading/baselines/rule_based.py#L176)

**Inputs and outputs:**

- **Args:**

  ```text
  bars: Market bars to process.
  period: Numeric value used for the period.
  oversold: Numeric value used for the oversold.
  overbought: Numeric value used for the overbought.
  atr_period: Legacy compatibility argument; unused by the signal.
  ```

- **Returns:**

  ```text
  A stateful position signal: enter long below ``oversold`` or short
  above ``overbought``; hold that side until RSI enters the 45–55 neutral
  zone, then return to flat. Opposite entries require first becoming flat.
  ```

**Observed usage:**

1. [test fixture: `test_legacy_atr_arguments_do_not_claim_or_change_signal_exit_semantics`](../../../../tests/unit/trading/test_rule_based_baselines_causality.py#L60)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_legacy_atr_arguments_do_not_claim_or_change_signal_exit_semantics() -> None:
    bars = _bars()

    pd.testing.assert_series_equal(
        ema_crossover(bars, atr_period=3, atr_stop_mult=0.5),
        ema_crossover(bars, atr_period=40, atr_stop_mult=5.0),
    )
    pd.testing.assert_series_equal(
        rsi_mean_reversion(bars, atr_period=3),
        rsi_mean_reversion(bars, atr_period=40),
    )
```

2. [test fixture: `test_rsi_mean_reversion_holds_until_neutral_then_rearms`](../../../../tests/unit/trading/test_rule_based_baselines_causality.py#L72)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_rsi_mean_reversion_holds_until_neutral_then_rearms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bars = _bars().iloc[:9]
    rsi_values = pd.Series([60.0, 25.0, 35.0, 44.9, 45.0, 75.0, 60.0, 55.0, 25.0])
    monkeypatch.setattr(rule_based, "_rsi", lambda _close, _period: rsi_values)

    signals = rsi_mean_reversion(bars)

    assert signals.tolist() == [0, 1, 1, 1, 0, -1, -1, 0, 1]
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`
