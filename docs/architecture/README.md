# System architecture

The system converts timestamped market data into model observations, applies
policy decisions through a risk-aware simulator, trains and evaluates agents,
and records the resulting artifacts. The architecture is split into stable
package boundaries so data processing, trading semantics, learning backends,
and broker integration can evolve independently.

## Architecture views

- [System context](context.md) shows the people and external systems around the
  framework.
- [Building blocks](building_blocks.md) explains the responsibilities of the
  production packages.
- [Dependency model](dependency_model.md) is generated from current Python
  imports and documents the allowed direction between packages.
- [Domain model](domain_model.md) shows the main trading and evaluation
  concepts without enumerating implementation classes.
- [Data flow](data_flow.md) follows prepared inputs through training and
  evaluation.
- [Model and policy architecture](model_and_policy_architecture.md) separates
  algorithm, encoder, policy distribution, action schema, and variant.
- [Runtime sequences](runtime/) cover data/features, environment steps,
  training, evaluation, experiment runs, and live/paper execution.
- [Deployment](deployment.md) describes local, cluster, artifact, and broker
  boundaries.
- [Migration records](migrations/README.md) document completed interface and
  path changes without creating a parallel work queue.
- [Cross-cutting concerns](cross_cutting_concerns.md),
  [quality attributes](quality_attributes.md), and
  [risks/technical debt](risks_and_technical_debt.md) cover architecture-wide
  constraints and limitations.

## Design constraints

Architecture tests enforce an acyclic production dependency graph, public
cross-package imports, backend-neutral evaluation and live interfaces, and
separation between reusable model components and learning algorithms. These
are executable constraints; diagrams describe the verified structure rather
than replacing those checks.

The system does not claim profitable trading or parity between historical
simulation and a live broker. Market data, feature alignment, costs, fills,
account guardrails, and checkpoint schemas all affect reported results.

## Package documentation

Each substantial source package has a local `README.md` for its concepts,
contracts, runtime behavior, configuration, tests, and extension points. The
[module guide](../modules/README.md) provides the cross-package reading order.
