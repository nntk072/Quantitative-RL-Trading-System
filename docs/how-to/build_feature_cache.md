# Build a feature cache

Feature caches store deterministic derived inputs so training variants can
reuse the same market history without rebuilding indicators inside each run.
The cache is valid only for the source data, timeframe alignment, feature
options, and normalization contract used to create it.

## Build path

1. Prepare source bars and ticks using [market-data preparation](prepare_market_data.md).
2. Resolve the intended feature and split configuration. Confirm causal
   higher-timeframe alignment and train-only normalization.
3. Use the repository's prepared-cache workflow and retain its report, source
   identities, feature configuration, and cache identity together.
4. Validate expected rows, columns, timestamps, symbols, and timeframes before
   pointing a training run at the cache.

Inspect the current command options before writing outputs:

```bash
uv run qrl-data prebuild-experiment-run-cache --help
uv run qrl-experiment rebuild-named-cache --help
uv run qrl-experiment rebuild-named-cache --plan-only
```

The named-cache plan command resolves paths without writing. A rebuild requires
the explicit backup and report paths accepted by the command. Do not hand-copy
one variant's feature cache to another unless the resolved feature inputs and
cache identity are identical.

## Invalidation and reuse

Rebuild or produce a cache miss when source data, feature definitions, enabled
context, timeframe set, alignment semantics, or normalization scope changes.
Changing only the policy encoder does not require a new feature cache when its
input schema is unchanged. Treat cache version and content identity as
correctness checks, not as evidence that the feature implementation is valid.

See [feature construction](../modules/features.md),
[configuration](../config.md), and
[reproducibility requirements](../concepts/reproducibility.md).
