# Evaluation · `reporting.run_artifact_writer`

This page contains 1 public callable records owned by `evaluation.reporting.run_artifact_writer`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `save_run`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.reporting.run_artifact_writer`

**Purpose:** Persist a complete train + test run.

**Exact API:** {py:obj}`evaluation.reporting.run_artifact_writer.save_run` · **Source:** [evaluation/reporting/run_artifact_writer.py:848](../../../../evaluation/reporting/run_artifact_writer.py#L848)

**Inputs and outputs:**

- **Args:**

  ```text
  out_dir: Base directory for generated run artifacts.
  name: Run label used when a timestamped directory is created.
  run_dir: Explicit pre-created directory (overrides *out_dir* / *name* if set).
      Useful when the caller has already written model weights into the same
      directory (e.g. ``train_rl.py``).
  train_result: In-sample backtest result mapping, if available.
  train_metrics: In-sample performance metrics, if available.
  train_bars: In-sample primary market bars.
  train_secondary: Optional in-sample correlated-symbol bars for SMT overlays.
  train_features: Optional in-sample feature frame for chart overlays.
  test_result: Out-of-sample backtest result mapping, if available.
  test_metrics: Out-of-sample performance metrics, if available.
  test_bars: Out-of-sample primary market bars.
  test_secondary: Optional out-of-sample correlated-symbol bars.
  test_features: Optional out-of-sample feature frame for chart overlays.
  cfg: Optional resolved configuration saved with the run.
  save_plots: Whether to write static evaluation plots.
  save_html: Whether to write interactive per-trade charts.
  save_csv: Whether to write machine-readable trade and equity tables.
  dpi: Resolution used for static plots.
  max_order_charts: Maximum number of per-trade static charts to generate.
  report_profile: Artifact profile controlling full or deferred chart output.
  ```

- **Returns:**

  ```text
  Path to the directory containing the saved run artifacts.
  ```

**Observed usage:**

1. [test fixture: `test_model_choice_probabilities_survive_rollout_and_artifact_export`](../../../../tests/integration/evaluation/test_random_eligible_setup_rollout.py#L266)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        features,
        env=env,
        strategy_actions=True,
        trade_setup_actions=True,
    )
    run_dir = save_run(
        run_dir=tmp_path / "model-choice-trace",
        train_result=result,
        train_metrics=calculate_metrics(
            result["equity"],
            trades=result["trades"],
            initial_balance=100_000.0,
        ),
        train_bars=bars,
        save_plots=False,
        save_html=False,
        save_csv=True,
        report_profile="experiment_run_fast",
    )

    saved = pd.read_csv(run_dir / "training" / "trade_setup_decisions.csv")
    assert len(saved) == 1
    saved_candidate_id = saved["trade_setup_candidate_id"].to_numpy(dtype=np.int64)[0]
    assert int(saved_candidate_id) == candidate_id
# … caller assertions omitted …
```

2. [test fixture: `test_save_run_creates_files`](../../../../tests/unit/evaluation/test_plots_export.py#L690)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_save_run_creates_files(synthetic_result, metrics, tmp_path):
    run_dir = save_run(
        out_dir=tmp_path,
        name="test_run",
        train_result=synthetic_result,
        train_metrics=metrics,
        test_result=synthetic_result,
        test_metrics=metrics,
        save_plots=True,
        save_html=True,
        save_csv=True,
        dpi=72,
    )
    assert run_dir.exists()
    # Root: only config/summary — no raw data or charts
    assert (run_dir / "summary.txt").stat().st_size > 0
    evaluation_manifest = json.loads((run_dir / "evaluation_manifest.json").read_text())
    assert evaluation_manifest["schema_version"] == "evaluation-artifacts-v1"
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`
