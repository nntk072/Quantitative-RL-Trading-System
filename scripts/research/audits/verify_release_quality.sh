#!/usr/bin/env bash
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

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

"$RUFF_BIN" format --check .
"$RUFF_BIN" check .
"$PYTHON_BIN" -m mypy .

"$PYTHON_BIN" -m pytest \
  tests/unit/features \
  tests/unit/trading/test_risk_properties.py \
  tests/unit/trading/test_risk_policy_contract.py \
  tests/unit/trading/test_repeated_payout_policy.py \
  tests/unit/simulation/test_environment/test_trading_env_golden_traces.py \
  tests/unit/simulation/test_environment/test_tick_fill_reconciliation.py \
  tests/unit/simulation/test_environment/test_risk_alignment.py \
  tests/unit/simulation/test_environment/test_ny_steps_eod.py \
  tests/unit/simulation/test_environment/test_year_episode_survival.py \
  tests/unit/decisioning/test_trade_setup_contract.py \
  tests/unit/decisioning/test_trade_setup_properties.py \
  tests/unit/models/test_trade_setup_observation_schema.py \
  tests/unit/simulation/test_environment/test_trade_setup_observation.py \
  tests/unit/models/test_hybrid_actor.py \
  tests/unit/market_data \
  tests/unit/evaluation/test_metrics.py \
  tests/unit/evaluation/test_matched_comparison.py \
  tests/unit/evaluation/test_rollout.py \
  tests/unit/evaluation/test_random_eligible_setup.py \
  tests/integration/evaluation/test_random_eligible_setup_rollout.py \
  tests/integration/evaluation/test_matched_setup_baselines.py \
  tests/integration/backtest/test_broker_fill_accounting.py \
  tests/integration/backtest/test_broker_quote_parity.py \
  tests/integration/backtest/test_engine_execution_contract.py \
  tests/integration/backtest/test_account_transition_parity.py \
  tests/integration/backtest/test_risk_lifecycle_characterization.py \
  tests/integration/test_position_fill_accounting.py \
  tests/integration/test_calibration_ci.py \
  tests/integration/test_trade_setup.py \
  tests/integration/test_scripts_smoke.py::TestBaselineAndReportScripts::test_run_baseline_eval \
  tests/unit/research/test_current_market_inputs.py \
  tests/unit/research/test_policy_trade_lifecycle_summary.py \
  tests/unit/research/test_release_manifest_hashes.py \
  tests/research/test_feature_prefix_invariance.py \
  tests/research/test_real_market_feature_prefix_shards.py \
  tests/research/test_trade_setup_opportunity_census.py \
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
  exit 0
fi

"$PYTHON_BIN" -m tools.documentation.inventory --check
"$PYTHON_BIN" -m tools.documentation.evidence_audit --check
"$PYTHON_BIN" -m sphinx -b html -W --keep-going docs "$SPHINX_OUT"
