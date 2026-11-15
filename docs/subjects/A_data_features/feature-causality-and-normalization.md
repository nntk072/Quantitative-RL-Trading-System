# Feature causality and normalization

**Status:** Wave A draft
**Use this when:** You need to decide which bar values are available to a
feature row or how fitted normalization state is carried into validation.

## Summary and use this when

Feature construction must preserve the information boundary at each decision
timestamp. Higher-timeframe values become available at their close. Normalizer
statistics are fitted only on allowed training rows and then applied to later
rows without refitting.

- Use this guide when adding a feature or aligning a higher timeframe.
- Use the split guide for the train/test partition that defines the fit mask.
- Use the cache identity guide when changing any feature input or semantics.

## Key terms

- [Availability time](../../glossary.md)
- [Training mask](../../glossary.md)
- [Normalization state](../../glossary.md)

## Explanation

### The rule

`market_data/transforms/align.py::align_timeframes` forward-fills completed
higher-timeframe values onto the M1 index. With default `completed_bars=True`,
it shifts the source series before alignment. Explicit `availability_times`
are used when a shortened or gapped bar has a known close time. Neither path
backfills future values.

`features/pipeline/normalization.py::fit_rolling_zscore_state` validates a
unique, complete Boolean training mask, fits rolling state on training rows,
and serializes the final state available at the last train timestamp.
Validation and live data apply that saved state rather than fitting on their
own observations.

### Why it works this way

An open-stamped H1 candle is not complete at its open. Its final high, low,
close, and indicator values cannot be available to an earlier M1 decision. A
normalizer fit over validation rows also uses distribution information from
the future relative to the training decision.

Indicator warm-up rows may precede a fold's training rows. They supply causal
history but are excluded from fitting by the fold's train mask. This keeps the
feature calculation continuous while restricting fitted state to the fold.

### Failure modes

- Backfill copies a later source candle into earlier decision rows.
- Aligning to the open timestamp makes a final candle value visible early.
- A nullable or misaligned mask changes which rows fit the normalizer.
- Fitting a new scaler on validation or live data changes the trained input
  contract.
- Dropping bars to enforce session eligibility alters rolling context.

## Worked example

The [causal-feature notebook](../../learn/tutorials/02_causal_features.ipynb)
compares a source timeframe with the values made visible on the decision
timeline. Its example uses a bounded fixture and does not claim predictive
value.

```{toctree}
:hidden:

examples/feature-causality-and-normalization
```

See the [contract reference](../../reference/subjects/feature-causality-and-normalization.md) for a compact input and output summary.

## Tasks

- [Add a feature](../../how-to/add_feature.md) and include a prefix-invariance
  check when the transformation uses future-sensitive operations.
- [Build a feature cache](../../how-to/build_feature_cache.md) after the
  feature semantics and identity inputs are defined.
- Choose train and validation rows with the
  [walk-forward guide](splits-and-walk-forward.md).

## Contract

| Item | Contract | Source |
|---|---|---|
| M1 spine | Decision index is the reference timeline | `market_data/transforms/align.py` |
| Higher timeframe | Latest completed value only; forward fill, never backfill | `align_timeframes` |
| Explicit close time | Availability can use per-bar close timestamps | `timeframe_close_times` |
| Fit mask | Unique index, Boolean dtype, full coverage, nonempty train rows | `features/pipeline/normalization.py` |
| Fit state | Schema, mode, window, columns, as-of time, means and scales | `fit_rolling_zscore_state` |
| Later rows | Apply saved train state without refitting | `apply_rolling_zscore_state` |

## Verify

- `tests/unit/features/test_htf_alignment.py` checks completed-bar timing and
  shortened final bars.
- `tests/unit/features/test_alignment_properties.py` checks causal alignment
  properties over generated time indexes.
- `tests/unit/features/test_feature_cache_and_fit_scope.py` checks train-mask
  fitting and state reuse.
- `tests/research/test_feature_prefix_invariance.py` checks real-market prefix
  invariance for its registered configurations.
- Research evidence: prefix tests verify a software property for their named
  inputs; they do not establish profitable trading behavior.

Independent QA: [five source-claim checks](../qa/feature-causality-and-normalization.md).

## Limits and common mistakes

- Causal availability depends on correct source timestamps and timeframe
  boundaries; an incorrect feed clock cannot be repaired by forward filling.
- Keep warm-up bars in the feature timeline and exclude them from fitting by
  mask when necessary.
- Do not replace the training-only rule with full-series z-scores for
  convenience.
- Inspect output prefixes and mask coverage when changing alignment behavior.

## Change checklist

For every newly derived value, identify its source interval, its availability
time, the decision timestamp that consumes it, and the training rows allowed
to fit any parameters. Keep those choices visible in the feature implementation
and its tests.

- Use a causal merge direction and ensure incomplete higher-timeframe bars are
  unavailable until their close or explicit availability timestamp.
- Test a boundary row, a gap, and a shortened final bar when the source has
  irregular intervals.
- Require a unique, aligned Boolean training mask with at least one fit row.
- Fit means and scales from training rows only; reuse the serialized state on
  validation and later live rows.
- Keep warm-up context available to trailing calculations without allowing it
  into the fitted state unless it is part of training.
- Add future-append or prefix-invariance tests when new code could read beyond
  the current row.
- Update cache identity when availability, normalization mode, or feature
  semantics affect outputs.

These checks establish software causality for the tested boundaries. Incorrect
source clocks and missing upstream observations remain separate data-quality risks.

## Review procedure

Choose a decision timestamp that falls before a higher-timeframe candle closes
and inspect the aligned value at that timestamp and at its close. Repeat for a
gap or shortened bar when those occur in the feed. For normalization, perturb
only validation values and confirm the serialized training state does not
change; then apply the original state and confirm output rows remain aligned.
Keep those checks close to the transformation and split contract so a future
caller cannot bypass them. The example notebook illustrates timing only; the
unit and property tests provide broader software coverage.

## Maintainer note

- Verified commit: `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`
- Verified date: 2026-11-15
- Owner: `data_scientist_engineer`
