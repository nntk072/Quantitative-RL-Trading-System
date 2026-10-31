# Cross-cutting concerns

These concerns span package boundaries and should be considered whenever a
change crosses an interface.

## Causality and chronology

Data and features must be aligned to what was available at the decision time.
Higher-timeframe context uses completed bars. Training, validation, and test
periods retain their declared chronological roles.

## Reproducibility and identity

Record the resolved configuration, source revision, seed, data/cache identity,
schema versions, checkpoint, execution assumptions, and evaluation period.
Run identity and artifact provenance are shared infrastructure, not informal
filename conventions.

## Numerical and schema compatibility

Observation coordinates, action coordinates, category ordering, units,
normalization, and checkpoint constructor settings are compatibility
contracts. A same-width tensor may still have different semantics.

## Risk and execution

Hard guardrails are enforced by the environment/account boundary. Learned
penalties and policy observations do not replace them. Execution assumptions
and costs must be applied consistently and recorded.

## Evidence and claims

Software correctness, training viability, historical economic performance,
and out-of-sample generalization are separate claims. Reports should not infer
one from another.
