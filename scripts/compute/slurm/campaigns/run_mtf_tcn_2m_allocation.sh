#!/usr/bin/env bash
# Validate and run a matched normal-data 2M TCN versus multi-window MTF pair.
set -Eeuo pipefail

REPO="${TRITON_REPO:-/scratch/work/nguyenl37/Quantitative-RL-Trading-System}"
SPEC="${CAMPAIGN_SPEC:-config/campaigns/rq_mtf_tcn_a4a_q5off_seed50_train2025_2m_normal_zero_latency_v1.yaml}"
CAMPAIGN_ID="${CAMPAIGN_ID:-rq_mtf_tcn_a4a_q5off_seed50_train2025_20261025_2m_normal_zero_latency_v1}"
WORKERS="${CAMPAIGN_WORKERS:-2}"
WORKER_CPUS="${CAMPAIGN_WORKER_CPUS:-47}"
OUT_DIR="$REPO/outputs/gpu_campaigns/$CAMPAIGN_ID"
JOB_ID="${SLURM_JOB_ID:?must run inside the approved two-node allocation}"
ALLOCATION_DIR="$REPO/outputs/gpu_allocations/$JOB_ID"
QUEUE="$ALLOCATION_DIR/worker_queue"
DONE="$ALLOCATION_DIR/release_managers"
REQUEST_ID="${CAMPAIGN_ALLOCATION_REQUEST_ID:-manual-$JOB_ID}"
RELEASED="$OUT_DIR/reports/allocation_released.$REQUEST_ID"
explicit_release=0

cd "$REPO"
export TRITON_REPO="$REPO"
source "$REPO/scripts/compute/slurm/activate_venv.sh"
export CAMPAIGN_OUT_DIR="$ALLOCATION_DIR"
export CAMPAIGN_WORKER_QUEUE="$QUEUE"
export CAMPAIGN_ALLOCATION_DONE_MARKER="$DONE"
export PATH="$REPO/scripts/compute/slurm/worker_bin:$PATH"
export PYTHONHASHSEED=0

mkdir -p "$OUT_DIR/logs" "$OUT_DIR/reports" "$ALLOCATION_DIR"
if [[ "${SLURM_PROCID:-0}" != "0" ]]; then
  exec "$VIRTUAL_ENV/bin/python" "$REPO/compute/slurm/worker_dispatch.py" --manager \
    >>"$OUT_DIR/logs/worker_manager_$(hostname -s)_${JOB_ID}.log" 2>&1
fi

controller_status=""
hold_console_ready=0
finish_allocation() {
  status=$?
  if [[ -z "$controller_status" ]]; then
    controller_status="$status"
  fi
  if [[ "$hold_console_ready" == 1 && "$explicit_release" == 0 ]]; then
    echo "Allocation task stopped (exit=$status); keeping job $JOB_ID available for follow-up."
    allocation_console
  fi
  if [[ "$explicit_release" == 1 ]]; then
    : > "$RELEASED"
  fi
  printf '%s\n' "$status" > "$DONE"
  if [[ -n "${manager_pid:-}" ]]; then
    wait "$manager_pid" || manager_status=$?
    if [[ "$status" -eq 0 && "${manager_status:-0}" -ne 0 ]]; then
      status="$manager_status"
    fi
  fi
  echo "TCN/MTF 2M allocation job=$JOB_ID exit=$status"
  exit "$status"
}
trap finish_allocation EXIT

allocation_console() {
  local command status
  echo "Campaign controller finished (exit=$controller_status); allocation $JOB_ID remains held."
  echo "Enter 'run <command>' to use this allocation, 'status' to inspect it, or 'release' to end it."
  while true; do
    if ! IFS= read -r -p "allocation[$JOB_ID]> " command; then
      echo "Allocation control input closed; releasing job $JOB_ID."
      explicit_release=1
      return 0
    fi
    case "$command" in
      release)
        echo "Releasing allocation $JOB_ID by request."
        explicit_release=1
        return 0
        ;;
      status)
        echo "job=$JOB_ID nodes=${SLURM_JOB_NODELIST:-unknown} queue=$QUEUE"
        scontrol show job -o "$JOB_ID" || true
        ;;
      run\ *)
        command="${command#run }"
        if [[ -z "$command" ]]; then
          echo "Usage: run <command>"
          continue
        fi
        set +e
        eval "$command"
        status=$?
        set -e
        echo "command finished exit=$status; allocation $JOB_ID remains held"
        ;;
      help)
        echo "Commands: run <command>, status, help, release"
        ;;
      *)
        echo "Unknown command. Enter 'help' for commands."
        ;;
    esac
  done
}

mkdir -p "$QUEUE/$JOB_ID"
"$VIRTUAL_ENV/bin/python" "$REPO/compute/slurm/worker_dispatch.py" --manager \
  >>"$OUT_DIR/logs/worker_manager_$(hostname -s)_${JOB_ID}.log" 2>&1 &
manager_pid=$!
node="$(hostname -s)"
ready="$QUEUE/$JOB_ID/$node/ready"
for _ in $(seq 1 60); do
  [[ -e "$ready" ]] && break
  kill -0 "$manager_pid" 2>/dev/null || {
    echo "local worker manager exited before readiness" >&2
    exit 1
  }
  sleep 1
done
if [[ ! -e "$ready" ]]; then
  echo "local worker manager did not become ready within 60 seconds" >&2
  exit 1
fi
hold_console_ready=1

if [[ -s "$OUT_DIR/campaign.json" ]]; then
  echo "campaign manifest already exists; use its existing fingerprint-aware resume path" >&2
  exit 2
fi

echo "Running source quality checks on $(hostname -s) before the campaign."
"$VIRTUAL_ENV/bin/ruff" format --check .
"$VIRTUAL_ENV/bin/ruff" check .
MYPY_STAGE="$(mktemp -d "/tmp/triton-mypy-${USER}-XXXXXX")"
ENV_DIR="$(dirname "$(dirname "$(command -v python)")")"
BASE="$(dirname "$(dirname "$(readlink -f "$ENV_DIR/bin/python")")")"
SITE="$ENV_DIR/lib/python3.12/site-packages"
mkdir -p "$MYPY_STAGE/sitepkgs" "$MYPY_STAGE/cache"
cp -a "$BASE" "$MYPY_STAGE/pythonbase"
cp -a "$SITE/mypy" "$SITE/mypyc" "$SITE/librt" "$SITE/pathspec" \
  "$SITE/packaging" "$SITE/mypy_extensions.py" \
  "$SITE/typing_extensions.py" "$MYPY_STAGE/sitepkgs/"
find "$SITE" -maxdepth 1 -name '*__mypyc*.so' \
  -exec cp -a {} "$MYPY_STAGE/sitepkgs/" \;
if PYTHONPATH="$MYPY_STAGE/sitepkgs:$SITE" \
  "$MYPY_STAGE/pythonbase/bin/python3.12" -m mypy . \
  --cache-dir "$MYPY_STAGE/cache" --no-color-output --show-error-codes; then
  rm -rf -- "$MYPY_STAGE"
  MYPY_STAGE=""
else
  status=$?
  rm -rf -- "$MYPY_STAGE"
  MYPY_STAGE=""
  exit "$status"
fi
"$VIRTUAL_ENV/bin/python" -m pytest \
  tests/test_simulation/test_environment/test_mtf_windows.py tests/test_simulation/test_environment/test_bundle_eval.py \
  tests/test_models/test_encoders.py tests/test_features/test_build_pipeline.py \
  tests/test_simulation/test_backtest/test_entry_levels.py -q
"$VIRTUAL_ENV/bin/python" "$REPO/experiments/campaigns/execution.py" \
  --campaign-spec "$REPO/$SPEC" \
  --workers "$WORKERS" \
  --n-envs 64 \
  --worker-nodes gpuarm1,gpuarm2 \
  --worker-cpus "$WORKER_CPUS" \
  --worker-gpu-type gh200 \
  --worker-gpus-per-node 1 \
  --dry-run

if ! bash "$REPO/scripts/data/setup_mode_dirs.sh"; then
  echo "failed to prepare the reusable normal/discretion input folders" >&2
  exit 2
fi
if "$VIRTUAL_ENV/bin/python" -m market_data.commands.prebuild_campaign_cache \
  2>&1 | tee "$OUT_DIR/logs/split_cache_build_${JOB_ID}.log" \
  > "$OUT_DIR/reports/split_cache_ready_${JOB_ID}.json"; then
  "$VIRTUAL_ENV/bin/python" -m json.tool "$OUT_DIR/reports/split_cache_ready_${JOB_ID}.json" >/dev/null
else
  status=$?
  echo "normal-profile cache build failed with status=$status" >&2
  exit "$status"
fi

mapfile -t ALLOCATED_NODES < <(scontrol show hostnames "${SLURM_JOB_NODELIST:?}")
MANAGER_DEADLINE=$((SECONDS + 180))
while true; do
  missing_nodes=()
  for allocated_node in "${ALLOCATED_NODES[@]}"; do
    node_key="${allocated_node%%.*}"
    [[ -e "$QUEUE/$JOB_ID/$node_key/ready" ]] || missing_nodes+=("$node_key")
  done
  [[ "${#missing_nodes[@]}" -eq 0 ]] && break
  if (( SECONDS >= MANAGER_DEADLINE )); then
    echo "worker managers not ready on every allocated node: ${missing_nodes[*]}" >&2
    exit 1
  fi
  sleep 2
done

echo "GH200 managers ready job=$JOB_ID nodes=${ALLOCATED_NODES[*]} workers=$WORKERS"
set +e
"$VIRTUAL_ENV/bin/python" "$REPO/experiments/campaigns/execution.py" \
  --campaign-spec "$REPO/$SPEC" \
  --workers "$WORKERS" \
  --n-envs 64 \
  --worker-nodes "${SLURM_JOB_NODELIST:?}" \
  --worker-cpus "$WORKER_CPUS" \
  --worker-gpu-type gh200 \
  --worker-gpus-per-node 1 \
  --fast-reports \
  2>&1 | tee -a "$OUT_DIR/logs/controller.log"
controller_status=${PIPESTATUS[0]}
set -e
allocation_console
exit "$controller_status"
