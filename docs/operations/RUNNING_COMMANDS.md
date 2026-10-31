# Command reference

This page lists safe command discovery and small verification operations. The
the canonical installed executable names use the project-oriented `qrl-*` prefix;
project-oriented names should be added together with working aliases and tests,
not guessed in documentation.

## Environment

Use the Python environment matching the host architecture. On Triton, `.venv`
is for ARM64/GH200 and `.venv-x86` is for x86_64. See the
[Triton operations guide](triton.md) for setup, storage, resource checks, and
Slurm rules.

## Discover commands

```bash
uv run qrl-data --help
uv run qrl-train --help
uv run qrl-evaluate --help
uv run qrl-experiment --help
uv run qrl-compute --help
orchestra --help
```

Use the active environment's executable directly when `uv` does not match the
compute-node architecture. Command help is read-only and does not start a
training run.

## Common bounded checks

```bash
# Validate maintained documentation and generated indexes.
./tools/check docs

# Check that generated variant documentation matches its source metadata.
uv run qrl-experiment catalog --check

# Inspect the bounded training interface before use.
uv run qrl-train train --help

# Inspect checkpoint evaluation without retraining.
uv run qrl-evaluate reanalyze --help
```

A short smoke command can still create files and consume compute; inspect the
resolved configuration and output paths before starting it. A smoke result is
not a completed experiment or economic result.

## Configuration overrides

Training accepts resolved configuration inputs and command-line overrides.
Inspect `--help`, then verify the effective configuration saved with the run.
Do not treat an override string as proof that the value was accepted or used.

## Compute and live operations

Use the current [resource and deployment procedures](README.md) before
allocating shared compute or connecting to a broker. Do not start training,
cache construction, or evaluation from a login shell when repository rules
require a compute allocation. Paper/live operation requires the separate
promotion and risk checks; historical backtest success is not authorization to
submit orders.
