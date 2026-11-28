# Documentation

This is the reader entry point for the quantitative reinforcement-learning
trading framework. The pages follow subsystem boundaries and explain the
purpose, ownership, interfaces, runtime behavior, assumptions, and limits of
each part before linking to source.

The intended [documentation website](https://nntk072.github.io/Quantitative-RL-Trading-System/)
and generated [Python API reference](https://nntk072.github.io/Quantitative-RL-Trading-System/api/)
are built from these maintained Markdown files and the Python package source.
The GitHub Actions workflow builds and deploys the site; repository Pages
settings must use GitHub Actions as the deployment source.

## Understand the system

- [Architecture](architecture/README.md): context, packages, import
  dependencies, data flow, model composition, and runtime sequences.
- [Module guides](modules/README.md): responsibilities and boundaries for
  every production package and the test system.
- [Learn foundations](learn/foundations.md): quantitative trading, RL,
  partial observability, algorithms, and evidence boundaries.
- [Concepts](concepts/README.md): observations/actions, trade setups, market
  structure, causality, execution costs, and account risk.
- [Reference](reference/README.md): versioned schemas and stable contracts.
- [Model and experiment catalog](model_variants.md): generated list of
  configured agents and research comparisons.
- [Glossary](glossary.md): canonical meanings for trading, RL, and evidence
  terms.

## Work with the framework

- [Configuration](config.md): source settings, composition, and cache identity.
- [Research](research/README.md): questions, findings, methodology, and
  validity limits.
- [Research evidence report](research/research_evidence_report.md): a synthesis
  of the current negative research evidence and open scientific gates.
- [Reproducibility](concepts/reproducibility.md): source, configuration, data, run, and
  evaluation identity expected for a result.
- [Operations](operations/triton.md): environments, storage, and Triton
  resource workflow.
- [Operations](operations/README.md): supported environments and maintained
  command workflows.
- [Commands](operations/RUNNING_COMMANDS.md): current executable commands.
- [Deployment](operations/DEPLOYMENT.md): paper/live boundaries and promotion
  controls.
- [Repository standards decisions](decisions/repository_standards.md): selected
  license and conduct policy, plus the verified security reporting route.
- [Architecture decisions](decisions/README.md): durable project choices.

## Guided use

- [Tutorials](tutorials/README.md): a project tour and bounded reproducible
  smoke workflow.
- [How-to guides](how-to/README.md): prepare data, build caches, train,
  evaluate, troubleshoot, and run experiments.
Research methods, evidence status, and validity limits are documented in the
[research section](research/README.md). Operational guides cover supported
environments and maintained command workflows.
