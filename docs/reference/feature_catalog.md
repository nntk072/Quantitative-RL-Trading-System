# Feature catalog

`features/pipeline/feature_matrix_builder.py` composes the configured feature
matrix. The default configuration selects the base technical block, configured
higher-timeframe indicator blocks, and causal structure context. Optional
feature families remain opt-in. The exact output columns depend on the config
and available source timeframes; cache identity includes the effective config,
input identity, schema, and feature-cache version.

## Families and ownership

| Family | Source and timeframe | Main columns or representation | Configuration | Causality, normalization, and consumers |
|---|---|---|---|---|
| Technical indicators and returns | `features/technical/indicators.py`; primary M1 plus each configured `features.htf_timeframes` stream. | `ema_<period>`, RSI, MACD, ATR, ADX, Bollinger bands, stochastic values, returns by configured horizon, realized volatility, session VWAP, range/body/wick and time features. Higher-timeframe outputs receive a timeframe prefix. | `features.window`, indicator period keys, `features.return_horizons`, `features.realized_vol_period`, `features.vwap_session`, `features.htf_timeframes`. | Rolling indicators use trailing data. Higher-timeframe rows become visible through forward-fill after source bars are complete. Train-only rolling z-scores use `train_mask`; feature consumers are training, simulation, evaluation, and cache builders. |
| Swings and market structure | `features/technical/swings.py`, `features/technical/structure.py`, and `features/pipeline/structure_stage.py`; M1 and enabled HTFs. | Confirmed swing highs/lows, latest unswept swing references, structure breaks/shifts, distances and validity flags; timeframe-prefixed context is emitted where configured. | `features.structure.enabled`, `.timeframes`, `.swing_candidate_count`, `.candidate_price_increment`; swing detection period settings. | A pivot is exposed only after its confirmation bars. Structure distance columns use configured price/ATR units. Tests include `tests/unit/features/test_structure.py` and causal/context tests. |
| SMT divergence | `features/context/smt.py`; primary and secondary symbols, on selected timeframes. | Directional divergence and aligned swing context for the configured symbol pair. | `data.secondary`, `features.smt.enabled`, `features.smt.timeframes`, `features.smt_swing_period`, `features.smt_corr_window`. | Both symbol streams are aligned on timestamps before comparison; no backward fill is used. It is consumed as a feature block, not as an execution signal. See `tests/unit/features/test_smt.py` and the data-alignment tests. |
| Liquidity sweeps | `features/context/liquidity.py` and `features/technical/htf_sweeps.py`; configured HTFs. | Sweep direction, level, source timeframe, pivot/confirmation times, and candidate counts. | `features.liquidity.enabled`, `.timeframes`, plus structure/sweep parameters. | Only confirmed pivots and completed source candles are eligible. Audit outputs keep source and confirmation times for verification. |
| Session levels and session OHLC | `features/context/session_levels.py`, `features/pipeline/session_stage.py`, and `features/pipeline/session_context_features.py`. | Current/prior session highs and lows, previous-day/week levels, quadrant values, and optional VWAP context. | `features.include_session_ohlc`, `features.sessions.*`, `session.*`, and `features.include_previous_session_pd`. | Session labels are eligibility/context flags; they do not remove rows from the feature dataset. Timezone conversion uses configured DST-aware rules. |
| Premium/discount and order blocks | `features/context/premium_discount.py` and `features/context/order_blocks.py`; selected session and source timeframes. | Premium/discount location and distance, prior-session context, order-block zones, age, retest and ATR-distance fields. | `features.include_pd_context`, `.include_previous_session_pd`, `.order_blocks.enabled`, `.order_blocks.timeframes`, and the order-block search/age/impulse values. | Source zones are based on confirmed structure and completed candles, then forward-aligned. Do not interpret these features as proof that a level will hold. |
| PO3, FVG, and IFVG | `features/po3/` plus `features/pipeline/po3_stage.py`; configured reference HTF/LTF streams. | PO3 phase/progress, gap zones, inversion state, retest/trigger state, and optional timeframe-specific zone/distance columns. | `features.include_po3`, `features.include_fvg_ifvg`, `features.include_po3_full`, `features.po3_*`, `features.ifvg_mtf`, and `features.gap_reaction_buffer_*`. | HTF zones and inversions are exposed only after the source candle closes; trigger confirmation follows the configured phase/reference modes. Coverage includes `tests/unit/features/test_po3_config.py`, PO3/IFVG tests, and alignment properties. |
| Entry ideas | `features/context/entry_ideas.py`; selected timeframes. | Multi-hot `entry_idea_<idea>_<timeframe>_<side>` columns and overlap summaries for PO3, order-block, FVG/IFVG retest, and swing-retracement ideas. | `features.entry_ideas.enabled`, `.timeframes`, `.retracement_low`, `.retracement_high`, and `.levels`. | Signals may overlap. Direct directional policies can use them as context; categorical setup-action policies also use the exact current-row flags to mask ineligible setup choices. `NO_TRADE` remains available. |
| Trade-setup candidate context | `features/context/trade_setup_candidates.py` and `decisioning/trade_setup.py`. | Stable candidate IDs map each idea/timeframe/direction tuple to its matching entry-idea column; a separate no-trade category is always present. | `env.trade_setup_actions` plus the entry-idea configuration and versioned action/observation schema. | Candidate masks are computed from current feature rows and applied before policy selection. The 109-category order is defined by the trade-setup catalog, not by dataframe column order. |

## Alignment, normalization, and cache rules

1. Build source-timeframe values using only data available by the decision
   timestamp. `market_data/transforms/align.py::align_timeframes` forward-fills
   completed values onto the M1 index; it never backfills future values.
2. Preserve every market bar. Session status and feature eligibility are masks
   or values, not row filters.
3. Fit rolling normalization on the training mask only. Validation and test
   rows use the last available training statistics; walk-forward folds refit
   within their own training partition.
4. Bump `FEATURE_CACHE_VERSION` when generated feature semantics change and
   include all content-affecting inputs in the cache hash. A version bump alone
   does not replace the content hash.
5. Treat the configured feature columns as model input schema. Column order,
   dtype, normalization, timeframe and mask semantics must be preserved in
   cache, observation, and checkpoint metadata.

The generated base defaults are listed in the
[configuration reference](configuration.md). Feature code and direct tests
are under `features/` and `tests/unit/features/`; no feature family name in
this page is a promise of predictive value.
