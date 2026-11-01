# Exit-Action Semantics: Root-Cause Decision and Minimal Matched Experiment

**Status:** PROPOSED / NOT AUTHORIZED FOR EXECUTION
**Date:** 2026-10-24
**Repository:** `nntk072/Quantitative-RL-Trading-System`
**Planning reference:** `785163c` (`Improve reports and fix GPU checkout selection`)
**Scope:** Exit-action interpretation, historical reproducibility, and evidence-gated experimental design.
**Explicit restriction:** **Do not change code, change training configurations, start/resume training, submit Slurm jobs, overwrite checkpoints, or modify preserved run evidence under this plan.** This document specifies *future* experiments requiring separate authorization.

---

## 1. Decision (one-page summary)

**Provisional decision:** Adopt structural exit as the default/neutral choice in a **new, separately versioned action contract**, while **retaining EMA-21 as an explicitly selected alternative**. Do **not** globally disable EMA and do **not** alter how any archived `overlay-action-v2` checkpoint is decoded.

**Next experiment:** First, a **no-training paired counterfactual evaluation** of a *single frozen historical checkpoint* over the same complete 2025 calendar: original v2 decode versus proposed v3 decode. Complement it with an **entry-cohort/exit-only shadow replay** to separate changed exit treatment from changes in which positions are admissible. Only if this stage is informative, seek authorization for **one fresh paired 2M-step pilot** comparing v2 and v3, with all other settings matched. **No 20M campaign** until evidence and gate criteria pass.

**Root-cause judgement:** Source-level neutral-action bias is **confirmed as a semantics issue**, but **not established as the cause** of the 2025 equity reversal. Losses on EMA-selected trades are an **association** subject to entry/regime/risk confounding. A more general deterioration in trading edge remains a live alternative hypothesis. The *absence of an actively enforced peak-equity drawdown stop* in the referenced historical replay also contributes to the magnitude of the observed drawdown; it is not proof of why expectancy turned negative.

**Separation of claims:**

- **Source fact:** Current overlay decoder uses `u=(raw+1)/2` and chooses EMA if `u_exit >= 0.5`; a Gaussian raw midpoint of `0` chooses EMA.
- **Source fact:** The hybrid actor represents structural and EMA via separate categories encoded as raw `-0.5` and `+0.5`, respectively. It must not be assumed to have the same Gaussian midpoint failure mode.
- **Hypothesis, not fact:** Default EMA selection may reduce reward capture in particular regimes, alter order eligibility, and contribute to falling expectancy.
- **Alternative hypothesis:** Entry quality, risk decisions, regime change, action collapse, transaction costs, or stochastic execution can account for continued losses even with structural exits.

---

## 2. Preserved evidence and limits

### 2.1 Relevant archived 2M pilot

The historical corrected seed-50, 2M-step pilot in `docs/thesis/manuscript_draft.md` (`rq1_entry_fsm_pair_seed50_train2025_20261024_entry_levels_pilot2m_v3`) reports:

| Metric                  | Hidden-state treatment | Visible-state control |
| ----------------------- | ---------------------: | --------------------: |
| Completed steps         |              2,007,040 |             2,007,040 |
| Completed trades        |                  1,356 |                   139 |
| Win rate                |                 39.38% |                41.73% |
| Profit factor           |                  0.972 |                 0.712 |
| Return                  |                 -9.99% |               -10.04% |
| Peak-to-trough drawdown |                 39.50% |                10.41% |
| Training survival gate  |                   FAIL |                  FAIL |

For the **hidden-state** arm, equity peaked at **$148,785 on 2025-03-20** and reached **$90,009 on 2025-11-12** (approximately **-$58,776**, or **-39.50% from peak**). This was **not** stopped by an active 10% peak-drawdown guard: `env.peak_trailing_dd_limit=0` for this run; the configured hard maximum loss was from initial equity (approximately $90,000 floor). The observed ~10% final loss and the 39.50% high-watermark drawdown measure different risks.

**Provenance:**

- Archived pilot campaign fingerprint: `9fafe8eccf1e38c2bc2863bc5e77661385e24e4ce8da47e38d8d8e5d12fd278e`.
- Archived pilot source commit: `cbf7825170dee7f68ad578a19023e0847b11393f`.
- Archived source snapshot SHA-256: `a4b3737fcf0ae9ee9329de50f461302c965d3cc97317be07fa97e2e8639910f1`.
- Read the **actual attempt manifest, resolved config, and checkpoint SHA-256** before choosing the exact checkpoint. Do not infer them from the current `main` branch.

**Other, distinct evidence:** `config/base/default.yaml` comments that EMA was selected on 92% of trades in an earlier first 20M run. **Do not transfer that frequency to this 2M pilot without checking its own action and trade logs.** The `2026-10-23` zero-trade prevention note describes two other 5M checkpoints with 33 closed trades and nearly constant deterministic actions; those observations signal a policy-learning concern but are not direct measurements of this historical equity excursion.

**Data status:** The 2025 period is the training/in-sample diagnostic interval. The 2026 report interval was previously inspected, so **do not use 2026 to pick thresholds, checkpoints, or variants**; no fresh holdout claim is available from it.

### 2.2 Source facts to preserve

| File                                           | Verified source behavior                                                                                                                                                 |
| ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `simulation/environment/action_runtime.py`   | `u=0.5*(raw+1)` and `ema_21 if u_exit>=0.5 else structural`; default reset to structural before strategy decoding.                                                   |
| `learning/rl/hybrid.py`                      | Explicit categorical centers `(-0.5, +0.5)` for `(structural, EMA)`, encoded within the Box layout.                                                                  |
| `learning/rl/ppo.py`                         | Optional mode-prior regularization pulls activated mean-action coordinates toward zero; confirm whether `exit` is in the actual active-prior set for the selected run. |
| `trading/orders/entries.py`                  | EMA mode has no structural TP; requires valid EMA. Structural mode requires valid structural target geometry.                                                            |
| `simulation/environment/ema_exit_runtime.py` | EMA exit acts only after >=1R favorable excursion and subsequent close through EMA-21 in the opposite direction; stop check precedes EMA check.                          |
| `decisioning/actions.py`                     | Current overlay contract version `overlay-action-v2`; action names/order vary by flags and widths alone are ambiguous.                                                 |
| `learning/rl/agent.py`                       | Saved action version and layout validation; incompatible schemas are rejected on load.                                                                                   |

**Important implication:** A changed decoder may change **entry eligibility**, not just exit timing. Comparing aggregate equity alone cannot isolate the mechanism.

---

## 3. Hypotheses and discriminating predictions

**H1 — Action-mapping bias materially contributes to decline.** Gaussian actions near zero unintentionally select EMA, shifting the realized exit distribution. Expected: a structural-neutral decoder sharply changes *unintended* EMA share and improves at least some matched entry-cohort outcomes; any aggregate replay improvement must be traceable to changes in exit management or valid order admission.

**H2 — General deterioration of trading edge.** Entry selection and/or management become unprofitable in later 2025 irrespective of exit mapping. Expected: structural-neutral decoding reduces EMA share but expectancy stays negative on common entry cohorts or substantial losses persist across both exit types; state-responsive behavior may be absent.

**H3 — Exposure/eligibility and risk semantics dominate apparent effect.** Structural target availability changes admission, size/exposure, and compounding; the peak-DD rule did not actively constrain the archived replay. Expected: any apparent improvement comes chiefly from fewer entries, different exposure, or account stopping behavior rather than better exits on identical entries.

**Do not infer causality from** `PnL | exit_mode=EMA` versus `PnL | exit_mode=structural` alone: exit mode was selected by the policy conditional on market state, and EMA/structural eligibility differs.

---

## 4. Proposed v3 action contract (DESIGN ONLY)

### 4.1 Gaussian Box decoding

Let `raw_exit` be the original normalized Box output, clipped to `[-1,1]`, with `u_exit=(raw_exit+1)/2`.

- **v2 (immutable historical semantics):** `EMA` if `u_exit >= 0.5` (equivalently `raw_exit >= 0`); else `structural`.
- **v3 (proposed):** `EMA` only if `raw_exit >= +0.25` (equivalently `u_exit >= 0.625`); otherwise `structural`.
- **Missing/disabled EMA:** `structural`, with an explicit reason/availability flag in diagnostics.
- Treat the `+0.25` threshold as an **engineering precommitment**, not a fitted optimal value. **Do not search it using the 2025 equity peak or any 2026 result.**

| Raw exit | v2         | Proposed v3 |
| -------: | ---------- | ----------- |
|     -0.5 | Structural | Structural  |
|      0.0 | EMA        | Structural  |
|     +0.1 | EMA        | Structural  |
|     +0.5 | EMA        | EMA         |
|     +1.0 | EMA        | EMA         |

Choosing merely `>` rather than `>=` at 0 **does not** create a robust neutral/default region for a near-zero Gaussian; the margin makes an EMA request unambiguously positive. This remains a *design choice* whose effect requires measurement.

### 4.2 Hybrid categorical encoding

Keep the two explicit categories:

- `structural` encoded at raw `-0.5`;
- `EMA` encoded at raw `+0.5`.

With a deterministic categorical tie, choose index 0 (`structural`). The policy must explicitly select the EMA class for the EMA path. Retain the categorical `log_prob` and action-centers consistency; do not introduce a new categorical head, action coordinate, or distribution as part of the exit-semantics treatment. If categorical logits strongly favor EMA, that is **learned action preference**, not evidence of the Gaussian midpoint bias.

### 4.3 Compatibility rules

1. Version **decoding semantics**, not merely the action width: `overlay-action-v2` (legacy) and `overlay-action-v3` (structural-neutral). Keep coordinate ordering and named layout keys unchanged.
2. Record `action_schema_version`, `exit_decoder_version`, raw/normalized activation boundary, EMA enabled flag, actor distribution, hybrid category centers, coordinate names/layout, and source fingerprint in run and evaluation manifests.
3. Preserve v2 checkpoint bytes and original v2 checkpoint-to-v2 decoder binding. **Never silently upgrade a v2 checkpoint or relabel an old run as v3.**
4. Loading/resuming a v2 model into a v3 training environment must fail closed. The only exception is a **read-only, explicitly labeled `legacy_v2_checkpoint__v3_counterfactual_decode`** evaluation adapter that does **not** mutate or resave the model.
5. Historical replays must continue matching original hashes/metrics within the established deterministic evaluation tolerance. For unversioned checkpoints, retain existing explicit legacy opt-in and layout requirements.
6. Add future contract tests (after separate approval): raw boundary values; exact midpoint; EMA-disabled fallback; hybrid category centers and ties; per-layout exit index; old checkpoint reproducibility; mismatched version rejection; serialized metadata round-trip; sequential replay parity under v2.

---

## 5. Smallest matched experiment: experimental protocol

### Phase 0 — Read-only provenance freeze (NO TRAINING)

**Goal:** Ensure that the study compares the *same artifact* and *same execution rules*.

1. Select the archived hidden-state 2M seed-50 checkpoint and corresponding historical run with the cited March-to-November equity swing.
2. Locate and verify its actual `checkpoint SHA-256`, source snapshot/commit, run manifest, resolved configuration, action layout, policy distribution (Gaussian vs hybrid), observation schema, data/split/cache identities, and report/trade/equity files.
3. Verify whether the exit mean prior was active. Recover raw exit-action statistics **at decision time**, EMA/structural assigned mode **at entry**, and the actual `exit_reason` **at close**; these are different fields and denominators.
4. Restore the archived source/evaluation identity, with no mixing from `main` commit `785163c` except clearly labeled read-only analytical tooling.
5. Reproduce the **original v2** ledger and equity curve before attempting any semantic counterfactual. Reconcile fills, trades, PnL, daily risk, terminal state, and hashes/tolerances. If it cannot be reproduced, **STOP** and report the provenance failure.

**Output:** Immutable identity table and v2 replay verification report. **STOP gate:** Do not infer effects when the historical baseline cannot be reproduced.

### Phase 1 — Two-arm frozen-checkpoint decoder intervention (NO LEARNING)

**Estimand:** Net difference in the *closed-loop simulated performance of a fixed historical policy when only its exit decoding is changed*; this is not the effect of retraining a v3 policy.

| Arm                          | Model weights          | Decoder           | EMA enabled | Calendar            |
| ---------------------------- | ---------------------- | ----------------- | ----------- | ------------------- |
| A: `v2_original`           | Same frozen checkpoint | Exact archived v2 | Yes         | Complete 2025 train |
| B: `v3_structural_neutral` | Exact same checkpoint  | Proposed v3       | Yes         | Identical           |

Protocol:

1. Prefer the checkpoint's declared evaluation action mode. Preserve deterministic/stochastic setting **exactly** and report it prominently. Do not compare deterministic A with stochastic B.
2. For deterministic policy action, evaluate both arms with the same frozen weights and input seed. For stochastic evaluation, use matched reproducible action randomness (e.g., controlled seeded streams or matched draws per decision) and identical execution randomness to the extent meaningful.
3. Both arms must use the **same source/runtime snapshot and evaluation backend** except the isolated decoder intervention. Any mandatory test harness code changes require **separate permission**, and that harness must be recorded as a derivative, not used to overwrite historical source.
4. Run over the **entire chronological 2025 training calendar**, including short sessions and original session schedule. Do not use only the profitable prefix or the decline period.
5. Record first differing decision, EMA share of eligible requests, accepted/rejected entries, exposure, positions, exits, equity, and reasons for divergence. Once positions/equity differ, observation and action streams can also diverge: document this explicitly.
6. Do not alter the checkpoint, reward, target algorithm, costs, risk policy, stop logic, entry constraints, or benchmark accept/reject criteria.

**Causal limitation:** The entire sequential replay is a decoder-intervention contrast in a simulator, but differences after the first divergence combine altered entry eligibility, position outcomes, account state, and subsequent policy decisions.

### Phase 2 — Matched entry-cohort/exit-only shadow analysis (NO LEARNING)

**Goal:** Disaggregate exit quality from structural entry admissibility and compounding feedback.

1. From the original v2 replay, extract a **fixed entry cohort** with decision time, side, fill reference, initial risk distance, stop level, intended size, available structural target menu, EMA observations, and input features.
2. For each entry, compute the counterfactual outcome under v2 EMA/structural rules and v3 structural-neutral rules **on the same future tick/bar path**, with the same initial size, stop, cost implementation, max holding/session-end behavior, and target availability.
3. If a v2 entry has **no admissible structural target** under v3, label it `NO_STRUCTURAL_TARGET` and report it as an **eligibility effect**; do not invent a substitute TP to manufacture a paired exit.
4. Separate **common admissible entries** (paired trade-level exit outcomes) from **entry-admission changes** (population selection) and **sequential feedback** (full replay). Reconcile their totals only where accounting identities legitimately apply; a shadow ledger will not necessarily equal closed-loop account equity.
5. Analyze PnL in dollars **and R units**, adverse/favorable excursion, reward capture, duration, exit reason, and cost sensitivity. Compare chronological monthly/quarterly expectancy and pre/post 2025-03-20 descriptively, noting the peak date was chosen ex post.
6. Inspect the original exit action histogram around raw 0, observed EMA selection frequency, and mode-prior activity. A large mass exactly at/near zero followed by EMA selection is the core mapping-bias mechanism; a confidently positive EMA preference is not.

**Output:** Trade-level pairing ledger, unmatched eligibility ledger, summary by month/quarter and pre/post peak, and explicit attribution of full-replay differences.

### Phase 3 — One paired fresh training pilot, only if authorized later

**Not part of current execution.** This phase is proposed only after phases 0–2 are interpreted and authorization is granted.

- **Two arms:** Fresh v2 training versus fresh v3 training of the **same selected variant**, with **same seed 50** and **same 2,000,000-step budget** (allow only the trainer's documented step-rounding behavior). Do not compare a legacy checkpoint to a newly trained one.
- Both arms must run on the **same approved source commit**, containing a selectable versioned decoder, with one-and-only-one intended difference: `exit_decoder_version` / action schema version. Preserve the same categorical policy if hybrid, or same Gaussian policy if Gaussian; do not simultaneously switch actor family.
- **No warm-start.** New initial weights, optimizer setup, and model construction must be generated reproducibly and matched across arms. The differing decoder will naturally cause training trajectories to diverge.
- Evaluate **both deterministic and stochastic** action policies as distinct labeled diagnostics if agreed in advance; do not switch evaluation choice because one arm looks better. Primary mode should match the frozen approved campaign protocol.
- Use only the 2025 training split for pilot selection and viability. The 2026 report interval remains exposed/report-only and is not a tuning surface.
- A single seed cannot establish a statistically robust improvement. If the 2M pair passes the agreed gates, consider additional **paired** seeds *before* considering a 20M campaign; no automatic escalation.

---

## 6. Frozen settings and sources of confounding

All paired arms must match on the **resolved effective configuration**, not just filenames. Assert equality for every key **except the explicitly declared exit decoder/schema fields** and run identity/log paths.

| Domain                | Must remain fixed                                                                                                                                                                                                                |
| --------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Input data            | Chronological 2025 split (`2024-12-30`–`2025-12-31`), full M1 bars, configured US100 and auxiliary series, M3–D1 data, scheduled short-session inputs, feature columns/normalizers, tick files, dataset/cache hashes       |
| Price discretization  | Same quarter-point rounding configuration if the selected historical/new pilot requires it; never compare rounded and unrounded runs as one-factor experiments                                                                   |
| Execution             | Same bid/ask quotes, seeded 0–30 ms latency, first-eligible-tick selection, quote side, spread, price increment, slippage **as implemented** (not merely as declared), commission and timing                              |
| Opportunity/entry     | Same PO3/IFVG or selected strategy family, candidate/arming FSM, visibility setting, direction/intensity/risk entry gates, order rejection criteria, session restrictions                                                        |
| Stops and targets     | Same SL anchor/buffer, structural TP menu, RR bounds, TP/SL mode settings, multi-TP/simplex, partials, trailing/breakeven, session close semantics                                                                               |
| Risk/account          | $100,000 initial balance; selected campaign's $1,000 idea-risk cap, $900 sizing cap, $5,000 daily limit, $10,000 initial-equity loss limit; no unapproved trade-risk floor; same peak-DD on/off behavior and gate interpretation |
| Architecture/training | PPO family, encoder, policy distribution, action layout, reward (e.g. DSR), optimizer, entropy/prior configuration, `n_envs`, minibatch, rollout, model-init seed, sample count                                                |
| Evaluation/reporting  | Identical calendar, execution seed, deterministic/stochastic policy option, breach handling, accounting, trade-reconstruction rules, and export metrics                                                                          |

**Source hierarchy:** Historical replay uses the archived pilot's actual run config and source identity; for later *fresh* paired pilots, use a newly approved, single frozen source revision and document exact settings. The current active `policy2m_v1` campaign is a **separate lineage**; never pool its outcomes with the prior pilot without an explicit matched-source design.

---

## 7. Mandatory diagnostic outputs

Require a machine-readable per-decision/per-trade dataset and a concise interpretation report with:

1. **Provenance:** source commit/snapshot SHA, config and dataset hashes, checkpoint SHA, action and observation versions, evaluation/backend identity, seeds, date window, execution assumptions.
2. **Action mapping:** raw `action_exit`, `exit_u`, decoder version, active threshold, requested/selected mode, actual entry mode, Gaussian versus hybrid, Gaussian mean/std or hybrid logits/category, mode prior flags.
3. **Trade lifecycle:** timestamps, side, source candidate, initial SL/TP/EMA availability, risk/size, entry accept/reject reason, realized exit reason and price, costs, planned and realized R, MAE/MFE, exposure, holding time.
4. **Equity/risk:** full equity and drawdown series, starting and peak equity, PnL attribution, initial-equity loss-floor breaches, daily breaches, peak-DD intervention status, position count, same-idea reopens.
5. **Time slices:** month/quarter by net expectancy R, loss rate, trade count, profit factor, drawdown, long/short and exit type; note that 2025-03-20 is a retrospectively selected peak and cannot serve as an unplanned validation set.
6. **Intervention attribution:** for each change, identify (i) common eligible trades with changed exits, (ii) entries rejected/accepted due to geometry, (iii) downstream changes in account state/policy inputs, (iv) differences attributable to execution randomness.
7. **Reconciliation:** position completes and fills sum to reported PnL; declared net return, trade counts, safety breaches and numerical metrics are recomputed from ledger and agree within a predeclared tolerance.

**Minimum analysis tables:** (a) A-versus-B full-calendar metrics, (b) paired common-entry exits, (c) unmatched admissions, (d) monthly/quarterly trade cohort metrics, (e) raw action mode-distribution near neutral, (f) cost/risk sensitivity. Include both raw evidence and limitations, not charts alone.

---

## 8. Predeclared decision gates

### Gate G0 — Historical fidelity (hard STOP)

- [ ] Archived checkpoint and all relevant manifest/source hashes verified.
- [ ] Original `overlay-action-v2` decoded identically, with no silently modified old model.
- [ ] Exact/within-tolerance original trade/equity reproducibility and risk ledger reconciliation demonstrated.
- [ ] Run is explicitly identified as Gaussian or hybrid; active mode prior is verified, not assumed.

**FAIL ⇒** No causal interpretation and no training. Diagnose only the integrity/reproducibility gap.

### Gate G1 — Semantic and comparison correctness

- [ ] v3 raw-zero returns structural; `+0.5` explicitly returns EMA; boundary `+0.25` documented.
- [ ] Hybrid category centers and categorical log-prob semantics remain valid.
- [ ] Old v2 inference behavior and resume compatibility are unchanged; v2→v3 resume is rejected.
- [ ] Matched replays differ only in decoder interpretation; first divergence and subsequent feedback are audited.
- [ ] Eligibility changes are reported separately from common-entry exit effects.

**FAIL ⇒** Do not use the comparison to support a causal or economic conclusion.

### Gate G2 — Evidence threshold for requesting the 2M pilot

- [ ] The actual historical policy has enough affected exit decisions to meaningfully test H1 (do not infer from another campaign's EMA rate).
- [ ] The neutral-action frequency and decoder intervention confirm that the hypothesis is operative, **or** show conclusively it is not operative for this policy family.
- [ ] Common-entry shadow outcomes and sequential outcomes are both reported; no result is attributed solely to an exit improvement if it is driven by reduced admissible trades.
- [ ] Any claimed improvement is not merely from suppressing activity, breached-risk accounting, or altered simulation costs.
- [ ] No thresholds, seeds or arms have been selected by optimizing against the observed 2025 peak or the exposed 2026 report period.

**Interpretation:** If v3 markedly changes accidental EMA selections and improves matched common-entry outcomes while preserving reasonable activity, request the pilot. If v3 reduces EMA but the same later-period losses persist across entry cohorts, prioritize entry/edge diagnostics rather than further exit tuning. If the selected checkpoint is hybrid and already uses explicit categories, the hypothesis may be largely inapplicable; document that result instead of forcing a treatment.

### Gate G3 — Requirements before ANY 20M campaign

- [ ] Fresh approved 2M v2/v3 pair completed with same data/seed/training budget and resolved settings except decoder.
- [ ] Both arms show interpretable trading activity and **noncollapsed / measurably state-responsive** actions (not just nonzero trades).
- [ ] No hard-loss/risk violation under the declared policy. Peak-DD monitoring is consistently active or consistently report-only; do not change this to engineer a pass.
- [ ] Improvement is assessed on net R/expectancy, risk-adjusted return, trade opportunity, and drawdown, not one favorable ending equity number.
- [ ] Additional independent **paired seeds** and cost sensitivity support the result if claiming it is more than a single-seed feasibility finding.
- [ ] Baseline reproducibility, full trade/equity reconciliation, config and checkpoint SHA-256, and schema round-trip tests are retained.
- [ ] The responsible research lead separately authorizes the budget. **No automatic 20M start.**

The G2/G3 criteria must be fixed **before** seeing new results. Do not optimize exit cutoff, reward, minimum trading frequency, drawdown enforcement, dataset splits or training budget in response to an unfavorable arm.

---

## 9. What would count as evidence for each explanation?

| Matched observation                                                                           | What it supports                                         | What it does **not** prove                      |
| --------------------------------------------------------------------------------------------- | -------------------------------------------------------- | ----------------------------------------------------- |
| Many raw exits near 0; v2 selects EMA and v3 structural                                       | Mechanically operative Gaussian neutral-action bias      | EMA necessarily causes negative PnL                   |
| Common eligible entry-cohort exits improve under v3, particularly in fixed late-2025 quarters | Exit choice contributes to loss realization              | Other years will be profitable                        |
| Full replay improves, but mostly because structural has no valid target and rejects entries   | Admission/selection effect                               | Better trade exits                                    |
| v3 EMA share falls, but late-2025 conditional expectancy stays negative across modes          | Broader edge deterioration more plausible                | Exact cause among entries, regimes, rewards, costs    |
| Hybrid policy intentionally chooses EMA through positive categorical logit                    | Learned preference rather than Gaussian midpoint default | Learned preference is good or bad                     |
| Frozen-checkpoint v3 worsens but fresh v3 training improves                                   | Retraining/adaptation matters                            | Robust performance or causal attribution across seeds |

---

## 10. Agent instructions and deliverables

**For any planning/review agent operating under this document now:**

1. Treat all steps above as **proposals**. **Do not execute experiments, implement the decoder, edit the repository, launch GPU work, or alter tmux/Slurm allocations.**
2. Inspect existing evidence *read-only* if authorized and identify missing artifacts/links required to execute phases 0–2 later.
3. Produce a **single concise GO/NO-GO proposal** with: exact archived checkpoint path and SHA once verified; effective decoder and actor family; feasibility of paired replays; all unresolved provenance blockers; expected compute budget only if measured or confidently evidenced.
4. If execution is separately authorized, open a minimal reviewed implementation task for versioned decode and test harness. Preserve v2 as a first-class selectable path. Do not start with a broad environment, reward, risk, or actor refactor.
5. Write any new diagnostic results under a **new** run ID with clear provenance and never overwrite archived output. Preserve complete comparative artifacts and a single reviewable final report.

**Planned artifact manifest (only if separately authorized later):**

```text
reports/exit_semantics_counterfactual_<run_id>/
  provenance.json
  frozen_config_diff.json
  v2_reproduction.json
  action_histograms.csv
  v2_full_calendar_equity.csv
  v3_full_calendar_equity.csv
  v2_trade_ledger.csv
  v3_trade_ledger.csv
  matched_entry_exit_shadows.csv
  unmatched_entry_eligibility.csv
  time_slice_comparison.csv
  decision_gates.json
  exit_semantics_findings.md
```

## 11. Relevant source references

- [`simulation/environment/action_runtime.py`](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/785163c/simulation/environment/action_runtime.py)
- [`learning/rl/hybrid.py`](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/785163c/learning/rl/hybrid.py)
- [`learning/rl/ppo.py`](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/785163c/learning/rl/ppo.py)
- [`trading/orders/entries.py`](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/785163c/trading/orders/entries.py)
- [`simulation/environment/ema_exit_runtime.py`](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/785163c/simulation/environment/ema_exit_runtime.py)
- [`decisioning/actions.py`](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/785163c/decisioning/actions.py)
- [`learning/rl/agent.py`](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/785163c/learning/rl/agent.py)
- [`docs/thesis/manuscript_draft.md`](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/785163c/docs/thesis/manuscript_draft.md)
- [`docs/thesis/master_project_execution_plan.md`](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/785163c/docs/thesis/master_project_execution_plan.md)
- [`docs/thesis/evidence/zero_trade_prevention_validation_20261023.md`](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/785163c/docs/thesis/evidence/zero_trade_prevention_validation_20261023.md)

---

**Final disposition:** **GO for planning and provenance review only. NO-GO for code changes, training, and larger campaigns until separately authorized and the specified evidence gates are met.**