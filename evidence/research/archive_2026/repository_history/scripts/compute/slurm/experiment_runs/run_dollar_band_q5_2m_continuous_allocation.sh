#!/usr/bin/env bash
# Run the matched 2M dollar-band/Q5 pair on the original continuous-price cache.
set -Eeuo pipefail

REPO="${TRITON_REPO:-/scratch/work/nguyenl37/Quantitative-RL-Trading-System}"
SPEC="${EXPERIMENT_RUN_SPEC:-config/experiment_runs/dollar_band_q5_a4a_seed50_train2025_2m_continuous_v1.yaml}"
EXPERIMENT_RUN_ID="${EXPERIMENT_RUN_ID:-dollar_band_q5_a4a_seed50_train2025_20261025_2m_continuous_v1}"
OUT_DIR="$REPO/outputs/experiment_runs/$EXPERIMENT_RUN_ID"
JOB_ID="${SLURM_JOB_ID:?must run inside an existing Slurm allocation}"
LAUNCH_ID="$(date -u +%Y%m%dT%H%M%SZ)"
QUEUE="$OUT_DIR/worker_queue/launch_$LAUNCH_ID"
DONE="$OUT_DIR/allocation_controller.exit.${JOB_ID}.${LAUNCH_ID}"

cd "$REPO"
export TRITON_REPO="$REPO"
source "$REPO/scripts/compute/slurm/activate_venv.sh"
export EXPERIMENT_RUN_OUT_DIR="$OUT_DIR"
export EXPERIMENT_RUN_WORKER_QUEUE="$QUEUE"
export EXPERIMENT_RUN_ALLOCATION_DONE_MARKER="$DONE"
export PYTHONHASHSEED=0
export PATH="$REPO/scripts/compute/slurm/worker_bin:$PATH"
source "$REPO/scripts/compute/slurm/experiment_run_srun_gh200_guard.sh"

if [[ -s "$OUT_DIR/experiment_run.json" ]]; then
  echo "experiment run manifest already exists; inspect it and resume through the experiment run controller" >&2
  exit 2
fi
if [[ -e "$QUEUE/$JOB_ID" ]]; then
  echo "worker queue already exists for Slurm job $JOB_ID" >&2
  exit 2
fi

mkdir -p "$OUT_DIR/logs" "$OUT_DIR/reports" "$QUEUE/$JOB_ID"
node="$(hostname -s)"
manager_log="$OUT_DIR/logs/worker_manager_${node}_${JOB_ID}.log"
manager_pid=""

finish_allocation() {
  status=$?
  trap - EXIT
  touch "$DONE"
  if [[ -n "$manager_pid" ]]; then
    if wait "$manager_pid"; then
      manager_status=0
    else
      manager_status=$?
    fi
    if [[ "$status" -eq 0 && "$manager_status" -ne 0 ]]; then
      status="$manager_status"
    fi
  fi
  echo "2M continuous-price dollar-band allocation job=$JOB_ID exit=$status"
  exit "$status"
}
trap finish_allocation EXIT

python -m compute.slurm.worker_dispatch --manager >>"$manager_log" 2>&1 &
manager_pid=$!
ready="$QUEUE/$JOB_ID/$node/ready"
for _ in $(seq 1 60); do
  [[ -e "$ready" ]] && break
  kill -0 "$manager_pid" 2>/dev/null || {
    echo "worker manager exited before readiness; inspect $manager_log" >&2
    exit 1
  }
  sleep 1
done
if [[ ! -e "$ready" ]]; then
  echo "worker manager did not become ready within 60 seconds; inspect $manager_log" >&2
  exit 1
fi

echo "GH200 allocation ready host=$node job=$JOB_ID cpus=${SLURM_CPUS_ON_NODE:-unknown}"
nvidia-smi -L

set +e
python "$REPO/experiments/runs/execution.py" \
  --experiment-run-spec "$REPO/$SPEC" \
  --workers 1 \
  --n-envs 8 \
  --worker-nodes "$node" \
  --worker-cpus 47 \
  --worker-gpu-type gh200 \
  --worker-gpus-per-node 1 \
  2>&1 | tee -a "$OUT_DIR/logs/controller.log"
controller_status=${PIPESTATUS[0]}
set -e
exit "$controller_status"
