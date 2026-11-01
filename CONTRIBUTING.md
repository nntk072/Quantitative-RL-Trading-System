# Contributing

Contributions should preserve the repository's domain boundaries and make
behavior reproducible. Read the root [agent/developer guide](AGENTS.md), the
relevant package `README.md`, and the matching page in [module guides](docs/modules/README.md)
before changing a subsystem.

## Change workflow

1. Identify the owning package and trace its callers, configuration, and tests.
2. Keep runtime settings in `config/`; do not add a second source of truth.
3. Add or update focused tests for behavior, compatibility, and failure cases.
4. Update the package guide and the relevant concept/reference documentation
   when public behavior, configuration, schemas, commands, or artifacts change.
5. Run the scoped tests and checks for the change. Before commit or push, run
   the full-tree checks required by
   [CI verification](.agents/rules/ci-verification.md).
6. Review the diff for user data, caches, checkpoints, and generated outputs.

## Architecture and scientific evidence

Production package dependencies and serialized action/observation contracts
are executable architecture constraints. Do not bypass them for convenience.
A passing software test establishes only the behavior it covers. Research
claims require the declared data split, execution assumptions, run identity,
and evaluation evidence described in the [research guide](docs/research/README.md).

The project source and developer-authored documentation are licensed under the
[MIT License](LICENSE). Do not contribute material that you do not have the
right to license under those terms. Dependencies, market data, model artifacts,
and research evidence may have separate terms; see the
[repository standards decisions](docs/decisions/repository_standards.md) and
[project limitations](docs/architecture/risks_and_technical_debt.md).
