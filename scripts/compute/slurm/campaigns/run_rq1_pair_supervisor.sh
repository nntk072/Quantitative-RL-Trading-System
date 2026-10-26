#!/usr/bin/env bash
# Sequentially reacquire the approved two-node GH200 shape until the pair campaign is terminal.
set -Eeuo pipefail
unset MANPATH

REPO="${TRITON_REPO:-/scratch/work/nguyenl37/Aalto_MS_Thesis}"
SPEC="${CAMPAIGN_SPEC:-config/campaigns/rq1_entry_fsm_pair_seed101_105_train2025_test2026_20261021_scratch1.yaml}"
CAMPAIGN_ID="${CAMPAIGN_ID:-rq1_entry_fsm_pair_seed101_105_train2025_test2026_20261021_scratch1}"
WORKERS="${CAMPAIGN_WORKERS:-2}"
WORKER_CPUS="${CAMPAIGN_WORKER_CPUS:-47}"
JOB_NAME="${CAMPAIGN_SLURM_JOB_NAME:-thesis-rq1}"
ALLOCATION_SCRIPT="${CAMPAIGN_ALLOCATION_SCRIPT:-scripts/compute/slurm/campaigns/run_rq1_pair_allocation.sh}"
OUT_DIR="$REPO/outputs/gpu_campaigns/$CAMPAIGN_ID"
LOG="$OUT_DIR/logs/allocation_supervisor.log"
OVERRIDE_REASON_FILE="$OUT_DIR/reports/resume_fingerprint_override_reason.txt"
NODES=(gpuarm1 gpuarm2)
# Any failed allocation after diagnosis is an early-exit gate: stop and inspect.
NO_PROGRESS_LIMIT=1
MAX_SCHEDULER_WAIT_CHECKS=10
scheduler_wait_checks=0

if [[ -z "${TMUX:-}" ]]; then
  echo "Run this supervisor in a named persistent login tmux session." >&2
  exit 2
fi

cd "$REPO"
mkdir -p "$OUT_DIR/logs"
if [[ -z "${CAMPAIGN_RESUME_FINGERPRINT_OVERRIDE_REASON:-}" && -s "$OVERRIDE_REASON_FILE" ]]; then
  CAMPAIGN_RESUME_FINGERPRINT_OVERRIDE_REASON="$(<"$OVERRIDE_REASON_FILE")"
fi
if [[ -n "${CAMPAIGN_RESUME_FINGERPRINT_OVERRIDE_REASON:-}" ]]; then
  if ((${#CAMPAIGN_RESUME_FINGERPRINT_OVERRIDE_REASON} < 12)); then
    echo "fingerprint override reason must be at least 12 characters" >&2
    exit 2
  fi
  export CAMPAIGN_RESUME_FINGERPRINT_OVERRIDE_REASON
fi
exec >>"$LOG" 2>&1
exec 9>"$OUT_DIR/.allocation_supervisor.lock"
if ! flock -n 9; then
  echo "$(date --iso-8601=seconds) another supervisor owns this campaign; exiting"
  exit 2
fi
echo "$(date --iso-8601=seconds) supervisor start campaign=$CAMPAIGN_ID host=$(hostname -s)"
if [[ -n "${CAMPAIGN_RESUME_FINGERPRINT_OVERRIDE_REASON:-}" ]]; then
  echo "$(date --iso-8601=seconds) fingerprint override reason loaded; continued evidence will be exploratory"
fi

campaign_state() {
  local manifest="$OUT_DIR/campaign.json"
  [[ -s "$manifest" ]] || { echo missing; return; }
  python3 - "$manifest" <<'PY'
import json
import sys
from collections import Counter

counts = Counter(job["status"] for job in json.load(open(sys.argv[1], encoding="utf-8"))["jobs"])
active = sum(counts.get(name, 0) for name in ("pending", "running", "interrupted"))
print(active, counts.get("failed", 0), counts.get("succeeded", 0))
PY
}

checkpoint_signature() {
  local root="$OUT_DIR/runs/attempts"
  [[ -d "$root" ]] || { echo empty; return; }
  find "$root" -type f \( -name 'ppo_ckpt_*_steps.zip' -o -name 'ppo_final.zip' \) \
    -printf '%P %s %T@\n' | sort | sha256sum | awk '{print $1}'
}

node_ready() {
  local node="$1" record
  sinfo -N -n "$node" -o '%N %P %T %C %m %e %G'
  record="$(scontrol show node -o "$node")"
  echo "$(date --iso-8601=seconds) inventory $record"
  squeue -w "$node" -o '%.18i %.10u %.12P %.20j %.8T %.10M %.24R' || true
  printf '%s\n' "$record" | python3 -c '
import sys

fields = dict(token.split("=", 1) for token in sys.stdin.read().split() if "=" in token)
state = fields.get("State", "").split("+", 1)[0]
free_cpus = int(fields.get("CPUEfctv", fields.get("CPUTot", "0"))) - int(fields.get("CPUAlloc", "0"))
free_mem = int(fields.get("RealMemory", "0")) - int(fields.get("AllocMem", "0"))
gres = fields.get("Gres", "")
ready = state == "IDLE" and free_cpus >= 48 and free_mem >= 512 * 1024 and "gpu:gh200:2" in gres
raise SystemExit(0 if ready else 1)
'
}

failures_without_progress=0
while true; do
  state="$(campaign_state)"
  if [[ "$state" == missing ]]; then
    active=1
    failed=0
    succeeded=0
    echo "$(date --iso-8601=seconds) initial manifest not present; allocation may establish it"
  else
    read -r active failed succeeded <<<"$state"
  fi
  echo "$(date --iso-8601=seconds) campaign active=$active failed=$failed succeeded=$succeeded"
  if [[ "$active" == 0 ]]; then
    echo "$(date --iso-8601=seconds) campaign terminal failed=$failed succeeded=$succeeded"
    exit 0
  fi

  jobs="$(squeue -u "${USER:?}" -p gpu-grace-h200-141g -h -o '%i %j %T %N')"
  if [[ -n "$jobs" ]]; then
    if ((scheduler_wait_checks >= MAX_SCHEDULER_WAIT_CHECKS)); then
      echo "$(date --iso-8601=seconds) reached $MAX_SCHEDULER_WAIT_CHECKS scheduler checks; leaving requests and campaign untouched"
      exit 2
    fi
    latest_end=0
    has_pending=0
    while read -r job_id _job_name job_state _node_list; do
      [[ -n "$job_id" ]] || continue
      if [[ "$job_state" == RUNNING ]]; then
        end_time="$(scontrol show job -o "$job_id" | sed -n 's/.*EndTime=\([^ ]*\).*/\1/p')"
        if [[ -n "$end_time" ]]; then
          end_epoch="$(date -d "$end_time" +%s 2>/dev/null || true)"
          if [[ -n "$end_epoch" ]] && ((end_epoch > latest_end)); then
            latest_end="$end_epoch"
          fi
        fi
      else
        has_pending=1
      fi
    done <<<"$jobs"
    printf '%s\n' "$jobs"
    now_epoch="$(date +%s)"
    if ((has_pending == 0 && latest_end > now_epoch)); then
      wait_seconds=$((latest_end - now_epoch - 120))
      ((wait_seconds < 60)) && wait_seconds=60
    else
      wait_seconds=60
    fi
    ((scheduler_wait_checks+=1))
    echo "$(date --iso-8601=seconds) existing allocation observed; next check in ${wait_seconds}s ($scheduler_wait_checks/$MAX_SCHEDULER_WAIT_CHECKS)"
    sleep "$wait_seconds"
    continue
  fi

  nodes_ready=1
  for node in "${NODES[@]}"; do
    if ! node_ready "$node"; then nodes_ready=0; fi
  done
  if [[ "$nodes_ready" != 1 ]]; then
    echo "$(date --iso-8601=seconds) required two-node inventory unavailable; stopping without requesting or modifying jobs"
    exit 2
  fi

  before="$(checkpoint_signature)"
  request_id="$(date +%s)-$$"
  released_marker="$OUT_DIR/reports/allocation_released.$request_id"
  echo "$(date --iso-8601=seconds) requesting one GH200/node, 48 CPUs and 512G/node, 6h"
  set +e
  srun \
    --immediate=60 \
    --partition=gpu-grace-h200-141g \
    --nodes=2 --nodelist=gpuarm1,gpuarm2 \
    --ntasks=2 --ntasks-per-node=1 \
    --cpus-per-task=48 --gpus-per-node=gh200:1 --mem=512G \
    --time=06:00:00 --job-name="$JOB_NAME" \
    --export=ALL,TRITON_REPO="$REPO",CAMPAIGN_SPEC="$SPEC",CAMPAIGN_ID="$CAMPAIGN_ID",RQ1_WORKERS="$WORKERS",CAMPAIGN_WORKERS="$WORKERS",CAMPAIGN_WORKER_CPUS="$WORKER_CPUS",CAMPAIGN_ALLOCATION_REQUEST_ID="$request_id" \
    --chdir="$REPO" \
    bash "$REPO/$ALLOCATION_SCRIPT"
  rc=$?
  set -e
  echo "$(date --iso-8601=seconds) allocation returned exit=$rc"
  if [[ -e "$released_marker" ]]; then
    echo "$(date --iso-8601=seconds) allocation explicitly released; supervisor will not reacquire"
    exit 0
  fi

  state="$(campaign_state)"
  if [[ "$state" == missing ]]; then
    active=1
    failed=0
    succeeded=0
  else
    read -r active failed succeeded <<<"$state"
  fi
  echo "$(date --iso-8601=seconds) post-allocation active=$active failed=$failed succeeded=$succeeded"
  if [[ "$active" == 0 ]]; then
    echo "$(date --iso-8601=seconds) campaign terminal failed=$failed succeeded=$succeeded"
    exit 0
  fi
  after="$(checkpoint_signature)"
  if [[ "$after" != "$before" ]]; then
    failures_without_progress=0
    echo "$(date --iso-8601=seconds) checkpoint progress observed"
  elif ((rc != 0)); then
    ((failures_without_progress+=1))
    echo "$(date --iso-8601=seconds) no checkpoint progress; failures=$failures_without_progress/$NO_PROGRESS_LIMIT"
    if ((failures_without_progress >= NO_PROGRESS_LIMIT)); then
      echo "$(date --iso-8601=seconds) stopping reacquisition for diagnosis; campaign and artifacts preserved"
      exit 2
    fi
  else
    failures_without_progress=0
  fi
done
