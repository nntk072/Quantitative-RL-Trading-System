#!/usr/bin/env bash
# One allocation runs the three strategy variants against their named caches.
set -euo pipefail

REPO="${TRITON_REPO:-$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)}"
SPEC="${EXPERIMENT_RUN_SPEC:-config/experiment_runs/3_strategy_prebuilt_cache_seed42_20m_20261014.yaml}"
EXPERIMENT_RUN_ID="ladder3_prebuilt_cache_seed42_20m_20261014"
OUT_DIR="$REPO/outputs/experiment_runs/$EXPERIMENT_RUN_ID"
DONE_MARKER="$OUT_DIR/allocation_controller.exit"
cd "$REPO"

if [[ "${SLURM_PROCID:-}" == "0" ]]; then
  trap 'mkdir -p "$OUT_DIR"; touch "$DONE_MARKER"' EXIT
  mkdir -p "$OUT_DIR/logs"
  # On GH200 nodes this selects the aarch64 project environment.
  # shellcheck disable=SC1091
  source "$REPO/scripts/compute/slurm/activate_venv.sh"
  timeout --signal=TERM --kill-after=2m 20700s \
    python "$REPO/experiments/runs/execution.py" \
    --experiment-run-spec "$REPO/$SPEC" \
    --resume \
    --workers 3 \
    --n-envs 4 \
    --worker-nodes "${SLURM_JOB_NODELIST:?}" \
    --worker-cpus 3 \
    --worker-gpu-type gh200 \
    --worker-gpus-per-node 2 \
    --fast-reports 2>&1 | tee -a "$OUT_DIR/logs/controller.log"
else
  while [[ ! -e "$DONE_MARKER" ]]; do
    sleep 10
  done
fi
