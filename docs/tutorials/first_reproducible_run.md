# First reproducible run

This short tour shows how configuration, prepared data, a model run, and its
evaluation evidence fit together. Use a small smoke configuration; this is a
workflow tutorial, not a recommendation to launch a long training run.

## 1. Inspect the configured interface

```bash
uv run qrl-data --help
uv run qrl-train train --help
uv run qrl-experiment catalog --check
```

The executable names are retained for compatibility during the project
identity migration. Read [command reference](../reference/cli.md) for current
ownership.

## 2. Prepare inputs and configuration

Follow [prepare market data](../how-to/prepare_market_data.md), then inspect
the resolved configuration and the chronological training/evaluation split.
Reuse a feature cache only when its input and feature identity match the run.

## 3. Run a bounded smoke

Use the repository's documented MVP/smoke option and a fixed seed. Inspect the
resolved settings before launching. Keep the output marked as a smoke result;
do not compare it as if it were a completed research experiment.

```bash
uv run qrl-train train --mvp --seed=42
```

On shared compute, first follow the [operations guide](../operations/triton.md)
and the repository's resource rules.

## 4. Evaluate and inspect evidence

Use the saved checkpoint and run identity with
[checkpoint evaluation](../how-to/evaluate_checkpoint.md). Review the equity
path, trade ledger, execution costs, account-limit events, and configuration
before interpreting aggregate metrics.

## What this tutorial does not establish

A successful command proves that this smoke path ran. It does not establish
profitable behavior, complete-year survival, comparative improvement, or
out-of-sample validity. Those claims require the protocol and evidence roles
described in [research methods](../research/README.md).
