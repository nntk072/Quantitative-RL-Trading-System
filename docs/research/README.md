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
- [Hybrid versus setup-conditioned replay](setup_conditioned_policy_replay.md):
  matched training comparison and resulting policy behavior.
- [Multi-timeframe encoder comparison](encoder_architecture_comparison.md):
  bounded speed and short-policy screen, with its limits.
- [Training throughput](gh200_throughput_audit.md): measured rates, observed
  bottlenecks, and why speed alone does not justify longer training.

The active experiment queue and its period-role decisions are in the
[research execution plan](../operations/research_execution_plan.md). This
section contains research methods and findings; historical run snapshots are
evidence, not independent work queues.

## Methods and limitations

- [Validation protocol](validation_protocol.md): data roles, selection rules,
  causal inputs, and evidence requirements.
- [Evaluation methodology](evaluation_methodology.md): model replay, event-driven
  backtests, metrics, and reporting boundaries.
- [Limitations](limitations.md): interpretation limits for historical
  simulation and model comparisons.
- [Finding card template](finding_card_template.md): a reusable structure for
  recording a research question, evidence, claim boundary, and decision.

Historical machine outputs and frozen report snapshots are indexed in the
[research evidence archive](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/main/evidence/research/archive_2026/README.md).

## Supporting evidence

- [Entry-idea opportunity counts](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/main/evidence/research/entry_idea_opportunity_counts/entry_idea_opportunity_counts.md): generated context-signal counts and CSV tables. These counts describe cached opportunities, not executed trades.
- [Setup-conditioned replay evidence](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/main/evidence/research/setup_conditioned_reasoning_replay/README.md): preserved train/test exports for the replay discussed in the linked protocol and result note.
- [Entry-idea feature previews](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/main/evidence/research/entry_idea_context_previews/README.md): H1 context plots, not performance evidence.
- [Directional swing cache validation](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/main/evidence/research/directional_swing_cache_validation.json): machine validation record.

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
