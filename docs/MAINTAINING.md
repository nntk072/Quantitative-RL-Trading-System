# Maintaining project documentation

Documentation has one primary home for each kind of knowledge:

| Location | Owns |
|---|---|
| Root `README.md` | Project purpose, capabilities, quick entry points, and limitations |
| Package `README.md` | Local subsystem ownership, architecture, contracts, tests, and extension path |
| `docs/architecture/` | System structure, dependencies, flows, deployment, and cross-cutting constraints |
| `docs/modules/` | Short cross-package module map and reading order |
| `docs/concepts/` | Domain and research explanations |
| `docs/reference/` | Exact names, schemas, options, units, and artifact contracts |
| `docs/how-to/` | Task-oriented procedures |
| `docs/tutorials/` | Guided learning examples with explicit evidence limits |
| `docs/research/` | Research questions, methods, findings, and validity statements |
| `docs/operations/` | Human-facing runtime and deployment procedures |
| `.agents/` | Agent navigation and implementation rules |
| Tests | Executable architecture and compatibility rules |
| `config/` | Behavior settings and experiment metadata |

## Change documentation with the owning interface

When a public behavior, schema, configuration key, command, or generated
catalog changes, update its reference page and local package guide in the same
change. Update architecture diagrams only when ownership or flow changes.
Research results belong with their protocol and evidence lineage; do not
rewrite a historical result to fit a new presentation.

Use `./tools/check docs` to validate maintained links, package-guide coverage,
the generated dependency model, and generated variant catalog. Keep examples
bounded; do not make documentation CI launch training or use external data.

Avoid duplicate authoritative explanations. Link to the source page instead
of copying tables across the root README, module overview, package README, and
reference pages.
