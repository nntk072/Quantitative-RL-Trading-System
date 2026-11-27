# Trading · `baselines.lstm_classifier`

This page contains 4 public callable records owned by `trading.baselines.lstm_classifier`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `LSTMStrategy`

**Kind:** class · **Status:** stable · **Owner:** `trading.baselines.lstm_classifier`

**Purpose:** Fixed-position-size strategy driven by a trained classifier.

**Exact API:** {py:obj}`trading.baselines.lstm_classifier.LSTMStrategy` · **Source:** [trading/baselines/lstm_classifier.py:156](../../../../trading/baselines/lstm_classifier.py#L156)

**Observed usage:**

1. [test fixture: `test_lstm_strategy_precomputes_thresholded_actions_and_replays_by_index`](../../../../tests/unit/trading/test_lstm_classifier_contracts.py#L118)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_lstm_strategy_precomputes_thresholded_actions_and_replays_by_index() -> None:
    model = _DirectionModel()
    features = pd.DataFrame({"x": [-1.0, -1.0, 1.0, 0.0, np.nan]})

    strategy = LSTMStrategy(
        cast(Any, model), features, window=2, long_size=0.75, short_size=-0.5, threshold=0.8
    )

    assert model.eval_called
    assert not model.seen_nan
    assert [strategy.act_at(index) for index in range(len(features))] == [
        0.0,
# … caller assertions omitted …
```

2. [test fixture: `test_lstm_strategy_neutral_probabilities_do_not_cross_action_threshold`](../../../../tests/unit/trading/test_lstm_classifier_contracts.py#L144)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_lstm_strategy_neutral_probabilities_do_not_cross_action_threshold() -> None:
    model = _DirectionModel()
    features = pd.DataFrame({"x": [0.0, 0.0, 0.0]})

    strategy = LSTMStrategy(cast(Any, model), features, window=1, threshold=0.99)

    assert [strategy.act_at(index) for index in range(len(features))] == [0.0, 0.0, 0.0]
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `LSTMSweepClassifier`

**Kind:** class · **Status:** stable · **Owner:** `trading.baselines.lstm_classifier`

**Purpose:** Small LSTM over feature windows producing a 3-class direction logit.

**Exact API:** {py:obj}`trading.baselines.lstm_classifier.LSTMSweepClassifier` · **Source:** [trading/baselines/lstm_classifier.py:114](../../../../trading/baselines/lstm_classifier.py#L114)

**Observed usage:**

1. [test fixture: `test_lstm_classifier_forward_returns_three_direction_logits`](../../../../tests/unit/trading/test_lstm_classifier_contracts.py#L84)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_lstm_classifier_forward_returns_three_direction_logits() -> None:
    model = LSTMSweepClassifier(n_features=2, hidden_size=3, num_layers=2, dropout=0.25)

    logits = model(torch.zeros((4, 5, 2)))

    assert logits.shape == (4, 3)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

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

**Observed usage:**

1. [test fixture: `test_sweep_dataset_uses_first_future_crossing_and_zero_fills_features`](../../../../tests/unit/trading/test_lstm_classifier_contracts.py#L43)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    )
    monkeypatch.setattr(
        "trading.baselines.lstm_classifier.detect_session_levels", lambda _bars: levels
    )

    x, y = build_sweep_dataset(bars, features, window=2, horizon=2)

    assert x.dtype == torch.float32
    assert y.dtype == torch.int64
    assert y.tolist() == [1, -1, 1]
    assert x[0, :, 0].tolist() == [1.0, 0.0]
```

2. [test fixture: `test_sweep_dataset_handles_missing_levels_and_rejects_unusable_inputs`](../../../../tests/unit/trading/test_lstm_classifier_contracts.py#L68)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    monkeypatch.setattr(
        "trading.baselines.lstm_classifier.detect_session_levels", lambda _bars: no_levels
    )

    with pytest.raises(ValueError, match="No valid session levels"):
        build_sweep_dataset(bars, features, window=2, horizon=1)

    partial_levels = no_levels.copy()
    partial_levels.loc[bars.index[-1], "asian_high"] = 100.0
    monkeypatch.setattr(
        "trading.baselines.lstm_classifier.detect_session_levels", lambda _bars: partial_levels
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `LSTMSweepClassifier.forward`

**Kind:** method · **Status:** stable · **Owner:** `trading.baselines.lstm_classifier`

**Purpose:** Return logits of shape ``(batch, 3)`` for classes {-1, 0, 1}.

**Exact API:** {py:obj}`trading.baselines.lstm_classifier.LSTMSweepClassifier.forward` · **Source:** [trading/baselines/lstm_classifier.py:142](../../../../trading/baselines/lstm_classifier.py#L142)

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
