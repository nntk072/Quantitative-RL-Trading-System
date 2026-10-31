# Triton Operations

This runbook is for people running or diagnosing work on Aalto's Triton
cluster. Exact Slurm safety rules for coding agents live in
[`.agents/rules/triton-slurm.md`](../../.agents/rules/triton-slurm.md); use
that file when operating as an agent. Hardware availability and queue state
change, so query Slurm instead of relying on recorded examples.

## Find or start a compute session

Run status and filesystem inspection from the login shell. Run training,
evaluation, cache construction, and other substantial computation inside a
Slurm compute allocation.

```bash
bash scripts/compute/slurm/status.sh
bash scripts/compute/slurm/find_gpu_session.sh
squeue -u "$USER"
sinfo
```

Reuse an appropriate running allocation when possible. Before requesting
compute, check current node, GPU, CPU, and host-memory availability and read
the [Slurm operating rules](../../.agents/rules/triton-slurm.md). Keep the
allocation shell persistent so completed work can be collected and the
allocation reused safely.

Once inside the compute shell, verify the actual node and device rather than
assuming the SSH gateway matches them:

```bash
hostname
uname -m
echo "${SLURM_JOB_ID:-no Slurm allocation}"
nvidia-smi
```

## Choose the matching Python environment

| Compute architecture and device | Environment | Setup |
| --- | --- | --- |
| ARM64, GH200 | `.venv` | `tools/setup-venv` with an ARM64 `uv` binary |
| x86_64, H100/H200 | `.venv-x86` | `tools/setup-venv-x86` |
| x86_64, V100 | `.venv-v100` | `tools/setup-venv-v100`; verify `sm_70` and a real CUDA operation |
| x86_64, MI210 | `/scratch/work/nguyenl37/.venv-mi210` | Separate ROCm setup; not part of current thesis runs |

Select the environment from inside the allocation:

```bash
source scripts/compute/slurm/activate_venv.sh
command -v python
python -c 'import sys; print(sys.prefix)'
python --version
```

Do not run an ARM environment from an x86 shell or reuse compiled packages
across architectures. The login home may provide an x86 `uv` binary on an ARM
node; use an architecture-matched binary for package operations. A Python
import or `nvidia-smi` alone does not validate the training runtime; use a real
device operation and the relevant tests before relying on a new environment.

## Storage and measurements

- `/scratch/work/nguyenl37` is persistent project storage for source,
  environments, checkpoints, logs, and reports. Lustre metadata operations and
  small-file imports may be slow.
- Node-local `/tmp` is faster but temporary. Keep a durable copy of every
  checkpoint, report, or dataset outside it before the allocation ends.
- Check filesystem capacity and user quotas before copying large environments:
  `df -h /tmp /scratch` and `du -sh <path>`.
- A requested Slurm RAM amount is a limit, not an observed peak. Report CPU,
  host RAM, GPU utilization, and GPU memory with the measurement source and
  whether each value is a peak, snapshot, or allocation limit.
- tmux preserves a terminal session; it does not keep an expired allocation
  alive. Save logs on scratch with the run configuration and source identity.

## Diagnose a slow command or Mypy startup

First verify the host, Python environment, exact command, and process state.
Lustre waits can delay imports without indicating a type error:

```bash
source scripts/compute/slurm/activate_venv.sh
timeout 30 mypy --version
ps -u "$USER" -o pid,stat,wchan:24,etime,pcpu,args
df -h /tmp /scratch
```

Exit code `124` means `timeout` expired. Inspect the process before concluding
that Lustre is responsible or starting another command. A full project type
check remains `mypy .`; never substitute a path-scoped check for the project
gate.

If Mypy stalls while importing from Lustre, stage its runtime and modules in a
private, architecture-local `/tmp` directory while keeping the project source
and dependencies from the matching persistent environment:

```bash
ENV_DIR="$(dirname "$(dirname "$(command -v python)")")"
STAGE="$(mktemp -d "/tmp/triton-mypy-${USER}-XXXXXX")"
mkdir -p "$STAGE/sitepkgs" "$STAGE/cache"
BASE="$(dirname "$(dirname "$(readlink -f "$ENV_DIR/bin/python")")")"
SITE="$ENV_DIR/lib/python3.12/site-packages"
cp -a "$BASE" "$STAGE/pythonbase"
cp -a "$SITE/mypy" "$SITE/mypyc" "$SITE/librt" "$SITE/pathspec" \
  "$SITE/packaging" "$SITE/mypy_extensions.py" "$SITE/typing_extensions.py" \
  "$STAGE/sitepkgs/"
find "$SITE" -maxdepth 1 -name '*__mypyc*.so' -exec cp -a {} "$STAGE/sitepkgs/" \;
PYTHONPATH="$STAGE/sitepkgs:$SITE" "$STAGE/pythonbase/bin/python3.12" \
  -m mypy . --cache-dir "$STAGE/cache" --no-color-output --show-error-codes
```

This workaround was verified on ARM64 with Python 3.12. The equivalent x86_64
staging path has not been validated. Remove only the unique staging directory
after the check completes; never clear shared `/tmp` contents or replace the
persistent environment to work around an import stall.

## Related references

- [Command examples](RUNNING_COMMANDS.md)
- [Reproducibility requirements](../reproducibility.md)
- [Agent Slurm rules](../../.agents/rules/triton-slurm.md)
