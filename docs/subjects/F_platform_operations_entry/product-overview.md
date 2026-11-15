# Product overview

**Status:** draft
**Use this when:** You need to choose a workflow, identify the package that owns a decision, or interpret the output of a research run.

## Summary and use this when

Quantitative RL Trading System is a Python framework for intraday US100 and
US500 trading research. It exposes separate workflows for market-data
preparation, historical simulation, policy training, checkpoint reanalysis,
and experiment orchestration. An optional MetaTrader integration has its own
host requirements and execution safeguards.

A useful starting point is the question you want to answer. To inspect the
input data, start with the market-data tools. To evaluate a saved policy,
gather its resolved configuration and observation/action identity. To compare
variants, use the experiment and evaluation workflows with a declared design.

## Key terms

- [Observation schema](../../glossary.md)
- [Action schema](../../glossary.md)
- [Checkpoint](../../glossary.md)
- [Experiment run](../../glossary.md)
- [Artifact and lineage](../../glossary.md)

## Explanation

### From inputs to an evaluation record

1. Market-data loaders and transforms assemble timestamped input series.
   Completed higher-timeframe observations enter downstream calculations
   according to causal availability rules.
2. Feature builders produce configured market context. Train-fitted state
   is carried into later transformations as prescribed by the data split.
3. Decisioning declares the shape and meaning of observations and actions.
   Models and their adapters consume those contracts.
4. Simulation steps historical state under explicit order, account, cost, and
   risk assumptions. Training can use the simulated environment for rollouts.
5. Experiment workflows coordinate configured variants and collect artifacts.
   Evaluation derives metrics or reports using their declared inputs and
   validity rules.

See the [architecture guides](../../architecture/README.md) for package and
runtime diagrams and the [research guide](../../research/README.md) for study
design and evidence requirements.

### Where the entry points lead

`pyproject.toml` registers the installed console scripts. Each top-level
workflow parses its own commands, then forwards to the package that performs
the operation. A command registered for the distribution can be discovered
using its help surface in an installed environment.

| If you want to | Start with | Confirm first |
|---|---|---|
| Discover or prepare inputs | `qrl-data --help` | Data source, timestamp semantics, write location |
| Train or compare a baseline | `qrl-train --help` | Resolved config, workload, output identity |
| Reanalyze a saved checkpoint | `qrl-evaluate --help` | Checkpoint, matching config and data, period role |
| Inspect or coordinate variants | `qrl-experiment --help` | Catalog, run state, frozen variant inputs |
| Find scheduler interfaces | `qrl-compute --help` | Current platform runbook and allocation |
| Inspect the orchestration interface | `orchestra --help` | Workflow state and phase prerequisites |

Running `qrl-train --help` shows help for its default training path.
The same executable also dispatches recognized first-token commands for
backtesting, baselines, the LSTM baseline, and VAE. See the current
[command reference](../../operations/RUNNING_COMMANDS.md) before starting a
workflow.

### What to carry between stages

Keep the resolved configuration with the run. It gives later stages the
actual variant, feature, environment, and risk settings used by the producer.
A checkpoint is one part of a run record. A review of an evaluated policy
also needs the data identity, schema, period role, evaluation assumptions,
and ledger or report identity.

The [feature and normalization guide](../A_data_features/feature-causality-and-normalization.md)
covers transformations across split boundaries. The
[artifact lineage guide](../E_evaluation_research/artifacts-evidence-lineage.md)
shows how to connect a reported number to the recorded inputs.

### Failure modes

- Using a checked-in variant name as a substitute for the resolved run
  settings hides overrides that can affect input and output semantics.
- Reusing a checkpoint with a different feature ordering can change the
  meaning of values while preserving vector shape.
- Treating a produced report as an independent experiment can obscure which
  checkpoint, data, and run artifacts the report consumed.
- Comparing a PPO training signal directly to a ledger return conflates
  optimization and evaluation.

## Worked example

The Tier A notebook reads the installed console-script metadata and verifies
the routes for data, training, evaluation, experiments, compute, and
orchestration. It only inspects package registration.

```{toctree}
:hidden:

examples/product-overview
```

## Tasks

- Use the [market-data preparation guide](../../how-to/prepare_market_data.md)
  to choose and validate the starting inputs.
- Follow [run training](../../how-to/run_training.md) for configuration
  discovery and bounded workflow steps.
- Follow [evaluate a checkpoint](../../how-to/evaluate_checkpoint.md) to
  select the saved model and the corresponding inputs.
- Follow [run an experiment](../../how-to/run_experiment.md) when the design
  involves multiple variants or seeds.
- Read the [platform contract reference](../../reference/subjects/product-overview.md)
  for stable script targets and supported dispatch names.

## Contract

| Item | Contract | Source |
|---|---|---|
| Distribution | `quantitative-rl-trading-system`, Python `>=3.12` | `pyproject.toml` |
| Data | Prepare, discover, or prebuild experiment-run cache | `market_data/cli.py::main` |
| Training | Recognized first token selects a workflow, otherwise training receives the arguments | `training/cli.py::main` |
| Evaluation | `reanalyze` dispatches to checkpoint reanalysis | `evaluation/cli.py::main` |
| Experiments | Explicit run, status, reporting, cache, checkpoint, and catalog commands | `experiments/cli.py::main` |
| Compute | Capacity, resources, continuation, and worker dispatch | `compute/cli.py::main` |
| Configuration | Canonical in-repository defaults | `config/base/default.yaml` |

## Verify

- `tests/architecture/test_project_identity.py` asserts project and
  installed-script names and checks the command reference.
- `tests/architecture/test_public_imports.py` checks CLI module imports and
  production package inclusion in the wheel.
- `tests/architecture/test_dependency_rules.py` checks package directions
  and research workflow boundaries.
- Check economic findings through the [research evidence rules](../../research/validation_protocol.md).

## Limits and common mistakes

A working console script establishes a supported entry point. Successful
training establishes a run and its software outputs. Use chronological
evaluation, matched execution rules, account outcomes, and uncertainty to
interpret economic results. Treat an exposed interval according to its
reported role.

Use the [deployment runbook](../../operations/DEPLOYMENT.md) for decisions
about interacting with a terminal. Historical simulation and checkpoint
reanalysis use their own input and execution assumptions.

## Change checklist

- Update packaging, dispatch tests, and command documentation together when
  changing an installed command.
- Describe new behavior and configuration in the package or reference page
  that owns it.
- Preserve provenance and schema compatibility when changing workflow outputs.
- Update a runbook and its verification steps when behavior crosses into
  scheduling or broker I/O.

## Maintainer note

- Verified commit: `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`
- Verified date: 2026-11-15
- Owner: `architect`
