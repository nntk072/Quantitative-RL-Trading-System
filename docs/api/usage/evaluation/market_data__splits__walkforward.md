# Evaluation · `market_data.splits.walkforward`

This page contains 2 public callable records owned by `market_data.splits.walkforward`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `WFSplit`

**Kind:** class · **Status:** stable · **Owner:** `market_data.splits.walkforward`

**Purpose:** Indices and metadata for one purged walk-forward fold.

**Exact API:** {py:obj}`market_data.splits.walkforward.WFSplit` · **Source:** [market_data/splits/walkforward.py:23](../../../../market_data/splits/walkforward.py#L23)

**Inputs and outputs:**

**Observed usage:**

1. [production caller: `purged_walk_forward`](../../../../market_data/splits/walkforward.py#L88)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …

        train_idx = np.arange(0, train_end_purged)
        test_idx = np.arange(test_start, test_end)
        if len(test_idx) == 0:
            continue
        yield WFSplit(train_idx=train_idx, test_idx=test_idx, fold=fold)
```

2. [production caller: `purged_walk_forward_legacy`](../../../../market_data/splits/walkforward.py#L136)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        test_idx = np.arange(test_start, test_end)

        if len(test_idx) == 0:
            continue

        yield WFSplit(train_idx=train_idx, test_idx=test_idx, fold=fold)
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `purged_walk_forward`

**Kind:** function · **Status:** stable · **Owner:** `market_data.splits.walkforward`

**Purpose:** Yield expanding walk-forward splits with non-overlapping test folds.

**Exact API:** {py:obj}`market_data.splits.walkforward.purged_walk_forward` · **Source:** [market_data/splits/walkforward.py:37](../../../../market_data/splits/walkforward.py#L37)

**Inputs and outputs:**

- **Args:**

  ```text
  n: Total number of samples.
  n_splits: Number of folds.
  test_size: Fraction of ``n`` used as the combined test budget.
  purge_bars: Bars removed from the end of train (feature lookback).
  embargo_bars: Extra gap between train end and test start.
  label_horizon: Extra purge bars for label/episode horizon (added to ``purge_bars``).
  ```

- **Yields:**

  ```text
  Each purged walk forward value, yielded in processing order.
  ```

**Observed usage:**

1. [test fixture: `test_purged_walk_forward_yields_expected_splits`](../../../../tests/unit/market_data/test_walkforward.py#L16)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_purged_walk_forward_yields_expected_splits() -> None:
    splits = list(purged_walk_forward(n=1000, n_splits=5))
    assert len(splits) == 5

    for split in splits:
        assert isinstance(split, WFSplit)
        assert split.fold >= 0
        assert len(split.train_idx) > 0
        assert len(split.test_idx) > 0
```

2. [test fixture: `test_no_leakage_between_train_and_test`](../../../../tests/unit/market_data/test_walkforward.py#L28)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_no_leakage_between_train_and_test() -> None:
    splits = list(purged_walk_forward(n=1000, n_splits=5))
    for split in splits:
        assert split.train_idx.max() < split.test_idx.min() - 60
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`
