# Documentation

This is the reader entry point for the quantitative reinforcement-learning
trading framework. The pages follow subsystem boundaries and explain the
purpose, ownership, interfaces, runtime behavior, assumptions, and limits of
each part before linking to source.

The intended [documentation website](https://nntk072.github.io/Quantitative-RL-Trading-System/)
and generated [Python API reference](https://nntk072.github.io/Quantitative-RL-Trading-System/api/)
are built from these maintained Markdown files and the Python package source.
The repository workflow is ready; the project owner must enable GitHub Pages
before these URLs serve the generated site.

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
- [Testing strategy](development/testing.md): test ownership, scoped gates, and
  the measured line and branch coverage baseline.
- [Commands](operations/RUNNING_COMMANDS.md): current executable commands.
- [Deployment](operations/DEPLOYMENT.md): paper/live boundaries and promotion
  controls.
- [Agent rules](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/main/AGENTS.md): repository invariants and contributor workflow.
- [Documentation maintenance](MAINTAINING.md): sources of truth and update
  expectations.
- [Source documentation policy](development/documentation.md): Google-style
  docstrings, comments, and useful diagrams.
- [Contributing](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/main/CONTRIBUTING.md): architecture-aware change and validation
  workflow.
- [Repository standards decisions](decisions/repository_standards.md): selected
  license and conduct policy, plus the verified security reporting route.
- [Architecture decisions](decisions/README.md): durable project choices.

## Guided use

- [Tutorials](tutorials/README.md): a project tour and bounded reproducible
  smoke workflow.
- [How-to guides](how-to/README.md): prepare data, build caches, train,
  evaluate, run experiments, and extend the system.

The active experiment queue and period-role decisions are recorded in the
[research execution plan](operations/research_execution_plan.md). That plan
does not define the software architecture or project identity.
