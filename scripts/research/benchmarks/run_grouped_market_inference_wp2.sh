#!/usr/bin/env bash
# Run a no-training full-policy market-row reuse A/B on two allocated GH200s.
set -euo pipefail

REPO_ROOT="/scratch/work/nguyenl37/Quantitative-RL-Trading-System-gh200-max-fps"
cd "$REPO_ROOT"
export TRITON_REPO="$REPO_ROOT"
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export AARCH64_VENV="/scratch/work/nguyenl37/Quantitative-RL-Trading-System/.venv"
source "$REPO_ROOT/scripts/compute/slurm/activate_venv.sh"

EXPECTED_BUNDLE_SHA256="d85e0dc8fa241c66d4d727dd4be5d463fc58dbbbd53a43fd00d75100387b052e"
BUNDLE_DIR="/scratch/work/nguyenl37/Quantitative-RL-Trading-System/cache/train_test_2025_2026/shared_env/e9d5a63f864394ddad5acfb73f184444a6293295e1bbeff6313d1bc5d842a28c"
CONFIG_PATH="config/research/thesis_mtf_shared_tcn_2m_high_throughput.yaml"
REPORT_DIR="docs/research/gh200_pipelined_ppo_refactor_20261028/measurements/wp2-job-${SLURM_JOB_ID:-local}"
mkdir -p "$REPORT_DIR"

actual_bundle_sha="$(sha256sum "$BUNDLE_DIR/manifest.json" | cut -d ' ' -f 1)"
if [[ "$actual_bundle_sha" != "$EXPECTED_BUNDLE_SHA256" ]]; then
    echo "Unexpected bundle manifest SHA-256: $actual_bundle_sha" >&2
    exit 2
fi

IFS=',' read -r -a allocated_gpus <<< "${CUDA_VISIBLE_DEVICES:-}"
if (( ${#allocated_gpus[@]} != 2 )); then
    echo "Expected exactly 2 allocated GPU IDs, got ${CUDA_VISIBLE_DEVICES:-unset}" >&2
    exit 2
fi

{
    printf 'job_id=%s\nhost=%s\nstarted=%s\n' \
        "${SLURM_JOB_ID:-local}" "$(hostname)" "$(date --iso-8601=seconds)"
    printf 'bundle_manifest_sha256=%s\n' "$actual_bundle_sha"
    printf 'config=%s\n' "$CONFIG_PATH"
    printf 'source_commit=%s\n' "$(git rev-parse HEAD)"
    printf 'tracked_diff_sha256=%s\n' "$(git diff --binary HEAD | sha256sum | cut -d ' ' -f 1)"
    printf 'CUDA_VISIBLE_DEVICES=%s\n' "$CUDA_VISIBLE_DEVICES"
    scontrol show job "${SLURM_JOB_ID:-}" 2>&1 || true
    nvidia-smi -q
} > "$REPORT_DIR/allocation-and-provenance.txt"

run_case() {
    local mode="$1"
    local gpu="$2"
    CUDA_VISIBLE_DEVICES="$gpu" "$VIRTUAL_ENV/bin/python" \
        scripts/research/benchmarks/measure_grouped_market_inference.py \
        --mode "$mode" \
        --job-id "${SLURM_JOB_ID:-local}" \
        --config "$CONFIG_PATH" \
        --bundle-dir "$BUNDLE_DIR" \
        --output "$REPORT_DIR/${mode}.json" \
        --n-envs 64 --seed 42 --warmup 20 --iterations 100 --rollout-steps 128
}

run_case full "${allocated_gpus[0]}" > "$REPORT_DIR/full.log" 2>&1 &
full_pid=$!
run_case grouped "${allocated_gpus[1]}" > "$REPORT_DIR/grouped.log" 2>&1 &
grouped_pid=$!
full_status=0
grouped_status=0
wait "$full_pid" || full_status=$?
wait "$grouped_pid" || grouped_status=$?
printf 'full_exit=%s\ngrouped_exit=%s\n' "$full_status" "$grouped_status" \
    > "$REPORT_DIR/case-status.txt"
if (( full_status != 0 || grouped_status != 0 )); then
    exit 1
fi

"$VIRTUAL_ENV/bin/python" - "$REPORT_DIR" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
full = json.loads((root / "full.json").read_text())
grouped = json.loads((root / "grouped.json").read_text())
same_observations = full["observations_sha256"] == grouped["observations_sha256"]
same_rollout = (
    full["rollout_observations_sha256"] == grouped["rollout_observations_sha256"]
)
same_seed_bundle = (
    full["mode"] == "full"
    and grouped["mode"] == "grouped"
    and full["n_envs"] == grouped["n_envs"]
    and full["rollout_steps"] == grouped["rollout_steps"]
    and full["seed"] == grouped["seed"]
    and full["bundle_manifest_sha256"] == grouped["bundle_manifest_sha256"]
    and full["resolved_config_sha256"] == grouped["resolved_config_sha256"]
    and full["policy_state_sha256"] == grouped["policy_state_sha256"]
    and full["source_commit"] == grouped["source_commit"]
)
report = {
    "measurement": "inference-only exact-market-row reuse; no training",
    "same_observation_batch": same_observations,
    "same_rollout_observations": same_rollout,
    "same_seed_bundle_source": same_seed_bundle,
    "baseline": full,
    "grouped": grouped,
    "grouped_speedup_p50": (
        full["latency_ms"]["p50"] / grouped["latency_ms"]["p50"]
        if same_observations and same_rollout and same_seed_bundle else None
    ),
    "interpretation_limit": (
        "Latency measures model inference only. It excludes discovering duplicate rows, "
        "constructing group indices, simulator stepping, IPC, PPO updates, callbacks, "
        "checkpointing, and full campaign replay."
    ),
}
(root / "RESULTS.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
rows = "\n".join(
    f"| {name} | {value:.3e} | {grouped['max_relative_errors'][name]:.3e} | "
    f"{grouped['parity_tolerances'][name]:.1e} |"
    for name, value in grouped["max_abs_errors"].items()
)
speedup = report["grouped_speedup_p50"]
speedup_text = f"{speedup:.3f}x" if speedup is not None else "UNAVAILABLE"
markdown = f"""# WP2 exact market-row reuse inference A/B

**Job:** `{full['job_id']}` on `{full['host']}`; two GH200s, one inference arm per GPU.
**Scope:** fresh seed-42 policy initialization and observations from the pinned training bundle; no PPO updates or historical replay.
**Source commit:** `{full['source_commit']}`
**Bundle manifest SHA-256:** `{full['bundle_manifest_sha256']}`
**Resolved config SHA-256:** `{full['resolved_config_sha256']}`
**Policy state SHA-256:** `{full['policy_state_sha256']}`

## Market reuse and parity

- Exact duplicate market rows: **{grouped['market_unique_rows']} / {grouped['n_envs']}**.
- Exact market reuse factor: **{grouped['market_reuse_factor']:.2f}x**.
- Across {grouped['market_reuse_summary']['sampled_vector_steps']} vector steps, market reuse was p50 **{grouped['market_reuse_summary']['market_reuse_factor_p50']:.2f}x**, p95 **{grouped['market_reuse_summary']['market_reuse_factor_p95']:.2f}x**.
- Across the same steps, account unique-row count was p50 **{grouped['market_reuse_summary']['account_unique_rows_p50']:.0f}**, p95 **{grouped['market_reuse_summary']['account_unique_rows_p95']:.0f}** of {grouped['account_rows']} environments.
- Unique account rows: **{grouped['account_unique_rows']} / {grouped['account_rows']}**.
- Same complete observation batch in both arms: **{same_observations}**.
- Same evolving rollout observations in both arms: **{same_rollout}**.
- Same seed, bundle, resolved config, initial policy weights, and source: **{same_seed_bundle}**.
- Feature, masked thesis logits/probabilities, deterministic actions, values, forward/evaluated log probabilities, and entropy all meet their listed tolerances: **{grouped['parity_passed']}**.

| Output | Max absolute difference | Max relative difference | Absolute tolerance |
|---|---:|---:|---:|
{rows}

All outputs also use relative tolerance `rtol={grouped['parity_relative_tolerance']:.1e}`.

## Full-policy latency

| Path | p50 ms / 64-env batch | p95 ms / 64-env batch |
|---|---:|---:|
| Full MTF encoding | {full['latency_ms']['p50']:.3f} | {full['latency_ms']['p95']:.3f} |
| Group exact duplicate market rows | {grouped['latency_ms']['p50']:.3f} | {grouped['latency_ms']['p95']:.3f} |

Grouped p50 speedup: **{speedup_text}**.

## Limits

This advances a freshly initialized random policy stochastically through {grouped['rollout_steps']} simulator steps per environment to observe market reuse and account divergence; it does not train and is not a trained-checkpoint evaluation. Latency is measured on the initial, midpoint, end, and terminal observation batches. It excludes the CPU work to discover duplicate rows, simulator stepping, IPC, PPO updates, callbacks, checkpointing, and year replay. These timings alone do not justify an integrated collector or a training-quality claim.
"""
(root / "RESULTS.md").write_text(markdown)
print(json.dumps(report, indent=2, sort_keys=True))
if not same_observations or not same_rollout or not same_seed_bundle:
    raise SystemExit("A/B provenance mismatch; do not compare the latency results")
PY

echo "COMPLETE wp2_grouped_market_inference report=$REPORT_DIR at=$(date --iso-8601=seconds)"
