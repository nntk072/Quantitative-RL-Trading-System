#!/usr/bin/env bash
# Run or resume the seed-42 18-variant experiment run under full-split episodes.
set -Eeuo pipefail

REPO="${TRITON_REPO:-/scratch/work/nguyenl37/Aalto_MS_Thesis}"
SPEC="${EXPERIMENT_RUN_SPEC:-config/experiment_runs/18_variant_seed42_20m_full_split_n64_20261015.yaml}"
EXPERIMENT_RUN_ID="${EXPERIMENT_RUN_ID:-ladder18_seed42_20m_full_split_n64_20261015}"
OUT_DIR="$REPO/outputs/experiment_runs/$EXPERIMENT_RUN_ID"
DONE_MARKER="$OUT_DIR/allocation_controller.exit"

cd "$REPO"
mkdir -p "$OUT_DIR/logs"
if [[ "${SLURM_PROCID:-0}" != "0" ]]; then
  while [[ ! -e "$DONE_MARKER" ]]; do sleep 10; done
  exit 0
fi

rm -f "$DONE_MARKER"
trap 'touch "$DONE_MARKER"' EXIT
source "$REPO/scripts/compute/slurm/activate_venv.sh"

python - "$REPO/config/base/default.yaml" <<'PY'
import sys
import yaml

with open(sys.argv[1], encoding="utf-8") as handle:
    config = yaml.safe_load(handle)
training = config.get("training", {})
if training.get("episode_mode") != "full_split":
    raise SystemExit("fresh full-year experiment run requires training.episode_mode=full_split")
if config.get("env", {}).get("max_episode_steps") is not None:
    raise SystemExit("full-split episodes require env.max_episode_steps=null")
PY

resume_args=()
if [[ -s "$OUT_DIR/experiment_run.json" ]]; then
  resume_args+=(--resume)
fi

set +e
timeout --signal=TERM --kill-after=2m 20700s \
  python "$REPO/experiments/runs/execution.py" \
  --experiment-run-spec "$REPO/$SPEC" \
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

echo "Full-split allocation controller exit=$status; checkpoint state is retained."
exit "$status"
