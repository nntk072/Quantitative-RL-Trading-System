# Research questions and methods

## Scope and evidence boundary

The scientific target is whether causally available multi-timeframe context and
candidate-conditioned sequential decisions improve feasible trading outcomes
under the configured execution costs and account-risk constraints. The active
evidence is one negative seed-50 matched pair on 2024-12-30 through 2025-12-31,
plus previously exposed 2026-01-01 through 2026-10-16 reporting data. That 2026
interval is exploratory only; it is not a fresh holdout. Current campaign input
hashes match their manifest, but missing/non-finite bid/ask rows and timestamp
ties leave data-quality and execution-order gates unresolved. No new model
comparison is registered for execution until those gates pass.

## Registered questions and decision rules

| ID | Question and estimand | Control / treatment; single factor | Unit and primary outcome | Safety, uncertainty, and multiplicity | Current disposition |
|---|---|---|---|---|---|
| DATA | Are synchronized bars, quotes, features, and candidate events valid at each decision time? Estimate required-field defect rates, coverage, and availability mismatches by instrument, timeframe, and period. | Exact local input and configured pipeline; compare native/resampled paths only where both are available. | Input row / decision timestamp. Primary gates: required quote completeness, causal availability, and zero unexplained material parity mismatches. | No model selection. Report denominators and exact missingness; stratify by instrument, session, month, and export period. A defect is not silently imputed or interpreted as a market closure. | **Failed/open:** 39 hashes match; tick exports contain missing/non-finite bid/ask rows and timestamp ties. Provider/license retrieval is outside the user's local-data scope; authoritative schedule/DST remains unresolved. |
| DECISION | Does setup-conditioned execution improve the risk-gated outcome over an unconditioned policy with the same history and trading semantics? | M0 unconditioned setup-hybrid policy vs M1 setup-conditioned policy; change setup-conditioned execution only. | Independent training seed × full chronological account path. Primary: pass the predeclared full-path hard-risk gate; secondary: net return after costs, drawdown, turnover, and abstention. | Paired seeds/configs; report every path, including stopped paths. Use run/seed as the replication unit; trades are not independent replicates. One primary contrast, no post-hoc variant selection. | **Negative, one seed:** selected P6 A4A/A4B both failed the historical strict zero-breach gate and completed the data split. March `daily_loss` means a legacy gross-loss counter breach, not net daily-equity drawdown; no causal or robust effect established. |
| PRICE | Does explicit candidate price geometry and history improve decisions over class-ID conditioning? | M1 class-ID setup conditioning vs M3 shared candidate-geometry scorer/conditional actor; change candidate geometry input only. | Eligible candidate × decision time, with account path as economic unit. Primary: held-out development candidate-ranking quality under calibrated labels; economic risk-gated outcome is a required downstream gate. | Fit labels/calibration on training folds only; purge label horizons and embargo fold boundaries. Report calibration and decision utility separately. Reject the comparison if geometry or labels use future path information. | **Not tested:** candidate census, price-grid audit, current real-data causality, and label integrity are incomplete. |
| LEARNING | Does RL add value beyond transparent rules, random eligible choice, and supervised candidate ranking? | Same candidate set, observation, costs, and risk semantics: fixed flat/no-entry, seeded random, simple rule, supervised ranker, and RL actor. Compare RL vs supervised ranker as the primary learning contrast. | Full chronological account path per independent seed. Primary: full-path risk-gate pass; secondary: net return/cost, drawdown, valid-opportunity abstention. | Match tradability and exposure; random baseline uses recorded seeds. Report uncertainty at seed/path level, with block resampling over sessions only as secondary uncertainty. Control family-wise error across declared model comparisons; no candidate chosen on exposed 2026. | **Not comparable yet:** the complete matched baseline registry, label audit, and independent-seed runs do not exist. No model is selected. |
| ROBUST | Does a surviving improvement persist across independent seeds, chronological folds, regimes, and cost stress? | Frozen finalist vs its matched control across predeclared folds, seeds, and cost scenarios; change only the declared stress factor within each contrast. | Seed × chronological fold × cost scenario, with full path retained. Primary: survival across all required scenarios; secondary: paired net-return delta and drawdown. | Require independent seeds and untouched future confirmation before confirmatory language. Correct for the declared family of stress/model comparisons. The exposed 2026 interval is excluded from selection and confirmation. | **Not answerable with present data:** one seed, no untouched holdout; 2026 is exposed. Obtain new eligible data/period before claiming confirmation. |
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
   promote legacy gross-loss-counter events as FTMO-style net equity breaches.
   Report net performance, drawdown, costs, turnover, and abstention as
   secondary outcomes.
5. **Uncertainty and multiplicity.** Predeclare one primary contrast per
   question. For multiple model/factor contrasts, apply a family-wise correction
   to the declared primary family. Use run/seed-level paired uncertainty; any
   session-block bootstrap is secondary and must not replace independent seeds.
   No statistical test can repair absent independent paths or an exposed
   holdout.
6. **Stopping.** Do not advance after a failed risk or validity gate. Do not
   increase training steps, add seeds, or tune hyperparameters merely to reverse
   a negative result. Any justified successor must register its changed factor,
   control, configuration/data identities, metric, uncertainty method, and
   stop/advance rule before evaluation.

## Claims supported now

- The selected seed-50 P6 pair failed its strict zero-breach training
  risk-survival gate. Both evaluations reached `data_end`; the March timestamps
  are first breach events, not terminal episode stops. The March `daily_loss`
  events use legacy semantics that sum losing closes without offsetting gains;
  they are not net daily-equity breaches. A4B also had a later
  maximum-drawdown event. The [trace dossier](P6_RISK_GATE_SEMANTICS_AND_BREACH_TRACE.md)
  reconciles the counter to the close ledgers.
- The March-to-April paired-trade decomposition and EMA21 reference are
  descriptive arithmetic, not a causal intervention or portfolio
  counterfactual.
- The prior 100k screens failed their maximum-loss gate. These are one-seed
  negative screens, not evidence that RL outperforms its controls.
- No tested policy has demonstrated a robust economic edge, and no model is
  selected. The evidence does not support live-profitability or fresh
  out-of-sample claims.

## Claims not supported

No current evidence establishes candidate price-geometry value, calibrated
future candidate outcomes, matched RL superiority to flat/random/rule/supervised
baselines, independent-seed robustness, cost-stress survival, untouched
out-of-sample performance, or real-broker execution parity. These are open
questions, not implicit extensions of the negative P6 result.
