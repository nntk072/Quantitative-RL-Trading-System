# Concepts

Concept pages explain the domain and research ideas independently of a
particular source file. Use references for exact serialized fields and module
guides for package responsibilities.

## Foundations and implementation concepts

- [Partial observability](partial_observability.md): what a policy can and
  cannot infer from its finite, masked input.
- [Sequence models](sequence_models.md): TCN, GRU, Transformer, and
  multi-timeframe encoder trade-offs in this implementation.
- [PPO rollout geometry](ppo_rollout_geometry.md): how environment count,
  rollout length, minibatches, and updates interact.
- [SAC](sac.md): replay-based learning and supported action-space constraints.
- [Constrained RL](constrained_rl.md): optional primal-dual cost learning and
  its separation from hard account guardrails.
- [Market time and validation](data_time_and_validation.md): bar clocks,
  completed-timeframe alignment, purged folds, and cache identity.
- [Trade lifecycle](trade_lifecycle.md): action eligibility through fill,
  management, close, and account reconciliation.
- [Evaluation statistics](research_statistics.md): metric interpretation,
  inference, selection risk, and cost stress.
- [Mathematical notation](math_notation.md): symbols and units used across
  concept and result pages.
- [Simulation/live parity](simulation_live_parity.md): shared contracts and
  differences that still require explicit validation.

## Trading and policy concepts

- [Trade setups](trade_setups.md): entry idea, setup timeframe, direction,
  eligibility, and structural ownership.
- [Observations and actions](observations_and_actions.md): what a policy sees
  and how its output becomes a trading intent.
- [Market structure](market_structure.md): causal swings, imbalances, session
  context, and invalidation.
- [Liquidity sweeps](liquidity_sweeps.md): confirmed-level take, bounded
  overshoot, reclaim, and active event state.
- [FVG and IFVG](fvg_ifvg.md): three-bar imbalance geometry, inversion, and
  confirmation timing.
- [PO3 phase state](po3.md): sweep-triggered manipulation/distribution state.
- [SMT divergence](smt.md): paired confirmed swings across instruments.
- [Order blocks](order_blocks.md): displacement-based zone lifecycle and
  validity limits.
- [Execution and costs](execution_and_costs.md): quote selection, fills,
  spread, slippage, and accounting boundaries.
- [Risk and account limits](risk_and_account_limits.md): position sizing,
  daily and account limits, and hard guardrails.
- [Rewards](rewards.md): how optimization signals relate to account outcomes.
- [Experiment design](experiment_design.md): matched comparisons and evidence
  roles.
- [Reproducibility](reproducibility.md): run identity and result recovery.

Exact contract details are in [reference](../reference/README.md).

```{toctree}
:maxdepth: 1
:caption: Concept guides

partial_observability
causality
sequence_models
ppo_rollout_geometry
sac
constrained_rl
data_time_and_validation
trade_lifecycle
research_statistics
math_notation
simulation_live_parity
trade_setups
observations_and_actions
market_structure
liquidity_sweeps
fvg_ifvg
po3
smt
order_blocks
execution_and_costs
risk_and_account_limits
rewards
experiment_design
reproducibility
```
