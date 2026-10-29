#!/usr/bin/env bash
# Bounded lossless compact-observation transport A/B. Run inside an existing
# GH200 allocation; this script does not request Slurm resources or rebuild data.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$REPO_ROOT"
export TRITON_REPO="$REPO_ROOT"
export AARCH64_VENV="${AARCH64_VENV:-/scratch/work/nguyenl37/Quantitative-RL-Trading-System/.venv}"
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
source "$REPO_ROOT/scripts/compute/slurm/activate_venv.sh"

EXPECTED_BUNDLE_SHA256="d85e0dc8fa241c66d4d727dd4be5d463fc58dbbbd53a43fd00d75100387b052e"
BUNDLE_DIR="${BUNDLE_DIR:-/scratch/work/nguyenl37/Quantitative-RL-Trading-System/cache/train_test_2025_2026/shared_env/e9d5a63f864394ddad5acfb73f184444a6293295e1bbeff6313d1bc5d842a28c}"
CONFIG_PATH="config/research/thesis_mtf_shared_tcn_2m_high_throughput.yaml"
REPORT_DIR="docs/research/gh200_pipelined_ppo_refactor_20261028/measurements/compact-obs-job-${SLURM_JOB_ID:-local}"
THROUGHPUT_SCRIPT="$REPO_ROOT/scripts/research/benchmarks/measure_ppo_throughput.py"
TIMESTEPS=81920 # 2 warmup plus 3 timed 16,384-transition rollouts.

mkdir -p "$REPORT_DIR"
ACTUAL_BUNDLE_SHA256="$(sha256sum "$BUNDLE_DIR/manifest.json" | cut -d ' ' -f 1)"
if [[ "$ACTUAL_BUNDLE_SHA256" != "$EXPECTED_BUNDLE_SHA256" ]]; then
    echo "Unexpected shared bundle hash: $ACTUAL_BUNDLE_SHA256" >&2
    exit 2
fi

"$VIRTUAL_ENV/bin/python" - <<'PY' > "$REPORT_DIR/runtime.txt" 2>&1
import platform
import torch

print(f"architecture={platform.machine()}")
print(f"torch={torch.__version__}")
print(f"cuda_available={torch.cuda.is_available()}")
if platform.machine() != "aarch64" or not torch.cuda.is_available():
    raise SystemExit("compact transport A/B requires the ARM GH200 allocation")
print(f"gpu={torch.cuda.get_device_name(0)}")
PY

run_case() {
    local mode="$1" seed="$2"
    local label="${mode}-seed${seed}"
    local output="$REPORT_DIR/${label}.json"
    local -a extra=(--measure-env-steps)
    if [[ "$mode" == "compact" ]]; then extra+=(--compact-observation-transport); fi
    printf 'START label=%s seed=%s time=%s\n' "$label" "$seed" "$(date --iso-8601=seconds)"
    "$VIRTUAL_ENV/bin/python" "$THROUGHPUT_SCRIPT" \
        --device cuda \
        --seed "$seed" \
        --config "$CONFIG_PATH" \
        --bundle-dir "$BUNDLE_DIR" \
        --total-timesteps "$TIMESTEPS" \
        --warmup-rollouts 2 \
        --output "$output" \
        "${extra[@]}" \
        > "$REPORT_DIR/${label}.log" 2>&1
    printf 'FINISH label=%s time=%s\n' "$label" "$(date --iso-8601=seconds)"
}

for seed in 42 43 44; do
    run_case stock "$seed"
    run_case compact "$seed"
done

"$VIRTUAL_ENV/bin/python" scripts/research/benchmarks/summarize_compact_observation_transport.py \
    "$REPORT_DIR" --output "$REPORT_DIR/RESULTS.md"
echo "COMPACT_OBSERVATION_TRANSPORT_COMPLETE report_dir=$REPORT_DIR"
