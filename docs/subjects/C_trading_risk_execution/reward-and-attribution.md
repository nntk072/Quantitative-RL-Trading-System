# Reward and attribution

**Status:** draft
**Use this when:** You need to distinguish the learner's step reward from account PnL and explain which component produced a signal.

## Summary and use this when

The environment first records the account transition, then calculates a configured reward from that transition and risk state. `reward_parts` makes the signal inspectable. Reward is an optimization signal, not a substitute for a trade ledger or a scientific outcome. Sources: `simulation/environment/accounting/step.py`, `simulation/environment/rewards.py`, `simulation/environment/reward_initialization.py`, `simulation/environment/episode/info.py`.

- Use this guide when a positive reward accompanies a losing trade or vice versa.
- Use it when reconciling partial exits, costs, and episode termination.
- Use the [subject reference](../../reference/subjects/reward-and-attribution.md) for keys and mode contracts.
- Use [reward modes](../../reference/rewards.md) for the short mode catalog.

## Key terms

- [MDP](../../glossary.md)
- [R multiple](../../glossary.md)
- [DSR](../../glossary.md)
- [Episode](../../glossary.md)
- [Risk budget](../../glossary.md)

## Explanation

### Account before reward

`_record_step_accounting` appends current equity, computes a step PnL from the change in equity, accounts for a payout withdrawn during the step, and calls `_calculate_reward`. Fill times can advance the equity valuation timestamp beyond a policy bar's nominal close. Source: `simulation/environment/accounting/step.py::_record_step_accounting`; test: `tests/unit/simulation/test_environment/test_equity_delta_reward.py`.

`_note_close` tracks realized close PnL and R for the current step; `_stamp_exit` stamps unique fill records and accumulates lifecycle outcomes. Several TP legs inside one step must not become several completed positions. Source: `simulation/environment/accounting/trades.py::_note_close`, `_stamp_exit`; test: `tests/integration/test_position_fill_accounting.py`.

Costs reach account equity through broker fills. A reward built from equity should not subtract modeled spread and commission again. Source: `trading/execution/broker.py::Broker.open_position`, `close_position`; `simulation/environment/rewards.py::EquityLogGrowthReward`; test: `tests/unit/simulation/test_environment/test_equity_log_growth_reward.py`.

### Mode-specific signals

`DSRReward` updates running first and second return moments and emits a differential Sharpe-style step signal with configured soft-band and breach terms. Its value is not realized portfolio Sharpe. Source: `simulation/environment/rewards.py::DSRReward`; test: `tests/unit/simulation/test_reward.py`.

`PnLReward` uses realized close PnL divided by initial balance when a close occurred, plus optional soft-band penalties and optional DSR contribution. A holding step need not have a realized-close PnL term even when marked equity changes. Source: `simulation/environment/rewards.py::PnLReward`; test: `tests/unit/simulation/test_reward.py`.

`RMultipleReward` uses finite realized R on a close and tracks cumulative R; it also applies soft-band terms and a hard-breach penalty. Nominal target RR and realized R differ when fills and costs differ. Source: `simulation/environment/rewards.py::RMultipleReward`; test: `tests/unit/simulation/test_reward.py`.

`EquityDeltaReward` divides step equity change by fixed dollar risk. It requires positive finite fixed risk; a hard breach returns its configured terminal penalty. The environment initializer requires fixed risk mode for this reward. Source: `simulation/environment/rewards.py::EquityDeltaReward`; `simulation/environment/reward_initialization.py::_initialize_reward_runtime`; test: `tests/unit/simulation/test_environment/test_equity_delta_reward.py`.

`EquityLogGrowthReward` scores a scaled log change between supplied after-cost equity endpoints. It cannot accept incompatible sweep or strategy shaping in the initializer. Log growth of a path and discounted training return are different quantities. Source: `simulation/environment/rewards.py::EquityLogGrowthReward`; `simulation/environment/reward_initialization.py::_initialize_reward_runtime`; test: `tests/unit/simulation/test_environment/test_equity_log_growth_reward.py`.

`SurvivalReward` returns -1 for hard breach, +1 for completing the full data split without breach, and zero otherwise. This mode ignores intermediate portfolio objectives in the initializer. Source: `simulation/environment/rewards.py::SurvivalReward`; `simulation/environment/reward_initialization.py::_initialize_reward_runtime`.

### Component attribution

`REWARD_PART_KEYS` defines a stable set of buckets: `pnl`, `dsr`, `soft_daily`, `soft_year`, `soft_trailing`, `strategy`, `breach`, `sweep`, `peak_dd`, `peak_eod_dd`, `equity_growth`, and `survival`. `fit_reward_parts` reconciles the component sum with the clipped reward where clipping occurs. Source: `simulation/environment/rewards.py::REWARD_PART_KEYS`, `fit_reward_parts`; test: `tests/unit/evaluation/test_reward_attribution.py`.

The step `info` includes `reward_parts` alongside account equity, position state, decision identifiers, and rejection reasons. A useful attribution trace joins that info with ledger fill IDs and timestamps, rather than treating the reward scalar as a trade outcome. Source: `simulation/environment/episode/info.py::_build_step_info`; `simulation/environment/accounting/trades.py::_stamp_exit`.

### Why different signs can be correct

The reward mode may include soft-band charges, breach penalties, or strategy shaping. A close PnL can be positive while the final reward is negative. Conversely, a dense equity reward can move before a position closes. That difference is a configuration and accounting question; it is not by itself an attribution bug. Sources: `simulation/environment/rewards.py`, `simulation/environment/reward_initialization.py`, `simulation/environment/accounting/step.py`.

## Worked example

The paired Tier A notebook uses fixed after-cost equity changes. It checks that `EquityDeltaReward` telescopes over a short path, that its `pnl` part matches each step, and that a breach returns the breach component. No policy is trained and no trading performance is inferred.

```{toctree}
:hidden:

examples/reward-and-attribution
```

## Tasks

- Use [add reward](../../how-to/add_reward.md) before changing a reward mode.
- Use [reward concept](../../concepts/rewards.md) for optimization interpretation.
- Use [evaluate checkpoint](../../how-to/evaluate_checkpoint.md) for outcome metrics.
- Follow [validation protocol](../../research/validation_protocol.md) before making an OOS claim.

## Contract

| Item | Contract | Source |
|---|---|---|
| Step PnL | Equity delta plus payout withdrawn this step | `simulation/environment/accounting/step.py::_record_step_accounting` |
| Realized close | Close PnL/R recorded separately | `simulation/environment/accounting/trades.py::_note_close` |
| DSR | Running-moment signal and risk terms | `simulation/environment/rewards.py::DSRReward` |
| PnL | Realized close PnL scaled by initial balance | `simulation/environment/rewards.py::PnLReward` |
| R multiple | Finite realized R on a close | `simulation/environment/rewards.py::RMultipleReward` |
| Equity delta | Step PnL divided by fixed dollar risk | `simulation/environment/rewards.py::EquityDeltaReward` |
| Survival | -1 breach, +1 completed split, else zero | `simulation/environment/rewards.py::SurvivalReward` |
| Attribution | Fixed component keys reconcile to reward | `simulation/environment/rewards.py::fit_reward_parts` |

## Verify

- `tests/unit/simulation/test_reward.py` checks DSR/PnL/R reward behavior.
- `tests/unit/simulation/test_environment/test_equity_delta_reward.py` checks dense equity R and breach penalty.
- `tests/unit/simulation/test_environment/test_equity_log_growth_reward.py` checks log-growth accounting.
- `tests/unit/evaluation/test_reward_attribution.py` checks component reporting.
- `tests/integration/test_position_fill_accounting.py` checks partial fills count as one position.
- Policy quality, risk-adjusted return, and OOS survival are **not measured** by a reward unit example.

## Limits and common mistakes

- The learner's reward sum is not the same object as net account PnL.
- DSR step signals are not terminal portfolio Sharpe.
- An open position can change equity before any realized close term appears.
- A partial target fill need not complete a position lifecycle.
- A breach penalty is a configured signal, not the dollar size of the loss.
- Discounting can break a simple equivalence with terminal log growth.
- Counting costs both in fills and in reward duplicates a charge.
- A synthetic equality check does not validate market efficacy.

## Review procedure

1. Capture resolved reward mode, weights, and risk settings.
2. Record initial balance and step-start equity.
3. Record all fills and payout withdrawals during the step.
4. Reconcile after-cost end equity with the trade ledger.
5. Compute step PnL with the payout adjustment.
6. Separate realized close PnL/R from unrealized change.
7. Inspect hard breach and soft-band states.
8. Recompute the selected mode's primary term.
9. Add any permitted shaping or penalty terms.
10. Check the reported `reward_parts` keys and sum.
11. Match the sum to the reward actually returned to the learner.
12. Check clipping or special terminal replacement where applicable.
13. Join decision, position, and fill identifiers before outcome attribution.
14. Preserve zero, negative, breached, and incomplete paths.
15. Report performance only from registered runs and immutable artifacts.

For a reproducible mismatch, include the resolved reward mode, previous/current equity, payout, realized close PnL/R, breach state, component map, returned scalar, and fill IDs. The bundled fixture verifies a mathematical contract only; strategy performance is **not measured**.

## Diagnostic cases

The following cases locate the contract boundary to inspect. They are software checks, not evidence of market outcomes.

| Case | Expected inspection result | Source |
|---|---|---|
| Open mark changes | Update step equity PnL | `simulation/environment/accounting/step.py` |
| Payout withdrawn | Add withdrawal back to step PnL | `simulation/environment/accounting/step.py` |
| Multiple TP legs in one step | Aggregate close bookkeeping | `simulation/environment/accounting/trades.py` |
| No realized close | Keep realized-close reward term absent | `simulation/environment/rewards.py` |
| Realized R close | Score finite R in rr mode | `simulation/environment/rewards.py` |
| Nonfinite realized R | Do not score R term | `simulation/environment/rewards.py` |
| Positive equity delta | Score positive fixed-risk ratio | `simulation/environment/rewards.py` |
| Negative equity delta | Score negative fixed-risk ratio | `simulation/environment/rewards.py` |
| Zero fixed risk | Reject equity-delta reward | `simulation/environment/rewards.py` |
| Equity-delta hard breach | Return configured penalty | `simulation/environment/rewards.py` |
| Survival intermediate step | Score zero | `simulation/environment/rewards.py` |
| Survival full completion | Score plus one | `simulation/environment/rewards.py` |
| Survival hard breach | Score minus one | `simulation/environment/rewards.py` |
| PnL close | Divide realized close PnL by initial balance | `simulation/environment/rewards.py` |
| Soft band crossing | Use named soft penalty bucket | `simulation/environment/rewards.py` |
| Clipped reward | Scale parts to clipped scalar | `simulation/environment/rewards.py` |
| Incompatible sweep with pnl | Reject combination | `simulation/environment/reward_initialization.py` |
| Incompatible shaping with equity mode | Reject combination | `simulation/environment/reward_initialization.py` |
| Step info publication | Include reward parts | `simulation/environment/episode/info.py` |
| Cost already in equity | Avoid second deduction | `simulation/environment/rewards.py` |

## Maintainer note

- Verified commit: `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`
- Verified date: 2026-11-15
- Owner: `quantitative_trading_engineer`
