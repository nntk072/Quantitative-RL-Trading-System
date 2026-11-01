# Training and experiments

Training composes resolved configuration, prepared data, feature identity, simulation, a learner backend, and artifact writing. Experiments add a controlled comparison layer around that run lifecycle. A result is interpretable only when those inputs and the comparison design are recorded together.

## Run lifecycle

1. **Resolve.** Load the base configuration and explicit overrides, validate the final tree, and write the resolved configuration. The YAML configuration is the source of truth; avoid hidden Python defaults for user-facing behavior.
2. **Prepare.** Select the declared data split and feature-cache identity. Cache identity includes content inputs, not only a manually incremented version.
3. **Construct.** Build the environment and learner from the resolved config. Record backend, seed, environment shape, and runtime/device metadata.
4. **Train.** Save checkpoints and logs into the run's artifact directory. Do not treat a successful optimizer loop as evidence of generalization.
5. **Finalize.** Write manifests and completion state atomically so a partial run cannot appear complete.
6. **Compare.** Match seeds, data, budgets, and evaluation protocol before attributing a difference to the treatment.

## Experiment contracts

A variant is a resolved treatment, not a filename label. Its identity must preserve the effective config and relevant source/data identity. Recovery should distinguish resumable incomplete work from completed immutable runs. The experiment runner owns provenance and lifecycle; scientific interpretation belongs in the result report and evidence registry.

## Practical entry points

Use the [run an experiment guide](../how-to/run_experiment) for the CLI workflow and the [experiment comparison tutorial](../learn/tutorials/advanced/experiment_comparison.ipynb) to inspect matched run records. The [training module guide](../modules/training) and [experiment module guide](../modules/experiments) explain package-specific options.

A short training smoke checks configuration, environment construction, and artifact wiring. It does not establish policy quality. For research decisions, follow [experiment design](../concepts/experiment_design), [evaluation methodology](../research/evaluation_methodology), and the active [research execution plan](../operations/research_execution_plan).

The curated [workflow API guide](../api/domains/workflows) links to generated training, experiment, and artifact references.
