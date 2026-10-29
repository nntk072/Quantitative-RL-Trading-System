#!/usr/bin/env bash
# Two-GH200 bounded measurement and quality-gate allocation.
#SBATCH --job-name=ppo-pipeline-wp0
#SBATCH --partition=gpu-grace-h200-141g
#SBATCH --nodelist=gpuarm1
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=96
#SBATCH --mem=512G
#SBATCH --gres=gpu:gh200:2
#SBATCH --time=06:00:00
#SBATCH --output=/scratch/work/nguyenl37/Quantitative-RL-Trading-System-gh200-max-fps/docs/research/gh200_pipelined_ppo_refactor_20261028/slurm-%j.out
#SBATCH --open-mode=append

set -euo pipefail

REPO_ROOT="/scratch/work/nguyenl37/Quantitative-RL-Trading-System-gh200-max-fps"
cd "$REPO_ROOT"
export TRITON_REPO="$REPO_ROOT"
export AARCH64_VENV="/scratch/work/nguyenl37/Quantitative-RL-Trading-System/.venv"
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1

mkdir -p docs/research/gh200_pipelined_ppo_refactor_20261028/measurements
source "$REPO_ROOT/scripts/compute/slurm/activate_venv.sh"

REPORT_DIR="docs/research/gh200_pipelined_ppo_refactor_20261028/measurements/wp0-job-${SLURM_JOB_ID}"
mkdir -p "$REPORT_DIR"
{
    printf 'job_id=%s\n' "$SLURM_JOB_ID"
    printf 'job_name=%s\n' "$SLURM_JOB_NAME"
    printf 'dependency=afterany:21267207\n'
    printf 'host=%s\n' "$(hostname)"
    printf 'start=%s\n' "$(date --iso-8601=seconds)"
    printf 'commit=%s\n' "$(git rev-parse HEAD)"
    printf '\nSlurm allocation:\n'
    scontrol show job "$SLURM_JOB_ID"
} > "$REPORT_DIR/allocation.txt" 2>&1

set +e
bash scripts/research/benchmarks/run_pipelined_ppo_wp0.sh
benchmark_status=$?
set -e
printf 'benchmark_exit=%s\nfinish=%s\n' "$benchmark_status" "$(date --iso-8601=seconds)" \
    >> "$REPORT_DIR/allocation.txt"

if [[ "$benchmark_status" -eq 0 ]]; then
    "$VIRTUAL_ENV/bin/python" scripts/research/benchmarks/summarize_pipelined_ppo_wp0.py \
        "$REPORT_DIR" --output "$REPORT_DIR/RESULTS.md" \
        > "$REPORT_DIR/summarize.txt" 2>&1
    set +e
    "$VIRTUAL_ENV/bin/ruff" format --check . > "$REPORT_DIR/ruff-format.txt" 2>&1
    format_status=$?
    "$VIRTUAL_ENV/bin/ruff" check . > "$REPORT_DIR/ruff-check.txt" 2>&1
    ruff_status=$?
    MYPY_STAGE="$(mktemp -d "/tmp/triton-mypy-${USER}-wp0-${SLURM_JOB_ID}-XXXXXX")"
    MYPY_ENV_DIR="$VIRTUAL_ENV"
    MYPY_BASE_DIR="$(dirname "$(dirname "$(readlink -f "$MYPY_ENV_DIR/bin/python")")")"
    MYPY_SITE_DIR="$MYPY_ENV_DIR/lib/python3.12/site-packages"
    if mkdir -p "$MYPY_STAGE/sitepkgs" "$MYPY_STAGE/cache" \
        && cp -a "$MYPY_BASE_DIR" "$MYPY_STAGE/pythonbase" \
        && cp -a "$MYPY_SITE_DIR/mypy" "$MYPY_SITE_DIR/mypyc" "$MYPY_SITE_DIR/librt" \
            "$MYPY_SITE_DIR/pathspec" "$MYPY_SITE_DIR/packaging" \
            "$MYPY_SITE_DIR/mypy_extensions.py" "$MYPY_SITE_DIR/typing_extensions.py" \
            "$MYPY_STAGE/sitepkgs/"; then
        find "$MYPY_SITE_DIR" -maxdepth 1 -name '*__mypyc*.so' \
            -exec cp -a {} "$MYPY_STAGE/sitepkgs/" \;
        printf 'staged_mypy_env=%s\n' "$MYPY_ENV_DIR" > "$REPORT_DIR/mypy.txt"
        if PYTHONPATH="$MYPY_STAGE/sitepkgs:$MYPY_SITE_DIR" \
            "$MYPY_STAGE/pythonbase/bin/python3.12" -m mypy --version \
            >> "$REPORT_DIR/mypy.txt" 2>&1; then
            if PYTHONPATH="$MYPY_STAGE/sitepkgs:$MYPY_SITE_DIR" \
                "$MYPY_STAGE/pythonbase/bin/python3.12" -m mypy . \
                --cache-dir "$MYPY_STAGE/cache" --no-color-output --show-error-codes \
                >> "$REPORT_DIR/mypy.txt" 2>&1; then
                mypy_status=0
            else
                mypy_status=$?
            fi
        else
            mypy_status=$?
        fi
    else
        printf 'Could not stage Python/Mypy on node-local storage.\n' > "$REPORT_DIR/mypy.txt"
        mypy_status=1
    fi
    rm -rf -- "$MYPY_STAGE"
    "$VIRTUAL_ENV/bin/pytest" \
        tests/test_train/test_mtf_benchmark_configs.py \
        tests/test_bench/test_measure_ppo_throughput.py \
        tests/test_bench/test_summarize_pipelined_ppo_wp0.py \
        tests/test_compute_contracts.py \
        -q > "$REPORT_DIR/focused-pytest.txt" 2>&1
    pytest_status=$?
    set -e
    {
        printf 'ruff_format_exit=%s\n' "$format_status"
        printf 'ruff_check_exit=%s\n' "$ruff_status"
        printf 'mypy_exit=%s\n' "$mypy_status"
        printf 'focused_pytest_exit=%s\n' "$pytest_status"
    } >> "$REPORT_DIR/allocation.txt"
    if [[ "$format_status" -ne 0 || "$ruff_status" -ne 0 || "$mypy_status" -ne 0 || "$pytest_status" -ne 0 ]]; then
        exit 1
    fi
else
    echo 'Quality gates skipped because WP0/WP1 benchmark sequence failed.' \
        > "$REPORT_DIR/quality-gates-skipped.txt"
    exit "$benchmark_status"
fi
