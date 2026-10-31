# Features Domain

## Primary Files

| File | Role |
|------|------|
| `features/pipeline/feature_matrix_builder.py` | Full feature pipeline orchestrator; composes feature stages and schema selection |
| `features/pipeline/feature_build_inputs.py` | Resolves source timeframes, pair resampling, raw FVG columns, and fit masks |
| `features/pipeline/feature_cache_identity.py` | Feature cache version, content identity, and cache path construction |
| `features/pipeline/schema.py` | Model-observation column selection and raw-price exclusion rules |
| `features/pipeline/session_stage.py` | Session OHLC, prior-period, and previous-session feature assembly |
| `features/pipeline/po3_stage.py` | PO3/IFVG state assembly and confirmed-sweep audit output |
| `features/pipeline/structure_stage.py` | Swing, structure, and MTF BOS feature assembly |
| `features/technical/indicators.py` | Technical indicators (EMA, RSI, MACD, ATR, etc.) |
| `features/context/smt.py` | SMT divergence between US100/US500 |
| `features/technical/structure.py` | Structure levels, session levels; wraps swings for SL/TP |
| `features/technical/swings.py` | Fractal pivots and ATR-filtered zigzag swings |
| `features/context/liquidity.py` | Liquidity sweeps and BOS detection |
| `features/po3/fvg_detection.py` | FVG configuration and three-bar detection |
| `features/po3/ifvg_detection.py` | IFVG configuration and confirmation rules |
| `features/po3/trigger_rules.py` | HTF/LTF PO3 entry trigger construction |
| `features/po3/zones.py` | FVG zone lifecycle and plotting records |
| `features/po3/__init__.py` | Public exports for current FVG/IFVG and trigger APIs |
| `features/po3/po3_phase_state.py` | PO3 manipulation/distribution phases and IFVG-zone state |
| `features/po3/ifvg_state.py` | Causal PO3 manipulation/reclaim/IFVG phase-state construction |
| `features/pipeline/normalization.py` | Rolling z-score normalization with legacy masked-window and frozen-fold modes |
| `features/context/session_levels.py` | CT-anchored session OHLC, prior period H/L, quadrants |
| `features/context/reachability.py` | Causal take-profit room cap and risk-ratio reachability |
| `features/pipeline/walkforward_feature_fitting.py` | Builds fold-local feature views while fitting only on fold training rows |
| `features/context/entry_ideas.py` | Builds multi-hot entry-idea signals and source-timeframe context |
| `market_data/transforms/align.py` | HTF → M1 alignment (used by features) |

## Key Symbols

| Symbol | File | Purpose |
|--------|------|---------|
| `build_features()` | `features/__init__.py` → `features/pipeline/feature_matrix_builder.py` | Public feature-matrix API and pipeline implementation |
| `configured_feature_timeframes()` | `features.pipeline.feature_build_inputs` | Read nested or flat timeframe settings with a documented default |
| `resample_market_pair()` | `features.pipeline.feature_build_inputs` | Reuse native timeframes or resample each symbol's own M1 bars |
| `source_timeframe_training_mask()` | `features.pipeline.feature_build_inputs` | Restrict source-timeframe fits to candles completed by the training cutoff |
| `FEATURE_CACHE_VERSION` | `features/pipeline/feature_cache_identity.py` | Cache version; bump when feature semantics/output schema change |
| `feature_cache_content_hash()` | `features/pipeline/feature_cache_identity.py` | Content-sensitive feature-cache identity |
| `MTF_RAW_SUFFIXES` | `features/pipeline/schema.py` | Raw price-level columns excluded from model sequence observations |
| `build_indicators()` | `features/technical/indicators.py` | Compute configured technical indicators |
| `smt_divergence()` | `features/context/smt.py` | SMT divergence between symbols |
| `detect_pivots()` | `features/technical/swings.py` | Detect fractal pivot points |
| `detect_swings()` | `features/technical/swings.py` | ATR-filtered zigzag swings |
| `detect_bos()` | `features/context/liquidity.py` | Break-of-structure detection |
| `detect_liquidity_sweeps()` | `features/context/liquidity.py` | Liquidity sweep detection |
| `structure_levels()` | `features/technical/structure.py` | Causal swing price levels for SL/TP |
| `detect_session_levels()` | `features/technical/structure.py` | Broker-timezone session-based levels |
| `build_fvg_zones()` | `features/po3/zones.py` | Build FVG zone records |
| `detect_fvg()` | `features/po3/fvg_detection.py` | Detect fair value gaps |
| `build_po3_phase_features()` | `features/po3/entries.py` | Timestamp-derived accumulation/manipulation/distribution phase |
| `detect_po3_entries()` | `features/po3/trigger_rules.py` | Detect PO3 entry signals |
| `build_po3_state()` | `features/po3/po3_phase_state.py` | PO3 manipulation/distribution state |
| `build_ifvg_zone_features()` | `features/po3/po3_phase_state.py` | IFVG active-zone state features |
| `rolling_zscore()` | `features/pipeline/normalization.py` | Train-mask normalization; `frozen_fold` holds final training statistics through validation |
| `reachable_r_series()` | `features/context/reachability.py` | Reachable reward room from feature-owned session-range estimates |
| `max_tp_distance()` | `features/context/reachability.py` | Causal session-range cap from already closed NY sessions |
| `align_timeframes()` | `market_data/transforms/align.py` | Causally forward-fill completed HTF features onto an M1 spine |

## Direct Dependencies

- `market_data.loading` (configured bar and timeframe inputs)
- `market_data/transforms/resample.py` (HTF resampling)
- `market_data/transforms/align.py` (HTF alignment)
- `market_data.transforms.session_schedule` (known session closes)
- `configuration.loader` (resolved feature config)
- `market_data/transforms/sessions.py` (session eligibility and session clock)

## Consumers (Callers)

- `simulation/environment/env.py` (consumes feature matrix)
- `training/runner/training.py` (triggers feature build)
- `live/runtime/strategy.py` (rebuilds features for live obs)

## Tests

| Test File | Covers |
|-----------|--------|
| `tests/unit/features/test_build_pipeline.py` | Full feature pipeline + cache version |
| `tests/unit/features/test_htf_alignment.py` | HTF alignment |
| `tests/unit/features/test_pivots_swings.py` | Pivot/swing detection |
| `tests/unit/features/test_structure.py` | Structure detection |
| `tests/unit/features/test_liquidity.py` | Liquidity sweeps and BOS |
| `tests/unit/features/test_po3_config.py` | PO3 FVG detection |
| `tests/unit/features/test_po3_state.py` | PO3 state features |
| `tests/unit/features/test_session_ohlc.py` | Session OHLC |
| `tests/unit/features/test_variants.py` | Feature variants |
| `tests/unit/features/test_causal_features.py` | Causal feature verification |

## Do NOT Read For Feature Tasks

- `simulation/environment/env.py` (env consumes features but doesn't create them)
- `models/` (models consume features but don't create them)
- `simulation/backtest/` (backtest engine — separate domain)
- `training/` (training — orchestrates, doesn't implement features)
- `integrations/mt5/` (live trading — separate domain)

## Critical Invariants

1. **Causal only** — no future references in indicators or structure signals.
2. **Closed-bar HTF alignment** — higher-timeframe values become visible only after source-candle completion; alignment forward-fills and never back-fills.
3. **Training-only fit scope** — fitted normalization uses training rows and remains fixed on validation/evaluation rows.
4. **Cache identity** — source bars, feature configuration, output ordering, and normalization semantics contribute to cache identity; update the feature-cache version when schema or meaning changes.
5. **Observation schema** — raw price-level context is not silently added to normalized model sequences; validity and eligibility stay separate from feature values.

## Change Map

| Task | Axis | Start file | Contract and focused test | Expected scope | Keep unchanged |
|---|---|---|---|---|---|
| Add a feature stage | feature transform | `features/pipeline/feature_matrix_builder.py` | feature schema and cache identity; `tests/unit/features/test_build_pipeline.py` | one stage plus causal regression | trading and training workflow semantics |
| Change an input representation | input schema | `features/contracts.py` | `InputSchema`/`InputView`; `tests/unit/market_data/test_input_view_contract.py` | view contract and consumer adapter | PPO-specific observation coordinates |

## Axis of Change

- **Axis:** market-derived feature and context algorithms.
- **Owner:** `features/`; dataset and session semantics remain owned by `market_data/`.
- **Stable boundary:** feature views and the public `features` API.
- **Expected edit radius:** one feature implementation, its focused test, and the pipeline composer only when stage wiring changes.
- **Must not depend on:** trading execution/order code, training workflows, or model implementations.

## Verified Source Paths

- `features/pipeline/feature_matrix_builder.py`
- `features/contracts.py`
- `features/input_view.py`
- `features/pipeline/session_stage.py`
- `features/pipeline/po3_stage.py`
- `features/pipeline/structure_stage.py`
- `features/context/reachability.py`
- `features/technical/indicators.py`
- `tests/unit/features/test_stage_a_observation.py`
