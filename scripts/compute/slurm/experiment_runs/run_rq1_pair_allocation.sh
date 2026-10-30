#!/usr/bin/env bash
# Run the frozen selected-pair experiment run in one existing GH200 allocation.
set -Eeuo pipefail

REPO="${TRITON_REPO:-/scratch/work/nguyenl37/Aalto_MS_Thesis}"
SPEC="${EXPERIMENT_RUN_SPEC:-config/experiment_runs/rq1_entry_fsm_pair_seed101_105_train2025_test2026_20261019.yaml}"
EXPERIMENT_RUN_ID="${EXPERIMENT_RUN_ID:-rq1_entry_fsm_pair_seed101_105_train2025_test2026_20261019}"
WORKERS="${RQ1_WORKERS:-${SLURM_NNODES:-1}}"
OUT_DIR="$REPO/outputs/experiment_runs/$EXPERIMENT_RUN_ID"
QUEUE="$OUT_DIR/worker_queue"
JOB_ID="${SLURM_JOB_ID:?must run inside an existing Slurm allocation}"
DONE="$OUT_DIR/allocation_controller.exit.$JOB_ID"
OVERRIDE_REASON_FILE="$OUT_DIR/reports/resume_fingerprint_override_reason.txt"
if [[ -z "${EXPERIMENT_RUN_RESUME_FINGERPRINT_OVERRIDE_REASON:-}" && -s "$OVERRIDE_REASON_FILE" ]]; then
  EXPERIMENT_RUN_RESUME_FINGERPRINT_OVERRIDE_REASON="$(<"$OVERRIDE_REASON_FILE")"
fi
if [[ -n "${EXPERIMENT_RUN_RESUME_FINGERPRINT_OVERRIDE_REASON:-}" ]]; then
  if ((${#EXPERIMENT_RUN_RESUME_FINGERPRINT_OVERRIDE_REASON} < 12)); then
    echo "fingerprint override reason must be at least 12 characters" >&2
    exit 2
  fi
  export EXPERIMENT_RUN_RESUME_FINGERPRINT_OVERRIDE_REASON
fi

cd "$REPO"
mkdir -p "$OUT_DIR/logs" "$OUT_DIR/reports"
source "$REPO/scripts/compute/slurm/activate_venv.sh"
export TRITON_REPO="$REPO"
export EXPERIMENT_RUN_OUT_DIR="$OUT_DIR"
export EXPERIMENT_RUN_WORKER_QUEUE="$QUEUE"
export EXPERIMENT_RUN_ALLOCATION_DONE_MARKER="$DONE"
export PATH="$REPO/scripts/compute/slurm/worker_bin:$PATH"
export PYTHONHASHSEED=0

if [[ "${SLURM_PROCID:-0}" != "0" ]]; then
  exec python "$REPO/compute/slurm/worker_dispatch.py" --manager \
    >>"$OUT_DIR/logs/worker_manager_$(hostname -s)_${JOB_ID}.log" 2>&1
fi

python3 - "$DONE" <<'PY'
from pathlib import Path
import sys

Path(sys.argv[1]).unlink(missing_ok=True)
PY

manager_pid=""
finish_allocation() {
  status=$?
  printf '%s\n' "$status" >"$DONE"
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
  echo "RQ1 pair allocation job=$JOB_ID exit=$status"
  exit "$status"
}
trap finish_allocation EXIT

READY="$QUEUE/$JOB_ID/$(hostname -s)/ready"
mkdir -p "$QUEUE/$JOB_ID"
python "$REPO/compute/slurm/worker_dispatch.py" --manager \
  >>"$OUT_DIR/logs/worker_manager_$(hostname -s)_${JOB_ID}.log" 2>&1 &
manager_pid=$!
for _ in $(seq 1 60); do
  [[ -e "$READY" ]] && break
  kill -0 "$manager_pid" 2>/dev/null || { echo "worker manager exited before ready" >&2; exit 1; }
  sleep 1
done
if [[ ! -e "$READY" ]]; then
  echo "worker manager did not become ready within 60 seconds" >&2
  exit 1
fi

mapfile -t ALLOCATED_NODES < <(scontrol show hostnames "${SLURM_JOB_NODELIST:?}")
deadline=$((SECONDS + 180))
while true; do
  missing=()
  for node in "${ALLOCATED_NODES[@]}"; do
    [[ -e "$QUEUE/$JOB_ID/${node%%.*}/ready" ]] || missing+=("${node%%.*}")
  done
  ((${#missing[@]} == 0)) && break
  if ((SECONDS >= deadline)); then
    echo "worker managers not ready on all allocated nodes: ${missing[*]}" >&2
    exit 1
  fi
  sleep 2
done
echo "worker managers ready on all nodes: ${ALLOCATED_NODES[*]}"

if [[ ! -s "$OUT_DIR/experiment_run.json" ]]; then
  echo "experiment run manifest is missing before resume validation: $OUT_DIR/experiment_run.json" >&2
  exit 2
fi
attempt_count="$(python3 - "$OUT_DIR/experiment_run.json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as stream:
    experiment_run = json.load(stream)
print(sum(int(job.get("attempts", 0)) for job in experiment_run.get("jobs", [])))
PY
)"
if [[ "$attempt_count" == "0" ]]; then
  python "$REPO/scripts/maintenance/migrations/migrate_preflight_experiment_run.py" \
    --experiment-run-id "$EXPERIMENT_RUN_ID" \
    --experiment-run-spec "$REPO/$SPEC" \
    --expected-fingerprint aa1a343608c41a8b9a596eb410c1648bbd22d6bf8484186ce02fc35d7c80e4ba \
    --workers "$WORKERS" \
    --worker-cpus 47 \
    --worker-gpu-type gh200 \
    --worker-gpus-per-node 1 \
    --fast-reports
else
  echo "skipping one-time preflight migration after $attempt_count trainer attempt(s); experiment run controller will enforce resume identity"
fi

resume_args=()
[[ -s "$OUT_DIR/experiment_run.json" ]] && resume_args+=(--resume)
if [[ -n "${EXPERIMENT_RUN_RESUME_FINGERPRINT_OVERRIDE_REASON:-}" ]]; then
  resume_args+=(
    --resume-fingerprint-override-reason
    "$EXPERIMENT_RUN_RESUME_FINGERPRINT_OVERRIDE_REASON"
  )
  echo "experiment run fingerprint override enabled; resulting training evidence is exploratory"
fi
set +e
timeout --signal=TERM --kill-after=2m 20700s \
  python "$REPO/experiments/runs/execution.py" \
  --experiment-run-spec "$REPO/$SPEC" \
  "${resume_args[@]}" \
  --workers "$WORKERS" \
  --n-envs 64 \
  --worker-nodes "${SLURM_JOB_NODELIST:?}" \
  --worker-cpus 47 \
  --worker-gpu-type gh200 \
  --worker-gpus-per-node 1 \
  --fast-reports \
  2>&1 | tee -a "$OUT_DIR/logs/controller.log"
controller_status=${PIPESTATUS[0]}
set -e
exit "$controller_status"
