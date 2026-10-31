# Command-line interfaces

The installed command surfaces currently include:

| Canonical command | Deprecated compatibility alias | Owns |
|---|---|---|
| `qrl-data` | `thesis-data` | Market data preparation, discovery, and experiment-run cache preparation. |
| `qrl-train` | `thesis-train` | Training and legacy baseline/backtest operations. |
| `qrl-evaluate` | `thesis-evaluate` | Checkpoint evaluation and report/reanalysis commands. |
| `qrl-experiment` | `thesis-experiment-run` | Variant catalog, run resolution, and experiment-run operations. |
| `qrl-compute` | `thesis-compute` | Device and resource diagnostics. |
| `orchestra` | Engineering workflow orchestration. |

The former `thesis-*` commands remain registered as deprecated compatibility aliases
for existing scripts and historical run instructions. Use the `qrl-*` commands
in new workflows. The aliases dispatch to the same implementations;
they do not select different configurations or behavior.

Inspect available operations with `--help`. A help check does not launch training or allocate a compute resource. Triton allocation requirements are documented separately in [operations](../operations/triton.md).
