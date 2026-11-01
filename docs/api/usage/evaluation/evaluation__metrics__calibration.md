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

1. [production caller: `write_calibration_artifacts`](../../../../evaluation/reporting/diagnostics.py#L115)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    long_wr = float(np.mean(long_out)) if long_out else 0.5
    short_wr = float(np.mean(short_out)) if short_out else 0.5

    preds = np.asarray([long_wr if d == 1 else short_wr for d, _ in records], dtype=np.float64)
    outcomes = np.asarray([y for _, y in records], dtype=np.float64)
    report = calibration_report(preds, outcomes, n_bins=min(10, max(3, len(records) // 5)))

    payload = {
        "ece": report.ece,
        "brier": report.brier,
        "n": int(report.bin_counts.sum()),
# … caller assertions omitted …
```

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

1. [production caller: `write_calibration_artifacts`](../../../../evaluation/reporting/diagnostics.py#L130)

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

1. [production caller: `plot_reliability_diagram`](../../../../evaluation/metrics/calibration.py#L127)

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

2. [production caller: `write_calibration_artifacts`](../../../../evaluation/reporting/diagnostics.py#L123)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        "ece": report.ece,
        "brier": report.brier,
        "n": int(report.bin_counts.sum()),
        "long_win_rate": long_wr,
        "short_win_rate": short_wr,
        "summary": report.summary(),
    }
    split_dir = Path(split_dir)
    write_text_atomic(split_dir / "calibration.json", json.dumps(payload, indent=2))

    if save_plots:
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`
