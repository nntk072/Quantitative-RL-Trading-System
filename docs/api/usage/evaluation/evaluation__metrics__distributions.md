# Evaluation · `metrics.distributions`

This page contains 2 public callable records owned by `evaluation.metrics.distributions`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `DistributionMetrics`

**Kind:** class · **Status:** stable · **Owner:** `evaluation.metrics.distributions`

**Purpose:** One distribution summary of a sequence of observations.

**Exact API:** {py:obj}`evaluation.metrics.distributions.DistributionMetrics` · **Source:** [evaluation/metrics/distributions.py:31](../../../../evaluation/metrics/distributions.py#L31)

**Observed usage:**

1. [production caller: `compute_distribution_metrics`](../../../../evaluation/metrics/distributions.py#L72)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    dropped = int(np.isnan(raw).sum() + np.isinf(raw).sum())
    clean = raw[np.isfinite(raw)]

    if clean.size == 0:
        nan = float("nan")
        return DistributionMetrics(
            count=0,
            mean=nan,
            median=nan,
            std=nan,
            min_value=nan,
            max_value=nan,
            p01=nan,
            p05=nan,
            p25=nan,
            p75=nan,
            p95=nan,
            p99=nan,
            skewness=nan,
            kurtosis=nan,
            var_05=nan,
            cvar_05=nan,
            dropped=dropped,
        )

    mean = float(clean.mean())
    std = float(clean.std(ddof=1) if clean.size > 1 else 0.0)
    p01, p05, p25, p75, p95, p99 = (float(q) for q in np.quantile(clean, _QUANTILES))
    median = float(np.median(clean))
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `compute_distribution_metrics`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.metrics.distributions`

**Purpose:** Summarise a sequence of observations with distribution statistics.

**Exact API:** {py:obj}`evaluation.metrics.distributions.compute_distribution_metrics` · **Source:** [evaluation/metrics/distributions.py:56](../../../../evaluation/metrics/distributions.py#L56)

**Inputs and outputs:**

- **Args:**

  ```text
  values: Observations (per-trade PnL, holding time, sweep delay).
  ```

- **Returns:**

  ```text
  A frozen :class:`DistributionMetrics`; empty or all-non-finite input
  yields ``count=0`` and NaN numeric fields.
  ```

**Observed usage:**

1. [test fixture: `test_empty_input_yields_nan_fields`](../../../../tests/unit/evaluation/test_distribution_metrics.py#L19)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_empty_input_yields_nan_fields(self) -> None:
    # Act
    metrics = compute_distribution_metrics([])

    # Assert
    assert metrics.count == 0
    assert math.isnan(metrics.mean)
    assert math.isnan(metrics.min_value)
    assert math.isnan(metrics.var_05)
```

2. [test fixture: `test_single_observation`](../../../../tests/unit/evaluation/test_distribution_metrics.py#L29)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_single_observation(self) -> None:
    # Act
    metrics = compute_distribution_metrics([10.0])

    # Assert
    assert metrics.count == 1
    assert metrics.mean == pytest.approx(10.0)
    assert metrics.median == pytest.approx(10.0)
    assert metrics.min_value == pytest.approx(10.0)
    assert metrics.max_value == pytest.approx(10.0)
    assert metrics.std == 0.0
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`
