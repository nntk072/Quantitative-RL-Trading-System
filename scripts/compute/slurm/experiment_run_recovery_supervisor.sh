#!/usr/bin/env bash
# Bootstrap one guarded allocation for cache recovery and the GPU CI gate.
# Once that allocation is released, hand continuity to the experiment run supervisor.
set -Eeuo pipefail

REPO="${TRITON_REPO:-$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)}"
SPEC="${EXPERIMENT_RUN_SPEC:-config/experiment_runs/18_variant_seed50_20m_full_split_n64_cpumask_v3_20261016.yaml}"
EXPERIMENT_RUN_ID="${EXPERIMENT_RUN_ID:-ladder18_seed50_20m_full_split_n64_cpumask_v3_20261016}"
SOURCE_EXPERIMENT_RUN="${SOURCE_EXPERIMENT_RUN:-$REPO/outputs/experiment_runs/ladder18_seed50_20m_full_split_n64_mainplan_20261016}"
OUT_DIR="$REPO/outputs/experiment_runs/$EXPERIMENT_RUN_ID"
LOG="$OUT_DIR/logs/allocation_supervisor.log"
mkdir -p "$(dirname "$LOG")"
exec >>"$LOG" 2>&1
echo "$(date --iso-8601=seconds) guarded recovery bootstrap start host=$(hostname -s)"

exec 9>"$OUT_DIR/.allocation_supervisor.lock"
if ! flock -n 9; then
  echo "$(date --iso-8601=seconds) another supervisor owns this experiment run; exiting"
  exit 0
fi

if [[ -s "$OUT_DIR/experiment_run.json" ]]; then
  state="$(python3 - "$OUT_DIR/experiment_run.json" <<'PY'
import json, sys
from collections import Counter
counts = Counter(job["status"] for job in json.load(open(sys.argv[1], encoding="utf-8"))["jobs"])
print(sum(counts.get(name, 0) for name in ("pending", "running", "interrupted")),
      counts.get("failed", 0), counts.get("succeeded", 0))
PY
)"
  read -r active failed succeeded <<<"$state"
  echo "$(date --iso-8601=seconds) preflight experiment run active=$active failed=$failed succeeded=$succeeded"
  if [[ "$active" == 0 && "$failed" == 18 && "$succeeded" == 0 ]]; then
    echo "$(date --iso-8601=seconds) requesting one guarded 2-node GH200 recovery allocation"
    srun \
      --partition=gpu-grace-h200-141g \
      --nodes=2 --ntasks=2 --ntasks-per-node=1 \
      --cpus-per-task=48 --gpus-per-node=gh200:1 --mem=512G \
      --time=06:00:00 --job-name=thesis18maskv3 \
      --export=ALL,TRITON_REPO="$REPO",EXPERIMENT_RUN_SPEC="$SPEC",EXPERIMENT_RUN_ID="$EXPERIMENT_RUN_ID",SOURCE_EXPERIMENT_RUN="$SOURCE_EXPERIMENT_RUN" \
      --chdir="$REPO" \
      bash "$REPO/scripts/compute/slurm/experiment_runs/run_18way_cpumask_allocation.sh"
    echo "$(date --iso-8601=seconds) bootstrap allocation returned; handing off to experiment run supervisor"
  fi
fi

exec bash "$REPO/scripts/compute/slurm/experiment_runs/run_18way_cpumask_supervisor.sh"
