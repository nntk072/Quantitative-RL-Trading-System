from __future__ import annotations

from scripts.research.analysis.features.build_feature_causality_matrix import (
    FIELDS,
    UNASSESSED,
    build_matrix,
)


def test_generated_matrix_lists_public_functions_and_all_setup_flags() -> None:
    rows, summary = build_matrix()

    function_rows = [
        row for row in rows if row["record_type"] == "public_feature_function_candidate"
    ]
    upstream_rows = [
        row for row in rows if row["record_type"] == "upstream_time_session_function_candidate"
    ]
    flag_rows = [row for row in rows if row["record_type"] == "setup_entry_idea_flag"]

    assert summary["schema_version"] == 2
    assert summary["public_feature_function_count"] == 96
    assert summary["upstream_time_session_function_count"] == 11
    assert summary["setup_entry_idea_flag_count"] == 108
    assert summary["supported_setup_entry_idea_flag_count"] == 24
    assert len(function_rows) == 96
    assert len(upstream_rows) == 11
    assert len(flag_rows) == 108
    assert len({row["feature_or_flag"] for row in flag_rows}) == 108
    assert all(set(row) == set(FIELDS) for row in rows)
    reviewed = {
        (row["source_path"], row["function"]): row
        for row in function_rows + upstream_rows
        if row["evidence_status"] != "metadata_review_required"
    }
    assert set(reviewed) == {
        ("features/technical/structure.py", "detect_session_levels"),
        ("features/technical/indicators.py", "volume_spike"),
        ("features/technical/indicators.py", "vwap_level"),
        ("features/technical/indicators.py", "vwap_from_session"),
        ("features/technical/indicators.py", "ny_session_clock"),
        ("features/technical/indicators.py", "sweep_velocity"),
        ("features/technical/indicators.py", "wick_ratio"),
        ("features/technical/indicators.py", "ema"),
        ("features/technical/indicators.py", "rsi"),
        ("features/technical/indicators.py", "macd"),
        ("features/technical/indicators.py", "ema_features"),
        ("features/technical/indicators.py", "atr"),
        ("features/technical/indicators.py", "adx"),
        ("features/technical/indicators.py", "bollinger"),
        ("features/technical/indicators.py", "stochastic"),
        ("features/technical/indicators.py", "returns"),
        ("features/technical/indicators.py", "realized_vol"),
        ("features/technical/indicators.py", "time_features"),
        ("features/technical/indicators.py", "atr_normalized_price"),
        ("features/technical/indicators.py", "build_indicators"),
        ("features/context/smt.py", "smt_divergence"),
        ("features/context/liquidity.py", "detect_liquidity_sweeps"),
        ("features/context/liquidity.py", "detect_bos"),
        ("features/context/liquidity.py", "detect_liquidity_sweeps_retained"),
        ("features/context/liquidity.py", "detect_mss"),
        ("features/context/premium_discount.py", "build_htf_pd_distance_features"),
        ("features/context/premium_discount.py", "build_pd_context_features"),
        ("features/context/premium_discount.py", "build_trader_context_features"),
        ("features/context/swing_retracement.py", "build_swing_retracement_features"),
        ("features/context/swing_retracement.py", "level_token"),
        ("features/pipeline/session_context_features.py", "ensure_london_atr_distances"),
        ("features/po3/entries.py", "build_po3_phase_features"),
        ("features/po3/fvg.py", "build_fvg_zone_features"),
        ("features/po3/fvg_detection.py", "detect_fvg"),
        ("features/po3/trigger_rules.py", "detect_entry_trigger"),
        ("features/po3/trigger_rules.py", "detect_htf_fvg"),
        ("features/po3/trigger_rules.py", "detect_ltf_ifvg"),
        ("features/po3/trigger_rules.py", "detect_po3_entries"),
        ("features/po3/zones.py", "build_fvg_zones"),
        ("features/po3/zones.py", "build_fvg_zones_for_plot"),
        ("features/technical/swings.py", "detect_pivots"),
        ("features/technical/swings.py", "detect_swings"),
        ("features/context/entry_ideas.py", "build_entry_idea_features"),
        ("features/context/entry_ideas.py", "entry_idea_context"),
        ("features/context/order_blocks.py", "build_order_block_features"),
        (
            "features/context/order_blocks.py",
            "build_order_block_features_with_event_ledger",
        ),
        ("features/context/session_levels.py", "session_mask"),
        ("features/context/session_levels.py", "session_ohlc"),
        ("features/context/session_levels.py", "prior_period_high_low"),
        ("features/context/session_levels.py", "range_quadrants"),
        ("features/context/session_levels.py", "prev_ny_high_low"),
        ("features/context/session_levels.py", "previous_labeled_session_ohlc"),
        ("features/context/trade_setup_candidates.py", "active_trade_setup_candidates"),
        ("features/context/trade_setup_candidates.py", "trade_setup_candidate_feature_columns"),
        ("features/context/trade_setup_candidates.py", "trade_setup_candidate_mask"),
        (
            "features/context/trade_setup_candidates.py",
            "trade_setup_candidate_event_identities",
        ),
        (
            "features/context/trade_setup_candidates.py",
            "trade_setup_candidate_event_time_fields",
        ),
        ("features/context/reachability.py", "max_tp_distance"),
        ("features/context/reachability.py", "reachable_r_series"),
        ("features/context/reachability.py", "attach_reachable_r"),
        ("features/context/reachability.py", "rr_reaches"),
        ("features/context/policy_market.py", "build_policy_market_context"),
        ("features/context/policy_market.py", "attach_policy_market_context"),
        ("features/pipeline/feature_build_inputs.py", "split_raw_fvg_features"),
        ("features/pipeline/feature_build_inputs.py", "configured_feature_timeframes"),
        ("features/pipeline/feature_build_inputs.py", "feature_block_enabled"),
        ("features/pipeline/feature_build_inputs.py", "resample_market_pair"),
        ("features/pipeline/feature_build_inputs.py", "source_timeframe_training_mask"),
        ("features/pipeline/session_stage.py", "append_session_features"),
        ("features/pipeline/structure_stage.py", "append_structure_features"),
        ("features/pipeline/po3_stage.py", "append_po3_state_features"),
        ("features/po3/ifvg_detection.py", "detect_ifvg_confirmation"),
        ("features/po3/ifvg_detection.py", "detect_ifvg_confirmation_events"),
        ("features/po3/fvg.py", "build_fvg_zone_features_with_event_ledger"),
        ("features/context/trade_setup_candidates.py", "trade_setup_event_identity_record"),
        ("features/po3/ifvg_state.py", "build_po3_ifvg_state"),
        ("features/po3/setup_lifecycle.py", "build_po3_setup_lifecycle_ledger"),
        ("features/po3/po3_phase_state.py", "build_po3_state"),
        ("features/po3/po3_phase_state.py", "build_distribution_after_ifvg"),
        ("features/po3/po3_phase_state.py", "build_ifvg_zone_features"),
        ("features/po3/po3_phase_state.py", "align_ifvg_zone_timeframes"),
        ("features/pipeline/feature_cache_identity.py", "feature_cache_content_hash"),
        ("features/pipeline/feature_cache_identity.py", "feature_cache_path"),
        ("features/pipeline/walkforward_feature_fitting.py", "build_walkforward_fold_features"),
        ("features/input_view.py", "input_view_from_frame"),
        ("features/pipeline/schema.py", "select_legacy_obs_columns"),
        ("features/pipeline/schema.py", "select_obs_columns"),
        ("features/pipeline/feature_matrix_builder.py", "build_features"),
        ("features/technical/structure.py", "structure_levels"),
        ("features/technical/htf_sweeps.py", "detect_confirmed_htf_sweeps"),
        ("features/technical/swings.py", "classify_structure"),
        ("features/technical/swings.py", "swing_features"),
        ("features/technical/swings.py", "retained_swing_levels"),
        ("features/technical/swings.py", "recent_unswept_swing_candidates"),
        ("features/technical/swings.py", "swing_history"),
        ("market_data/transforms/sessions.py", "get_session"),
        ("market_data/transforms/sessions.py", "ny_session_mask"),
        ("market_data/transforms/sessions.py", "add_session_labels"),
        ("market_data/transforms/sessions.py", "filter_session"),
        ("market_data/transforms/sessions.py", "add_session_id"),
        ("market_data/transforms/session_schedule.py", "scheduled_session_close_map"),
        ("market_data/transforms/align.py", "align_timeframes"),
        ("features/pipeline/normalization.py", "rolling_zscore"),
        ("market_data/transforms/align.py", "timeframe_close_times"),
        ("market_data/transforms/align.py", "join_symbols"),
        ("market_data/transforms/resample.py", "resample"),
        ("market_data/transforms/resample.py", "build_all_timeframes"),
    }
    assert summary["reviewed_function_metadata_count"] == 107
    assert summary["unassessed_function_metadata_count"] == 0
    reachability_adapter = reviewed[("features/context/reachability.py", "attach_reachable_r")]
    assert "optional reachable_r_valid" in reachability_adapter["output_features"]
    assert "opt_in_validity_mask_tested" in reachability_adapter["evidence_status"]
    assert "selected historical configs do not enable it" in reachability_adapter["evidence_note"]
    for function_name in (
        "atr",
        "adx",
        "bollinger",
        "stochastic",
        "realized_vol",
        "atr_normalized_price",
        "build_indicators",
    ):
        assert (
            "source_and_assembled_prefix_tested"
            in reviewed[("features/technical/indicators.py", function_name)]["evidence_status"]
        )
    for source_path, function_name in (
        ("features/context/premium_discount.py", "build_htf_pd_distance_features"),
        ("features/po3/fvg_detection.py", "detect_fvg"),
        ("features/pipeline/po3_stage.py", "append_po3_state_features"),
    ):
        assert (
            "source_and_assembled_prefix_tested"
            in reviewed[(source_path, function_name)]["evidence_status"]
        )
    fold_contract = reviewed[
        (
            "features/pipeline/walkforward_feature_fitting.py",
            "build_walkforward_fold_features",
        )
    ]
    assert "source_fold_fit_and_selected_prefix_tested" in fold_contract["evidence_status"]
    assert "exhaustive per-family" in fold_contract["evidence_note"]
    trader_context_contract = reviewed[
        ("features/context/premium_discount.py", "build_trader_context_features")
    ]
    assert trader_context_contract["evidence_status"] == "source_and_composition_fixture_tested"
    assert "TestTraderContextComposition" in trader_context_contract["deterministic_fixture"]
    structure_class_contract = reviewed[("features/technical/swings.py", "classify_structure")]
    assert structure_class_contract["evidence_status"] == "source_and_direct_event_fixture_tested"
    assert (
        "test_classify_structure_labels_new_highs_and_lows"
        in structure_class_contract["deterministic_fixture"]
    )
    swing_history_contract = reviewed[("features/technical/swings.py", "swing_history")]
    assert swing_history_contract["evidence_status"] == "source_and_direct_history_fixture_tested"
    assert "test_swing_history_is_current_first" in swing_history_contract["deterministic_fixture"]
    mss_contract = reviewed[("features/context/liquidity.py", "detect_mss")]
    assert mss_contract["evidence_status"] == "source_and_direction_transition_fixture_tested"
    assert (
        "test_mss_marks_only_exact_changes_in_bos_direction"
        in mss_contract["deterministic_fixture"]
    )
    indicator_contracts = {
        row["function"]: row
        for row in function_rows
        if row["source_path"] == "features/technical/indicators.py"
    }
    assert (
        indicator_contracts["volume_spike"]["evidence_status"]
        == "source_and_pipeline_formula_tested; selected_real_market_profiles_passed"
    )
    assert (
        indicator_contracts["wick_ratio"]["evidence_status"]
        == "source_and_formula_fixture_tested; selected_real_market_profiles_passed; legacy_upper_wick_name_retained"
    )
    assert summary["reviewed_setup_flag_output_availability_count"] == 108
    assert summary["unassessed_setup_flag_source_event_count"] == 0
    assert summary["reviewed_supported_setup_flag_source_event_count"] == 24
    assert summary["reviewed_inactive_setup_flag_source_event_count"] == 84
    assert summary["active_candidate_rows"] == 488008
    assert summary["identified_source_event_rows"] == 488008
    assert summary["missing_source_event_time_rows"] == 0
    assert summary["distinct_candidate_scoped_event_ids"] == 109391
    assert summary["identified_identity_episode_starts"] == 115863
    assert summary["adjacent_active_identity_changes"] == 13758
    assert summary["distinct_ids_reused_across_active_episodes"] == 5719
    assert summary["row_weighted_identity_coverage_fraction"] == 1.0
    assert summary["candidate_identity_lifecycle_semantics"] == (
        "tuple and active-mask descriptive counters; not logical market-event cardinality"
    )
    assert (
        summary["identified_identity_episode_starts"]
        >= summary["distinct_candidate_scoped_event_ids"]
    )
    assert (
        summary["adjacent_active_identity_changes"] <= summary["identified_identity_episode_starts"]
    )
    for field in (
        "identified_identity_episode_starts",
        "adjacent_active_identity_changes",
        "distinct_ids_reused_across_active_episodes",
    ):
        assert sum(int(row[field]) for row in flag_rows) == summary[field]
    assert summary["candidate_identity_summary_path"].endswith(
        "candidate_event_identity_summary.csv"
    )
    identity_contract = reviewed[
        ("features/context/trade_setup_candidates.py", "trade_setup_candidate_event_identities")
    ]
    assert (
        "selected_training_profile_identity_coverage_measured"
        in identity_contract["evidence_status"]
    )
    assert "same-side IFVG confirmation" in identity_contract["source_event_timestamp"]
    assert "not logical event cardinality" in identity_contract["evidence_note"]
    assert "candidate_event_identity_summary.csv" in identity_contract["evidence_artifact"]
    assert (
        "selected_real_market_prefix_profiles_passed"
        in reviewed[("market_data/transforms/align.py", "align_timeframes")]["evidence_status"]
    )
    assert (
        "selected_real_market_prefix_profiles_passed"
        in reviewed[("features/pipeline/normalization.py", "rolling_zscore")]["evidence_status"]
    )
    assert (
        "schedule_authority_unresolved"
        in reviewed[("market_data/transforms/align.py", "timeframe_close_times")]["evidence_status"]
    )
    assert (
        "feed_clock_and_staleness_unresolved"
        in reviewed[("market_data/transforms/align.py", "join_symbols")]["evidence_status"]
    )
    assert (
        "source_timezone_and_schedule_authority_unresolved"
        in reviewed[("features/context/session_levels.py", "session_mask")]["evidence_status"]
    )
    assert (
        "source_timezone_and_schedule_authority_unresolved"
        in reviewed[("features/context/session_levels.py", "previous_labeled_session_ohlc")][
            "evidence_status"
        ]
    )
    assert (
        "cross_symbol_clock_and_staleness_unresolved"
        in reviewed[("features/context/smt.py", "smt_divergence")]["evidence_status"]
    )
    assert (
        "completed_bar_and_source_clock_semantics_unresolved"
        in reviewed[("features/context/order_blocks.py", "build_order_block_features")][
            "evidence_status"
        ]
    )
    assert (
        "only London"
        in reviewed[("features/technical/indicators.py", "sweep_velocity")]["evidence_note"]
    )
    assert (
        "upper-wick"
        in reviewed[("features/technical/indicators.py", "wick_ratio")]["output_features"]
    )
    assert (
        "bin_completeness_and_close_authority_unresolved"
        in reviewed[("market_data/transforms/resample.py", "resample")]["evidence_status"]
    )
    assert all(
        row["evidence_status"] == "metadata_review_required"
        for row in function_rows + upstream_rows
        if (row["source_path"], row["function"]) not in reviewed
    )
    reviewed_flags = [
        row
        for row in flag_rows
        if row["evidence_status"] == "source_semantics_reviewed_feed_clock_unresolved"
    ]
    assert len(reviewed_flags) == 24
    assert all(row["source_event_timestamp"] != UNASSESSED for row in reviewed_flags)
    assert all(
        row["identity_measurement_status"] == "measured_all_active_rows_resolved"
        for row in reviewed_flags
    )
    assert all(row["identity_coverage_fraction"] == "1.0" for row in reviewed_flags)
    assert all("publication time" in row["evidence_note"] for row in reviewed_flags)
    assert all("event cardinality" in row["evidence_note"] for row in reviewed_flags)
    reviewed_inactive_flags = [
        row
        for row in flag_rows
        if row["evidence_status"]
        == "source_reviewed_inactive_by_selected_config_identity_limits_open"
    ]
    assert len(reviewed_inactive_flags) == 84
    assert all(row["source_event_timestamp"] != UNASSESSED for row in reviewed_inactive_flags)
    assert all(
        row["identity_measurement_status"] == "measured_no_active_rows"
        for row in reviewed_inactive_flags
    )
    for family, expected_phrase in (
        ("fvg_retest", "Same-row overlapping retests still collapse"),
        ("ifvg_retest", "overlapping same-side events"),
        ("ifvg_unretested", "later retest"),
        ("po3", "resolver keys the selected gap origin"),
        ("order_block", "multiple concurrent same-side blocks"),
    ):
        family_rows = [
            row
            for row in reviewed_inactive_flags
            if f"entry_idea_{family}_" in row["feature_or_flag"]
        ]
        assert family_rows
        assert all(expected_phrase in row["evidence_note"] for row in family_rows)
    assert all(row["effective_availability_timestamp"] != UNASSESSED for row in flag_rows)
    assert all(
        row["identity_measurement_status"] == "measured_no_active_rows"
        for row in reviewed_inactive_flags
    )
    assert all(row["fit_scope"] == "not_fitted" for row in flag_rows)
    assert summary["acceptance_status"].startswith("incomplete")
