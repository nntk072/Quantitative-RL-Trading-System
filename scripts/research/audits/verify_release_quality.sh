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
  tests/unit/features/test_causal_features.py \
  tests/unit/features/test_htf_alignment.py \
  tests/unit/trading/test_risk_properties.py \
  tests/unit/trading/test_repeated_payout_policy.py \
  tests/unit/simulation/test_environment/test_trading_env_golden_traces.py \
  tests/unit/simulation/test_environment/test_tick_fill_reconciliation.py \
  tests/unit/decisioning/test_trade_setup_contract.py \
  tests/unit/decisioning/test_trade_setup_properties.py \
  tests/unit/models/test_trade_setup_observation_schema.py \
  tests/unit/simulation/test_environment/test_trade_setup_observation.py \
  tests/unit/models/test_hybrid_actor.py \
  tests/unit/market_data/test_ticks.py \
  tests/integration/backtest/test_broker_fill_accounting.py \
  tests/integration/backtest/test_broker_quote_parity.py \
  tests/integration/test_trade_setup.py \
  tests/integration/test_scripts_smoke.py::TestBaselineAndReportScripts::test_run_baseline_eval \
  tests/unit/research/test_current_p6_market_inputs.py \
  tests/unit/research/test_release_manifest_hashes.py -q

"$PYTHON_BIN" -m sphinx -b html -W --keep-going docs "$SPHINX_OUT"
