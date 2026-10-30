#!/usr/bin/env bash
# Reacquire the approved two-node GH200 shape for the fresh normal-profile pair.
set -uo pipefail

REPO="${TRITON_REPO:-/scratch/work/nguyenl37/Quantitative-RL-Trading-System}"
export TRITON_REPO="$REPO"
export EXPERIMENT_RUN_SPEC="${EXPERIMENT_RUN_SPEC:-config/experiment_runs/dollar_band_q5_a4a_seed50_train2025_2m_normal_zero_latency_v1.yaml}"
export EXPERIMENT_RUN_ID="${EXPERIMENT_RUN_ID:-dollar_band_q5_a4a_seed50_train2025_20261025_2m_normal_zero_latency_v1}"
export EXPERIMENT_RUN_WORKERS="${EXPERIMENT_RUN_WORKERS:-2}"
export EXPERIMENT_RUN_WORKER_CPUS="${EXPERIMENT_RUN_WORKER_CPUS:-47}"
export EXPERIMENT_RUN_SLURM_JOB_NAME="${EXPERIMENT_RUN_SLURM_JOB_NAME:-thesis-q5-normal}"
export EXPERIMENT_RUN_ALLOCATION_SCRIPT="${EXPERIMENT_RUN_ALLOCATION_SCRIPT:-scripts/compute/slurm/experiment_runs/run_dollar_band_q5_2m_normal_allocation.sh}"

cd "$REPO"
if bash "$REPO/scripts/compute/slurm/experiment_runs/run_rq1_pair_supervisor.sh"; then
  status=0
else
  status=$?
fi
echo "normal-profile Q5 supervisor exited with status=$status"
exec bash
