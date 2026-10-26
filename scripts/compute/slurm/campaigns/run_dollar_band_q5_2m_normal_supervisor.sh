#!/usr/bin/env bash
# Reacquire the approved two-node GH200 shape for the fresh normal-profile pair.
set -uo pipefail

REPO="${TRITON_REPO:-/scratch/work/nguyenl37/Quantitative-RL-Trading-System}"
export TRITON_REPO="$REPO"
export CAMPAIGN_SPEC="${CAMPAIGN_SPEC:-config/campaigns/dollar_band_q5_a4a_seed50_train2025_2m_normal_zero_latency_v1.yaml}"
export CAMPAIGN_ID="${CAMPAIGN_ID:-dollar_band_q5_a4a_seed50_train2025_20261025_2m_normal_zero_latency_v1}"
export CAMPAIGN_WORKERS="${CAMPAIGN_WORKERS:-2}"
export CAMPAIGN_WORKER_CPUS="${CAMPAIGN_WORKER_CPUS:-47}"
export CAMPAIGN_SLURM_JOB_NAME="${CAMPAIGN_SLURM_JOB_NAME:-thesis-q5-normal}"
export CAMPAIGN_ALLOCATION_SCRIPT="${CAMPAIGN_ALLOCATION_SCRIPT:-scripts/compute/slurm/campaigns/run_dollar_band_q5_2m_normal_allocation.sh}"

cd "$REPO"
if bash "$REPO/scripts/compute/slurm/campaigns/run_rq1_pair_supervisor.sh"; then
  status=0
else
  status=$?
fi
echo "normal-profile Q5 supervisor exited with status=$status"
exec bash
