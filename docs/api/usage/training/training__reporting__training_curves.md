# Training · `reporting.training_curves`

This page contains 2 public callable records owned by `training.reporting.training_curves`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `save_dashboard_plots`

**Kind:** function · **Status:** stable · **Owner:** `training.reporting.training_curves`

**Purpose:** Chart the dashboard CSV written during ``learn()``.

**Exact API:** {py:obj}`training.reporting.training_curves.save_dashboard_plots` · **Source:** [training/reporting/training_curves.py:738](../../../../training/reporting/training_curves.py#L738)

**Inputs and outputs:**

- **Args:**

  ```text
  log_path: Path or filename identifying the log.
  out_dir: Out dir used by the operation described above.
  dpi: Resolution of generated plots, in dots per inch.
  save_html: Whether to enable or require the save html.
  ```

**Observed usage:**

1. [test fixture: `test_save_dashboard_plots`](../../../../tests/unit/training/test_training_curves.py#L153)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            "n_trades": [10, 20],
            "turnover": [0.3, 0.4],
        }
    ).to_csv(log_path, index=False)
    out = tmp_path / "plots"
    save_dashboard_plots(log_path, out_dir=out, save_html=False)
    for name in (
        "dashboard_return",
        "dashboard_pnl",
        "dashboard_sharpe",
        "dashboard_profit_factor",
# … caller assertions omitted …
```

2. [production caller: `evaluate_test_split`](../../../../training/runner/seed_runtime.py#L674)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
                    seed_model_dir,
                    dpi=getattr(cfg.output, "dpi", 150),
                )
                if trade_setup_plots:
                    log.info("Saved trade-setup learning plots: %s", trade_setup_plots)
            save_dashboard_plots(
                seed_model_dir / "dashboard_log.csv",
                out_dir=seed_model_dir,
                dpi=getattr(cfg.output, "dpi", 150),
                save_html=getattr(cfg.output, "save_html", False),
            )
        except Exception as exc:
            log.warning("Training progress plots skipped: %s", exc)

            # Final train/test replays use the configured policy action mode. Stochastic
            # evaluations are reseeded so their sampled trajectories can be reproduced.
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/training/index`

## `save_training_plots`

**Kind:** function · **Status:** stable · **Owner:** `training.reporting.training_curves`

**Purpose:** Generate all training-progress charts from *log_path* CSV into *out_dir*.

**Exact API:** {py:obj}`training.reporting.training_curves.save_training_plots` · **Source:** [training/reporting/training_curves.py:515](../../../../training/reporting/training_curves.py#L515)

**Inputs and outputs:**

- **Args:**

  ```text
  log_path: Path or filename identifying the log.
  out_dir: Out dir used by the operation described above.
  dpi: Resolution of generated plots, in dots per inch.
  save_html: Whether to enable or require the save html.
  ```

**Observed usage:**

1. [test fixture: `test_save_training_plots`](../../../../tests/unit/training/test_training_curves.py#L93)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        }
    )
    log_path = tmp_path / "training_log.csv"
    df.to_csv(log_path, index=False)

    save_training_plots(log_path, out_dir=tmp_path, save_html=False)

    for name in ["learning_curve", "losses", "entropy_explvar", "kl_clip", "lr"]:
        assert (tmp_path / f"{name}.png").stat().st_size > 0, f"Missing {name}.png"
```

2. [test fixture: `test_save_training_plots_empty_log`](../../../../tests/unit/training/test_training_curves.py#L121)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_save_training_plots_empty_log(tmp_path):
    missing = tmp_path / "nonexistent.csv"
    save_training_plots(missing, out_dir=tmp_path, save_html=False)
    # Should not raise, should create no files
    assert not any(tmp_path.glob("*.png"))
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/training/index`
