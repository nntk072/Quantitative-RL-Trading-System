#!/usr/bin/env bash
# Reacquire the approved two-node shape and resume the verified 18-run matrix.
set -Eeuo pipefail

REPO="${TRITON_REPO:-$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)}"
SPEC="${EXPERIMENT_RUN_SPEC:-config/experiment_runs/18_variant_seed42_20m_policy_migration_nenv64_20261014.yaml}"
EXPERIMENT_RUN_ID="ladder18_seed42_20m_policy_migration_nenv64_20261014"
OUT_DIR="$REPO/outputs/experiment_runs/$EXPERIMENT_RUN_ID"
LOG="$OUT_DIR/logs/allocation_supervisor.log"
MAX_ERRORS="${MAX_ALLOCATION_ERRORS:-3}"
mkdir -p "$(dirname "$LOG")"
exec >>"$LOG" 2>&1
echo "$(date --iso-8601=seconds) VecEnv-resume supervisor start host=$(hostname -s)"

# A second login shell can start the same continuation while the first `srun`
# is blocked in the queue. Lock the shared experiment run directory before it can
# submit, so only one supervisor owns this experiment run across login hosts.
exec 9>"$OUT_DIR/.allocation_supervisor.lock"
if ! flock -n 9; then
  echo "$(date --iso-8601=seconds) another supervisor already owns this experiment run; exiting"
  exit 0
fi

read_state() {
  [[ -s "$OUT_DIR/experiment_run.json" ]] || { echo missing; return; }
  # The login host may inherit an AArch64 venv path; use its system Python.
  PATH=/usr/bin:/bin python3 - "$OUT_DIR/experiment_run.json" <<'PY'
import json, sys
from collections import Counter
counts = Counter(job["status"] for job in json.load(open(sys.argv[1], encoding="utf-8"))["jobs"])
active = sum(counts.get(name, 0) for name in ("pending", "running", "interrupted"))
print(active, counts.get("failed", 0), counts.get("succeeded", 0))
PY
}

checkpoint_signature() {
  local root="$OUT_DIR/runs/attempts"
  if [[ ! -d "$root" ]]; then
    echo missing
    return
  fi
  find "$root" -type f -name 'ppo_ckpt_*_steps.zip' \
    -printf '%P %s %T@\n' | sort | sha256sum | awk '{print $1}'
}

old_experiment_run_active() {
  if pgrep -f '[r]un_experiment_run_18way_two_node_supervisor.sh' >/dev/null; then
    return 0
  fi
  local queued
  if ! queued="$(squeue -u "${USER:?}" -h -o '%j %T')"; then
    echo "$(date --iso-8601=seconds) cannot verify old allocation status; waiting" >&2
    return 0
  fi
  printf '%s\n' "$queued" | awk '
    $1 ~ /^thesis18(x2|vec)$/ && ($2 == "RUNNING" || $2 == "PENDING" || $2 == "CONFIGURING") { found=1 }
    END { exit !found }
  '
}

errors=0
while true; do
  state="$(read_state)"
  if [[ "$state" != missing ]]; then
    read -r active failed succeeded <<<"$state"
    echo "$(date --iso-8601=seconds) experiment run active=$active failed=$failed succeeded=$succeeded"
    if [[ "$active" == 0 ]]; then
      [[ "$failed" == 0 && "$succeeded" == 18 ]] && exit 0
      exit 1
    fi
  fi

  if old_experiment_run_active; then
    echo "$(date --iso-8601=seconds) waiting for the original experiment run organizer/allocation to stop"
    sleep 60
    continue
  fi

  echo "$(date --iso-8601=seconds) requesting two nodes, one GH200/node, 48 CPUs and 512G/node, 6h"
  checkpoints_before="$(checkpoint_signature)"
  set +e
  srun \
    --partition=gpu-grace-h200-141g \
    --nodes=2 --ntasks=2 --ntasks-per-node=1 \
    --cpus-per-task=48 --gpus-per-node=gh200:1 --mem=512G \
    --time=06:00:00 --job-name=thesis18vec \
    --export=ALL,TRITON_REPO="$REPO",EXPERIMENT_RUN_SPEC="$SPEC" \
    --chdir="$REPO" \
    bash scripts/compute/slurm/experiment_runs/run_18way_vector_resume_allocation.sh
  rc=$?
  set -e
  echo "$(date --iso-8601=seconds) allocation returned exit=$rc"

  state="$(read_state)"
  if [[ "$state" == missing ]]; then
    ((errors+=1))
    if (( errors >= MAX_ERRORS )); then echo "retry limit reached before experiment run manifest"; exit 2; fi
    sleep "$((120 * errors))"
    continue
  fi
  read -r active failed succeeded <<<"$state"
  echo "$(date --iso-8601=seconds) experiment run after allocation active=$active failed=$failed succeeded=$succeeded"
  if [[ "$active" == 0 ]]; then
    [[ "$failed" == 0 && "$succeeded" == 18 ]] && exit 0
    exit 1
  fi
  checkpoints_after="$(checkpoint_signature)"
  if [[ "$checkpoints_after" != "$checkpoints_before" ]]; then
    echo "$(date --iso-8601=seconds) allocation made checkpoint progress; resetting no-progress error count"
    errors=0
  elif (( rc != 0 )); then
    ((errors+=1))
    echo "$(date --iso-8601=seconds) no new checkpoint; consecutive allocation errors=$errors/$MAX_ERRORS"
  else
    errors=0
  fi
  if (( errors >= MAX_ERRORS )); then echo "no-progress allocation retry limit reached; inspect this log"; exit 2; fi
  sleep 30
done
