#!/usr/bin/env bash
# Run the matched growth-PPO pair with and without a fixed EOD drawdown rule.
set -Eeuo pipefail

REPO="${TRITON_REPO:-/scratch/work/nguyenl37/Quantitative-RL-Trading-System}"
SPEC="${CAMPAIGN_SPEC:-config/campaigns/sustainable_growth_seed50_train2025_2m_eod_dd10k_v1.yaml}"
CAMPAIGN_ID="${CAMPAIGN_ID:-sustainable_growth_seed50_train2025_20261025_2m_eod_dd10k_v1}"
WORKERS="${CAMPAIGN_WORKERS:-2}"
WORKER_CPUS="${CAMPAIGN_WORKER_CPUS:-47}"
N_ENVS="${CAMPAIGN_N_ENVS:-8}"
OUT_DIR="$REPO/outputs/gpu_campaigns/$CAMPAIGN_ID"
JOB_ID="${SLURM_JOB_ID:?must run inside the sequential GH200 allocation}"
ALLOCATION_DIR="$REPO/outputs/gpu_allocations/$JOB_ID"
QUEUE="$ALLOCATION_DIR/worker_queue"
DONE="$ALLOCATION_DIR/release_managers"
RELEASED="$OUT_DIR/reports/allocation_released.$JOB_ID"
explicit_release=0

cd "$REPO"
export TRITON_REPO="$REPO"
source "$REPO/scripts/compute/slurm/activate_venv.sh"
export CAMPAIGN_OUT_DIR="$ALLOCATION_DIR"
export CAMPAIGN_WORKER_QUEUE="$QUEUE"
export CAMPAIGN_ALLOCATION_DONE_MARKER="$DONE"
export PATH="$REPO/scripts/compute/slurm/worker_bin:$PATH"
export PYTHONHASHSEED=0

mkdir -p "$OUT_DIR/logs" "$OUT_DIR/reports" "$QUEUE/$JOB_ID"
mkdir -p "$ALLOCATION_DIR"

if [[ "${SLURM_PROCID:-0}" != "0" ]]; then
  exec python "$REPO/compute/slurm/worker_dispatch.py" --manager \
    >>"$OUT_DIR/logs/worker_manager_$(hostname -s)_${JOB_ID}.log" 2>&1
fi

controller_status=""
manager_pid=""
finish_allocation() {
  status=$?
  if [[ -n "$controller_status" ]]; then status="$controller_status"; fi
  if [[ -n "${manager_pid:-}" ]]; then
    kill "$manager_pid" 2>/dev/null || true
    wait "$manager_pid" || manager_status=$?
    if [[ "$status" -eq 0 && "${manager_status:-0}" -ne 0 ]]; then
      status="$manager_status"
    fi
  fi
  if [[ "$explicit_release" == 1 ]]; then : > "$RELEASED"; fi
  printf '%s\n' "$status" > "$DONE"
  echo "EOD drawdown campaign allocation job=$JOB_ID exit=$status"
  exit "$status"
}
trap finish_allocation EXIT

if [[ -s "$OUT_DIR/campaign.json" ]]; then
  echo "campaign manifest already exists; use its fingerprint-aware resume path" >&2
  exit 2
fi

python "$REPO/compute/slurm/worker_dispatch.py" --manager \
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
echo "GH200 worker managers ready job=$JOB_ID nodes=${ALLOCATED_NODES[*]} workers=$WORKERS"

PREVIOUS_MTF_CAMPAIGNS=(
  rq_mtf_tcn_a4a_q5off_seed50_train2025_20261025_2m_normal_zero_latency_alltf_swings_v1
  rq_mtf_tcn_a4a_q5off_seed50_train2025_20261025_2m_normal_zero_latency_v1
  rq_mtf_tcn_a4a_q5off_seed50_train2025_20261025_2m_normal_zero_latency_log1k_v3
)
for previous_id in "${PREVIOUS_MTF_CAMPAIGNS[@]}"; do
  previous_dir="$REPO/outputs/gpu_campaigns/$previous_id"
  echo "Checking the requested full report before the new benchmark: $previous_id"
  if [[ -s "$previous_dir/reports/project_results_report.md" ]]; then
    report_name=project_results_report.md
    echo "Using existing report: $previous_dir/reports/$report_name"
  elif python "$REPO/scripts/research/thesis/evaluation/report_variant_details.py" \
    --campaign-dir "$previous_dir" \
    > "$previous_dir/reports/project_results_report_generation.log" 2>&1; then
    report_name=project_results_report.md
  else
    if ! grep -Eqi 'required split equity data is missing|required learner diagnostics|required training/testing comparison figures|training log is required for learner diagnostics|no figures|missing.*equity' \
      "$previous_dir/reports/project_results_report_generation.log"; then
      echo "unexpected full-report failure for $previous_id; see project_results_report_generation.log" >&2
      exit 1
    fi
    python - "$previous_dir" <<'PY'
import json
import sys
from pathlib import Path

campaign_dir = Path(sys.argv[1])
manifest = json.loads((campaign_dir / "campaign.json").read_text(encoding="utf-8"))
summary_path = campaign_dir / "reports" / "campaign_results_summary.md"
summary = summary_path.read_text(encoding="utf-8") if summary_path.is_file() else "No saved campaign summary exists."
log_path = campaign_dir / "reports" / "project_results_report_generation.log"
log_text = log_path.read_text(encoding="utf-8", errors="replace")
reason = next(
    (line.strip() for line in log_text.splitlines() if any(
        marker in line.lower()
        for marker in ("required split equity data is missing", "required learner diagnostics", "required training/testing comparison figures", "no figures", "missing")
    )),
    "Required full train/test replay artifacts were not saved.",
)
report = (
    f"# Full available-evidence report: {campaign_dir.name}\n\n"
    f"Campaign fingerprint: `{manifest.get('fingerprint', 'not recorded')}`.\n\n"
    "## Result status\n\n"
    "This campaign does not have enough saved replay evidence for a strategy-performance report. "
    "The report generator requires complete training and testing equity paths and learner diagnostics; "
    f"it stopped on: `{reason}`. No equity, drawdown, or trade figures have been fabricated.\n\n"
    "The campaign summary below is the complete saved numerical evidence. Missing values mean the "
    "campaign did not produce a valid full result and must not be interpreted as zero or as a pass.\n\n"
    + summary
)
(campaign_dir / "reports" / "project_results_report.md").write_text(report, encoding="utf-8")
PY
    report_name=project_results_report.md
  fi
  python - "$previous_dir/campaign.json" "$previous_dir/reports/$report_name" <<'PY'
import json
import sys
from pathlib import Path

manifest_path, report_path = map(Path, sys.argv[1:])
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
jobs = manifest.get("jobs", [])
terminal = {"succeeded", "failed", "interrupted"}
if not jobs or any(job.get("status") not in terminal for job in jobs):
    raise SystemExit(f"refusing checkpoint cleanup for a nonterminal campaign: {manifest_path}")
if not report_path.is_file() or report_path.stat().st_size == 0:
    raise SystemExit(f"full result report missing or empty: {report_path}")
PY
  find "$previous_dir/runs" -type f -path '*/model/ppo_*.zip' -delete
done

echo "Running focused EOD drawdown and variant resolution tests on $(hostname -s)."
python -m ruff format \
  simulation/environment/env.py \
  simulation/environment/risk_runtime.py \
  simulation/environment/episode_equity.py \
  simulation/environment/step_accounting_runtime.py \
  simulation/environment/step_constraints_runtime.py \
  simulation/environment/step_end_runtime.py \
  trading/account/state.py \
  evaluation/rollout/model.py \
  training/artifacts/manifests.py \
  training/artifacts/metrics.py \
  tests/test_train/test_equity_gate.py \
  tests/test_train/test_sustainable_growth_variant_resolution.py
python -m ruff format --check \
  simulation/environment/env.py \
  simulation/environment/risk_runtime.py \
  simulation/environment/episode_equity.py \
  simulation/environment/step_accounting_runtime.py \
  simulation/environment/step_constraints_runtime.py \
  simulation/environment/step_end_runtime.py \
  trading/account/state.py \
  evaluation/rollout/model.py \
  training/artifacts/manifests.py \
  training/artifacts/metrics.py \
  tests/test_train/test_equity_gate.py \
  tests/test_train/test_sustainable_growth_variant_resolution.py
python -m ruff check \
  simulation/environment/env.py \
  simulation/environment/risk_runtime.py \
  simulation/environment/episode_equity.py \
  simulation/environment/step_accounting_runtime.py \
  simulation/environment/step_constraints_runtime.py \
  simulation/environment/step_end_runtime.py \
  trading/account/state.py \
  evaluation/rollout/model.py \
  training/artifacts/manifests.py \
  training/artifacts/metrics.py \
  tests/test_train/test_equity_gate.py \
  tests/test_train/test_sustainable_growth_variant_resolution.py
python -m pytest \
  tests/test_train/test_equity_gate.py \
  tests/test_envs/test_ny_steps_eod.py \
  tests/test_train/test_sustainable_growth_variant_resolution.py -q \
  2>&1 | tee "$OUT_DIR/logs/focused_validation_${JOB_ID}.log"

python "$REPO/experiments/campaigns/execution.py" \
  --campaign-spec "$REPO/$SPEC" \
  --workers "$WORKERS" \
  --n-envs "$N_ENVS" \
  --worker-nodes "${SLURM_JOB_NODELIST:?}" \
  --worker-cpus "$WORKER_CPUS" \
  --worker-gpu-type gh200 \
  --worker-gpus-per-node 1 \
  --dry-run > "$OUT_DIR/reports/campaign_preflight_${JOB_ID}.json"
python -m json.tool "$OUT_DIR/reports/campaign_preflight_${JOB_ID}.json" >/dev/null

set +e
python "$REPO/experiments/campaigns/execution.py" \
  --campaign-spec "$REPO/$SPEC" \
  --workers "$WORKERS" \
  --n-envs "$N_ENVS" \
  --worker-nodes "${SLURM_JOB_NODELIST:?}" \
  --worker-cpus "$WORKER_CPUS" \
  --worker-gpu-type gh200 \
  --worker-gpus-per-node 1 \
  --fast-reports \
  2>&1 | tee -a "$OUT_DIR/logs/controller.log"
controller_status=${PIPESTATUS[0]}
set -e

if [[ -f "$REPO/scripts/research/thesis/evaluation/report_variant_details.py" ]]; then
  if ! python "$REPO/scripts/research/thesis/evaluation/report_variant_details.py" \
    --campaign-dir "$OUT_DIR" \
    > "$OUT_DIR/reports/project_results_report_generation.log" 2>&1; then
    echo "full per-variant report generation failed; see $OUT_DIR/reports/project_results_report_generation.log" >&2
    controller_status=1
  fi
fi

echo "Campaign controller finished (exit=$controller_status); allocation $JOB_ID remains held."
echo "Enter 'status' to inspect, or 'release' to let the sequential supervisor finish."
while true; do
  if ! IFS= read -r -p "allocation[$JOB_ID]> " command; then
    echo "Allocation input closed; preserving the running allocation."
    sleep 3600
    continue
  fi
  case "$command" in
    release)
      explicit_release=1
      break
      ;;
    status)
      scontrol show job -o "$JOB_ID"
      ;;
    help)
      echo "Commands: status, help, release"
      ;;
    *)
      echo "Unknown command. Enter 'status', 'help', or 'release'."
      ;;
  esac
done
exit "$controller_status"
