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

1. [production caller: `metrics_with_ci`](../../../../evaluation/metrics/bootstrap.py#L311)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        path = np.empty(sample.size + 1, dtype=np.float64)
        path[0] = eq[0]
        path[1:] = eq[0] * np.cumprod(1.0 + sample)
        return max_drawdown_stat(path)

    mdd_ci = bootstrap_ci(rets, reconstructed_drawdown, n_boot, level, rng_seed)
    # Bootstrap estimate should describe the observed path, including the
    # initial-capital observation and its first loss.
    mdd_ci = CI(max_drawdown_stat(eq), mdd_ci.lower, mdd_ci.upper, mdd_ci.level)
    return {
        "sharpe": bootstrap_ci(
# … caller assertions omitted …
```

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

1. [test fixture: `test_bootstrap_statistics_match_canonical_metric_definitions`](../../../../tests/unit/evaluation/test_metrics.py#L190)

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

2. [test fixture: `test_bootstrap_statistics_keep_empty_sample_conventions`](../../../../tests/unit/evaluation/test_metrics.py#L200)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_bootstrap_statistics_keep_empty_sample_conventions(self) -> None:
    empty = np.asarray([], dtype=np.float64)

    assert sharpe_stat(empty) == 0.0
    assert sortino_stat(empty) == 0.0
    assert math.isnan(max_drawdown_stat(empty))
    assert math.isnan(win_rate_stat(empty))
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

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = CI(...)
result = instance.as_tuple()
```

**Lifecycle context:** This callable participates in `CI`: A percentile confidence interval. Related public lifecycle methods: {py:obj}`evaluation.metrics.bootstrap.CI.as_tuple`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`
