# Splits and walk-forward

**Status:** Wave A draft
**Use this when:** You need a chronological train/evaluation partition or a
fold-local feature build that cannot use later rows to fit state.

## Summary and use this when

Walk-forward evaluation tests a sequence of later time blocks after training
on earlier rows. Purge and embargo create a gap around each test block so
labels or transition horizons do not leak across the boundary. The default
splitter emits non-overlapping test folds.

- Use it when comparing models across chronological test windows.
- Use fold-local fitting when normalization state must be refit per training
  fold.
- Use [result identity and evidence lineage](../../research/result_identity_and_evidence.md)
  for reproducible run provenance.

## Key terms

- [Walk-forward](../../glossary.md)
- [Purge / embargo](../../glossary.md)
- [OOS](../../glossary.md)

## Explanation

### The rule

`market_data/splits/walkforward.py::purged_walk_forward` allocates the total
test budget across contiguous blocks at the end of the series. Each fold trains
on indices before its test start, then subtracts `embargo_bars` and the
effective purge from the train end. The effective purge includes
`label_horizon`.

The default arguments are five splits, a 20% total test budget, 60 purge bars,
and 20 embargo bars. These defaults are source settings, not a universal
recommendation for every label or timeframe.

### Why it works this way

Random shuffling destroys the order that determines whether a value was
available at decision time. Expanding chronological training and disjoint test
blocks make the temporal direction explicit. The purge horizon must cover the
labels and any other overlapping outcome window.

`features/pipeline/walkforward_feature_fitting.py::build_walkforward_fold_features`
keeps indicator context through the validation end but fits using only the
fold's training index. Validation rows are transformed with the fitted state;
they do not define it.

### Failure modes

- A purge shorter than the label horizon allows train labels to cross into test.
- Overlapping test windows cause the same outcomes to be counted more than once.
- Fitting normalization on the full dataset leaks validation statistics.
- A fold too small for its gaps can yield no usable split; check the returned
  folds instead of assuming the requested count was produced.

## Worked example

The [walk-forward notebook](../../learn/tutorials/06_walk_forward_validation.ipynb)
shows chronological partitions and the required gaps on a deterministic
example. It is a procedure demonstration, not a performance result.

```{toctree}
:hidden:

examples/splits-and-walk-forward
```

See the [contract reference](../../reference/subjects/splits-and-walk-forward.md) for a compact input and output summary.

## Tasks

- [Configure data partitions](../../how-to/configuration_recipes.md) and inspect
  the resolved configuration.
- [Run a configured experiment](../../how-to/run_experiment.md) with the
  intended evaluation windows.
- For feature fitting inside each fold, see `build_walkforward_fold_features`
  in `features/pipeline/walkforward_feature_fitting.py`.

## Contract

| Item | Contract | Source |
|---|---|---|
| Input | Positive row count and chronological index | `market_data/splits/walkforward.py` |
| Test blocks | Contiguous and non-overlapping | `purged_walk_forward` |
| Train end | `test_start - embargo - purge - label horizon` | `purged_walk_forward` |
| Fold feature context | Bars through validation end for causal warm-up | `features/pipeline/walkforward_feature_fitting.py` |
| Fit rows | Current fold training rows only | `features/pipeline/normalization.py` |
| Validation use | Apply fitted state; do not refit on validation data | `features/pipeline/normalization.py` |

## Verify

- `tests/unit/market_data/test_walkforward.py` checks expected boundaries,
  non-overlap, and horizon-aware purge.
- `tests/unit/market_data/test_walkforward_properties.py` exercises fold
  properties across generated settings.
- `tests/unit/features/test_train_walkforward_contract.py` checks that
  fold-local feature fitting stays inside train indices.
- Research evidence: this explanation makes no claim that any fold establishes
  generalization beyond its recorded data period.

Independent QA: [five source-claim checks](../qa/splits-and-walk-forward.md).

## Limits and common mistakes

- Split fractions and purge lengths are design choices that must follow the
  label and transition horizons.
- A fold result is not independent if test blocks overlap.
- The locked report interval remains unavailable for model selection; see the
  [validation protocol](../../research/validation_protocol.md).
- `purged_walk_forward_legacy` is deprecated and explicitly emits overlapping
  test blocks. Do not use it for new evaluations.

## Change checklist

Before altering a split, state the label horizon, feature lookback, total test
budget, and embargo needed by the target evaluation. The default values are
implementation defaults; they are not automatically suitable for every task.

- Inspect actual returned folds because short inputs can yield fewer than the
  requested number of splits or no usable split.
- Confirm each train index ends before its test after both purge and embargo.
- Confirm test indices are contiguous and do not overlap across folds.
- Include the full outcome horizon in purge when labels consume future bars.
- Build rolling context through the validation end only when the transformation
  is causal, and pass the training indices as the fit mask.
- Recompute fold-local normalization state for each training fold; never fit it
  using that fold's validation rows.
- Keep the locked reporting interval out of threshold or checkpoint selection.

A passing split property test verifies temporal mechanics for its generated
cases. It does not establish that the selected windows represent future markets.

## Review procedure

For a proposed split configuration, write down the exact test start and end
indices and calculate the train cutoff from embargo, feature purge, and label
horizon. Compare that arithmetic with the returned arrays. Include a small input
that cannot fit the requested number of folds and verify that the caller handles
an empty or shorter result explicitly. Finally, confirm the evaluation runner
uses the same fold boundaries recorded in its manifest. Synthetic index checks
validate boundary arithmetic; only recorded experiment artifacts support
research conclusions.

## Maintainer note

- Verified commit: `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`
- Verified date: 2026-11-15
- Owner: `data_scientist_engineer`
