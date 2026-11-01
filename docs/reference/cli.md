# Command-line interfaces

The installed command surfaces are:

| Command | Owns |
|---|---|
| `qrl-data` | Market data preparation, discovery, and experiment-run cache preparation. |
| `qrl-train` | Training, baseline, and backtest operations. |
| `qrl-evaluate` | Checkpoint evaluation and report/reanalysis commands. |
| `qrl-experiment` | Variant catalog, run resolution, and experiment-run operations. |
| `qrl-compute` | Device and resource diagnostics. |
| `orchestra` | Engineering workflow orchestration. |

The `qrl-*` prefixes identify the repository command family. Inspect available
operations with `--help`. A help check does not launch training or allocate a
compute resource. Triton allocation requirements are documented separately in
[operations](../operations/triton.md).
