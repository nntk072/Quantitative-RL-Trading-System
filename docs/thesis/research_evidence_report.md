# Multi-timeframe context and setup-conditioned trading policies: an evidence report

**Document status:** evidence-bounded manuscript draft. This is not a final
thesis or release verdict. It summarizes the local evidence snapshot present
in the checkout on 2026-11-02; its scientific claims remain bounded by the
source, model, execution, and release gaps described below.

## Abstract

This report examines whether multi-timeframe market context and setup-conditioned
reinforcement-learning policies have demonstrated better decisions under the
project's configured execution and account-risk rules. The repository defines
a six-family, nine-timeframe, two-direction setup catalog and supplies a
training-period matched policy pair, earlier short-budget screens, local
market-data audits, and reproducible analyses of saved trade rows. The
selected seed-50 pair completed its configured training-period evaluation but
both arms failed the declared zero-breach survival gate. Its historical daily
loss events came from a gross-negative-close counter and do not establish
net-equity daily breaches. The opportunity census counts eligible feature
contexts, not executable trades. Configured native bars agree with their M1
resampling on timestamps and OHLCV, but spread interpretation, tick quote
chronology, authoritative source clock and schedule remain unresolved. No
matched economic baseline registry, independent-seed robustness result, or
untouched confirmatory period is available. The evidence therefore does not
establish that setup conditioning, reinforcement learning, or any tested
policy yields a robust economic edge.

## 1. Introduction and motivation

Trading policies act on a stream of market observations while their decisions
affect later positions, risk, and available actions. A useful research result
must therefore connect what was observable at decision time to the candidate
trade, its order and fill path, account transitions, and final evaluation. A
backtest return alone cannot establish that this chain was causal or that the
same policy would remain viable under declared account constraints.

This project represents market context across M1 and higher timeframes and
offers a catalog of structural setup choices. The research motivation is to
test whether historical multi-timeframe context and setup-conditioned action
heads improve decisions under controlled risk and execution assumptions. The
relevant alternative explanations include candidate availability, feature
timing, action-interface rejection, reward semantics, trading costs, and
account-risk behavior. The evidence below treats those mechanisms as separate
questions and retains negative results.

The bibliography frames the method without implying that its published
results transfer to this dataset. Sequential decision-making and partial
observability motivate representing temporal state rather than treating each
candle as an independent example (Sutton and Barto, 2018; Kaelbling, Littman,
and Cassandra, 1998). PPO and SAC provide policy-learning references, while
constrained policy optimization motivates keeping risk constraints explicit
(Schulman et al., 2017; Haarnoja et al., 2018; Achiam et al., 2017). Temporal
convolution, attention, and multi-horizon models are relevant architecture
families, not evidence that a particular encoder is best here (Bai, Kolter,
and Koltun, 2018; Vaswani et al., 2017; Lim et al., 2021). Trading-system
evaluation and repeated model selection require caution about noisy returns
and selection effects (Sharpe, 1966; Lo, 2002; Bailey and López de Prado,
2014; Bailey et al., 2017; White, 2000). The curated bibliography is in
[`docs/research/references.md`](../research/references.md).

## 2. Research questions and hypotheses

These questions organize the existing evidence. They are not a claim that a
prospective preregistration was completed before the historical runs.

| Question | Hypothesis to test | Current status |
|---|---|---|
| **RQ1 — Data and timing:** Can the configured multi-timeframe observations be aligned and made available causally? | H1: Each feature and higher-timeframe value is available only after its source information could be observed. | Partially tested. Configured prefix and bar-parity checks pass within bounded scopes; source-event publication times, schedule authority, and exhaustive feature coverage remain open. |
| **RQ2 — Entry-state visibility:** Does exposing the entry-state machine to a setup-conditioned policy improve risk-gated decisions? | H2: Visible FSM state improves policy outcomes over the same policy with state hidden, under matched data, action, cost, risk, and evaluation semantics. | Not established. The A4A/A4B pair differs only by the declared visibility treatment; both arms failed the survival gate and one seed supports descriptive results only. The pair does not compare setup-conditioned with unconditioned policies. |
| **RQ3 — Price geometry:** Does representing an explicit candidate entry, stop, target, and lifetime improve decisions beyond a setup ID? | H3: Candidate-specific geometry and history provide useful information beyond categorical setup identity. | Not tested. Tick-based MFE/MAE now describes recorded position paths, but the current policy has no candidate-specific proposed-price or order-TTL inputs and the historical runs lack decision-level geometry traces. |
| **RQ4 — Learning value:** Does RL improve over feasible flat, random, rule-based, and supervised controls under common execution and risk semantics? | H4: An RL policy improves net, risk-adjusted outcomes over matched non-RL policies. | Not established. A reusable flat/random setup evaluator now has synthetic coverage but no market-data result; a complete comparable baseline registry is absent. |
| **RQ5 — Robustness:** Does any observed advantage survive independent seeds, chronological development folds, costs, and regimes? | H5: A policy advantage is stable under the declared uncertainty and stress protocol. | Not tested to a confirmatory standard. There is one selected matched seed and the 2026 report interval is exposed. |

The active [`validation protocol`](../research/validation_protocol.md) preserves
the distinction between training, validation, exposed exploratory periods,
and a still-uninspected locked period.

## 3. Data, periods, and exposure

The current evidence uses local US100.cash and US500.cash exports. The main
training interval is 2024-12-30 through 2025-12-31. The interval 2026-01-01
through 2026-10-16 was previously inspected and is exposed exploratory/report
data; it is not an untouched test period. Re-running it cannot restore
confirmatory status.

The selected campaign manifest names 39 input entries and approximately
8.16 GB of selected campaign inputs. A separate local inventory records 140
declared paths resolving to 64 unique files, approximately 16.33 GB. The
selected campaign input hashes matched their recorded manifest in the
current-source audit. The raw data remain local and are not included here.
Provider identity, license terms, and redistribution rights are **not
assessed**; this report makes no rights claim.

Configured native M3, M5, M10, M15, M30, H1, H4, and D1 series were compared
with M1-derived bars for both symbols. Across 30 native series, timestamps and
OHLCV matched the configured M1 aggregation on 532,350 development rows and
423,018 exposed-report rows. US100 D1 is configured as an M1-derived view and
is not an independent native parity check. Native spread differed from both
M1-mean and M1-last references; these measurements do not identify which
spread aggregation is authoritative. The configured schedule's authority and
the source clock/timezone/DST interpretation remain unresolved. See
[`multi-timeframe alignment`](../research/multitimeframe_data_alignment.md)
and the canonical report path
`evidence/research/releases/negative-evidence-readiness/configured_timeframe_parity.json`.

The selected pair's tick audit found 371,390 rows with a required bid or ask
side missing or non-finite. It found 329,471 adjacent equal-timestamp pairs:
328,918 pairs had changed quote values and 553 had a missing quote; no
identical-quote pair was counted. The training M1 series had 23 minutes per
instrument with no tick in the same minute. These are data-quality findings,
not proof of within-minute quote availability, authoritative timestamp order,
or the quote used by a broker. A separate scan matched 3,698 tick-backed fill
events from both selected ledgers to local tick timestamp groups. Sixteen
events shared groups with changed quote values; 87 were in groups missing the
required quote side, and the stable parser used a carried side for those 87
events. The refreshed report records reported and reconstructed prices,
timestamp-group price ranges, carried-side age, and order/arrival/fill timing.
It still does not establish within-timestamp order or executable availability
at arrival, and no no-carry or next-valid-quote economic sensitivity has been
computed. See
`evidence/research/releases/negative-evidence-readiness/current_market_input_diagnostic.json`,
`evidence/research/releases/negative-evidence-readiness/tick_quote_side_flag_cross_tab.json`,
and [`fill quote availability`](../research/fill_quote_availability.md) with
the machine report at
`evidence/research/fill_quote_source_alignment/selected_campaign_fill_quote_alignment.json`.
The stable-source v2 quality profile is now complete: all 39 campaign inputs
(8.16 GB) are present and hash-matched, with day/week/month counts retained by
role, instrument, and timeframe. The selected event-alignment report still
does not establish an executable quote for carried-side or changed-tie events;
the companion monthly quote-side table and figure are descriptive quality
summaries, not evidence of quote availability at order arrival.

## 4. Simulator, account rules, and evaluation method

The system contains a TradingEnv training path and an event-driven backtest.
They model different execution purposes and should not be treated as
identical without controlled reconciliation. The selected campaign used a
configured tick-fill path with seeded 0–30 ms order-arrival latency and the
first eligible bid/ask tick after arrival; a missing required tick input
fails closed. The local tick export nevertheless contains missing sides and
same-timestamp ties, and the authoritative feed clock and schedule are not
known. This report therefore does not claim that every historical fill is
verified against a uniquely ordered executable quote.

The environment and event-driven backtest now reset daily counters on the
supplied date-derived session ID. Controlled synthetic traces check loss,
reset, open PnL, wins, and later-session losses at two starting balances. A
separate source-characterization fixture confirms both engines process
same-bar protective exits before account guardrails, scope daily breaches to
the supplied session, and latch maximum-loss/trailing-drawdown breaches for
the remainder of a non-episodic rollout. Paired synthetic repeated-payout
traces also align on payout, reset, and a later max-drawdown failure. This is
narrow deterministic policy parity on synthetic inputs, not true within-bar
chronology or full lifecycle coverage. A bounded local-data action replay
matches a controlled entry and exit to unique, complete local quote groups and
reconciles both engines' fills, PnL, and ending balance; it does not replay a
historical policy. The external reset anchor, full training/live risk parity,
and broad real-feed lifecycle coverage remain open.

The selected matched policy pair used seed 50, 2 million training steps, 32
environments, and the 2024-12-30 through 2025-12-31 interval. Its declarations
include the declared `env.entry_state_observation` treatment: A4A used the
six-coordinate account vector without entry-state one-hot values, and A4B
used the ten-coordinate vector with them. The preserved resolved configs
differ only in this setting, so the widths are an intentional single-factor
visibility contrast rather than an unexplained configuration discrepancy.
This does not make the arms input-identical or establish matched economics.
The policy's 2026 evaluation-period action trace is incomplete. The stored
`fail_time` is the first breach time, while both evaluations reached the end
of the configured data split. Retained 2025 training-partition records now
reconcile all 987 A4A and 825 A4B positions to fill events and ordered
decision/submission/fill/exit timestamps, including recorded holding times. A
separate local TickBook analysis derives timestamp-bounded liquidation-side
MFE/MAE for these positions: median MFE is 0.569R/0.552R and median MAE is
0.815R/0.774R for A4A/A4B. The arms have different trade cohorts; these
observations are not feasible exit counterfactuals and do not establish
authoritative quote chronology. Historical candidate-proposal and eligibility
state is not linked to each selected action. See the
[`selected policy trade lifecycle`](../research/selected_policy_trade_lifecycle.md)
report, the trade excursion results at
`evidence/research/selected_policy_trade_lifecycle/trade_excursions/README.md`,
and the paired evidence packet at
`evidence/research/selected_policy_trade_lifecycle/`.

| Training arm | Positions | Median MFE (R) | Mean MFE (R) | Median MAE (R) | Mean MAE (R) | Paths reaching 1R MFE |
|---|---:|---:|---:|---:|---:|---:|
| A4A | 987 | 0.569 | 0.960 | 0.815 | 0.670 | 32.4% |
| A4B | 825 | 0.552 | 0.944 | 0.774 | 0.663 | 31.9% |

R here is price excursion divided by the recorded initial stop distance.
Liquidation-side bid/ask prices are used, but commissions are not deducted.
The cohorts differ and timestamp-tie bounds affect 2 A4A and 1 A4B position;
these descriptive values are not a matched treatment estimate or feasible
exit counterfactual.

The current setup catalog contains six idea families crossed with nine
timeframes and two directions: 108 setup IDs plus `NO_TRADE`. The supported
setup mask represents eligibility at the current row. The conditioned policy
adds a learned setup-ID embedding to the market latent for execution heads;
it does not encode a candidate-specific proposed entry, stop, target, fill
time, or order lifetime. The configured opportunity census covers 351,432
training M1 decisions: 24 catalog categories are supported by its registered
configuration and 84 are unsupported. Candidate episode starts are feature
context transitions, not independent trade outcomes. The architecture and
run-shape boundaries are documented in
[`model observation and action semantics`](../research/model_observation_and_action_semantics.md)
and the census packet at
`evidence/research/trade_setup_opportunity_census/`.

## 5. Results

### 5.1 Selected matched policy pair

Both arms failed the predeclared strict zero-breach training risk-survival
gate, although both evaluations completed the configured data split. The
treatment recorded 987 positions and −2.154% net return, ending at $97,845.69.
The control recorded 825 positions and −10.056%, ending at $89,943.95, which
was $56.05 below the $90,000 floor. Aggregate ending equity does not erase a
per-episode gate failure.

The first daily-loss events occurred on 2025-03-06 under the historical
`trading_policy.mode=legacy` counter. That counter accumulated gross losing
closed-trade PnL without offsetting winning closes or measuring net daily
equity. Through the events, gross negative closes were $5,017.66 for the
treatment and $5,399.25 for the control, while net realized close PnL was
−$3,004.28 and −$3,389.32, respectively. These events establish failure of
the configured historical counter; they do not establish an FTMO-style
net-equity daily-loss breach. The control also recorded a later maximum
drawdown event on 2025-10-28. The detailed trace is recorded in
`evidence/research/releases/negative-evidence-readiness/legacy_daily_loss_counter_breach_trace.md`;
see also [`entry/exit attribution`](../research/entry_and_exit_attribution.md)
for the paired-row analysis. These counts preserve the distinction between the
historical gross-loss counter and net realized close PnL.

The training entry-funnel diagnosis found that 88.3% of treatment entry
requests and 91.1% of control requests were rejected because the entry state
machine was not armed. This indicates substantial action-interface attrition;
it does not show that changing the mask would improve economic results or
explain the losing equity paths.

The March-to-April actual gross mean-R change was −0.2177 for the treatment
and −0.2238 for the control. The month-stratified 95% intervals were
[−0.5837, 0.1429] and [−0.5656, 0.1118], both including zero. The frozen-entry
EMA21 reference decomposes saved monthly outcomes arithmetically; it is not a
new policy rollout, causal intervention, or compounded portfolio
counterfactual. This paired-row recomputation is R2 evidence, not a raw-tick
replay or checkpoint reproduction. See the
[`entry/exit reproduction notebook`](../reproduce/entry_and_exit_attribution.ipynb)
and canonical paired rows in
`evidence/research/entry_and_exit_attribution/`.

### 5.2 Earlier short-budget screen and exposed interval

An earlier 100k-step, one-seed screen replayed 99,492 training decision bars.
Both policies failed the configured $10,000 maximum-loss gate. The control
ended at $90,003.73 over 308 positions; the setup-conditioned treatment ended
at $90,026.53 over 1,031 positions. This is a negative exploratory screen,
not a 2-million-step result and not confirmation of comparative performance.
The registered equity figure and its limitations are in
[`the full training-period screen`](../research/setup_conditioned_policy_replay.md).

The exposed 2026 report-period replay ended at −10.0016% for the treatment
and −10.3679% for the control; both breached the account floor. Because those
dates were already inspected, these outcomes are descriptive stress evidence,
not holdout results.

A separate one-seed, 2-million-step MTF architecture screen recorded all three
variants failing their training survival gates and their full-period exposed
test replays. Each reported training and test return was negative. This is a
separate `thesis-overlay-action-v1` screen, not the selected 109-way
trade-setup conditioning comparison, and it does not rank the architectures.
The [semantic evidence packet](../../evidence/research/model_observation_and_action_semantics/mtf_architecture_screen.json)
records the source report path and hash, its `final_report_only` role, and the
previously inspected status of that interval.

### 5.3 Data, feature, and model audits

The current-source [all-profile real-market prefix report](../../evidence/research/feature_causality/real_market_feature_prefix_invariance_all_profiles.json)
resolves 130 configurations into 19 feature-builder groups and passes all 57
comparisons across three cutoffs, with no changed features and zero maximum
absolute delta. Its audit-runner and profile-inventory hashes match current
files; it records 78 source-file and four local-input hashes. This evidence
supports only those configured features, rows, and cutoffs. Event
cardinality, publication timing, calendar authority, and untested
configurations remain unresolved.
The source-backed matrix has source-contract metadata for all 106 public
feature/upstream candidates (95 feature functions and 11 upstream transforms)
and M1 output-availability records for all 108
setup flags. All 108 have source-level producer reviews; 24 selected flags
also have measured source-time identity coverage. The other 84 are disabled by
the registered overlay and have no active candidate rows or measured identity
counts. Source review records scalar/latest-zone event collapse for FVG/IFVG
and single-active-zone state for order blocks. PO3 identity includes the
selected same-timeframe IFVG confirmation and zone origin, with M1 using the
aligned IFVG-zone origin and MTF using source-state origin; tuple IDs can
still recur across disconnected state episodes. In the selected training
census, all 488,008 active rows resolve to 109,391 candidate-scoped IDs. Its
descriptive lifecycle counters record 115,863 identified episode starts,
13,758 adjacent identity changes, and 5,719 IDs reused across separate
active-mask intervals; these do not establish logical event cardinality.
Scalar FVG/IFVG projections can still collapse overlapping events. The audit
does not prove publication-time causality, schedule validity, or every
feature's end-to-end availability. See
[`feature causality and availability`](../research/feature_causality_and_availability.md)
and `evidence/research/feature_causality/feature_causality_matrix.csv`. A
separate source review maps the four signal families used by the 24 enabled
flags, but it does not resolve the policy's same-row decision/close boundary.

The opportunity census is descriptive. Twenty-four categories have configured
support and 84 do not; enabled candidate episode starts range from 3 for long
D1 standard-deviation context to 24,413 for long M1 unretested-IFVG context.
These counts reflect overlapping feature-state transitions and must not be
read as independent trades or expected returns.

Saved run manifests record distinct MTF input shapes, including M1 `[60,160]`
and `[60,322]` in separate architecture runs. The older selected policy
artifacts record an M1 `[60,746]` stream and a 12-coordinate action schema.
The scanned selected and architecture-comparison roots contain no qualifying
per-decision selected-setup or proposed-price geometry trace. The scope is
limited to those roots; it is not proof that no such trace exists elsewhere.

## 6. Baselines, ablations, and uncertainty

The available empirical comparison is not sufficient to estimate a general
RL advantage. A reusable flat/random setup evaluator now resolves the
source-configured environment, uses fresh environments and action schemas,
and records absolute metrics plus decision, event, and equity ledgers in
synthetic tests. A content-addressed draft-bundle writer binds input, config,
and source identities, but it has only synthetic integration coverage and no
market-data bundle. No market-data rollout has been registered or run. Simple
rule baselines have no promoted matched real-data result. A separate
cash/buy-and-hold calculation is an analytic
reference rather than the same simulator. Classical and supervised
implementations exist in the repository; there is no complete registry showing that they use the
same eligible action domain, data, fills, costs, risk, budget, seed, and
evaluation windows as the RL policy. The supervised sweep-direction prototype
now retains neutral labels and does not inspect the exposed 2026 interval
during its training epochs; its one post-training report remains descriptive
and report-only. It is still not a candidate-value baseline. The evaluated
registry has no theoretical comparator. Outcomes must not be inferred from
code availability.

No price-aware candidate-conditioned challenger has been implemented or
evaluated. No supervised candidate labels, calibrated outcome model,
candidate-level fill probabilities, or candidate-geometry sensitivity
results are established. Ablation, calibration, and price-sensitivity figures
therefore have no empirical result in this report.

The selected pair contains one training seed. Its paired monthly bootstrap
intervals describe the saved monthly paired rows and include zero; they do not
capture training-seed variation, model-selection uncertainty, missing-source
clock uncertainty, tick-tie ordering, or generalization to an independent
period. No independent paired-seed study, purged chronological model-selection
result, multiplicity-adjusted superiority estimate, or untouched holdout is
available. The complete 2026 report interval is exposed. Accordingly, no
claim of statistical superiority or robust economic value is supported.

## 7. Limitations and threats to validity

1. **Data clock and schedule:** local timestamps and configured session labels
   do not establish source timezone, DST history, authoritative market
   calendar, partial sessions, or unscheduled closures.
2. **Tick execution:** missing bid/ask sides and tied timestamps leave quote
   chronology uncertain. The selected fill-to-tick scan matches timestamps
   but records missing-side and changed-quote groups; minute or timestamp
   overlap is not proof of an executable quote at order arrival.
3. **Feature availability:** all 106 inventoried public feature/upstream
   functions have source-contract metadata, but selected prefix comparisons
   and component tests are bounded. The 24 enabled setup flags carry resolved
   source-time identities in matching decision records without changing the
   binary model-facing mask; these identities are not proof of one logical
   event per tuple. The 84 configuration-disabled flags have producer-level
   reviews but no selected-profile candidate measurements, and configurations
   outside selected checks remain open.
4. **Risk semantics:** the historical gross-negative-close counter is not a
   net-equity daily-loss contract. Current synthetic lifecycle tests establish
   selected protection ordering, breach scope, and repeated-payout transitions
   in TradingEnv and the event-driven backtest. They do not establish
   training/live parity, full account-lifecycle equivalence, or an external
   daily reset anchor.
5. **Policy matching:** the selected A4A/A4B configs differ only in the
   declared `env.entry_state_observation` treatment; the four extra account
   coordinates are its one-hot state. This is a controlled single-factor
   contrast, though the one-seed results are not robust evidence. Per-decision
   setup/geometry traces are absent from the inspected roots.
6. **Statistical exposure:** one selected seed, repeated historical searches,
   and an exposed report period limit independent inference. No new
   confirmatory period is present.
7. **Baseline coverage:** matched flat/random/rule/supervised/RL economic
   outcomes are incomplete, so the observed policy results cannot be ranked
   against a common decision set.
8. **External validity:** this is a local historical simulation. It does not
   establish broker queue position, market impact, live latency, or live
   profitability.

Provider identity, license terms, and redistribution rights are not assessed
in this local-only scope. Raw data are excluded and no rights claim is made.
The general [`research limitations`](../research/limitations.md) and the
release report at
`evidence/research/releases/negative-evidence-readiness/FINAL_READINESS_REPORT.md`
provide additional detail.

## 8. Conclusion

In the evidence currently available, the selected setup-conditioned policy
pair did not pass its declared training risk-survival gate, and no tested
policy has demonstrated a robust economic edge against a complete matched
baseline set. The configuration and feature audits provide useful bounded
engineering evidence: configured native bars reproduce M1 OHLCV aggregates,
selected feature profiles pass tested prefix comparisons, and the opportunity
census shows that only a subset of the nominal setup catalog is active under
the evaluated overlay. Those findings do not resolve source-clock,
within-timestamp quote, end-to-end feature timing, account-semantic, or
baseline-comparability questions.

The defensible conclusion is therefore negative and limited: the available
historical policies did not establish viability, and the one-seed A4A/A4B
evidence does not establish a benefit from exposing entry-state information.
That pair does not estimate the effect of setup conditioning itself. These
results do not imply that setup-conditioned or reinforcement-learning methods
are generally ineffective. A stronger claim requires the open data, timing,
risk, matched-baseline, multi-seed, and independent-validation gates to pass.

## 9. Reproducibility and data availability

The current result package distinguishes inspectable records from
independently recomputable evidence. The selected monthly attribution is R2
for the tracked paired-trade rows and summary; the underlying full run ledgers,
raw tick data, checkpoints, and training environment are not bundled in that
packet. Earlier 100k policy screens are reported at the evidence grade in the
result registry; they are not full retraining reproductions. The repository
does not claim research R3 frozen-policy replay or R4 retraining for the
selected attribution.

Reproduce the tracked monthly tables, intervals, decomposition, and figure by
executing all cells in the
[`entry/exit attribution notebook`](../reproduce/entry_and_exit_attribution.ipynb).
The documentation build also executes this notebook. Rebuild the candidate
census and its heatmap using the commands in
`evidence/research/trade_setup_opportunity_census/README.md` and the
corresponding scripts under
`scripts/research/analysis/features/`. Recreate configured bar comparisons
with `scripts/research/analysis/market_data/compare_configured_timeframe_bars.py`.
These commands require the local source files described by the campaign and
inventory manifests; raw market files are not distributed in this report.

## Evidence map

| Topic | Canonical research page | Machine evidence path |
|---|---|---|
| Research findings and claim status | [`Research map`](../research/README.md) | `evidence/research/releases/negative-evidence-readiness/FINAL_READINESS_REPORT.md` |
| Data provenance and access | [`Multi-timeframe alignment`](../research/multitimeframe_data_alignment.md) | `evidence/research/releases/negative-evidence-readiness/DATA_PROVENANCE_AND_ACCESS.md` |
| Feature timing | [`Feature causality`](../research/feature_causality_and_availability.md) | `evidence/research/feature_causality/feature_causality_matrix.csv` |
| Candidate coverage | Opportunity census packet at `evidence/research/trade_setup_opportunity_census/README.md` | `evidence/research/trade_setup_opportunity_census/census.json` |
| Model/action semantics | [`Model observation and action`](../research/model_observation_and_action_semantics.md) | `evidence/research/model_observation_and_action_semantics/run_artifact_shape_inventory.json` |
| MTF architecture screen | [`Model observation and action`](../research/model_observation_and_action_semantics.md) | `evidence/research/model_observation_and_action_semantics/mtf_architecture_screen.json` |
| Account-gate result | [`Entry and exit attribution`](../research/entry_and_exit_attribution.md) | `evidence/research/entry_and_exit_attribution/` and `evidence/research/releases/negative-evidence-readiness/legacy_daily_loss_counter_breach_trace.md` |
| Risk lifecycle behavior | [Risk and account limits](../concepts/risk_and_account_limits.md) | `tests/integration/backtest/test_risk_lifecycle_characterization.py` |
| Tick quote limitations | [`Fill quote availability`](../research/fill_quote_availability.md) | `evidence/research/releases/negative-evidence-readiness/current_market_input_diagnostic.json` |
| Reproduction grades | [`Result registry`](../reproduce/result_registry.md) | `evidence/research/releases/negative-evidence-readiness/RESULTS_REPRODUCIBILITY_MATRIX.csv` |
| Static test navigation | [Research map](../research/README.md) | `evidence/research/function_test_coverage/function_test_reference_map.csv` |

## References

All citations below refer to the existing curated bibliography; no additional
literature sources are asserted in this draft. Full entries are available in
[`docs/research/references.md`](../research/references.md).

- Achiam et al. (2017), constrained policy optimization.
- Bailey and López de Prado (2014), deflated Sharpe ratio; Bailey et al.
  (2017), probability of backtest overfitting.
- Bai, Kolter, and Koltun (2018), sequence modelling with convolutional and
  recurrent networks.
- Haarnoja et al. (2018), soft actor-critic.
- Kaelbling, Littman, and Cassandra (1998), partially observable sequential
  decision processes.
- Lim et al. (2021), temporal fusion transformers.
- Lo (2002), statistical properties of Sharpe ratios; Sharpe (1966),
  investment performance measurement.
- Schulman et al. (2017), proximal policy optimization.
- Sutton and Barto (2018), reinforcement learning foundations.
- Vaswani et al. (2017), attention-based sequence modelling.
- White (2000), data-snooping adjustment.
- Zhang, Zohren, and Roberts (2020), deep reinforcement learning for trading.
