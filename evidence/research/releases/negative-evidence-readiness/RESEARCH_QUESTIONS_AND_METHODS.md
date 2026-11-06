# Research questions and methods

## Scope and evidence boundary

The scientific target is whether causally available multi-timeframe context and
candidate-conditioned sequential decisions improve feasible trading outcomes
under the configured execution costs and account-risk constraints. The active
evidence is one negative seed-50 matched pair on 2024-12-30 through 2025-12-31,
plus previously exposed 2026-01-01 through 2026-10-16 reporting data. That 2026
interval is exploratory only; it is not a fresh holdout. Current campaign input
hashes match their manifest, but missing/non-finite bid/ask rows and timestamp
ties leave data-quality and execution-order gates unresolved. The configured
native timeframe audit now finds exact timestamps and OHLCV parity against M1
resampling, but native spread differs from the tested M1 references and the
schedule is not authoritative. No new model comparison is registered for
execution until the remaining gates pass.

## Registered questions and decision rules

| ID | Question and estimand | Control / treatment; single factor | Unit and primary outcome | Safety, uncertainty, and multiplicity | Current disposition |
|---|---|---|---|---|---|
| DATA | Are synchronized bars, quotes, features, and candidate events valid at each decision time? Estimate required-field defect rates, coverage, and availability mismatches by instrument, timeframe, and period. | Exact local input and configured pipeline; compare native/resampled paths only where both are available. | Input row / decision timestamp. Primary gates: required quote completeness, causal availability, and zero unexplained material parity mismatches. | No model selection. Report denominators and exact missingness; stratify by instrument, session, month, and export period. A defect is not silently imputed or interpreted as a market closure. | **Partial for bars; failed/open overall:** 39 selected-campaign hashes match. All 30 native symbol/timeframe series have exact timestamp/OHLCV parity (532,350 development rows; 423,018 exposed-report rows). Native spread differs from M1 mean and last references. Tick exports contain missing/non-finite bid/ask rows and timestamp ties. Provider/license retrieval is outside local-data scope; authoritative schedule/DST remains unresolved. See `configured_timeframe_parity.json`. |
| DECISION | Does exposing the entry-state machine to a setup-conditioned policy improve the risk-gated outcome? | A4A hides entry state; A4B exposes it. Preserved configs differ only in `env.entry_state_observation`; this is the declared single factor. | Independent training seed × full chronological account path. Passing the full-path hard-risk gate is a prerequisite; net return after costs is the account-level outcome. This A4A/A4B factor comparison is secondary to the primary policy-versus-no-trade selection contrast. | Paired seeds/configs; report every path, including stopped paths. Use run/seed as the replication unit; trades are not independent replicates. Do not select a model from this factor contrast alone. | **Negative, one seed:** both arms failed the historical strict zero-breach gate and completed the data split. March `daily_loss` means a historical gross realized-loss counter breach, not net daily-equity drawdown; this does not establish benefit or harm from visible state. This pair does not compare setup-conditioned against unconditioned policies. |
| PRICE | Does explicit candidate price geometry and history improve decisions over class-ID conditioning? | M1 class-ID setup conditioning vs M3 shared candidate-geometry scorer/conditional actor; change candidate geometry input only. | Eligible candidate × decision time, with account path as economic unit. Candidate-ranking quality under calibrated labels is a representation diagnostic, not the primary account-level selection outcome; the candidate policy must still pass the no-trade economic selection gate. | Fit labels/calibration on training folds only; purge label horizons and embargo fold boundaries. Report calibration and decision utility separately. Reject the comparison if geometry or labels use future path information. | **Not tested:** candidate census, price-grid audit, current real-data causality, and label integrity are incomplete. |
| LEARNING | Does RL outperform supervised candidate ranking as a secondary learning comparison, and do candidate policies demonstrate value over taking no trade? | Same candidate set, observation, costs, and risk semantics: always-no-trade is the primary policy-selection control; seeded random, simple rules, supervised ranker, and RL actor are secondary comparisons. RL vs supervised ranker is secondary. | Full chronological account path per independent seed. Primary selection outcome: paired treatment-minus-always-no-trade net return on initial operating equity, after the hard-risk gate. | Match tradability and exposure; random baseline uses recorded seeds. Require at least six paired seeds plus a prospectively powered fixed count; report every path. Use exact one-sided paired sign-flip for up to 15 pairs, or the prospectively selected 100,000-draw Monte Carlo sign-flip above 15; use a paired seed-level bootstrap. No candidate is selected on exposed 2026. | **Not comparable yet:** the complete matched baseline registry, label audit, and independent-seed runs do not exist. No model is selected. |
| ROBUST | Does a selected improvement persist across independent seeds, chronological folds, regimes, and cost stress? | Frozen finalist vs its matched control across predeclared folds, seeds, and cost scenarios; change only the declared stress factor within each contrast. This is a secondary stress diagnostic; the primary policy-selection contrast remains treatment versus always-no-trade. | Seed × chronological fold × cost scenario, with full path retained. Hard-risk survival in every required scenario is a gate; paired net-return delta and drawdown are secondary summaries. | Require independent seeds and untouched future confirmation before confirmatory language. Do not create a second model-selection primary from stress results. The exposed 2026 interval is excluded from selection and confirmation. | **Not answerable with present data:** one seed, no untouched holdout; 2026 is exposed. Obtain new eligible data/period before claiming confirmation. |
| COMPUTE | Which architecture/runtime reduces end-to-end cost without changing information or decision quality? | Matched encoder/runtime implementations with identical observations, optimizer path, transitions, and hardware; change encoder/runtime only. | Complete rollout/update block and trained run. Primary: wall time and peak memory per fixed valid transition budget; preserve throughput, gradient, action, and risk-gate checks. | Repeat on the same verified device/software stack; report allocation and measured utilization separately. Do not infer GPU speed from allocation or historical throughput. Compute comparisons do not establish economic value. | **Not measured in this snapshot:** no GPU allocation or model benchmark was run. |

## Analysis and selection protocol

1. **Gate before ranking.** Data provenance, timestamp/session semantics,
   feature causality, candidate eligibility, fill/account parity, and
   versioned hard-risk semantics must pass before an economic comparison is
   interpreted. A compatibility counter that sums gross losing closes is not
   evidence of net daily-equity survival.
2. **Development only.** Reserve chronological folds inside the non-exposed
   development period for fitting and selection. Purge by maximum label horizon
   and apply the configured embargo. Preserve the entire 2026 interval as
   exposed report-only; do not use it for tuning or confirmation.
3. **Replication unit.** Independent training seed and full account trajectory
   are the primary replication units. Trade rows and overlapping candidate
   events do not count as independent model replications. Report run-level
   outcomes individually and summarize paired seed deltas only when enough
   independent seeds exist.
4. **Primary gate.** A candidate that breaches a validated account hard-loss
   constraint or fails to complete its required full chronological path is
   not viable, regardless of aggregate endpoint or PPO training reward.
   Label historical gate failures by the exact configured semantics; do not
   promote gross realized-loss counter events as FTMO-style net equity breaches.
   Report net performance, drawdown, costs, turnover, and abstention as
   secondary outcomes.
5. **Uncertainty and multiplicity.** Predeclare the primary model-selection
   contrast as treatment versus always-no-trade before outcomes. Random, rule,
   supervised, RL-versus-supervised, and representation-factor contrasts are
   secondary and cannot replace a failed primary comparison. Use paired seed
   uncertainty for the primary inference. Any session-block analysis is
   secondary and must not replace independent seeds. No statistical test can
   repair absent independent paths or an exposed holdout.
6. **Stopping.** Do not advance after a failed risk or validity gate. Do not
   increase training steps, add seeds, or tune hyperparameters merely to reverse
   a negative result. Any justified successor must register its changed factor,
   control, configuration/data identities, metric, uncertainty method, and
   stop/advance rule before evaluation.
7. **Frozen economic decision rule.** The primary model-selection estimand is
   the equal-weighted paired difference in full-path net return on initial
   operating equity between the registered treatment and always-no-trade,
   across independent training-seed account paths. Full-path net return is
   ending retained equity plus cumulative payouts minus initial operating
   equity, divided by initial operating equity. Every treatment path must pass
   the validated hard-risk gate and complete the required evaluation interval;
   payouts are realized withdrawals from balance above the initial operating
   balance, so principal and losses are not withdrawable. Any failed path makes
   the candidate ineligible regardless of its average return. The null is a
   non-positive treatment-minus-no-trade effect. A
   positive result requires a one-sided paired sign-flip test at alpha 0.05:
   enumerate all sign assignments exactly through 15 pairs, or use the
   prospectively chosen 100,000-draw Monte Carlo method above 15 pairs. Also
   require a paired 95% percentile bootstrap interval over seed pairs (10,000
   resamples, RNG seed 42) whose lower bound is above zero. Require at least six
   paired seeds as the resolution floor; prospective power analysis must set
   the larger fixed seed count before training, because six alone do not
   establish adequate power. This is one primary contrast, so no multiplicity
   correction is needed for it. Other baselines and factor comparisons are
   secondary; if a later protocol promotes multiple primary contrasts, define
   that family and correction before observing outcomes. The sign-flip test
   assumes seed-pair labels are exchangeable under the null; if that assumption
   is not defensible, mark the test not estimable and do not promote. Report
   every seed and stopped path; no optional stopping, replacement seeds, or
   outcome-driven expansion is allowed. The paired-seed analyzer's explicit
   `aalto.paired_seed_metrics.v2` primary-selection contract requires the
   prospectively fixed `expected_seeds`, `evaluation_exposure`, and
   `primary_selection` record (`treatment_vs_always_no_trade`,
   `net_return_initial_equity_pct`, one-sided `greater`, and control ID
   `always_no_trade_v1`), and label the input as development exposure with
   `matched_exploratory` evidence role. It cannot label selection evidence as
   confirmation or use a holdout. Every arm must record a complete path,
   hard-risk gate result, initial and ending retained equity, cumulative
   payouts, and return metric; the no-trade control must have zero trades,
   retain initial equity, and record no payout. The analyzer reconciles return
   to retained equity plus payouts and preserves the older v1 schema for
   historical/descriptive results.
8. **Development inference only.** The rules above do not create confirmation:
   all current local policy periods are development or previously exposed.
   Any future use of them is exploratory selection evidence. A confirmatory
   claim requires a genuinely untouched eligible period, which is unavailable
   in the current local data. Do not repurpose the exposed 2026 interval.
9. **Version lock.** This protocol is frozen before any successor validation
   outcomes. A justified change requires a new protocol version and a recorded
   reason before outcomes for that successor are opened. The current upstream
   data, feature, and simulator gates do not pass, so no successor model result
   is authorized by this protocol.

## Claims supported now

- The selected seed-50 matched pair failed its strict zero-breach training
  risk-survival gate. Both evaluations reached `data_end`; the March timestamps
  are first breach events, not terminal episode stops. The March `daily_loss`
  events use legacy semantics that sum losing closes without offsetting gains;
  they are not net daily-equity breaches. A4B also had a later
  maximum-drawdown event. The [trace dossier](gross_realized_loss_counter_breach_trace.md)
  reconciles the counter to the close ledgers.
- The March-to-April paired-trade decomposition and EMA21 reference are
  descriptive arithmetic, not a causal intervention or portfolio
  counterfactual.
- The prior 100k screens failed their maximum-loss gate. These are one-seed
  negative screens, not evidence that RL outperforms its controls.
- The current training-only conditional candidate replay yielded 1,067,731
  bracket rows, 72.0% unresolved. The unresolved share ranges from 84.8%–94.2%
  through 2025-08 to 15.9% in December, and local quote gaps dominate the
  unresolved reasons. This is a no-go for training or calibrating a candidate
  value model on the resolved subset; rows exclude account state and policy
  action. See the [candidate outcome packet](../../candidate_outcomes/README.md).
- No tested policy has demonstrated a robust economic edge, and no model is
  selected. The evidence does not support live-profitability or fresh
  out-of-sample claims.

## Claims not supported

No current evidence establishes candidate price-geometry value, calibrated
future candidate outcomes, matched RL superiority to flat/random/rule/supervised
baselines, independent-seed robustness, cost-stress survival, untouched
out-of-sample performance, or real-broker execution parity. These are open
questions, not implicit extensions of the negative matched-pair result.
