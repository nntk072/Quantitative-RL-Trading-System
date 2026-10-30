#!/usr/bin/env bash
# Run/resume the seed-50 18-variant experiment run with disjoint per-worker CPU masks.
set -Eeuo pipefail

REPO="${TRITON_REPO:-/scratch/work/nguyenl37/Aalto_MS_Thesis}"
SPEC="${EXPERIMENT_RUN_SPEC:-config/experiment_runs/18_variant_seed50_20m_full_split_n64_cpumask_v3_20261016.yaml}"
EXPERIMENT_RUN_ID="${EXPERIMENT_RUN_ID:-ladder18_seed50_20m_full_split_n64_cpumask_v3_20261016}"
SOURCE_EXPERIMENT_RUN="${SOURCE_EXPERIMENT_RUN:-$REPO/outputs/experiment_runs/ladder18_seed50_20m_full_split_n64_mainplan_20261016}"
OUT_DIR="$REPO/outputs/experiment_runs/$EXPERIMENT_RUN_ID"
CHECKPOINT_MAP="$OUT_DIR/initial_checkpoints.json"
DONE_MARKER="$OUT_DIR/allocation_controller.exit"
PREFLIGHT_MARKER="$OUT_DIR/gpu_ci_gate.passed"
PREFLIGHT_FAILED="$OUT_DIR/gpu_ci_gate.failed"
START_MARKER="$OUT_DIR/start_training_after_commit"
CURRENT_SOURCE_SHA="$(git -C "$REPO" rev-parse HEAD)"

cd "$REPO"
mkdir -p "$OUT_DIR/logs"
if [[ "${SLURM_PROCID:-0}" != "0" ]]; then
  while [[ ! -e "$DONE_MARKER" ]]; do sleep 10; done
  exit 0
fi

rm -f "$DONE_MARKER"
trap 'touch "$DONE_MARKER"' EXIT
source "$REPO/scripts/compute/slurm/activate_venv.sh"

if [[ ! -s "$PREFLIGHT_MARKER" \
  || "$(cat "$PREFLIGHT_MARKER")" != "$CURRENT_SOURCE_SHA" \
  || -n "$(git -C "$REPO" status --porcelain)" ]]; then
  retry=1
  while true; do
    if TRITON_REPO="$REPO" EXPERIMENT_RUN_OUT_DIR="$OUT_DIR" \
      bash "$REPO/scripts/compute/slurm/experiment_runs/validate_cpu_mask_experiment_run_gpu.sh"; then
      git -C "$REPO" rev-parse HEAD > "$PREFLIGHT_MARKER"
      break
    fi
    touch "$PREFLIGHT_FAILED"
    retry_marker="$OUT_DIR/retry_gpu_ci_gate.$retry"
    echo "GPU CI gate failed; fix the cause, then touch $retry_marker"
    while [[ ! -e "$retry_marker" ]]; do sleep 20; done
    mv "$retry_marker" "$retry_marker.consumed"
    ((retry+=1))
  done
fi

echo "GPU checks passed; waiting for the agent commit/push gate before training."
while [[ ! -e "$START_MARKER" ]]; do sleep 20; done
if [[ -n "$(git -C "$REPO" status --porcelain)" ]]; then
  echo "ERROR: refusing to train from an uncommitted worktree" >&2
  exit 2
fi
git -C "$REPO" rev-parse HEAD > "$PREFLIGHT_MARKER"

if [[ ! -s "$CHECKPOINT_MAP" ]]; then
  retry=1
  while true; do
    if python "$REPO/experiments/runs/checkpoints.py" \
      --source-experiment-run "$SOURCE_EXPERIMENT_RUN" \
      --variant-file "$REPO/config/experiment_runs/variant_list.txt" \
      --seeds 50 \
      --timesteps 20000000 \
      --output "$CHECKPOINT_MAP" \
      2>&1 | tee -a "$OUT_DIR/logs/checkpoint_lineage.log"; then
      break
    fi
    retry_marker="$OUT_DIR/retry_checkpoint_lineage.$retry"
    echo "Checkpoint-lineage validation failed; fix the cause, then touch $retry_marker"
    while [[ ! -e "$retry_marker" ]]; do sleep 20; done
    mv "$retry_marker" "$retry_marker.consumed"
    ((retry+=1))
  done
fi

resume_args=()
if [[ -s "$OUT_DIR/experiment_run.json" ]]; then
  resume_args+=(--resume)
fi

set +e
timeout --signal=TERM --kill-after=2m 20700s \
  python "$REPO/experiments/runs/execution.py" \
  --experiment-run-spec "$REPO/$SPEC" \
  --initial-checkpoints "$CHECKPOINT_MAP" \
  "${resume_args[@]}" \
  --workers 18 \
  --n-envs 64 \
  --worker-nodes "${SLURM_JOB_NODELIST:?}" \
  --worker-cpus 5 \
  --worker-gpu-type gh200 \
  --worker-gpus-per-node 1 \
  --fast-reports \
  2>&1 | tee -a "$OUT_DIR/logs/controller.log"
status=${PIPESTATUS[0]}
set -e

echo "CPU-mask experiment run allocation controller exit=$status; checkpoint lineage is retained."
exit "$status"
