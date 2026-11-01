# Foundations: quantitative trading and reinforcement learning

This page gives the mental model for reading the rest of the portal. It is a
learning resource; exact software contracts live in the linked reference pages.

## What “quant” means here

Quantitative trading turns market observations into rules that can be stated,
implemented, measured, and challenged. A useful research question is narrower
than “does AI make money?” For example: *under a fixed data split, action
schema, execution model, and risk budget, does a policy change one measured
behavior relative to a matched control?* A historical simulation can answer
questions about that simulation. It cannot guarantee live fills or future
returns.

This repository studies policies that act on US100/US500 market data. The
pipeline transforms timestamped bars into causal features, builds an
observation, decodes an action into a trade intent, applies execution and risk
rules, and records outcomes. Start at the [system overview](../index.md), then
follow the [framework guide](../framework/index.md).

## The decision problem

At decision time \(t\), the environment exposes observation \(o_t\). The
policy samples or selects action \(a_t\); the simulator advances to a later
decision point and returns reward \(r_t\), next observation \(o_{t+1}\), and
termination information. The agent tries to improve expected discounted
return

\[
J(\pi)=\mathbb{E}_{\pi}\left[\sum_{t=0}^{T}\gamma^t r_t\right].
\]

The reward is a training objective, not a synonym for profit. Fees, spread,
slippage, risk limits, episode boundaries, and reward shaping affect what the
objective means. Inspect [reward design](../concepts/rewards.md),
[execution costs](../concepts/execution_and_costs.md), and the exact
[action schema](../reference/action_schemas.md) together.

## MDP and partial observability

An MDP is commonly written \((S,A,P,R,\gamma)\): states, actions, transition
distribution, reward, and discount. A trading policy does not observe the
complete market state. It gets a finite history of bars/features and a compact
account/position state, so the practical model is partially observable. The
policy may infer useful context from history, but an encoder cannot recover
information absent from the data.

The code represents observations as branches (for example a sequence, account
vector, and optional masks). Padding and validity masks matter: zero-filled
missing history is not the same as an observed zero. Schema order and meaning
are versioned because they determine what a checkpoint sees. See
[observations](../concepts/observations_and_actions.md),
[observation schemas](../reference/observation_schemas.md), and the
[partial observability guide](../concepts/partial_observability.md).

## PPO and SAC in this repository

PPO is an on-policy actor-critic method. It collects a rollout under the
current policy, estimates advantages using rewards, value predictions,
\(\gamma\), and GAE \(\lambda\), then performs clipped policy updates. For
vectorized environments, the rollout sample count is the product of per-env
steps and number of environments. The builder may adjust per-env `n_steps` to
preserve configured aggregate geometry; always use the saved manifest for a
run rather than infer its realized geometry from defaults. The source of truth
is [`learning/rl/agent.py`](../../learning/rl/agent.py) and the current
[`default.yaml`](../../config/base/default.yaml).

SAC is an off-policy actor-critic algorithm with replay and entropy
regularization. This code requires a continuous `Box` action space for SAC.
Trade-setup categorical actions use PPO's masked categorical distributions and
are rejected for SAC by the agent builder. Availability of an encoder name
does not imply every encoder/action/algo combination is supported.

| Choice | Practical fit | Repository constraint |
|---|---|---|
| PPO | Repeated fresh rollouts and discrete or continuous configured policies | Current defaults and custom categorical setup distributions are PPO paths. |
| SAC | Continuous actions with replay-based updates | Requires a continuous `Box` action space. |
| Constrained PPO | Researching a separate cost constraint alongside reward | Optional primal-dual callback; it does not replace hard environment guardrails. |

See [PPO rollout geometry](../concepts/ppo_rollout_geometry.md),
[SAC](../concepts/sac.md), and [constrained RL](../concepts/constrained_rl.md).

## Action parameterization

The action is a proposal. It can encode direction, intensity, stop selection,
risk, target selection, management mode, or a categorical trade setup,
depending on the configured schema. The environment resolves this proposal
against current eligibility, strategy references, account state, and risk
limits. An action coordinate is not an executed order until those checks and
the fill path succeed. See [trade lifecycle](../concepts/trade_lifecycle.md)
and [action reference](../reference/action_schemas.md).

## Reading evidence without overclaiming

Separate three levels:

1. A software trace demonstrates deterministic behavior for fixed synthetic
   inputs.
2. A frozen replay recomputes specified outcomes from a checkpoint and frozen
   inputs.
3. A new training campaign estimates outcomes across its declared seeds and
   protocol.

These are different evidence claims. The current registry records one R2
frozen cohort recomputation and one R2 software trace, while other evidence is
R1 or incomplete; it records no R3/R4 result. Read the
[result registry](../reproduce/result_registry.md) and
[evidence levels](../concepts/reproducibility.md) before interpreting a plot.

## Suggested path

1. [Market data tutorial](tutorials/01_market_data.ipynb)
2. [Causal features tutorial](tutorials/02_causal_features.ipynb)
3. [Trading and risk tutorial](tutorials/03_trading_and_risk.ipynb)
4. [Environment tutorial](tutorials/04_environment.ipynb)
5. [Evaluation tutorial](tutorials/05_evaluation.ipynb)
6. [Reproduce a recorded result](../reproduce/index.md)

The tutorials use bounded examples; none requires GPU training or proprietary
market data.
