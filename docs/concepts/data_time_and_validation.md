# Market time, resampling, and validation

## Timestamp meaning

A timestamp needs a declared clock, timezone, and convention: does it label a
bar's opening time, closing time, or source event? Daylight-saving changes and
market-session calendars make naive local timestamps ambiguous. The loader and
session schedule are configured through the data/session settings; cache
identity includes time and session fields because changing them changes
features.

Before joining feeds, verify monotonicity, duplicates, timezone conversion,
missing intervals, and whether timestamps denote completed bars. Never infer
clock semantics from a filename alone. See [data ingestion](../how-to/prepare_market_data.md)
and the [configuration reference](../reference/configuration.md).

## Resampling

Resampling aggregates lower-timeframe OHLCV into a higher-timeframe candle.
The resulting candle is not available until its source interval has completed.
For a right-labeled five-minute bar, exposing its final high/low at an earlier
minute would leak future information. Repository alignment uses forward-fill
from completed higher-timeframe observations; backward fill is invalid for
causal inputs.

## Splits and walk-forward folds

The canonical `purged_walk_forward` creates expanding training prefixes and
contiguous, non-overlapping test blocks at the end of the series. The combined
test budget is split across folds. Before each test block it removes the
configured embargo and purges `purge_bars + max(0, label_horizon)` from the
training end. A deprecated legacy splitter has overlapping test folds and
must not be used for new work.

Purging reduces overlap from lookback/label dependencies; it does not cure
every form of adaptive selection. Keep a final locked holdout out of
architecture selection and describe the exact fold/time ranges. See the
[validation protocol](../research/validation_protocol.md) and implementation
[`market_data/splits/walkforward.py`](../../market_data/splits/walkforward.py).

## Normalization and cache identity

When using frozen-fold fit semantics, fit statistics on the training mask and
apply the last known training statistics outside that fit region. The
repository also retains a legacy masked-window normalization mode for
historical compatibility; report which mode was used. Feature caches include
a version and content hash over relevant config, timestamps, bar columns,
secondary instrument inputs, masks, and timeframe bars. A hand-edited version
string without matching data identity is not a reproducibility argument.

See [feature causality](causality.md),
[cache how-to](../how-to/build_feature_cache.md), and
[cache/schema reference](../reference/cache_and_schema_versions.md).
