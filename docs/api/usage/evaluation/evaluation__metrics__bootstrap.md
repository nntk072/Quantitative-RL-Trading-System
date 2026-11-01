# Evaluation · `metrics.bootstrap`

This page contains 4 public callable records owned by `evaluation.metrics.bootstrap`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `CI`

**Kind:** class · **Status:** stable · **Owner:** `evaluation.metrics.bootstrap`

**Purpose:** A percentile confidence interval.

**Exact API:** {py:obj}`evaluation.metrics.bootstrap.CI` · **Source:** [evaluation/metrics/bootstrap.py:22](../../../../evaluation/metrics/bootstrap.py#L22)

**Observed usage:**

1. [production caller: `bootstrap_ci`](../../../../evaluation/metrics/bootstrap.py#L67)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
    arr = np.asarray(values, dtype=np.float64)
    n = arr.size
    if n == 0:
        return CI(float("nan"), float("nan"), float("nan"), level)
    estimate = float(stat_fn(arr))
    if n == 1 or n_boot <= 0:
        return CI(estimate, estimate, estimate, level)

        # Moving-block starts require ``n - block_len + 1 > 0``; shrink the block
# … caller assertions omitted …
```

2. [production caller: `paired_metric_difference_ci`](../../../../evaluation/metrics/bootstrap.py#L127)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        raise ValueError("Paired return series must be one-dimensional and have the same length")
    if not np.isfinite(treatment).all() or not np.isfinite(control).all():
        raise ValueError("Paired return series must contain only finite returns")
    n = treatment.size
    if n == 0:
        return CI(float("nan"), float("nan"), float("nan"), level)
    estimate = float(stat_fn(treatment) - stat_fn(control))
    if n == 1 or n_boot <= 0:
        return CI(estimate, estimate, estimate, level)

    block_len = max(1, min(int(block_len), n))
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `bootstrap_ci`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.metrics.bootstrap`

**Purpose:** Percentile bootstrap CI for ``stat_fn(values)``.

**Exact API:** {py:obj}`evaluation.metrics.bootstrap.bootstrap_ci` · **Source:** [evaluation/metrics/bootstrap.py:39](../../../../evaluation/metrics/bootstrap.py#L39)

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

1. [production caller: `metrics_with_ci`](../../../../evaluation/metrics/bootstrap.py#L274)

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

**Exact API:** {py:obj}`evaluation.metrics.bootstrap.sharpe_stat` · **Source:** [evaluation/metrics/bootstrap.py:148](../../../../evaluation/metrics/bootstrap.py#L148)

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

1. [production caller: `metrics_with_ci`](../../../../evaluation/metrics/bootstrap.py#L280)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    # Bootstrap estimate should describe the observed path, including the
    # initial-capital observation and its first loss.
    mdd_ci = CI(max_drawdown_stat(eq), mdd_ci.lower, mdd_ci.upper, mdd_ci.level)
    return {
        "sharpe": bootstrap_ci(
            rets, lambda r: sharpe_stat(r, periods_per_year), n_boot, level, rng_seed
        ),
        "sortino": bootstrap_ci(
            rets, lambda r: sortino_stat(r, periods_per_year), n_boot, level, rng_seed
        ),
        "max_drawdown": mdd_ci,
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `CI.as_tuple`

**Kind:** method · **Status:** stable · **Owner:** `evaluation.metrics.bootstrap`

**Purpose:** Return the lower and upper confidence limits as a pair.

**Exact API:** {py:obj}`evaluation.metrics.bootstrap.CI.as_tuple` · **Source:** [evaluation/metrics/bootstrap.py:30](../../../../evaluation/metrics/bootstrap.py#L30)

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
