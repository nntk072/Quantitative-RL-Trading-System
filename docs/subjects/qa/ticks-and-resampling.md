# QA: ticks-and-resampling

- Rechecked: 2026-11-15 at HEAD `c0d982f9`; working tree has unrelated dirty files. This restores the missing report and is not a clean original-baseline build.
- Hub: [`../A_data_features/ticks-and-resampling.md`](../A_data_features/ticks-and-resampling.md), 154 lines; required headings and 150–500 page budget: **PASS**.
- Contract reference: [`../../reference/subjects/ticks-and-resampling.md`](../../reference/subjects/ticks-and-resampling.md) exists. Local links: **PASS**; its QA-report link resolves after this report is created.
- Notebook: [`../A_data_features/examples/ticks-and-resampling.ipynb`](../A_data_features/examples/ticks-and-resampling.ipynb); Tier A CPU, bundled/deterministic input, metadata validation **PASS**, saved output cells 1, saved error outputs 0, re-executed in memory in 1.94s (<60s). Notebook is in `examples/`, so no same-stem Sphinx collision.

## Five source-claim checks

| Claim | Source | Result |
|---|---|---|
| Tick iterator yields raw date/time strings. | `market_data/loading/bars.py::iter_ticks_chunks` | PASS |
| TickBook builder parses and localizes timestamps using its `tz` argument. | `market_data/loading/ticks.py::build_tick_book` | PASS |
| Quote lookup returns first tick at/after request and no stale quote past the end. | `market_data/loading/ticks.py::TickBook.quote_at` | PASS |
| Resampler uses first/max/min/last for OHLC. | `market_data/transforms/resample.py::_OHLCV_AGG` | PASS |
| Resampler sums activity, averages spread, and uses left-labeled/left-closed bins. | `market_data/transforms/resample.py::resample` | PASS |

## Limits

The full documentation site build was not run. No research-performance claim is made.
