#!/usr/bin/env bash
# WP3 feasibility only: benchmark the stock 64-env collector against inference
# pipelining by logical env cohorts. Run inside an existing GH200 allocation.
# This script never submits Slurm work and never modifies production collectors.
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
OUTPUT_ROOT="docs/research/gh200_pipelined_ppo_refactor_20261028/measurements"
REPORT_DIR="$OUTPUT_ROOT/wp3-job-${SLURM_JOB_ID:-local}"
THROUGHPUT_SCRIPT="$REPO_ROOT/scripts/research/benchmarks/measure_ppo_throughput.py"
TIMESTEPS=81920 # 5 full 16,384-transition rollouts: 2 warmups, 3 measured.

mkdir -p "$REPORT_DIR"
{
    printf 'job_id=%s\nnode=%s\nstart=%s\ncommit=%s\n' \
        "${SLURM_JOB_ID:-none}" "$(hostname)" "$(date --iso-8601=seconds)" "$(git rev-parse HEAD)"
    printf 'cpus=%s\nmem=%s\ncuda_visible_devices=%s\n' \
        "${SLURM_CPUS_PER_TASK:-unset}" "${SLURM_MEM_PER_NODE:-unset}" "${CUDA_VISIBLE_DEVICES:-unset}"
    printf '\nslurm job:\n'
    if [[ -n "${SLURM_JOB_ID:-}" ]]; then scontrol show job "$SLURM_JOB_ID"; fi
} > "$REPORT_DIR/allocation.txt" 2>&1

BUNDLE_MANIFEST="$BUNDLE_DIR/manifest.json"
test -r "$BUNDLE_MANIFEST"
ACTUAL_BUNDLE_SHA256="$(sha256sum "$BUNDLE_MANIFEST" | cut -d ' ' -f 1)"
if [[ "$ACTUAL_BUNDLE_SHA256" != "$EXPECTED_BUNDLE_SHA256" ]]; then
    echo "Unexpected shared bundle hash: $ACTUAL_BUNDLE_SHA256" >&2
    exit 2
fi

"$VIRTUAL_ENV/bin/python" - <<'PY' > "$REPORT_DIR/runtime-preflight.txt" 2>&1
import os
import platform
import sys
import torch

print(f"architecture={platform.machine()}")
print(f"python={sys.executable}")
print(f"venv={os.environ.get('VIRTUAL_ENV')}")
print(f"torch={torch.__version__}")
print(f"cuda_available={torch.cuda.is_available()}")
if platform.machine() != "aarch64" or not torch.cuda.is_available():
    raise SystemExit("WP3 requires the ARM GH200 allocation and CUDA")
print(f"gpu={torch.cuda.get_device_name(0)}")
print(f"cuda_capability={torch.cuda.get_device_capability(0)}")
PY
nvidia-smi -q > "$REPORT_DIR/nvidia-smi-before.txt"

run_case() {
    local label="$1" seed="$2" cohort_count="$3" profile="$4" validate="$5"
    local output="$REPORT_DIR/${label}.json"
    local -a extra=(--cohort-count "$cohort_count" --measure-env-steps)
    if [[ "$profile" == "yes" ]]; then extra+=(--profile-phases); fi
    if [[ "$validate" == "yes" ]]; then extra+=(--validate-cohort-thesis-masks); fi
    printf 'START label=%s seed=%s cohorts=%s time=%s\n' "$label" "$seed" "$cohort_count" "$(date --iso-8601=seconds)"
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

run_validation_smoke() {
    local label="cohort2-contract-smoke"
    local output="$REPORT_DIR/${label}.json"
    printf 'START label=%s time=%s\n' "$label" "$(date --iso-8601=seconds)"
    "$VIRTUAL_ENV/bin/python" "$THROUGHPUT_SCRIPT" \
        --device cuda --seed 42 \
        --config "$CONFIG_PATH" --bundle-dir "$BUNDLE_DIR" \
        --cohort-count 2 --validate-cohort-thesis-masks \
        --total-timesteps 16384 --warmup-rollouts 0 --output "$output" \
        > "$REPORT_DIR/${label}.log" 2>&1
    printf 'FINISH label=%s time=%s\n' "$label" "$(date --iso-8601=seconds)"
}

# A single full rollout verifies 109-way masked actions, preserved row order in
# PPO's action buffer, finite rewards/GAE, terminations, and the update barrier.
run_validation_smoke

# Detailed baseline profile is separate from FPS comparisons because profiler
# instrumentation perturbs the run. It records policy, worker, IPC, and wait data.
run_case sequential64-profile 42 1 yes no

# Matched, unprofiled core throughput repeats. All cases keep 64 envs, 256
# transitions/env/update, batch 4096, 15 epochs, same dataset and paired seeds.
for seed in 42 43 44; do
    run_case "sequential64-seed${seed}" "$seed" 1 no no
    run_case "pipeline2x32-seed${seed}" "$seed" 2 no no
    run_case "pipeline4x16-seed${seed}" "$seed" 4 no no
done

"$VIRTUAL_ENV/bin/python" scripts/research/benchmarks/summarize_wp3_cohort_feasibility.py \
    "$REPORT_DIR" --output "$REPORT_DIR/RESULTS.md" \
    > "$REPORT_DIR/summarize.log" 2>&1
printf 'finish=%s\n' "$(date --iso-8601=seconds)" >> "$REPORT_DIR/allocation.txt"
echo "WP3_COMPLETE report_dir=$REPORT_DIR"
