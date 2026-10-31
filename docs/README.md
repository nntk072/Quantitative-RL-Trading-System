# Documentation

This is the reader entry point for the quantitative reinforcement-learning
trading framework. The pages follow subsystem boundaries and explain the
purpose, ownership, interfaces, runtime behavior, assumptions, and limits of
each part before linking to source.

## Understand the system

- [Architecture](architecture/README.md): context, packages, import
  dependencies, data flow, model composition, and runtime sequences.
- [Module guides](modules/README.md): responsibilities and boundaries for
  every production package and the test system.
- [Concepts](concepts/README.md): observations/actions, trade setups, market
  structure, execution costs, and account risk.
- [Reference](reference/README.md): versioned schemas and stable contracts.
- [Model and experiment catalog](model_variants.md): generated list of
  configured agents and research comparisons.
- [Glossary](glossary.md): canonical meanings for trading, RL, and evidence
  terms.

## Work with the framework

- [Configuration](config.md): source settings, composition, and cache identity.
- [Research](research/README.md): questions, findings, methodology, and
  validity limits.
- [Reproducibility](concepts/reproducibility.md): source, configuration, data, run, and
  evaluation identity expected for a result.
- [Operations](operations/triton.md): environments, storage, and Triton
  resource workflow.
- [Commands](operations/RUNNING_COMMANDS.md): current executable commands.
- [Deployment](operations/DEPLOYMENT.md): paper/live boundaries and promotion
  controls.
- [Agent rules](../AGENTS.md): repository invariants and contributor workflow.
- [Documentation maintenance](MAINTAINING.md): sources of truth and update
  expectations.
- [Contributing](../CONTRIBUTING.md): architecture-aware change and validation
  workflow.
- [Architecture decisions](decisions/README.md): durable project choices.

## Guided use

- [Tutorials](tutorials/README.md): a project tour and bounded reproducible
  smoke workflow.
- [How-to guides](how-to/README.md): prepare data, build caches, train,
  evaluate, run experiments, and extend the system.

The active experiment queue and its period-role decisions remain at the
[project execution plan](thesis/master_project_execution_plan.md) until its
compatibility migration is complete. That retained path does not define the
software architecture or project identity.
