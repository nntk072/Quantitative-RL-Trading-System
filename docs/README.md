# Documentation

This documentation is organized around the repository’s actual modules. A
reader can follow the system from market input to model decision, simulated
execution, training, and evaluation without first studying the source code.

## Start with the system

- [System architecture](architecture.md): end-to-end flow, key boundaries, and
  important limits.
- [Module guides](modules/README.md): one guide for each application module,
  plus cross-cutting software testing.
- [Configuration guide](config.md): where behavior is selected and how run
  settings fit together.
- [Model and experiment catalog](model_variants.md): generated index of
  selectable algorithms, encoders, and comparison roles.

## Research and evidence

- [Research guide](research/README.md): research questions, findings, and
  interpretation limits.
- [Thesis validation protocol](thesis/validation_protocol.md): roles of
  training, validation, and previously inspected test periods.
- [Threats to validity](thesis/threats_to_validity.md): known limitations in
  data, execution, and inference.
- [Master project execution plan](thesis/master_project_execution_plan.md):
  the operational thesis work queue.

## Operating the repository

- [Triton operations](operations/triton.md): environments, storage, resource
  allocations, and troubleshooting.
- [Command guide](operations/RUNNING_COMMANDS.md): supported command examples.
- [Deployment boundary](operations/DEPLOYMENT.md): paper and live runtime
  considerations.
- [Shared agent rules](../AGENTS.md): repository invariants and required
  engineering workflow for coding agents.

## Documentation style

Module pages explain purpose, concepts, inputs, outputs, diagrams, assumptions,
and limitations. They keep source references secondary. Research pages explain
the question, comparison, result, and evidence limits. Reader-facing pages use
clear names and describe setup and outcomes; exact input identities remain in
machine-readable run records.
