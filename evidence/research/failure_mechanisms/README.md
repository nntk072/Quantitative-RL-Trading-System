# Historical failure-mechanism diagnosis

## Scope and conclusion

This packet diagnoses the selected seed-50 A4A/A4B policy pair on its
2024-12-30 through 2025-12-31 development interval. It reads the retained
training artifacts and concept evidence only. The exposed 2026 reporting
period is not used. The campaign fingerprint is
`b37580606ca374326bce7207fb7eef118cede36cf0eaad25d37be9465bb4e1e4`.

Both policies failed the predeclared zero-breach risk gate and had negative
recorded bid/ask net returns: A4A ended at $97,845.69 (−2.154%) over 987
positions; A4B ended at $89,943.95 (−10.056%) over 825 positions. Both runs
reached the end of the configured development split. There is no evidence here
that one model is viable or superior.

The artifacts establish two substantial candidate mechanisms: frequent entry
requests while the state machine was not armed, and a large midpoint-to-
executable bid/ask drag on the recorded fills. Neither is a complete causal
explanation. The historical policy decision trace is incomplete, local tick
timestamps contain ties and missing quote sides, and the report-period data
are exposed. Keep the conclusion bounded.

## Measured mechanisms

| Mechanism | Measured evidence | What the measurement supports | What remains unresolved |
|---|---|---|---|
| Entry/FSM interface attrition | 42,126/47,706 A4A entry requests (88.3%) and 47,612/52,282 A4B requests (91.1%) were rejected while not armed. Recorded candidates were 1,969/2,412; invalidations were 978/1,582. | Action requests were often inconsistent with the recorded FSM state. Candidate generation was nonzero. | Does not show whether the mask, policy, decoder, candidate lifetime, or FSM contract caused the requests; does not establish candidate quality or explain PnL. The old runs lack a complete candidate-to-action trace. |
| Midpoint versus executable quote outcomes | At the retained fill times, A4A midpoint PnL sums to +$15,936.72 and recorded bid/ask net to −$2,154.31; A4B is +$4,268.82 versus −$10,056.05. Mean midpoint-to-bid/ask drag is 0.03739 R and 0.03730 R per position. All recorded entries and close fills in this reconstruction are tick sourced; raw bid/ask PnL reconciles to recorded net. | Under the selected TickBook quote rows, crossing from midpoint to executable bid/ask prices is large enough to reverse the aggregate sign. Costs must be reported beside the midpoint outcomes. | This is a fixed-fill accounting decomposition, not a cost intervention or proof of a deployable midpoint edge. Tie ordering, missing-side carry, external quote availability, and provider clock are unresolved in the local files. |
| Entry/exit cohort change | March-to-April A4A gross mean R changed −0.2177 (95% interval [−0.5837, 0.1429]); A4B changed −0.2238 ([−0.5656, 0.1118]). The entry-cohort and conditional EMA21-exit components each have intervals including zero. | The saved cohort decomposition does not identify a statistically separated entry or exit cause for this month-to-month change. | EMA21 is a fixed-entry accounting reference, not a causal policy or account-path counterfactual; this analysis does not identify the full-year loss mechanism. |
| Configured risk gate | The March `daily_loss` event used the historical legacy counter of gross negative closes without positive-close offsets or open PnL. Through first breach, gross negative closes were $5,017.66/$5,399.25 and net realized close PnL was −$3,004.28/−$3,389.32. A4B also recorded a later `max_drawdown` event. | Both arms failed the configured historical gate; the March event is not evidence of a net daily-equity loss rule. | This explains the gate classification, not why the policy entered the trades or whether a different daily-risk contract would be economically viable. |
| PPO learning-health signals | Each training log has 245 rows through 2,007,040 steps. PPO losses, entropy, approximate KL, clip fraction, and explained variance are finite from the second row onward. Median approximate KL is about 0.0050 for both arms; median explained variance is 0.0439/0.0472. | The retained logs do not show non-finite PPO metrics. | No predeclared acceptance thresholds or complete optimizer telemetry establish healthy learning. Training logs have no gradient norm or constrained-PPO dual/cost updates; dashboard `grad_norm` and zero breach/cost fields are only 21 sampled snapshots. |
| Fill-to-source quote alignment | The selected ledgers contain 3,698 tick-backed events (1,812 entries, 1,886 exits). Sixteen events share a timestamp group with changed quote values; 87 are in groups with a missing required side, and the parser carries a side for all 87. All fill prices match the configured 0.25-grid parser reconstruction; 667 match the stable-parser side price without grid rounding. | The saved fill ledger is internally consistent with the recorded parser/grid at the matched timestamps. | This does not prove provider order, executable quote at arrival, broker price, or authoritative source clock. The 87 carried-side events and 16 changed-quote events retain chronology uncertainty. |
| Position lifecycle and PnL reconciliation | The A4A report links 987/987 positions to fill events; A4B links 825/825. All opens, completed positions, fill counts, final close timestamps, and close-fill net PnL reconcile by `position_id`; aggregate position PnL matches reported total and ending equity in both arms to < $1e-9. Every open has a recorded decision-to-submission gap of 60 seconds. A separate configured-TickBook analysis derives timestamp-bounded MFE/MAE for the same 987/825 training positions. | The retained training records support internally complete position/fill accounting and the reported aggregate net PnL/equity; the added excursion bounds describe recorded price paths against initial stop distance. | The source tables still have no MFE/MAE columns or complete candidate-proposal/eligibility-to-action link. Excursions do not prove a feasible alternative exit; endpoint ordering and carried quote sides remain uncertain. The 60-second gap remains a bar-label/completed-bar boundary, not measured inference or network latency. These checks do not isolate a causal loss mechanism. See the [paired lifecycle packet](../selected_policy_trade_lifecycle/README.md), the [trade excursion packet](../selected_policy_trade_lifecycle/trade_excursions/README.md), and the [A4A](../selected_policy_trade_lifecycle/a4a_training/selected_policy_trade_lifecycle.md) / [A4B](../selected_policy_trade_lifecycle/a4b_training/selected_policy_trade_lifecycle.md) reports. |

## Exit-reason cohorts

The reusable [`summarize_trade_exit_cohorts.py`](../../../scripts/research/analysis/evaluation/summarize_trade_exit_cohorts.py)
groups the existing per-position excursion ledgers by recorded exit reason.
The [machine-readable report](exit_reason_cohorts.json), [cohort table](exit_reason_cohorts.csv),
and [artifact manifest](exit_reason_cohorts_manifest.json) retain source hashes
and the analysis boundary. The data are separate historical cohorts, not
paired observations; net realized R and price-only MFE/MAE have different
numerators.

| Arm | Exit reason | Positions | Mean / median realized net R | Median MFE R, lower bound | Reached 1R MFE | Median hold (hours) |
|---|---|---:|---:|---:|---:|---:|
| A4A | EMA-21 exit | 83 | 0.993 / 0.992 | 1.103 | 95.2% | 0.13 |
| A4A | Session end | 151 | 0.615 / 0.058 | 0.377 | 23.2% | 3.58 |
| A4A | Structural stop | 585 | −0.731 / −1.000 | 0.396 | 20.7% | 0.13 |
| A4A | Structural TP3 | 168 | 1.430 / 1.027 | 1.032 | 50.6% | 0.15 |
| A4B | EMA-21 exit | 82 | 1.031 / 1.009 | 1.139 | 92.7% | 0.12 |
| A4B | Session end | 125 | 0.661 / 0.037 | 0.347 | 25.6% | 3.45 |
| A4B | Structural stop | 496 | −0.715 / −1.000 | 0.333 | 19.4% | 0.13 |
| A4B | Structural TP3 | 122 | 1.325 / 0.961 | 0.981 | 48.4% | 0.15 |

These summaries describe recorded outcomes only. A position with 1R MFE does
not establish that a 1R exit was executable under the policy's account path,
quote chronology, and portfolio constraints. Gross R and cost R are not
available in this cohort source, and the MFE numerator excludes commissions.
Do not use this table to claim that an alternative exit would have improved
the campaign.

The PPO metric distribution (first finite value → last, then p05 / median / p95)
is:

| Metric | A4A | A4B |
|---|---|---|
| Entropy loss | −17.0193 → −15.6744; −16.9131 / −16.2758 / −15.7282 | −17.0198 → −15.9037; −16.9200 / −16.4939 / −15.9987 |
| Policy-gradient loss | −0.003093 → −0.003432; −0.003396 / −0.002364 / −0.001263 | −0.002959 → −0.002467; −0.003365 / −0.002284 / −0.001324 |
| Value loss | 6.5483 → 2.4010; 0.1470 / 3.2454 / 7.9276 | 6.5047 → 2.5817; 0.1433 / 3.2808 / 8.0371 |
| Approximate KL | 0.004356 → 0.005404; 0.003621 / 0.005018 / 0.006608 | 0.006155 → 0.005925; 0.003747 / 0.005023 / 0.006781 |
| Clip fraction | 0.03881 → 0.08547; 0.02121 / 0.04021 / 0.06900 | 0.04076 → 0.05534; 0.02104 / 0.03945 / 0.06481 |
| Total loss | 3.2739 → 1.1740; 0.0421 / 1.6009 / 3.7770 | 3.2634 → 1.1788; 0.0420 / 1.5877 / 3.8932 |
| Explained variance | 0 → 0.10423; −0.00522 / 0.04393 / 0.22868 | 0 → 0.10331; −0.00480 / 0.04719 / 0.23330 |

### Source audit of the entry-state rejection path

The selected A4A/A4B quarter-point variants use the same continuous strategy
action controls and differ in the explicit entry-state observation setting:
`entry_state_observation=false` for A4A and `true` for A4B. The state machine
does not dynamically restrict the Box action space. `_prepare_action_intent`
decodes the policy output, treats an intensity-qualified direction as an entry
request, and in `FLAT` or `CANDIDATE` records `entry_state_not_armed` before
forcing the executed direction and risk to zero. When visibility is enabled,
the state is appended to the account observation; it does not change the action
schema. The selected pair's 88.3% and 91.1% not-armed rejection shares are
therefore consistent with policy requests reaching an intentional environment
guard, rather than evidence of candidate-feature decoding failure. The slightly
higher A4B share also shows that exposing state alone did not remove these
requests in this one-seed pair.

This source interpretation now has a focused synthetic regression: an
intensity-qualified action in `FLAT` and `CANDIDATE` is logged as
`entry_state_not_armed`, while the candidate progresses to `ARMED` and the
same action can then trigger the stored candidate. A schema test confirms
visible and hidden variants retain the same action schema while account
observation widths differ. This rules out the hypothesis that the state
visibility flag itself masks entry actions; it does not explain why the
historical policies made these choices or establish a causal effect on PnL.
The old campaign still lacks per-decision action/state joins, so do not infer
which opportunity or policy output produced each rejection. Any conditional
action-mask/factorization change is a new scientific factor and remains behind
the Stage D/E gates; no training or replay is authorized by this audit.

Current policy rollouts now write one decision row with the selected setup,
the complete eligible-ID list, action coordinates, categorical entropy,
source-event identity/status/times, entry state and rejection reason, plus the
trade-event row interval produced by that decision. Synthetic integration
tests verify the selected ID and eligibility against the environment and link
the row interval to resulting events. This supports a future candidate-to-fill
funnel, but it does not backfill the historical pair. Per-candidate logits or
the full probability vector are not stored. The compact trace now records the
selected choice probability, `NO_TRADE` probability, and probability/ID of the
highest-probability eligible trade choice. Four focused helper cases validate
the compact summary and its fail-closed checks. The full policy-to-saved-row
integration remains in the release verification gate; no policy-probability
market trace has been generated. The summary supports abstention diagnosis
without repeating a policy forward pass or storing 109 values per decision;
other eligible candidates' individual probabilities remain unavailable.

Explained variance also ranges from −0.2383 to 0.9278 in A4A and −0.5195 to
0.9083 in A4B. These are recorded values, not predefined failure thresholds;
the variability prevents describing the value fit as uniformly stable.

The local tick profile covers 172,290,383 rows. It records 371,390 rows with
one required bid/ask side missing or non-finite and 329,471 adjacent timestamp
ties: 328,918 changed-quote pairs and 553 pairs with a missing quote. There are
23 training M1 minutes without ticks per instrument. For the selected campaign
specifically, 16 of 3,698 fill events fall in changed-quote timestamp groups
and 87 in groups with a missing required side. These counts limit how strongly
the fixed-fill bid/ask decomposition can be interpreted; they do not show
which prices any historical policy could have received.

## Interpretations the evidence rejects

- The first stored `fail_time` was not the end of evaluation: both training
  evaluations completed the configured split.
- The March `daily_loss` event was not calculated from net daily equity. The
  historical legacy counter accumulated gross negative closes and ignored
  profitable closes and open PnL.
- The 2026 interval cannot serve as a fresh holdout; it was already inspected
  and remains report-only.
- Non-finite PPO loss/entropy/KL values are not observed in the retained
  `training_log.csv` rows. This does **not** establish that optimization was
  effective or that the policy learned a useful entry rule.

## Unresolved alternatives

The retained evidence does not separate candidate scarcity from candidate
mask/expiry behavior; policy selection from action decoding; entry quality from
exit choice; spread drag from tie-order or quote-side carry artifacts; and
account sizing from the selected risk contract. It also cannot establish
continuous gradient health, constrained updates, or a causal relationship
between the entry/FSM attrition and economic outcome.

The current local tick audit found rows with a missing/non-finite required side,
adjacent equal timestamps, and 23 training M1 minutes without ticks per market.
These are limits on executable-price interpretation, not evidence that any one
data issue caused the policy loss. Provider-rights and externally authoritative
calendar/clock work remain excluded at the user's direction; this packet makes
no rights or calendar-authority claim.

## Suggested single-factor work after earlier gates

No replay or training is authorized by this diagnosis. After Stage D/E data,
action, and execution contracts pass, the first policy experiment to consider
is a preregistered change to the entry/FSM action-eligibility interface alone,
with unchanged features, candidate semantics, execution, costs, risk, seed
design, and eligible validation period. Preserve the current selected pair as
historical evidence. Treat a cost-only comparison as a fixed-fill accounting
stress, not as a strategy result, until quote chronology is adequately
identified.

## Sources

- [Selected-pair consolidated results](../releases/negative-evidence-readiness/CONSOLIDATED_RESEARCH_RESULTS.md)
- [Machine-readable entry-action funnel](../releases/negative-evidence-readiness/entry_action_funnel_diagnosis/entry_action_funnel_diagnosis.json)
- [Legacy risk-gate trace](../releases/negative-evidence-readiness/legacy_daily_loss_counter_breach_trace.md)
- [Monthly entry/exit attribution and its evidence packet](../entry_and_exit_attribution/README.md)
- [Selected-campaign fill-to-tick quote alignment](../fill_quote_source_alignment/README.md)
- [Local market-quality report](../releases/negative-evidence-readiness/local_market_data_quality.json)
- The original selected-run `training_log.csv` and sampled `dashboard_log.csv` files are preserved under `/scratch/work/nguyenl37/Quantitative-RL-Trading-System-research-archive/outputs/gpu_campaigns/rq1_entry_fsm_pair_seed50_train2025_20261024_policy2m_v1/`. The source paths and training-log checksums are recorded in the summary JSON.
- The reproducible PPO metric summary is [`ppo_training_dynamics.json`](ppo_training_dynamics.json); it records both training-log hashes and the summarizer's source hash.
- The numerical report verifier outputs are outside the repository at `/scratch/work/nguyenl37/agent_plans/Quantitative-RL-Trading-System/numerical_verifier_a4a_21349346.json` and `numerical_verifier_a4b_21349346.json`. Both fail only because the required checkpoint train/test backend-parity reports are absent. Generating those reports would require a checkpoint replay before earlier plan gates pass.

The reusable PPO telemetry summarizer is
[`summarize_ppo_training_dynamics.py`](../../../scripts/research/analysis/evaluation/summarize_ppo_training_dynamics.py).
It records source hashes, metric coverage, non-finite counts, step bounds, and
descriptive quantiles without applying optimizer-health thresholds. Recreate
the two-arm summary from the preserved source logs with:

```bash
.venv-x86/bin/python scripts/research/analysis/evaluation/summarize_ppo_training_dynamics.py \
  --arm a4a=/scratch/work/nguyenl37/Quantitative-RL-Trading-System-research-archive/outputs/gpu_campaigns/rq1_entry_fsm_pair_seed50_train2025_20261024_policy2m_v1/runs/attempts/ladder_a4a_entry_fsm_hidden_qgrid025__seed50/attempt1/ladder_a4a_entry_fsm_hidden_qgrid025__seed50/20261024_150835_114072_rl_train_seed50_tcn/model/training_log.csv \
  --arm a4b=/scratch/work/nguyenl37/Quantitative-RL-Trading-System-research-archive/outputs/gpu_campaigns/rq1_entry_fsm_pair_seed50_train2025_20261024_policy2m_v1/runs/attempts/ladder_a4b_entry_fsm_qgrid025__seed50/attempt1/ladder_a4b_entry_fsm_qgrid025__seed50/20261024_150835_483291_rl_train_seed50_tcn/model/training_log.csv \
  --out evidence/research/failure_mechanisms/ppo_training_dynamics.json
```
