# Experiments · `research.statistics`

This page contains 6 public callable records owned by `experiments.research.statistics`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `PairedStatistics`

**Kind:** class · **Status:** experimental · **Owner:** `experiments.research.statistics`

**Purpose:** Prospectively registered paired-seed inference result.

**Exact API:** {py:obj}`experiments.research.statistics.PairedStatistics` · **Source:** [experiments/research/statistics.py:14](../../../../experiments/research/statistics.py#L14)

**Observed usage:**

1. [production caller: `analyze_paired_seeds`](../../../../experiments/research/statistics.py#L138)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def analyze_paired_seeds(
    treatment: Iterable[float],
    control: Iterable[float],
    *,
    bootstrap_samples: int = 10_000,
    rng_seed: int = 42,
) -> PairedStatistics:
    differences = paired_differences(treatment, control)
    p_value = exact_sign_flip_greater(differences)
    lower, upper = paired_bootstrap_interval(
        differences,
        samples=bootstrap_samples,
        seed=rng_seed,
    )
    return PairedStatistics(
        mean_difference=float(np.mean(differences)),
        sign_flip_p_value=p_value,
        bootstrap_lower=lower,
        bootstrap_upper=upper,
        pair_count=int(differences.size),
    )
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`

## `PairedStatistics.positive`

**Kind:** method · **Status:** experimental · **Owner:** `experiments.research.statistics`

**Purpose:** Return whether all registered superiority criteria are satisfied.

**Exact API:** {py:obj}`experiments.research.statistics.PairedStatistics.positive` · **Source:** [experiments/research/statistics.py:24](../../../../experiments/research/statistics.py#L24)

**Inputs and outputs:**

- **Returns:**

  ```text
  Result produced by positive.
  ```

**Observed usage:**

1. [production caller: `analyze_primary_payload`](../../../../experiments/research/primary_comparison.py#L180)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    all_safe = all(
        pair["treatment"]["hard_risk_gate_passed"] is True
        and pair["control"]["hard_risk_gate_passed"] is True
        for pair in pairs
    )
    positive = all_safe and statistics.positive
    return {
        "schema_version": 1,
        "status": "positive" if positive else "negative_or_inconclusive",
        "pair_count": statistics.pair_count,
        "mean_difference_pct": statistics.mean_difference,
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`

## `analyze_paired_seeds`

**Kind:** function · **Status:** experimental · **Owner:** `experiments.research.statistics`

**Purpose:** Compute the registered paired statistics for up to fifteen seeds.

**Exact API:** {py:obj}`experiments.research.statistics.analyze_paired_seeds` · **Source:** [experiments/research/statistics.py:113](../../../../experiments/research/statistics.py#L113)

**Inputs and outputs:**

- **Args:**

  ```text
  treatment: Treatment values paired by independent seed.
  control: Control values paired by independent seed.
  bootstrap_samples: Number of paired bootstrap resamples.
  rng_seed: Random seed used by the statistical procedure.
  ```

- **Returns:**

  ```text
  Result produced by analyze_paired_seeds.
  ```

**Observed usage:**

1. [production caller: `analyze_primary_payload`](../../../../experiments/research/primary_comparison.py#L174)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    ]
    control = [
        _finite(pair["control"]["net_return_initial_equity_pct"], "control return")
        for pair in pairs
    ]
    statistics = analyze_paired_seeds(treatment, control)
    all_safe = all(
        pair["treatment"]["hard_risk_gate_passed"] is True
        and pair["control"]["hard_risk_gate_passed"] is True
        for pair in pairs
    )
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`

## `exact_sign_flip_greater`

**Kind:** function · **Status:** experimental · **Owner:** `experiments.research.statistics`

**Purpose:** Return the exact one-sided paired sign-flip p-value.

**Exact API:** {py:obj}`experiments.research.statistics.exact_sign_flip_greater` · **Source:** [experiments/research/statistics.py:58](../../../../experiments/research/statistics.py#L58)

**Inputs and outputs:**

- **Args:**

  ```text
  differences: Paired treatment-minus-control differences.
  max_pairs: Largest pair count allowed for exact enumeration.
  ```

- **Returns:**

  ```text
  Result produced by exact_sign_flip_greater.
  ```

**Observed usage:**

1. [production caller: `analyze_paired_seeds`](../../../../experiments/research/statistics.py#L132)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def analyze_paired_seeds(
    treatment: Iterable[float],
    control: Iterable[float],
    *,
    bootstrap_samples: int = 10_000,
    rng_seed: int = 42,
) -> PairedStatistics:
    differences = paired_differences(treatment, control)
    p_value = exact_sign_flip_greater(differences)
    lower, upper = paired_bootstrap_interval(
        differences,
        samples=bootstrap_samples,
        seed=rng_seed,
    )
    return PairedStatistics(
        mean_difference=float(np.mean(differences)),
        sign_flip_p_value=p_value,
        bootstrap_lower=lower,
        bootstrap_upper=upper,
        pair_count=int(differences.size),
    )
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`

## `paired_bootstrap_interval`

**Kind:** function · **Status:** experimental · **Owner:** `experiments.research.statistics`

**Purpose:** Return the registered percentile interval for the paired-seed mean.

**Exact API:** {py:obj}`experiments.research.statistics.paired_bootstrap_interval` · **Source:** [experiments/research/statistics.py:86](../../../../experiments/research/statistics.py#L86)

**Inputs and outputs:**

- **Args:**

  ```text
  differences: Paired treatment-minus-control differences.
  samples: Number of bootstrap resamples.
  seed: Random seed used for deterministic sampling.
  ```

- **Returns:**

  ```text
  Result produced by paired_bootstrap_interval.
  ```

**Observed usage:**

1. [production caller: `analyze_paired_seeds`](../../../../experiments/research/statistics.py#L133)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def analyze_paired_seeds(
    treatment: Iterable[float],
    control: Iterable[float],
    *,
    bootstrap_samples: int = 10_000,
    rng_seed: int = 42,
) -> PairedStatistics:
    differences = paired_differences(treatment, control)
    p_value = exact_sign_flip_greater(differences)
    lower, upper = paired_bootstrap_interval(
        differences,
        samples=bootstrap_samples,
        seed=rng_seed,
    )
    return PairedStatistics(
        mean_difference=float(np.mean(differences)),
        sign_flip_p_value=p_value,
        bootstrap_lower=lower,
        bootstrap_upper=upper,
        pair_count=int(differences.size),
    )
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`

## `paired_differences`

**Kind:** function · **Status:** experimental · **Owner:** `experiments.research.statistics`

**Purpose:** Return finite treatment-minus-control differences with equal cardinality.

**Exact API:** {py:obj}`experiments.research.statistics.paired_differences` · **Source:** [experiments/research/statistics.py:37](../../../../experiments/research/statistics.py#L37)

**Inputs and outputs:**

- **Args:**

  ```text
  treatment: Treatment values paired by independent seed.
  control: Control values paired by independent seed.
  ```

- **Returns:**

  ```text
  Result produced by paired_differences.
  ```

**Observed usage:**

1. [production caller: `analyze_paired_seeds`](../../../../experiments/research/statistics.py#L131)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def analyze_paired_seeds(
    treatment: Iterable[float],
    control: Iterable[float],
    *,
    bootstrap_samples: int = 10_000,
    rng_seed: int = 42,
) -> PairedStatistics:
    differences = paired_differences(treatment, control)
    p_value = exact_sign_flip_greater(differences)
    lower, upper = paired_bootstrap_interval(
        differences,
        samples=bootstrap_samples,
        seed=rng_seed,
    )
    return PairedStatistics(
        mean_difference=float(np.mean(differences)),
        sign_flip_p_value=p_value,
        bootstrap_lower=lower,
        bootstrap_upper=upper,
        pair_count=int(differences.size),
    )
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`
