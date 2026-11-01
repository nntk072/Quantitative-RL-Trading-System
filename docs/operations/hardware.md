# Hardware and environment matrix

Choose an environment whose operating-system architecture and accelerator
backend match the installed Python environment. A device name in config is not
proof that a supported kernel actually runs.

| Platform | Python environment | Compute notes |
|---|---|---|
| ARM64 Triton GH200 | `.venv` | Use the ARM environment and validate CUDA with a real operation. Keep data and compute on the allocated node; login hosts are for inspection/launch only. |
| x86_64 Triton H100/H200 | `.venv-x86` | Use architecture-matched wheels; check device capability and package support. |
| V100 | `.venv-v100` when configured | Verify `sm_70` support and execute a real CUDA operation; the documented `.venv-x86` cu130 build is incompatible. |
| MI210 | `.venv-mi210` | Excluded from current project research policy; consult operations guidance before any non-research use. |
| CPU | matching local/node venv | Use for bounded docs, unit tests, and explicitly CPU-only evaluation; large feature/training workloads need an appropriate compute allocation. |

The table is an environment selection guide, not an availability report.
Check current hardware inventory, allocation, CPU/RAM, and project Slurm rules
before submitting work. See [Triton operations](triton.md),
[Python environment guide](../development/testing.md), and
the maintained [agent Slurm rules](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/main/.agents/rules/triton-slurm.md).
