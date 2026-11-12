# Model and baseline catalog

## Policy semantics

The current setup catalog contains 6 idea families × 9 timeframes × 2
directions (108 setup categories), plus `NO_TRADE` (109 categorical choices).
These are masked alternatives. They are not 108 independent return
regressions. The hybrid actor selects a setup using a shared market
representation; in conditioned mode its selected setup embedding also
conditions execution actions. Multi-timeframe temporal encoders represent
historical observations, but that alone does not prove price-level-specific
expected returns, fill probabilities, or candidate lifetime modeling.

## Implemented baselines and evidence coverage

| Baseline tier | Current implementation | What is verified here | Missing for a scientific comparison |
|---|---|---|---|
| Always-flat / no-entry | `always_flat` is a selectable reference in `scripts/research/analysis/evaluation/run_baseline_eval.py`; the separate Tier 0 setup evaluator also persists this arm under the same configured setup-action path. | The 2025 development Tier 0 control processed 351,432 bars and 99,492 decisions with zero entries, fills, return, and breaches. Its result packet and source/input identities are hash-manifested. This validates a real-data no-trade trajectory only. | No economic comparison is possible from a zero-entry arm. The general continuous baseline evaluator is not a matched registry for every RL action schema; its 2026 default remains exposed report-only. |
| Random eligible setup | `RandomEligibleSetupPolicy` in `evaluation.rollout` samples uniformly from the current `trade_setup_mask`, with a private seed, explicit decision-level trade probability, and normalized risk coordinate. `evaluation/rollout/matched_setup_baselines.py` pairs it with always-no-trade through the source-configured evaluation path. Every non-synthetic evaluation requires a positive absolute risk budget and resolves the effective config to `dollar_band` sizing at the fixed policy coordinate. | The verified 2025 development packet records 1,854 positions, 1,895 fills, -10.16% return, and 25 breach events over 99,492 shared decisions. Per-arm moving-block intervals and paired step-aligned intervals are included with the fixed structure rule. A serialization defect that copied the random arm's intervals into the flat arm was fixed and regression-tested; affected bundles are marked superseded. | This one-seed Tier 0 result is a negative accounting and execution-sanity reference, not an RL or strategy comparison. It cannot estimate between-seed variation or equal realized-risk distributions against RL. |
| Deterministic structure rule | `StructurePrioritySetupPolicy` in `evaluation/rollout/structure_priority_setup.py` selects from the exact 109-choice setup mask under declared family/timeframe precedence, keeps the risk coordinate fixed, and abstains on a direction conflict. It runs as a `RuleSetupBaselineArm` in the same matched evaluator. | The verified 2025 development run completed 1,169 positions and 1,209 fills, returned -10.03%, and recorded 25 breach events. The draft packet includes arm-specific within-trajectory intervals and paired step-aligned intervals against the random reference. | This is one deterministic Tier 1 rule, not an RL ranking or viability result. EMA, RSI, session-momentum, and other simple-rule comparisons are not yet registered under this matched contract. Its declared risk coordinate does not prove equal realized-risk distributions. |
| Simple rules | `BuyAndHoldStrategy`, `EMAMACDRSIStrategy`, `MultiLevelBreakoutStrategy`, and `SessionMomentumStrategy` in `trading/baselines/classical.py`; `run_baseline_eval.py` routes these through `TradingEnv`. Separate signal helpers are in `rule_based.py`. | Synthetic unit tests cover strategy signals; a smoke integration test covers report creation. The evaluator defaults to buy/hold, EMA/MACD/RSI, and breakout; session momentum requires explicit selection. The matched setup evaluator additionally supports the deterministic structure rule above. | No current-source matched real-data evaluation is promoted. Freeze one rule, period, costs, risk settings, and action semantics before comparing. |
| Supervised sweep-direction prototype | `LSTMSweepClassifier`/`LSTMStrategy` in `trading/baselines/lstm_classifier.py`; training entry point is `training/runner/lstm_baseline.py`. | The dataset now retains neutral examples and labels the first future close crossing using the session levels available at the last observed input row. The trainer no longer inspects the exposed report-only slice during the epoch loop; it emits one post-training exploratory score and trading summary labeled `exposed_report_only`. | This remains a heuristic sweep-direction model, not a candidate-value model or matched baseline result. Its historical 2026 interval remains exposed, and no model-selection, matched full-path risk, or economic comparison is claimed. |
| Cash / buy-and-hold reference | `cash_hold.py` has a separate train-sized US100 long-hold calculation; classical module also includes simple buy-and-hold signals. | Unit tests exercise the analytical sizing and accounting helper. | The cash-hold calculation is not an identical candidate-policy evaluation; its hard-coded contract/swap inputs need source verification and a common evaluation wrapper. |
| Theoretical comparator | None in the evaluated baseline registry. | No empirical evidence. | Define a non-deployable, explicitly non-comparable upper bound only if its information set and hindsight use can be bounded and labeled. |
| RL controls | Hybrid/setup-conditioned PPO screens and the selected matched policy pair. | One-seed 100k negative screens; selected seed-50 matched pair failed both training risk gates. | Independent seeds, full matched baseline set, cost stress, and untouched confirmation are absent. |

Source review: [matched setup-baseline composition](../../../../evaluation/rollout/matched_setup_baselines.py), [baseline evaluator](../../../../scripts/research/analysis/evaluation/run_baseline_eval.py), [classical strategies](../../../../trading/baselines/classical.py), [supervised baseline](../../../../trading/baselines/lstm_classifier.py), [test coverage index](FUNCTION_TEST_EVIDENCE_INDEX.csv). No baseline performance ranking is inferred from code presence or synthetic tests.

## Why the current implementations are not yet a matched comparison

The baseline entry points do not currently share one frozen economic
evaluation contract:

| Implementation | Action and observation domain | Data and period | Fill, cost, and risk boundary |
|---|---|---|---|
| Always-flat and simple rules | Scalar continuous actions through `TradingEnv`; the rules mostly ignore observations or consume precomputed signals. | The separate Tier 0 no-trade control ran over the 2025 development split and completed 99,492 decisions; its hash-manifested packet is under `evidence/research/matched_setup_baselines/`. The older `run_baseline_eval.py` still defaults to exposed 2026 reporting data. | The no-trade result has no entries/fills and is a control-path result only. Other rules do not yet use the selected-pair tickbook/latency contract. |
| Random eligible setup | Samples the current 108-way eligibility mask, retains abstention, and uses a fixed normalized risk coordinate. Non-synthetic Tier 0 calls require an explicit absolute dollar budget and record the effective `dollar_band` config. | One 2025 development reference completed 99,492 decisions, ending at -10.16% with 25 breach events. Earlier fail-closed diagnostics exposed and corrected bid/ask comparison, entry-bar, partial-target chronology, and source-quote precision issues. | Negative Tier 0 accounting evidence only. No multi-seed, equal-realized-risk, historical-checkpoint, or confirmatory comparison is available. |
| Deterministic structure rule | Uses the same `trade_setup_mask`, action schema, environment, and configured execution/risk machinery as a setup-conditioned arm; family/timeframe precedence and fixed risk coordinate are recorded in rule metadata. | One 2025 local-development rollout shares 99,492 decisions and identical inputs with the flat and random arms; its return is -10.03% with 25 breach events. | One deterministic rule and one period only. Paired intervals versus random are within-path evidence, not between-seed or equal-realized-risk inference. |
| Supervised references | `ReferenceTorchProvider` predicts an argmax over a 20-action schema; the setup-conditioned policy uses a 109-choice setup vocabulary plus execution coordinates. The LSTM baseline is separately defined. | Reference learner accepts caller-provided arrays and labels; the package has no audited candidate-target preparation or economic run. | No common candidate labels, fill model, selection rule, account gate, or matched rollout is registered. |
| Historical setup RL | Selected pair used a 12-coordinate action schema and one seed. Account widths 6 versus 10 encode the declared entry-state visibility treatment. | The selected 2025 development pair completed; the 2026 replay period is exposed and remains descriptive. | Preserved resolved configs differ only in `env.entry_state_observation`. Historical evaluation used seeded 0–30 ms latency and first eligible tick with fail-closed missing-tick handling, but both arms failed the configured zero-breach gate under the gross realized-loss counter. The general evaluator's defaults are not this contract. |

Consequently, the current failure diagnosis is incomplete beyond the entry
funnel: there is no complete saved trace from proposal and mask through policy
choice, decoder, order, executable quote, fill, and exit that explains the
losing path. A new exact candidate/event join over the matched development
baseline traces finds 39,566 random and 43,974 structure-priority decision
rows inside the proposal ledger's 60-minute validity windows, but does not
identify a selected market/limit proposal or bracket; historical A4 PPO
proposal-to-action linkage remains unavailable. The expanded
[`candidate action linkage packet`](../../candidate_action_linkage/README.md)
preserves event, time-window, and unmatched rows. Do not launch an economic
comparison until the shared data, action, execution, risk, budget, and period contract is explicit. The
reusable baseline commands and their non-comparable defaults are described in
the source links above; running them against exposed 2026 data cannot create
confirmatory evidence.

## Evidence-backed RL models

| Model/evidence | Status | Claim boundary |
|---|---|---|
| Hybrid PPO, 100k | Negative screen | One seed; full 2025 replay breached maximum loss. |
| Setup-conditioned PPO, 100k | Negative screen | One seed; full 2025 replay breached maximum loss. |
| Selected matched policy pair, 2M | Withdrawn historical performance result | Run/source identities, resolved configs, and raw/provenance records remain archived. Performance and derived trade-outcome summaries are excluded from current comparison, selection, and confirmation. |
| MTF architecture screen, 2M | Withdrawn historical result | Its [stub packet](../../model_observation_and_action_semantics/mtf_architecture_screen.json) retains source/run provenance and protocol identity only. Performance metrics were removed from current tracked content; do not use the screen as current comparative evidence or as evidence for the registered forthcoming 18-arm benchmark. |
| MTF encoder throughput comparison | Engineering measurement | Runtime comparison only; no trading viability claim. |
| Candidate geometry/history model | Bounded no-go for current labels; model remains untested | The full conditional replay has 769,187/1,067,731 unresolved bracket rows (72.0%), with unresolved shares varying from 84.8%–94.2% through 2025-08 to 15.9% in December. A 12-row deterministic replay audit matched through the same execution function; it is not an independent algorithm. The resolved subset is selected by quote availability and trigger horizon, so it cannot support candidate calibration, supervised fitting, or candidate-value inference. No candidate-conditioned model was trained. |

## Recorded run shapes and decision traces

The [run-artifact inventory](../../model_observation_and_action_semantics/run_artifact_shape_inventory.json)
hashes recognized manifests and training logs under two named output roots. It
found run-recorded MTF sequence widths of 160 for one MTF profile and 322 for
an MTF-reasoning profile, with their configured M3–D1 stream widths also
recorded in the semantic model page. The selected matched-policy artifacts
record M1 `[60, 746]` and a 12-coordinate action schema, with account-vector
widths of 6 for A4A and 10 for A4B. The four extra coordinates are the
one-hot entry-state visibility treatment: the preserved run configs differ
only in `env.entry_state_observation`. This is the intended single-factor
contrast, not an unplanned input mismatch; the arms are not input-identical.
One seed and failed risk gates still prevent a robust policy-benefit claim.
The scan found no qualifying
per-decision selected-setup trace and no trace with proposed entry, stop,
target, and expiration geometry in those roots. The result is limited to the
named artifacts; it does not prove that such a trace never existed elsewhere.
The separate training-only
`evidence/research/candidate_geometry_price_scale/` audit now confirms
finite, ATR-normalized source-zone or retracement-band bounds for all 488,008
active candidate-row occurrences in the selected profile. This is candidate
feature support, not a recovered historical decision/action trace and not
entry/stop/target/expiry, fill, label, or outcome evidence. It therefore does
not close the source-to-policy linkage gap.
The audited reproduction command is in
`evidence/research/model_observation_and_action_semantics/README.md`.

The recent MTF-reasoning artifact is a distinct historical architecture run:
its report records `thesis_mask` with `thesis-overlay-action-v1`, not the
configured C/D `trade_setup_mask` policy contract. Its `[109]` mask shape must
not be used as evidence for the 109-way setup-conditioned run's actual schema.

## Comparative conclusion

Implementations exist for several baseline types, but a complete matched
registry of always-flat, randomized, deterministic rules, supervised scorers,
RL controls, and theoretical upper bounds under identical executable prices,
costs, risk rules, sample periods, and uncertainty methods does not. Do not
claim comparative superiority or select a deployable model. The supported
decision is **no model has demonstrated an economic edge**.

## Recommended next scientific comparison

Only after current-source data, event labels, and execution chronology pass
their gates, preregister a single-factor matched comparison. Keep the
existing setup-conditioned policy as a control. A price-aware candidate scorer
is a hypothesis, not a guaranteed improvement. Specify candidate entry/stop/
target geometry, order expiration, fill censoring, training-only calibration,
costs, risk gate, seeds, and a non-exposed validation design before fitting.
