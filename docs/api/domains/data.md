# Data and features API

The market-data and feature domains transform timestamped source bars into a causal, versioned feature matrix. Ingestion owns parsing and validation; timeframe transforms own temporal alignment; feature builders own derived values; normalization and cache identity preserve train/test and reproducibility boundaries.

## Core contracts

- A bar index is an ordered timestamp axis with explicit source timezone semantics. Validate duplicate, missing, and malformed rows before feature construction.
- Higher-timeframe values become available only after the source candle is complete. `align_timeframes` forward-fills completed values onto the lower-timeframe spine; it does not backfill from a future close.
- Session labels are eligibility information. They do not remove rows from the feature dataset.
- Normalization statistics are fitted on training rows only. Later splits use the last training statistics.
- Feature-cache identity includes content inputs and schema/version. A version bump without content identity is not sufficient.

## Example

Align higher-timeframe bars to an M1 spine using the default completed-candle rule:

```python
from market_data.transforms.align import align_timeframes

aligned = align_timeframes(m1, {"M5": m5})
```

The helper shifts completed bars and forward-fills them; callers that already shift must use the documented `completed_bars=False` option to avoid shifting twice.

## Lifecycle and extension

Prepare normalized bars, align timeframe inputs, build feature columns, apply train-only transforms, then write/read the versioned cache. Add features through the configured pipeline and update its catalog, causality tests, and cache identity. Keep raw market transformations separate from strategy eligibility masks.

Start with the [market data and feature framework](../../framework/market_data_and_features), [causal feature tutorial](../../learn/tutorials/02_causal_features.ipynb), and [add a feature](../../how-to/add_feature). Generated references: {doc}`market data <../generated/market_data/index>` and {doc}`features <../generated/features/index>`.
