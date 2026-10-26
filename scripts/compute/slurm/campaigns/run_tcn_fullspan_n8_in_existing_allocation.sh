#!/usr/bin/env bash
# Run one corrected-coverage TCN/DSR campaign through existing node managers.
set -Eeuo pipefail

REPO="${TRITON_REPO:-/scratch/work/nguyenl37/Quantitative-RL-Trading-System}"
SPEC="$REPO/config/campaigns/rq_tcn_a4a_seed50_train2025_2m_normal_fullspan_n8_v1.yaml"
JOB_ID="${SLURM_JOB_ID:?must run inside the existing GH200 allocation}"
ALLOCATION_DIR="$REPO/outputs/gpu_allocations/$JOB_ID"
QUEUE="$ALLOCATION_DIR/worker_queue"

cd "$REPO"
source "$REPO/scripts/compute/slurm/activate_venv.sh"

for node in gpuarm1 gpuarm2; do
  ready="$QUEUE/$JOB_ID/$node/ready"
  if [[ ! -e "$ready" ]]; then
    echo "existing worker manager is not ready: $node ($ready)" >&2
    exit 2
  fi
done

export TRITON_REPO="$REPO"
export CAMPAIGN_OUT_DIR="$ALLOCATION_DIR"
export CAMPAIGN_WORKER_QUEUE="$QUEUE"
export CAMPAIGN_ALLOCATION_DONE_MARKER="$ALLOCATION_DIR/release_managers"
export PATH="$REPO/scripts/compute/slurm/worker_bin:$PATH"
export PYTHONHASHSEED=0

exec "$VIRTUAL_ENV/bin/python" "$REPO/experiments/campaigns/execution.py" \
  --campaign-spec "$SPEC" \
  --workers 1 \
  --n-envs 8 \
  --worker-nodes gpuarm1 \
  --worker-cpus 47 \
  --worker-gpu-type gh200 \
  --worker-gpus-per-node 1 \
  --fast-reports
