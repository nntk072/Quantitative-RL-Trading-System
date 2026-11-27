# Evaluation · `metrics.calibration`

This page contains 4 public callable records owned by `evaluation.metrics.calibration`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `CalibrationReport`

**Kind:** class · **Status:** stable · **Owner:** `evaluation.metrics.calibration`

**Purpose:** Binned reliability data + summary scores.

**Exact API:** {py:obj}`evaluation.metrics.calibration.CalibrationReport` · **Source:** [evaluation/metrics/calibration.py:22](../../../../evaluation/metrics/calibration.py#L22)

**Observed usage:**

1. [production caller: `calibration_report`](../../../../evaluation/metrics/calibration.py#L63)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
    p = np.asarray(predicted_probs, dtype=np.float64).ravel()
    y = np.asarray(outcomes, dtype=np.float64).ravel()
    if p.size != y.size:
        raise ValueError("predicted_probs and outcomes must have the same length")
    if p.size == 0:
        return CalibrationReport(
            np.array([], dtype=np.float64),
            np.array([], dtype=np.float64),
            np.array([], dtype=np.int64),
            float("nan"),
            float("nan"),
        )

    p = np.clip(p, 0.0, 1.0)  # type: ignore[assignment]
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    bin_ids = np.digitize(p, edges[1:-1], right=False)

# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `calibration_report`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.metrics.calibration`

**Purpose:** Bin predictions into ``n_bins`` equal-width bins over [0, 1].

**Exact API:** {py:obj}`evaluation.metrics.calibration.calibration_report` · **Source:** [evaluation/metrics/calibration.py:43](../../../../evaluation/metrics/calibration.py#L43)

**Inputs and outputs:**

- **Args:**

  ```text
  predicted_probs: Policy-implied probability of a winning trade, in [0, 1].
  outcomes: 1.0 for winning trades, 0.0 for losers (same order as predictions).
  n_bins: Number of equal-width bins. Bins with zero samples are dropped.
  ```

- **Returns:**

  ```text
  Result of bin predictions into ``n_bins`` equal-width bins over [0, 1].
  ```

**Observed usage:**

1. [test fixture: `test_calibration_report_clips_probabilities_and_omits_empty_bins`](../../../../tests/unit/evaluation/test_calibration.py#L19)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_calibration_report_clips_probabilities_and_omits_empty_bins() -> None:
    report = calibration_report(np.asarray([-0.2, 1.2]), np.asarray([0.0, 1.0]), n_bins=4)

    np.testing.assert_allclose(report.bin_centers, [0.0, 1.0])
    np.testing.assert_allclose(report.bin_win_rates, [0.0, 1.0])
    np.testing.assert_array_equal(report.bin_counts, [1, 1])
    assert report.ece == 0.0
    assert report.brier == 0.0
    assert "bins=2  n=2" in report.summary()
```

2. [test fixture: `test_empty_calibration_report_and_reliability_plot_are_supported`](../../../../tests/unit/evaluation/test_calibration.py#L30)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_empty_calibration_report_and_reliability_plot_are_supported() -> None:
    empty = calibration_report(np.asarray([]), np.asarray([]))
    assert empty.bin_counts.size == 0
    assert np.isnan(empty.ece)
    assert np.isnan(empty.brier)

    fig, ax = plt.subplots()
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `plot_reliability_diagram`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.metrics.calibration`

**Purpose:** Draw the reliability diagram; returns the matplotlib Axes.

**Exact API:** {py:obj}`evaluation.metrics.calibration.plot_reliability_diagram` · **Source:** [evaluation/metrics/calibration.py:97](../../../../evaluation/metrics/calibration.py#L97)

**Inputs and outputs:**

- **Args:**

  ```text
  report: Report used by the operation described above.
  ax: Ax used by the operation described above.
  ```

- **Returns:**

  ```text
  Result of draw the reliability diagram; returns the matplotlib Axes.
  ```

**Observed usage:**

1. [test fixture: `test_empty_calibration_report_and_reliability_plot_are_supported`](../../../../tests/unit/evaluation/test_calibration.py#L36)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    assert empty.bin_counts.size == 0
    assert np.isnan(empty.ece)
    assert np.isnan(empty.brier)

    fig, ax = plt.subplots()
    returned = plot_reliability_diagram(empty, ax)
    assert returned is ax
    assert len(ax.patches) == 0
    plt.close(fig)

    created = plot_reliability_diagram(empty)
# … caller assertions omitted …
```

2. [production caller: `write_calibration_artifacts`](../../../../evaluation/reporting/diagnostics.py#L130)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    split_dir = Path(split_dir)
    write_text_atomic(split_dir / "calibration.json", json.dumps(payload, indent=2))

    if save_plots:
        fig, ax = plt.subplots(figsize=(5, 5))
        plot_reliability_diagram(report, ax=ax)
        _save(fig, split_dir / "reliability.png", dpi)

    return payload
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `CalibrationReport.summary`

**Kind:** method · **Status:** stable · **Owner:** `evaluation.metrics.calibration`

**Purpose:** Return a compact, human-readable calibration summary.

**Exact API:** {py:obj}`evaluation.metrics.calibration.CalibrationReport.summary` · **Source:** [evaluation/metrics/calibration.py:31](../../../../evaluation/metrics/calibration.py#L31)

**Inputs and outputs:**

- **Returns:**

  ```text
  Text returned by ``summary``.
  ```

**Observed usage:**

1. [test fixture: `test_calibration_report_clips_probabilities_and_omits_empty_bins`](../../../../tests/unit/evaluation/test_calibration.py#L26)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_calibration_report_clips_probabilities_and_omits_empty_bins() -> None:
    report = calibration_report(np.asarray([-0.2, 1.2]), np.asarray([0.0, 1.0]), n_bins=4)

    np.testing.assert_allclose(report.bin_centers, [0.0, 1.0])
    np.testing.assert_allclose(report.bin_win_rates, [0.0, 1.0])
    np.testing.assert_array_equal(report.bin_counts, [1, 1])
    assert report.ece == 0.0
    assert report.brier == 0.0
    assert "bins=2  n=2" in report.summary()
```

2. [production caller: `plot_reliability_diagram`](../../../../evaluation/metrics/calibration.py#L127)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            edgecolor="k",
            label="observed win rate",
        )
    ax.set_xlabel("Predicted probability of win")
    ax.set_ylabel("Observed win rate")
    ax.set_title(report.summary())
    ax.legend(loc="upper left", fontsize=8)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    plt.tight_layout()
    return ax
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`
