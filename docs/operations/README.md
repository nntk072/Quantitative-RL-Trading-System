# Operations

The [research execution plan](research_execution_plan.md) records the active
research queue and its evidence gates.

Operational guides describe supported environments and procedures. Agent
allocation rules in `.agents/rules/` govern how coding agents use those
resources; this directory is the human-facing explanation.

- [Triton environment and resource workflow](triton.md)
- [Command reference](RUNNING_COMMANDS.md)
- [Paper/live deployment boundary](DEPLOYMENT.md)
- [Hardware and environment matrix](hardware.md)
- [Performance engineering](performance.md)
- [Command cookbook](cli_cookbook.md)

```{toctree}
:maxdepth: 1
:caption: Operations guides

research_execution_plan
triton
RUNNING_COMMANDS
DEPLOYMENT
live-status
hardware
performance
cli_cookbook
```

Check current command help and scheduler state before acting. Historical run
records are evidence, not live scheduler status.
