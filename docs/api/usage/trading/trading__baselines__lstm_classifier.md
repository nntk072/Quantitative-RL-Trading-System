# Trading · `baselines.lstm_classifier`

This page contains 4 public callable records owned by `trading.baselines.lstm_classifier`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `LSTMStrategy`

**Kind:** class · **Status:** stable · **Owner:** `trading.baselines.lstm_classifier`

**Purpose:** Fixed-position-size strategy driven by a trained classifier.

**Exact API:** {py:obj}`trading.baselines.lstm_classifier.LSTMStrategy` · **Source:** [trading/baselines/lstm_classifier.py:148](../../../../trading/baselines/lstm_classifier.py#L148)

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = LSTMStrategy(model=..., features=..., window=..., long_size=..., short_size=..., threshold=...)
```

**Lifecycle context:** Fixed-position-size strategy driven by a trained classifier.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `LSTMSweepClassifier`

**Kind:** class · **Status:** stable · **Owner:** `trading.baselines.lstm_classifier`

**Purpose:** Small LSTM over feature windows producing a 3-class direction logit.

**Exact API:** {py:obj}`trading.baselines.lstm_classifier.LSTMSweepClassifier` · **Source:** [trading/baselines/lstm_classifier.py:106](../../../../trading/baselines/lstm_classifier.py#L106)

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = LSTMSweepClassifier(n_features=..., hidden_size=..., num_layers=..., dropout=...)
```

**Lifecycle context:** Small LSTM over feature windows producing a 3-class direction logit.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `build_sweep_dataset`

**Kind:** function · **Status:** stable · **Owner:** `trading.baselines.lstm_classifier`

**Purpose:** Build labelled (features-window, direction) pairs for training.

**Exact API:** {py:obj}`trading.baselines.lstm_classifier.build_sweep_dataset` · **Source:** [trading/baselines/lstm_classifier.py:25](../../../../trading/baselines/lstm_classifier.py#L25)

**Inputs and outputs:**

- **Args:**

  ```text
  bars: OHLCV DataFrame with DatetimeIndex.
  features: Feature matrix aligned row-for-row with ``bars``.
  window: Number of past feature rows per sample.
  horizon: Look-ahead bars for labelling.
  ```

- **Returns:**

  ```text
  Tuple ``(X, y)`` where ``X`` is ``(n_samples, window, n_features)``
  float32 and ``y`` is ``(n_samples,)`` int64 with values in {-1, 0, 1}.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = build_sweep_dataset(bars=..., features=..., window=..., horizon=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `LSTMSweepClassifier.forward`

**Kind:** method · **Status:** stable · **Owner:** `trading.baselines.lstm_classifier`

**Purpose:** Return logits of shape ``(batch, 3)`` for classes {-1, 0, 1}.

**Exact API:** {py:obj}`trading.baselines.lstm_classifier.LSTMSweepClassifier.forward` · **Source:** [trading/baselines/lstm_classifier.py:134](../../../../trading/baselines/lstm_classifier.py#L134)

**Inputs and outputs:**

- **Args:**

  ```text
  x: X used by the operation described above.
  ```

- **Returns:**

  ```text
  Result of return logits of shape ``(batch, 3)`` for classes {-1, 0, 1}.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = LSTMSweepClassifier(...)
result = instance.forward(x=...)
```

**Lifecycle context:** This callable participates in `LSTMSweepClassifier`: Small LSTM over feature windows producing a 3-class direction logit. Related public lifecycle methods: {py:obj}`trading.baselines.lstm_classifier.LSTMSweepClassifier.forward`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`
