# Soft Actor-Critic (SAC)

SAC is an off-policy actor-critic algorithm. It learns a stochastic policy and
critics using replayed transitions, with an entropy term that rewards useful
action diversity. This differs from PPO's repeated updates on newly collected
rollouts.

The project builds Stable-Baselines3 SAC with configured learning rate, replay
buffer size, batch size, target-update coefficient, discount, train frequency,
gradient steps, entropy coefficient, and learning-start threshold. The exact
defaults are in `config/base/default.yaml`; the resolved config and training
manifest describe an individual run.

## Compatibility in this codebase

The builder rejects SAC unless the environment action space is continuous
Gymnasium `Box`. Trade-setup actions currently require PPO's masked categorical
distribution, so they cannot be combined with SAC through the supported builder
path. SAC is implemented and has integration/unit tests, but that does not
mean every policy head, action schema, or research protocol has been validated
for it.

## Experiment considerations

- Replay changes the sample reuse and data-age profile; describe it when
  comparing against PPO.
- Keep the same market partitions, costs, observation, and risk constraints
  when isolating the algorithm factor.
- Report replay buffer configuration and total environment interactions.
- Distinguish an algorithm smoke test from a trained or economically useful
  result.

Implementation: [`learning/rl/agent.py`](../../learning/rl/agent.py). See also
[PPO rollout geometry](ppo_rollout_geometry.md),
[action schemas](../reference/action_schemas.md), and
[SAC integration test](../../tests/integration/test_sac_agent_integration.py).
