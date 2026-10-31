# Setup-conditioned reasoning benchmark protocol

## Scope

Variant D changes only the policy factorization. The matched 2M configs are
Variant C (`config/research/thesis_mtf_reasoning_2m.yaml`,
`thesis_hybrid_v1`) and D
(`config/research/thesis_mtf_reasoning_conditioned_2m.yaml`,
`thesis_conditioned_v1`). Both resolve to 2,000,000 timesteps, 8 environments,
2,048 rollout steps, batch size 512, and 15 PPO epochs. Both use the same
109-candidate setup catalog, mask,
NO_TRADE action, action/observation schemas, MTF encoder, reward, simulator,
execution settings, and train/test partition. The D execution actor receives
the market latent and the selected primary-setup embedding.
Both enable `features.include_strategy_state` because the configured
`PO3IFVGStrategy` requires causal sweep, manipulation, distribution, and IFVG
state columns at environment startup.

Do not interpret a short learning smoke as an economic comparison. Its purpose
is to verify valid PPO learning and usable diagnostic artifacts before a
separately authorized benchmark-length run.

## Decisive questions and evidence

| Question | Required evidence |
| --- | --- |
| Does the policy trade, or collapse to NO_TRADE? | Decision-bar NO_TRADE rates, split by whether any trade setup was eligible; actual opened trades and equity/return metrics. |
| Does setup entropy evolve sensibly? | Per-month masked setup entropy from the training replay and testing replay. Read it with eligibility counts; high entropy over a one-choice mask is not expected. |
| Does it select multiple ideas and timeframes? | Selection counts and eligibility-adjusted rates by idea and timeframe, plus the idea-by-timeframe matrix. Actual opened-trade diversity is reported separately from sampled choices. |
| Are invalid setup selections exactly zero? | Count every selected category against that bar's recorded mask. Acceptance is exactly zero. |
| Are structural SL/TP violations exactly zero? | On each open event check stop and selected target price side, source-timeframe floor relative to the selected setup, and SD level-1 source-timeframe semantics. Acceptance is zero. |
| Does training behavior remain sane on test? | Use the same diagnostics on chronological train and test replays; compare NO_TRADE, entropy, idea/timeframe use, constraints, equity, and drawdown without tuning on test. |
| Does D produce setup-dependent execution? | Policy factorization tests plus per-idea/timeframe execution-action summaries and realized risk/stop/target summaries. Identical execution summaries across theses are a warning, not proof by themselves. |
| Is economic behavior moving sensibly? | Report the existing net equity, drawdown, breach, trade expectancy, and cost metrics on both splits. A bounded smoke can reveal catastrophic deterioration but cannot establish superiority. |

## Saved artifacts

Each split should contain `thesis_decisions.csv`,
`thesis_policy_metrics.json`, and selection tables by idea, timeframe, and
idea-by-timeframe. It also contains `thesis_performance_by_idea_timeframe.csv`,
selection and performance heatmaps, and positions with primary-thesis and
structural SL/TP provenance. Training output separately includes
`learning_diagnostics.csv`, `thesis_activity.png`, and `thesis_entropy.png`.
Keep rollout-time learning diagnostics separate from train/test replay
diagnostics and keep training and testing in their existing output folders.

The decision trace records the selected category, eligible category IDs,
mask validity, setup entropy, and execution coordinates. Historical trace
files and schema fields still use `thesis_*` names; those are serialized
compatibility identifiers. Trade-level checks preserve the primary setup,
selected timeframe, structural references, and schema version.

## Gates

Before a benchmark-length run:

1. C compatibility and D categorical masking pass tests.
2. PPO rollout sampling and `evaluate_actions` reproduce the hierarchical log
   probability using the stored setup category, without resampling.
3. Execution outputs depend on the selected setup; setup logits depend only
   on the market latent.
4. Save/load preserves the policy class, embedding dimensions, action schema,
   and setup observation schema.
5. A bounded PPO smoke completes with finite loss, entropy, gradients, and
   checkpoint reload.
6. Train/test reporting emits all eight decisive metrics; invalid choices and
   structural violations are exactly zero in both splits.

The 2M overlays explicitly pin `quality_execution.exact_n_envs: true` so
hardware-aware scaling cannot silently change the matched environment count.

Economic superiority requires a matched, adequately trained comparison and
uncertainty analysis. A passing implementation smoke is not evidence of
profitable or generalizable trading.
