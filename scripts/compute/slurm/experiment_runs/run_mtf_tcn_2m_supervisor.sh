#!/usr/bin/env bash
# Reacquire the approved two-node GH200 shape for the matched TCN/MTF 2M pair.
set -uo pipefail

REPO="${TRITON_REPO:-/scratch/work/nguyenl37/Quantitative-RL-Trading-System}"
export TRITON_REPO="$REPO"
export EXPERIMENT_RUN_SPEC="${EXPERIMENT_RUN_SPEC:-config/experiment_runs/rq_mtf_tcn_a4a_q5off_seed50_train2025_2m_normal_zero_latency_v1.yaml}"
export EXPERIMENT_RUN_ID="${EXPERIMENT_RUN_ID:-rq_mtf_tcn_a4a_q5off_seed50_train2025_20261025_2m_normal_zero_latency_v1}"
export EXPERIMENT_RUN_WORKERS="${EXPERIMENT_RUN_WORKERS:-2}"
export EXPERIMENT_RUN_WORKER_CPUS="${EXPERIMENT_RUN_WORKER_CPUS:-47}"
export EXPERIMENT_RUN_SLURM_JOB_NAME="${EXPERIMENT_RUN_SLURM_JOB_NAME:-thesis-mtf-2m}"
export EXPERIMENT_RUN_ALLOCATION_SCRIPT="${EXPERIMENT_RUN_ALLOCATION_SCRIPT:-scripts/compute/slurm/experiment_runs/run_mtf_tcn_2m_allocation.sh}"

cd "$REPO"
if bash "$REPO/scripts/compute/slurm/experiment_runs/run_rq1_pair_supervisor.sh"; then
  status=0
else
  status=$?
fi
echo "TCN/MTF 2M supervisor exited with status=$status"
exec bash
