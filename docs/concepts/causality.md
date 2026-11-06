# Causality and feature visibility

A feature is causal when the value exposed at decision time uses only data that
was available by that time. This is a timestamp contract, not just an
indicator formula.

## Completed higher-timeframe bars

The M1 spine is the decision-time reference. For open-stamped bars, a higher
timeframe candle becomes visible at its close, not at its open. The canonical
alignment helper shifts a higher-timeframe series before forward-filling it;
when availability timestamps are provided, it aligns the value at those
close times (including shortened scheduled-session bars). Secondary symbols
are joined backward as-of so the selected source timestamp is not later than
the primary timestamp.

```text
M1 decision time t → latest source bar with availability_time ≤ t
```

Never backward-fill market inputs. When a caller has already moved an event to
its actual availability timestamp, it must not accidentally shift that event a
second time; see the `completed_bars` contract in
[`market_data/transforms/align.py`](../../market_data/transforms/align.py).

## Fitting statistics

The `frozen_fold` normalization mode fits rolling statistics on training
observations only, then forward-fills the final available training statistics
through validation. `legacy_masked_window` keeps its historical calendar-row
window for fitting, then carries the last training statistics through held-out
rows. State the mode with the fold/split used.

## Causality audit

For each feature, identify:

1. the raw source columns and source timeframe;
2. the event/candle completion time needed to calculate it;
3. any confirmation or invalidation delay;
4. the alignment and missing-value behavior;
5. the fitting partition for normalization;
6. a prefix test showing that appending future rows does not change past
   feature values.

The repository has prefix-causality tests for assembled and real-market
features. See [data time and validation](data_time_and_validation.md),
[feature catalog](../reference/feature_catalog.md), and
[causality tests](../../tests/unit/features/test_assembled_causality.py).

## Cache identity

The content hash includes the feature-cache version, relevant resolved feature
and session configuration, full time indexes and selected OHLCV/spread fields
for both instruments, train mask, normalization mode when non-legacy, and
timeframe inputs. Cache invalidation therefore depends on content identity as
well as `FEATURE_CACHE_VERSION`.
