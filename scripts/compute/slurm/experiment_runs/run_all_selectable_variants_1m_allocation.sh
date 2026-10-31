#!/usr/bin/env bash
# Run the registered 42-variant, one-seed 1M exploratory screen on two GH200s.
set -Eeuo pipefail

REPO="${TRITON_REPO:-/scratch/work/nguyenl37/Quantitative-RL-Trading-System}"
SPEC="${EXPERIMENT_RUN_SPEC:-config/experiment_runs/all_selectable_seed42_train2025_1m_n8_adaptive_20261031.yaml}"
EXPERIMENT_RUN_ID="${EXPERIMENT_RUN_ID:-all_selectable_seed42_train2025_1m_n8_adaptive_20261031}"
WORKERS="${EXPERIMENT_RUN_WORKERS:-auto}"
WORKER_CPUS="${EXPERIMENT_RUN_WORKER_CPUS:-auto}"
N_ENVS="${EXPERIMENT_RUN_N_ENVS:-8}"
MAX_WORKERS_PER_GPU="${EXPERIMENT_RUN_MAX_WORKERS_PER_GPU:-9}"
JOB_ID="${SLURM_JOB_ID:?must run inside the two-node GH200 allocation}"
OUT_DIR="$REPO/outputs/experiment_runs/$EXPERIMENT_RUN_ID"
QUEUE="$OUT_DIR/worker_queue"
ALLOCATION_DIR="$REPO/outputs/gpu_allocations/$JOB_ID"
DONE="$ALLOCATION_DIR/release_managers"

cd "$REPO"
export TRITON_REPO="$REPO"
export EXPERIMENT_RUN_OUT_DIR="$OUT_DIR"
export EXPERIMENT_RUN_WORKER_QUEUE="$QUEUE"
export EXPERIMENT_RUN_ALLOCATION_DONE_MARKER="$DONE"
export PATH="$REPO/scripts/compute/slurm/worker_bin:$PATH"
export PYTHONHASHSEED=0
source "$REPO/scripts/compute/slurm/experiment_run_srun_gh200_guard.sh"

manager_pid=""
controller_status=0
console_open=0
allocation_console() {
  local command run_status
  console_open=1
  echo "Allocation $JOB_ID remains open. Commands: status, run <command>, release."
  while IFS= read -r -p "allocation[$JOB_ID]> " command; do
    case "$command" in
      release)
        echo "Releasing allocation $JOB_ID by request."
        return 0
        ;;
      status)
        scontrol show job -o "$JOB_ID" || true
        ;;
      run\ *)
        command="${command#run }"
        set +e
        eval "$command"
        run_status=$?
        set -e
        echo "Follow-up command exited with status=$run_status."
        ;;
      help)
        echo "Commands: status, run <command>, release"
        ;;
      *)
        echo "Unknown command; use 'help'."
        ;;
    esac
  done
  echo "Allocation console input closed; releasing allocation $JOB_ID."
}

finish_allocation() {
  status=$?
  trap - EXIT
  if [[ "${SLURM_PROCID:-0}" == "0" && "$console_open" == "0" ]]; then
    echo "Controller stopped with exit=$status; keeping allocation $JOB_ID for inspection."
    allocation_console
  fi
  if [[ "${SLURM_PROCID:-0}" == "0" ]]; then
    mkdir -p "$ALLOCATION_DIR"
    printf '%s\n' "$status" > "$DONE"
  fi
  if [[ -n "$manager_pid" ]]; then
    wait "$manager_pid" || manager_status=$?
    if [[ "$status" -eq 0 && "${manager_status:-0}" -ne 0 ]]; then
      status="$manager_status"
    fi
  fi
  echo "all-selectable 1M run controller exit=$status; allocation $JOB_ID remains held"
  exit "$status"
}
trap finish_allocation EXIT

source "$REPO/scripts/compute/slurm/activate_venv.sh"
mkdir -p "$OUT_DIR/logs" "$OUT_DIR/reports" "$ALLOCATION_DIR"

if [[ "${SLURM_PROCID:-0}" != "0" ]]; then
  exec "$VIRTUAL_ENV/bin/python" "$REPO/compute/slurm/worker_dispatch.py" --manager \
    >>"$OUT_DIR/logs/worker_manager_$(hostname -s)_${JOB_ID}.log" 2>&1
fi

if [[ -s "$OUT_DIR/experiment_run.json" ]]; then
  echo "experiment run manifest already exists; refusing to duplicate or resume it" >&2
  exit 2
fi

mkdir -p "$QUEUE/$JOB_ID"
"$VIRTUAL_ENV/bin/python" "$REPO/compute/slurm/worker_dispatch.py" --manager \
  >>"$OUT_DIR/logs/worker_manager_$(hostname -s)_${JOB_ID}.log" 2>&1 &
manager_pid=$!
local_node="$(hostname -s)"
local_ready="$QUEUE/$JOB_ID/$local_node/ready"
for _ in $(seq 1 60); do
  [[ -e "$local_ready" ]] && break
  kill -0 "$manager_pid" 2>/dev/null || {
    echo "local worker manager exited before readiness" >&2
    exit 1
  }
  sleep 1
done
if [[ ! -e "$local_ready" ]]; then
  echo "local worker manager did not become ready within 60 seconds" >&2
  exit 1
fi

mapfile -t allocated_nodes < <(scontrol show hostnames "${SLURM_JOB_NODELIST:?}")
manager_deadline=$((SECONDS + 180))
while true; do
  missing_nodes=()
  for node in "${allocated_nodes[@]}"; do
    node_key="${node%%.*}"
    [[ -e "$QUEUE/$JOB_ID/$node_key/ready" ]] || missing_nodes+=("$node_key")
  done
  ((${#missing_nodes[@]} == 0)) && break
  if ((SECONDS >= manager_deadline)); then
    echo "worker managers not ready on all nodes: ${missing_nodes[*]}" >&2
    exit 1
  fi
  sleep 2
done

worker_nodes="$(IFS=,; echo "${allocated_nodes[*]}")"
echo "GH200 managers ready: nodes=$worker_nodes workers=$WORKERS envs=$N_ENVS"
set +e
"$VIRTUAL_ENV/bin/python" "$REPO/experiments/runs/execution.py" \
  --experiment-run-spec "$REPO/$SPEC" \
  --workers "$WORKERS" \
  --n-envs "$N_ENVS" \
  --worker-nodes "$worker_nodes" \
  --worker-cpus "$WORKER_CPUS" \
  --worker-gpu-type gh200 \
  --worker-gpus-per-node 1 \
  --max-workers-per-gpu "$MAX_WORKERS_PER_GPU" \
  --fast-reports \
  2>&1 | tee -a "$OUT_DIR/logs/controller.log"
controller_status=${PIPESTATUS[0]}
set -e
exit "$controller_status"
