#!/usr/bin/env bash
# Sequential E64 profiling and worker-topology screen for the GH200 PPO plan.
# Run once inside one approved, persistent GH200 allocation. This script never
# submits Slurm work or changes the active C/D jobs.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$REPO_ROOT"
export TRITON_REPO="$REPO_ROOT"
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1

source "$REPO_ROOT/scripts/compute/slurm/activate_venv.sh"

EXPECTED_BUNDLE_SHA256="d85e0dc8fa241c66d4d727dd4be5d463fc58dbbbd53a43fd00d75100387b052e"
BUNDLE_DIR="${BUNDLE_DIR:-/scratch/work/nguyenl37/Quantitative-RL-Trading-System/cache/train_test_2025_2026/shared_env/e9d5a63f864394ddad5acfb73f184444a6293295e1bbeff6313d1bc5d842a28c}"
CONFIG_PATH="config/research/thesis_mtf_shared_tcn_2m_high_throughput.yaml"
OUTPUT_ROOT="docs/research/gh200_pipelined_ppo_refactor_20261028/measurements"
REPORT_DIR="$OUTPUT_ROOT/wp0-job-${SLURM_JOB_ID:-local}"
THROUGHPUT_SCRIPT="$REPO_ROOT/scripts/research/benchmarks/measure_ppo_throughput.py"
TIMESTEPS=65536

mkdir -p "$REPORT_DIR"
printf 'host=%s\njob_id=%s\ncommit=%s\n' \
    "$(hostname)" "${SLURM_JOB_ID:-none}" "$(git rev-parse HEAD)" > "$REPORT_DIR/run.txt"
git status --short >> "$REPORT_DIR/run.txt"
TRACKED_DIFF_SHA256="$(git diff --binary HEAD | sha256sum | cut -d ' ' -f 1)"
printf 'tracked_diff_sha256=%s\n' "$TRACKED_DIFF_SHA256" >> "$REPORT_DIR/run.txt"

BUNDLE_MANIFEST="$BUNDLE_DIR/manifest.json"
test -r "$BUNDLE_MANIFEST"
ACTUAL_BUNDLE_SHA256="$(sha256sum "$BUNDLE_MANIFEST" | cut -d ' ' -f 1)"
if [[ "$ACTUAL_BUNDLE_SHA256" != "$EXPECTED_BUNDLE_SHA256" ]]; then
    echo "Unexpected shared bundle hash: $ACTUAL_BUNDLE_SHA256" >&2
    exit 2
fi

{
    uname -a
    lscpu
    printf '\nSLURM_CPUS_PER_TASK=%s\nCUDA_VISIBLE_DEVICES=%s\n' \
        "${SLURM_CPUS_PER_TASK:-unset}" "${CUDA_VISIBLE_DEVICES:-unset}"
    for tool in cc gcc clang nvcc ptxas nsys ncu; do
        printf '%s=' "$tool"
        command -v "$tool" || true
    done
    printf '\nCPU cgroup:\n'
    for path in /sys/fs/cgroup/cpu.max /sys/fs/cgroup/cpuset.cpus.effective; do
        if [[ -r "$path" ]]; then
            printf '%s: ' "$path"
            cat "$path"
        fi
    done
    nvidia-smi -q
    if command -v nsys >/dev/null 2>&1; then
        printf '\nNsight Systems environment:\n'
        nsys status --environment || true
    fi
} > "$REPORT_DIR/node-and-toolchain.txt" 2>&1

"$VIRTUAL_ENV/bin/python" - <<'PY' > "$REPORT_DIR/runtime-preflight.txt" 2>&1
import os
import platform
import sys
import torch

print(f"architecture={platform.machine()}")
print(f"python_executable={sys.executable}")
print(f"checkout={os.environ.get('TRITON_REPO')}")
print(f"venv={os.environ.get('VIRTUAL_ENV')}")
print(f"torch={torch.__version__}")
print(f"cuda_available={torch.cuda.is_available()}")
if not torch.cuda.is_available():
    raise SystemExit("CUDA is required for this profile")
print(f"gpu={torch.cuda.get_device_name(0)}")
print(f"cuda_capability={torch.cuda.get_device_capability(0)}")
PY

run_case() {
    local label="$1"
    shift
    local output="$REPORT_DIR/${label}.json"
    echo "START case=$label at=$(date --iso-8601=seconds)"
    "$VIRTUAL_ENV/bin/python" "$THROUGHPUT_SCRIPT" \
        --device cuda \
        --seed 42 \
        --config "$CONFIG_PATH" \
        --bundle-dir "$BUNDLE_DIR" \
        --total-timesteps "$TIMESTEPS" \
        --warmup-rollouts 2 \
        --output "$output" \
        "$@"
    echo "FINISH case=$label at=$(date --iso-8601=seconds)"
}

# Reuse the three immutable E64 high-geometry baseline repeats already
# measured on this bundle and seed. They used the production E config plus
# the same seven geometry overrides now represented by the explicit overlay.
# The config-equivalence test guards that relationship; do not spend another
# three runs remeasuring an established baseline.
BASELINE_SOURCE="docs/research/gh200_max_fps_architecture_redesign_20261028/measurements"
cp "$BASELINE_SOURCE/E64-high.json" \
    "$REPORT_DIR/e64-high-baseline-repeat1.json"
cp "$BASELINE_SOURCE/E64-high-baseline-repeat2.json" \
    "$REPORT_DIR/e64-high-baseline-repeat2.json"
cp "$BASELINE_SOURCE/E64-high-baseline-repeat3.json" \
    "$REPORT_DIR/e64-high-baseline-repeat3.json"
{
    printf 'baseline_source=%s\n' "$BASELINE_SOURCE"
    sha256sum \
        "$BASELINE_SOURCE/E64-high.json" \
        "$BASELINE_SOURCE/E64-high-baseline-repeat2.json" \
        "$BASELINE_SOURCE/E64-high-baseline-repeat3.json"
} > "$REPORT_DIR/baseline-source.txt"

# Run the phase profile and 64-subprocess comparison concurrently, one case
# per allocated GPU. Each has the same env count, rollout, batch, epochs, seed,
# bundle and step cap, with two warmup and two measured rollouts. Treat the
# topology difference as directional because this is a single short pass.
IFS=',' read -r -a allocated_gpus <<< "${CUDA_VISIBLE_DEVICES:-}"
if (( ${#allocated_gpus[@]} < 2 )); then
    echo "Expected two allocated GPUs, got CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-unset}" >&2
    exit 2
fi

(
    CUDA_VISIBLE_DEVICES="${allocated_gpus[0]}" \
        run_case e64-high-phase-profile --profile-phases
) > "$REPORT_DIR/e64-high-phase-profile.log" 2>&1 &
profile_pid=$!
(
    CUDA_VISIBLE_DEVICES="${allocated_gpus[1]}" \
        run_case e64-high-subproc64 --overrides env.vector_backend=subproc
) > "$REPORT_DIR/e64-high-subproc64.log" 2>&1 &
subproc_pid=$!

profile_status=0
subproc_status=0
wait "$profile_pid" || profile_status=$?
wait "$subproc_pid" || subproc_status=$?
if (( profile_status != 0 || subproc_status != 0 )); then
    printf 'phase_profile_exit=%s\nsubproc64_exit=%s\n' \
        "$profile_status" "$subproc_status" > "$REPORT_DIR/case-status.txt"
    exit 1
fi

printf 'nsys=not run in the short measurement scope; SM-active and detailed transfer metrics remain UNKNOWN\n' \
    > "$REPORT_DIR/nsys-status.txt"

"$VIRTUAL_ENV/bin/python" scripts/research/benchmarks/summarize_pipelined_ppo_wp0.py \
    "$REPORT_DIR" --output "$REPORT_DIR/RESULTS.md" \
    > "$REPORT_DIR/summarize.txt" 2>&1

# The already-submitted Slurm wrapper captured an earlier focused-test list.
# Run the full current focused set in this same allocation, without creating
# another Slurm step; the wrapper still supplies the full-tree Ruff/Mypy gates.
"$VIRTUAL_ENV/bin/pytest" \
    tests/test_train/test_mtf_benchmark_configs.py \
    tests/test_bench/test_measure_ppo_throughput.py \
    tests/test_bench/test_summarize_pipelined_ppo_wp0.py \
    tests/test_compute_contracts.py \
    -q > "$REPORT_DIR/focused-pytest-current.txt" 2>&1

echo "COMPLETE report_dir=$REPORT_DIR at=$(date --iso-8601=seconds)"
