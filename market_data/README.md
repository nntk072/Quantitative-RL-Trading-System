# Market data

`market_data/` turns raw timestamped market inputs into aligned, chronological
tables for feature construction and simulation. It owns loading, cleaning,
timeframe resampling/alignment, sessions, and split boundaries; it does not
define model features or choose trading actions.

The main stages are:

```text
source files -> load/normalize -> validate time/order -> resample/align
             -> session and split metadata -> feature/cache consumers
```

The package is organized around loading pipelines, transformations, schemas,
and command entry points. Timestamp timezone, completed-candle visibility,
missing-data handling, and split chronology are correctness contracts. A
change to resampling or alignment requires leakage and boundary tests.

## Internal stages

| Stage | Output contract | Main failure to detect |
|---|---|---|
| Loading | Normalized timestamped source tables | Wrong columns, timezone, duplicates, invalid quote fields |
| Transform | Resampled/aligned series with close-time semantics | Incomplete source bar becoming visible too early |
| Session/calendar | Context flags attached to retained timeline | Dropping bars because a session is short or closed |
| Split selection | Ordered training/evaluation views and masks | Period overlap or fitting preprocessing on evaluation rows |
| Cache | Prepared inputs tied to source/config identity | Reusing stale data after source or transform changes |

The stages keep market facts separate from policy interpretation. A
session/calendar label is context, not itself a trade filter. Missing intervals
remain explicit gaps. Resampling can aggregate extrema from multiple lower
timeframe bars, so a coarse bar's high/low need not equal one aligned fine
candle's high/low.

## Extension and validation

Add loaders or transforms behind existing package interfaces and preserve
timestamp, timezone, and sort-order contracts. Test boundary timestamps,
missing intervals, partial source windows, calendar transitions, and split
separation. Focused suites are under `tests/unit/market_data/`; feature
alignment and cache behavior are also covered in feature and integration tests.

See the [market-data guide](../docs/modules/market_data.md),
[data flow](../docs/architecture/data_flow.md), and
[causal-feature concept](../docs/concepts/market_structure.md).
