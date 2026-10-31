# Scripts

`scripts/` contains explicit command-line workflows for research analysis,
data maintenance, validation, and cluster operations. Shared behavior belongs
in its owning production package; scripts should parse inputs, call that
behavior, and write clearly identified outputs.

## Areas

| Path | Responsibility |
|---|---|
| `scripts/research/analysis/` | Canonical analysis, evaluation, report, and evidence-verification commands |
| `scripts/research/audits/`, `benchmarks/`, `strategy_checks/` | Focused data, performance, and strategy diagnostics |
| `scripts/research/thesis/` | Deprecated import and command-path adapters for preserved research references |
| `scripts/maintenance/` | Controlled data/cache and repository maintenance workflows |
| `scripts/compute/slurm/` | Slurm wrappers and allocation-side command launchers |
| `scripts/dev/` | Developer checks and repository-local support commands |
| `scripts/train/` | Training entrypoints retained for compatibility or specialized workflows |

Before running a script, inspect `--help`, its resolved input/output paths, and
whether it reads or writes experiment evidence. Research scripts should record
their inputs and assumptions; operational wrappers must follow the resource
rules in `.agents/rules/triton-slurm.md`.

The production dependency tests prohibit importing `scripts/` from reusable
packages. See [repository architecture](../docs/architecture/README.md) and
[running commands](../docs/operations/RUNNING_COMMANDS.md).

The canonical analysis commands and compatibility boundary are described in
[`research/analysis/`](research/analysis/README.md) and
[`research/thesis/`](research/thesis/README.md).
