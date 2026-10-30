#!/usr/bin/env bash
# Sequentially run the matched fixed-$10,000 EOD drawdown 2M screen.
set -uo pipefail

REPO="${TRITON_REPO:-/scratch/work/nguyenl37/Quantitative-RL-Trading-System}"
export TRITON_REPO="$REPO"
export EXPERIMENT_RUN_SPEC="${EXPERIMENT_RUN_SPEC:-config/experiment_runs/sustainable_growth_seed50_train2025_2m_eod_dd10k_v1.yaml}"
export EXPERIMENT_RUN_ID="${EXPERIMENT_RUN_ID:-sustainable_growth_seed50_train2025_20261025_2m_eod_dd10k_v1}"
export EXPERIMENT_RUN_WORKERS="${EXPERIMENT_RUN_WORKERS:-2}"
export EXPERIMENT_RUN_WORKER_CPUS="${EXPERIMENT_RUN_WORKER_CPUS:-47}"
export EXPERIMENT_RUN_N_ENVS="${EXPERIMENT_RUN_N_ENVS:-8}"
export EXPERIMENT_RUN_SLURM_JOB_NAME="${EXPERIMENT_RUN_SLURM_JOB_NAME:-thesis-eod-dd10k-2m}"
export EXPERIMENT_RUN_ALLOCATION_SCRIPT="${EXPERIMENT_RUN_ALLOCATION_SCRIPT:-scripts/compute/slurm/experiment_runs/run_sustainable_growth_eod_dd_allocation.sh}"

cd "$REPO"
if bash "$REPO/scripts/compute/slurm/experiment_runs/run_rq1_pair_supervisor.sh"; then
  status=0
else
  status=$?
fi
echo "EOD drawdown experiment run supervisor exited with status=$status"
exec bash
