# Training

`training/` composes resolved configuration, prepared inputs, features,
simulation environments, and a learner into a recoverable training run. It
owns orchestration and lifecycle, while market data, features, execution, and
learning retain their domain responsibilities.

```text
resolved config -> dataset/cache -> environment workers -> learner
                -> diagnostics/checkpoints -> run artifacts
```

| Area | Responsibility |
|---|---|
| `runner/` | Stage training setup and execute the training lifecycle. |
| `setup/` | Construct environment and callback components. |
| `callbacks/` | Capture learner and environment diagnostics without changing trading semantics. |
| `cli.py` | User-facing training command surface. |

Recovery requires matching run identity, resolved configuration, data/cache
identity, model schema, and compatible checkpoint state. A completed step
budget or saved checkpoint alone is not a successful trading result. See the
[training guide](../docs/modules/training.md),
[run how-to](../docs/how-to/run_training.md), and
[data flow](../docs/architecture/data_flow.md).
Callback behavior is described in the local [callback guide](callbacks/README.md).

## Run lifecycle

The runner resolves settings and input identity, prepares environment
construction arguments, creates worker instances, invokes the learner, and
collects callbacks/checkpoints until the declared budget or stop condition.
Setup modules construct reusable worker and callback components; the runner
coordinates their lifecycle. A failure before learner initialization is a
setup/recovery issue, not evidence about policy learning.

Run identity includes the effective configuration, source/data inputs,
training budget, seed, and compatible policy schema. Resume must continue the
same declared run only when its fingerprint and checkpoint state validate.
Changing code or config while work is live can make the artifact chain
ambiguous; preserve the resolved config and worker logs with each attempt.

Focused tests are under `tests/unit/training/`, with integration checks for
training entrypoints and checkpoint behavior. Use the
[training how-to](../docs/how-to/run_training.md) for the safe launch sequence.
