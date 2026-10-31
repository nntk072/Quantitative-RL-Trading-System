# Sustainable Equity Growth Experiments

## Scope and baseline

This research family changes the PPO reward objective while retaining the
single-instrument US100 environment, the existing action schema, execution
simulator, feature inputs, PPO implementation, and hard account guardrails.
It does not introduce multi-asset allocation or replace the default DSR reward.

The configured baseline remains `env.reward_mode: dsr`. The current reward
factory also supports `pnl`, `rr`, and `equity_delta_r`; `equity_delta_r` is a
fixed-risk-normalized equity increment, not a log-growth objective. The
variant resolver now accepts that existing mode and the new
`equity_log_growth` mode.

The authoritative reward path is `env.reward_mode` through environment reward
initialization. CLI `--reward` selects legacy sweep shaping and is not the
economic objective; run logs now record both separately. The baseline PPO
defaults remain in `config/base/default.yaml` (`gamma=0.99`, GAE `0.95`, clip
`0.2`, learning rate `3e-4`, 20M requested steps). No default changes to DSR or
PPO behavior are part of this implementation.

The environment records account equity after each transition. Account equity
is balance plus open PnL. Bid/ask fills, modeled slippage, and commissions are
already reflected in those account values, so the growth reward does not
subtract costs a second time. The training environment closes positions at the
NY session boundary and currently does not model overnight financing. The
objective includes simulator-supported costs but cannot claim financing-cost
coverage. A cash payout/reset changes account equity and therefore appears as
an equity change; this objective measures account equity, not account equity
plus previously withdrawn payouts.

Execution audit: bid/ask and configured slippage are applied by the broker
fill path; commissions are deducted when configured. US100 spread is configured
as 0.6 points and raw tick quotes can supply their own bid/ask. Explicit
commission defaults to zero. The configured 5-point adverse slippage applies to
stop/target fills; the extra tick-entry slippage parameter defaults to zero.
Stage 2 sets added randomized fill latency to zero and keeps all other cost
settings at their repository defaults, so its stop/target costs include the
configured 5-point slippage.

## Growth reward

For previous and current account equity `E_before` and `E_after`, the reward is

```text
r_t = 100 * (log(E_after) - log(E_before))
```

The scale is recorded as `env.equity_log_growth_scale` and defaults to `100`.
The endpoints come from the environment's equity ledger, covering realized and
unrealized changes, including execution costs. A hard risk breach with positive
ending equity receives its measured log-equity change; the environment ends
the episode through its existing guardrail. Nonfinite equity fails loudly;
nonpositive starting equity is invalid, and nonpositive ending equity receives
the configured terminal penalty.

Without discounting and while equity remains positive, the rewards telescope
to `100 * log(E_terminal / E_initial)`. With PPO `gamma=0.99`, PPO's
discounted objective is not terminal log growth. The reward comparison keeps
the existing PPO gamma fixed and records this limitation; it does not tune
gamma separately for the growth arm.

## Constrained-PPO audit

`LagrangianRiskCallback` is opt-in and PPO-only. It reads per-step daily,
maximum-loss, and enabled trailing-risk increments from environment info,
normalizes them to fractions of the configured maximum-loss limit, applies
`lambda * cost` to the PPO rollout rewards, accumulates completed-episode cost,
and updates a bounded multiplier at rollout end. A hard breach contributes a
unit cost. This is an empirical expected-cost penalty, not a breach-probability
guarantee. Environment hard limits remain in force.

The configured cost uses the largest normalized component per step, avoiding
double-counting overlapping account-risk measures. The default
`cost_discount_gamma=1.0` differs from PPO's default `gamma=0.99`: PPO discounts
the injected penalty, while the multiplier estimator otherwise accumulates
undiscounted cost. The existing Q5 defaults and results are preserved. The new
growth-plus-Q5 arm explicitly sets `cost_discount_gamma=0.99` so its budget and
PPO penalty use the same discount horizon. It sets
`episode_cost_budget=0.1`: the allowable discounted episode cost is 0.1 times
the maximum-loss limit in normalized cost units. This is a dual-learning
target, not a 10% breach-probability bound.

The multiplier updates only when an episode completes. The Q5 callback stores
its multiplier/config on the PPO model, but the training setup rejects Q5
checkpoint resume because partial full-split environment/account state is not
restored. A constrained pilot is informative only if it records completed
episodes and at least one dual update; otherwise Q5 did not yet affect learning.
This means exact interrupted Q5 continuation is not currently available; the
Q5 stage must stay deferred until that limitation is accepted for a bounded
uninterrupted run or the training checkpoint contract is extended and tested.

## Staged comparison

The variants in `config/experiments.yaml` are 2M-step, seed-50 development
screening arms. They use the current A4a action overlay, TCN for PPO, dollar-band
risk sizing capped at $900 with a $100 hold floor, $5,000 daily and $10,000
maximum loss limits, no peak-trailing stop, and zero added randomized fill
latency.
The first experiment run specification includes only the matched PPO reward pair.
Final evaluation uses stochastic actions, matching the action mode used during
PPO training; evaluation action seeds are recorded. Q5 and SAC remain registered
for later stages but do not run until their prerequisite gates pass. The
per-variant risk YAML files keep the risk policy explicit.

1. `sustainable_growth_ppo_dsr`: reference PPO + DSR.
2. `sustainable_growth_ppo_log`: matched PPO + log equity growth; reward is the
   only planned intervention.
3. `sustainable_growth_ppo_log_q5`: same growth policy with the existing
   Lagrangian risk mechanism enabled.
4. `sustainable_growth_sac_log`: a later algorithm comparison using SAC with
   the same Box action schema and growth reward; its optimizer is the planned
   difference.

The first pair answers RQ1. The second pair (2 vs 3) answers the Q5 screening
question. SAC follows only after the PPO reward and constrained pathway are
validated. One seed and 2M steps can detect implementation faults and obvious
collapse; they cannot establish superiority. Full 20M experiment runs require
separate authorization.

Training uses the 2025 split. The 2026 report interval has already been exposed
in prior experiments, so it is exploratory/report-only and cannot support a
fresh confirmatory claim. No untouched chronological holdout is currently
identified; RQ4 confirmation remains unavailable until one is established.

## Evidence gates

- **Correctness:** unit and environment tests cover signs, zero change,
  telescoping, no double-counting of ledger costs, breach accounting, nonfinite
  values, reset, config resolution, and the recorded reward scale. Existing
  default-DSR behavior remains unchanged.
- **PPO pilot viability:** both matched arms have finite diagnostics and
  interpretable action/trade activity; report return and survival separately.
- **Q5 viability:** show completed episode counts, multiplier updates, episode
  costs in declared units, and no action collapse. Preserve the hard guardrails.
- **SAC compatibility:** verify PPO and SAC expose the same overlay action
  schema before training; report any residual optimizer differences.
- **Generalization:** require independent seeds and an untouched chronological
  period before claiming a durable performance improvement.

## Observed research findings

The matched seed-50, 2M-step reward screen compared PPO + DSR with PPO +
log-equity growth on the 2025 training interval. Both reached the hard maximum
loss floor before completing that interval. The 2026 replay was already
exposed and is exploratory/report-only.

| Policy | Split | Net return | Maximum drawdown | Sharpe | Profit factor | Win rate | Trades | Result |
|---|---|---:|---:|---:|---:|---:|---:|---|
| PPO + DSR | Training | -10.15% | 36.69% | -0.371 | 0.965 | 42.8% | 1,110 | Hard floor reached |
| PPO + log-equity growth | Training | -10.18% | 33.66% | -0.336 | 0.962 | 41.0% | 847 | Hard floor reached |
| PPO + DSR | Exposed report-only | -10.07% | 29.04% | -0.495 | 0.947 | — | 683 | Hard-floor stop |
| PPO + log-equity growth | Exposed report-only | -10.16% | 30.67% | -0.400 | 0.941 | — | 512 | Hard-floor stop |

These results reject both tested policies as sustainable candidates under this
screen. They do not identify whether entry quality, exit behavior, regime
change, reward alignment, or execution cost caused the decline. The matched
regime-attribution report records the separate feature-normalization and
regime-context findings, including their limits:
[Regime attribution](regime_attribution.md).

The practical lesson is to treat positive early-period equity as insufficient
evidence. Candidate policies must survive the full training interval and
report their full-path trade and risk behavior before any test-period result is
interpreted. No result in this note establishes generalization or a fresh
out-of-sample improvement.
