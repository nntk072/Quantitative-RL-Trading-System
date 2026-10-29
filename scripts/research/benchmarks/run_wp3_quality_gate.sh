#!/usr/bin/env bash
# Run the repository-required full-tree Ruff/Mypy gate and focused WP3 tests
# within an existing ARM GH200 allocation. This script submits no Slurm steps.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$REPO_ROOT"
export TRITON_REPO="$REPO_ROOT"
export AARCH64_VENV="${AARCH64_VENV:-/scratch/work/nguyenl37/Quantitative-RL-Trading-System/.venv}"
source "$REPO_ROOT/scripts/compute/slurm/activate_venv.sh"
REPORT_DIR="${WP3_REPORT_DIR:-docs/research/gh200_pipelined_ppo_refactor_20261028/measurements/wp3-job-${SLURM_JOB_ID:-local}}"
mkdir -p "$REPORT_DIR"

PYTHON_FILES=(
    scripts/research/benchmarks/ppo_cohort_pipeline.py
    scripts/research/benchmarks/measure_ppo_throughput.py
    scripts/research/benchmarks/summarize_wp3_cohort_feasibility.py
    tests/test_bench/test_ppo_cohort_pipeline.py
    tests/test_bench/test_summarize_wp3_cohort_feasibility.py
)
set +e
"$VIRTUAL_ENV/bin/ruff" format "${PYTHON_FILES[@]}" > "$REPORT_DIR/ruff-format-write.txt" 2>&1
format_write_status=$?
"$VIRTUAL_ENV/bin/ruff" format --check . > "$REPORT_DIR/ruff-format-check.txt" 2>&1
format_status=$?
"$VIRTUAL_ENV/bin/ruff" check --fix "${PYTHON_FILES[@]}" > "$REPORT_DIR/ruff-fix.txt" 2>&1
ruff_fix_status=$?
"$VIRTUAL_ENV/bin/ruff" check . > "$REPORT_DIR/ruff-check.txt" 2>&1
ruff_status=$?

MYPY_STAGE="$(mktemp -d "/tmp/triton-mypy-${USER}-wp3-${SLURM_JOB_ID:-local}-XXXXXX")"
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
    PYTHONPATH="$MYPY_STAGE/sitepkgs:$MYPY_SITE_DIR" \
        "$MYPY_STAGE/pythonbase/bin/python3.12" -m mypy . \
        --cache-dir "$MYPY_STAGE/cache" --no-color-output --show-error-codes \
        > "$REPORT_DIR/mypy.txt" 2>&1
    mypy_status=$?
else
    echo "Could not stage Mypy on node-local storage" > "$REPORT_DIR/mypy.txt"
    mypy_status=1
fi
rm -rf -- "$MYPY_STAGE"

"$VIRTUAL_ENV/bin/python" -m pytest \
    tests/test_bench/test_ppo_cohort_pipeline.py \
    tests/test_bench/test_summarize_wp3_cohort_feasibility.py \
    tests/test_bench/test_measure_ppo_throughput.py \
    -q > "$REPORT_DIR/focused-tests.log" 2>&1
pytest_status=$?

{
    printf 'ruff_format_exit=%s\n' "$format_status"
    printf 'ruff_format_write_exit=%s\n' "$format_write_status"
    printf 'ruff_fix_exit=%s\n' "$ruff_fix_status"
    printf 'ruff_check_exit=%s\n' "$ruff_status"
    printf 'mypy_full_tree_exit=%s\n' "$mypy_status"
    printf 'focused_pytest_exit=%s\n' "$pytest_status"
} > "$REPORT_DIR/quality-gate-status.txt"
cat "$REPORT_DIR/quality-gate-status.txt"
if (( format_status != 0 || format_write_status != 0 || ruff_fix_status != 0 || ruff_status != 0 || mypy_status != 0 || pytest_status != 0 )); then
    exit 1
fi
