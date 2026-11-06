#!/usr/bin/env bash
# Run the configured all-profile prefix audit inside one existing GH200 allocation.
set -euo pipefail

repo=/scratch/work/nguyenl37/Quantitative-RL-Trading-System
inventory="$repo/evidence/research/feature_causality/feature_configuration_inventory.json"
python="$repo/.venv/bin/python"
shard_count=4

if [[ -z "${SLURM_JOB_ID:-}" ]]; then
  echo "Run this launcher inside an existing Slurm allocation." >&2
  exit 2
fi
host=$(hostname -s)
if [[ "$host" != gpuarm1 && "$host" != gpuarm2 ]]; then
  echo "Expected a GH200 node (gpuarm1 or gpuarm2), found: $host" >&2
  exit 2
fi
job_info=$(scontrol show job -o "$SLURM_JOB_ID") || {
  echo "Cannot inspect the active Slurm allocation: $SLURM_JOB_ID" >&2
  exit 2
}
job_gres=$(awk '
  {
    for (i = 1; i <= NF; i++) {
      if ($i ~ /^Gres=/) {
        sub(/^Gres=/, "", $i)
        print $i
        exit
      }
    }
  }
' <<<"$job_info")
if [[ -n "$job_gres" ]]; then
  has_one_gh200=false
  [[ "$job_gres" == gpu:gh200:1 || "$job_gres" == gpu:gh200:1\(* ]] && has_one_gh200=true
else
  # Some Triton Slurm versions report the allocation under AllocTRES rather
  # than a Gres field (for example, gres/gpu:gh200=1).
  job_alloc_tres=$(awk '
    {
      for (i = 1; i <= NF; i++) {
        if ($i ~ /^AllocTRES=/) {
          sub(/^AllocTRES=/, "", $i)
          print $i
          exit
        }
      }
    }
  ' <<<"$job_info")
  job_gh200_count=$(awk -F, '
    {
      for (i = 1; i <= NF; i++) {
        if ($i ~ /^gres\/gpu:gh200=/) {
          sub(/^gres\/gpu:gh200=/, "", $i)
          print $i
          exit
        }
      }
    }
  ' <<<"$job_alloc_tres")
  job_gres="${job_gh200_count:-unknown} GH200 in AllocTRES"
  has_one_gh200=false
  [[ "$job_gh200_count" == 1 ]] && has_one_gh200=true
fi
if [[ "$has_one_gh200" != true ]]; then
  echo "Expected exactly one GH200 in the active allocation, found: ${job_gres:-unknown}" >&2
  exit 2
fi
job_cpus=$(sed -n 's/.*NumCPUs=\([^ ]*\).*/\1/p' <<<"$job_info")
job_memory=$(sed -n 's/.*MinMemoryNode=\([^ ]*\).*/\1/p' <<<"$job_info")
job_time=$(sed -n 's/.*TimeLimit=\([^ ]*\).*/\1/p' <<<"$job_info")
if [[ ! "$job_cpus" =~ ^[0-9]+$ ]] || (( job_cpus < 48 )); then
  echo "Prefix audit requires at least 48 allocated CPUs, found: ${job_cpus:-unknown}" >&2
  exit 2
fi
if [[ "$job_memory" != 512G ]]; then
  echo "Prefix audit requires the documented 512G host-memory allocation, found: ${job_memory:-unknown}" >&2
  exit 2
fi
if [[ "$job_time" != 12:00:00 ]]; then
  echo "Prefix audit requires a 12-hour allocation, found: ${job_time:-unknown}" >&2
  exit 2
fi
if [[ $# -ne 1 ]]; then
  echo "Usage: $0 OUT_DIR (outside the repository; must be empty or absent)" >&2
  exit 2
fi
if [[ ! -x "$python" ]]; then
  echo "ARM64 project environment is unavailable: $python" >&2
  exit 2
fi

out_dir=$1
if [[ "$out_dir" != /* ]]; then
  out_dir="$PWD/$out_dir"
fi
case "$out_dir" in
  "$repo"|"$repo"/*)
    echo "Store shard logs outside the repository: $out_dir" >&2
    exit 2
    ;;
esac
if [[ -e "$out_dir" ]] && find "$out_dir" -mindepth 1 -maxdepth 1 -print -quit | grep -q .; then
  echo "Output directory must be empty to preserve prior run evidence: $out_dir" >&2
  exit 2
fi
mkdir -p "$out_dir"

export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

script_path=$(realpath "${BASH_SOURCE[0]}")
{
  printf 'launcher=%s\n' "$script_path"
  printf 'launcher_sha256=%s\n' "$(sha256sum "$script_path" | cut -d ' ' -f 1)"
  printf 'slurm_job_id=%s\n' "$SLURM_JOB_ID"
  printf 'host=%s\n' "$host"
  printf 'started_at_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf 'shard_count=%s\n' "$shard_count"
  printf 'feature_inventory=%s\n' "$inventory"
  "$python" --version
} > "$out_dir/launch_metadata.txt"

run_shard() {
  local index=$1
  local status=0
  if "$python" "$repo/scripts/research/analysis/features/verify_real_market_feature_prefix_invariance.py" \
    --profile-inventory "$inventory" \
    --profile-group-shard "$index/$shard_count" \
    --out "$out_dir/shard_${index}.json"; then
    status=0
  else
    status=$?
  fi
  printf '%s\n' "$status" > "$out_dir/shard_${index}.exit"
  return "$status"
}

declare -a pids
for index in 0 1 2 3; do
  run_shard "$index" > "$out_dir/shard_${index}.log" 2>&1 &
  pids[$index]=$!
done

failed=0
for index in 0 1 2 3; do
  if wait "${pids[$index]}"; then
    :
  else
    status=$?
    printf 'shard=%s exit=%s\n' "$index" "$status" >> "$out_dir/failures.txt"
    failed=1
  fi
done
if (( failed )); then
  echo "One or more shards failed; reports and logs are preserved in $out_dir" >&2
  exit 1
fi

if "$python" "$repo/scripts/research/analysis/features/merge_real_market_feature_prefix_shards.py" \
  --inventory "$inventory" \
  --shards "$out_dir/shard_0.json" "$out_dir/shard_1.json" \
    "$out_dir/shard_2.json" "$out_dir/shard_3.json" \
  --out "$out_dir/merged.json"; then
  :
else
  status=$?
  echo "Shard merge failed; reports and logs are preserved in $out_dir" >&2
  exit "$status"
fi
printf 'finished_at_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$out_dir/launch_metadata.txt"
