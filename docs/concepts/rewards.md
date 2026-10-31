# Rewards

The reward is the signal used to update the policy. It is not the same thing
as net account return, a trade ledger, or an evaluation score. Reward modes
must be declared in the resolved run configuration and interpreted alongside
account outcomes.

The repository supports multiple reward families, including differential
Sharpe, realized PnL, R-multiple, and normalized equity-change objectives.
Their scale, discounting, episode reset, and treatment of open positions can
differ. A reward change is a research intervention and should not be silently
introduced into a baseline.

Good reward validation checks sign and scale against account transitions,
ensures execution costs are not counted twice, and verifies that a flat or
loss-making trajectory does not receive an unexplained favorable objective.
Training reward improvement alone is not evidence of improved trading.

See [reward reference](../reference/rewards.md),
[learning](../modules/learning.md), and
[evaluation](../modules/evaluation.md).
