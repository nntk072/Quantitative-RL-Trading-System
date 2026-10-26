#!/usr/bin/env bash
# Sequentially run the matched fixed-$10,000 EOD drawdown 2M screen.
set -uo pipefail

REPO="${TRITON_REPO:-/scratch/work/nguyenl37/Quantitative-RL-Trading-System}"
export TRITON_REPO="$REPO"
export CAMPAIGN_SPEC="${CAMPAIGN_SPEC:-config/campaigns/sustainable_growth_seed50_train2025_2m_eod_dd10k_v1.yaml}"
export CAMPAIGN_ID="${CAMPAIGN_ID:-sustainable_growth_seed50_train2025_20261025_2m_eod_dd10k_v1}"
export CAMPAIGN_WORKERS="${CAMPAIGN_WORKERS:-2}"
export CAMPAIGN_WORKER_CPUS="${CAMPAIGN_WORKER_CPUS:-47}"
export CAMPAIGN_N_ENVS="${CAMPAIGN_N_ENVS:-8}"
export CAMPAIGN_SLURM_JOB_NAME="${CAMPAIGN_SLURM_JOB_NAME:-thesis-eod-dd10k-2m}"
export CAMPAIGN_ALLOCATION_SCRIPT="${CAMPAIGN_ALLOCATION_SCRIPT:-scripts/compute/slurm/campaigns/run_sustainable_growth_eod_dd_allocation.sh}"

cd "$REPO"
if bash "$REPO/scripts/compute/slurm/campaigns/run_rq1_pair_supervisor.sh"; then
  status=0
else
  status=$?
fi
echo "EOD drawdown campaign supervisor exited with status=$status"
exec bash
