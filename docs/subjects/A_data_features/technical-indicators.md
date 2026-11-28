# Technical indicators

**Status:** Wave A draft
**Use this when:** You need to understand the current causal indicator
functions, their output columns, warm-up behavior, or session-activity inputs.

## Summary and use this when

The technical indicator module implements rolling and exponentially smoothed
features with pandas and NumPy. Indicators are trailing calculations: values
at a row use that row and preceding rows. Their presence in the input matrix
does not imply that a strategy has predictive value.

- Use this guide to inspect a feature family before changing its periods.
- Use the causality guide for higher-timeframe visibility and normalization.
- Use the feature catalog for the configured full output matrix.

## Key terms

- [Warm-up](../../glossary.md)
- [Prefix invariance](../../glossary.md)
- [Session VWAP](../../glossary.md)

## Explanation

### The rule

`features/technical/indicators.py` provides EMA, RSI, MACD, ATR, ADX, Bollinger
features, stochastic values, volume-spike ratios, VWAP, returns, and realized
volatility. Functions return pandas objects aligned to their input index.
`ema_features` emits the EMA, one-bar slope, and relative distance for every
configured span.

### Why it works this way

Keeping transformations in one module makes their row-wise time direction and
output naming inspectable. Pure pandas/NumPy implementations avoid a separate
indicator library dependency. Feature configuration decides which families
enter the model matrix; this catalog does not imply every function is enabled
by default.

The `vwap_level` implementation uses `activity_series` (tick count) and resets
the cumulative numerator and denominator by `session_id`. It does not treat
CFD `<VOL>` as exchange volume. Zero activity is unavailable for the ratio.

### Failure modes

- A rolling indicator has an initial warm-up region; filling it with future
  values violates the time boundary.
- A zero denominator can produce an undefined value. Inspect the documented
  `NaN` behavior rather than assuming a zero signal.
- A VWAP without `session_id` or usable activity raises `ValueError`.
- Changing smoothing, period, or warm-up behavior changes generated features
  and therefore requires cache invalidation.

## Worked example

The Tier A notebook calculates EMA, RSI, MACD, and ATR on a fixed synthetic
OHLC sequence and checks prefix invariance. The values illustrate code output;
they are not a selected trading signal.

```{toctree}
:hidden:

examples/technical-indicators
```

See the [contract reference](../../reference/subjects/technical-indicators.md) for a compact input and output summary.

## Tasks

- Document a feature's config and cache-identity effects.
- Check all consumers through the [feature catalog](../../reference/feature_catalog.md).
- Use [cache identity](cache-identity.md) when changing calculation semantics.

## Contract

| Function | Inputs | Output |
|---|---|---|
| `ema` | Series, positive span | Aligned exponentially weighted Series |
| `rsi` | Close Series, period | Aligned RSI Series |
| `macd` | Close Series, fast/slow/signal spans | MACD line, signal, histogram |
| `atr` | OHLC frame, period | Named `atr` Series |
| `adx` | OHLC frame, period | ADX, plus DI, minus DI columns |
| `bollinger` | Close Series, period and multiplier | Percent-B, normalized width, midpoint |
| `stochastic` | OHLC frame, K and D periods | K and D columns |
| `vwap_level` | OHLC, `session_id`, activity count | Session-reset tick-count VWAP |

Exact default periods and selected families are in `config/base/default.yaml`
and `docs/reference/feature_catalog.md`. The implementation owns behavior.

## Verify

- `tests/unit/features/test_feature_cache_and_fit_scope.py` exercises feature
  construction and fit scope.
- `tests/unit/features/test_htf_alignment.py` checks indicator timing after
  timeframe alignment.
- The notebook checks deterministic outputs and prefix invariance on a small
  fixture.
- Research evidence: no indicator performance claim is made by this page.

Independent QA: [five source-claim checks](../qa/technical-indicators.md).

## Limits and common mistakes

- Causality means no future rows are read; it does not mean the indicator is a
  useful predictor.
- A stable indicator implementation still depends on correct source bars and
  timestamps.
- Session VWAP is tick-count weighted and is not a volume-weighted exchange
  benchmark.
- Treat NaNs and warm-up length consistently across training, evaluation, and
  live inference.

## Change checklist

Before changing an indicator, inspect its input columns, index behavior, warm-up
rules, smoothing convention, and consumers in the configured feature matrix.
Keep numerical behavior explicit so that a function name alone does not hide a
changed feature contract.

- Test output index and length for short inputs, ordinary inputs, and a series
  that contains missing values.
- Check early rows and zero-denominator cases; preserve documented NaN or
  fallback behavior instead of filling from later rows.
- Use only current and prior observations, then verify prefix invariance for
  the changed calculation.
- For session VWAP, supply the required session identifier and activity count;
  do not substitute CFD tick volume for exchange-traded volume.
- Confirm whether an indicator is enabled by the canonical feature config
  before describing it as a model input.
- Update cache identity when a period, smoothing rule, column name, or warm-up
  contract changes.
- Inspect downstream normalization and schema consumers when output columns
  are added, removed, or renamed.

Indicator correctness is a software contract. Predictive value requires a
separate, properly controlled research result.

## Review procedure

For a changed indicator, compare a few hand-computable rows with the returned
Series, including the first row where a value is expected and the initial warm-
up region. Append later observations and compare the earlier output prefix.
Check the exact columns consumed by the feature builder and verify the canonical
configuration enables them before describing them as model inputs. If the
calculation uses session activity, test a session reset and zero-activity row.
These checks explain the numerical contract; a separate experiment is required
to evaluate any trading use of the resulting feature.

## Maintainer note

- Verified commit: `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`
- Verified date: 2026-11-15
- Owner: `data_scientist_engineer`
