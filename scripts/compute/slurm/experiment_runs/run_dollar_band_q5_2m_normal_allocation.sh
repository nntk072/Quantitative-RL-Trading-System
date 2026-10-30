#!/usr/bin/env bash
# Run the matched normal-price 2M Q5 pair on two persistent GH200 managers.
set -Eeuo pipefail

REPO="${TRITON_REPO:-/scratch/work/nguyenl37/Quantitative-RL-Trading-System}"
SPEC="${EXPERIMENT_RUN_SPEC:-config/experiment_runs/dollar_band_q5_a4a_seed50_train2025_2m_normal_zero_latency_v1.yaml}"
EXPERIMENT_RUN_ID="${EXPERIMENT_RUN_ID:-dollar_band_q5_a4a_seed50_train2025_20261025_2m_normal_zero_latency_v1}"
WORKERS="${EXPERIMENT_RUN_WORKERS:-2}"
WORKER_CPUS="${EXPERIMENT_RUN_WORKER_CPUS:-47}"
OUT_DIR="$REPO/outputs/experiment_runs/$EXPERIMENT_RUN_ID"
QUEUE="$OUT_DIR/worker_queue"
JOB_ID="${SLURM_JOB_ID:?must run inside the approved two-node allocation}"
DONE="$OUT_DIR/allocation_controller.exit.$JOB_ID"

cd "$REPO"
export TRITON_REPO="$REPO"
source "$REPO/scripts/compute/slurm/activate_venv.sh"
export EXPERIMENT_RUN_OUT_DIR="$OUT_DIR"
export EXPERIMENT_RUN_WORKER_QUEUE="$QUEUE"
export EXPERIMENT_RUN_ALLOCATION_DONE_MARKER="$DONE"
export PATH="$REPO/scripts/compute/slurm/worker_bin:$PATH"
export PYTHONHASHSEED=0

mkdir -p "$OUT_DIR/logs" "$OUT_DIR/reports"
if [[ "${SLURM_PROCID:-0}" != "0" ]]; then
  exec python "$REPO/compute/slurm/worker_dispatch.py" --manager \
    >>"$OUT_DIR/logs/worker_manager_$(hostname -s)_${JOB_ID}.log" 2>&1
fi

if [[ -s "$OUT_DIR/experiment_run.json" ]]; then
  echo "experiment run manifest already exists; use its existing fingerprint-aware resume path" >&2
  exit 2
fi

finish_allocation() {
  status=$?
  printf '%s\n' "$status" > "$DONE"
  if [[ -n "${manager_pid:-}" ]]; then
    wait "$manager_pid" || manager_status=$?
    if [[ "$status" -eq 0 && "${manager_status:-0}" -ne 0 ]]; then
      status="$manager_status"
    fi
  fi
  echo "normal-price Q5 2M allocation job=$JOB_ID exit=$status"
  exit "$status"
}
trap finish_allocation EXIT

# Build the selected normal profile once. Its cache root is distinct from the
# discretion profile and all historical quarter-point cache directories.
if ! bash "$REPO/scripts/data/setup_mode_dirs.sh"; then
  echo "failed to prepare the reusable normal/discretion input folders" >&2
  exit 2
fi
if python -m market_data.commands.prebuild_experiment_run_cache \
  2>&1 | tee "$OUT_DIR/logs/split_cache_build_${JOB_ID}.log" \
  > "$OUT_DIR/reports/split_cache_ready_${JOB_ID}.json"; then
  python -m json.tool "$OUT_DIR/reports/split_cache_ready_${JOB_ID}.json" >/dev/null
else
  status=$?
  echo "normal-profile cache build failed with status=$status" >&2
  exit "$status"
fi

mkdir -p "$QUEUE/$JOB_ID"
python "$REPO/compute/slurm/worker_dispatch.py" --manager \
  >>"$OUT_DIR/logs/worker_manager_$(hostname -s)_${JOB_ID}.log" 2>&1 &
manager_pid=$!
node="$(hostname -s)"
ready="$QUEUE/$JOB_ID/$node/ready"
for _ in $(seq 1 60); do
  [[ -e "$ready" ]] && break
  kill -0 "$manager_pid" 2>/dev/null || {
    echo "local worker manager exited before readiness" >&2
    exit 1
  }
  sleep 1
done
if [[ ! -e "$ready" ]]; then
  echo "local worker manager did not become ready within 60 seconds" >&2
  exit 1
fi

mapfile -t ALLOCATED_NODES < <(scontrol show hostnames "${SLURM_JOB_NODELIST:?}")
MANAGER_DEADLINE=$((SECONDS + 180))
while true; do
  missing_nodes=()
  for allocated_node in "${ALLOCATED_NODES[@]}"; do
    node_key="${allocated_node%%.*}"
    [[ -e "$QUEUE/$JOB_ID/$node_key/ready" ]] || missing_nodes+=("$node_key")
  done
  if [[ "${#missing_nodes[@]}" -eq 0 ]]; then
    break
  fi
  if (( SECONDS >= MANAGER_DEADLINE )); then
    echo "worker managers not ready on every allocated node: ${missing_nodes[*]}" >&2
    exit 1
  fi
  sleep 2
done

echo "GH200 managers ready job=$JOB_ID nodes=${ALLOCATED_NODES[*]} workers=$WORKERS"
set +e
python "$REPO/experiments/runs/execution.py" \
  --experiment-run-spec "$REPO/$SPEC" \
  --workers "$WORKERS" \
  --n-envs 64 \
  --worker-nodes "${SLURM_JOB_NODELIST:?}" \
  --worker-cpus "$WORKER_CPUS" \
  --worker-gpu-type gh200 \
  --worker-gpus-per-node 1 \
  --fast-reports \
  2>&1 | tee -a "$OUT_DIR/logs/controller.log"
controller_status=${PIPESTATUS[0]}
set -e
exit "$controller_status"
