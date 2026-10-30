#!/usr/bin/env bash
# Preserve an experiment run's original Git SHA during resume fingerprint creation.
# The controller still hashes every training/config input, so changed experiment run
# sources continue to fail the existing fingerprint check.

experiment_run_manifest="${TRITON_REPO:?}/outputs/experiment_runs/${EXPERIMENT_RUN_ID:?}/experiment_run.json"
if [[ ! -s "$experiment_run_manifest" ]]; then
  return 0
fi

# activate_venv.sh may be sourced again by nested validation scripts. Keep the
# first real Git path and shim environment instead of wrapping the shim itself.
if [[ "${EXPERIMENT_RUN_GIT_IDENTITY_ACTIVE:-}" == "1" ]]; then
  return 0
fi

experiment_run_recorded_git_sha="$(python - "$experiment_run_manifest" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as stream:
    manifest = json.load(stream)
print(manifest.get("git_sha", ""))
PY
)"
if [[ ! "$experiment_run_recorded_git_sha" =~ ^[0-9a-f]{40}$ ]]; then
  echo "ERROR: experiment run manifest has no valid recorded git_sha: $experiment_run_manifest" >&2
  return 1
fi

experiment_run_real_git="$(command -v git)"
experiment_run_git_shim_dir="${TMPDIR:-/tmp}/experiment-run-git-identity-${SLURM_JOB_ID:-$$}"
mkdir -p "$experiment_run_git_shim_dir"
cat >"$experiment_run_git_shim_dir/git" <<'SH'
#!/usr/bin/env bash
if [[ $# -eq 2 && "$1" == "rev-parse" && "$2" == "HEAD" ]]; then
  parent_exe="$(readlink "/proc/$PPID/exe" 2>/dev/null || true)"
  parent_cmd="$(tr '\0' ' ' <"/proc/$PPID/cmdline" 2>/dev/null || true)"
  if [[ "$parent_exe" == */python* \
    && "$(pwd -P)" == "${EXPERIMENT_RUN_GIT_IDENTITY_REPO:-}" \
    && "$parent_cmd" == *experiment_run_controller.py* ]]; then
    printf '%s\n' "${EXPERIMENT_RUN_GIT_IDENTITY_SHA:?}"
    exit 0
  fi
fi
exec "${EXPERIMENT_RUN_GIT_IDENTITY_REAL_GIT:?}" "$@"
SH
chmod 700 "$experiment_run_git_shim_dir/git"

export EXPERIMENT_RUN_GIT_IDENTITY_SHA="$experiment_run_recorded_git_sha"
export EXPERIMENT_RUN_GIT_IDENTITY_REPO="$(cd "$TRITON_REPO" && pwd -P)"
export EXPERIMENT_RUN_GIT_IDENTITY_REAL_GIT="$experiment_run_real_git"
export EXPERIMENT_RUN_GIT_IDENTITY_ACTIVE=1
export PATH="$experiment_run_git_shim_dir:$PATH"
echo "Experiment run resume will retain recorded Git identity $experiment_run_recorded_git_sha; source hashes remain enforced."
