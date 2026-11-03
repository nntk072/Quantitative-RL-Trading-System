"""Build a source-linked inventory for the Stage D causal feature audit."""

from __future__ import annotations

import ast
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from configuration.paths import repository_root

ROOT = repository_root(__file__)
FEATURE_ROOT = ROOT / "features"
UPSTREAM_DATA_MODULES = (
    ROOT / "market_data/transforms/align.py",
    ROOT / "market_data/transforms/resample.py",
    ROOT / "market_data/transforms/sessions.py",
    ROOT / "market_data/transforms/session_schedule.py",
)
TEST_ROOTS = (
    ROOT / "tests" / "unit" / "features",
    ROOT / "tests" / "unit" / "market_data",
    ROOT / "tests" / "research",
)
DEFAULT_CENSUS_DIR = ROOT / "evidence/research/trade_setup_opportunity_census"
OUTPUT_DIR = ROOT / "evidence/research/feature_causality"
MATRIX_PATH = OUTPUT_DIR / "feature_causality_matrix.csv"
SUMMARY_PATH = OUTPUT_DIR / "feature_causality_matrix.json"

FIELDS = (
    "record_type",
    "feature_or_flag",
    "function",
    "output_features",
    "source_timeframe",
    "source_event_timestamp",
    "effective_availability_timestamp",
    "units",
    "lookback_or_state_lifetime",
    "warmup_missingness",
    "fit_scope",
    "masked_cases",
    "deterministic_fixture",
    "prefix_invariance_test",
    "source_path",
    "test_path_candidates",
    "evidence_artifact",
    "evidence_status",
    "evidence_note",
    "active_candidate_rows",
    "identified_source_event_rows",
    "missing_source_event_time_rows",
    "distinct_candidate_scoped_event_ids",
    "identified_identity_episode_starts",
    "adjacent_active_identity_changes",
    "distinct_ids_reused_across_active_episodes",
    "identity_coverage_fraction",
    "identity_measurement_status",
)

UNASSESSED = "UNASSESSED"

# Manually reviewed against the listed implementation and tests. These entries
# document only the contracts those sources establish; they do not establish
# feed-clock or exchange-calendar authority.
REVIEWED_FUNCTION_METADATA: dict[tuple[str, str], dict[str, str]] = {
    (
        "features/technical/structure.py",
        "detect_session_levels",
    ): {
        "output_features": "rolling Asian/London highs and lows plus prior-day OHLC levels",
        "source_timeframe": "input OHLC timeframe, interpreted using index wall-clock fields",
        "source_event_timestamp": "current and prior observations in the rolling session streams; completed prior-day extrema for previous-day levels",
        "effective_availability_timestamp": "current row for rolling session levels; first bar of each later source date for prior-day high/low",
        "units": "price units",
        "lookback_or_state_lifetime": "rolling swing_period rows over selected Asian/London observations, forward-filled to later rows; prior-day values shift one date",
        "warmup_missingness": "levels remain missing before qualifying source-session bars; prior-day extrema missing before a completed prior date",
        "fit_scope": "not fitted",
        "masked_cases": "session masks use index wall-clock labels; timezone/source-clock interpretation must match configured export",
        "deterministic_fixture": "tests/unit/features/test_session_levels.py::TestDetectSessionLevels.test_session_levels_are_prefix_invariant; tests/unit/features/test_session_levels.py::TestDetectSessionLevels.test_prev_day_high_low",
        "prefix_invariance_test": "tests/unit/features/test_session_levels.py::TestDetectSessionLevels.test_session_levels_are_prefix_invariant; aggregate selected-profile real-market prefix report",
        "test_path_candidates": "tests/unit/features/test_session_levels.py; tests/research/test_feature_prefix_invariance.py",
        "evidence_artifact": "docs/research/feature_causality_and_availability.md",
        "evidence_status": "source_and_prefix_fixture_reviewed; session_wall_clock_authority_unresolved",
        "evidence_note": "Rolling levels use past/current rows and are carried forward; they are not necessarily final full-session highs. Source timezone authority and whether the configured session windows match the instrument remain open.",
    },
    (
        "features/technical/indicators.py",
        "volume_spike",
    ): {
        "output_features": "current activity divided by the trailing rolling median activity",
        "source_timeframe": "input activity series timeframe",
        "source_event_timestamp": "current activity and up to window-1 preceding rows",
        "effective_availability_timestamp": "current input row",
        "units": "dimensionless ratio",
        "lookback_or_state_lifetime": "trailing window rows with min_periods=1",
        "warmup_missingness": "available from first row unless median is zero or input missing",
        "fit_scope": "not fitted",
        "masked_cases": "zero median yields missing; pipeline supplies tick-count activity when configured",
        "deterministic_fixture": "tests/unit/features/test_causal_features.py::test_volume_spike_uses_current_activity_over_trailing_median; tests/unit/features/test_build_pipeline.py::TestBuildFeaturesPipeline.test_volume_spike_uses_canonical_tick_activity_when_volume_is_zero",
        "prefix_invariance_test": "tests/unit/features/test_causal_features.py::test_volume_spike_is_prefix_invariant; aggregate selected-profile real-market prefix report",
        "test_path_candidates": "tests/unit/features/test_causal_features.py; tests/integration/test_activity.py; tests/research/test_feature_prefix_invariance.py",
        "evidence_artifact": "docs/research/feature_causality_and_availability.md",
        "evidence_status": "source_and_pipeline_formula_tested; selected_real_market_profiles_passed",
        "evidence_note": "Direct fixtures verify the rolling-median formula, zero/missing behavior, and pipeline use of tick-count activity when CFD volume columns are zero.",
    },
    (
        "features/technical/indicators.py",
        "vwap_level",
    ): {
        "output_features": "session-reset cumulative typical-price weighted by tick-count activity",
        "source_timeframe": "input OHLC and activity timeframe",
        "source_event_timestamp": "current bar OHLC/activity and prior rows with the same session_id",
        "effective_availability_timestamp": "current input row",
        "units": "price units",
        "lookback_or_state_lifetime": "cumulative within session_id; resets when the supplied ID changes",
        "warmup_missingness": "requires session_id and activity input; zero activity rows are ignored as weights",
        "fit_scope": "not fitted",
        "masked_cases": "raises when session_id or activity is unavailable; no validation of session-id timezone authority",
        "deterministic_fixture": "tests/unit/features/test_session_ohlc.py::test_vwap_level_resets_per_session; tests/unit/features/test_session_ohlc.py::test_vwap_level_requires_session_id",
        "prefix_invariance_test": "incremental within-session cumsum by source; aggregate selected-profile real-market prefix report",
        "test_path_candidates": "tests/unit/features/test_session_ohlc.py; tests/integration/test_activity.py; tests/research/test_feature_prefix_invariance.py",
        "evidence_artifact": "docs/research/feature_causality_and_availability.md",
        "evidence_status": "source_and_fixture_reviewed; session_id_clock_authority_unresolved",
        "evidence_note": "This is a tick-count-weighted CFD VWAP-like measure, not exchange-volume VWAP; its reset semantics inherit session_id.",
    },
    (
        "features/technical/indicators.py",
        "vwap_from_session",
    ): {
        "output_features": "close-to-session-VWAP relative distance",
        "source_timeframe": "input OHLC and activity timeframe",
        "source_event_timestamp": "current close and current/prior session VWAP state",
        "effective_availability_timestamp": "current input row",
        "units": "dimensionless relative price distance",
        "lookback_or_state_lifetime": "inherits cumulative within-session state from vwap_level",
        "warmup_missingness": "inherits missingness and requirements from vwap_level; zero VWAP denominator yields missing",
        "fit_scope": "not fitted",
        "masked_cases": "available only when session VWAP is enabled and its source columns exist",
        "deterministic_fixture": "tests/unit/features/test_session_ohlc.py::test_vwap_level_matches_normalized_vwap",
        "prefix_invariance_test": "inherits vwap_level row-wise cumulative prefix behavior; selected-profile report when configured",
        "test_path_candidates": "tests/unit/features/test_session_ohlc.py; tests/research/test_feature_prefix_invariance.py",
        "evidence_artifact": "docs/research/feature_causality_and_availability.md",
        "evidence_status": "source_and_fixture_reviewed; optional_config_and_session_clock_limits",
        "evidence_note": "This helper is opt-in and inherits the session id's timezone/reset meaning and activity-source semantics.",
    },
    (
        "features/technical/indicators.py",
        "ny_session_clock",
    ): {
        "output_features": "clipped NY-session phase sine/cosine and normalized minutes-to-close",
        "source_timeframe": "input DatetimeIndex",
        "source_event_timestamp": "current index hour and minute only",
        "effective_availability_timestamp": "current input row",
        "units": "dimensionless phase values and [0,1] minutes-to-close",
        "lookback_or_state_lifetime": "none; row-local transform with configured clock bounds",
        "warmup_missingness": "none for valid HH:MM boundaries and a datetime index",
        "fit_scope": "not fitted",
        "masked_cases": "outside-session times clip to endpoints; the function does not timezone-convert the index",
        "deterministic_fixture": "tests/unit/features/test_stage_a_observation.py::test_session_clock_clips_outside_the_session",
        "prefix_invariance_test": "row-local; aggregate selected-profile real-market prefix report",
        "test_path_candidates": "tests/unit/features/test_stage_a_observation.py; tests/research/test_feature_prefix_invariance.py",
        "evidence_artifact": "docs/research/feature_causality_and_availability.md",
        "evidence_status": "source_and_fixture_reviewed; input_clock_authority_unresolved",
        "evidence_note": "The builder passes configured session start/end, but this function reads wall-clock fields from the supplied index as-is.",
    },
    (
        "features/technical/indicators.py",
        "sweep_velocity",
    ): {
        "output_features": "bullish and bearish close distance from London levels normalized by ATR",
        "source_timeframe": "input OHLC timeframe plus aligned session-level series",
        "source_event_timestamp": "current close, current/past ATR state, and current aligned London high/low values",
        "effective_availability_timestamp": "current input row; level availability inherits detect_session_levels",
        "units": "dimensionless ATR-normalized distances",
        "lookback_or_state_lifetime": "recursive ATR; London/Asian levels forward-fill from their source rows",
        "warmup_missingness": "missing levels or zero ATR yield missing outputs",
        "fit_scope": "not fitted",
        "masked_cases": "Asian level arguments are accepted but unused; output uses only London high/low",
        "deterministic_fixture": "tests/unit/features/test_causal_features.py::test_sweep_velocity_is_prefix_invariant",
        "prefix_invariance_test": "tests/unit/features/test_causal_features.py::test_sweep_velocity_is_prefix_invariant; aggregate selected-profile real-market prefix report",
        "test_path_candidates": "tests/unit/features/test_causal_features.py; tests/research/test_feature_prefix_invariance.py",
        "evidence_artifact": "docs/research/feature_causality_and_availability.md",
        "evidence_status": "source_and_prefix_fixture_reviewed; selected_real_market_profiles_passed; asian_parameter_usage_unresolved",
        "evidence_note": "Despite accepting Asian level parameters, the implementation currently uses only London levels. The prefix test proves no future-row dependence for supplied levels, not an Asian-level contribution.",
    },
    (
        "features/technical/indicators.py",
        "wick_ratio",
    ): {
        "output_features": "absolute upper-wick extent divided by total candle range",
        "source_timeframe": "input OHLC timeframe",
        "source_event_timestamp": "current bar open, high, low, and close",
        "effective_availability_timestamp": "current input row after bar close",
        "units": "dimensionless ratio when high exceeds low",
        "lookback_or_state_lifetime": "none; row-local candle calculation",
        "warmup_missingness": "missing for zero-range bars",
        "fit_scope": "not fitted",
        "masked_cases": "lower wick is not represented; formula's abs does not create a lower-wick feature",
        "deterministic_fixture": "tests/unit/features/test_causal_features.py::test_wick_ratio_measures_upper_wick_only",
        "prefix_invariance_test": "row-local formula fixture; aggregate selected-profile real-market prefix report",
        "test_path_candidates": "tests/unit/features/test_causal_features.py; tests/research/test_feature_prefix_invariance.py",
        "evidence_artifact": "docs/research/feature_causality_and_availability.md",
        "evidence_status": "source_and_formula_fixture_tested; selected_real_market_profiles_passed; legacy_upper_wick_name_retained",
        "evidence_note": "The direct fixture verifies the upper-wick formula. The established output name is retained for observation compatibility and documented as upper-wick-only.",
    },
    (
        "features/technical/indicators.py",
        "ema",
    ): {
        "output_features": "exponentially weighted moving average",
        "source_timeframe": "input series timeframe",
        "source_event_timestamp": "current row and all prior rows since series start",
        "effective_availability_timestamp": "current input row",
        "units": "same units as the input series",
        "lookback_or_state_lifetime": "recursive EWM state with span parameter",
        "warmup_missingness": "pandas EWM emits from the first finite observation by default",
        "fit_scope": "not fitted",
        "masked_cases": "input NaNs follow pandas EWM behavior; no explicit gap/staleness policy",
        "deterministic_fixture": "tests/unit/features/test_causal_features.py::test_ema_causal",
        "prefix_invariance_test": "tests/unit/features/test_causal_features.py::test_ema_causal; aggregate selected-profile real-market prefix report",
        "test_path_candidates": "tests/unit/features/test_causal_features.py",
        "evidence_artifact": "docs/research/feature_causality_and_availability.md",
        "evidence_status": "source_and_prefix_fixture_reviewed; selected_real_market_profiles_passed",
        "evidence_note": "EWM is computed in input order from current/past values. The selected full-pipeline prefix checks do not cover every configuration or input clock.",
    },
    (
        "features/technical/indicators.py",
        "rsi",
    ): {
        "output_features": "relative strength index",
        "source_timeframe": "input close series timeframe",
        "source_event_timestamp": "current close change and prior EWM gain/loss state",
        "effective_availability_timestamp": "current input row",
        "units": "bounded oscillator in [0, 100] when defined",
        "lookback_or_state_lifetime": "recursive EWM gain/loss with alpha=1/period",
        "warmup_missingness": "first difference and zero-loss denominator produce missing values",
        "fit_scope": "not fitted",
        "masked_cases": "zero losses are replaced by NaN; no explicit missing-bar policy",
        "deterministic_fixture": "tests/unit/features/test_causal_features.py::test_rsi_causal",
        "prefix_invariance_test": "tests/unit/features/test_causal_features.py::test_rsi_causal; aggregate selected-profile real-market prefix report",
        "test_path_candidates": "tests/unit/features/test_causal_features.py",
        "evidence_artifact": "docs/research/feature_causality_and_availability.md",
        "evidence_status": "source_and_prefix_fixture_reviewed; selected_real_market_profiles_passed",
        "evidence_note": "The implementation uses current and prior close changes only. The tests check truncated-prefix invariance for the fixture.",
    },
    (
        "features/technical/indicators.py",
        "macd",
    ): {
        "output_features": "MACD line, signal line, and histogram",
        "source_timeframe": "input close series timeframe",
        "source_event_timestamp": "current close and recursive fast/slow/signal EMA states",
        "effective_availability_timestamp": "current input row",
        "units": "price units for all three outputs",
        "lookback_or_state_lifetime": "recursive EWM spans for fast, slow, and signal components",
        "warmup_missingness": "default EWM emits from first observation; upstream missing values propagate per pandas",
        "fit_scope": "not fitted",
        "masked_cases": "no explicit missing-bar or session-reset policy",
        "deterministic_fixture": "tests/unit/features/test_causal_features.py::test_macd_causal",
        "prefix_invariance_test": "tests/unit/features/test_causal_features.py::test_macd_causal; aggregate selected-profile real-market prefix report",
        "test_path_candidates": "tests/unit/features/test_causal_features.py",
        "evidence_artifact": "docs/research/feature_causality_and_availability.md",
        "evidence_status": "source_and_prefix_fixture_reviewed; selected_real_market_profiles_passed",
        "evidence_note": "The implementation composes causal EMAs. The configured real-market report covers selected feature profiles, not all periods/configurations.",
    },
    (
        "features/technical/indicators.py",
        "ema_features",
    ): {
        "output_features": "configured EMA values, one-row slopes, and normalized close-to-EMA distances",
        "source_timeframe": "input close series timeframe",
        "source_event_timestamp": "current close plus recursive EWM state; slope also uses prior EMA",
        "effective_availability_timestamp": "current input row",
        "units": "EMA in price units; slope in price units per bar; distance dimensionless",
        "lookback_or_state_lifetime": "one recursive EWM per configured period plus one-row difference",
        "warmup_missingness": "slope is missing at the first row; zero EMA denominator yields missing distance",
        "fit_scope": "not fitted",
        "masked_cases": "zero EMA values yield missing normalized distances",
        "deterministic_fixture": "tests/unit/features/test_causal_features.py::test_ema_causal",
        "prefix_invariance_test": "tests/unit/features/test_causal_features.py::test_ema_causal; aggregate selected-profile real-market prefix report",
        "test_path_candidates": "tests/unit/features/test_causal_features.py; tests/unit/features/test_build_pipeline.py",
        "evidence_artifact": "docs/research/feature_causality_and_availability.md",
        "evidence_status": "source_and_prefix_fixture_reviewed; selected_real_market_profiles_passed",
        "evidence_note": "Configured EMA periods are resolved from feature config. These outputs inherit the input index and do not retain raw source event times.",
    },
    (
        "features/technical/indicators.py",
        "atr",
    ): {
        "output_features": "exponentially smoothed average true range",
        "source_timeframe": "input OHLC timeframe",
        "source_event_timestamp": "current high/low and previous close",
        "effective_availability_timestamp": "current input row",
        "units": "price units",
        "lookback_or_state_lifetime": "recursive EWM true-range state with alpha=1/period",
        "warmup_missingness": "first row uses high-low because shifted previous close is missing and row maximum skips NaN",
        "fit_scope": "not fitted",
        "masked_cases": "no session reset; missing OHLC policy is inherited from pandas aggregation",
        "deterministic_fixture": "tests/unit/features/test_pivots_swings.py::test_swings_only_visible_after_confirmation; tests/unit/features/test_feature_cache_and_fit_scope.py::test_d1_technical_features_are_normalized_before_m1_alignment",
        "prefix_invariance_test": "tests/unit/features/test_assembled_causality.py::test_assembled_matrix_truncation_causality; aggregate selected-profile real-market prefix report",
        "test_path_candidates": "tests/unit/features/test_pivots_swings.py; tests/unit/features/test_feature_cache_and_fit_scope.py; tests/unit/features/test_assembled_causality.py",
        "evidence_artifact": "docs/research/feature_causality_and_availability.md",
        "evidence_status": "source_and_assembled_prefix_tested; selected_real_market_profiles_passed",
        "evidence_note": "True range uses the current bar and previous close only. Its lack of session reset and first-row convention are explicit implementation semantics. The assembled prefix test covers its selected builder configuration, not every ATR period or input pathology.",
    },
    (
        "features/technical/indicators.py",
        "adx",
    ): {
        "output_features": "ADX, positive directional index, and negative directional index",
        "source_timeframe": "input OHLC timeframe",
        "source_event_timestamp": "current high/low movement and true range including previous close",
        "effective_availability_timestamp": "current input row",
        "units": "dimensionless directional values scaled to [0, 100] when defined",
        "lookback_or_state_lifetime": "recursive EWM states for directional movement, true range, and DX",
        "warmup_missingness": "initial diff/zero denominators create missing values; pandas EWM then propagates",
        "fit_scope": "not fitted",
        "masked_cases": "zero true-range or directional denominator yields missing values; no session reset",
        "deterministic_fixture": "tests/unit/features/test_build_pipeline.py::TestBuildFeaturesPipeline.test_expected_base_columns_present",
        "prefix_invariance_test": "tests/unit/features/test_assembled_causality.py::test_assembled_matrix_truncation_causality; aggregate selected-profile real-market prefix report",
        "test_path_candidates": "tests/unit/features/test_build_pipeline.py; tests/unit/features/test_assembled_causality.py",
        "evidence_artifact": "docs/research/feature_causality_and_availability.md",
        "evidence_status": "source_and_assembled_prefix_tested; selected_real_market_profiles_passed",
        "evidence_note": "Directional movement and true range use current/past OHLC. The assembled prefix test covers its selected builder configuration, not every ADX period or denominator edge case.",
    },
    (
        "features/technical/indicators.py",
        "bollinger",
    ): {
        "output_features": "rolling percent-B, normalized band width, and moving midpoint",
        "source_timeframe": "input close series timeframe",
        "source_event_timestamp": "current close and trailing close window",
        "effective_availability_timestamp": "current input row",
        "units": "percent-B dimensionless; width relative to midpoint; midpoint in price units",
        "lookback_or_state_lifetime": "trailing period rows with full-window warmup",
        "warmup_missingness": "midpoint and deviation remain missing until the full rolling window is present; zero band/mid denominators yield missing",
        "fit_scope": "not fitted",
        "masked_cases": "constant windows yield missing percent-B due to zero width",
        "deterministic_fixture": "tests/unit/features/test_build_pipeline.py::TestBuildFeaturesPipeline.test_expected_base_columns_present",
        "prefix_invariance_test": "tests/unit/features/test_assembled_causality.py::test_assembled_matrix_truncation_causality; aggregate selected-profile real-market prefix report",
        "test_path_candidates": "tests/unit/features/test_build_pipeline.py; tests/unit/features/test_assembled_causality.py",
        "evidence_artifact": "docs/research/feature_causality_and_availability.md",
        "evidence_status": "source_and_assembled_prefix_tested; selected_real_market_profiles_passed",
        "evidence_note": "Rolling calculations use the current and trailing rows. The assembled prefix test covers its selected builder configuration, not every Bollinger period or degenerate input.",
    },
    (
        "features/technical/indicators.py",
        "stochastic",
    ): {
        "output_features": "rolling stochastic K and smoothed D",
        "source_timeframe": "input OHLC timeframe",
        "source_event_timestamp": "current close and trailing high/low ranges",
        "effective_availability_timestamp": "current input row",
        "units": "oscillator scaled to [0, 100] when defined",
        "lookback_or_state_lifetime": "trailing k_period high/low and d_period K-value windows",
        "warmup_missingness": "K waits for k_period rows; D waits for k_period plus d_period minus one rows",
        "fit_scope": "not fitted",
        "masked_cases": "zero rolling range yields missing K and downstream D",
        "deterministic_fixture": "tests/unit/features/test_build_pipeline.py::TestBuildFeaturesPipeline.test_expected_base_columns_present",
        "prefix_invariance_test": "tests/unit/features/test_assembled_causality.py::test_assembled_matrix_truncation_causality; aggregate selected-profile real-market prefix report",
        "test_path_candidates": "tests/unit/features/test_build_pipeline.py; tests/unit/features/test_assembled_causality.py",
        "evidence_artifact": "docs/research/feature_causality_and_availability.md",
        "evidence_status": "source_and_assembled_prefix_tested; selected_real_market_profiles_passed",
        "evidence_note": "Both stages are trailing rolling operations; no future row is indexed. The assembled prefix test covers its selected builder configuration; warmup and missingness behavior has separate fixtures.",
    },
    (
        "features/technical/indicators.py",
        "returns",
    ): {
        "output_features": "log close returns at configured horizons",
        "source_timeframe": "input close series timeframe",
        "source_event_timestamp": "current close and close h rows earlier",
        "effective_availability_timestamp": "current input row",
        "units": "dimensionless log return",
        "lookback_or_state_lifetime": "configured horizon rows",
        "warmup_missingness": "first h rows are missing; nonpositive close becomes missing before log",
        "fit_scope": "not fitted",
        "masked_cases": "nonpositive prices yield missing log values and returns",
        "deterministic_fixture": "tests/unit/features/test_causal_features.py::test_returns_causal",
        "prefix_invariance_test": "tests/unit/features/test_causal_features.py::test_returns_causal; aggregate selected-profile real-market prefix report",
        "test_path_candidates": "tests/unit/features/test_causal_features.py",
        "evidence_artifact": "docs/research/feature_causality_and_availability.md",
        "evidence_status": "source_and_prefix_fixture_reviewed; selected_real_market_profiles_passed",
        "evidence_note": "The log difference uses a same-timeframe close and its earlier close only; requested horizons are config supplied.",
    },
    (
        "features/technical/indicators.py",
        "realized_vol",
    ): {
        "output_features": "rolling population standard deviation of log returns",
        "source_timeframe": "input close series timeframe",
        "source_event_timestamp": "current log return and trailing period return rows",
        "effective_availability_timestamp": "current input row",
        "units": "dimensionless return volatility",
        "lookback_or_state_lifetime": "period trailing returns; requires a full rolling window",
        "warmup_missingness": "missing until period return values are present; nonpositive closes propagate missing",
        "fit_scope": "not fitted",
        "masked_cases": "no explicit missing-data imputation",
        "deterministic_fixture": "tests/unit/features/test_build_pipeline.py::TestBuildFeaturesPipeline.test_expected_base_columns_present",
        "prefix_invariance_test": "tests/unit/features/test_assembled_causality.py::test_assembled_matrix_truncation_causality; aggregate selected-profile real-market prefix report",
        "test_path_candidates": "tests/unit/features/test_build_pipeline.py; tests/unit/features/test_assembled_causality.py",
        "evidence_artifact": "docs/research/feature_causality_and_availability.md",
        "evidence_status": "source_and_assembled_prefix_tested; selected_real_market_profiles_passed",
        "evidence_note": "Rolling standard deviation uses current/past log returns with population deviation. The assembled prefix test covers its selected builder configuration, not every period or missing-data pattern.",
    },
    (
        "features/technical/indicators.py",
        "time_features",
    ): {
        "output_features": "cyclical time-of-day and weekday sine/cosine columns",
        "source_timeframe": "input DatetimeIndex",
        "source_event_timestamp": "current timestamp fields only",
        "effective_availability_timestamp": "current input row",
        "units": "dimensionless sine/cosine values in [-1, 1]",
        "lookback_or_state_lifetime": "none; row-local timestamp transform",
        "warmup_missingness": "none for a valid datetime index",
        "fit_scope": "not fitted",
        "masked_cases": "timestamp timezone/local-clock interpretation is inherited from the supplied index",
        "deterministic_fixture": "tests/unit/features/test_causal_features.py::test_time_features_use_the_supplied_index_and_are_prefix_invariant",
        "prefix_invariance_test": "tests/unit/features/test_causal_features.py::test_time_features_use_the_supplied_index_and_are_prefix_invariant; aggregate selected-profile real-market prefix report",
        "test_path_candidates": "tests/unit/features/test_causal_features.py; tests/research/test_feature_prefix_invariance.py",
        "evidence_artifact": "docs/research/feature_causality_and_availability.md",
        "evidence_status": "source_and_supplied_index_fixture_tested; timestamp_timezone_authority_unresolved",
        "evidence_note": "The code reads the supplied index hour/minute/day-of-week; it does not convert to a configured exchange timezone itself.",
    },
    (
        "features/technical/indicators.py",
        "atr_normalized_price",
    ): {
        "output_features": "current close change divided by ATR",
        "source_timeframe": "input OHLC timeframe",
        "source_event_timestamp": "current close, prior close, and current/past true-range state",
        "effective_availability_timestamp": "current input row",
        "units": "dimensionless ATR-normalized close move",
        "lookback_or_state_lifetime": "one-row close difference plus recursive ATR state",
        "warmup_missingness": "first close difference is missing; zero ATR denominator yields missing",
        "fit_scope": "not fitted",
        "masked_cases": "no session reset or explicit gap policy",
        "deterministic_fixture": "tests/unit/features/test_build_pipeline.py::TestBuildFeaturesPipeline.test_expected_base_columns_present",
        "prefix_invariance_test": "tests/unit/features/test_assembled_causality.py::test_assembled_matrix_truncation_causality; aggregate selected-profile real-market prefix report",
        "test_path_candidates": "tests/unit/features/test_build_pipeline.py; tests/unit/features/test_assembled_causality.py",
        "evidence_artifact": "docs/research/feature_causality_and_availability.md",
        "evidence_status": "source_and_assembled_prefix_tested; selected_real_market_profiles_passed",
        "evidence_note": "The function combines a causal one-row difference with current/past ATR. The assembled prefix test covers its selected builder configuration only.",
    },
    (
        "features/technical/indicators.py",
        "build_indicators",
    ): {
        "output_features": "configured EMA/MACD/RSI/ATR/ADX/Bollinger/stochastic/returns/volatility/time and optional session-VWAP features",
        "source_timeframe": "input cleaned bar timeframe; caller builds separate matrices for configured higher-timeframe streams",
        "source_event_timestamp": "inherited from each same-index bar and any prior-row rolling state",
        "effective_availability_timestamp": "same input row before downstream higher-timeframe availability alignment",
        "units": "mixed; see component function records and configured output schema",
        "lookback_or_state_lifetime": "component-specific recursive or trailing states; optional VWAP resets by supplied session_id",
        "warmup_missingness": "component-specific NaNs are not globally imputed here",
        "fit_scope": "normalization occurs downstream, not in this builder",
        "masked_cases": "VWAP is omitted unless enabled and session_id is present; component missingness remains",
        "deterministic_fixture": "tests/unit/features/test_htf_alignment.py::test_align_timeframes_completed_bar; tests/unit/features/test_feature_cache_and_fit_scope.py::test_d1_technical_features_are_normalized_before_m1_alignment",
        "prefix_invariance_test": "aggregate selected-profile real-market report rebuilds configured feature matrices and compares four profiles at three cutoffs",
        "test_path_candidates": "tests/unit/features/test_build_pipeline.py; tests/unit/features/test_htf_alignment.py; tests/unit/features/test_assembled_causality.py; tests/research/test_feature_prefix_invariance.py",
        "evidence_artifact": "docs/research/feature_causality_and_availability.md",
        "evidence_status": "source_and_assembled_prefix_tested; selected_real_market_profiles_passed; exhaustive_configurations_open",
        "evidence_note": "This builder is same-timeframe and leaves causal alignment and normalization to later stages. The assembled prefix fixture and real-market audit cover selected configurations, not every option or feed publication time.",
    },
    (
        "features/context/liquidity.py",
        "detect_liquidity_sweeps",
    ): {
        "output_features": "fresh high/low sweep events, active swing level, wick extreme, reclaim flag, and bars since sweep",
        "source_timeframe": "input OHLC timeframe plus confirmed swing and ATR series on the same index",
        "source_event_timestamp": "current bar high/low crossing the prior-row confirmed swing level; reclaim uses current close",
        "effective_availability_timestamp": "current bar close, conditional on the input row representing a completed bar; source-clock label semantics remain unresolved",
        "units": "binary events, price levels, and integer-like bar age",
        "lookback_or_state_lifetime": "swing_period confirmation history, ATR period, and active sweep state until reclaim",
        "warmup_missingness": "no sweep without finite prior confirmed level and ATR; level/age remain missing when inactive",
        "fit_scope": "not fitted",
        "masked_cases": "a take must be fresh and within max_sweep_distance_atr times ATR; deep breaks are not sweeps",
        "deterministic_fixture": "tests/unit/features/test_liquidity.py::TestSweepLow; tests/unit/features/test_liquidity.py::TestSweepHigh",
        "prefix_invariance_test": "tests/unit/features/test_liquidity.py::TestCausality.test_sweep_does_not_use_future_data",
        "test_path_candidates": "tests/unit/features/test_liquidity.py; tests/research/test_feature_prefix_invariance.py",
        "evidence_artifact": "docs/research/feature_causality_and_availability.md",
        "evidence_status": "source_and_fixture_reviewed; bar_close_and_source_clock_semantics_unresolved",
        "evidence_note": "The function shifts confirmed structure one row before testing current OHLC. Its event is only knowable after that bar closes; exported row labels do not establish the underlying publication clock.",
    },
    (
        "features/context/liquidity.py",
        "detect_bos",
    ): {
        "output_features": "up/down close-through BOS flags and the crossed prior swing level",
        "source_timeframe": "bars and structure levels on the same OHLC timeframe",
        "source_event_timestamp": "current close crossing a previously confirmed swing level",
        "effective_availability_timestamp": "current bar close, conditional on completed-bar input; source-clock label semantics remain unresolved",
        "units": "binary events and price units",
        "lookback_or_state_lifetime": "inherits swing confirmation window from structure; level is shifted one row",
        "warmup_missingness": "no BOS before a finite prior confirmed high/low exists; level is missing when no event fires",
        "fit_scope": "not fitted",
        "masked_cases": "wick penetration without a close-through does not fire; missing prior levels are inactive",
        "deterministic_fixture": "tests/unit/features/test_liquidity.py::TestBos.test_bos_up_from_confirmed_swing; tests/unit/features/test_liquidity.py::TestBos.test_wick_above_is_not_bos",
        "prefix_invariance_test": "tests/unit/features/test_liquidity.py::TestCausality.test_sweep_does_not_use_future_data",
        "test_path_candidates": "tests/unit/features/test_liquidity.py; tests/unit/features/test_pd_context.py",
        "evidence_artifact": "docs/research/feature_causality_and_availability.md",
        "evidence_status": "source_and_fixture_reviewed; bar_close_and_source_clock_semantics_unresolved",
        "evidence_note": "The helper shifts the supplied structure level and compares only the current close. Upstream structure construction and the source clock remain separate acceptance conditions.",
    },
    (
        "features/context/smt.py",
        "smt_divergence",
    ): {
        "output_features": "confirmed paired-swing SMT flags, rolling close correlation, and relative close spread",
        "source_timeframe": "caller-supplied primary and secondary streams aligned to the primary index",
        "source_event_timestamp": "swing confirmation row for divergence; current close rows for correlation and spread",
        "effective_availability_timestamp": "primary row at the later of the paired pivot confirmations; correlation/spread at the primary row",
        "units": "binary event flags, dimensionless rolling correlation, and relative price spread",
        "lookback_or_state_lifetime": "pair matching within max(1, swing_period) row indices; rolling correlation spans corr_window rows",
        "warmup_missingness": "rolling correlation missing until its window is populated; unmatched pivots emit no divergence",
        "fit_scope": "not fitted",
        "masked_cases": "secondary values are forward-filled onto the primary index; leading unmatched rows remain missing; no maximum staleness limit is applied",
        "deterministic_fixture": "tests/unit/features/test_smt.py::test_smt_requires_paired_successive_swings_and_marks_divergence_on_confirmation; tests/unit/features/test_smt.py::test_unmatched_primary_pivot_does_not_create_smt; tests/unit/features/test_smt.py::test_smt_forward_fills_missing_secondary_bars_without_future_influence",
        "prefix_invariance_test": "tests/unit/features/test_smt.py::test_smt_forward_fills_missing_secondary_bars_without_future_influence; selected real-market profiles passed aggregate prefix comparison",
        "test_path_candidates": "tests/unit/features/test_smt.py; tests/research/test_feature_prefix_invariance.py",
        "evidence_artifact": "docs/research/feature_causality_and_availability.md",
        "evidence_status": "source_and_missing_bar_prefix_fixture_tested; cross_symbol_clock_and_staleness_unresolved",
        "evidence_note": "The direct fixture verifies internal missing secondary bars carry the prior close and that leading gaps are not backfilled; full and truncated results match. This does not establish secondary publication time or a maximum acceptable age.",
    },
    (
        "features/context/order_blocks.py",
        "build_order_block_features",
    ): {
        "output_features": "bullish/bearish active zone flags, raw zone bounds and midpoint, origin timestamp, age, ATR distance, new-zone events, and retest events",
        "source_timeframe": "single input OHLC timeframe; ATR and confirmed swing levels use the same bars",
        "source_event_timestamp": "origin opposing candle plus displacement close-through bar; retest uses zone-overlap bar and a later confirming close",
        "effective_availability_timestamp": "displacement bar close for new zones and current bar close for retest confirmation, conditional on completed-bar input",
        "units": "binary flags, price units, milliseconds since epoch for origin time, integer-like bar age, and ATR-normalized distance",
        "lookback_or_state_lifetime": "prior confirmed swing and ATR state; last opposing candle searched within search_bars; zone expires after max_age_bars or distal-edge close-through",
        "warmup_missingness": "no zone without a finite prior swing, finite ATR, qualifying displacement, and opposing candle; price/state fields are missing while inactive",
        "fit_scope": "not fitted",
        "masked_cases": "only close-through displacement qualifies; new-zone source time is retained but displacement/publication time is not emitted as a separate field",
        "deterministic_fixture": "tests/unit/features/test_order_blocks.py::test_order_block_features_are_causal_and_keep_raw_zone_prices; tests/unit/features/test_order_blocks.py::test_order_block_retest_requires_overlap_then_later_close_confirmation; tests/unit/features/test_order_blocks.py::test_new_same_side_order_block_replaces_previous_zone; tests/unit/features/test_order_blocks.py::test_order_block_parameters_reject_invalid_values",
        "prefix_invariance_test": "tests/unit/features/test_order_blocks.py::test_order_block_features_are_causal_and_keep_raw_zone_prices compares a 120-row prefix against the full result",
        "test_path_candidates": "tests/unit/features/test_order_blocks.py; tests/research/test_feature_prefix_invariance.py",
        "evidence_artifact": "docs/research/feature_causality_and_availability.md",
        "evidence_status": "source_and_prefix_fixture_reviewed; completed_bar_and_source_clock_semantics_unresolved",
        "evidence_note": "structure_levels shifts the last confirmed swing one row before the break check, while ATR and the candidate candle search use current/past rows. Fixtures verify later-row retest confirmation, same-side replacement, and prefix invariance; the producer still represents only one active same-side zone, while input timestamp timezone, source-clock authority, and exact event publication time remain open.",
    },
    (
        "features/context/order_blocks.py",
        "build_order_block_features_with_event_ledger",
    ): {
        "output_features": "unchanged scalar latest-zone feature frame plus a per-zone retest ledger with zone ID, side, confirmation time, source origin, bounds, and scalar-selection marker",
        "source_timeframe": "single input OHLC timeframe; ATR and confirmed swing levels use the same bars",
        "source_event_timestamp": "source opposing-candle origin, zone-overlap bar, and later retest-confirmation close",
        "effective_availability_timestamp": "each retest event is emitted only on a bar after the recorded overlap, at that bar's close, conditional on completed-bar input",
        "units": "scalar feature units plus integer-like bar IDs, nanosecond timestamps, side labels, price bounds, and boolean scalar-selection marker",
        "lookback_or_state_lifetime": "diagnostic zones remain eligible through max_age_bars or distal-edge close-through; later overlaps can re-arm a zone after a prior confirmation",
        "warmup_missingness": "inherits scalar detector requirements: confirmed swing, finite ATR, qualifying displacement, and an opposing source candle",
        "fit_scope": "not fitted",
        "masked_cases": "creation-bar retests are excluded; invalidated or expired diagnostic zones are removed; scalar-zone selection is marked only when its retest is also present in the scalar output",
        "deterministic_fixture": "tests/unit/features/test_order_blocks.py::test_order_block_event_ledger_preserves_overlapping_zone_retests",
        "prefix_invariance_test": "tests/unit/features/test_order_blocks.py::test_order_block_event_ledger_is_prefix_causal compares scalar rows and per-zone events through a truncated prefix",
        "test_path_candidates": "tests/unit/features/test_order_blocks.py; scripts/research/analysis/features/analyze_order_block_zone_events.py",
        "evidence_artifact": "evidence/research/feature_causality/feature_causality_matrix.csv",
        "evidence_status": "source_and_per_zone_prefix_fixtures_reviewed; policy_event_cardinality_and_source_clock_open",
        "evidence_note": "The diagnostic API preserves overlapping still-active zones and keeps the scalar feature output identical. Its ordinal zone IDs are local to one input sequence and do not establish stable logical event identity, one proposal per zone, policy selection, or feed publication time; no selected-config market census is claimed because order-block features are disabled in that overlay.",
    },
    (
        "features/context/session_levels.py",
        "session_mask",
    ): {
        "output_features": "boolean membership in a configured wall-clock session window",
        "source_timeframe": "input DatetimeIndex and configured session timezone/window",
        "source_event_timestamp": "current timestamp interpreted through the selected source_clock_model and converted to session_tz",
        "effective_availability_timestamp": "current input row",
        "units": "boolean eligibility flag",
        "lookback_or_state_lifetime": "none; row-local timezone conversion and half-open [start, end) comparison",
        "warmup_missingness": "none for a timezone-aware index and valid configured timezone/window",
        "fit_scope": "not fitted",
        "masked_cases": "naive indices and unsupported source_clock_model values raise; FTMO model reconstructs UTC instants from assumed server wall time",
        "deterministic_fixture": "tests/unit/features/test_session_ohlc.py::test_session_mask_january_broker_times; tests/unit/features/test_session_ohlc.py::test_ftmo_server_clock_maps_winter_and_summer_to_same_ct_session",
        "prefix_invariance_test": "row-local timestamp transform; no dedicated multi-row prefix test",
        "test_path_candidates": "tests/unit/features/test_session_ohlc.py; tests/unit/features/test_session_filter.py",
        "evidence_artifact": "docs/research/feature_causality_and_availability.md",
        "evidence_status": "source_and_clock_fixture_reviewed; source_timezone_and_schedule_authority_unresolved",
        "evidence_note": "Timezone conversion and the FTMO GMT+2/+3 mapping are implemented and fixture-tested, but the configured source clock, exchange-session authority, and source event/publication timing are not established by those fixtures.",
    },
    (
        "features/context/session_levels.py",
        "session_ohlc",
    ): {
        "output_features": "running session open/high/low/current close, forward-filled after the window ends",
        "source_timeframe": "input OHLC timeframe interpreted in session_tz under source_clock_model",
        "source_event_timestamp": "in-session open/high/low and current close observations; completed session values after the configured window",
        "effective_availability_timestamp": "current row for running values; completed values are held from subsequent rows after the session window",
        "units": "price units",
        "lookback_or_state_lifetime": "state accumulates from the first observed in-window row through the window and carries forward until later session observations",
        "warmup_missingness": "all outputs remain missing before the first configured session window is observed",
        "fit_scope": "not fitted",
        "masked_cases": "only rows in the wall-clock window contribute; timezone/source-clock interpretation and missing-session-bar quality are not validated here",
        "deterministic_fixture": "tests/unit/features/test_session_ohlc.py::test_session_ohlc_basic; tests/unit/features/test_session_ohlc.py::test_session_ohlc_causal",
        "prefix_invariance_test": "tests/unit/features/test_session_ohlc.py::test_session_ohlc_causal; tests/unit/features/test_session_ohlc.py::test_ftmo_ct_session_features_are_prefix_invariant_across_dst",
        "test_path_candidates": "tests/unit/features/test_session_ohlc.py; tests/research/test_feature_prefix_invariance.py",
        "evidence_artifact": "docs/research/feature_causality_and_availability.md",
        "evidence_status": "source_and_prefix_fixtures_reviewed; source_timezone_and_schedule_authority_unresolved",
        "evidence_note": "The implementation uses running cummax/cummin inside the session and forward-fill afterward. DST and selected clock-model fixtures do not independently establish source timezone, calendar authority, or exact source-event publication times.",
    },
    (
        "features/context/session_levels.py",
        "prior_period_high_low",
    ): {
        "output_features": "previous completed calendar-day or ISO-week high and low",
        "source_timeframe": "input OHLC bars grouped by calendar date/week in the configured tz after source-clock conversion",
        "source_event_timestamp": "observed extrema from the prior calendar period",
        "effective_availability_timestamp": "rows in the next configured calendar period, conditional on the timezone/calendar interpretation",
        "units": "price units",
        "lookback_or_state_lifetime": "one completed day or ISO week; each period maps the previous period's aggregate",
        "warmup_missingness": "missing throughout the first represented calendar period because no prior period is present",
        "fit_scope": "not fitted",
        "masked_cases": "only D-prefixed or W-prefixed frequencies are accepted; incomplete prior periods use the extrema of observed rows",
        "deterministic_fixture": "tests/unit/features/test_session_ohlc.py::test_prior_period_high_low_yesterday; tests/unit/features/test_session_ohlc.py::test_prior_period_high_low_lastweek",
        "prefix_invariance_test": "previous-period mapping uses a one-period shift; no dedicated prefix-extension assertion",
        "test_path_candidates": "tests/unit/features/test_session_ohlc.py",
        "evidence_artifact": "docs/research/feature_causality_and_availability.md",
        "evidence_status": "source_and_fixture_reviewed; source_timezone_and_schedule_authority_unresolved",
        "evidence_note": "The shift prevents current-period extrema from feeding that period's rows. Calendar timezone/source-clock authority and whether the observed prior period is complete remain open.",
    },
    (
        "features/context/session_levels.py",
        "range_quadrants",
    ): {
        "output_features": "four quarter-band boundary levels derived from supplied high/low series",
        "source_timeframe": "inherited from the caller-supplied high and low series",
        "source_event_timestamp": "inherited from the supplied high/low values",
        "effective_availability_timestamp": "same row as the supplied high/low values",
        "units": "same price units as high and low",
        "lookback_or_state_lifetime": "none; row-wise arithmetic only",
        "warmup_missingness": "missing high/low inputs propagate through arithmetic",
        "fit_scope": "not fitted",
        "masked_cases": "no validation of range ordering, source, completion, or timestamp alignment; the two equilibrium outputs are duplicates by definition",
        "deterministic_fixture": "tests/unit/features/test_session_ohlc.py::test_range_quadrants; tests/unit/features/test_session_ohlc.py::test_range_quadrants_nan_propagates",
        "prefix_invariance_test": "row-wise arithmetic; no independent multi-row prefix test",
        "test_path_candidates": "tests/unit/features/test_session_ohlc.py",
        "evidence_artifact": "docs/research/feature_causality_and_availability.md",
        "evidence_status": "source_and_fixture_reviewed; input_range_availability_unresolved",
        "evidence_note": "The helper adds no state or delay; its availability and causality depend entirely on the caller-provided range series.",
    },
    (
        "features/context/session_levels.py",
        "prev_ny_high_low",
    ): {
        "output_features": "latest clock-completed configured session high and low",
        "source_timeframe": "input high/low rows selected by a configured wall-clock window in session_tz",
        "source_event_timestamp": "observed highs/lows within the session; the session end is the completion boundary",
        "effective_availability_timestamp": "first input row at or after the configured session end, according to source_clock_model",
        "units": "price units",
        "lookback_or_state_lifetime": "most recently clock-completed session; levels persist until a later session completion",
        "warmup_missingness": "missing until the first configured session end has passed",
        "fit_scope": "not fitted",
        "masked_cases": "observed extrema are promoted at clock close even with data gaps; completeness is audited separately",
        "deterministic_fixture": "tests/unit/features/test_session_ohlc.py::test_prev_ny_high_low_uses_only_completed_ny_sessions; tests/unit/features/test_session_ohlc.py::test_prev_ny_high_low_promotes_observed_range_after_clock_close_with_data_gap; tests/unit/features/test_session_ohlc.py::test_prev_ny_high_low_uses_local_close_across_dst_transition",
        "prefix_invariance_test": "tests/unit/features/test_session_ohlc.py::test_prev_ny_high_low_uses_only_completed_ny_sessions",
        "test_path_candidates": "tests/unit/features/test_session_ohlc.py; tests/research/test_feature_prefix_invariance.py",
        "evidence_artifact": "docs/research/feature_causality_and_availability.md",
        "evidence_status": "source_and_prefix_fixture_reviewed; source_timezone_and_schedule_authority_unresolved",
        "evidence_note": "The helper does not require a complete session and exposes the observed range at its configured clock boundary. Source timezone, calendar/schedule authority, and exact publication clock remain open.",
    },
    (
        "features/context/session_levels.py",
        "previous_labeled_session_ohlc",
    ): {
        "output_features": "latest complete configured session high/low/midpoint and stable label code",
        "source_timeframe": "input high/low rows and configured session windows interpreted in session_tz under source_clock_model",
        "source_event_timestamp": "all expected in-session bars through the final bar before the configured close",
        "effective_availability_timestamp": "configured session close boundary, emitted at the first input row at or after that boundary",
        "units": "price units plus integer-like session label code; zero code means no completed session",
        "lookback_or_state_lifetime": "latest complete labeled session; prior levels remain until a later complete session closes",
        "warmup_missingness": "price and close-time fields remain missing until a qualifying complete session closes; label code begins at zero",
        "fit_scope": "not fitted",
        "masked_cases": "requires the expected final bar and a contiguous bar_minutes sequence; truncated or internally gapped sessions are skipped",
        "deterministic_fixture": "tests/unit/features/test_session_ohlc.py::test_previous_labeled_session_uses_latest_completed_session_and_dst_clock; tests/unit/features/test_session_ohlc.py::test_previous_labeled_session_does_not_promote_truncated_tail; tests/unit/features/test_session_ohlc.py::test_previous_labeled_session_skips_session_with_missing_interior_bar",
        "prefix_invariance_test": "completion is assigned only from each configured close onward; no separate prefix-extension assertion",
        "test_path_candidates": "tests/unit/features/test_session_ohlc.py; tests/research/test_feature_prefix_invariance.py",
        "evidence_artifact": "docs/research/feature_causality_and_availability.md",
        "evidence_status": "source_and_completion_fixtures_reviewed; source_timezone_and_schedule_authority_unresolved",
        "evidence_note": "Source verifies contiguous expected timestamps and delays exposure to the configured close. Session schedule authority, source timezone/clock model provenance, and source publication time remain open.",
    },
    (
        "features/technical/swings.py",
        "detect_pivots",
    ): {
        "output_features": "confirmed high/low pivot events, pivot wick price/extreme, and source-row location",
        "source_timeframe": "input OHLC timeframe",
        "source_event_timestamp": "pivot-center row at i; stored location points to that source row",
        "effective_availability_timestamp": "confirmation row i + right; event and price are emitted only there",
        "units": "price units and integer-like row positions; event flags are boolean",
        "lookback_or_state_lifetime": "left bars before and right bars after each center row",
        "warmup_missingness": "no pivot can be confirmed before left/right windows are populated; absent pivots remain false/NaN",
        "fit_scope": "not fitted",
        "masked_cases": "strict inequalities reject ties at the pivot high/low; final right-window rows cannot be confirmed",
        "deterministic_fixture": "tests/unit/features/test_pivots_swings.py::test_pivot_confirmation_has_no_lookahead",
        "prefix_invariance_test": "tests/unit/features/test_pivots_swings.py::test_features_invariant_to_future_data verifies downstream structure prefix values",
        "test_path_candidates": "tests/unit/features/test_pivots_swings.py",
        "evidence_artifact": "docs/research/feature_causality_and_availability.md",
        "evidence_status": "source_and_fixture_reviewed; confirmation_delay_explicit",
        "evidence_note": "The pivot center is historical context only; the event is available after the configured right-side confirmation bars.",
    },
    (
        "features/technical/swings.py",
        "detect_swings",
    ): {
        "output_features": "ATR-filtered accepted swing events and forward-filled accepted swing prices, extremes, and source locations",
        "source_timeframe": "input OHLC timeframe and confirmed pivot stream",
        "source_event_timestamp": "underlying pivot confirmation row and its stored center location",
        "effective_availability_timestamp": "acceptance row when close reverses by ATR threshold; missing ATR makes threshold zero",
        "units": "price units, row positions, and boolean events; ATR threshold is price-scaled",
        "lookback_or_state_lifetime": "candidate can be replaced by a more extreme confirmed pivot until reversal; accepted swing state persists forward",
        "warmup_missingness": "accepted-price fields stay missing until first acceptance; computed ATR warmup becomes zero threshold through _atr_at",
        "fit_scope": "not fitted",
        "masked_cases": "opposite-side candidates are held until reversal/acceptance; ATR-missing candidates accept immediately at confirmation",
        "deterministic_fixture": "tests/unit/features/test_pivots_swings.py::test_swings_only_visible_after_confirmation; tests/unit/features/test_pivots_swings.py::test_swing_features_are_causal",
        "prefix_invariance_test": "tests/unit/features/test_pivots_swings.py::test_features_invariant_to_future_data; tests/unit/features/test_pivots_swings.py::test_retained_levels_incremental_equals_full_run",
        "test_path_candidates": "tests/unit/features/test_pivots_swings.py",
        "evidence_artifact": "docs/research/feature_causality_and_availability.md",
        "evidence_status": "source_and_fixture_reviewed; acceptance_delay_explicit",
        "evidence_note": "Accepted swing values are emitted at acceptance and then carried forward. This is distinct from the earlier pivot-center timestamp and the pivot confirmation timestamp.",
    },
    (
        "features/context/entry_ideas.py",
        "build_entry_idea_features",
    ): {
        "output_features": "108 directional/timeframe setup-entry flags plus idea-count and overlap summaries",
        "source_timeframe": "M1-aligned feature rows containing M1 and prefixed higher-timeframe source columns",
        "source_event_timestamp": "inherited source feature event timestamps; not retained by the binary output flags",
        "effective_availability_timestamp": "same M1 row as each aligned source flag; source availability depends on upstream feature construction",
        "units": "binary float flags and nonnegative counts",
        "lookback_or_state_lifetime": "inherited from each source event/state; the projection adds no memory",
        "warmup_missingness": "missing, nonnumeric, nonfinite, zero, and negative source values project inactive",
        "fit_scope": "not fitted; deterministic row-wise projection",
        "masked_cases": "unavailable or unsupported source columns remain inactive; idea combinations remain multi-hot",
        "deterministic_fixture": "tests/unit/features/test_entry_ideas.py::test_entry_ideas_are_multi_hot_and_keep_source_timeframes; tests/unit/features/test_entry_ideas.py::test_gap_reaction_context_keeps_fvg_and_ifvg_distinct",
        "prefix_invariance_test": "projection is row-wise; end-to-end prefix comparison covers four selected configured profiles, not every source-feature family",
        "test_path_candidates": "tests/unit/features/test_entry_ideas.py; tests/research/test_feature_prefix_invariance.py",
        "evidence_artifact": "docs/research/feature_causality_and_availability.md",
        "evidence_status": "source_and_fixture_reviewed; output_row_availability_known; source_event_timing_unresolved",
        "evidence_note": "Catalog flags are overlapping context projections, not independent discoveries or executable trades. The flag does not preserve the originating event time or publication delay.",
    },
    (
        "features/context/entry_ideas.py",
        "entry_idea_context",
    ): {
        "output_features": "selected directional idea names, source-timeframe labels, stop timeframe floor, gap families, and optional active-zone records",
        "source_timeframe": "timeframe encoded in the selected source feature names or confirmation code",
        "source_event_timestamp": "source event timestamps are used only for selected PO3 zone records; other zone records omit event time",
        "effective_availability_timestamp": "called at decision time using the current feature row; it does not read later rows",
        "units": "categorical metadata, timeframe names, and validated price-zone bounds",
        "lookback_or_state_lifetime": "reports active source flags and active zones provided in the current row",
        "warmup_missingness": "invalid direction yields empty context; malformed or missing zone bounds are omitted",
        "fit_scope": "not fitted; current-row projection",
        "masked_cases": "only positive directional flags and valid direction-matched zones are emitted; FVG and IFVG remain separate",
        "deterministic_fixture": "tests/unit/features/test_entry_ideas.py::test_entry_idea_context_matches_zero_copy_feature_row; tests/unit/features/test_entry_ideas.py::test_po3_context_records_only_the_ifvg_used_for_distribution; tests/unit/features/test_entry_ideas.py::test_fvg_retest_context_records_only_its_active_fvg_for_plot_controls",
        "prefix_invariance_test": "current-row projection; no independent multi-row prefix test",
        "test_path_candidates": "tests/unit/features/test_entry_ideas.py",
        "evidence_artifact": "docs/research/feature_causality_and_availability.md",
        "evidence_status": "source_and_fixture_reviewed; bounded_to_supplied_row_context",
        "evidence_note": "This helper describes source context for trade construction and reporting; its presence does not validate upstream feature timing or establish that a zone was published by the decision clock.",
    },
    (
        "market_data/transforms/align.py",
        "align_timeframes",
    ): {
        "output_features": "input columns renamed with timeframe and optional symbol prefix",
        "source_timeframe": "caller-supplied higher timeframe",
        "source_event_timestamp": "higher-timeframe row index (bar open in the tested fixtures)",
        "effective_availability_timestamp": (
            "with availability_times, the supplied close timestamp; otherwise the next observed "
            "higher-timeframe index after shift(1), then forward-filled on the M1 index"
        ),
        "units": "inherited from input feature columns",
        "lookback_or_state_lifetime": "latest available higher-timeframe row persists until a later row",
        "warmup_missingness": "no value before the first available completed higher-timeframe row",
        "fit_scope": "not fitted by this alignment function",
        "masked_cases": "empty higher-timeframe inputs are skipped; null supplied availability times are dropped",
        "deterministic_fixture": (
            "tests/unit/features/test_htf_alignment.py::test_align_timeframes_completed_bar; "
            "tests/unit/features/test_htf_alignment.py::test_align_timeframes_uses_explicit_close_times_for_short_final_bar"
        ),
        "prefix_invariance_test": (
            "tests/unit/features/test_htf_alignment.py::test_htf_future_invariance"
        ),
        "test_path_candidates": "tests/unit/features/test_htf_alignment.py",
        "evidence_artifact": "docs/research/feature_causality_and_availability.md",
        "evidence_status": "source_and_fixture_reviewed; selected_real_market_prefix_profiles_passed",
        "evidence_note": (
            "Source and deterministic tests establish completed-bar alignment and explicit-close "
            "behavior. Selected real-market profiles passed prefix invariance. The default uses the next observed HTF index, not an authoritative session calendar."
        ),
    },
    (
        "features/pipeline/normalization.py",
        "rolling_zscore",
    ): {
        "output_features": "one standardized output column per input column, same names",
        "source_timeframe": "inherited from input rows",
        "source_event_timestamp": "current input row timestamp and its trailing-window observations",
        "effective_availability_timestamp": "current input row timestamp; rolling statistics use current/past rows only",
        "units": "dimensionless z-score; zero standard deviation produces missing output",
        "lookback_or_state_lifetime": (
            "window rows; frozen_fold counts selected training observations, legacy mode uses the input row window"
        ),
        "warmup_missingness": "standard deviation is missing until at least two eligible observations; zero variance remains missing",
        "fit_scope": (
            "frozen_fold requires an aligned nonempty training mask and freezes validation statistics at final train values; "
            "legacy_masked_window uses train rows when masked, or all rows when no mask is supplied"
        ),
        "masked_cases": "misaligned or empty frozen_fold masks raise; masked legacy rows do not fit statistics",
        "deterministic_fixture": (
            "tests/unit/features/test_fold_normalize.py::test_frozen_fold_does_not_drift_over_validation_rows; "
            "tests/unit/features/test_fold_normalize.py::test_frozen_fold_validation_poisoning_preserves_train_values; "
            "tests/unit/features/test_feature_cache_and_fit_scope.py::test_fit_scoped_zscore_ignores_future_poison"
        ),
        "prefix_invariance_test": (
            "Train-stat poisoning tests cover fit isolation; selected real-market feature profiles passed prefix invariance at three cutoffs"
        ),
        "test_path_candidates": (
            "tests/unit/features/test_fold_normalize.py; tests/unit/features/test_feature_cache_and_fit_scope.py"
        ),
        "evidence_artifact": "docs/research/feature_causality_and_availability.md",
        "evidence_status": "source_and_fit_scope_fixtures_reviewed; selected_real_market_prefix_profiles_passed",
        "evidence_note": (
            "Implementation and tests establish train-only fitted statistics for the documented modes. "
            "The selected real-market profiles passed prefix invariance, but this does not establish causal correctness of every caller or feature family."
        ),
    },
    (
        "market_data/transforms/align.py",
        "timeframe_close_times",
    ): {
        "output_features": "availability_time timestamp series",
        "source_timeframe": "caller-supplied timeframe",
        "source_event_timestamp": "input bar index (bar open in the tested fixtures)",
        "effective_availability_timestamp": (
            "nominal open plus timeframe duration; for intraday bars, clipped to a supplied "
            "date-specific close when the bar overlaps that close after session_start; D1 is not clipped"
        ),
        "units": "timezone-aware or naive timestamps inherited from the input index",
        "lookback_or_state_lifetime": "none; each timestamp is calculated from its own bar and optional schedule row",
        "warmup_missingness": "empty input returns an empty timestamp series; unsupported timeframe raises",
        "fit_scope": "not fitted",
        "masked_cases": "schedule applies only to matching dates and intraday bars meeting the configured session-start condition",
        "deterministic_fixture": (
            "tests/unit/features/test_alignment_properties.py::test_timeframe_close_times_clip_a_short_session_final_bar; "
            "tests/unit/features/test_alignment_properties.py::test_timeframe_close_times_reject_unsupported_timeframes"
        ),
        "prefix_invariance_test": "not applicable to this row-local timestamp calculation; schedule authority remains unresolved",
        "test_path_candidates": "tests/unit/features/test_alignment_properties.py",
        "evidence_artifact": "docs/research/feature_causality_and_availability.md",
        "evidence_status": "source_and_fixture_reviewed; schedule_authority_unresolved",
        "evidence_note": (
            "Implementation and fixtures establish the configured clipping rule. They do not establish that the local schedule is authoritative."
        ),
    },
    (
        "market_data/transforms/align.py",
        "join_symbols",
    ): {
        "output_features": "secondary input columns prefixed and backward-as-of joined to primary rows",
        "source_timeframe": "caller-supplied secondary stream",
        "source_event_timestamp": "secondary row index timestamp",
        "effective_availability_timestamp": (
            "latest secondary row timestamp less than or equal to the primary row timestamp; exact matches are allowed"
        ),
        "units": "inherited from secondary input columns",
        "lookback_or_state_lifetime": "latest prior secondary row persists without a configured tolerance",
        "warmup_missingness": "missing secondary values remain missing until a prior or same-time row exists",
        "fit_scope": "not fitted",
        "masked_cases": "future secondary rows are excluded; stale-row expiry is not enforced",
        "deterministic_fixture": "tests/unit/features/test_alignment_properties.py::test_secondary_symbol_join_never_uses_a_future_bar",
        "prefix_invariance_test": "same fixture verifies no future-row join; source-clock/publication latency remains unresolved",
        "test_path_candidates": "tests/unit/features/test_alignment_properties.py",
        "evidence_artifact": "docs/research/feature_causality_and_availability.md",
        "evidence_status": "source_and_fixture_reviewed; feed_clock_and_staleness_unresolved",
        "evidence_note": (
            "Backward as-of matching prevents a later timestamp from being selected. It does not prove the matched secondary observation was published by that decision time."
        ),
    },
    (
        "market_data/transforms/resample.py",
        "resample",
    ): {
        "output_features": "OHLCV and spread aggregates for each nonempty left-labeled M1 bin; M1 requests return a copy",
        "source_timeframe": "M1 input to caller-selected target timeframe",
        "source_event_timestamp": "left edge of each resample bin",
        "effective_availability_timestamp": (
            "not produced here; downstream alignment must wait until the bin closes and apply the configured close-time rule"
        ),
        "units": "input OHLCV and spread units; volume is summed and spread averaged when present",
        "lookback_or_state_lifetime": "one resample bin; no cross-bin state",
        "warmup_missingness": "bins without an open are dropped; other aggregates follow pandas first/max/min/last/sum/mean semantics",
        "fit_scope": "not fitted",
        "masked_cases": "only present columns are aggregated; partial bins are retained when an open is present",
        "deterministic_fixture": (
            "tests/unit/features/test_htf_alignment.py::test_htf_columns_present; "
            "tests/unit/features/test_htf_alignment.py::test_htf_alignment_causal_open_time"
        ),
        "prefix_invariance_test": (
            "tests/unit/features/test_htf_alignment.py::test_htf_future_invariance covers the downstream feature pipeline; "
            "not a standalone resampler prefix contract"
        ),
        "test_path_candidates": "tests/unit/features/test_htf_alignment.py",
        "evidence_artifact": "docs/research/feature_causality_and_availability.md",
        "evidence_status": "source_and_pipeline_fixture_reviewed; bin_completeness_and_close_authority_unresolved",
        "evidence_note": (
            "The resampler assigns left labels and aggregates observed rows but does not prove bin completeness or set publication time. "
            "Causal availability depends on downstream close-time alignment and the authoritative feed/session calendar."
        ),
    },
    (
        "market_data/transforms/resample.py",
        "build_all_timeframes",
    ): {
        "output_features": "M1, M3, M5, M10, M15, M30, H1, H4, and D1 OHLCV frames",
        "source_timeframe": "M1 input bars",
        "source_event_timestamp": "inherited left labels from the M1 index and each pandas resample bin",
        "effective_availability_timestamp": (
            "not produced here; each non-M1 frame requires downstream close-time alignment"
        ),
        "units": "inherited OHLCV and spread units",
        "lookback_or_state_lifetime": "one input frame per timeframe; no cross-timeframe state",
        "warmup_missingness": "inherits resample behavior; empty-open bins are omitted and partial bins remain",
        "fit_scope": "not fitted",
        "masked_cases": "all declared TFs are built; unsupported/missing source intervals are not synthesized",
        "deterministic_fixture": "tests/integration/test_resample_m10.py::test_build_all_timeframes_includes_m10",
        "prefix_invariance_test": "not established for all target frames; downstream HTF prefix test is separate",
        "test_path_candidates": "tests/integration/test_resample_m10.py; tests/unit/features/test_htf_alignment.py",
        "evidence_artifact": "evidence/research/feature_causality/feature_causality_matrix.csv",
        "evidence_status": "source_and_fixture_reviewed; downstream_close_and_bin_completeness_open",
        "evidence_note": (
            "This is a deterministic composition of the configured resampler. It does not validate native-frame parity, "
            "input completeness, or source publication time."
        ),
    },
    (
        "market_data/transforms/session_schedule.py",
        "scheduled_session_close_map",
    ): {
        "output_features": "date-to-configured-broker-close-time mapping",
        "source_timeframe": "configured date-indexed session schedule CSV",
        "source_event_timestamp": "session_date and scheduled_ny_close_broker_time values read from the configured file",
        "effective_availability_timestamp": "configuration-time lookup; this function does not emit market-row features",
        "units": "ISO-like date text and broker-time HH:MM text",
        "lookback_or_state_lifetime": "none; mapping is rebuilt from the configured schedule file",
        "warmup_missingness": "no path returns an empty map; configured missing files or columns fail closed",
        "fit_scope": "not fitted",
        "masked_cases": "duplicate dates collapse according to dict construction; file authority and completeness are not checked",
        "deterministic_fixture": "tests/unit/market_data/test_session_schedule.py::test_scheduled_session_close_map_reads_configured_calendar",
        "prefix_invariance_test": "not applicable to a configuration lookup",
        "test_path_candidates": "tests/unit/market_data/test_session_schedule.py",
        "evidence_artifact": "evidence/research/feature_causality/feature_causality_matrix.csv",
        "evidence_status": "source_and_fixture_reviewed; schedule_authority_out_of_scope",
        "evidence_note": (
            "The parser verifies required columns and resolves relative paths. User-directed scope excludes external calendar/provider "
            "authority assessment; no completeness or timezone-parity claim is made."
        ),
    },
    (
        "market_data/transforms/sessions.py",
        "get_session",
    ): {
        "output_features": "one of asia, london, ny, or closed",
        "source_timeframe": "single supplied timestamp",
        "source_event_timestamp": "the timestamp passed by the caller",
        "effective_availability_timestamp": "same timestamp after localization/conversion to the supplied broker timezone",
        "units": "categorical session label",
        "lookback_or_state_lifetime": "none; classification is row-local",
        "warmup_missingness": "none for a parseable timestamp and valid HH:MM close",
        "fit_scope": "not fitted",
        "masked_cases": "naive timestamps localize to tz; aware timestamps convert to tz; out-of-window times are closed",
        "deterministic_fixture": "tests/unit/features/test_session_filter.py::test_get_session_closed_label; tests/unit/features/test_session_levels.py::TestGetSession",
        "prefix_invariance_test": "not applicable to row-local clock classification",
        "test_path_candidates": "tests/unit/features/test_session_filter.py; tests/unit/features/test_session_levels.py",
        "evidence_artifact": "evidence/research/feature_causality/feature_causality_matrix.csv",
        "evidence_status": "source_and_boundary_fixtures_reviewed; timezone_authority_out_of_scope",
        "evidence_note": (
            "The code establishes its configured broker-time windows and inclusive NY close. It does not establish that the input "
            "clock or timezone matches an external exchange calendar."
        ),
    },
    (
        "market_data/transforms/sessions.py",
        "ny_session_mask",
    ): {
        "output_features": "boolean eligibility mask indexed like the input timestamps",
        "source_timeframe": "supplied DatetimeIndex",
        "source_event_timestamp": "each row's unconverted wall-clock time",
        "effective_availability_timestamp": "same input row; the mask reads index.time without timezone conversion",
        "units": "boolean",
        "lookback_or_state_lifetime": "none; row-local inclusive [start, end] comparison",
        "warmup_missingness": "no warmup; empty input yields an empty mask",
        "fit_scope": "not fitted",
        "masked_cases": "timestamps outside the configured inclusive wall-clock window are false",
        "deterministic_fixture": "tests/unit/features/test_session_filter.py::test_trading_mask_separate_from_features",
        "prefix_invariance_test": "not applicable to row-local masking",
        "test_path_candidates": "tests/unit/features/test_session_filter.py",
        "evidence_artifact": "evidence/research/feature_causality/feature_causality_matrix.csv",
        "evidence_status": "source_and_fixture_reviewed; input_clock_authority_out_of_scope",
        "evidence_note": (
            "This is a mask helper; it does not itself alter feature rows. Its wall-clock interpretation follows the supplied index as-is."
        ),
    },
    (
        "market_data/transforms/sessions.py",
        "add_session_labels",
    ): {
        "output_features": "session categorical column with asia, london, ny, or closed values",
        "source_timeframe": "DataFrame DatetimeIndex",
        "source_event_timestamp": "each input index timestamp",
        "effective_availability_timestamp": "same row after localization/conversion to the configured tz",
        "units": "categorical session label",
        "lookback_or_state_lifetime": "none; row-local classification",
        "warmup_missingness": "none for parseable DatetimeIndex and valid HH:MM close",
        "fit_scope": "not fitted",
        "masked_cases": "naive indexes localize to tz; aware indexes convert; labels do not drop rows",
        "deterministic_fixture": "tests/unit/features/test_session_filter.py::test_trading_mask_separate_from_features",
        "prefix_invariance_test": "not applicable to row-local labels",
        "test_path_candidates": "tests/unit/features/test_session_filter.py; tests/unit/features/test_session_tz_pd.py",
        "evidence_artifact": "evidence/research/feature_causality/feature_causality_matrix.csv",
        "evidence_status": "source_and_fixture_reviewed; timezone_authority_out_of_scope",
        "evidence_note": (
            "Labels preserve all feature rows. They establish the configured broker-time classification, not external session-calendar parity."
        ),
    },
    (
        "market_data/transforms/sessions.py",
        "filter_session",
    ): {
        "output_features": "row subset whose index wall-clock time falls inside the inclusive NY window",
        "source_timeframe": "DataFrame DatetimeIndex",
        "source_event_timestamp": "each input row index timestamp",
        "effective_availability_timestamp": "same input row; delegates to ny_session_mask without timezone conversion",
        "units": "filtered DataFrame with original columns and index",
        "lookback_or_state_lifetime": "none; row-local eligibility selection",
        "warmup_missingness": "empty input or no eligible rows returns an empty DataFrame",
        "fit_scope": "not fitted",
        "masked_cases": "drops rows outside the mask; repository invariant forbids using it to build feature datasets",
        "deterministic_fixture": "tests/unit/features/test_session_filter.py::test_session_filter_keeps_only_window; test_feature_pipeline_keeps_non_ny_bars",
        "prefix_invariance_test": "not applicable; direct row selection",
        "test_path_candidates": "tests/unit/features/test_session_filter.py",
        "evidence_artifact": "evidence/research/feature_causality/feature_causality_matrix.csv",
        "evidence_status": "source_and_usage_reviewed; mask_only_pipeline_invariant_preserved",
        "evidence_note": (
            "The utility returns a filtered view-copy, but production feature construction does not call it; eligibility remains mask-only there."
        ),
    },
    (
        "market_data/transforms/sessions.py",
        "add_session_id",
    ): {
        "output_features": "integer session_id column",
        "source_timeframe": "DataFrame DatetimeIndex",
        "source_event_timestamp": "normalized calendar date of each row in the index timezone",
        "effective_availability_timestamp": "same row; ID assignment uses the complete input date set but IDs depend only on sorted dates",
        "units": "integer category, not elapsed time",
        "lookback_or_state_lifetime": "one ID per distinct normalized input date",
        "warmup_missingness": "none for a valid DatetimeIndex",
        "fit_scope": "not fitted",
        "masked_cases": "calendar-date boundaries define IDs; this is not a market-session authority assertion",
        "deterministic_fixture": "tests/unit/features/test_session_filter.py::test_session_id_increments_per_day",
        "prefix_invariance_test": "not explicitly tested; ID numbering can shift if earlier dates are added",
        "test_path_candidates": "tests/unit/features/test_session_filter.py",
        "evidence_artifact": "evidence/research/feature_causality/feature_causality_matrix.csv",
        "evidence_status": "source_and_fixture_reviewed; calendar_timezone_semantics_unresolved",
        "evidence_note": (
            "The same-date membership is causal, but numeric IDs are dataset-relative and the calendar-date reset is not independently validated against market sessions."
        ),
    },
    (
        "features/context/trade_setup_candidates.py",
        "active_trade_setup_candidates",
    ): {
        "output_features": "tuple of candidates whose exact idea/timeframe/direction source column is finite and positive",
        "source_timeframe": "inherited from each named entry_idea source column",
        "source_event_timestamp": "current feature row; originating event time is not carried by this projection",
        "effective_availability_timestamp": "current row after all source columns have been constructed and aligned",
        "units": "candidate records with categorical idea, timeframe, and direction",
        "lookback_or_state_lifetime": "inherits each source feature's event/state lifetime",
        "warmup_missingness": "missing, nonnumeric, nonfinite, zero, or negative values are inactive",
        "fit_scope": "not fitted; deterministic row projection",
        "masked_cases": "absent candidate columns are treated inactive; NO_TRADE is not returned by this helper",
        "deterministic_fixture": "tests/integration/test_trade_setup.py::test_each_entry_idea_has_exact_timeframe_candidate",
        "prefix_invariance_test": "row-local projection; upstream feature-family timing remains separate",
        "test_path_candidates": "tests/integration/test_trade_setup.py; tests/unit/simulation/test_environment/test_trade_setup_observation.py",
        "evidence_artifact": "evidence/research/feature_causality/feature_causality_matrix.csv",
        "evidence_status": "source_and_fixture_reviewed; upstream_event_identity_not_retained",
        "evidence_note": "This projects existing binary source columns and cannot identify the originating event or prove source-clock publication timing.",
    },
    (
        "features/context/trade_setup_candidates.py",
        "trade_setup_candidate_feature_columns",
    ): {
        "output_features": "stable candidate-ID to entry-idea-column mapping for the 108-category action schema",
        "source_timeframe": "one encoded timeframe per candidate column",
        "source_event_timestamp": "none; schema mapping only",
        "effective_availability_timestamp": "configuration/schema construction time",
        "units": "integer category ID and feature-column name",
        "lookback_or_state_lifetime": "none; static candidate catalog projection",
        "warmup_missingness": "none",
        "fit_scope": "not fitted",
        "masked_cases": "NO_TRADE is excluded from the source-column mapping and handled by the mask builder",
        "deterministic_fixture": "tests/integration/test_trade_setup.py::test_candidate_mask_keeps_exact_timeframe_and_direction",
        "prefix_invariance_test": "not applicable to a static mapping",
        "test_path_candidates": "tests/unit/simulation/test_environment/test_trade_setup_factory_config.py; tests/integration/test_trade_setup.py",
        "evidence_artifact": "evidence/research/feature_causality/feature_causality_matrix.csv",
        "evidence_status": "schema_and_fixture_reviewed",
        "evidence_note": "This defines stable schema identity only; it does not establish that every candidate is configured or supported by source semantics.",
    },
    (
        "features/context/trade_setup_candidates.py",
        "trade_setup_candidate_mask",
    ): {
        "output_features": "109-element float32 eligibility mask with NO_TRADE always active",
        "source_timeframe": "inherited from each candidate's exact source feature column",
        "source_event_timestamp": "current feature row; source event identity is not retained",
        "effective_availability_timestamp": "current row after source features have been aligned",
        "units": "binary eligibility indicators",
        "lookback_or_state_lifetime": "inherits candidate source-column lifetimes",
        "warmup_missingness": "inactive/missing candidate values map to zero; NO_TRADE maps to one",
        "fit_scope": "not fitted; deterministic row projection",
        "masked_cases": "only finite positive exact candidate columns become eligible; NO_TRADE remains eligible",
        "deterministic_fixture": "tests/integration/test_trade_setup.py::test_candidate_mask_keeps_exact_timeframe_and_direction",
        "prefix_invariance_test": "row-local projection; upstream feature-family timing remains separate",
        "test_path_candidates": "tests/integration/test_trade_setup.py; tests/unit/simulation/test_environment/test_trade_setup_observation.py",
        "evidence_artifact": "evidence/research/feature_causality/feature_causality_matrix.csv",
        "evidence_status": "source_and_fixture_reviewed; upstream_event_identity_not_retained",
        "evidence_note": "The mask uses the current feature row and exact candidate column. It does not preserve the signal's original event timestamp.",
    },
    (
        "features/context/trade_setup_candidates.py",
        "trade_setup_candidate_event_identities",
    ): {
        "output_features": "versioned source-event identity records for active candidates when all required times resolve",
        "source_timeframe": "candidate setup timeframe plus family-specific source event metadata",
        "source_event_timestamp": "PO3 sweep/reclaim plus same-side IFVG confirmation and selected zone origin (aligned IFVG-zone origin for M1; source-timeframe PO3-state origin for MTF), order-block origin/retest, swing-leg endpoints, FVG retest/origin, or IFVG confirmation/retest/origin timestamps",
        "effective_availability_timestamp": "current feature row; resolver consumes already-aligned metadata and does not change eligibility timing",
        "units": "stable text ID and ordered event timestamps normalized to nanoseconds",
        "lookback_or_state_lifetime": "identity is stable across repeated rows for the same source times; a new event time changes the ID",
        "warmup_missingness": "missing and conflicting times produce explicit unresolved status and no ID",
        "fit_scope": "not fitted; deterministic row projection",
        "masked_cases": "no boolean edge or decision-row timestamp fallback; IFVG unretested uses the selected global confirmation timestamp",
        "deterministic_fixture": "tests/unit/features/test_trade_setup_candidate_events.py; tests/unit/features/test_po3_mtf_state.py",
        "prefix_invariance_test": "row-local resolver; producer feature families retain their separate prefix tests",
        "test_path_candidates": "tests/unit/features/test_trade_setup_candidate_events.py; tests/unit/features/test_build_pipeline.py; tests/unit/features/test_po3_state.py; tests/unit/features/test_order_blocks.py; tests/unit/features/test_po3_mtf_state.py",
        "evidence_artifact": "evidence/research/feature_causality/feature_causality_matrix.csv",
        "evidence_status": "source_identity_linked_to_decision_records_tested; selected_training_profile_identity_coverage_measured; event_cardinality_and_feed_clock_open",
        "evidence_note": "PO3 identity includes the direction-matched IFVG confirmation and selected zone-origin timestamps; M1 uses the shared aligned IFVG-zone origin while MTF uses source-timeframe PO3-state origin. The environment attaches candidate ID/status to the decision record; source times stay out of model tensors and the 109-choice mask is unchanged. The selected training census measures timestamp resolution, not logical event cardinality or feed publication time.",
    },
    (
        "features/context/trade_setup_candidates.py",
        "trade_setup_candidate_event_time_fields",
    ): {
        "output_features": "ordered source timestamp field names and unit scales for a candidate category",
        "source_timeframe": "candidate setup timeframe and family event metadata",
        "source_event_timestamp": "none emitted; returns the canonical timestamp field contract consumed by identity resolution",
        "effective_availability_timestamp": "configuration/schema lookup time",
        "units": "feature column names paired with multipliers converting values to nanoseconds",
        "lookback_or_state_lifetime": "static mapping per candidate category",
        "warmup_missingness": "invalid and NO_TRADE category IDs raise ValueError",
        "fit_scope": "not fitted; deterministic catalog mapping",
        "masked_cases": "catalog mapping alone does not establish a configured or active candidate",
        "deterministic_fixture": "tests/unit/features/test_trade_setup_candidate_events.py::test_candidate_event_time_fields_preserve_source_units_and_order",
        "prefix_invariance_test": "not applicable to a static mapping",
        "test_path_candidates": "tests/unit/features/test_trade_setup_candidate_events.py; tests/research/test_trade_setup_opportunity_census.py",
        "evidence_artifact": "evidence/research/feature_causality/feature_causality_matrix.csv",
        "evidence_status": "source_mapping_and_fixture_tested",
        "evidence_note": "The mapping is reused by row-level identity resolution and vectorized training-census coverage; it does not infer timestamps from boolean flags.",
    },
    (
        "features/context/reachability.py",
        "max_tp_distance",
    ): {
        "output_features": "maximum take-profit price distance from a trailing quantile of completed NY-session ranges",
        "source_timeframe": "input OHLC rows and aligned atr_5 series",
        "source_event_timestamp": "current ATR plus prior completed-session high/low ranges",
        "effective_availability_timestamp": "after the last observed NY-window row for the prior input date; the current date is excluded at its last row",
        "units": "price units",
        "lookback_or_state_lifetime": "expanding completed-session history capped at n_sessions; quantile recalculated when a session completes",
        "warmup_missingness": "NaN until a valid completed session and positive current ATR are available",
        "fit_scope": "not fitted; rolling historical quantile",
        "masked_cases": "uses broker-index wall-clock NY mask; missing/nonpositive ATR and invalid ranges are skipped",
        "deterministic_fixture": "tests/unit/evaluation/test_order_chart.py::test_rr_cap_scales_with_atr_not_a_fixed_point_distance",
        "prefix_invariance_test": "not separately recorded; strictly prior session endpoints are selected by searchsorted",
        "test_path_candidates": "tests/unit/evaluation/test_order_chart.py; tests/unit/features/test_stage_a_observation.py",
        "evidence_artifact": "evidence/research/feature_causality/feature_causality_matrix.csv",
        "evidence_status": "source_and_fixture_reviewed; input_clock_and_session_completeness_open",
        "evidence_note": "The implementation excludes the current row's own session result. It uses the final observed NY-window row as a session endpoint and does not verify missing final bars or calendar authority.",
    },
    (
        "features/context/reachability.py",
        "reachable_r_series",
    ): {
        "output_features": "capped, nonnegative ratio of reachable TP distance to direction-aware structural stop distance",
        "source_timeframe": "input OHLC plus aligned atr_5, PO3 manipulation bounds, and direction/bias features when present",
        "source_event_timestamp": "current bar/features plus prior completed NY-session ranges used by max_tp_distance",
        "effective_availability_timestamp": "current input row, conditional on completed-row semantics and upstream feature availability",
        "units": "dimensionless R multiple capped to [0, 20]",
        "lookback_or_state_lifetime": "inherits max_tp_distance completed-session window; structural risk is row-local",
        "warmup_missingness": "missing distance/risk resolves to zero after nan_to_num; missing required ATR/close returns a zero series",
        "fit_scope": "not fitted",
        "masked_cases": "direction selects long/short risk; neutral direction uses tighter positive side; falls back to ATR when structural risk is absent",
        "deterministic_fixture": "tests/unit/features/test_stage_a_observation.py::test_reachable_r_is_room_over_the_structural_stop",
        "prefix_invariance_test": "inherits max_tp_distance's completed-session restriction; no separate whole-series prefix test listed",
        "test_path_candidates": "tests/unit/features/test_stage_a_observation.py",
        "evidence_artifact": "evidence/research/feature_causality/feature_causality_matrix.csv",
        "evidence_status": "source_and_fixture_reviewed; input_clock_and_session_completeness_open",
        "evidence_note": "The output is a causal context estimate only if source rows and session endpoints are correctly labeled; zero can mean unavailable input as well as no reachable room.",
    },
    (
        "features/context/reachability.py",
        "attach_reachable_r",
    ): {
        "output_features": "reachable_r; optional reachable_r_valid when env.reachable_r_validity_mask is enabled",
        "source_timeframe": "observation index aligned to OHLC and feature inputs",
        "source_event_timestamp": "inherits reachable_r_series row and prior completed-session history",
        "effective_availability_timestamp": "observation row after the source series is constructed",
        "units": "dimensionless R multiple",
        "lookback_or_state_lifetime": "inherits reachable_r_series; the opt-in validity column marks known aligned values",
        "warmup_missingness": "legacy default fills missing values with zero; the opt-in reachable_r_valid column distinguishes unknown values from valid zero",
        "fit_scope": "not fitted",
        "masked_cases": "observation rows reindex the computed series; input/index mismatch can produce zero-filled rows",
        "deterministic_fixture": "tests/unit/features/test_stage_a_observation.py::test_reachable_r_is_room_over_the_structural_stop; tests/unit/features/test_stage_a_observation.py::test_reachable_r_validity_separates_unknown_from_valid_zero",
        "prefix_invariance_test": "inherits reachable_r_series; no separate prefix fixture listed",
        "test_path_candidates": "tests/unit/features/test_stage_a_observation.py; tests/unit/simulation/test_environment/test_env_bundle_builder.py",
        "evidence_artifact": "evidence/research/feature_causality/feature_causality_matrix.csv",
        "evidence_status": "source_and_fixture_reviewed; default_missingness_collapses_to_zero; opt_in_validity_mask_tested",
        "evidence_note": "The default observation schema retains its existing zero fill; the opt-in reachable_r_valid sequence column distinguishes unavailable prior-session range from a valid zero, but the selected historical configs do not enable it.",
    },
    (
        "features/context/reachability.py",
        "rr_reaches",
    ): {
        "output_features": "boolean predicate that the requested reward-risk target fits within a supplied max distance",
        "source_timeframe": "scalar order geometry supplied by the caller",
        "source_event_timestamp": "none; scalar comparison only",
        "effective_availability_timestamp": "order-validation time",
        "units": "price units for entry/stop/distance and dimensionless RR ratio",
        "lookback_or_state_lifetime": "none",
        "warmup_missingness": "nonfinite max distance means no completed session has yet supplied a cap and returns true",
        "fit_scope": "not fitted",
        "masked_cases": "uses absolute entry-stop distance and 1e-9 inclusive tolerance",
        "deterministic_fixture": "tests/unit/evaluation/test_order_chart.py::test_rr_cap_scales_with_atr_not_a_fixed_point_distance",
        "prefix_invariance_test": "not applicable to scalar geometry",
        "test_path_candidates": "tests/integration/backtest/test_entry_levels.py; tests/unit/evaluation/test_order_chart.py",
        "evidence_artifact": "evidence/research/feature_causality/feature_causality_matrix.csv",
        "evidence_status": "source_and_boundary_fixtures_reviewed",
        "evidence_note": "This validates supplied geometry only; the causal provenance of max_distance is established by its producer.",
    },
    (
        "features/context/policy_market.py",
        "build_policy_market_context",
    ): {
        "output_features": "scheduled-session calendar features plus tick quote offsets, spread, age, activity, and availability flags",
        "source_timeframe": "M1 bars with bid/ask ticks in each [bar open, bar end) interval",
        "source_event_timestamp": "current bar close/ATR; scheduled date mapping; latest bid and ask tick strictly before bar end",
        "effective_availability_timestamp": "after the M1 bar interval is complete; tick observations at bar end belong to the next interval",
        "units": "normalized ATR distances, fractions, minutes, log1p tick count, and binary availability",
        "lookback_or_state_lifetime": "row-local quote aggregate and schedule lookup; no forward fill",
        "warmup_missingness": "missing/invalid quote fields become NaN with tick_quote_available=0; schedule defaults to configured session end for absent dates",
        "fit_scope": "not fitted",
        "masked_cases": "bars/features index must match; requires nonempty ticks and schedule columns; invalid or inverted quotes are masked",
        "deterministic_fixture": "tests/unit/features/test_policy_market_context.py::test_short_schedule_is_known_at_first_bar_and_quotes_stop_at_bar_close",
        "prefix_invariance_test": "tests/unit/features/test_policy_market_context.py::test_future_ticks_do_not_change_completed_bar_context",
        "test_path_candidates": "tests/unit/features/test_policy_market_context.py",
        "evidence_artifact": "evidence/research/feature_causality/feature_causality_matrix.csv",
        "evidence_status": "source_and_prefix_fixtures_reviewed; schedule_authority_and_feed_clock_out_of_scope",
        "evidence_note": "Fixtures establish interval and prefix behavior for supplied data. They do not validate external schedule authority, tick publication latency, or provider rights.",
    },
    (
        "features/context/policy_market.py",
        "attach_policy_market_context",
    ): {
        "output_features": "existing feature frame plus collision-checked policy_market_context columns",
        "source_timeframe": "same index as the input M1 bar/feature pair",
        "source_event_timestamp": "inherits build_policy_market_context sources",
        "effective_availability_timestamp": "inherits build_policy_market_context completed-bar boundary",
        "units": "mixed normalized, temporal, and binary policy context",
        "lookback_or_state_lifetime": "row-local; no additional state",
        "warmup_missingness": "inherits context builder; duplicate output columns fail closed",
        "fit_scope": "not fitted",
        "masked_cases": "requires successful context build and no existing columns with the same names",
        "deterministic_fixture": "tests/unit/features/test_policy_market_context.py::test_attach_policy_market_context_preserves_features_and_appends_context; tests/unit/features/test_policy_market_context.py::test_attach_policy_market_context_rejects_duplicate_context_columns",
        "prefix_invariance_test": "inherits tests/unit/features/test_policy_market_context.py::test_future_ticks_do_not_change_completed_bar_context",
        "test_path_candidates": "tests/unit/features/test_policy_market_context.py",
        "evidence_artifact": "evidence/research/feature_causality/feature_causality_matrix.csv",
        "evidence_status": "source_and_adapter_fixtures_reviewed; schedule_authority_and_feed_clock_out_of_scope",
        "evidence_note": "Direct adapter fixtures verify index preservation, unchanged base-feature values, context append, and duplicate-column rejection. Timing, schedule authority, and quote availability inherit the builder's bounded constraints.",
    },
    (
        "features/pipeline/feature_build_inputs.py",
        "split_raw_fvg_features",
    ): {
        "output_features": "normalized/model feature frame and separate copy of matching raw FVG price/flag/origin columns",
        "source_timeframe": "inherited from supplied feature columns",
        "source_event_timestamp": "none added; existing source columns are partitioned without recomputation",
        "effective_availability_timestamp": "unchanged from the supplied feature frame",
        "units": "inherited column units; raw FVG levels remain price/timestamp values",
        "lookback_or_state_lifetime": "none; column selection only",
        "warmup_missingness": "missing values remain unchanged; if no columns match, returns the input frame and an empty aligned frame",
        "fit_scope": "not fitted",
        "masked_cases": "matches known raw FVG suffixes only; unlisted columns remain in the feature frame",
        "deterministic_fixture": "tests/unit/features/test_feature_build_inputs.py::test_split_raw_fvg_features_keeps_model_features_separate",
        "prefix_invariance_test": "not applicable to column partitioning",
        "test_path_candidates": "tests/unit/features/test_feature_build_inputs.py",
        "evidence_artifact": "evidence/research/feature_causality/feature_causality_matrix.csv",
        "evidence_status": "source_and_fixture_reviewed; upstream_feature_timing_inherited",
        "evidence_note": "This helper avoids exposing raw zone geometry in normalized inputs but does not validate the timing of the original FVG columns.",
    },
    (
        "features/pipeline/feature_build_inputs.py",
        "configured_feature_timeframes",
    ): {
        "output_features": "ordered list of timeframe labels from nested or legacy flat configuration, with fallback defaults",
        "source_timeframe": "not a market-data transform",
        "source_event_timestamp": "none",
        "effective_availability_timestamp": "configuration-resolution time",
        "units": "timeframe label strings",
        "lookback_or_state_lifetime": "none",
        "warmup_missingness": "missing or empty values use the declared defaults",
        "fit_scope": "not fitted",
        "masked_cases": "nested timeframes take precedence over a flat key",
        "deterministic_fixture": "tests/unit/features/test_feature_build_inputs.py::test_configured_feature_timeframes_supports_nested_and_flat_config",
        "prefix_invariance_test": "not applicable to configuration resolution",
        "test_path_candidates": "tests/unit/features/test_feature_build_inputs.py",
        "evidence_artifact": "evidence/research/feature_causality/feature_causality_matrix.csv",
        "evidence_status": "source_and_fixture_reviewed",
        "evidence_note": "This resolves which source bars a builder requests; it does not establish native/derived bar parity.",
    },
    (
        "features/pipeline/feature_build_inputs.py",
        "feature_block_enabled",
    ): {
        "output_features": "boolean block activation selected from nested or legacy flat configuration",
        "source_timeframe": "not a market-data transform",
        "source_event_timestamp": "none",
        "effective_availability_timestamp": "configuration-resolution time",
        "units": "boolean",
        "lookback_or_state_lifetime": "none",
        "warmup_missingness": "missing feature config uses the supplied default",
        "fit_scope": "not fitted",
        "masked_cases": "nested enabled flag takes precedence over the flat legacy flag",
        "deterministic_fixture": "tests/unit/features/test_feature_build_inputs.py::test_feature_block_enabled_prefers_nested_then_flat_configuration",
        "prefix_invariance_test": "not applicable to configuration resolution",
        "test_path_candidates": "tests/unit/features/test_feature_build_inputs.py",
        "evidence_artifact": "evidence/research/feature_causality/feature_causality_matrix.csv",
        "evidence_status": "source_and_fixture_reviewed",
        "evidence_note": "This is a deterministic configuration gate; unsupported source features remain a separate matrix status.",
    },
    (
        "features/pipeline/feature_build_inputs.py",
        "resample_market_pair",
    ): {
        "output_features": "primary and optional secondary bar frames from exact-timeframe native frames or independent M1 resampling",
        "source_timeframe": "requested timeframe, selected independently for each instrument",
        "source_event_timestamp": "inherited from supplied native frame or resample bin labels",
        "effective_availability_timestamp": "not assigned here; downstream alignment owns completed-bar availability",
        "units": "input OHLCV and spread units",
        "lookback_or_state_lifetime": "one frame per requested timeframe; no cross-frame state",
        "warmup_missingness": "empty/missing secondary remains None; missing requested native frame is resampled from M1",
        "fit_scope": "not fitted",
        "masked_cases": "native input wins when present; native-vs-derived parity is not checked here",
        "deterministic_fixture": "tests/unit/features/test_feature_build_inputs.py::test_resample_market_pair_uses_native_per_symbol_and_derives_missing_frame",
        "prefix_invariance_test": "not applicable to source selection; resampling/alignment tests are separate",
        "test_path_candidates": "tests/unit/features/test_feature_build_inputs.py; tests/unit/features/test_htf_alignment.py",
        "evidence_artifact": "evidence/research/feature_causality/feature_causality_matrix.csv",
        "evidence_status": "source_and_fixture_reviewed; native_derived_parity_open",
        "evidence_note": "The helper makes source selection explicit but does not establish that a supplied native frame equals the same-timeframe M1 resample.",
    },
    (
        "features/pipeline/feature_build_inputs.py",
        "source_timeframe_training_mask",
    ): {
        "output_features": "boolean source-frame mask whose availability timestamp is at or before the final selected M1 training row",
        "source_timeframe": "source bar timeframe plus primary M1 split mask",
        "source_event_timestamp": "source bar open/index and configured close-time mapping",
        "effective_availability_timestamp": "timeframe_close_times result compared to the maximum M1 train-row timestamp",
        "units": "boolean fit-membership mask",
        "lookback_or_state_lifetime": "one source bar close boundary per row",
        "warmup_missingness": "None train mask propagates None; empty train membership returns all false",
        "fit_scope": "limits higher-timeframe fitting rows to source candles already closed by the M1 train cutoff",
        "masked_cases": "rows with missing primary train-mask values are false; scheduled close semantics inherit the supplied schedule",
        "deterministic_fixture": "tests/unit/features/test_feature_build_inputs.py::test_source_timeframe_training_mask_excludes_unclosed_source_bars; test_source_timeframe_training_mask_handles_missing_train_rows",
        "prefix_invariance_test": "boundary fixtures establish close-before-cutoff membership; full per-fold source coverage remains separate",
        "test_path_candidates": "tests/unit/features/test_feature_build_inputs.py; tests/unit/features/test_feature_cache_and_fit_scope.py",
        "evidence_artifact": "evidence/research/feature_causality/feature_causality_matrix.csv",
        "evidence_status": "source_and_fit_boundary_fixtures_reviewed; schedule_authority_out_of_scope",
        "evidence_note": "The comparison is fail-closed at the configured close timestamp. It inherits timestamp and schedule meaning from its inputs and does not validate external authority.",
    },
    (
        "features/pipeline/session_stage.py",
        "append_session_features",
    ): {
        "output_features": "configured running-session OHLC/VWAP, completed prior-period/session levels, and range quadrants",
        "source_timeframe": "primary OHLC/activity rows, grouped by configured wall-clock session windows and date/week periods",
        "source_event_timestamp": "current input rows for running sessions; only prior completed period/session rows for lagged levels",
        "effective_availability_timestamp": "current row for running session features; first later source row after each completed period for prior levels",
        "units": "price levels, categorical/time labels, and price-relative quadrant distances",
        "lookback_or_state_lifetime": "within-session accumulation; previous day/week/NY session carried forward",
        "warmup_missingness": "requires feature config; missing activity/session IDs suppress optional VWAP; prior-period levels warm up after a completed period",
        "fit_scope": "not fitted",
        "masked_cases": "session OHLC/VWAP and previous-session PD are independently configured; labels use configured clock model/timezone",
        "deterministic_fixture": "tests/unit/features/test_session_levels.py; tests/unit/features/test_session_ohlc.py; tests/unit/features/test_session_tz_pd.py",
        "prefix_invariance_test": "source tests cover session boundaries and prior-period shift; full caller/configuration coverage remains open",
        "test_path_candidates": "tests/unit/features/test_session_levels.py; tests/unit/features/test_session_ohlc.py; tests/unit/features/test_session_tz_pd.py",
        "evidence_artifact": "evidence/research/feature_causality/feature_causality_matrix.csv",
        "evidence_status": "source_and_fixture_reviewed; configured_clock_authority_out_of_scope",
        "evidence_note": "The stage composes reviewed helpers and uses only current or completed prior periods. Session timezone/calendar interpretation is inherited from local configuration.",
    },
    (
        "features/pipeline/structure_stage.py",
        "append_structure_features",
    ): {
        "output_features": "M1 swing/structure history plus optional timeframe-specific structure levels and BOS flags",
        "source_timeframe": "primary M1 plus configured MTF source bars derived/selected by resample_pair",
        "source_event_timestamp": "current M1 structure state and confirmed source-timeframe pivots/BOS events",
        "effective_availability_timestamp": "M1 structure row; MTF blocks become visible according to injected align_blocks policy",
        "units": "price levels, event flags, timestamps, and integer-like bar ages",
        "lookback_or_state_lifetime": "swing confirmation window; structure levels persist until replaced by newer confirmed state",
        "warmup_missingness": "feature config absent returns unchanged features; unconfirmed levels remain missing; empty MTF frames are skipped",
        "fit_scope": "not fitted",
        "masked_cases": "MTF activation and timeframe selection are config-controlled; candidate count is restricted to 1..3",
        "deterministic_fixture": "tests/unit/features/test_structure.py; tests/unit/features/test_pivots_swings.py; tests/unit/features/test_htf_alignment.py",
        "prefix_invariance_test": "individual source tests cover pivot/structure and HTF alignment; injected caller coverage remains open",
        "test_path_candidates": "tests/unit/features/test_structure.py; tests/unit/features/test_pivots_swings.py; tests/unit/features/test_htf_alignment.py",
        "evidence_artifact": "evidence/research/feature_causality/feature_causality_matrix.csv",
        "evidence_status": "source_and_fixture_reviewed; injected_mtf_availability_policy_must_match",
        "evidence_note": "M1 and MTF producer outputs are composed here; causal availability of injected MTF alignment and source candle clocks remains a separate gate.",
    },
    (
        "features/pipeline/po3_stage.py",
        "append_po3_state_features",
    ): {
        "output_features": "configured sweep, BOS, PO3/IFVG zone/state, confirmation, MTF post-IFVG distribution readiness, and aligned MTF IFVG context",
        "source_timeframe": "primary M1 plus configured MTF source bars",
        "source_event_timestamp": "current/past sweeps and BOS, close-through IFVG confirmation, and later state transitions",
        "effective_availability_timestamp": "M1 current-row close for M1 states; configured source-timeframe close boundary for aligned MTF PO3 and IFVG blocks",
        "units": "binary state/event flags, price-zone bounds, directions, and bar-age values",
        "lookback_or_state_lifetime": "stateful PO3/IFVG lifecycle with configured IFVG age; active zone and confirmation state persist per producer contract",
        "warmup_missingness": "feature config absent or strategy state disabled returns unchanged features; invalid phase/reference modes raise",
        "fit_scope": "not fitted",
        "masked_cases": "phase mode, reference mode, MTF enablement, and timeframe lists are config-controlled",
        "deterministic_fixture": "tests/unit/features/test_po3_state.py; tests/unit/features/test_po3_ifvg_state.py; tests/unit/features/test_po3_config.py; tests/unit/features/test_po3_mtf_state.py",
        "prefix_invariance_test": "tests/unit/features/test_assembled_causality.py::test_assembled_matrix_truncation_causality with include_strategy_state enabled; tests/unit/features/test_po3_ifvg_state.py::test_revised_state_is_prefix_causal; tests/unit/features/test_po3_mtf_state.py",
        "test_path_candidates": "tests/unit/features/test_po3_state.py; tests/unit/features/test_po3_ifvg_state.py; tests/unit/features/test_po3_config.py; tests/unit/features/test_assembled_causality.py; tests/unit/features/test_po3_mtf_state.py; tests/unit/features/test_variants.py::test_po3_state_mtf_behind_flag",
        "evidence_artifact": "evidence/research/feature_causality/feature_causality_matrix.csv",
        "evidence_status": "source_and_assembled_prefix_tested; MTF_synthetic_availability_tested; feed_clock_and_unselected_configurations_open",
        "evidence_note": "The MTF PO3 builder now computes post-IFVG readiness on each source timeframe before close-time alignment in both phase modes. Synthetic M5 tests establish close-boundary availability and prefix invariance; they do not establish external feed publication time or all timeframe/configuration combinations.",
    },
    (
        "features/po3/ifvg_detection.py",
        "detect_ifvg_confirmation",
    ): {
        "output_features": "bull/bear IFVG confirmation pulses, zone bounds, positional FVG-origin bars, and source-origin timestamps in the assembled zone state",
        "source_timeframe": "input OHLC and FVG rows on the same index",
        "source_event_timestamp": "FVG origin row, a later zone-pass wick row, and a still-later qualifying close row",
        "effective_availability_timestamp": "qualifying completed input-bar close; confirmation requires i > pass_bar",
        "units": "binary pulses, price bounds, and integer-like row positions",
        "lookback_or_state_lifetime": "active FVG state expires at 50 bars; pass extreme and last pass-bar retained until confirm/expiry; newest same-row confirmation wins the scalar output",
        "warmup_missingness": "no zones before FVG rows; zone bounds/origins are NaN when no confirmation occurs",
        "fit_scope": "not fitted",
        "masked_cases": "zero-size gaps cannot confirm; optional inversion chooses opposing FVG orientation; close-through buffer is configurable",
        "deterministic_fixture": "tests/unit/features/test_po3_config.py::TestIFVGConfirmationBehavior.test_bullish_ifvg_fires_on_close_through; test_zero_threshold_still_requires_strictly_beyond_far_edge",
        "prefix_invariance_test": "tests/unit/features/test_po3_config.py::TestIFVGConfirmationBehavior; direct full/prefix comparison not listed",
        "test_path_candidates": "tests/unit/features/test_po3_config.py",
        "evidence_artifact": "evidence/research/feature_causality/feature_causality_matrix.csv",
        "evidence_status": "source_and_boundary_fixtures_reviewed; source_clock_and_positional_identity_limits",
        "evidence_note": "The detector retains the selected FVG origin as a row offset. The assembled state converts it to a source timestamp; same-row collisions still retain only the newest matching gap.",
    },
    (
        "features/po3/ifvg_state.py",
        "build_po3_ifvg_state",
    ): {
        "output_features": "sweep/manipulation/reclaim/wait/IFVG/distribution state, setup IDs, and source timestamp/zone provenance fields",
        "source_timeframe": "aligned bar, sweep, and IFVG rows",
        "source_event_timestamp": "sweep row plus producer-supplied pivot/confirmation time, reclaim row, IFVG confirmation row, and FVG origin row",
        "effective_availability_timestamp": "current completed input row; distribution_after_ifvg becomes active only after the IFVG confirmation row",
        "units": "binary state flags, direction codes, price levels, nanosecond timestamps, and row offsets",
        "lookback_or_state_lifetime": "one active setup; fresh sweep replaces state; associated IFVG age is bounded by max_ifvg_age_bars",
        "warmup_missingness": "idle state is zero; unavailable event timestamps and levels are NaN",
        "fit_scope": "not fitted",
        "masked_cases": "conflicting simultaneous high/low sweep is recorded and does not start either side; IFVG origin must not precede sweep",
        "deterministic_fixture": "tests/unit/features/test_po3_ifvg_state.py::test_reclaim_waits_for_associated_ifvg_then_starts_distribution; test_fvg_origin_before_setup_is_not_accepted",
        "prefix_invariance_test": "tests/unit/features/test_po3_ifvg_state.py::test_revised_state_is_prefix_causal",
        "test_path_candidates": "tests/unit/features/test_po3_ifvg_state.py",
        "evidence_artifact": "evidence/research/feature_causality/feature_causality_matrix.csv",
        "evidence_status": "source_and_prefix_fixtures_reviewed; inherited_sweep_and_feed_clock_limits",
        "evidence_note": "The state machine retains event provenance for these inputs. Timestamp meaning and availability remain inherited from upstream bars and sweep/IFVG producers.",
    },
    (
        "features/po3/setup_lifecycle.py",
        "build_po3_setup_lifecycle_ledger",
    ): {
        "output_features": "diagnostic lifecycle rows for accepted PO3 producer setup sequences and separate same-bar sweep conflicts",
        "source_timeframe": "the index and timeframe of the supplied PO3 state frame",
        "source_event_timestamp": "producer-retained sweep, reclaim, IFVG confirmation, and FVG-origin timestamps",
        "effective_availability_timestamp": "the lifecycle summary is available only through the last observed completed state row; input-end is a censoring boundary",
        "units": "local producer setup sequence IDs, row positions, directions, prices, and inherited source timestamps",
        "lookback_or_state_lifetime": "one record per state-machine setup until a later accepted sweep replaces it or the input ends",
        "warmup_missingness": "no records before accepted sweep events; ambiguous producer states fail closed",
        "fit_scope": "not fitted",
        "masked_cases": "conflicting simultaneous sweeps are separate rejected records and do not start setup sequences",
        "deterministic_fixture": "tests/unit/features/test_po3_setup_lifecycle.py::test_ledger_records_phase_transitions_rearm_and_conflict_separately; test_ledger_extracts_reclaim_and_conflict_from_producer_output",
        "prefix_invariance_test": "tests/unit/features/test_po3_setup_lifecycle.py::test_finalized_setup_lifecycle_is_prefix_invariant",
        "test_path_candidates": "tests/unit/features/test_po3_setup_lifecycle.py",
        "evidence_artifact": "evidence/research/feature_causality/feature_causality_matrix.csv",
        "evidence_status": "synthetic_projection_tested; logical_event_cardinality_and_source_clock_not_established",
        "evidence_note": "This is a diagnostic projection of the current single-active-setup state machine. It does not identify concurrent latent setups, policy proposals, trades, or a ground-truth event ontology.",
    },
    (
        "features/po3/po3_phase_state.py",
        "build_po3_state",
    ): {
        "output_features": "legacy PO3 manipulation/distribution flags, direction, and running manipulation bounds",
        "source_timeframe": "input OHLC, sweep events, and optional Asian level rows on the same positions",
        "source_event_timestamp": "current sweep row and current/past manipulation leg bars",
        "effective_availability_timestamp": "current completed input row; distribution begins on the first close beyond the prior running manipulation extreme",
        "units": "binary state flags, direction codes, and price levels",
        "lookback_or_state_lifetime": "state persists through distribution until a new qualifying sweep re-arms it",
        "warmup_missingness": "no state until a qualifying sweep; unavailable manipulation levels are NaN",
        "fit_scope": "not fitted",
        "masked_cases": "when Asian levels are supplied, both must be nonmissing; their numerical values are not used as thresholds",
        "deterministic_fixture": "tests/unit/features/test_po3_state.py::TestPO3StateLong.test_manipulation_end_and_distribution; TestPO3StateGuards.test_no_state_without_asian_context",
        "prefix_invariance_test": "tests/unit/features/test_po3_state.py::TestPO3StateGuards.test_causality",
        "test_path_candidates": "tests/unit/features/test_po3_state.py",
        "evidence_artifact": "evidence/research/feature_causality/feature_causality_matrix.csv",
        "evidence_status": "source_and_prefix_fixtures_reviewed; asian_context_is_availability_gate_only",
        "evidence_note": "This legacy state implementation gates on the availability of Asian high/low values but does not compare price with those values; its source sweep timing remains upstream-dependent.",
    },
    (
        "features/po3/po3_phase_state.py",
        "build_distribution_after_ifvg",
    ): {
        "output_features": "binary distribution-after-IFVG eligibility sequence",
        "source_timeframe": "aligned per-row distribution, manipulation, and IFVG confirmation arrays",
        "source_event_timestamp": "matching-side IFVG confirmation followed by same-leg distribution rows",
        "effective_availability_timestamp": "confirmation row arms pending state; output starts on a later row if the leg remains active",
        "units": "binary state flag",
        "lookback_or_state_lifetime": "arm persists within the active directional setup; new setup or idle clears it",
        "warmup_missingness": "zero while idle or before the matching confirmation",
        "fit_scope": "not fitted",
        "masked_cases": "only matching directional confirmation arms; opposite confirmation is ignored",
        "deterministic_fixture": "tests/unit/features/test_po3_state.py::test_distribution_arms_the_bar_after_the_opposing_gap_fails",
        "prefix_invariance_test": "state is row-forward only; no dedicated prefix comparison listed",
        "test_path_candidates": "tests/unit/features/test_po3_state.py",
        "evidence_artifact": "evidence/research/feature_causality/feature_causality_matrix.csv",
        "evidence_status": "source_and_boundary_fixture_reviewed",
        "evidence_note": "The helper enforces post-confirmation ordering but inherits correctness and timing of its input state arrays.",
    },
    (
        "features/po3/po3_phase_state.py",
        "build_ifvg_zone_features",
    ): {
        "output_features": "active IFVG zone bounds/age, price relation, positional and timestamp FVG-origin metadata, confirmation pulse, and later retest-confirmation pulse",
        "source_timeframe": "input OHLC rows and internally detected FVG/IFVG on the same timeframe",
        "source_event_timestamp": "FVG origin, close-through IFVG confirmation, zone departure, later retest, and later confirming close",
        "effective_availability_timestamp": "current completed bar; IFVG becomes active on confirmation, retest flag only after a later qualifying close",
        "units": "binary flags, price levels, ATR-normalized distance, row ages, and origin row indices/prices",
        "lookback_or_state_lifetime": "latest confirmed zone per side; expires at max_age_bars or close-through invalidation",
        "warmup_missingness": "no active zone starts with distance sentinel 5 and age -1; zone/source values are NaN when absent",
        "fit_scope": "not fitted",
        "masked_cases": "zone requires departure before retest; intrabar touch alone is not confirmation; ATR falls back to 1 when unavailable",
        "deterministic_fixture": "tests/unit/features/test_po3_state.py::TestIFVGZones.test_holding_retest_is_not_a_close_inside_the_gap; test_fill_ends_the_zone",
        "prefix_invariance_test": "tests/unit/features/test_po3_state.py::TestIFVGZones.test_causality",
        "test_path_candidates": "tests/unit/features/test_po3_state.py; tests/unit/features/test_po3_ifvg_state.py",
        "evidence_artifact": "evidence/research/feature_causality/feature_causality_matrix.csv",
        "evidence_status": "source_and_prefix_fixtures_reviewed; selected_origin_identity_tested; full_overlap_cardinality_open",
        "evidence_note": "The producer distinguishes close-through confirmation from later retest confirmation and retains the selected gap's source time. Only the newest same-row confirmation is kept by the scalar state; other colliding zones remain outside the model category.",
    },
    (
        "features/po3/po3_phase_state.py",
        "align_ifvg_zone_timeframes",
    ): {
        "output_features": "M1-aligned HTF active-zone fields and merged confirmation pulses with timeframe codes",
        "source_timeframe": "primary M1 plus supplied higher timeframe bars/zone features",
        "source_event_timestamp": "source confirmation row and source timeframe availability timestamp; origin row is translated to the M1 spine",
        "effective_availability_timestamp": "first primary index at or after explicit close time; without explicit closes, one source row is shifted",
        "units": "binary pulses, price-zone values, timeframe-minute codes, and M1-relative row indices",
        "lookback_or_state_lifetime": "active zone values forward-fill from eligible availability; confirmation pulses are sparse",
        "warmup_missingness": "primary zones must share the primary bar index; per-timeframe bars/zones must also match",
        "fit_scope": "not fitted",
        "masked_cases": "M1 confirmation has priority; collisions among higher frames resolve by mapping order; unknown timeframe codes raise",
        "deterministic_fixture": "tests/unit/features/test_po3_state.py::test_configured_ifvg_timeframes_align_and_merge_causally",
        "prefix_invariance_test": "the same fixture checks event visibility against explicit close boundaries; broader irregular-gap coverage remains open",
        "test_path_candidates": "tests/unit/features/test_po3_state.py; tests/unit/features/test_po3_config.py",
        "evidence_artifact": "evidence/research/feature_causality/feature_causality_matrix.csv",
        "evidence_status": "source_and_boundary_fixture_reviewed; close_times_inherit_configured_clock",
        "evidence_note": "Production composition supplies close-time series; the fallback shift path and configured schedule authority remain separate limitations.",
    },
    (
        "features/pipeline/feature_cache_identity.py",
        "feature_cache_content_hash",
    ): {
        "output_features": "16-hex digest over feature version/config, selected source data and indices, timeframes, schedule file, normalization mode, and train mask",
        "source_timeframe": "primary/secondary source bars and any supplied per-timeframe bars",
        "source_event_timestamp": "all hashed source indices and schedule-file bytes",
        "effective_availability_timestamp": "cache-identity construction time; no feature values emitted",
        "units": "hexadecimal content identity",
        "lookback_or_state_lifetime": "none; complete supplied source frames and mask are hashed",
        "warmup_missingness": "None inputs are explicitly tagged; absent optional columns are simply not included",
        "fit_scope": "normalization mode and train-mask values participate in identity",
        "masked_cases": "feature config and select OHLCV/activity columns are included; unrelated DataFrame columns are not hashed",
        "deterministic_fixture": "tests/unit/features/test_cache_hash_full_column.py::test_identical_data_gives_identical_digest; test_mid_series_change_changes_digest",
        "prefix_invariance_test": "not applicable to identity hashing; train-mask changes are regression-tested",
        "test_path_candidates": "tests/unit/features/test_cache_hash_full_column.py; tests/unit/features/test_feature_cache_and_fit_scope.py",
        "evidence_artifact": "evidence/research/feature_causality/feature_causality_matrix.csv",
        "evidence_status": "source_and_content_identity_fixtures_reviewed; selected_column_hash_scope_explicit",
        "evidence_note": "The digest includes source identity fields and configured feature semantics but hashes a selected data-column set rather than every arbitrary input column.",
    },
    (
        "features/pipeline/feature_cache_identity.py",
        "feature_cache_path",
    ): {
        "output_features": "cache path keyed by symbol, feature-cache version, and feature_cache_content_hash",
        "source_timeframe": "inherits primary, secondary, and optional timeframe inputs supplied to the hash function",
        "source_event_timestamp": "inherits hashed source indices",
        "effective_availability_timestamp": "path construction time",
        "units": "filesystem path ending in parquet",
        "lookback_or_state_lifetime": "none",
        "warmup_missingness": "none; hash helper tags absent optional inputs",
        "fit_scope": "train mask and normalization mode are part of the path identity",
        "masked_cases": "cache version is explicit; cache reads/writes and sidecar atomicity are owned by callers",
        "deterministic_fixture": "tests/unit/features/test_feature_cache_and_fit_scope.py::test_cache_hash_changes_when_feature_flag_flips; test_fold_cache_separates_normalization_conventions",
        "prefix_invariance_test": "not applicable to path construction",
        "test_path_candidates": "tests/unit/features/test_feature_cache_and_fit_scope.py; tests/unit/features/test_cache_hash_full_column.py",
        "evidence_artifact": "evidence/research/feature_causality/feature_causality_matrix.csv",
        "evidence_status": "source_and_cache_identity_fixtures_reviewed",
        "evidence_note": "A changed source/config/fit convention selects a different path; this does not validate the contents of an already existing cache file.",
    },
    (
        "features/pipeline/walkforward_feature_fitting.py",
        "build_walkforward_fold_features",
    ): {
        "output_features": "train and validation feature slices rebuilt through validation end with a fold-specific content-addressed cache path",
        "source_timeframe": "primary M1 bars and optional secondary source bars through the final validation row",
        "source_event_timestamp": "source feature history through validation end; no later rows passed to build_features",
        "effective_availability_timestamp": "per-feature causal availability; fitted normalizer is forward-filled from train-only statistics",
        "units": "feature values in the configured pipeline schema",
        "lookback_or_state_lifetime": "technical features keep causal pre-fold warm-up history; normalization uses only fold train observations",
        "warmup_missingness": "empty bars, unordered bars, empty split, overlap, or train after validation raise",
        "fit_scope": "train-only mask is passed with normalization_mode=frozen_fold; validation rows are excluded from fitting",
        "masked_cases": "train and validation indexes must be ordered, present, and disjoint",
        "deterministic_fixture": "tests/unit/features/test_feature_cache_and_fit_scope.py::test_walkforward_fold_rebuilds_using_only_fold_train_fit",
        "prefix_invariance_test": "tests/unit/features/test_feature_cache_and_fit_scope.py::test_walkforward_fold_rebuilds_using_only_fold_train_fit; tests/unit/features/test_assembled_causality.py::test_assembled_matrix_truncation_causality",
        "test_path_candidates": "tests/unit/features/test_feature_cache_and_fit_scope.py; tests/unit/features/test_fold_normalize.py; tests/unit/features/test_assembled_causality.py",
        "evidence_artifact": "evidence/research/feature_causality/feature_causality_matrix.csv",
        "evidence_status": "source_fold_fit_and_selected_prefix_tested; exhaustive_feature_configurations_open",
        "evidence_note": "The fold isolation test proves later rows after validation cannot change earlier fold train/validation features or cache identity. The assembled prefix property covers one selected configuration; exhaustive per-family and configuration coverage remains open.",
    },
    (
        "features/input_view.py",
        "input_view_from_frame",
    ): {
        "output_features": "InputView values selected and ordered by the declared InputSchema columns",
        "source_timeframe": "inherited from the supplied DataFrame rows",
        "source_event_timestamp": "input row index is not carried into the InputView values",
        "effective_availability_timestamp": "view construction time; no feature timing is added",
        "units": "float values with units inherited from schema columns",
        "lookback_or_state_lifetime": "none; row/column projection only",
        "warmup_missingness": "missing declared columns raise; values are converted to float without imputation",
        "fit_scope": "not fitted",
        "masked_cases": "extra source columns are ignored; declared column order is preserved",
        "deterministic_fixture": "tests/unit/market_data/test_input_view_contract.py",
        "prefix_invariance_test": "not applicable to input projection",
        "test_path_candidates": "tests/unit/market_data/test_input_view_contract.py; tests/unit/features/test_build_pipeline.py",
        "evidence_artifact": "evidence/research/feature_causality/feature_causality_matrix.csv",
        "evidence_status": "source_and_schema_fixture_reviewed; numeric_missingness_is_not_validated_here",
        "evidence_note": "The adapter enforces declared names/order but does not validate finite values, source timing, or feature meaning.",
    },
    (
        "features/pipeline/schema.py",
        "select_legacy_obs_columns",
    ): {
        "output_features": "numeric feature columns after explicitly supplied raw prices and known MTF raw price-level columns are dropped",
        "source_timeframe": "inherited from input feature columns",
        "source_event_timestamp": "none added; column selection only",
        "effective_availability_timestamp": "unchanged from selected source columns",
        "units": "inherited units; only numeric columns are retained",
        "lookback_or_state_lifetime": "none",
        "warmup_missingness": "NaN/inf values are not imputed or removed here",
        "fit_scope": "not fitted",
        "masked_cases": "uses explicit raw columns and MTF_RAW_SUFFIXES; legacy path retains some absolute metadata for replay compatibility",
        "deterministic_fixture": "tests/unit/features/test_build_pipeline.py::test_absolute_event_metadata_is_not_exposed_as_model_features",
        "prefix_invariance_test": "not applicable to schema filtering",
        "test_path_candidates": "tests/unit/features/test_build_pipeline.py; tests/unit/simulation/test_environment/test_observation_schema.py",
        "evidence_artifact": "evidence/research/feature_causality/feature_causality_matrix.csv",
        "evidence_status": "source_and_schema_fixtures_reviewed; legacy_metadata_behavior_retained",
        "evidence_note": "This preserves the explicitly legacy observation view; use select_obs_columns for the current schema metadata exclusions.",
    },
    (
        "features/pipeline/schema.py",
        "select_obs_columns",
    ): {
        "output_features": "numeric model columns with configured raw price fields and absolute timestamp/row-ID metadata removed",
        "source_timeframe": "inherited from input feature columns",
        "source_event_timestamp": "none added; column selection only",
        "effective_availability_timestamp": "unchanged from selected source columns",
        "units": "inherited units; relative duration/age fields remain eligible",
        "lookback_or_state_lifetime": "none",
        "warmup_missingness": "NaN/inf values are not imputed or removed here",
        "fit_scope": "not fitted",
        "masked_cases": "absolute ns/ms timestamps and origin/setup IDs are removed by suffix; declared raw price columns remain excluded",
        "deterministic_fixture": "tests/unit/features/test_build_pipeline.py::test_absolute_event_metadata_is_not_exposed_as_model_features",
        "prefix_invariance_test": "not applicable to schema filtering",
        "test_path_candidates": "tests/unit/features/test_build_pipeline.py; tests/unit/simulation/test_environment/test_observation_schema.py",
        "evidence_artifact": "evidence/research/feature_causality/feature_causality_matrix.csv",
        "evidence_status": "source_and_schema_fixtures_reviewed",
        "evidence_note": "This prevents absolute timestamp/ID values from becoming model inputs while keeping relative-age features; upstream feature timing remains separate.",
    },
    (
        "features/pipeline/feature_matrix_builder.py",
        "build_features",
    ): {
        "output_features": "configured indicator, MTF, session, structure, SMT, PO3/IFVG, order-block, context, and setup-flag matrix",
        "source_timeframe": "primary M1 plus configuration-selected native/resampled MTF bars and optional secondary-symbol bars",
        "source_event_timestamp": "inherited from each producer; MTF blocks use timeframe_close_times before alignment",
        "effective_availability_timestamp": "M1 row for M1 producers; first M1 row at/after configured source close for aligned MTF producers",
        "units": "mixed normalized indicators, categorical/binary flags, and explicitly preserved raw structural metadata",
        "lookback_or_state_lifetime": "inherits per-family producer windows and state machines; cached output is keyed by source/config/fit identity",
        "warmup_missingness": "cache hits require matching identity hash; output drops all-NaN rows but otherwise preserves producer missingness",
        "fit_scope": "rolling_zscore receives the supplied train mask; D1-on-source mode constructs source-timeframe training membership",
        "masked_cases": "feature blocks and timeframe lists are config-gated; source/event IDs and exact publication clocks are not uniformly retained",
        "deterministic_fixture": "tests/unit/features/test_build_pipeline.py::TestBuildFeaturesPipeline.test_pipeline_produces_frame; tests/unit/features/test_htf_alignment.py::test_htf_future_invariance",
        "prefix_invariance_test": "tests/unit/features/test_htf_alignment.py::test_htf_future_invariance; selected real-market prefix report covers selected profiles only",
        "test_path_candidates": "tests/unit/features/test_build_pipeline.py; tests/unit/features/test_htf_alignment.py; tests/unit/features/test_feature_cache_and_fit_scope.py",
        "evidence_artifact": "evidence/research/feature_causality/feature_causality_matrix.csv",
        "evidence_status": "source_and_selected_profile_fixtures_reviewed; exhaustive_config_and_event_identity_open",
        "evidence_note": "The builder uses explicit completed-time alignment for configured HTFs. Per-family causality, native-derived parity, all config combinations, event cardinality, and source-time identity outside the selected training profile remain separate acceptance gates.",
    },
    (
        "features/technical/structure.py",
        "structure_levels",
    ): {
        "output_features": "confirmed zigzag swing high/low levels, retained unswept levels, optional distinct candidates, and pivot/confirmation metadata",
        "source_timeframe": "input OHLC timeframe",
        "source_event_timestamp": "confirmed fractal pivot and optional ATR reversal; candidate pivot location and confirmation row are retained",
        "effective_availability_timestamp": "swing acceptance row; candidate confirmation metadata may add configured timeframe duration",
        "units": "price levels, row positions, integer-like timestamps, bar age, and tick-grid identity",
        "lookback_or_state_lifetime": "left/right fractal windows, ATR-frozen reversal threshold, and retained/candidate state until body close-through or cap",
        "warmup_missingness": "levels missing until confirmed; invalid candidate count/price increment raises",
        "fit_scope": "not fitted",
        "masked_cases": "ATR missing means acceptance on confirmation; optional candidate set only when count > 1",
        "deterministic_fixture": "tests/unit/features/test_structure.py::test_structure_levels_causality; tests/unit/features/test_pivots_swings.py::test_retained_levels_appear_only_after_confirmation",
        "prefix_invariance_test": "tests/unit/features/test_structure.py::test_structure_levels_are_causal; tests/unit/features/test_pivots_swings.py::test_retained_levels_incremental_equals_full_run",
        "test_path_candidates": "tests/unit/features/test_structure.py; tests/unit/features/test_pivots_swings.py",
        "evidence_artifact": "evidence/research/feature_causality/feature_causality_matrix.csv",
        "evidence_status": "source_and_prefix_fixtures_reviewed; source_timeframe_clock_semantics_inherited",
        "evidence_note": "Accepted swings become visible only after pivot confirmation and any configured ATR reversal. Raw event timestamps remain tied to input index labels and downstream MTF alignment.",
    },
    (
        "features/technical/htf_sweeps.py",
        "detect_confirmed_htf_sweeps",
    ): {
        "output_features": "M1 sweep flags/levels, reference timeframe, pivot and confirmation timestamps, counts, and optional crossed-reference audit",
        "source_timeframe": "M1 OHLC with resampled M3 through D1 reference pivots",
        "source_event_timestamp": "pivot row, full right-hand confirmation bar close, and later first M1 crossing row",
        "effective_availability_timestamp": "M1 row timestamp at or after the confirmed source-bar close",
        "units": "binary event flags, price levels, timeframe-minute codes, nanosecond timestamps, and candidate counts",
        "lookback_or_state_lifetime": "confirmed levels persist until first crossing; at most eight same-side/timeframe references retained",
        "warmup_missingness": "partial trailing source bars excluded; no event without a confirmed pivot and positive qualifying ATR",
        "fit_scope": "not fitted",
        "masked_cases": "first cross consumes a reference even when overshoot is too deep; tie priority is timeframe, overshoot, newest pivot, then price",
        "deterministic_fixture": "tests/unit/features/test_htf_sweeps.py::test_actual_resampled_pivot_uses_close_time_and_ignores_partial_bar; test_real_m1_sweep_waits_until_resampled_m5_pivot_is_confirmed",
        "prefix_invariance_test": "tests/unit/features/test_htf_sweeps.py::test_confirmation_after_sweep_cannot_change_prefix",
        "test_path_candidates": "tests/unit/features/test_htf_sweeps.py",
        "evidence_artifact": "evidence/research/feature_causality/feature_causality_matrix.csv",
        "evidence_status": "source_and_boundary_fixtures_reviewed; clock_meaning_inherits_input_index",
        "evidence_note": "Fixtures establish no use before the configured HTF close and exclude partial trailing bins. External feed/timezone authority is outside scope.",
    },
    (
        "features/technical/swings.py",
        "classify_structure",
    ): {
        "output_features": "HH/HL/LH/LL categorical label and one-hot flags on accepted swing events",
        "source_timeframe": "accepted swing rows from the input swing frame",
        "source_event_timestamp": "current accepted high/low swing and the previously accepted same-side price",
        "effective_availability_timestamp": "same row as the accepted swing event",
        "units": "categorical label and binary flags",
        "lookback_or_state_lifetime": "one prior accepted swing price per side",
        "warmup_missingness": "no label until a prior accepted same-side swing exists",
        "fit_scope": "not fitted",
        "masked_cases": "equal prices produce no HH/LH/HL/LL label; current event updates the stored same-side reference",
        "deterministic_fixture": "tests/unit/features/test_pivots_swings.py::test_classify_structure_labels_new_highs_and_lows_against_prior_events",
        "prefix_invariance_test": "covered compositionally by tests/unit/features/test_pivots_swings.py::test_features_invariant_to_future_data",
        "test_path_candidates": "tests/unit/features/test_pivots_swings.py",
        "evidence_artifact": "evidence/research/feature_causality/feature_causality_matrix.csv",
        "evidence_status": "source_and_direct_event_fixture_tested",
        "evidence_note": "The direct fixture checks higher/lower labels against the prior accepted same-side event; causal availability inherits the accepted swing timestamp.",
    },
    (
        "features/technical/swings.py",
        "swing_features",
    ): {
        "output_features": "ATR-normalized distance, side, size, bars-since, accepted event, and structure one-hot features",
        "source_timeframe": "input OHLC and aligned accepted swings/structure",
        "source_event_timestamp": "current close/ATR and latest accepted swing events/prices",
        "effective_availability_timestamp": "current row after swing acceptance",
        "units": "dimensionless ATR ratios, normalized age in [0,1], direction code, and binary events",
        "lookback_or_state_lifetime": "latest accepted swing state; bars-since age capped by obs_window",
        "warmup_missingness": "distance/size require valid ATR and accepted swing; side remains missing before first event",
        "fit_scope": "not fitted",
        "masked_cases": "invalid/nonpositive ATR becomes missing; age scale has minimum one bar",
        "deterministic_fixture": "tests/unit/features/test_pivots_swings.py::test_swing_features_are_causal; test_bars_since_last_swing_scales_by_obs_window",
        "prefix_invariance_test": "tests/unit/features/test_pivots_swings.py::test_features_invariant_to_future_data",
        "test_path_candidates": "tests/unit/features/test_pivots_swings.py",
        "evidence_artifact": "evidence/research/feature_causality/feature_causality_matrix.csv",
        "evidence_status": "source_and_prefix_fixtures_reviewed",
        "evidence_note": "These values use only current/past accepted swing state; price-level provenance is separately filtered from model observation columns.",
    },
    (
        "features/technical/swings.py",
        "retained_swing_levels",
    ): {
        "output_features": "fixed-width retained high/low levels and pivot locations plus one-time wick-sweep events",
        "source_timeframe": "aligned accepted swings and same-timeframe OHLC",
        "source_event_timestamp": "accepted swing confirmation, first later wick cross, and body-close invalidation",
        "effective_availability_timestamp": "swing confirmation row; removed only after a close through the level",
        "units": "price levels, row locations, integer counts, and binary-like swept event represented by a price",
        "lookback_or_state_lifetime": "until close-through invalidation, capped to max_levels newest retained items per side",
        "warmup_missingness": "NaN fixed slots before enough retained levels exist",
        "fit_scope": "not fitted",
        "masked_cases": "wick crosses emit once but keep the level; body close through removes it",
        "deterministic_fixture": "tests/unit/features/test_pivots_swings.py::test_retained_levels_appear_only_after_confirmation; test_retained_levels_are_removed_on_body_close_through",
        "prefix_invariance_test": "tests/unit/features/test_pivots_swings.py::test_retained_levels_incremental_equals_full_run",
        "test_path_candidates": "tests/unit/features/test_pivots_swings.py",
        "evidence_artifact": "evidence/research/feature_causality/feature_causality_matrix.csv",
        "evidence_status": "source_and_prefix_fixtures_reviewed",
        "evidence_note": "A wick sweep and close-through invalidation are distinct events; the code emits the wick event once and retains the level until invalidation.",
    },
    (
        "features/technical/swings.py",
        "recent_unswept_swing_candidates",
    ): {
        "output_features": "newest-first fixed candidate prices with pivot time, confirmation time, and age",
        "source_timeframe": "aligned accepted swings and same-timeframe OHLC",
        "source_event_timestamp": "pivot location, swing acceptance row, and any body-close invalidation",
        "effective_availability_timestamp": "completed swing acceptance row plus optional confirmation_delay_ms",
        "units": "price, epoch milliseconds, and bar age",
        "lookback_or_state_lifetime": "latest count distinct price-grid candidates per side until close-through or replacement",
        "warmup_missingness": "NaN slots before candidates are accepted; invalid count/increment/delay raises",
        "fit_scope": "not fitted",
        "masked_cases": "same tick-grid price replaces older representative; close-through removes; wick alone does not remove",
        "deterministic_fixture": "tests/unit/features/test_pivots_swings.py::test_recent_unswept_candidates_are_newest_first_and_keep_provenance; test_recent_candidate_expires_only_after_close_through",
        "prefix_invariance_test": "tests/unit/features/test_pivots_swings.py::test_recent_unswept_candidate_is_not_visible_if_swept_on_confirmation_bar",
        "test_path_candidates": "tests/unit/features/test_pivots_swings.py",
        "evidence_artifact": "evidence/research/feature_causality/feature_causality_matrix.csv",
        "evidence_status": "source_and_boundary_fixtures_reviewed; source_clock_inherited",
        "evidence_note": "The function records pivot and acceptance indexes, but absolute time fields inherit source-index timezone/label semantics.",
    },
    (
        "features/technical/swings.py",
        "swing_history",
    ): {
        "output_features": "last N accepted swing high/low price values, newest first",
        "source_timeframe": "accepted swing-event frame",
        "source_event_timestamp": "current accepted swing event and earlier accepted same-side prices",
        "effective_availability_timestamp": "current row when each swing is accepted",
        "units": "price units",
        "lookback_or_state_lifetime": "bounded queue of N accepted levels per side",
        "warmup_missingness": "NaN for history slots not yet populated; each newest slot fills at its accepted event",
        "fit_scope": "not fitted",
        "masked_cases": "invalid/nonfinite swing price events are ignored; n is clamped to at least one",
        "deterministic_fixture": "tests/unit/features/test_pivots_swings.py::test_swing_history_is_current_first_and_does_not_backfill",
        "prefix_invariance_test": "direct row-forward queue fixture verifies current-first order and no pre-event backfill",
        "test_path_candidates": "tests/unit/features/test_build_pipeline.py; tests/unit/features/test_pivots_swings.py",
        "evidence_artifact": "evidence/research/feature_causality/feature_causality_matrix.csv",
        "evidence_status": "source_and_direct_history_fixture_tested",
        "evidence_note": "The direct fixture verifies current-first slot order, prior-slot retention, and NaN before the first accepted event.",
    },
}


def _reviewed_contract(
    *,
    output: str,
    source: str,
    event: str,
    available: str,
    units: str,
    lifetime: str,
    missing: str,
    masked: str,
    fixture: str,
    prefix: str,
    tests: str,
    status: str,
    note: str,
) -> dict[str, str]:
    """Build a reviewed function contract while keeping each field explicit."""
    return {
        "output_features": output,
        "source_timeframe": source,
        "source_event_timestamp": event,
        "effective_availability_timestamp": available,
        "units": units,
        "lookback_or_state_lifetime": lifetime,
        "warmup_missingness": missing,
        "fit_scope": "not fitted",
        "masked_cases": masked,
        "deterministic_fixture": fixture,
        "prefix_invariance_test": prefix,
        "test_path_candidates": tests,
        "evidence_artifact": "evidence/research/feature_causality/feature_causality_matrix.csv",
        "evidence_status": status,
        "evidence_note": note,
    }


REVIEWED_FUNCTION_METADATA.update(
    {
        (
            "features/context/liquidity.py",
            "detect_liquidity_sweeps_retained",
        ): _reviewed_contract(
            output="binary sweep flags, swept level/row, and per-bar swept-level counts",
            source="same-timeframe OHLC, ATR, and retained confirmed swing levels",
            event="current wick cross of a level retained as of the previous row",
            available="current row; confirmed level must precede it and ATR must be finite positive",
            units="binary flags, price, row location, and integer count",
            lifetime="one event row; retained levels persist until separate close-through invalidation",
            missing="no sweep without a prior retained level or usable ATR",
            masked="nonpositive/nonfinite ATR and overshoots above the configured ATR cap are rejected",
            fixture="tests/unit/features/test_liquidity.py::test_retained_sweep_requires_finite_positive_atr; test_retained_sweep_uses_atr_overshoot_limit",
            prefix="tests/unit/features/test_pivots_swings.py::test_retained_levels_incremental_equals_full_run",
            tests="tests/unit/features/test_liquidity.py; tests/unit/features/test_pivots_swings.py",
            status="source_and_boundary_fixtures_reviewed; row_relative_level_identity",
            note="A single side-level event is emitted per bar. Source timestamps inherit the input index; swing confirmation identity is a row location.",
        ),
        (
            "features/context/liquidity.py",
            "detect_mss",
        ): _reviewed_contract(
            output="mss_up/mss_down pulse and crossed BOS price level",
            source="same-timeframe close-through BOS events and structure levels",
            event="current BOS event and the last earlier BOS direction",
            available="same row as the opposite-direction BOS",
            units="binary flags and price level",
            lifetime="one event row; direction state retains only the latest BOS side",
            missing="zero before an initial BOS and when consecutive BOS events keep the same direction",
            masked="simultaneous directions prefer upward BOS via the first branch; source BOS semantics exclude wick-only crosses",
            fixture="tests/unit/features/test_pd_context.py::TestMssCausal.test_mss_marks_only_exact_changes_in_bos_direction",
            prefix="direct prefix truncation assertion in the exact direction-transition fixture",
            tests="tests/unit/features/test_pd_context.py; tests/unit/features/test_liquidity.py",
            status="source_and_direction_transition_fixture_tested",
            note="The exact sequence verifies first BOS suppression, repeated direction suppression, opposite-direction pulses, crossed levels, and prefix consistency.",
        ),
        (
            "features/context/premium_discount.py",
            "build_htf_pd_distance_features",
        ): _reviewed_contract(
            output="ATR-normalized distances to latest swing and Asian/London midpoints plus premium/discount flags",
            source="one configured higher-timeframe OHLC stream and its session labels",
            event="current HTF close, current ATR, confirmed swing levels, and session extrema available to the helper",
            available="current HTF row; downstream alignment is responsible for completed-bar publication",
            units="ATR ratios and binary flags",
            lifetime="latest causal swing and current session-level context",
            missing="distances are missing when swing/session levels or positive ATR are unavailable; flags are zero without midpoint",
            masked="atr_m1 argument is intentionally unused; internal HTF ATR uses period 5",
            fixture="tests/unit/features/test_pd_context.py::TestBuildFeaturesPdContext.test_pd_columns_and_htf_pd_present",
            prefix="tests/unit/features/test_assembled_causality.py::test_assembled_matrix_truncation_causality with include_pd_context enabled",
            tests="tests/unit/features/test_pd_context.py; tests/unit/features/test_variants.py; tests/unit/features/test_assembled_causality.py",
            status="source_and_assembled_prefix_tested; next_close_alignment_and_clock_limit_recorded",
            note="The assembled prefix fixture enables PD context and compares projected outputs across a 700-row cutoff. The helper emits on HTF labels; caller alignment and the supplied index clock still determine next-close visibility.",
        ),
        (
            "features/context/premium_discount.py",
            "build_pd_context_features",
        ): _reviewed_contract(
            output="session-routed Asia/London ranges, prior calendar day/week levels, ATR distances, and PD bias flags",
            source="input OHLC, configured session labels, and prior calendar-date/week groups",
            event="current close/session range and prior completed date/week extrema",
            available="running London levels on current London row; completed Asia/London after session transition; prior calendar groups on later dates",
            units="prices, ATR ratios, categorical/binary flags, and direction code",
            lifetime="current session accumulators plus held completed ranges and previous calendar period",
            missing="prior-day/week values absent before prior period; invalid ATR distances are filled to zero for session context",
            masked="same-session Asia context is hidden; routing follows configured timezone/session labels",
            fixture="tests/unit/features/test_pd_context.py::TestPdContextRouting",
            prefix="tests/research/test_feature_prefix_invariance.py covers selected full pipeline profiles, not isolated session authority",
            tests="tests/unit/features/test_pd_context.py; tests/unit/features/test_session_tz_pd.py; tests/research/test_feature_prefix_invariance.py",
            status="source_and_fixture_reviewed; configured_timezone_calendar_authority_open",
            note="Fixtures establish routing and boundary availability under configured labels; they do not establish an external session calendar or feed clock.",
        ),
        (
            "features/context/premium_discount.py",
            "build_trader_context_features",
        ): _reviewed_contract(
            output="HTF bias, manipulation-opposes-bias flag, and context trade direction",
            source="row-aligned PD bias and optional PO3 manipulation/distribution state",
            event="current row values from PD and PO3 feature producers",
            available="same aligned feature row; inherited from upstream source features",
            units="direction code and binary flag",
            lifetime="row-wise composition with no added memory",
            missing="absent optional inputs default to zero; nonfinite bias handling is not independently validated",
            masked="opposing active manipulation selects reversal side until distribution state takes precedence",
            fixture="tests/unit/features/test_pd_context.py::TestTraderContextComposition",
            prefix="direct row-wise composition; upstream timing limits inherit",
            tests="tests/unit/features/test_pd_context.py; tests/unit/features/test_po3_state.py",
            status="source_and_composition_fixture_tested",
            note="Direct fixtures cover bias clipping, reversal, distribution precedence, and optional-input fallback; timing inherits upstream blocks.",
        ),
        (
            "features/context/swing_retracement.py",
            "level_token",
        ): _reviewed_contract(
            output="stable schema token used in swing-level feature column names",
            source="configured numeric retracement/extension level",
            event="configuration value; no market event",
            available="feature schema construction time",
            units="text token derived from a dimensionless level",
            lifetime="static for a given feature configuration",
            missing="not applicable; builder rejects empty/nonfinite levels",
            masked="distinct configured values that collapse under the legacy token format are rejected by the builder",
            fixture="tests/unit/features/test_entry_ideas.py::test_swing_retracement_rejects_levels_with_colliding_column_tokens",
            prefix="not time-series data",
            tests="tests/unit/features/test_entry_ideas.py",
            status="source_and_schema_boundary_fixture_reviewed",
            note="Legacy names remain unchanged; builder now prevents silent overwrites from colliding custom level tokens.",
        ),
        (
            "features/context/swing_retracement.py",
            "build_swing_retracement_features",
        ): _reviewed_contract(
            output="confirmed-leg direction, retracement band/entry flags, leg timestamps, raw ladder prices, and normalized distances",
            source="same-timeframe close and confirmed swing high/low state",
            event="latest confirmed swing pair; invalidation occurs when close exits the permitted impulse range",
            available="current row after both pivot confirmations and while the leg remains valid",
            units="prices, epoch nanoseconds, dimensionless retracement/distances, and binary flags",
            lifetime="one confirmed pivot pair until a new pair or body-close invalidation",
            missing="no values before valid pivots; invalidated-leg values are masked",
            masked="empty/nonfinite/duplicate level sets, invalid bounds, and colliding column tokens fail closed",
            fixture="tests/unit/features/test_entry_ideas.py::test_swing_retracement_uses_confirmed_leg_and_050_to_0786_band; test_swing_retracement_does_not_use_unconfirmed_future_pivot",
            prefix="tests/unit/features/test_entry_ideas.py::test_swing_retracement_does_not_use_unconfirmed_future_pivot",
            tests="tests/unit/features/test_entry_ideas.py; tests/unit/features/test_build_pipeline.py",
            status="source_and_prefix_fixtures_reviewed; absolute_clock_inherits_input_index",
            note="The feature is a deterministic retracement idea, not a fitted statistical band. Pivot/event identity is represented by row-relative timestamps.",
        ),
        (
            "features/pipeline/session_context_features.py",
            "ensure_london_atr_distances",
        ): _reviewed_contract(
            output="legacy London high/low distances normalized by ATR-5 when PD-context columns are absent",
            source="row-aligned London levels, close, and ATR-5",
            event="current aligned close relative to supplied London range levels",
            available="current feature row",
            units="ATR ratios",
            lifetime="stateless row-wise derivation",
            missing="no-op when required columns are absent; nonpositive ATR produces missing distances",
            masked="returns input unchanged when both PD-context distances already exist; caller close is reindexed",
            fixture="tests/unit/features/test_stage_a_observation.py::test_london_distances_use_explicit_atr_signs; test_london_distances_skipped_when_pd_context_present",
            prefix="stateless row-wise derivation",
            tests="tests/unit/features/test_stage_a_observation.py",
            status="source_and_fixture_reviewed",
            note="This is a compatibility fallback and does not independently validate calendar/session provenance of supplied levels.",
        ),
        (
            "features/po3/entries.py",
            "build_po3_phase_features",
        ): _reviewed_contract(
            output="time-derived PO3 phase category and normalized session progress",
            source="input DatetimeIndex wall-clock fields",
            event="current timestamp relative to configured session start/end",
            available="same timestamp row; outside configured interval phase is missing",
            units="ordinal phase and fraction of session duration",
            lifetime="stateless timestamp transform",
            missing="phase is missing before start and after end; progress clips to zero/one",
            masked="nonpositive session duration raises; timezone/calendar meaning is inherited from index and configured strings",
            fixture="tests/unit/features/test_variants.py::test_po3_phase_known_timestamps; test_po3_phase_outside_session_nan; test_po3_phase_turns_unknown_after_session_end",
            prefix="stateless timestamp transform",
            tests="tests/unit/features/test_variants.py",
            status="source_and_boundary_fixtures_reviewed; timezone_authority_out_of_scope",
            note="The configured end timestamp is included; later timestamps are masked. No external session authority is claimed.",
        ),
        (
            "features/po3/fvg.py",
            "build_fvg_zone_features",
        ): _reviewed_contract(
            output="active FVG zone bounds/origin, in-zone flags, capped ATR edge distances, and later retest flags",
            source="same-timeframe OHLC, three-bar gaps, ATR, and derived active-zone state",
            event="each sparse gap pulse on its third candle; later zone touches/retests and body-close invalidation",
            available="formation row and subsequent active rows; retest requires later bar",
            units="prices, capped ATR ratios, and binary flags",
            lifetime="up to nonnegative configured zone horizon or first invalidating close",
            missing="distance uses cap when no zone or ATR is unavailable; origin may be absent near sample start",
            masked="invalid/nonpositive ATR does not fabricate a price-unit distance; negative horizon or nonfinite reaction buffer raises",
            fixture="tests/unit/features/test_variants.py::test_fvg_zone_features_in_zone; test_fvg_retest_holds_and_a_fill_ends_the_zone; test_same_bar_fvg_retests_identify_the_last_selected_zone; test_fvg_zone_features_causal; tests/unit/features/test_po3_state.py::TestIFVGZones.test_overlapping_fvg_retests_project_the_newest_zone_identity_causally; test_fvg_distance_uses_cap_when_atr_is_unavailable",
            prefix="tests/unit/features/test_variants.py::test_fvg_zone_features_causal; tests/unit/features/test_po3_state.py::TestIFVGZones.test_overlapping_fvg_retests_project_the_newest_zone_identity_causally",
            tests="tests/unit/features/test_variants.py; tests/unit/features/test_po3_state.py",
            status="source_and_prefix_fixtures_reviewed; zone_collection_cardinality_tested; scalar_event_cardinality_open",
            note="The zone builder preserves adjacent overlapping records. The scalar feature contract still selects the newest same-side source zone when multiple retests confirm together, with that selected origin carried in the identity.",
        ),
        (
            "features/po3/fvg_detection.py",
            "detect_fvg",
        ): _reviewed_contract(
            output="bullish/bearish three-candle gap flags and zone bounds",
            source="same-timeframe OHLC rows i-2 and i",
            event="current third candle completing the strict positive imbalance",
            available="current row; no future bar is read",
            units="binary flags and price bounds",
            lifetime="formation pulse on one row",
            missing="first two rows cannot form a gap; bounds are missing when no gap forms",
            masked="zero/equal imbalance is excluded; minimum configured threshold applies in price units",
            fixture="tests/unit/features/test_po3_config.py::TestDetectFVG",
            prefix="tests/unit/features/test_assembled_causality.py::test_assembled_matrix_truncation_causality with include_fvg_ifvg enabled",
            tests="tests/unit/features/test_po3_config.py; tests/unit/features/test_variants.py; tests/unit/features/test_assembled_causality.py",
            status="source_and_assembled_prefix_tested; feed_event_identity_and_publication_time_open",
            note="The assembled prefix fixture enables the FVG pipeline and compares its outputs across a 700-row cutoff. The detector establishes a row-level geometric gap; it does not identify a unique feed event or publication time.",
        ),
        (
            "features/po3/trigger_rules.py",
            "detect_entry_trigger",
        ): _reviewed_contract(
            output="long/short trigger flags and trigger-type labels from confirmed IFVG zones",
            source="current OHLC plus previously confirmed IFVG bounds",
            event="later retest, zone re-entry, or close-through after IFVG confirmation becomes observable",
            available="trigger row strictly after the first observed confirmation row",
            units="binary flags and categorical trigger type",
            lifetime="confirmed zone expires after 50 indexed rows",
            missing="missing zone bounds prevent registering a confirmation",
            masked="requires exact bars/IFVG index equality; forward-filled confirmation is recorded once at its rising edge",
            fixture="tests/unit/features/test_po3_config.py::TestDetectEntryTrigger.test_retest_requires_a_bar_after_confirmation; test_forward_filled_confirmation_is_one_expiring_event",
            prefix="row-forward state; no separate full prefix test for each trigger type",
            tests="tests/unit/features/test_po3_config.py; tests/unit/features/test_variants.py",
            status="source_and_boundary_fixtures_reviewed; input_confirm_time_is_aligned_availability",
            note="The confirmation timestamp here is the first row supplied as observable, not an inference/publication timestamp from an external provider.",
        ),
        (
            "features/po3/trigger_rules.py",
            "detect_htf_fvg",
        ): _reviewed_contract(
            output="HTF FVG flags and price bounds projected onto the M1 spine",
            source="resampled or supplied HTF OHLC stream",
            event="HTF three-bar FVG row and optional availability timestamp",
            available="next HTF open by default, or caller-supplied availability mapping",
            units="binary flags and price bounds",
            lifetime="forward-filled until a later HTF value replaces the row state",
            missing="leading rows without a completed HTF source have zero flags and missing bounds",
            masked="final incomplete HTF bar is not published by default shift; custom availability policy is caller responsibility",
            fixture="tests/unit/features/test_po3_config.py::TestMTFCausality.test_htf_fvg_not_visible_within_own_period; test_explicit_close_alignment_does_not_add_a_second_delay",
            prefix="tests/unit/features/test_po3_config.py::TestMTFCausality",
            tests="tests/unit/features/test_po3_config.py; tests/unit/features/test_variants.py",
            status="source_and_alignment_fixtures_reviewed; schedule_and_feed_clock_authority_out_of_scope",
            note="Availability is positional/configured; source timestamp timezone and provider publication time remain unverified.",
        ),
        (
            "features/po3/trigger_rules.py",
            "detect_ltf_ifvg",
        ): _reviewed_contract(
            output="primary-timeframe IFVG confirmation flags and zone bounds on M1 rows",
            source="resampled or supplied primary timeframe OHLC and FVG confirmation",
            event="primary timeframe IFVG confirmation plus optional availability timestamp",
            available="next primary timeframe open by default, or caller-supplied availability mapping",
            units="binary flags and price bounds",
            lifetime="forward-filled until a later primary timeframe observation replaces it",
            missing="leading rows without completed confirmation have zero flags and missing bounds",
            masked="last incomplete primary bar is not exposed by default shift; `ltf` parameter is retained but unused",
            fixture="tests/unit/features/test_po3_config.py::TestMTFCausality.test_ltf_ifvg_confirmation_not_visible_within_own_period; test_explicit_close_alignment_does_not_add_a_second_delay",
            prefix="tests/unit/features/test_po3_config.py::TestMTFCausality",
            tests="tests/unit/features/test_po3_config.py; tests/unit/features/test_variants.py",
            status="source_and_alignment_fixtures_reviewed; timezone_and_feed_clock_authority_out_of_scope",
            note="The implementation detects IFVG on primary_tf; the ltf argument has no effect. Publication-time truth is not established.",
        ),
        (
            "features/po3/trigger_rules.py",
            "detect_po3_entries",
        ): _reviewed_contract(
            output="combined HTF FVG, primary IFVG confirmation, and long/short entry triggers",
            source="M1 spine plus configured or precomputed HTF and primary timeframe bars",
            event="upstream FVG/IFVG events and later trigger rows",
            available="inherits each aligned source availability; trigger is later than observed confirmation",
            units="binary flags, prices, and trigger type",
            lifetime="inherits source zone and 50-row trigger state horizons",
            missing="absent source bars use resampling; no signal before source availability",
            masked="timeframe labels normalize to uppercase; explicit availability is passed to both alignment paths",
            fixture="tests/unit/features/test_po3_config.py::TestMTFCausality.test_po3_entries_no_entry_before_confirmation_visible; test_explicit_close_alignment_does_not_add_a_second_delay",
            prefix="tests/unit/features/test_variants.py::test_po3_full_no_lookahead_on_entries",
            tests="tests/unit/features/test_po3_config.py; tests/unit/features/test_variants.py",
            status="source_and_integration_fixtures_reviewed; source_event_identity_and_external_clock_open",
            note="Composition does not add a separate provider timestamp; effective availability is inherited from the supplied/aligned bars.",
        ),
        (
            "features/po3/zones.py",
            "build_fvg_zones",
        ): _reviewed_contract(
            output="ordered FVG/IFVG zone records with bounds, confirmation kind, end time, and invalidation state",
            source="row-aligned OHLC and either forward-filled 0-to-1 state transitions or sparse event pulses",
            event="signal rising edge for state inputs or each positive row when signals_are_events is enabled; later body close through far edge or configured horizon",
            available="signal row; zone ends at first invalidating close or inclusive nonnegative row horizon",
            units="timestamps, prices, categorical kind/side, and status flags",
            lifetime="max_zone_bars rows or earlier close-through",
            missing="no zones for empty inputs, absent signal columns, invalid bounds, or no event/rising edge",
            masked="bars/signals must have identical indexes; negative horizons raise; wick alone does not invalidate",
            fixture="tests/unit/features/test_po3_config.py::TestBuildFVGZones.test_zone_from_htf_fvg; test_adjacent_overlapping_fvg_events_keep_distinct_zone_records; test_zone_invalidation_on_fill; test_zone_horizon_expiry; test_zone_builder_rejects_misaligned_signal_rows",
            prefix="event and end scans are forward-only; no dedicated truncation test for record equality",
            tests="tests/unit/features/test_po3_config.py",
            status="source_and_boundary_fixtures_reviewed; timestamp_clock_inherits_input_index",
            note="The aligned signal row is treated as observable. Sparse event mode preserves consecutive and overlapping detections; state mode retains rising-edge behavior. Neither mode establishes upstream feed publication time.",
        ),
        (
            "features/po3/zones.py",
            "build_fvg_zones_for_plot",
        ): _reviewed_contract(
            output="plot-only native HTF FVG and LTF IFVG rectangles with gap bounds and fill end",
            source="resampled native timeframe OHLC and retrospectively detected FVG/IFVG rows",
            event="native gap formation/confirmation; plotted FVG starts at bar2 open",
            available="retrospective chart geometry; deliberately not a model-facing availability timestamp",
            units="timestamps, prices, kind/side labels, and status flags",
            lifetime="until native timeframe close-through invalidation or end of supplied sample",
            missing="empty input or fewer than three native bars yields no zones for that family",
            masked="plot start intentionally precedes causal M1 feature visibility; must not be used as policy input",
            fixture="tests/unit/features/test_po3_config.py::TestBuildFVGZonesForPlot",
            prefix="plot geometry recomputes from supplied sample; no feature prefix contract applies",
            tests="tests/unit/features/test_po3_config.py",
            status="source_reviewed_plot_only_noncausal_geometry_by_design",
            note="This helper is explicitly retrospective and plot-only. Agent-facing causal zones use build_fvg_zones instead.",
        ),
        (
            "features/po3/fvg.py",
            "build_fvg_zone_features_with_event_ledger",
        ): _reviewed_contract(
            output="unchanged scalar FVG features plus one diagnostic record per confirmed source zone",
            source="same-timeframe OHLC, three-bar gaps, ATR, and derived active-zone state",
            event="each source-zone retest confirmation and the scalar-selected zone",
            available="confirmation row; retest requires a later bar than zone formation",
            units="scalar feature units plus price, row positions, and nanosecond timestamps in event records",
            lifetime="inherits the nonnegative configured zone horizon or first invalidating close",
            missing="no event record until a source zone confirms a retest",
            masked="diagnostic ledger preserves collisions; selected_by_scalar identifies the unchanged scalar projection",
            fixture="tests/unit/features/test_variants.py::test_fvg_zone_features_and_event_ledger_are_causal; test_fvg_zone_event_ledger_preserves_collisions_without_changing_features",
            prefix="tests/unit/features/test_variants.py::test_fvg_zone_features_and_event_ledger_are_causal",
            tests="tests/unit/features/test_variants.py",
            status="source_and_event_prefix_fixture_tested; feed_clock_and_scalar_event_cardinality_open",
            note="The ledger records each confirmed source zone without changing model-facing features. It does not establish external publication time or policy-action cardinality.",
        ),
        (
            "features/po3/ifvg_detection.py",
            "detect_ifvg_confirmation_events",
        ): _reviewed_contract(
            output="one diagnostic record per confirmed source gap with confirmation, pass, origin, zone, and scalar-selection fields",
            source="same-timeframe OHLC and FVG rows on a DatetimeIndex",
            event="source gap origin, later wick pass, and subsequent qualifying close confirmation",
            available="completed input-bar close; confirmation requires a row after the pass row",
            units="price bounds, positional rows, nanosecond timestamps, side, and scalar-selection flag",
            lifetime="inherits IFVG active-zone expiry and confirmation conditions from the scalar detector",
            missing="no record until a source gap confirms; missing source times remain unresolved",
            masked="ledger preserves same-row collisions and identifies the newest matching gap selected by scalar output",
            fixture="tests/unit/features/test_po3_config.py::TestIFVGConfirmationBehavior.test_same_bar_confirmations_keep_the_newest_matching_gap_identity; tests/research/test_ifvg_zone_event_ledger.py",
            prefix="tests/unit/features/test_po3_config.py::TestIFVGConfirmationBehavior.test_ifvg_confirmation_event_ledger_is_prefix_causal",
            tests="tests/unit/features/test_po3_config.py; tests/research/test_ifvg_zone_event_ledger.py",
            status="source_collision_and_prefix_fixtures_tested; feed_clock_and_policy_event_cardinality_open",
            note="This API emits diagnostic source-gap confirmations and leaves the scalar newest-confirmation projection unchanged. It does not establish publication time or downstream action cardinality.",
        ),
        (
            "features/context/trade_setup_candidates.py",
            "trade_setup_event_identity_record",
        ): _reviewed_contract(
            output="versioned dictionary serialization of an optional trade-setup source-event identity",
            source="identity object fields already resolved by the candidate event identity function",
            event="no new event; preserves source times, ID, and identity status",
            available="serialization time; source-event availability is inherited from the identity object",
            units="text fields and integer nanosecond timestamps",
            lifetime="single identity record; no timeseries state",
            missing="None serializes to an empty mapping; unresolved identity status is preserved when present",
            masked="does not resolve identities, infer times, or modify the candidate/action catalog",
            fixture="tests/unit/features/test_trade_setup_candidate_events.py::test_event_identity_record_preserves_version_status_and_source_times",
            prefix="not applicable to a static serialization",
            tests="tests/unit/features/test_trade_setup_candidate_events.py",
            status="source_serialization_and_fixture_tested",
            note="The serializer carries the supplied version, identity status, ID, and ordered source timestamps; it performs no market-data computation.",
        ),
    }
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _artifact_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def _public_functions() -> list[tuple[str, str, str]]:
    """Return feature and upstream time/session functions, deduplicated by source."""
    found: set[tuple[str, str, str]] = set()
    for source in sorted(FEATURE_ROOT.rglob("*.py")):
        if source.name == "__init__.py":
            continue
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        relative = source.relative_to(ROOT).as_posix()
        for node in tree.body:
            if isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef)
            ) and not node.name.startswith("_"):
                found.add(("public_feature_function_candidate", relative, node.name))
    for source in UPSTREAM_DATA_MODULES:
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        relative = source.relative_to(ROOT).as_posix()
        for node in tree.body:
            if isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef)
            ) and not node.name.startswith("_"):
                found.add(("upstream_time_session_function_candidate", relative, node.name))
    return sorted(found)


def _candidate_tests(function_name: str) -> list[str]:
    """List test files mentioning a function; candidates require human verification."""
    paths: list[str] = []
    for test_root in TEST_ROOTS:
        if not test_root.exists():
            continue
        for test_path in sorted(test_root.rglob("test_*.py")):
            try:
                source = test_path.read_text(encoding="utf-8")
            except OSError:
                continue
            if function_name in source:
                paths.append(test_path.relative_to(ROOT).as_posix())
    return paths


def _function_row(record_type: str, source_path: str, function_name: str) -> dict[str, Any]:
    candidates = _candidate_tests(function_name)
    row = {
        "record_type": record_type,
        "feature_or_flag": function_name,
        "function": function_name,
        "output_features": UNASSESSED,
        "source_timeframe": UNASSESSED,
        "source_event_timestamp": UNASSESSED,
        "effective_availability_timestamp": UNASSESSED,
        "units": UNASSESSED,
        "lookback_or_state_lifetime": UNASSESSED,
        "warmup_missingness": UNASSESSED,
        "fit_scope": UNASSESSED,
        "masked_cases": UNASSESSED,
        "deterministic_fixture": UNASSESSED,
        "prefix_invariance_test": UNASSESSED,
        "source_path": source_path,
        "test_path_candidates": ";".join(candidates) if candidates else UNASSESSED,
        "evidence_artifact": "",
        "evidence_status": "metadata_review_required",
        "evidence_note": (
            "Generated source inventory only; inferred test paths are candidates, not validated coverage."
        ),
        "active_candidate_rows": "",
        "identified_source_event_rows": "",
        "missing_source_event_time_rows": "",
        "distinct_candidate_scoped_event_ids": "",
        "identified_identity_episode_starts": "",
        "adjacent_active_identity_changes": "",
        "distinct_ids_reused_across_active_episodes": "",
        "identity_coverage_fraction": "",
        "identity_measurement_status": "not_applicable",
    }
    reviewed = REVIEWED_FUNCTION_METADATA.get((source_path, function_name))
    if reviewed:
        row.update(reviewed)
    return row


def _candidate_rows(
    census_dir: Path,
) -> tuple[list[dict[str, Any]], str, str, dict[str, int | float]]:
    candidate_summary = census_dir / "candidate_summary.csv"
    candidate_identity_summary = census_dir / "candidate_event_identity_summary.csv"
    if not candidate_summary.is_file():
        raise FileNotFoundError(f"candidate census is required: {candidate_summary}")
    if not candidate_identity_summary.is_file():
        raise FileNotFoundError(
            f"candidate event identity census is required: {candidate_identity_summary}"
        )
    with candidate_summary.open(newline="", encoding="utf-8") as stream:
        candidates = list(csv.DictReader(stream))
    with candidate_identity_summary.open(newline="", encoding="utf-8") as stream:
        identity_reader = csv.DictReader(stream)
        identity_columns = set(identity_reader.fieldnames or ())
        identity_rows = list(identity_reader)
    required_identity_columns = {
        "candidate_id",
        "active_m1_rows",
        "identified_source_event_rows",
        "missing_source_event_time_rows",
        "distinct_source_event_ids",
        "identity_coverage_fraction",
        "identified_identity_episode_starts",
        "adjacent_active_identity_changes",
        "distinct_ids_reused_across_active_episodes",
    }
    missing_identity_columns = required_identity_columns - identity_columns
    if missing_identity_columns:
        missing_names = ", ".join(sorted(missing_identity_columns))
        raise ValueError(f"candidate event identity census lacks lifecycle fields: {missing_names}")
    ids = [row.get("candidate_id", "") for row in candidates]
    if len(candidates) != 108 or len(set(ids)) != 108:
        raise ValueError(f"expected 108 unique candidate rows, found {len(candidates)}")
    identities = {row.get("candidate_id", ""): row for row in identity_rows}
    if len(identity_rows) != 108 or set(ids) != set(identities):
        raise ValueError(
            "candidate and event identity summaries must contain the same 108 candidates"
        )

    active_total = identified_total = missing_total = distinct_total = 0
    episode_start_total = adjacent_change_total = reused_identity_total = 0
    for candidate in candidates:
        identity = identities[candidate["candidate_id"]]
        active = int(candidate["active_m1_rows"])
        identified = int(identity["identified_source_event_rows"])
        missing = int(identity["missing_source_event_time_rows"])
        distinct = int(identity["distinct_source_event_ids"])
        episode_starts = int(identity["identified_identity_episode_starts"])
        adjacent_changes = int(identity["adjacent_active_identity_changes"])
        reused_ids = int(identity["distinct_ids_reused_across_active_episodes"])
        if active != int(identity["active_m1_rows"]) or identified + missing != active:
            raise ValueError(
                f"candidate identity counts do not reconcile for {candidate['candidate_id']}"
            )
        if distinct > identified:
            raise ValueError(
                f"distinct event IDs exceed identified rows for {candidate['candidate_id']}"
            )
        if not 0 <= episode_starts <= identified:
            raise ValueError(
                f"identity episode starts do not reconcile for {candidate['candidate_id']}"
            )
        if not 0 <= adjacent_changes <= max(identified - 1, 0):
            raise ValueError(
                f"adjacent identity changes do not reconcile for {candidate['candidate_id']}"
            )
        if not 0 <= reused_ids <= distinct:
            raise ValueError(
                f"reused identity count does not reconcile for {candidate['candidate_id']}"
            )
        active_total += active
        identified_total += identified
        missing_total += missing
        distinct_total += distinct
        episode_start_total += episode_starts
        adjacent_change_total += adjacent_changes
        reused_identity_total += reused_ids

    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        identity = identities[candidate["candidate_id"]]
        flag = candidate["feature_column"]
        supported = candidate["support_status"] == "supported"
        idea = candidate["idea"]
        timeframe = candidate["timeframe"]
        source_event = UNASSESSED
        state_lifetime = "inherited from the source feature; per-family event-versus-state lifetime review remains open"
        event_note = "Source-event semantics have not been reviewed."
        if supported and idea == "standard_deviation":
            source_event = (
                "current source-bar close and latest confirmed swing leg; identity uses source-time metadata "
                "standard_deviation_leg_start_time_ns + standard_deviation_leg_end_time_ns"
            )
            state_lifetime = (
                "eligibility can persist across consecutive source rows while close remains in the configured "
                "retracement band; MTF values project at timeframe_close_times onto M1"
            )
            event_note = (
                "Code semantics establish close-based eligibility from a confirmed swing leg. The companion "
                "resolver uses retained leg times when present; source indices are treated as open-stamped by "
                "the local config and provider publication time is unknown."
            )
        elif supported and idea == "po3":
            source_event = "source PO3 sweep and reclaim plus direction-matched, same-timeframe IFVG confirmation and associated FVG-origin timestamps"
            state_lifetime = "row-wise PO3 eligibility state keyed by its sweep/reclaim/qualifying-IFVG leg; binary eligibility can persist across rows"
            event_note = (
                "The source requires post-confirmation same-direction PO3 distribution and an active gap; source "
                "sweep/reclaim, matching IFVG confirmation, and associated FVG-origin times form the companion "
                "identity when present. The selected gap is keyed, but the ID does not prove all same-row events, "
                "unique state episodes, or feed publication time."
            )
        elif supported and idea == "ifvg_retest":
            source_event = (
                "IFVG confirmation timestamp plus the later retest-confirmation timestamp that clears the "
                "configured reaction threshold, keyed by selected source FVG origin"
            )
            state_lifetime = "event flag on the qualifying retest-confirmation row"
            event_note = (
                "The fixture/code distinguishes the later retest from confirmation; identity also includes the "
                "selected source FVG origin. Other colliding zones are not separate category events; feed "
                "publication time remains unknown."
            )
        elif supported and idea == "ifvg_unretested":
            source_event = (
                "selected IFVG close-through confirmation and source FVG-origin timestamps"
            )
            state_lifetime = "confirmation/state flag as emitted by the M1 IFVG producer"
            event_note = (
                "This is the close-through confirmation, not the later retest event; source feed publication time "
                "remains unknown. The companion resolver keys the selected global confirmation and source origin."
            )
        elif idea == "fvg_retest":
            source_event = (
                "completed third source-candle FVG formation, followed by a zone-overlap retest and a later "
                "qualifying close; the selected scalar retest is keyed by its source FVG origin"
            )
            state_lifetime = (
                "multiple zones can coexist; sparse adjacent formation pulses remain distinct, while the latest "
                "same-side retest to confirm on one row supplies the scalar event and source-origin key"
            )
            event_note = (
                "Source review: the retest is a later completed-bar event. Same-row overlapping retests still "
                "collapse to one selected scalar zone, whose origin is now retained in the identity. This flag "
                "is disabled by the registered overlay; no local candidate "
                "rows or identity counts are evidence for it."
            )
        elif idea == "ifvg_retest":
            source_event = (
                "FVG origin row, later pass-wick row, qualifying close-through confirmation, and a still-later "
                "zone retest with reaction-threshold close"
            )
            state_lifetime = (
                "latest confirmed IFVG zone per direction replaces older active zone; retest requires a later "
                "leave, touch, and qualifying close"
            )
            event_note = (
                "Source review: confirmation and retest are distinct later-row events. The identity includes the "
                "selected zone's source origin, but scalar confirmation and latest-zone state discard other "
                "overlapping same-side events. This timeframe flag is disabled by the registered "
                "overlay; no local candidate rows or identity counts are evidence for it."
            )
        elif idea == "ifvg_unretested":
            source_event = (
                "FVG origin row, later pass-wick row, and qualifying close-through IFVG confirmation; this is "
                "not the subsequent retest event"
            )
            state_lifetime = (
                "latest confirmed IFVG zone per direction replaces older active zone; confirmation identity "
                "includes the selected source FVG origin when present"
            )
            event_note = (
                "Source review: this candidate uses the close-through confirmation pulse, not a later retest. "
                "The scalar producer can retain only one same-side confirmation/zone at a row and the active "
                "state replaces older zones. Other same-row gaps are not represented as separate model actions. "
                "This timeframe flag is disabled by the registered overlay; no "
                "local candidate rows or identity counts are evidence for it."
            )
        elif idea == "po3":
            source_event = (
                "direction-matched sweep, later reclaim, qualifying IFVG confirmation, and subsequent "
                "distribution-after-IFVG state; resolver keys sweep, reclaim, same-direction IFVG confirmation, and associated source FVG origin"
            )
            state_lifetime = (
                "persistent directional state until replaced by a fresh sweep; non-M1 PO3 state is separately "
                "built on source-timeframe bars and projected to M1"
            )
            event_note = (
                "Source review: a sweep/reclaim alone is not eligible; distribution requires a qualifying "
                "same-direction IFVG. The resolver keys the selected gap origin but can still reuse an ID across "
                "state episodes; this does not count all colliding source events. This flag is disabled by the "
                "registered overlay; no local candidate rows or identity counts are evidence for it."
            )
        elif idea == "order_block":
            source_event = (
                "prior confirmed swing break with displacement, last opposing-candle origin, later zone overlap, "
                "and a still-later close confirming the retest"
            )
            state_lifetime = (
                "one active zone per direction; a new same-side break replaces prior zone and clears pending "
                "retest state; invalidation/expiry ends eligibility"
            )
            event_note = (
                "Source review: candidate identity uses origin plus retest confirmation, while the producer does "
                "not retain a distinct displacement/creation timestamp and cannot represent multiple concurrent "
                "same-side blocks. The registered overlay disables this family; no local candidate rows or "
                "identity counts are evidence for it."
            )
        rows.append(
            {
                "record_type": "setup_entry_idea_flag",
                "feature_or_flag": flag,
                "function": "build_entry_idea_features; trade_setup_candidate_mask",
                "output_features": flag,
                "source_timeframe": timeframe,
                "source_event_timestamp": source_event,
                "effective_availability_timestamp": (
                    (
                        "source timeframe_close_times boundary, projected onto the first M1 feature row at/after "
                        "that boundary"
                        if timeframe != "M1"
                        else "M1 source-row close boundary, represented by the next minute boundary for open-stamped rows"
                    )
                    if supported
                    else "M1 feature-row timestamp where a configured source flag would project; no selected-overlay availability"
                ),
                "units": "binary_context_flag",
                "lookback_or_state_lifetime": state_lifetime,
                "warmup_missingness": (
                    "missing, nonnumeric, or nonpositive source values are treated as inactive by the flag projection"
                ),
                "fit_scope": "not_fitted",
                "masked_cases": candidate["support_status"],
                "deterministic_fixture": (
                    "tests/unit/features/test_entry_ideas.py::test_standard_deviation_projection_covers_timeframe_and_direction"
                    + (
                        "; tests/unit/features/test_trade_setup_candidate_events.py::test_mtf_candidate_event_identity_survives_causal_availability_alignment"
                        if timeframe != "M1"
                        else ""
                    )
                    if supported and idea == "standard_deviation"
                    else "tests/unit/features/test_entry_ideas.py::test_selected_m1_setup_projections_keep_exact_family_and_direction"
                    if supported and idea in {"po3", "ifvg_retest", "ifvg_unretested"}
                    else "shared family fixtures exist; exact coverage for this candidate/timeframe/direction is unverified"
                ),
                "prefix_invariance_test": (
                    "row-local projection has no history state; producer timing and prefix invariance are tested upstream"
                    if supported and idea == "standard_deviation" and timeframe == "M1"
                    else "row-local projection plus source-close availability and truncated-prefix agreement across eight MTF windows are tested"
                    if supported and idea == "standard_deviation"
                    else "row-local projection has no history state; producer timing and prefix invariance are tested upstream"
                    if supported and idea in {"po3", "ifvg_retest", "ifvg_unretested"}
                    else "source feature pipeline prefix invariance is tracked separately; real-market result pending"
                ),
                "source_path": (
                    "features/context/entry_ideas.py; "
                    "features/context/trade_setup_candidates.py; "
                    "features/pipeline/feature_matrix_builder.py"
                ),
                "test_path_candidates": (
                    "tests/unit/features/test_entry_ideas.py; tests/unit/features/test_trade_setup_candidate_events.py; "
                    "tests/research/test_trade_setup_opportunity_census.py"
                    if supported
                    and idea in {"standard_deviation", "po3", "ifvg_retest", "ifvg_unretested"}
                    else "tests/unit/features/test_entry_ideas.py; tests/research/test_trade_setup_opportunity_census.py"
                ),
                "evidence_artifact": _artifact_path(candidate_summary),
                "evidence_status": (
                    "source_semantics_reviewed_feed_clock_unresolved"
                    if supported
                    else "source_reviewed_inactive_by_selected_config_identity_limits_open"
                    if source_event != UNASSESSED
                    else "unsupported_by_config"
                ),
                "evidence_note": (
                    f"candidate_id={candidate['candidate_id']}; "
                    f"active_m1_rows={candidate['active_m1_rows']}; "
                    f"{event_note} The binary flag itself does not carry an event ID; the separate resolver "
                    "emits candidate-scoped timestamp identities when required source times resolve. The local census "
                    "measured identity coverage; it does not validate event cardinality, feed publication time, or trades."
                ),
                "active_candidate_rows": identity["active_m1_rows"],
                "identified_source_event_rows": identity["identified_source_event_rows"],
                "missing_source_event_time_rows": identity["missing_source_event_time_rows"],
                "distinct_candidate_scoped_event_ids": identity["distinct_source_event_ids"],
                "identified_identity_episode_starts": identity[
                    "identified_identity_episode_starts"
                ],
                "adjacent_active_identity_changes": identity["adjacent_active_identity_changes"],
                "distinct_ids_reused_across_active_episodes": identity[
                    "distinct_ids_reused_across_active_episodes"
                ],
                "identity_coverage_fraction": identity["identity_coverage_fraction"],
                "identity_measurement_status": (
                    "measured_all_active_rows_resolved"
                    if int(identity["active_m1_rows"]) > 0
                    and int(identity["missing_source_event_time_rows"]) == 0
                    else "measured_no_active_rows"
                    if int(identity["active_m1_rows"]) == 0
                    else "measured_with_unresolved_source_times"
                ),
            }
        )
    totals = {
        "active_candidate_rows": active_total,
        "identified_source_event_rows": identified_total,
        "missing_source_event_time_rows": missing_total,
        "distinct_candidate_scoped_event_ids": distinct_total,
        "identified_identity_episode_starts": episode_start_total,
        "adjacent_active_identity_changes": adjacent_change_total,
        "distinct_ids_reused_across_active_episodes": reused_identity_total,
        "row_weighted_identity_coverage_fraction": (
            identified_total / active_total if active_total else 0.0
        ),
    }
    return (
        rows,
        _sha256(candidate_summary),
        _sha256(candidate_identity_summary),
        totals,
    )


def build_matrix(
    census_dir: Path = DEFAULT_CENSUS_DIR,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build the function and setup-flag inventory with explicit open statuses."""
    functions = _public_functions()
    rows = [_function_row(record_type, path, name) for record_type, path, name in functions]
    candidate_rows, candidate_sha256, identity_sha256, identity_totals = _candidate_rows(census_dir)
    identity_artifact = _artifact_path(census_dir / "candidate_event_identity_summary.csv")
    for row in rows:
        if (
            row["source_path"] == "features/context/trade_setup_candidates.py"
            and row["function"] == "trade_setup_candidate_event_identities"
        ):
            row["evidence_artifact"] = (
                "evidence/research/feature_causality/feature_causality_matrix.csv; "
                f"{identity_artifact}"
            )
    rows.extend(candidate_rows)
    rows.sort(key=lambda row: (row["record_type"], row["source_path"], row["feature_or_flag"]))

    feature_function_count = sum(
        record_type == "public_feature_function_candidate"
        for record_type, _path, _name in functions
    )
    upstream_function_count = sum(
        record_type == "upstream_time_session_function_candidate"
        for record_type, _path, _name in functions
    )
    summary = {
        "schema_version": 2,
        "function_inventory_scope": (
            "public top-level functions under features/ plus upstream time/session transforms; "
            "scope review required"
        ),
        "public_feature_function_count": feature_function_count,
        "upstream_time_session_function_count": upstream_function_count,
        "setup_entry_idea_flag_count": len(candidate_rows),
        "supported_setup_entry_idea_flag_count": sum(
            row["evidence_status"] == "source_semantics_reviewed_feed_clock_unresolved"
            for row in candidate_rows
        ),
        "reviewed_function_metadata_count": len(REVIEWED_FUNCTION_METADATA),
        "unassessed_function_metadata_count": (
            feature_function_count + upstream_function_count - len(REVIEWED_FUNCTION_METADATA)
        ),
        "reviewed_setup_flag_output_availability_count": sum(
            row["effective_availability_timestamp"] != UNASSESSED for row in candidate_rows
        ),
        "unassessed_setup_flag_source_event_count": sum(
            row["source_event_timestamp"] == UNASSESSED for row in candidate_rows
        ),
        "reviewed_inactive_setup_flag_source_event_count": sum(
            row["evidence_status"]
            == "source_reviewed_inactive_by_selected_config_identity_limits_open"
            for row in candidate_rows
        ),
        "reviewed_supported_setup_flag_source_event_count": sum(
            row["evidence_status"] == "source_semantics_reviewed_feed_clock_unresolved"
            for row in candidate_rows
        ),
        "candidate_summary_path": _artifact_path(census_dir / "candidate_summary.csv"),
        "candidate_summary_sha256": candidate_sha256,
        "candidate_identity_summary_path": _artifact_path(
            census_dir / "candidate_event_identity_summary.csv"
        ),
        "candidate_identity_summary_sha256": identity_sha256,
        "candidate_identity_lifecycle_semantics": (
            "tuple and active-mask descriptive counters; not logical market-event cardinality"
        ),
        **identity_totals,
        "matrix_row_count": len(rows),
        "acceptance_status": (
            "incomplete; event cardinality and configurations outside selected checks remain open"
        ),
    }
    return rows, summary


def write_matrix(census_dir: Path = DEFAULT_CENSUS_DIR) -> dict[str, Any]:
    rows, summary = build_matrix(census_dir)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with MATRIX_PATH.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    summary["matrix_sha256"] = _sha256(MATRIX_PATH)
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--census-dir", type=Path, default=DEFAULT_CENSUS_DIR)
    arguments = parser.parse_args()
    print(json.dumps(write_matrix(arguments.census_dir), indent=2))
