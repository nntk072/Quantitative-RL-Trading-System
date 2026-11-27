# Evaluation · `metrics.bootstrap`

This page contains 4 public callable records owned by `evaluation.metrics.bootstrap`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `CI`

**Kind:** class · **Status:** stable · **Owner:** `evaluation.metrics.bootstrap`

**Purpose:** A percentile confidence interval.

**Exact API:** {py:obj}`evaluation.metrics.bootstrap.CI` · **Source:** [evaluation/metrics/bootstrap.py:62](../../../../evaluation/metrics/bootstrap.py#L62)

**Observed usage:**

1. [production caller: `bootstrap_ci`](../../../../evaluation/metrics/bootstrap.py#L108)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
    _validate_bootstrap_parameters(n_boot, level, block_len)
    arr = _finite_vector(values, "values")
    n = arr.size
    if n == 0:
        return CI(float("nan"), float("nan"), float("nan"), level)
    estimate = float(stat_fn(arr))
    if n == 1 or n_boot == 0:
        return CI(estimate, estimate, estimate, level)

    # Moving-block starts require ``n - block_len + 1 > 0``; shrink the block
# … caller assertions omitted …
```

2. [production caller: `paired_metric_difference_ci`](../../../../evaluation/metrics/bootstrap.py#L167)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    control = _finite_vector(control_returns, "control_returns")
    if treatment.ndim != 1 or control.ndim != 1 or treatment.size != control.size:
        raise ValueError("Paired return series must be one-dimensional and have the same length")
    n = treatment.size
    if n == 0:
        return CI(float("nan"), float("nan"), float("nan"), level)
    estimate = float(stat_fn(treatment) - stat_fn(control))
    if n == 1 or n_boot == 0:
        return CI(estimate, estimate, estimate, level)

    block_len = min(int(block_len), n)
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `bootstrap_ci`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.metrics.bootstrap`

**Purpose:** Percentile bootstrap CI for ``stat_fn(values)``.

**Exact API:** {py:obj}`evaluation.metrics.bootstrap.bootstrap_ci` · **Source:** [evaluation/metrics/bootstrap.py:79](../../../../evaluation/metrics/bootstrap.py#L79)

**Inputs and outputs:**

- **Args:**

  ```text
  values: Values to process, in input order.
  stat_fn: Stat fn used by the operation described above.
  n_boot: Numeric value used for the n boot.
  level: Numeric value used for the level.
  rng_seed: Numeric value used for the rng seed.
  block_len: Numeric value used for the block len.
  ```

- **Returns:**

  ```text
  Result of percentile bootstrap CI for ``stat_fn(values)``.
  ```

**Observed usage:**

1. [test fixture: `test_bootstrap_rejects_invalid_resampling_parameters`](../../../../tests/unit/evaluation/test_bootstrap_edge_cases.py#L34)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_bootstrap_rejects_invalid_resampling_parameters(
    n_boot: int, level: float, block_len: int, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        bootstrap_ci(np.asarray([1.0, 2.0]), np.mean, n_boot, level, block_len=block_len)
```

2. [test fixture: `test_bootstrap_short_empty_and_nonfinite_statistic_paths`](../../../../tests/unit/evaluation/test_bootstrap_edge_cases.py#L38)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_bootstrap_short_empty_and_nonfinite_statistic_paths() -> None:
    empty = bootstrap_ci(np.asarray([]), np.mean, n_boot=4)
    assert math.isnan(empty.estimate) and math.isnan(empty.lower) and math.isnan(empty.upper)

    one = bootstrap_ci(np.asarray([3.0]), np.mean, n_boot=4)
    assert one.as_tuple() == (3.0, 3.0, 3.0)
    no_resamples = bootstrap_ci(np.asarray([1.0, 3.0]), np.mean, n_boot=0)
    assert no_resamples.as_tuple() == (2.0, 2.0, 2.0)

    short_blocks = bootstrap_ci(np.asarray([1.0, 3.0]), np.mean, n_boot=5, block_len=8)
    assert short_blocks.estimate == pytest.approx(2.0)
    all_nan = bootstrap_ci(np.asarray([1.0, 2.0]), lambda _values: float("nan"), n_boot=3)
    assert math.isnan(all_nan.lower) and math.isnan(all_nan.upper)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `sharpe_stat`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.metrics.bootstrap`

**Purpose:** Sharpe of bar returns (annualisation matching evaluation/metrics).

**Exact API:** {py:obj}`evaluation.metrics.bootstrap.sharpe_stat` · **Source:** [evaluation/metrics/bootstrap.py:188](../../../../evaluation/metrics/bootstrap.py#L188)

**Inputs and outputs:**

- **Args:**

  ```text
  returns: Returns used by the operation described above.
  periods_per_year: Numeric value used for the periods per year.
  ```

- **Returns:**

  ```text
  Numeric result returned by ``sharpe_stat``.
  ```

**Observed usage:**

1. [test fixture: `test_bootstrap_metric_wrappers_validate_inputs_and_initial_balance`](../../../../tests/unit/evaluation/test_bootstrap_edge_cases.py#L75)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_bootstrap_metric_wrappers_validate_inputs_and_initial_balance() -> None:
    with pytest.raises(ValueError, match="periods_per_year"):
        sharpe_stat(np.asarray([1.0]), periods_per_year=0)
    with pytest.raises(ValueError, match="periods_per_year"):
        sortino_stat(np.asarray([1.0]), periods_per_year=0)
    with pytest.raises(ValueError, match="one-dimensional"):
        sharpe_stat(np.asarray([[1.0, 2.0]]))
    with pytest.raises(ValueError, match="finite"):
# … caller assertions omitted …
```

2. [test fixture: `test_bootstrap_statistics_match_canonical_metric_definitions`](../../../../tests/unit/evaluation/test_metrics.py#L230)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            initial_balance=100.0,
            trade_pnls=trade_pnls,
            periods_per_year=12,
        )

        assert sharpe_stat(returns, periods_per_year=12) == pytest.approx(canonical.sharpe)
        assert sortino_stat(returns, periods_per_year=12) == pytest.approx(canonical.sortino)
        assert max_drawdown_stat(equity) == pytest.approx(canonical.max_drawdown)
        assert win_rate_stat(np.asarray(trade_pnls, dtype=np.float64)) == pytest.approx(
            canonical.win_rate
        )
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `CI.as_tuple`

**Kind:** method · **Status:** stable · **Owner:** `evaluation.metrics.bootstrap`

**Purpose:** Return the lower and upper confidence limits as a pair.

**Exact API:** {py:obj}`evaluation.metrics.bootstrap.CI.as_tuple` · **Source:** [evaluation/metrics/bootstrap.py:70](../../../../evaluation/metrics/bootstrap.py#L70)

**Inputs and outputs:**

- **Returns:**

  ```text
  Values returned by ``as_tuple``, in the declared order.
  ```

**Observed usage:**

1. [test fixture: `test_bootstrap_short_empty_and_nonfinite_statistic_paths`](../../../../tests/unit/evaluation/test_bootstrap_edge_cases.py#L42)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_bootstrap_short_empty_and_nonfinite_statistic_paths() -> None:
    empty = bootstrap_ci(np.asarray([]), np.mean, n_boot=4)
    assert math.isnan(empty.estimate) and math.isnan(empty.lower) and math.isnan(empty.upper)

    one = bootstrap_ci(np.asarray([3.0]), np.mean, n_boot=4)
    assert one.as_tuple() == (3.0, 3.0, 3.0)
    no_resamples = bootstrap_ci(np.asarray([1.0, 3.0]), np.mean, n_boot=0)
    assert no_resamples.as_tuple() == (2.0, 2.0, 2.0)

    short_blocks = bootstrap_ci(np.asarray([1.0, 3.0]), np.mean, n_boot=5, block_len=8)
    assert short_blocks.estimate == pytest.approx(2.0)
    all_nan = bootstrap_ci(np.asarray([1.0, 2.0]), lambda _values: float("nan"), n_boot=3)
    assert math.isnan(all_nan.lower) and math.isnan(all_nan.upper)
```

2. [test fixture: `test_paired_bootstrap_uses_aligned_series_and_short_sample_conventions`](../../../../tests/unit/evaluation/test_bootstrap_edge_cases.py#L59)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        return float(np.mean(values))

    empty = paired_metric_difference_ci(np.asarray([]), np.asarray([]), stat)
    assert math.isnan(empty.estimate)
    exact = paired_metric_difference_ci(np.asarray([3.0]), np.asarray([1.0]), stat, n_boot=4)
    assert exact.as_tuple() == (2.0, 2.0, 2.0)
    no_resamples = paired_metric_difference_ci(
        np.asarray([2.0, 4.0]), np.asarray([1.0, 1.0]), stat, n_boot=0
    )
    assert no_resamples.as_tuple() == (2.0, 2.0, 2.0)
    sampled = paired_metric_difference_ci(
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`
