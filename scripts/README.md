# Scripts

`scripts/` contains explicit command-line workflows for research analysis,
data maintenance, validation, and cluster operations. Shared behavior belongs
in its owning production package; scripts should parse inputs, call that
behavior, and write clearly identified outputs.

## Areas

| Path | Responsibility |
|---|---|
| `scripts/research/analysis/` | Canonical research analyses organized by feature, market-data, model, decisioning, evaluation, and evidence domain |
| `scripts/research/audits/` | Release and protocol gates plus narrow verification commands |
| `scripts/research/benchmarks/`, `strategy_checks/` | Focused performance and strategy diagnostics |
| `scripts/maintenance/` | Controlled data/cache and repository maintenance workflows |
| `scripts/compute/slurm/` | Slurm wrappers and allocation-side command launchers |
| `scripts/dev/` | Developer checks and repository-local support commands |
| `scripts/train/` | Training entrypoints retained for compatibility or specialized workflows |

Before running a script, inspect `--help`, its resolved input/output paths, and
whether it reads or writes experiment evidence. Research scripts should record
their inputs and assumptions; operational wrappers must follow the resource
rules in `.agents/rules/triton-slurm.md`.

For new research tooling, place reusable commands with the domain they
investigate rather than collecting all Python files under `audits/`. Keep
shared runtime behavior in the corresponding production package, and make
analysis commands reusable across configs and runs. The detailed placement
rules are in [`research/analysis/`](research/analysis/README.md).

The production dependency tests prohibit importing `scripts/` from reusable
packages. See [repository architecture](../docs/architecture/README.md) and
[running commands](../docs/operations/RUNNING_COMMANDS.md).

The canonical analysis commands are described in
[`research/analysis/`](research/analysis/README.md).
