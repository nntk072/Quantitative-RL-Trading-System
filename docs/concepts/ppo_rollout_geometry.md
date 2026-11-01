# PPO rollout geometry

For PPO, one rollout contains observations collected from the configured
vectorized environments. If each of \(N\) environments contributes \(T\)
steps, the aggregate rollout has \(N\times T\) transitions. The minibatch
size and number of epochs then determine how many optimizer minibatches process
that rollout.

```text
aggregate samples = effective environments × steps per environment
updates per rollout = ceil(aggregate samples / minibatch size) × epochs
```

The project builder uses `env.n_envs`, `ppo.n_steps`, `ppo.batch_size`, and
`ppo.n_epochs`. When a vector environment factory is present and the configured
environment count exceeds one, it divides configured PPO `n_steps` by the
environment count before constructing SB3 PPO. Consequently, saved model
values and manifest fields are the right source for the realized rollout, not
an assumption that the YAML `n_steps` always means per-environment steps.
Training manifests record logical/effective environment count, per-env steps,
aggregate rollout size, batch size, and updates per rollout.

Increasing environments changes more than speed: it changes how many episodes
or market segments can be sampled concurrently and can affect resource use.
The training configuration stage may cap environments unless a quality-run
resource contract requires exact geometry. A comparison that changes this
geometry should report it as a changed method.

The default configuration currently sets `env.n_envs: 8`, `ppo.n_steps: 2048`,
and `ppo.batch_size: 512`; those are defaults, not a statement about any
historical run. Read the resolved run config and manifest. Implementation:
[`build_agent`](../../learning/rl/agent.py),
[`configuration_stage`](../../training/runner/configuration_stage.py),
and [manifest writer](../../training/artifacts/manifests.py).

For an experiment, capture at minimum:

- algorithm and action space;
- requested and effective environment count;
- `n_steps`, aggregate rollout samples, batch size, epochs;
- seed mapping across workers;
- hardware and measured throughput;
- resolved config and source identity.

See [training](../framework/training_and_experiments.md),
[run artifacts](../reference/artifacts.md), and the
[GH200 throughput audit](../research/gh200_throughput_audit.md).
