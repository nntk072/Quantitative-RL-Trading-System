# Constrained reinforcement learning

Reward maximization and risk constraints answer different questions. A reward
can favor a behavior, while a separate cost signal and constraint can limit a
declared risk quantity. The environment's hard guardrails remain authoritative
for whether a trade is allowed or an episode stops; a learned multiplier is
not a substitute for those controls.

The repository has an optional primal-dual PPO path. It tracks a cost budget
and updates a non-negative Lagrange multiplier from observed costs. Configuration
includes the episode cost-budget fraction, dual learning rate, multiplier
maximum, and cost discount. The default YAML marks this as optional/research
only. The callback and the environment's hard limits must be interpreted
separately in results.

```text
policy objective: maximize reward − multiplier × cost
dual update:      increase pressure when measured cost exceeds its budget
hard guardrails:  independently reject/stop actions at configured limits
```

This schematic is explanatory; consult
[`learning/rl/callbacks.py`](../../learning/rl/callbacks.py)
and the resolved configuration for implementation details. The measured cost,
episode boundary, discount, and budget definition must be stated. A lower cost
on one rollout does not establish constraint satisfaction over deployment.

Read [risk and account limits](risk_and_account_limits.md),
[reward attribution](rewards.md), and the
[training guide](../framework/training_and_experiments.md).
