# Command cookbook

These examples summarize maintained entry points. Run `--help` against the
current checkout before copying options into an experiment record.

```bash
# Inspect installed command groups
qrl-data --help
qrl-train --help

# Prepare configured market data (review config and paths first)
qrl-data prepare --help

# Run the configured short software smoke path
qrl-train train --mvp

# Check a focused documentation change
./tools/check docs
```

The smoke path verifies software wiring and is not an economic result. Exact
flags may be provided by different console scripts in the active environment;
the [CLI reference](../reference/cli.md) and `pyproject.toml` entry points own
the current names. Research run execution and Triton scheduling have separate
evidence/safety procedures: use the
[research queue](../research/workflow.md) and
[Triton guide](triton.md), not a copied generic command.
