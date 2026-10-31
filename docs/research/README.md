# Research guide

This folder records what the experiments ask, what they observed, and what
those observations do and do not support. A research result is not a software
architecture description or a claim of future profitability.

## Current research topics

- [Sustainable equity growth](sustainable_equity_growth.md): reward objectives,
  account-risk constraints, and observed PPO results.
- [Regime attribution](regime_attribution.md): how returns and trading behavior
  changed across market periods, with interpretation limits.
- [Daily regime feature normalization](regime_context_comparison.md): matched
  control/treatment result and why it did not establish an improvement.
- [Order blocks and multi-timeframe context](order_block_and_multitimeframe_context.md):
  definitions, candidate use, and current engineering limits.
- [GH200 throughput](gh200_throughput_audit.md): measured training speed and
  the resource conditions that affected it.
- [Thesis-hybrid versus thesis-conditioned replay](thesis_policy_training_replay.md):
  matched training comparison and resulting policy behavior.
- [Multi-timeframe encoder comparison](encoder_architecture_comparison.md):
  bounded speed and short-policy screen, with its limits.
- [Training throughput](gh200_throughput_audit.md): measured rates, observed
  bottlenecks, and why speed alone does not justify longer training.

The thesis pages contain the current manuscript, validation boundaries, and
project work queue. Older run notes remain in the evidence archive and should
not be treated as active instructions.

## How to read a result

1. Identify the research question and the declared control/treatment change.
2. Check whether data, action meaning, risk rules, costs, training budget, and
   evaluation behavior were matched.
3. Read the full-period equity, trade, and risk outcomes alongside training
   diagnostics.
4. Separate observed results from possible explanations.
5. Treat exposed periods as exploratory; do not use them to claim fresh
   confirmatory performance.

Reports use human-readable variant and period names. Exact run identity stays
in machine-readable records.
