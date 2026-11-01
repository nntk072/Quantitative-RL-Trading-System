# Entry-idea opportunity-count aggregates

## Research question

How often were the configured PO3, order-block, standard-deviation/Fibonacci,
and FVG/IFVG context flags active in the cached M1 timeline, and how often
did each flag family begin a new active episode across its reported source
timeframes?

## Data and method

The archived count report summarizes a 630,787-row US100.cash feature cache
across M1, M3, M5, M10, M15, M30, H1, H4, and D1 context. Its annual and
per-idea/per-timeframe CSVs are tracked; the underlying feature cache is not.
The [reproduction notebook](../reproduce/entry_idea_opportunity_counts.ipynb)
recomputes family episode totals and timeframe aggregates from those CSVs,
checks them against the annual summary, and regenerates a plot.

## Result and status

The tracked per-timeframe table sums to 120,161 family/timeframe episode starts
in 2025 and 95,297 in the exposed 2026 interval. The family totals are:

| Year | PO3 | Order block | Standard deviation | FVG/IFVG reaction |
| ---: | ---: | ---: | ---: | ---: |
| 2024 | 95 | 119 | 330 | 368 |
| 2025 | 14,421 | 17,339 | 42,150 | 46,251 |
| 2026 | 11,172 | 13,500 | 34,375 | 36,250 |

These are cached-context episode counts, not executable trades, unique
independent opportunities, policy decisions, or performance. Repeated
higher-timeframe states are correlated across M1 rows. The 2026 dates are
already exposed and report-only.

## Reproduction level and limits

This is R2 only for the annual family totals and timeframe aggregates that can
be recomputed from the tracked machine-readable CSVs. The timestamp-level
feature cache and original counting inputs are absent, so the notebook cannot
independently recount source bars or verify feature extraction from raw data.
It does not support checkpoint replay or retraining.

See the [archived count report](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/main/evidence/research/entry_idea_opportunity_counts/entry_idea_opportunity_counts.md),
[multi-timeframe context preview](order_block_and_multitimeframe_context.md),
and [result registry](../reproduce/result_registry.md).
