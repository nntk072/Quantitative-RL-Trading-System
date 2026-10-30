# Data Domain

## Primary Files

| File | Role |
|------|------|
| `market_data/loading/market_data_ingestion.py` | Bar dataset pipeline; owns `run_pipeline()` and `BAR_CACHE_VERSION` |
| `market_data/loading/tick_book_pipeline.py` | Configured tick-source selection, cache reuse, and multi-partition TickBook assembly |
| `market_data/loading/bars.py` | Stream/load raw bar and tick CSV files |
| `market_data/loading/ticks.py` | TickBook contract, tick ingestion, and timestamp/quote lookup |
| `market_data/cache/bars.py` | Bar-cache path, identity, completion validation, and atomic parquet/manifest publication |
| `market_data/cache/ticks.py` | Tick-cache semantic identity and atomic storage |
| `market_data/transforms/price_grid.py` | Price-grid normalization and tick-cache filenames |
| `market_data/transforms/resample.py` | Resample configured bars to higher timeframes |
| `market_data/transforms/cleaning.py` | Clean bars (deduplicate, sort, validate) |
| `market_data/transforms/sessions.py` | Session labels, NY mask, session IDs, and lookup |
| `market_data/transforms/session_schedule.py` | Load the configured date-specific session-close calendar |
| `market_data/transforms/align.py` | Align completed HTF bars to the M1 spine |
| `market_data/splits/definitions.py` | Train/test date-based split and training-mask contracts |
| `market_data/splits/walkforward.py` | Purged, non-overlapping walk-forward split generation |
| `market_data/contracts.py` | Logical dataset/event schema contracts |

## Key Symbols

| Symbol | File | Purpose |
|--------|------|---------|
| `run_pipeline()` | `market_data.loading` | Load, resample, clean, label, and cache configured bar datasets |
| `BAR_CACHE_VERSION` | `market_data.loading` | Bar-cache schema generation |
| `bar_cache_path()` | `market_data.cache.bars` | Canonical versioned bar-cache path |
| `build_tick_books()` | `market_data.loading` | Build/load configured TickBooks and join ordered tick partitions |
| `TickBook` | `market_data.loading.ticks` | Tick data container with quote lookup and execution-time access |
| `load_bars()` | `market_data.loading` | Load raw CSV bars |
| `resample()` | `market_data.transforms` | Resample bars to supported higher timeframes |
| `clean()` | `market_data.transforms` | Deduplicate, sort, and validate bars |
| `scheduled_session_close_map()` | `market_data.transforms.session_schedule` | Resolve the configured date-specific session-close calendar |
| `get_session()` | `market_data.transforms.sessions` | Broker-timezone session label (`asia`/`london`/`ny`/`closed`) |
| `add_session_labels()` | `market_data.transforms.sessions` | Add session eligibility labels without dropping rows |
| `add_session_id()` | `market_data.transforms.sessions` | Add unique session IDs |
| `ny_session_mask()` | `market_data.transforms.sessions` | Boolean NY-session mask |
| `filter_session()` | `market_data.transforms.sessions` | Mask-only helper (never drop feature bars) |
| `split_train_test()` | `market_data.splits` | Split aligned bars/features at date boundaries |
| `align_timeframes()` | `market_data.transforms.align` | Forward-fill completed HTF features onto the M1 spine |

## Direct Dependencies

- `configuration.loader` (resolved configuration)
- `pandas`, `omegaconf`
- `artifacts.identity` and `artifacts.atomic` (source identities and atomic cache manifests)

## Consumers (Callers)

- `features/pipeline/feature_matrix_builder.py` (uses pipeline output)
- `training/runner/training.py` (uses split + pipeline)
- `training/runner/backtest.py` (uses pipeline)

## Tests

| Test File | Covers |
|-----------|--------|
| `tests/integration/test_pipeline_splits.py` | `run_pipeline()` partition and cache behavior |
| `tests/integration/test_bar_cache_manifest.py` | Bar-cache identity and atomic completion manifest |
| `tests/integration/test_session_schedule.py` | Session-calendar loading and schema validation |
| `tests/integration/test_price_grid.py` | Price-grid identity and normalization |
| `tests/integration/test_resample_m10.py` | Higher-timeframe resampling semantics |
| `tests/unit/features/test_session_filter.py` | `filter_session()`, `ny_session_mask()`, cache versioning |
| `tests/unit/market_data/test_ticks.py` | `TickBook`, `build_tick_book()` |
| `tests/unit/features/test_causal_features.py` | Causal alignment verification |

## Do NOT Read For Data Tasks

- `features/` (downstream — read only if feature logic affects data)
- `simulation/environment/` (environment — separate domain)
- `models/` (models — separate domain)
- `simulation/backtest/` (backtest — separate domain)
- `training/` (training — separate domain)
- `integrations/mt5/` (live trading — separate domain)

## Critical Invariants

1. **M1 is the policy sequence, not the only source** — the thesis input uses the supplied M3–D1 bars as native higher-timeframe context; M1 resampling is not a substitute for those source files.
2. **Session labels are eligibility flags** — `filter_session` is mask-only, never drops feature bars
3. **Locked OOS split** — `train_end` / `test_start` in `default.yaml` must not be overridden by variants
4. **Semantic cache identity** — bar-cache reuse requires source identity plus partition, symbol/timeframe, timezone, NY session end, timestamp convention, and price-grid identity. Tick-cache reuse requires source bytes, timezone, session filter, and price-grid identity. Both parquet types and their atomic completion manifests are published together; incomplete or stale entries are rebuilt.
## Change Map

| Task | Axis | Start file | Contract and focused test | Expected scope | Keep unchanged |
|---|---|---|---|---|---|
| Add a market source | source adapter | `market_data/loading/bars.py` | `DatasetRef` and `MarketEventSchema`; `tests/unit/market_data/test_dataset_source_contract.py` | one source and source contract tests | feature algorithms and training workflows |
| Change session or split semantics | dataset policy | `market_data/splits/definitions.py` | partition identity; focused tests under `tests/integration/` | one transform or split module | model and report code |

## Axis of Change

- **Axis:** market source, event representation, transforms, and split policy.
- **Owner:** `market_data/` owns dataset identity, timestamps, event schema, and partitioning.
- **Stable boundary:** `DatasetRef`, `MarketEventSchema`, and `MarketDataset`.
- **Expected edit radius:** one source, transform, or split implementation with focused data tests.
- **Must not depend on:** training workflows, model internals, or report rendering.

## Verified Source Paths

- `market_data/loading/market_data_ingestion.py`
- `market_data/loading/tick_book_pipeline.py`
- `market_data/cache/bars.py`
- `market_data/cache/ticks.py`
- `market_data/transforms/session_schedule.py`
- `market_data/loading/bars.py`
- `market_data/loading/ticks.py`
- `market_data/splits/definitions.py`
- `market_data/transforms/align.py`
- `market_data/contracts.py`
