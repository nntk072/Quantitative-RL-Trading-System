#!/usr/bin/env bash
# Throughput probe on a GPU node, following the production training configuration.
#
# Usage (inside an existing GPU allocation):
#   BUNDLE_DIR=cache/shared_env/<key> VARIANT=ladder_a2_tp bash scripts/research/benchmarks/run_fps_probe.sh 200000
#
# BUNDLE_DIR is required: the bundle key depends on the variant's features and
# strategy, so a hard-coded path from another configuration would measure the
# wrong environment. Build it once per variant with train_rl, then point here.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$REPO_ROOT"
export TRITON_REPO="$REPO_ROOT"

TOTAL_TIMESTEPS="${1:-100000}"
: "${BUNDLE_DIR:?set BUNDLE_DIR to an existing shared env bundle for this variant}"
VARIANT="${VARIANT:-}"
CONFIG_PATH="${CONFIG_PATH:-}"

if [[ -n "$VARIANT" && -n "$CONFIG_PATH" ]]; then
    echo "ERROR: set either VARIANT or CONFIG_PATH, not both" >&2
    exit 2
fi

RUN_LABEL="${VARIANT:-${CONFIG_PATH##*/}}"
RUN_LABEL="${RUN_LABEL%.yaml}"
RUN_LABEL="${RUN_LABEL:-default}"
OUT="${OUT:-outputs/fps_$(hostname)_${RUN_LABEL}.json}"

source "$REPO_ROOT/scripts/compute/slurm/activate_venv.sh"
mkdir -p "$(dirname "$OUT")"

echo "HOST=$(hostname) VARIANT=${VARIANT:-default} CONFIG_PATH=${CONFIG_PATH:-default} BUNDLE_DIR=$BUNDLE_DIR"
VARIANT_ARGS=()
[[ -n "$VARIANT" ]] && VARIANT_ARGS=(--variant "$VARIANT")
CONFIG_ARGS=()
[[ -n "$CONFIG_PATH" ]] && CONFIG_ARGS=(--config "$CONFIG_PATH")
PROFILE_ARGS=()
[[ -n "${N_ENVS:-}" ]] && PROFILE_ARGS+=(--n-envs "$N_ENVS")
[[ -n "${ROLLOUT_STEPS_PER_ENV:-}" ]] && \
    PROFILE_ARGS+=(--rollout-steps-per-env "$ROLLOUT_STEPS_PER_ENV")
[[ -n "${BATCH_SIZE:-}" ]] && PROFILE_ARGS+=(--batch-size "$BATCH_SIZE")

"$VIRTUAL_ENV/bin/python" "$REPO_ROOT/scripts/research/benchmarks/measure_ppo_throughput.py" \
    --device cuda \
    --total-timesteps "$TOTAL_TIMESTEPS" \
    --bundle-dir "$BUNDLE_DIR" \
    "${CONFIG_ARGS[@]}" \
    "${VARIANT_ARGS[@]}" \
    "${PROFILE_ARGS[@]}" \
    --output "$OUT"
echo "EXIT=0"
