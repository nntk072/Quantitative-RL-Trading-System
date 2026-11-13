# Operations

Operational guides describe supported runtime environments and procedures.
Research experiment definitions live in the research catalog rather than in a
separate operational plan.

- [Triton environment and resource workflow](triton.md)
- [Command reference](RUNNING_COMMANDS.md)
- [Paper/live deployment boundary](DEPLOYMENT.md)
- [Hardware and environment matrix](hardware.md)
- [Performance engineering](performance.md)
- [Command cookbook](cli_cookbook.md)
- [Research workflow](../research/workflow.md)

Agent-support rules under `.agents/` are optional developer tooling for
repository improvement; they are not runtime or scientific configuration.

```{toctree}
:maxdepth: 1
:caption: Operations guides

triton
RUNNING_COMMANDS
DEPLOYMENT
live-status
hardware
performance
cli_cookbook
```

Check command help and scheduler state before acting. Historical run records
are evidence, not live scheduler status.
