# Add a reward

A reward is the learner's optimization signal. It must be reconciled with the
simulated account path and must not silently alter execution or hard account
guardrails.

1. Define the objective mathematically, its units and scaling, equity valuation
   timing, episode reset behavior, and treatment of non-finite or terminal
   states.
2. Implement it in the existing reward selection path. Preserve the behavior
   of established reward modes.
3. Test positive, negative, and zero account changes, partial exits, costs,
   liquidation, episode boundaries, and finite outputs.
4. Verify reward components against actual equity changes and ensure costs are
   not counted twice.
5. Add a configured comparison that changes only the reward where feasible.
   Evaluate trading outcomes and policy behavior, not reward totals alone.

See the [reward concept](../concepts/rewards.md),
[reward reference](../reference/rewards.md), and
[environment guide](../../simulation/environment/README.md).
