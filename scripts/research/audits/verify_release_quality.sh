#!/usr/bin/env bash
set -uo pipefail

REPOSITORY_ROOT="$(git rev-parse --show-toplevel)" || exit 2
cd "$REPOSITORY_ROOT" || exit 2

PYTHON_BIN="${QRL_PYTHON:-.venv/bin/python}"
RUFF_BIN="${QRL_RUFF:-.venv/bin/ruff}"
SPHINX_OUT="${QRL_SPHINX_OUT:-/tmp/qrl-release-docs}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  printf 'Python executable not found: %s\n' "$PYTHON_BIN" >&2
  exit 2
fi
if [[ ! -x "$RUFF_BIN" ]]; then
  printf 'Ruff executable not found: %s\n' "$RUFF_BIN" >&2
  exit 2
fi

overall_status=0

run_gate() {
  local gate_name="$1"
  shift
  printf '\n=== %s ===\n' "$gate_name"
  if "$@"; then
    printf 'PASS: %s\n' "$gate_name"
  else
    local gate_status=$?
    printf 'FAIL (%s): %s\n' "$gate_status" "$gate_name" >&2
    overall_status=1
  fi
}

run_gate "full-tree Ruff format" "$RUFF_BIN" format --check .
run_gate "full-tree Ruff lint" "$RUFF_BIN" check .
run_gate "full-tree Mypy" "$PYTHON_BIN" -m mypy .

run_gate "scoped unit, integration, and research tests" "$PYTHON_BIN" -m pytest \
  tests/unit/features \
  tests/unit/trading/test_risk_properties.py \
  tests/unit/trading/test_guardrails.py \
  tests/unit/trading/test_risk.py \
  tests/unit/trading/test_risk_policy_contract.py \
  tests/unit/trading/test_repeated_payout_policy.py \
  tests/unit/trading/test_account_state_snapshots.py \
  tests/unit/trading/test_entry_execution_orders.py \
  tests/unit/trading/test_execution_quote_ranges.py \
  tests/unit/trading/test_cost_model.py \
  tests/unit/trading/test_multi_tp.py \
  tests/unit/trading/test_stop_management.py \
  tests/architecture/test_repository_path_migration.py \
  tests/unit/simulation/test_environment/test_trading_env_golden_traces.py \
  tests/unit/simulation/test_environment/test_simulation_transition_contract.py \
  tests/unit/simulation/test_environment/test_observation_schema.py \
  tests/unit/simulation/test_environment/test_tick_fill_reconciliation.py \
  tests/unit/simulation/test_environment/test_risk_alignment.py \
  tests/unit/simulation/test_environment/test_fixed_risk_sizing.py \
  tests/unit/simulation/test_environment/test_eligibility_wiring.py \
  tests/unit/simulation/test_environment/test_entry_state_machine.py \
  tests/unit/simulation/test_environment/test_mtf_windows.py \
  tests/unit/simulation/test_environment/test_strategy_env.py \
  tests/unit/simulation/test_environment/test_ny_steps_eod.py \
  tests/unit/simulation/test_environment/test_year_episode_survival.py \
  tests/unit/simulation/test_environment/test_trade_setup_factory_config.py \
  tests/unit/simulation/test_environment/test_trade_setup_observation.py \
  tests/unit/simulation/test_environment/test_trader_actions.py \
  tests/unit/simulation/test_environment/test_continuous_actions.py \
  tests/unit/simulation/test_environment/test_entry_rejection_counters.py \
  tests/unit/simulation/test_environment/test_sl_tp_fill.py \
  tests/unit/simulation/test_environment/test_swing_trailing_stop.py \
  tests/unit/simulation/test_environment/test_trailing_stop_causality.py \
  tests/unit/simulation/test_environment/test_take_profit_level_ordering.py \
  tests/unit/simulation/test_environment/test_tp_action_contracts.py \
  tests/unit/simulation/test_environment/test_tp_action_decode.py \
  tests/unit/simulation/test_environment/test_tp_execution.py \
  tests/unit/simulation/test_environment/test_tp_mode_state.py \
  tests/unit/simulation/test_environment/test_trading_env_decomposition.py \
  tests/unit/simulation/test_environment/test_decision_correlation.py \
  tests/unit/simulation/test_environment/test_protective_level_runtime.py \
  tests/unit/decisioning/test_trade_setup_contract.py \
  tests/unit/decisioning/test_action_schema_config.py \
  tests/unit/decisioning/test_candidate_geometry_contract.py \
  tests/unit/decisioning/test_trade_setup_properties.py \
  tests/unit/configuration/test_config_typo_safety.py \
  tests/unit/learning/test_candidate_geometry_actor.py \
  tests/unit/configuration/test_survival_candidate_geometry_config.py \
  tests/unit/decisioning/test_candidate_geometry_schema_validation.py \
  tests/unit/learning/test_candidate_geometry_agent.py \
  tests/unit/learning/test_candidate_geometry_policy.py \
  tests/unit/research/test_pretraining_research_contract.py \
  tests/unit/research/test_survival_compute_budget.py \
  tests/unit/research/test_survival_launch_plan.py \
  tests/unit/simulation/test_environment/test_candidate_geometry_observation.py \
  tests/unit/training/test_research_protocol.py \
  tests/unit/learning/test_checkpoint_resume.py \
  tests/unit/learning/test_survival_objective_config.py \
  tests/unit/training/test_variant_resolver.py \
  tests/unit/training/test_backtest_runner_policy.py \
  tests/unit/training/test_feature_fit_scope.py \
  tests/unit/training/test_vae_admission.py \
  tests/unit/training/test_sustainable_growth_variant_resolution.py \
  tests/unit/training/test_training_smoke.py \
  tests/unit/training/test_checkpoint_eval_determinism.py \
  tests/unit/training/test_train_rl_decomposition.py::test_survival_evaluation_summary_ignores_profit_and_activity \
  tests/unit/training/test_train_rl_decomposition.py::test_evaluation_writer_rejects_truthy_malformed_survival_flags \
  tests/unit/training/test_train_rl_decomposition.py::test_evaluation_writer_rejects_malformed_breach_counts \
  tests/unit/training/test_train_rl_decomposition.py::test_training_log_does_not_truth_coerce_report_split_flags \
  tests/unit/training/test_train_rl_decomposition.py::test_survival_training_logs_profit_and_activity_checks_as_diagnostics \
  tests/unit/training/test_train_rl_decomposition.py::test_survival_training_logs_any_incomplete_or_breached_path_as_failure \
  tests/unit/training/test_train_rl_decomposition.py::test_training_aggregation_requires_explicit_boolean_gate_passes \
  tests/unit/training/test_train_rl_decomposition.py::test_survival_qualification_precedes_profit_activity_and_policy_fit \
  tests/unit/training/test_train_rl_decomposition.py::test_zero_train_trades_fail_closed_in_portfolio_training \
  tests/unit/training/test_train_rl_decomposition.py::test_training_runtime_hard_risk_flags_require_typed_consistent_values \
  tests/unit/training/test_survival_gate.py \
  tests/unit/training/test_training_main.py \
  tests/unit/experiments/test_model_variant_catalog.py \
  tests/unit/experiments/test_experiment_run_policy_overrides.py \
  tests/unit/experiments/test_command_boundaries.py \
  tests/unit/models/test_trade_setup_observation_schema.py \
  tests/unit/models/test_mtf_encoder_registration.py \
  tests/unit/models/test_encoders.py \
  tests/unit/models/test_hybrid_actor.py \
  tests/unit/market_data \
  tests/unit/evaluation/test_run_summary.py \
  tests/unit/evaluation/test_metrics.py \
  tests/unit/evaluation/test_cost_decomposition.py \
  tests/unit/evaluation/test_candidate_eligibility.py \
  tests/unit/evaluation/test_candidate_execution.py \
  tests/unit/evaluation/test_candidate_outcomes.py \
  tests/unit/evaluation/test_candidate_proposals.py \
  tests/unit/evaluation/test_candidate_quote_coverage.py \
  tests/unit/evaluation/test_account_state_trace_reconciliation.py \
  tests/unit/evaluation/test_policy_decision_reconciliation.py \
  tests/unit/evaluation/test_trade_setup_policy_diagnostics.py \
  tests/unit/evaluation/test_run_manifest.py \
  tests/unit/evaluation/test_eval_run_provenance.py \
  tests/unit/evaluation/test_limit_execution_sensitivity.py \
  tests/unit/evaluation/test_run_artifact_writer_limits.py \
  tests/unit/evaluation/test_plots_export.py \
  tests/unit/evaluation/test_matched_comparison.py \
  tests/unit/evaluation/test_structure_priority_setup.py \
  tests/unit/evaluation/test_matched_setup_baseline_cli.py \
  tests/unit/evaluation/test_rollout.py \
  tests/unit/evaluation/test_order_chart_regeneration.py \
  tests/unit/evaluation/test_random_eligible_setup.py \
  tests/unit/research/test_variant_details_report.py \
  tests/unit/research/test_numerical_report_verifier.py \
  tests/integration/evaluation/test_random_eligible_setup_rollout.py \
  tests/integration/evaluation/test_matched_setup_baselines.py \
  tests/integration/backtest/test_broker_fill_accounting.py \
  tests/integration/backtest/test_broker_quote_parity.py \
  tests/integration/backtest/test_engine_execution_contract.py \
  tests/integration/backtest/test_engine_backtrader_signal_parity.py \
  tests/integration/backtest/test_no_action_account_parity.py \
  tests/integration/backtest/test_target_reference_contract.py \
  tests/integration/backtest/test_entry_levels.py \
  tests/integration/backtest/test_local_tick_action_trace.py \
  tests/integration/backtest/test_multi_target_protective_lifecycle.py \
  tests/integration/backtest/test_repeated_payout_backtest.py \
  tests/integration/backtest/test_agent_selected_entry_execution.py \
  tests/integration/backtest/test_setup_mask_backtest_boundary.py \
  tests/unit/simulation/test_backtest_management_modes.py \
  tests/integration/backtest/test_account_transition_parity.py \
  tests/integration/backtest/test_risk_lifecycle_characterization.py \
  tests/integration/test_position_fill_accounting.py \
  tests/integration/test_calibration_ci.py \
  tests/integration/test_trade_setup.py \
  tests/integration/test_matched_comparison.py \
  tests/unit/live/test_risk_manager.py \
  tests/unit/live/test_live_entrypoint.py \
  tests/unit/live/test_rl_bridge.py \
  tests/unit/live/test_rl_robot.py \
  tests/unit/live/test_multi_symbol_risk_stops.py \
  tests/integration/test_scripts_smoke.py::TestBaselineAndReportScripts::test_run_baseline_eval \
  tests/unit/research/test_current_market_inputs.py \
  tests/unit/research/test_paired_seed_statistics.py \
  tests/unit/research/test_policy_trade_lifecycle_summary.py \
  tests/unit/research/test_release_manifest_hashes.py \
  tests/unit/research/test_candidate_limit_fill_packet_comparison.py \
  tests/unit/research/test_candidate_outcome_replay_comparison.py \
  tests/unit/research/test_gross_realized_loss_counter_audit.py \
  tests/unit/research/test_missing_artifact_nested_archive_reconciliation.py \
  tests/unit/research/test_paired_seed_count_plan.py \
  tests/unit/research/test_policy_trade_lifecycle_packet.py \
  tests/unit/research/test_recorded_equity_series_audit.py \
  tests/unit/research/test_refresh_result_manifest_artifact_hashes.py \
  tests/unit/research/test_deterministic_reanalysis.py \
  tests/unit/configuration/test_candidate_limit_sensitivity_config.py \
  tests/research/test_feature_prefix_invariance.py \
  tests/research/test_simulator_local_tick_trace_verifier.py \
  tests/research/test_observation_validity_semantics.py \
  tests/research/test_real_market_feature_prefix_shards.py \
  tests/research/test_trade_setup_opportunity_census.py \
  tests/research/test_candidate_event_cardinality_register.py \
  tests/research/test_candidate_outcome_independent_arithmetic.py \
  tests/research/test_missing_artifact_archive_reconciliation.py \
  tests/research/test_missing_artifact_filesystem_reconciliation.py \
  tests/research/test_real_market_feature_prefix_launcher.py \
  tests/research/test_research_provenance_byte_verification.py \
  tests/research/test_score_rule_baselines_period_scope.py \
  tests/research/test_selected_campaign_artifact_verification.py \
  tests/research/test_candidate_geometry_support.py \
  tests/research/test_matched_setup_baseline_accounting_audit.py \
  tests/research/test_plot_trade_setup_opportunity_census.py \
  tests/research/test_configured_timeframe_parity.py \
  tests/research/test_feature_causality_matrix.py \
  tests/research/test_po3_setup_lifecycle_ledger.py \
  tests/research/test_entry_and_exit_attribution_evidence.py \
  tests/research/test_entry_action_funnel_diagnosis.py \
  tests/research/test_fill_quote_source_alignment.py \
  tests/research/test_market_data_inventory_hashing.py \
  tests/research/test_quote_quality_scans.py \
  tests/research/test_market_data_quality_plot.py \
  tests/research/test_function_test_reference_map.py \
  tests/research/test_model_observation_action_artifact_inventory.py \
  tests/research/test_research_provenance_dag.py \
  tests/research/test_historical_source_mappings.py \
  tests/research/test_historical_variant_screen_recoverability.py \
  tests/research/test_selected_checkpoint_recoverability.py \
  tests/unit/research/test_trade_exit_cohorts.py \
  tests/research/test_exit_action_semantics_evidence.py -q

if [[ "${QRL_SKIP_DOCS:-0}" == "1" ]]; then
  printf 'Documentation inventory, evidence audit, and Sphinx are deferred by QRL_SKIP_DOCS=1.\n'
  exit "$overall_status"
fi

run_gate "documentation inventory" "$PYTHON_BIN" -m tools.documentation.inventory --check
run_gate "documentation evidence audit" "$PYTHON_BIN" -m tools.documentation.evidence_audit --check
run_gate "Sphinx build" "$PYTHON_BIN" -m sphinx -b html -W --keep-going docs "$SPHINX_OUT"

if [[ "$overall_status" -eq 0 ]]; then
  printf '\nAll configured release gates passed.\n'
else
  printf '\nOne or more configured release gates failed.\n' >&2
fi
exit "$overall_status"
